#!/usr/bin/env python3
"""
gmail_scan.py
-------------
Polls Gmail for unprocessed legal/financial documents since the last run.
Reads last_scan_started from .tracker/state.json to build a date range query.
Writes scan brief to stdout so Claude's SessionStart hook injects it into context.

PREREQUISITE: gws (Google Workspace CLI) must be installed and authenticated.
  Install:      npm install -g @googleworkspace/cli
  Auth (once):  gws auth setup
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PLUGIN_DIR  = Path(__file__).parent.parent
TRACKER_DIR = PLUGIN_DIR / ".tracker"
STATE_FILE  = TRACKER_DIR / "state.json"
RUNS_LOG    = TRACKER_DIR / "runs.jsonl"
SKIP_LOG    = TRACKER_DIR / "skipped.jsonl"
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"

# ── Gmail query terms ─────────────────────────────────────────────────────────
LEGAL_POSITIVE_TERMS = (
    "agreement OR contract OR invoice OR \"purchase order\" OR \"PO#\" "
    "OR NDA OR \"statement of work\" OR SOW OR MSA OR amendment OR addendum "
    "OR lease OR retainer OR quotation OR \"legal notice\" OR \"amount due\" "
    "OR \"payment due\" OR \"net 30\" OR \"net 60\" "
    "OR \"subscription renewal\" OR \"auto-renew\" OR \"renews on\""
)

JUNK_SUBJECT_TERMS = (
    "\"% off\" OR \"sale ends\" OR \"limited time\" OR \"promo code\" "
    "OR \"unsubscribe\" OR \"flash sale\" OR \"black friday\" OR \"cyber monday\""
)


def load_state(state_file: Path = STATE_FILE) -> dict:
    if state_file.exists():
        data = json.loads(state_file.read_text())
        # Migrate old 'last_run' key to new split keys
        if "last_run" in data and "last_scan_started" not in data:
            data["last_scan_started"]   = data.pop("last_run")
            data["last_scan_completed"] = None
        return data
    return {
        "last_scan_started":    None,
        "last_scan_completed":  None,
        "last_run_email_count": 0,
        "total_runs":           0,
    }


def save_state_started(state: dict, state_file: Path = STATE_FILE,
                       timestamp: str = None) -> None:
    """Write state with last_scan_started set. Does NOT set last_scan_completed."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    state["last_scan_started"] = ts
    state["total_runs"] = state.get("total_runs", 0) + 1
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(json.dumps(state, indent=2))


def get_date_range(state: dict) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    base_ts = state.get("last_scan_started")
    if base_ts:
        last_dt  = datetime.fromisoformat(base_ts)
        after_dt = last_dt - timedelta(days=1)  # 1-day overlap buffer
    else:
        after_dt = now - timedelta(days=30)
    return after_dt.strftime("%Y/%m/%d"), now.strftime("%Y/%m/%d")


def build_gmail_query(after_date: str, before_date: str) -> str:
    return (
        f"({LEGAL_POSITIVE_TERMS}) "
        f"after:{after_date} before:{before_date} "
        f"-category:promotions -category:social -category:updates "
        f"-category:forums "
        f"-label:^smartlabel_newsletters "
        f"-subject:({JUNK_SUBJECT_TERMS}) "
        f"(is:unread OR has:attachment)"
    )


def append_jsonl(filepath: Path, record: dict) -> None:
    with open(filepath, "a") as f:
        f.write(json.dumps(record) + "\n")


def log_error(context: str, error: str) -> None:
    append_jsonl(ERROR_LOG, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context":   context,
        "error":     error,
    })


def main(state_file: Path = STATE_FILE):
    state                    = load_state(state_file)
    after_date, before_date  = get_date_range(state)
    query                    = build_gmail_query(after_date, before_date)
    now_iso                  = datetime.now(timezone.utc).isoformat()

    list_cmd = (
        f"gws gmail users messages list "
        f"--params '{{\"userId\":\"me\",\"maxResults\":50,"
        f"\"q\":\"{query}\"}}' --page-all"
    )
    get_cmd = (
        "gws gmail users messages get "
        "--params '{\"userId\":\"me\",\"id\":\"<messageId>\",\"format\":\"full\"}'"
    )
    attachment_cmd = (
        "gws gmail users messages attachments get "
        "--params '{\"userId\":\"me\",\"messageId\":\"<msgId>\",\"id\":\"<attachId>\"}'"
    )

    last_completed = state.get("last_scan_completed") or "Never"

    print(f"""
=== DOC RADAR: Daily Gmail Scan ===
Timestamp       : {now_iso}
Date range      : {after_date} -> {before_date}
Last scan start : {state.get('last_scan_started') or 'Never (first run)'}
Last scan done  : {last_completed}

STEP 1 — Fetch candidate messages:
  {list_cmd}

STEP 2 — For each messageId returned, fetch full content:
  {get_cmd}

STEP 3 — Download any PDF or DOCX attachments:
  {attachment_cmd} > /tmp/attachment_<msgId>.<ext>

STEP 4 — For each retrieved email or attachment, invoke the skill chain:

  Invoke `doc-radar:legal-doc-detector` on the email content (and pass the
  local attachment file path if one was downloaded). The skill chain handles
  everything from that point: attachment reading, junk filtering,
  deduplication, extraction, calendar scheduling, and hash recording.

  DO NOT run scripts directly. The skill chain manages all sub-steps
  (deduplication, checkpointing, hash recording) internally.

After ALL emails are processed, update .tracker/state.json:
  Set last_scan_completed to: {now_iso}

NOTE: If gws is not installed:
  npm install -g @googleworkspace/cli && gws auth setup

NOTE: If gws returns HTTP 429 (rate limit):
  Wait 60 seconds before retrying the list command.
  Process only messages already fetched — do not re-fetch.
  The next session will pick up missed messages via the date overlap buffer.
""")

    # Ensure tracker dir exists before writing state
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    # Record scan start — Claude updates last_scan_completed after all docs processed
    save_state_started(state, state_file, timestamp=now_iso)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error("gmail_scan.py:main", str(e))
        sys.exit(0)  # Never block Claude's session start
