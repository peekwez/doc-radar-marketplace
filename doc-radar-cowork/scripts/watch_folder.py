#!/usr/bin/env python3
"""
watch_folder.py
---------------
Called by the PostToolUse/Write hook. Checks whether a newly written file
is in the watched legal-inbox folder. If it is, outputs a context message
to stdout so Claude processes it through the doc-radar pipeline.

Usage:
    python3 watch_folder.py --file "/path/to/newly/written/file.pdf"
"""

import argparse
import json
import os
import sys
from pathlib import Path
from datetime import datetime, timezone

WATCHED_DIRS = [
    Path.home() / "legal-inbox",
    Path.home() / "Downloads" / "legal-inbox",
    Path.home() / "Desktop" / "legal-inbox",
]

SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".txt", ".eml", ".msg",
    ".xlsx", ".xls", ".csv",  # for PO/invoice spreadsheets
}

PLUGIN_DIR  = Path(__file__).parent.parent
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"


def log_error(context: str, error: str) -> None:
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    with open(ERROR_LOG, "a") as f:
        f.write(json.dumps({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context,
            "error": error,
        }) + "\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=False, default="",
                        help="Path of the file that was just written")
    args = parser.parse_args()

    filepath = args.file.strip()
    if not filepath:
        sys.exit(0)  # No file path, nothing to do

    file_path = Path(filepath)

    # Check if file is in a watched directory
    in_watched_dir = any(
        str(file_path).startswith(str(watched))
        for watched in WATCHED_DIRS
    )

    if not in_watched_dir:
        sys.exit(0)  # Not in a watched folder, ignore

    # Check file extension
    if file_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        sys.exit(0)  # Unsupported type, ignore

    # Check file exists and is non-empty
    if not file_path.exists():
        sys.exit(0)

    if file_path.stat().st_size == 0:
        sys.exit(0)

    # Output context injection for Claude
    print(f"""
=== DOC RADAR: New File Detected in Legal Inbox ===
Timestamp : {datetime.now(timezone.utc).isoformat()}
File path : {file_path}
File name : {file_path.name}
File size : {file_path.stat().st_size:,} bytes
Extension : {file_path.suffix.lower()}

ACTION REQUIRED: A new file has appeared in the legal inbox folder.
1. Read the file content from: {file_path}
2. Run the legal-doc-detector skill to determine if it is a legal document
3. If yes: run doc-extractor (including SHA-256 hash check for duplicates)
4. If not a duplicate: run deadline-scheduler to create calendar events
5. Log results to .tracker/runs.jsonl
""")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error("watch_folder.py:main", str(e))
        sys.exit(0)  # Never block the hook
