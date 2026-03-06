#!/usr/bin/env python3
"""
update_log.py
-------------
Appends an update record to .tracker/runs.jsonl after calendar events are
created. Does NOT rewrite the file — readers resolve final run status by
taking the latest record per sha256.

Usage:
    python3 update_log.py --sha256 "<hash>" --event-ids "id1,id2,id3"
    python3 update_log.py --sha256 "<hash>" --status "calendar_error" --error-msg "..."
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
import jsonl_utils as ju

PLUGIN_DIR  = SCRIPT_DIR.parent
TRACKER_DIR = PLUGIN_DIR / ".tracker"
RUNS_LOG    = TRACKER_DIR / "runs.jsonl"
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sha256",    required=True)
    parser.add_argument("--event-ids", default="")
    parser.add_argument("--status",    default="complete",
                        choices=["complete", "calendar_error",
                                 "calendar_duplicate_skipped"])
    parser.add_argument("--error-msg", default="")
    args = parser.parse_args()

    event_ids = [e.strip() for e in args.event_ids.split(",") if e.strip()]

    # Ensure schema header exists (idempotent)
    ju.init_jsonl(RUNS_LOG, "runs.jsonl")

    # Append update record — never rewrite
    record = {
        "_type":              "update",
        "sha256":             args.sha256.strip(),
        "calendar_event_ids": event_ids,
        "status":             args.status,
        "completed_at":       datetime.now(timezone.utc).isoformat(),
    }
    if args.error_msg:
        record["error"] = args.error_msg

    ju.append_record(RUNS_LOG, record)

    print(json.dumps({
        "status":             args.status,
        "sha256":             args.sha256,
        "calendar_event_ids": event_ids,
    }))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        ju.append_record(ERROR_LOG, {
            "_type":     "error",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context":   "update_log.py:main",
            "error":     str(e),
        })
        sys.exit(1)
