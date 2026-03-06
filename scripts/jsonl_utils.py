#!/usr/bin/env python3
"""
jsonl_utils.py
--------------
Shared utilities for append-only JSONL tracker files.

Every tracker file follows two invariants:
  1. Line 1 is always a schema record (written once at creation).
  2. All subsequent writes are append-only — files are never rewritten.

State is resolved by reading all records and taking the latest per key.
"""
import json
from datetime import datetime, timezone
from pathlib import Path


def init_jsonl(filepath: Path, filename: str) -> None:
    """Create the file with a schema header if it does not already exist."""
    if filepath.exists() and filepath.stat().st_size > 0:
        return
    filepath.parent.mkdir(parents=True, exist_ok=True)
    schema = {
        "_type":      "schema",
        "version":    "1.0",
        "file":       filename,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    with open(filepath, "w") as f:
        f.write(json.dumps(schema) + "\n")


def append_record(filepath: Path, record: dict) -> None:
    """Append a single record to the JSONL file."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a") as f:
        f.write(json.dumps(record) + "\n")


def read_records(filepath: Path) -> list[dict]:
    """Read all non-schema records from a JSONL file."""
    if not filepath.exists():
        return []
    records = []
    for line in filepath.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
            if rec.get("_type") != "schema":
                records.append(rec)
        except json.JSONDecodeError:
            continue
    return records


def latest_per_key(filepath: Path, key: str) -> dict[str, dict]:
    """Return a dict mapping key -> most recent record for that key value."""
    result: dict[str, dict] = {}
    for record in read_records(filepath):
        k = record.get(key)
        if k is not None:
            result[k] = record  # later records overwrite earlier ones
    return result
