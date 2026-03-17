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


def main():
    # Re-resolve tracker dir at call time so monkeypatching env works in tests
    tracker_dir = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
    pending_log = tracker_dir / "pending.jsonl"

    # Resolve latest stage per run_id — later appends win
    latest = ju.latest_per_key(pending_log, "run_id")
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
        "For each item, invoke the skill chain starting from its current stage:",
        "  stage=detected   ->  invoke `doc-radar-cowork:doc-extractor`",
        "  stage=extracted  ->  invoke `doc-radar-cowork:deadline-scheduler`",
        "",
        "DO NOT run scripts directly. The skills handle all pipeline steps.",
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
