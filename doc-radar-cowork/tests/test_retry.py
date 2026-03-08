"""Tests for retry.py — surfaces pending items from previous sessions."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "retry.py"


def run_retry(tmp_path: Path) -> str:
    env = {"RETRY_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, env=env
    )
    return result.stdout


def write_pending(tmp_path: Path, entries: list[dict]) -> None:
    """Write pending.jsonl with schema header + entries."""
    f = tmp_path / "pending.jsonl"
    schema = {"_type": "schema", "version": "1.0", "file": "pending.jsonl", "created_at": "2026-03-05T00:00:00Z"}
    lines = [json.dumps(schema)] + [json.dumps(e) for e in entries]
    f.write_text("\n".join(lines) + "\n")


def test_no_output_when_no_pending_file(tmp_path):
    """No pending.jsonl means no output (silent success)."""
    output = run_retry(tmp_path)
    assert output.strip() == ""


def test_no_output_when_all_complete(tmp_path):
    """Items whose latest stage is complete produce no output."""
    write_pending(tmp_path, [
        {"_type": "checkpoint", "run_id": "r1", "sha256": "abc", "doc_ref": "INV-001",
         "source_id": "gmail:msg1", "stage": "complete", "timestamp": "2026-03-04T10:00:00Z", "error": None},
    ])
    output = run_retry(tmp_path)
    assert output.strip() == ""


def test_outputs_retry_brief_for_pending_items(tmp_path):
    """Items with stage != complete produce a retry brief on stdout."""
    write_pending(tmp_path, [
        {"_type": "checkpoint", "run_id": "r1", "sha256": "abc", "doc_ref": "INV-001",
         "source_id": "gmail:msg1", "stage": "extracted", "timestamp": "2026-03-04T10:00:00Z", "error": None}
    ])
    output = run_retry(tmp_path)
    assert "DOC RADAR: Pending Retry" in output
    assert "INV-001" in output
    assert "extracted" in output


def test_latest_record_per_run_id_wins(tmp_path):
    """If a run_id has both extracted and complete records, complete wins — no output."""
    write_pending(tmp_path, [
        {"_type": "checkpoint", "run_id": "r1", "sha256": "abc", "doc_ref": "INV-001",
         "source_id": "s1", "stage": "extracted", "timestamp": "2026-03-04T10:00:00Z", "error": None},
        {"_type": "checkpoint", "run_id": "r1", "sha256": "abc", "doc_ref": "INV-001",
         "source_id": "s1", "stage": "complete", "timestamp": "2026-03-04T10:05:00Z", "error": None},
    ])
    output = run_retry(tmp_path)
    assert output.strip() == ""


def test_retry_output_uses_namespaced_skills(tmp_path, monkeypatch, capsys):
    import retry
    write_pending(tmp_path, [
        {"_type": "checkpoint", "run_id": "abc123", "sha256": "abc", "doc_ref": "INV-001",
         "source_id": "gmail:msgid", "stage": "extracted",
         "timestamp": "2026-03-06T00:00:00+00:00", "error": None},
    ])
    monkeypatch.setenv("RETRY_TRACKER_DIR", str(tmp_path))
    retry.main()
    out = capsys.readouterr().out
    assert "doc-radar-cowork:doc-extractor" in out
    assert "doc-radar-cowork:deadline-scheduler" in out
    assert "DO NOT run scripts directly" in out
    assert "-> deadline-scheduler ->" not in out
