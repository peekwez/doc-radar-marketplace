#!/usr/bin/env python3
"""
retry.py
--------
Reads .tracker/pending.jsonl and outputs a retry brief to stdout if any
documents are stuck mid-pipeline from a previous session.

Produces NO output if nothing needs retrying — silent exit keeps Claude's
context clean.

Injected into Claude context via the SessionStart hook alongside the
gmail scan brief.
"""
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

SCRIPT_DIR  = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))
import jsonl_utils as ju

PLUGIN_DIR  = SCRIPT_DIR.parent
TRACKER_DIR = Path(os.environ.get("RETRY_TRACKER_DIR", str(PLUGIN_DIR / ".tracker")))
PENDING_LOG = TRACKER_DIR / "pending.jsonl"


def main():
    # Resolve latest stage per run_id — later appends win
    latest = ju.latest_per_key(PENDING_LOG, "run_id")
    pending = [rec for rec in latest.values() if rec.get("stage") != "complete"]

    if not pending:
        sys.exit(0)  # Nothing to retry — no output

    now_iso = datetime.now(timezone.utc).isoformat()

    lines = [
        "",
        "=== DOC RADAR: Pending Retry Items ===",
        f"Timestamp     : {now_iso}",
        f"Items pending : {len(pending)}",
        "",
        "The following documents were partially processed in a previous session.",
        "Process each through the pipeline starting from their current stage:",
        "  extracted -> deadline-scheduler -> checkpoint complete -> record hash",
        "  detected  -> doc-extractor -> deadline-scheduler -> checkpoint complete -> record hash",
        "",
    ]

    for i, item in enumerate(pending, 1):
        lines.append(
            f"{i}. [{item.get('stage', '?').upper()}] {item.get('doc_ref', 'unknown')} "
            f"| source: {item.get('source_id', '?')} "
            f"| since: {item.get('timestamp', '?')[:10]}"
        )
        if item.get("error"):
            lines.append(f"   Error: {item['error']}")

    lines.append("")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit(0)  # Never block session start
