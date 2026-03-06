"""Tests for shared JSONL append-only utilities."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
import jsonl_utils as ju


def test_init_writes_schema_header(tmp_path):
    """init_jsonl writes a schema record as line 1 and nothing else."""
    f = tmp_path / "test.jsonl"
    ju.init_jsonl(f, "test.jsonl")
    lines = [l for l in f.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    rec = json.loads(lines[0])
    assert rec["_type"] == "schema"
    assert rec["file"] == "test.jsonl"
    assert "created_at" in rec


def test_init_is_idempotent(tmp_path):
    """Calling init_jsonl twice does not duplicate the schema header."""
    f = tmp_path / "test.jsonl"
    ju.init_jsonl(f, "test.jsonl")
    ju.init_jsonl(f, "test.jsonl")
    lines = [l for l in f.read_text().splitlines() if l.strip()]
    assert len(lines) == 1


def test_append_record(tmp_path):
    """append_record adds a record after the schema header."""
    f = tmp_path / "test.jsonl"
    ju.init_jsonl(f, "test.jsonl")
    ju.append_record(f, {"key": "val"})
    lines = [l for l in f.read_text().splitlines() if l.strip()]
    assert len(lines) == 2
    assert json.loads(lines[1])["key"] == "val"


def test_read_records_skips_schema(tmp_path):
    """read_records returns data records only, not the schema header."""
    f = tmp_path / "test.jsonl"
    ju.init_jsonl(f, "test.jsonl")
    ju.append_record(f, {"_type": "data", "id": "1"})
    ju.append_record(f, {"_type": "data", "id": "2"})
    records = ju.read_records(f)
    assert all(r["_type"] == "data" for r in records)
    assert len(records) == 2


def test_latest_per_key(tmp_path):
    """latest_per_key returns the most recent record for each key value."""
    f = tmp_path / "test.jsonl"
    ju.init_jsonl(f, "test.jsonl")
    ju.append_record(f, {"run_id": "r1", "stage": "detected"})
    ju.append_record(f, {"run_id": "r1", "stage": "extracted"})
    ju.append_record(f, {"run_id": "r2", "stage": "detected"})
    result = ju.latest_per_key(f, "run_id")
    assert result["r1"]["stage"] == "extracted"
    assert result["r2"]["stage"] == "detected"
