"""Tests for hash_check.py --check-only behaviour."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "hash_check.py"


def test_check_only_does_not_record(tmp_path):
    """--check-only should return 'new' but NOT write to seen_hashes.jsonl."""
    hashes_file = tmp_path / "seen_hashes.jsonl"
    content_file = tmp_path / "doc.txt"
    content_file.write_text("unique content abc123")

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file), "--check-only"],
        capture_output=True, text=True,
        env={"HASH_CHECK_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    )
    output = json.loads(result.stdout)
    assert output["status"] == "new"
    assert not hashes_file.exists(), "check-only must not write to seen_hashes.jsonl"


def test_check_only_detects_existing_duplicate(tmp_path):
    """--check-only correctly identifies a previously recorded hash."""
    content_file = tmp_path / "doc.txt"
    content_file.write_text("duplicate content xyz")
    env = {"HASH_CHECK_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}

    # First: record without --check-only
    subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file)],
        capture_output=True, text=True, env=env
    )

    # Second: check-only on same content — should show duplicate
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file), "--check-only"],
        capture_output=True, text=True, env=env
    )
    output = json.loads(result.stdout)
    assert output["status"] == "duplicate"


def test_normal_mode_records_hash(tmp_path):
    """Without --check-only, hash IS written to seen_hashes.jsonl."""
    hashes_file = tmp_path / "seen_hashes.jsonl"
    content_file = tmp_path / "doc.txt"
    content_file.write_text("recordable content 999")
    env = {"HASH_CHECK_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file)],
        capture_output=True, text=True, env=env
    )
    output = json.loads(result.stdout)
    assert output["status"] == "new"
    assert hashes_file.exists(), "normal mode must write to seen_hashes.jsonl"
