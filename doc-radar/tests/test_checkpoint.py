"""Tests for checkpoint.py — per-doc pipeline state tracking."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "checkpoint.py"


def run_checkpoint(args: list[str], tmp_path: Path) -> dict:
    env = {"CHECKPOINT_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def latest_stages(tmp_path: Path) -> dict[str, str]:
    """Return {run_id: latest_stage} by reading pending.jsonl via jsonl_utils."""
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    import jsonl_utils as ju
    f = tmp_path / "pending.jsonl"
    latest = ju.latest_per_key(f, "run_id")
    return {k: v["stage"] for k, v in latest.items()}


def test_write_detected_checkpoint(tmp_path):
    """Writing a 'detected' checkpoint appends a record to pending.jsonl."""
    run_checkpoint([
        "--run-id", "run-001", "--sha256", "abc123", "--doc-ref", "INV-001",
        "--source-id", "gmail:msg1", "--stage", "detected"
    ], tmp_path)
    stages = latest_stages(tmp_path)
    assert stages.get("run-001") == "detected"


def test_later_stage_wins_per_run_id(tmp_path):
    """Appending a later stage for the same run_id resolves as latest stage."""
    base_args = ["--run-id", "run-002", "--sha256", "def456",
                 "--doc-ref", "PO-002", "--source-id", "gmail:msg2"]
    run_checkpoint(base_args + ["--stage", "detected"], tmp_path)
    run_checkpoint(base_args + ["--stage", "extracted"], tmp_path)
    stages = latest_stages(tmp_path)
    assert stages.get("run-002") == "extracted"


def test_complete_stage_resolves_as_complete(tmp_path):
    """Marking stage=complete resolves as complete (retry.py will skip it)."""
    base_args = ["--run-id", "run-003", "--sha256", "ghi789",
                 "--doc-ref", "CTR-003", "--source-id", "file:/tmp/x.pdf"]
    run_checkpoint(base_args + ["--stage", "detected"], tmp_path)
    run_checkpoint(base_args + ["--stage", "complete"], tmp_path)
    stages = latest_stages(tmp_path)
    assert stages.get("run-003") == "complete"


def test_multiple_docs_tracked_independently(tmp_path):
    """Multiple documents maintain independent checkpoint state."""
    run_checkpoint(["--run-id", "r1", "--sha256", "h1", "--doc-ref", "D1",
                    "--source-id", "s1", "--stage", "detected"], tmp_path)
    run_checkpoint(["--run-id", "r2", "--sha256", "h2", "--doc-ref", "D2",
                    "--source-id", "s2", "--stage", "extracted"], tmp_path)
    stages = latest_stages(tmp_path)
    assert stages["r1"] == "detected"
    assert stages["r2"] == "extracted"


def test_schema_header_is_line_1(tmp_path):
    """pending.jsonl always starts with a schema record."""
    run_checkpoint(["--run-id", "r1", "--sha256", "h1", "--doc-ref", "D1",
                    "--source-id", "s1", "--stage", "detected"], tmp_path)
    lines = [l for l in (tmp_path / "pending.jsonl").read_text().splitlines() if l.strip()]
    first = json.loads(lines[0])
    assert first["_type"] == "schema"
