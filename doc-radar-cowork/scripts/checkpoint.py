#!/usr/bin/env python3
"""
checkpoint.py
-------------
Writes per-document pipeline checkpoints to .tracker/pending.jsonl.
All writes are append-only. retry.py resolves current stage per run_id
by taking the latest record. The 'complete' stage signals no further action.

Usage:
    python3 checkpoint.py --run-id <uuid> --sha256 <hash> --doc-ref <ref> \
                          --source-id <id> --stage <stage>

Stages: detected | extracted | scheduled | complete
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR   = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
import jsonl_utils as ju

PLUGIN_DIR   = SCRIPT_DIR.parent
TRACKER_DIR  = Path(os.environ.get("CHECKPOINT_TRACKER_DIR", str(PLUGIN_DIR / ".tracker")))
PENDING_LOG  = TRACKER_DIR / "pending.jsonl"
VALID_STAGES = {"detected", "extracted", "scheduled", "complete"}

TRACKER_DIR.mkdir(parents=True, exist_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id",    required=True)
    parser.add_argument("--sha256",    required=True)
    parser.add_argument("--doc-ref",   required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--stage",     required=True, choices=VALID_STAGES)
    parser.add_argument("--error",     default=None)
    args = parser.parse_args()

    # Ensure schema header exists (idempotent)
    ju.init_jsonl(PENDING_LOG, "pending.jsonl")

    # Append checkpoint record — always append, never rewrite.
    # retry.py resolves current stage by taking latest record per run_id.
    record = {
        "_type":     "checkpoint",
        "run_id":    args.run_id,
        "sha256":    args.sha256,
        "doc_ref":   args.doc_ref,
        "source_id": args.source_id,
        "stage":     args.stage,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error":     args.error,
    }
    ju.append_record(PENDING_LOG, record)
    print(json.dumps({"status": "ok", "run_id": args.run_id, "stage": args.stage}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)
