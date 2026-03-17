#!/usr/bin/env python3
"""
scan_prompt.py
--------------
MCP-native replacement for gmail_scan.py.

Generates a SessionStart prompt instructing Claude to scan Gmail using the
Gmail MCP connector (search_messages / read_message tools) instead of the
gws CLI.  No external binaries required.

Reads  last_scan_started from .tracker/state.json to build the date range.
Writes scan instructions to stdout so the SessionStart hook injects them
into Claude's context.
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
PLUGIN_DIR  = Path(__file__).parent.parent
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
STATE_FILE  = TRACKER_DIR / "state.json"
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"

# ── Gmail search query ────────────────────────────────────────────────────────
LEGAL_POSITIVE_TERMS = (
    'agreement OR contract OR invoice OR "purchase order" OR "PO#" '
    'OR NDA OR "statement of work" OR SOW OR MSA OR amendment OR addendum '
    'OR lease OR retainer OR quotation OR "legal notice" OR "amount due" '
    'OR "payment due" OR "net 30" OR "net 60" '
    'OR "subscription renewal" OR "auto-renew" OR "renews on"'
)

JUNK_SUBJECT_TERMS = (
    '"% off" OR "sale ends" OR "limited time" OR "promo code" '
    'OR "unsubscribe" OR "flash sale" OR "black friday" OR "cyber monday"'
)


def load_state(state_file: Path = STATE_FILE) -> dict:
    if state_file.exists():
        data = json.loads(state_file.read_text())
        # Migrate old 'last_run' key
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
    """Record that a scan has started. last_scan_completed is set by Claude
    after it finishes processing all documents."""
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
        after_dt = last_dt - timedelta(days=1)   # 1-day overlap buffer
    else:
        after_dt = now - timedelta(days=30)       # first run: last 30 days
    return after_dt.strftime("%Y/%m/%d"), now.strftime("%Y/%m/%d")


DRIVE_LEGAL_NAMES = (
    "name contains 'contract' OR name contains 'invoice' OR name contains 'NDA' "
    "OR name contains 'agreement' OR name contains 'purchase order' OR name contains 'SOW' "
    "OR name contains 'MSA' OR name contains 'lease' OR name contains 'retainer' "
    "OR name contains 'amendment' OR name contains 'quotation'"
)

DRIVE_MIME_TYPES = (
    "mimeType='application/pdf' "
    "OR mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' "
    "OR mimeType='text/plain'"
)


def build_drive_query(after_date: str) -> str:
    """Build a Google Drive API query for legal documents modified since after_date.
    after_date format: YYYY-MM-DD or YYYY/MM/DD (slashes are normalized automatically)
    """
    after_date = after_date.replace("/", "-")
    return (
        f"({DRIVE_LEGAL_NAMES}) "
        f"AND ({DRIVE_MIME_TYPES}) "
        f"AND modifiedTime > '{after_date}T00:00:00' "
        f"AND trashed=false"
    )


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
    state                   = load_state(state_file)
    after_date, before_date = get_date_range(state)
    query                   = build_gmail_query(after_date, before_date)
    now_iso                 = datetime.now(timezone.utc).isoformat()
    last_completed          = state.get("last_scan_completed") or "Never"

    print(f"""=== DOC RADAR: Daily Gmail Scan ===
Timestamp       : {now_iso}
Date range      : {after_date} -> {before_date}
Last scan start : {state.get('last_scan_started') or 'Never (first run)'}
Last scan done  : {last_completed}

STEP 1 — Search Gmail using the Gmail MCP connector (search_messages tool):

  Query: {query}

  Call: search_messages(query=<above query>, max_results=50)

  This returns a list of message IDs and thread IDs.

STEP 2 — For each message ID returned, fetch the full content:

  Call: read_message(message_id=<messageId>)

  This returns the email subject, sender, date, body text, and
  a list of any attachments (name, mimeType, size).

  NOTE: The Gmail MCP connector does not support attachment download.
  If an email has a PDF or DOCX attachment that appears to be the
  primary legal document (not inline):
    - Note the attachment name and size in your processing log.
    - Apply the Three-Signal Test to the email body + subject only.
    - If the body alone passes, process it. If it does not pass but
      the attachment filename strongly suggests a legal doc (e.g.,
      "MSA_2026.pdf", "Invoice_INV-001.docx"), flag the email for
      manual review and log to .tracker/skipped.jsonl with
      skip_reason: "attachment_not_downloadable".

STEP 3 — For each retrieved email, invoke the skill chain:

  Invoke `doc-radar-cowork:legal-doc-detector` on the email content.
  The skill chain handles everything from that point: junk filtering,
  deduplication, extraction, calendar scheduling, and hash recording.

  DO NOT run scripts directly. The skill chain manages all sub-steps
  (deduplication, checkpointing, hash recording) internally.

After ALL emails are processed, update .tracker/state.json:
  Set last_scan_completed to: {now_iso}

NOTE: If the Gmail MCP connector is not available (tool not found):
  Ensure the doc-radar-cowork plugin is enabled in Claude settings and
  the Gmail connector is authorised. No CLI installation is required.

NOTE: If search_messages returns HTTP 429 (rate limit):
  Wait 60 seconds before retrying.
  Process only messages already fetched — do not re-fetch.
  The next session will pick up missed messages via the date overlap buffer.
""")

    drive_query = build_drive_query(after_date)

    print(f"""
=== DOC RADAR: Google Drive Scan ===
Timestamp  : {now_iso}
Date range : modified after {after_date.replace("/", "-")}

STEP A — Search Google Drive for legal document candidates:

  Call: google_drive_search(
    api_query="{drive_query}",
    order_by="modifiedTime desc",
    page_size=50
  )

  This returns a list of files with their IDs, names, MIME types,
  modification dates, and owners.

STEP B — Fetch content for each file returned:

  Call: google_drive_fetch(document_ids=["<fileId>", ...])

  This returns the text content of each file directly — no download needed.
  Pass up to 10 file IDs per call to avoid context overload.

STEP C — For each file fetched, invoke the skill chain:

  Invoke `doc-radar-cowork:legal-doc-detector` on the file content.
  Set source='google_drive' and source_id='<fileId>' when passing to
  doc-extractor. The Drive file URL is:
    https://drive.google.com/file/d/<fileId>/view

  DO NOT run scripts directly. The skill chain manages all sub-steps
  (deduplication, checkpointing, hash recording) internally.

NOTE: If google_drive_search is not available (tool not found):
  Ensure the Google Drive connector is authorised in Claude settings.
  The Drive connector is automatically available in the Claude app.

NOTE: Files already processed are deduplicated via SHA-256. Re-scanning the
  same file will produce a duplicate hash and be skipped automatically.
""")

    # Record scan start — Claude updates last_scan_completed when done
    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    save_state_started(state, state_file, timestamp=now_iso)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error("scan_prompt.py:main", str(e))
        sys.exit(0)   # Never block Claude's session start
