# doc-radar-cowork Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a new `doc-radar-cowork` plugin to the doc-radar-marketplace that replaces all `gws` CLI calls with native Gmail, Google Calendar, and Google Drive MCP connector tool calls — making it work in the Claude desktop app without any CLI installation.

**Architecture:** Mirror the existing `doc-radar` plugin structure exactly, replacing only the three files that contain `gws` calls: `scripts/gmail_scan.py` → `scripts/scan_prompt.py` (outputs MCP-based instructions), `skills/legal-doc-detector/SKILL.md` (Gmail MCP tools), and `skills/deadline-scheduler/SKILL.md` (Calendar MCP tools). All Python utility scripts and the doc-extractor, archiver, digest, and dashboard skills are copied unchanged. A `.mcp.json` is added to declare the three required connectors.

**Tech Stack:** Python 3.10+, pytest, Claude MCP tool protocol (Gmail connector: `search_messages` / `read_message`, Calendar connector: `gcal_list_events` / `gcal_create_event`), plugin manifest JSON.

---

## Task 1: Create feature branch and plugin scaffold

**Files:**
- Create: `doc-radar-cowork/.claude-plugin/plugin.json`
- Create: `doc-radar-cowork/.mcp.json`
- Create: `doc-radar-cowork/.tracker/.gitkeep`
- Create: `doc-radar-cowork/.tracker/state.json`
- Create: `doc-radar-cowork/.tracker/runs.jsonl`
- Create: `doc-radar-cowork/.tracker/seen_hashes.jsonl`
- Create: `doc-radar-cowork/.tracker/skipped.jsonl`
- Create: `doc-radar-cowork/.tracker/errors.jsonl`
- Create: `doc-radar-cowork/.tracker/pending.jsonl`
- Create: `doc-radar-cowork/README.md`
- Modify: `.claude-plugin/marketplace.json`

**Step 1: Create feature branch**

```bash
cd /Users/kwesi/Desktop/doc-radar-marketplace
git checkout -b feat/doc-radar-cowork
```

Expected: `Switched to a new branch 'feat/doc-radar-cowork'`

**Step 2: Create plugin manifest**

Create `doc-radar-cowork/.claude-plugin/plugin.json`:

```json
{
  "name": "doc-radar-cowork",
  "description": "Scans Gmail and watched folders for legal and financially binding documents using native MCP connectors — no CLI required. Extracts key dates, deduplicates via SHA-256, logs to JSONL, and creates Google Calendar events with tiered reminders. Designed for the Claude desktop app (Cowork mode).",
  "version": "1.0.0",
  "author": {
    "name": "Kwesi Apponsah"
  },
  "homepage": "https://github.com/peekwez/doc-radar-marketplace",
  "repository": "https://github.com/peekwez/doc-radar-marketplace",
  "license": "MIT",
  "keywords": ["contracts", "invoices", "legal", "purchase-orders", "calendar", "automation", "gmail", "mcp", "cowork", "deduplication"]
}
```

**Step 3: Create .mcp.json**

Create `doc-radar-cowork/.mcp.json`:

```json
{
  "mcpServers": {
    "gmail": {
      "type": "http",
      "url": "https://gmail.mcp.claude.com/mcp"
    },
    "google-calendar": {
      "type": "http",
      "url": "https://gcal.mcp.claude.com/mcp"
    },
    "google-drive": {
      "type": "http",
      "url": "https://drive.mcp.claude.com/mcp"
    }
  }
}
```

**Step 4: Create .tracker files**

```bash
mkdir -p doc-radar-cowork/.tracker
touch doc-radar-cowork/.tracker/.gitkeep
touch doc-radar-cowork/.tracker/runs.jsonl
touch doc-radar-cowork/.tracker/seen_hashes.jsonl
touch doc-radar-cowork/.tracker/skipped.jsonl
touch doc-radar-cowork/.tracker/errors.jsonl
touch doc-radar-cowork/.tracker/pending.jsonl
```

Create `doc-radar-cowork/.tracker/state.json`:

```json
{
  "last_scan_started": null,
  "last_scan_completed": null,
  "last_run_email_count": 0,
  "total_runs": 0
}
```

**Step 5: Register plugin in marketplace.json**

Add to the `plugins` array in `.claude-plugin/marketplace.json`:

```json
{
  "name": "doc-radar-cowork",
  "source": "./doc-radar-cowork",
  "description": "MCP-native version of doc-radar for the Claude desktop app. Scans Gmail and watched folders for legal/financial documents using Gmail, Calendar, and Drive connectors. No CLI installation required.",
  "version": "1.0.0",
  "author": {
    "name": "Kwesi Apponsah"
  }
}
```

**Step 6: Create README.md**

Create `doc-radar-cowork/README.md`:

```markdown
# doc-radar-cowork

MCP-native version of doc-radar for the Claude desktop app (Cowork mode).

Identical functionality to `doc-radar` but uses Gmail, Google Calendar, and
Google Drive MCP connectors instead of the `gws` CLI. No CLI installation required.

## Requirements

Connect the following in the Claude desktop app:
- Gmail connector
- Google Calendar connector
- Google Drive connector (optional — for Drive attachment reading)

## Known limitations vs doc-radar

- **Attachment download**: The Gmail MCP connector does not support downloading
  binary attachments. Inline email content is processed fully; PDF/DOCX
  attachments are noted but not extracted. If files are also in Google Drive,
  the Drive connector can read them.
- **Email labelling**: The Gmail MCP connector does not support modifying labels.
  Deduplication relies entirely on SHA-256 content hashing (which is the primary
  deduplication mechanism in both versions).
```

**Step 7: Commit scaffold**

```bash
git add doc-radar-cowork/ .claude-plugin/marketplace.json
git commit -m "feat: scaffold doc-radar-cowork plugin with MCP connectors"
```

---

## Task 2: Copy unchanged utility scripts from doc-radar

**Files:**
- Create: `doc-radar-cowork/scripts/checkpoint.py` (copy)
- Create: `doc-radar-cowork/scripts/hash_check.py` (copy)
- Create: `doc-radar-cowork/scripts/jsonl_utils.py` (copy)
- Create: `doc-radar-cowork/scripts/retry.py` (copy)
- Create: `doc-radar-cowork/scripts/update_log.py` (copy)
- Create: `doc-radar-cowork/scripts/watch_folder.py` (copy)
- Create: `doc-radar-cowork/scripts/dashboard.py` (copy)

**Step 1: Copy scripts**

```bash
mkdir -p doc-radar-cowork/scripts
cp doc-radar/scripts/checkpoint.py   doc-radar-cowork/scripts/
cp doc-radar/scripts/hash_check.py   doc-radar-cowork/scripts/
cp doc-radar/scripts/jsonl_utils.py  doc-radar-cowork/scripts/
cp doc-radar/scripts/retry.py        doc-radar-cowork/scripts/
cp doc-radar/scripts/update_log.py   doc-radar-cowork/scripts/
cp doc-radar/scripts/watch_folder.py doc-radar-cowork/scripts/
cp doc-radar/scripts/dashboard.py    doc-radar-cowork/scripts/
```

**Step 2: Verify no gws references in copied scripts**

```bash
grep -rn "gws" doc-radar-cowork/scripts/
```

Expected: no output (none of these scripts use gws).

**Step 3: Commit**

```bash
git add doc-radar-cowork/scripts/
git commit -m "feat: copy unchanged utility scripts from doc-radar"
```

---

## Task 3: Write scan_prompt.py (replaces gmail_scan.py)

**Files:**
- Create: `doc-radar-cowork/scripts/scan_prompt.py`
- Test: `doc-radar-cowork/tests/test_scan_prompt.py`

This is the key difference from doc-radar. Instead of printing gws bash commands for Claude to run, it prints instructions telling Claude to call the Gmail MCP `search_messages` tool directly.

The date-range logic and query-building logic are identical to `gmail_scan.py`.

**Step 1: Write the failing tests first**

Create `doc-radar-cowork/tests/__init__.py` (empty) and `doc-radar-cowork/tests/conftest.py`:

```python
# doc-radar-cowork/tests/conftest.py
import pytest
from pathlib import Path
import tempfile, json

@pytest.fixture
def tmp_tracker(tmp_path):
    state = {
        "last_scan_started": None,
        "last_scan_completed": None,
        "last_run_email_count": 0,
        "total_runs": 0,
    }
    state_file = tmp_path / "state.json"
    state_file.write_text(json.dumps(state))
    return tmp_path
```

Create `doc-radar-cowork/tests/test_scan_prompt.py`:

```python
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from scan_prompt import load_state, get_date_range, build_gmail_query, build_mcp_prompt


def test_load_state_missing_file(tmp_path):
    state = load_state(tmp_path / "nonexistent.json")
    assert state["last_scan_started"] is None
    assert state["total_runs"] == 0


def test_load_state_existing(tmp_path):
    data = {"last_scan_started": "2026-03-06T10:00:00+00:00",
            "last_scan_completed": None, "last_run_email_count": 0, "total_runs": 3}
    f = tmp_path / "state.json"
    f.write_text(json.dumps(data))
    state = load_state(f)
    assert state["total_runs"] == 3
    assert state["last_scan_started"] == "2026-03-06T10:00:00+00:00"


def test_get_date_range_first_run():
    state = {"last_scan_started": None}
    after, before = get_date_range(state)
    now = datetime.now(timezone.utc)
    after_dt = datetime.strptime(after, "%Y/%m/%d").replace(tzinfo=timezone.utc)
    # First run: 30-day lookback
    assert (now - after_dt).days >= 29


def test_get_date_range_subsequent_run():
    last = datetime.now(timezone.utc) - timedelta(days=2)
    state = {"last_scan_started": last.isoformat()}
    after, before = get_date_range(state)
    after_dt = datetime.strptime(after, "%Y/%m/%d").replace(tzinfo=timezone.utc)
    # Should be 1-day overlap buffer before last_scan_started
    assert (last - after_dt).days >= 0


def test_build_gmail_query_contains_required_terms():
    q = build_gmail_query("2026/03/06", "2026/03/07")
    assert "invoice" in q
    assert "agreement" in q
    assert "after:2026/03/06" in q
    assert "before:2026/03/07" in q
    assert "-category:promotions" in q


def test_build_mcp_prompt_contains_search_messages():
    query = "invoice after:2026/03/06"
    prompt = build_mcp_prompt(query, "2026/03/06", "2026/03/07",
                              "2026-03-07T20:00:00+00:00", "Never")
    assert "search_messages" in prompt
    assert "read_message" in prompt
    assert "doc-radar:legal-doc-detector" in prompt
    assert "search_messages" in prompt
    # Must NOT contain gws references
    assert "gws" not in prompt
```

**Step 2: Run tests to confirm they fail**

```bash
cd doc-radar-cowork
python3 -m pytest tests/test_scan_prompt.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError: No module named 'scan_prompt'`

**Step 3: Write scan_prompt.py**

Create `doc-radar-cowork/scripts/scan_prompt.py`:

```python
#!/usr/bin/env python3
"""
scan_prompt.py
--------------
Generates the SessionStart hook prompt for doc-radar-cowork.
Outputs instructions telling Claude to use the Gmail MCP connector's
search_messages and read_message tools — no gws CLI required.

Identical date-range and query logic to doc-radar/scripts/gmail_scan.py.
"""

import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PLUGIN_DIR  = Path(__file__).parent.parent
TRACKER_DIR = PLUGIN_DIR / ".tracker"
STATE_FILE  = TRACKER_DIR / "state.json"
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"

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
        after_dt = last_dt - timedelta(days=1)
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


def build_mcp_prompt(query: str, after_date: str, before_date: str,
                     now_iso: str, last_completed: str) -> str:
    return f"""
=== DOC RADAR (COWORK): Daily Gmail Scan ===
Timestamp       : {now_iso}
Date range      : {after_date} -> {before_date}
Last scan done  : {last_completed}

STEP 1 — Fetch candidate messages using the Gmail MCP connector:

  Call the search_messages tool with:
    query: "{query}"

  This returns a list of messages with their IDs and snippets.

STEP 2 — For each message returned, fetch its full content:

  Call the read_message tool with:
    message_id: <id from search results>

  This returns the full message body, sender, subject, date,
  and attachment metadata (filename, mimeType, attachmentId).

  NOTE: The Gmail MCP connector does not support downloading binary
  attachments directly. If an email has a PDF or DOCX attachment,
  note the filename and attachmentId in the extraction record.
  If the file is also present in Google Drive, use the Drive MCP
  connector to read it.

STEP 3 — For each retrieved email, invoke the skill chain:

  Invoke `doc-radar:legal-doc-detector` on the email content.
  Pass: subject, sender, date, full body text, and attachment
  metadata (filename + mimeType). The skill chain handles junk
  filtering, deduplication, extraction, and calendar scheduling.

  DO NOT run scripts directly. The skill chain manages all sub-steps.

After ALL emails are processed, update .tracker/state.json:
  Set last_scan_completed to: {now_iso}

NOTE: If the Gmail connector is not connected:
  Open the Claude desktop app settings and connect the Gmail connector.
  Then restart the session — this scan will run automatically.

NOTE: If search_messages returns a rate limit error (429):
  Wait 60 seconds and retry. Process only messages already fetched.
  The next session will pick up missed messages via the date overlap buffer.
"""


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

    print(build_mcp_prompt(query, after_date, before_date, now_iso, last_completed))

    TRACKER_DIR.mkdir(parents=True, exist_ok=True)
    save_state_started(state, state_file, timestamp=now_iso)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error("scan_prompt.py:main", str(e))
        sys.exit(0)  # Never block Claude's session start
```

**Step 4: Run tests and confirm they pass**

```bash
cd doc-radar-cowork
python3 -m pytest tests/test_scan_prompt.py -v
```

Expected: all 6 tests PASS.

**Step 5: Confirm no gws references in entire plugin**

```bash
grep -rn "gws" doc-radar-cowork/scripts/
```

Expected: no output.

**Step 6: Commit**

```bash
git add doc-radar-cowork/scripts/scan_prompt.py doc-radar-cowork/tests/
git commit -m "feat: add scan_prompt.py — MCP-native Gmail scan prompt (no gws)"
```

---

## Task 4: Copy unchanged skills from doc-radar

**Files:**
- Create: `doc-radar-cowork/skills/doc-extractor/SKILL.md` (copy)
- Create: `doc-radar-cowork/skills/archiver/SKILL.md` (copy)
- Create: `doc-radar-cowork/skills/digest/SKILL.md` (copy)
- Create: `doc-radar-cowork/skills/dashboard/SKILL.md` (copy)

**Step 1: Copy skills**

```bash
mkdir -p doc-radar-cowork/skills/doc-extractor
mkdir -p doc-radar-cowork/skills/archiver
mkdir -p doc-radar-cowork/skills/digest
mkdir -p doc-radar-cowork/skills/dashboard

cp doc-radar/skills/doc-extractor/SKILL.md  doc-radar-cowork/skills/doc-extractor/
cp doc-radar/skills/archiver/SKILL.md       doc-radar-cowork/skills/archiver/
cp doc-radar/skills/digest/SKILL.md         doc-radar-cowork/skills/digest/
cp doc-radar/skills/dashboard/SKILL.md      doc-radar-cowork/skills/dashboard/
```

**Step 2: Confirm no gws references in copied skills**

```bash
grep -rn "gws" doc-radar-cowork/skills/doc-extractor/ \
               doc-radar-cowork/skills/archiver/ \
               doc-radar-cowork/skills/digest/ \
               doc-radar-cowork/skills/dashboard/
```

Expected: no output.

**Step 3: Commit**

```bash
git add doc-radar-cowork/skills/
git commit -m "feat: copy unchanged skills (doc-extractor, archiver, digest, dashboard)"
```

---

## Task 5: Write legal-doc-detector/SKILL.md (Gmail MCP version)

**Files:**
- Create: `doc-radar-cowork/skills/legal-doc-detector/SKILL.md`

This file is identical to `doc-radar/skills/legal-doc-detector/SKILL.md` except the entire **"Gmail Access via gws"** section is replaced with **"Gmail Access via MCP"**.

**Step 1: Create the file**

Create `doc-radar-cowork/skills/legal-doc-detector/SKILL.md`. Copy the full content of `doc-radar/skills/legal-doc-detector/SKILL.md`, then replace the section from `## Gmail Access via gws` through the closing code block (ending at `Always use --dry-run before modifying...`) with:

```markdown
## Gmail Access via MCP

To fetch emails for scanning, call these Gmail MCP connector tools directly
(no Bash or CLI required):

**Step 1 — Search for candidate messages:**

Call `search_messages` with:
```
query: "(agreement OR contract OR invoice OR ...) after:YYYY/MM/DD ..."
```
Returns: list of `{ id, threadId, snippet, subject, from, date }` objects.

**Step 2 — Fetch full message content:**

For each `id` returned, call `read_message` with:
```
message_id: <id>
```
Returns: `{ subject, from, date, body (plain text), attachments: [{ filename, mimeType, attachmentId }] }`

**Step 3 — Attachment handling (limited):**

The Gmail MCP connector does not support downloading binary attachments.
- If the message body contains the document inline: process it directly.
- If there is a PDF or DOCX attachment: note the filename and attachmentId
  in the extraction record. If the file also exists in Google Drive, call
  the Drive MCP `read_file` tool to extract its text content.
- If neither is possible: log to `.tracker/skipped.jsonl` with
  `skip_reason: "attachment_not_downloadable"` and continue.

**Step 4 — Marking processed emails:**

The Gmail MCP connector does not support modifying labels. Deduplication
is handled entirely by SHA-256 content hashing in `doc-radar:doc-extractor`.
Do not attempt to label emails.
```

**Step 2: Verify the new file has no gws references**

```bash
grep -n "gws" doc-radar-cowork/skills/legal-doc-detector/SKILL.md
```

Expected: no output.

**Step 3: Verify search_messages and read_message are present**

```bash
grep -n "search_messages\|read_message" doc-radar-cowork/skills/legal-doc-detector/SKILL.md
```

Expected: at least 2 matches.

**Step 4: Commit**

```bash
git add doc-radar-cowork/skills/legal-doc-detector/
git commit -m "feat: legal-doc-detector — replace gws Gmail with MCP search_messages/read_message"
```

---

## Task 6: Write deadline-scheduler/SKILL.md (Calendar MCP version)

**Files:**
- Create: `doc-radar-cowork/skills/deadline-scheduler/SKILL.md`

Identical to `doc-radar/skills/deadline-scheduler/SKILL.md` except:
1. The **"Calendar Access via gws"** section is replaced with **"Calendar Access via MCP"**
2. The **"Dry-Run Mode"** section removes the `--dry-run` flag references
3. The **Step 1** duplicate check uses `gcal_list_events` instead of `gws calendar events list`
4. All `gws calendar events insert` calls become `gcal_create_event` calls
5. **Step 6 error handling** is updated (no gws command to reference)

**Step 1: Create the file**

Create `doc-radar-cowork/skills/deadline-scheduler/SKILL.md`. Copy the full content of `doc-radar/skills/deadline-scheduler/SKILL.md`, then apply these replacements:

**Replace** `## Calendar Access via gws` section with:

```markdown
## Calendar Access via MCP

All calendar operations use the Google Calendar MCP connector tools directly.
No Bash or CLI required.

**Duplicate check before creating:**

Call `gcal_list_events` with:
```
q: "<doc_ref or party names>"
timeMin: "<today in ISO 8601>"
timeMax: "<expiry_date + 180 days in ISO 8601>"
```

**Create an event:**

Call `gcal_create_event` with the full event object. Example:
```json
{
  "summary": "PAYMENT DUE: INV-001 — Acme Corp — USD 12500",
  "start": { "date": "2026-04-15" },
  "end":   { "date": "2026-04-16" },
  "description": "...",
  "colorId": "5",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email", "minutes": 10080 },
      { "method": "popup", "minutes": 1440  }
    ]
  }
}
```
```

**Replace** the `## Dry-Run Mode` section's gws flag references:

Change `Use --dry-run on every gws calendar events insert call` to:
`Do NOT call gcal_create_event — only build and display the payloads.`

**Replace** all `gws calendar events insert` references in Step 3 onwards with `gcal_create_event`.

**Replace** `gws calendar events list` in Step 1 with `gcal_list_events`.

**In Step 6 error handling**, replace:

```
If `gws calendar events insert` fails:
```

with:

```
If `gcal_create_event` fails:
```

**Step 2: Verify no gws references**

```bash
grep -n "gws" doc-radar-cowork/skills/deadline-scheduler/SKILL.md
```

Expected: no output.

**Step 3: Verify MCP tool names are present**

```bash
grep -n "gcal_create_event\|gcal_list_events" doc-radar-cowork/skills/deadline-scheduler/SKILL.md
```

Expected: at least 4 matches.

**Step 4: Commit**

```bash
git add doc-radar-cowork/skills/deadline-scheduler/
git commit -m "feat: deadline-scheduler — replace gws calendar CLI with gcal_create_event/gcal_list_events"
```

---

## Task 7: Write doc-radar-agent.md (MCP tools version)

**Files:**
- Create: `doc-radar-cowork/agents/doc-radar-agent.md`

Identical to `doc-radar/agents/doc-radar-agent.md` except the **"Tools Available"** and **"Prerequisites"** sections are rewritten.

**Step 1: Create the file**

Create `doc-radar-cowork/agents/doc-radar-agent.md`. Copy content from `doc-radar/agents/doc-radar-agent.md`, then replace the `## Tools Available` section with:

```markdown
## Tools Available

- **Gmail MCP connector** — primary source for email scanning:
  - `search_messages` — search inbox with date-range + legal keyword query
  - `read_message` — fetch full message content (body, subject, sender, attachment metadata)
  - Note: attachment download and label modification are not supported by this connector
- **Google Calendar MCP connector** — calendar event management:
  - `gcal_list_events` — duplicate event check before creating
  - `gcal_create_event` — create deadline/reminder events with tiered reminders
- **Google Drive MCP connector** (optional) — attachment text extraction:
  - Use to read PDF/DOCX files if they also exist in the user's Drive
- **Read** — read attachment content from `~/legal-inbox/`
- **Python scripts** (via Bash):
  - `scripts/hash_check.py` — SHA-256 deduplication
  - `scripts/update_log.py` — update runs.jsonl with event IDs
  - `scripts/checkpoint.py` — pipeline stage tracking
```

Replace the `## Prerequisites` section with:

```markdown
## Prerequisites

Ensure the following connectors are connected in the Claude desktop app:
- Gmail connector
- Google Calendar connector
- Google Drive connector (optional — for Drive-hosted attachments)

No CLI installation required. If a connector is not connected, the scan
will proceed but skip emails that require that connector's functionality.
```

**Step 2: Verify no gws references**

```bash
grep -n "gws" doc-radar-cowork/agents/doc-radar-agent.md
```

Expected: no output.

**Step 3: Commit**

```bash
git add doc-radar-cowork/agents/
git commit -m "feat: doc-radar-agent — update tools list to MCP connectors, remove gws prerequisites"
```

---

## Task 8: Write hooks.json

**Files:**
- Create: `doc-radar-cowork/hooks/hooks.json`

**Step 1: Create the file**

Create `doc-radar-cowork/hooks/hooks.json`:

```json
{
  "description": "doc-radar-cowork event hooks",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/scan_prompt.py 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/retry.py 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/watch_folder.py --file \"$(echo $CLAUDE_HOOK_INPUT | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))\" 2>/dev/null)\" 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
          }
        ]
      }
    ]
  }
}
```

**Step 2: Commit**

```bash
git add doc-radar-cowork/hooks/
git commit -m "feat: add hooks.json — SessionStart calls scan_prompt.py, PostToolUse watches ~/legal-inbox"
```

---

## Task 9: Copy remaining tests and run full test suite

**Files:**
- Create: `doc-radar-cowork/tests/test_hash_check.py` (copy)
- Create: `doc-radar-cowork/tests/test_checkpoint.py` (copy)
- Create: `doc-radar-cowork/tests/test_jsonl_utils.py` (copy)
- Create: `doc-radar-cowork/tests/test_retry.py` (copy)
- Create: `doc-radar-cowork/tests/test_dashboard.py` (copy)

**Step 1: Copy tests**

```bash
cp doc-radar/tests/test_hash_check.py   doc-radar-cowork/tests/
cp doc-radar/tests/test_checkpoint.py   doc-radar-cowork/tests/
cp doc-radar/tests/test_jsonl_utils.py  doc-radar-cowork/tests/
cp doc-radar/tests/test_retry.py        doc-radar-cowork/tests/
cp doc-radar/tests/test_dashboard.py    doc-radar-cowork/tests/
```

**Step 2: Run full test suite**

```bash
cd doc-radar-cowork
python3 -m pytest tests/ -v
```

Expected: all tests PASS. If any fail due to path differences, update the import path at the top of the failing test to use `doc-radar-cowork/scripts/` instead of `doc-radar/scripts/`.

**Step 3: Verify zero gws references in entire plugin**

```bash
grep -rn "gws" doc-radar-cowork/
```

Expected: no output.

**Step 4: Commit**

```bash
git add doc-radar-cowork/tests/
git commit -m "feat: copy and verify remaining tests — full suite passing, zero gws references"
```

---

## Task 10: Final verification and PR

**Step 1: Check complete file structure matches expectations**

```bash
find doc-radar-cowork -type f | sort
```

Expected output includes: `.claude-plugin/plugin.json`, `.mcp.json`, `.tracker/state.json`, `agents/doc-radar-agent.md`, `hooks/hooks.json`, `scripts/scan_prompt.py` + 7 other scripts, `skills/` with 6 SKILL.md files, `tests/` with 7 test files, `README.md`.

**Step 2: Confirm marketplace.json has both plugins**

```bash
python3 -c "import json; m=json.load(open('.claude-plugin/marketplace.json')); print([p['name'] for p in m['plugins']])"
```

Expected: `['doc-radar', 'doc-radar-cowork']`

**Step 3: Run full test suite one final time from repo root**

```bash
cd doc-radar-cowork && python3 -m pytest tests/ -v
```

Expected: all tests PASS.

**Step 4: Push and open PR**

```bash
git push -u origin feat/doc-radar-cowork
gh pr create \
  --title "feat: add doc-radar-cowork — MCP-native version for Claude desktop app" \
  --body "Adds doc-radar-cowork alongside the existing doc-radar plugin.

## What changed
- New plugin \`doc-radar-cowork/\` targeting Claude desktop app Cowork mode
- Replaces all \`gws\` CLI calls with Gmail and Google Calendar MCP connector tools
- \`.mcp.json\` declares gmail, google-calendar, and google-drive connectors
- \`scan_prompt.py\` replaces \`gmail_scan.py\` — same date logic, MCP instructions instead of gws commands
- \`legal-doc-detector\` SKILL uses \`search_messages\` + \`read_message\` instead of gws bash
- \`deadline-scheduler\` SKILL uses \`gcal_create_event\` + \`gcal_list_events\` instead of gws bash
- All utility scripts and unchanged skills copied from doc-radar
- Full test suite passing, zero gws references in new plugin

## Known limitations
- Gmail MCP has no attachment download → attachments noted but not extracted (Drive fallback available)
- Gmail MCP has no label/modify → email deduplication relies entirely on SHA-256 hashing (already the primary mechanism)"
```
