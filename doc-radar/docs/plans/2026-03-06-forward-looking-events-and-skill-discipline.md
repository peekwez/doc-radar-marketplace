# Doc Radar Enhancements: Skill Discipline, PDF Extraction, Source Linking & Operational Tools

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix agent skill-chain bypass; add PDF extraction via Claude's built-in Read tool; link calendar events to source emails; add confidence scoring, dry-run mode, digest skill, archiver skill, HTML dashboard, rate limit handling, and null-date warnings.

**Architecture:** Twelve independent improvements across skills, scripts, and new skills. No breaking changes to the JSONL schema — all additions are additive fields. Skills are the authoritative processing layer; scripts only generate context injections and reports. Dashboard is a self-contained HTML file (Tailwind CDN + Chart.js CDN) that Python generates by embedding data directly.

**Tech Stack:** Python 3, pytest, SKILL.md (Markdown), HTML/CSS/JS, Tailwind CSS Play CDN, Chart.js CDN, Gmail URL format (`https://mail.google.com/mail/u/0/#all/<messageId>`)

---

## Scope Summary

| # | Area | Change | Type |
|---|------|--------|------|
| 1 | `gmail_scan.py` + `retry.py` | Replace manual step lists with `doc-radar:legal-doc-detector` invocation | Python + tests |
| 2 | `legal-doc-detector` skill | Add PDF/DOCX reading via Claude `Read` tool | SKILL.md |
| 3 | `deadline-scheduler` skill | Embed Gmail source URL in every calendar event description | SKILL.md |
| 4 | `doc-extractor` skill | Add per-field confidence scores to extraction output | SKILL.md |
| 5 | `doc-extractor` skill | Surface visible warning when all date fields are null | SKILL.md |
| 6 | `gmail_scan.py` | Add HTTP 429 rate-limit handling note to hook output | Python + tests |
| 7 | `deadline-scheduler` skill | Add dry-run mode (preview events without inserting) | SKILL.md |
| 8 | New skill: `digest` | Summarise upcoming deadlines from `runs.jsonl` (user-invoked: `/doc-radar:digest`) | SKILL.md |
| 9 | New skill: `archiver` | Mark documents paid/completed/resolved | SKILL.md |
| 10 | New script: `dashboard.py` | Generate self-contained HTML dashboard (Tailwind CDN + Chart.js) | Python + tests |
| 10b | New skill: `dashboard` | `/doc-radar:dashboard` — generate and open the HTML report | SKILL.md |
| 11 | Path portability | Replace hardcoded `~/.claude/plugins/doc-radar/scripts/` with `${CLAUDE_SKILL_DIR}/../../scripts/` | All SKILL.md files |
| 12 | Push + PR | — | Git |

---

### Task 1: Fix `gmail_scan.py` and `retry.py` to enforce skill-chain invocation

**Files:**
- Modify: `doc-radar/scripts/gmail_scan.py`
- Modify: `doc-radar/scripts/retry.py`
- Test: `doc-radar/tests/test_gmail_scan.py`
- Test: `doc-radar/tests/test_retry.py`

**Background:** `gmail_scan.py` prints a numbered step list including "Run hash_check.py", "Run doc-extractor skill", etc. Claude reads these as direct execution instructions and follows them literally, bypassing the skill system. `retry.py` has the same problem with bare pipeline names.

**Step 1: Write failing tests for gmail_scan.py**

Open `doc-radar/tests/test_gmail_scan.py` and add:

```python
def test_gmail_scan_output_uses_skill_chain(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "doc-radar:legal-doc-detector" in out
    assert "hash_check.py" not in out
    assert "doc-extractor skill" not in out
    assert "deadline-scheduler skill" not in out

def test_gmail_scan_warns_against_direct_scripts(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "DO NOT run scripts directly" in out
```

**Step 2: Write failing test for retry.py**

Open `doc-radar/tests/test_retry.py` and add:

```python
def test_retry_output_uses_namespaced_skills(tmp_path, monkeypatch, capsys):
    import json, retry
    pending_file = tmp_path / "pending.jsonl"
    pending_file.write_text(json.dumps({
        "run_id": "abc123", "stage": "extracted",
        "doc_ref": "INV-001", "source_id": "gmail:msgid",
        "timestamp": "2026-03-06T00:00:00+00:00"
    }) + "\n")
    monkeypatch.setenv("RETRY_TRACKER_DIR", str(tmp_path))
    retry.main()
    out = capsys.readouterr().out
    assert "doc-radar:doc-extractor" in out
    assert "doc-radar:deadline-scheduler" in out
    assert "DO NOT run scripts directly" in out
    assert "-> deadline-scheduler ->" not in out
```

**Step 3: Run all three tests to confirm they fail**

```bash
cd doc-radar && python -m pytest tests/test_gmail_scan.py::test_gmail_scan_output_uses_skill_chain tests/test_gmail_scan.py::test_gmail_scan_warns_against_direct_scripts tests/test_retry.py::test_retry_output_uses_namespaced_skills -v
```

Expected: All FAIL.

**Step 4: Update `gmail_scan.py` — replace the numbered step list**

In `gmail_scan.py`, replace the `print(f"""...""")` block's body with:

```python
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

  DO NOT run scripts (hash_check.py, checkpoint.py, update_log.py) directly.
  DO NOT manually perform steps the skills define internally.

After ALL emails are processed, update .tracker/state.json:
  Set last_scan_completed to: {now_iso}

NOTE: If gws is not installed:
  npm install -g @googleworkspace/cli && gws auth setup
""")
```

**Step 5: Update `retry.py` — replace pipeline description lines**

Replace the `lines = [...]` list with:

```python
    lines = [
        "",
        "=== DOC RADAR: Pending Retry Items ===",
        f"Timestamp     : {now_iso}",
        f"Items pending : {len(pending)}",
        "",
        "The following documents were partially processed in a previous session.",
        "For each item, invoke the skill chain starting from its current stage:",
        "  stage=detected   ->  invoke `doc-radar:doc-extractor`",
        "  stage=extracted  ->  invoke `doc-radar:deadline-scheduler`",
        "",
        "DO NOT run scripts directly. The skills handle all pipeline steps.",
        "",
    ]
```

**Step 6: Run all three tests to confirm they pass**

```bash
cd doc-radar && python -m pytest tests/test_gmail_scan.py::test_gmail_scan_output_uses_skill_chain tests/test_gmail_scan.py::test_gmail_scan_warns_against_direct_scripts tests/test_retry.py::test_retry_output_uses_namespaced_skills -v
```

Expected: All PASS.

**Step 7: Run full test suite**

```bash
cd doc-radar && python -m pytest tests/ -v
```

**Step 8: Commit**

```bash
git add doc-radar/scripts/gmail_scan.py doc-radar/scripts/retry.py doc-radar/tests/test_gmail_scan.py doc-radar/tests/test_retry.py
git commit -m "fix: instruct Claude to invoke skill chain; remove manual script steps from hook output"
```

---

### Task 2: Add PDF/attachment reading to `legal-doc-detector` SKILL.md

**Files:**
- Modify: `doc-radar/skills/legal-doc-detector/SKILL.md`

**Step 1: Add `## Attachment Handling` section**

Open `doc-radar/skills/legal-doc-detector/SKILL.md`. Insert the following section immediately before `## Trigger Conditions`:

```markdown
---

## Attachment Handling

When an email has a PDF, DOCX, or plain-text attachment downloaded to a local
path (e.g. `/tmp/attachment_<msgId>.pdf`):

1. Use the `Read` tool on the local file path to extract its text content.
   Claude's built-in Read tool handles PDFs natively — no OCR service needed.
2. Treat the extracted text as the document body for the Three-Signal Test
   and document type detection.
3. Pass both the email metadata (subject, sender, date) AND the extracted
   attachment text to `doc-radar:doc-extractor` as the document content.

If the `Read` tool cannot extract text (binary-only, encrypted, or corrupted
file), log to `.tracker/skipped.jsonl`:
```json
{
  "timestamp": "<ISO 8601 UTC>",
  "source_id": "<messageId>",
  "skip_reason": "unreadable_attachment",
  "filename": "<attachment filename>"
}
```
Then stop — do not invoke `doc-radar:doc-extractor` for this item.
```

**Step 2: Verify placement — re-read the file and confirm `## Attachment Handling` appears before `## Trigger Conditions`**

**Step 3: Commit**

```bash
git add doc-radar/skills/legal-doc-detector/SKILL.md
git commit -m "feat(legal-doc-detector): read PDF/DOCX attachments via Claude built-in Read tool"
```

---

### Task 3: Add Gmail source URL to calendar events in `deadline-scheduler` SKILL.md

**Files:**
- Modify: `doc-radar/skills/deadline-scheduler/SKILL.md`

**Step 1: Update the Event Description Template**

In `## Step 3 — Event Description Template`, find the `DOCUMENT DETAILS` block and replace it:

Old:
```
DOCUMENT DETAILS
────────────────
Type      : [doc_type]
Reference : [doc_ref]
Governing : [jurisdiction]
Source    : [gmail message link or file path]
SHA-256   : [first 12 chars of hash]
Processed : [ISO timestamp]
```

New:
```
DOCUMENT DETAILS
────────────────
Type      : [doc_type]
Reference : [doc_ref]
Governing : [jurisdiction]
SHA-256   : [first 12 chars of hash]
Processed : [ISO timestamp]

SOURCE
──────
[construct URL based on source field:]
  gmail        -> https://mail.google.com/mail/u/0/#all/[source_id]
  file_drop    -> [source_id — full file path]
  direct_paste -> Pasted directly in conversation
```

**Step 2: Add source URL construction note**

Immediately before the description template code block, add:

```markdown
**Source URL construction rule:**
Always include the SOURCE section. For Gmail sources:
`"https://mail.google.com/mail/u/0/#all/" + source_id`
This links the calendar event to the originating email for audit trail.
```

**Step 3: Commit**

```bash
git add doc-radar/skills/deadline-scheduler/SKILL.md
git commit -m "feat(deadline-scheduler): add Gmail source URL to calendar event descriptions"
```

---

### Task 4: Add per-field confidence scores to `doc-extractor` SKILL.md

**Files:**
- Modify: `doc-radar/skills/doc-extractor/SKILL.md`

**Step 1: Add `confidence` block to the extraction JSON schema**

In `## Step 2 — Extract Fields`, after the closing `}` of the main JSON schema, add:

```markdown
Additionally, append a `confidence` block:

```json
"confidence": {
  "overall":      "high | medium | low",
  "due_date":     "high | medium | low | null",
  "expiry_date":  "high | medium | low | null",
  "renewal_date": "high | medium | low | null",
  "value_amount": "high | medium | low | null",
  "parties":      "high | medium | low"
}
```

**Confidence levels:**
- `high` — field is explicitly stated in a clearly formatted way
- `medium` — field is inferred (e.g., "Net 30" from invoice date)
- `low` — field is guessed from ambiguous language; note in `extraction_notes`
- `null` — field not found
```

**Step 2: Add `"confidence": {...}` to the Step 3 example JSON record in `runs.jsonl`**

**Step 3: Commit**

```bash
git add doc-radar/skills/doc-extractor/SKILL.md
git commit -m "feat(doc-extractor): add per-field confidence scores to extraction output"
```

---

### Task 5: Add null-date extraction warning to `doc-extractor` SKILL.md

**Files:**
- Modify: `doc-radar/skills/doc-extractor/SKILL.md`

**Step 1: Add Step 2.5 — Null-Date Warning**

In `doc-radar/skills/doc-extractor/SKILL.md`, insert after `## Step 2 — Extract Fields`:

```markdown
---

## Step 2.5 — Null-Date Warning

After extraction, check all actionable date fields:
`effective_date`, `expiry_date`, `due_date`, `renewal_date`, `cancel_by_date`,
`milestone_dates`.

If every one of these is `null`, output a visible warning before continuing:

```
⚠ WARNING: No actionable dates extracted from [doc_type] [doc_ref]
  (source: [source_id]). All date fields are null.
  Calendar events cannot be created. Review extraction_notes for context.
  Proceeding to log the record.
```

Still write the record to `runs.jsonl` with `status: "no_dates_extracted"`.
Still invoke `doc-radar:deadline-scheduler` — it will create no events but
completes the pipeline cleanly.
```

**Step 2: Commit**

```bash
git add doc-radar/skills/doc-extractor/SKILL.md
git commit -m "feat(doc-extractor): warn when all date fields are null after extraction"
```

---

### Task 6: Add rate-limit handling to `gmail_scan.py`

**Files:**
- Modify: `doc-radar/scripts/gmail_scan.py`
- Test: `doc-radar/tests/test_gmail_scan.py`

**Step 1: Write failing test**

```python
def test_gmail_scan_output_includes_rate_limit_guidance(capsys, tmp_path):
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "429" in out or "rate limit" in out.lower()
```

**Step 2: Run test to confirm it fails**

```bash
cd doc-radar && python -m pytest tests/test_gmail_scan.py::test_gmail_scan_output_includes_rate_limit_guidance -v
```

**Step 3: Add rate-limit note to the `print` block**

After the `NOTE: If gws is not installed:` line, add:

```python
"""
NOTE: If gws returns HTTP 429 (rate limit):
  Wait 60 seconds before retrying the list command.
  Process only messages already fetched — do not re-fetch.
  The next session will pick up missed messages via the date overlap buffer.
"""
```

**Step 4: Run test to confirm it passes**

```bash
cd doc-radar && python -m pytest tests/test_gmail_scan.py::test_gmail_scan_output_includes_rate_limit_guidance -v
```

**Step 5: Run full test suite and commit**

```bash
cd doc-radar && python -m pytest tests/ -v
git add doc-radar/scripts/gmail_scan.py doc-radar/tests/test_gmail_scan.py
git commit -m "feat(gmail_scan): add HTTP 429 rate-limit handling guidance to hook output"
```

---

### Task 7: Add dry-run mode to `deadline-scheduler` SKILL.md

**Files:**
- Modify: `doc-radar/skills/deadline-scheduler/SKILL.md`

**Step 1: Add `## Dry-Run Mode` section**

Insert the following immediately before `## Step 1 — Duplicate Calendar Event Check`:

```markdown
## Dry-Run Mode

If the user's request or context includes `--dry-run` or `dry_run: true`:

1. Build all event payloads exactly as normal.
2. Use `--dry-run` on every `gws calendar events insert` call.
3. Output a preview table after all events are built:

```
DRY RUN PREVIEW — no events were created
─────────────────────────────────────────
Doc         : [doc_ref] ([doc_type])
Events that would be created:
  [title]  |  [date]  |  [reminders summary]
```

4. Do NOT write to `runs.jsonl`, record the hash, or write checkpoints.
5. End with: "Dry run complete. Re-run without --dry-run to create these events."
```

**Step 2: Commit**

```bash
git add doc-radar/skills/deadline-scheduler/SKILL.md
git commit -m "feat(deadline-scheduler): add dry-run mode for previewing calendar events"
```

---

### Task 8: Create `doc-radar:digest` skill

**Files:**
- Create: `doc-radar/skills/digest/SKILL.md`

**Background:** Claude Code skills have replaced commands. A skill with `disable-model-invocation: true` is user-invoked only (equivalent to the old `/commands` pattern), accessible as `/doc-radar:digest`.

**Step 1: Create the skill directory and file**

```bash
mkdir -p doc-radar/skills/digest
```

Create `doc-radar/skills/digest/SKILL.md`:

```markdown
---
name: digest
description: Show a summary of upcoming deadlines from the doc-radar run log. Use when the user asks for a deadline summary, what is coming up, or what documents need attention.
disable-model-invocation: true
---

Read `.tracker/runs.jsonl` using the `Read` tool (path relative to plugin root:
`${CLAUDE_SKILL_DIR}/../../.tracker/runs.jsonl`).

Filter records: exclude `status` values of `"duplicate_hash"`,
`"calendar_duplicate_skipped"`, and `"archived"`.

For each record, find the earliest upcoming date across:
`due_date`, `expiry_date`, `renewal_date`, `cancel_by_date`.

Sort by that date ascending. Group into three time horizons:

**THIS WEEK** (next 7 days)
**THIS MONTH** (next 8–30 days)
**LATER** (beyond 30 days)

Output a formatted digest:

```
DOC RADAR DIGEST — Upcoming Deadlines
Generated: [ISO date]
══════════════════════════════════════

THIS WEEK
─────────
[date]  [doc_type]  [doc_ref]  [parties.issuer]  [currency] [amount]
        Source: https://mail.google.com/mail/u/0/#all/[source_id]

THIS MONTH
──────────
...

LATER
─────
...
```

End with:
> "[N] upcoming deadlines. Next: [doc_ref] on [date]."

If `runs.jsonl` does not exist or has no actionable records:
> "No upcoming deadlines found. Run a Gmail scan to process documents."
```

**Step 2: Verify the file exists**

```bash
ls doc-radar/skills/digest/SKILL.md
```

**Step 3: Commit**

```bash
git add doc-radar/skills/digest/SKILL.md
git commit -m "feat: add doc-radar:digest skill for upcoming deadlines summary"
```

---

### Task 9: Create `doc-radar:archiver` skill

**Files:**
- Create: `doc-radar/skills/archiver/SKILL.md`

**Step 1: Create the skill directory and file**

```bash
mkdir -p doc-radar/skills/archiver
```

Create `doc-radar/skills/archiver/SKILL.md`:

```markdown
---
name: archiver
description: >
  Marks a doc-radar document record as archived (paid, completed, or resolved).
  Use when the user indicates a document has been acted on — invoice paid,
  contract signed/terminated, PO fulfilled, subscription cancelled.
  Removes the document from active digest views.
disable-model-invocation: true
---

# Document Archiver

## Purpose
Update a processed document's run log entry to `status: "archived"` so it is
excluded from future digests and retry queues.

---

## Step 1 — Identify the record

Match by any of:
- `doc_ref` (invoice number, PO number, contract ID)
- `sha256` prefix (first 12 characters)
- `source_id` (Gmail message ID or file path)

Read `.tracker/runs.jsonl` using the `Read` tool
(`${CLAUDE_SKILL_DIR}/../../.tracker/runs.jsonl`).
Find the matching record(s).

If no match:
> "No record found matching '[query]'. Run /doc-radar:digest to see available records."

---

## Step 2 — Confirm with user

Show the matched record and ask:

```
Archive this document?
  Type    : [doc_type]
  Ref     : [doc_ref]
  Parties : [issuer] / [recipient]
  Amount  : [currency] [amount]
  Source  : [Gmail URL or file path]

Confirm? (yes / no)
```

---

## Step 3 — Update the run log

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/update_log.py \
  --sha256 "<hash>" \
  --status "archived" \
  --archived-at "<ISO 8601 UTC>" \
  --archived-reason "<paid | completed | cancelled | terminated | other>"
```

---

## Step 4 — Confirm

> "Archived: [doc_type] [doc_ref] ([archived-reason]). It will no longer appear in digests."
```

**Step 2: Commit**

```bash
git add doc-radar/skills/archiver/SKILL.md
git commit -m "feat: add doc-radar:archiver skill for marking documents as resolved"
```

---

### Task 10: Create `dashboard.py` — self-contained HTML dashboard

**Files:**
- Create: `doc-radar/scripts/dashboard.py`
- Test: `doc-radar/tests/test_dashboard.py`

**Background:** Shadcn/ui requires a build step (React + Vite) with no CDN option. Instead, generate a single self-contained HTML file styled to match shadcn's design system using:
- **Tailwind CSS Play CDN** (`https://cdn.tailwindcss.com`) for utility classes
- **Chart.js CDN** (`https://cdn.jsdelivr.net/npm/chart.js`) for bar + doughnut charts
- **Shadcn design tokens** replicated as CSS variables (slate palette, card borders, radii)
- Data embedded directly in the HTML — no server, no fetch, opens with `file://`

**Dashboard layout:**
```
┌─────────────────────────────────────────────────────────────┐
│  Sidebar          │  Header: "Doc Radar"  [Export JSON]     │
│  ─────────────    │─────────────────────────────────────────│
│  Overview  ●      │  Stats Row (4 cards):                   │
│  Upcoming         │  [Total] [Upcoming] [Overdue] [Archived]│
│  All Docs         │─────────────────────────────────────────│
│  Archived         │  [Bar chart: docs/month] [Donut: types] │
│                   │─────────────────────────────────────────│
│                   │  Table: Type | Ref | Issuer | Amount |  │
│                   │         Key Date | Status | Source      │
└─────────────────────────────────────────────────────────────┘
```

**Step 1: Write failing tests**

Create `doc-radar/tests/test_dashboard.py`:

```python
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

def _record(**kw):
    base = {
        "timestamp": "2026-03-06T00:00:00+00:00",
        "run_id": "abc123",
        "doc_type": "invoice",
        "doc_ref": "INV-001",
        "sha256": "abc123def456xyz",
        "parties": {"issuer": "Acme Corp", "recipient": "NorthGrid"},
        "due_date": "2026-04-01",
        "expiry_date": None,
        "renewal_date": None,
        "cancel_by_date": None,
        "value": {"amount": 5000.0, "currency": "USD", "payment_terms": "Net 30"},
        "source": "gmail",
        "source_id": "msg123",
        "status": "complete",
        "calendar_event_ids": ["evt1"],
    }
    base.update(kw)
    return base

def test_dashboard_generates_html_file(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    runs.write_text(json.dumps(_record()) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    assert out.exists()
    content = out.read_text()
    assert "<!DOCTYPE html>" in content
    assert "INV-001" in content

def test_dashboard_includes_gmail_link(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    runs.write_text(json.dumps(_record()) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    content = out.read_text()
    assert "mail.google.com" in content
    assert "msg123" in content

def test_dashboard_shows_all_doc_types(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    records = [
        _record(doc_type="invoice",  doc_ref="INV-001", source_id="m1"),
        _record(doc_type="contract", doc_ref="MSA-001", source_id="m2", run_id="def"),
        _record(doc_type="nda",      doc_ref="NDA-001", source_id="m3", run_id="ghi"),
    ]
    runs.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    content = out.read_text()
    assert "INV-001" in content
    assert "MSA-001" in content
    assert "NDA-001" in content

def test_dashboard_empty_runs(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    runs.write_text("")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    assert out.exists()
    content = out.read_text()
    assert "No documents" in content

def test_dashboard_stats_counts(tmp_path):
    import dashboard
    runs = tmp_path / "runs.jsonl"
    records = [
        _record(run_id="a", status="complete",  due_date="2099-12-01"),
        _record(run_id="b", status="complete",  due_date="2020-01-01"),
        _record(run_id="c", status="archived",  due_date="2099-12-01"),
    ]
    runs.write_text("\n".join(json.dumps(r) for r in records) + "\n")
    out = tmp_path / "dashboard.html"
    dashboard.generate(runs_path=runs, output_path=out)
    content = out.read_text()
    assert '"total": 3' in content or "3" in content  # total docs
```

**Step 2: Run tests to confirm they fail**

```bash
cd doc-radar && python -m pytest tests/test_dashboard.py -v
```

Expected: FAIL — `dashboard.py` does not exist.

**Step 3: Implement `dashboard.py`**

Create `doc-radar/scripts/dashboard.py`. The script must:
1. Read and parse `runs.jsonl`
2. Compute stats: total, upcoming (future key date), overdue (past key date, not archived), archived
3. Build chart data: docs processed per month (last 6 months), docs by type (top 6)
4. Render an HTML file with:
   - Tailwind CDN + Chart.js CDN in `<head>`
   - Shadcn CSS variables (slate palette, card styling, badge colors)
   - Two-column sidebar layout
   - Four stat cards
   - Bar chart (docs per month) + Doughnut chart (by type) side by side
   - Full data table with colored badges per doc_type and status, Gmail source links
   - Data embedded as `const DATA = {...}` in a `<script>` block

```python
#!/usr/bin/env python3
"""
dashboard.py
------------
Generates a self-contained HTML dashboard from .tracker/runs.jsonl.
Uses Tailwind CSS Play CDN and Chart.js CDN — no build step required.

Usage:
  python3 dashboard.py [--runs PATH] [--output PATH] [--open]
"""
import argparse
import html as html_mod
import json
import webbrowser
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

PLUGIN_DIR  = Path(__file__).parent.parent
TRACKER_DIR = PLUGIN_DIR / ".tracker"
TODAY       = date.today()

# ── shadcn/ui design token colours for badge types ────────────────────────────
TYPE_COLORS = {
    "invoice":             ("bg-blue-100 text-blue-800",   "#3b82f6"),
    "contract":            ("bg-purple-100 text-purple-800","#8b5cf6"),
    "msa":                 ("bg-purple-100 text-purple-800","#8b5cf6"),
    "nda":                 ("bg-yellow-100 text-yellow-800","#f59e0b"),
    "sow":                 ("bg-green-100 text-green-800",  "#10b981"),
    "purchase_order":      ("bg-orange-100 text-orange-800","#f97316"),
    "lease":               ("bg-pink-100 text-pink-800",    "#ec4899"),
    "retainer":            ("bg-pink-100 text-pink-800",    "#ec4899"),
    "amendment":           ("bg-gray-100 text-gray-800",    "#6b7280"),
    "legal_notice":        ("bg-red-100 text-red-800",      "#ef4444"),
    "quotation":           ("bg-teal-100 text-teal-800",    "#14b8a6"),
    "subscription_renewal":("bg-indigo-100 text-indigo-800","#6366f1"),
    "other":               ("bg-gray-100 text-gray-800",    "#6b7280"),
}

STATUS_COLORS = {
    "complete":                    "bg-green-100 text-green-800",
    "extracted":                   "bg-blue-100 text-blue-800",
    "archived":                    "bg-gray-100 text-gray-500 line-through",
    "no_dates_extracted":          "bg-yellow-100 text-yellow-800",
    "calendar_error":              "bg-red-100 text-red-800",
    "calendar_duplicate_skipped":  "bg-gray-100 text-gray-600",
    "all_events_past":             "bg-gray-100 text-gray-600",
}


def load_records(runs_path: Path) -> list[dict]:
    if not runs_path.exists():
        return []
    records = []
    for line in runs_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def key_date(r: dict) -> date | None:
    for field in ("due_date", "expiry_date", "renewal_date", "cancel_by_date"):
        val = r.get(field)
        if val:
            try:
                return date.fromisoformat(val)
            except ValueError:
                pass
    return None


def gmail_link(r: dict) -> str:
    if r.get("source") == "gmail" and r.get("source_id"):
        url = f"https://mail.google.com/mail/u/0/#all/{r['source_id']}"
        return f'<a href="{url}" target="_blank" class="text-blue-600 hover:underline text-xs">Open email ↗</a>'
    elif r.get("source") == "file_drop":
        return f'<span class="text-xs text-slate-500">{html_mod.escape(r.get("source_id",""))}</span>'
    return '<span class="text-xs text-slate-400">Direct paste</span>'


def fmt_amount(r: dict) -> str:
    v = r.get("value") or {}
    amt = v.get("amount")
    cur = v.get("currency") or ""
    if amt is None:
        return "—"
    return f"{cur} {amt:,.2f}"


def compute_stats(records: list[dict]) -> dict:
    total    = len(records)
    upcoming = sum(1 for r in records
                   if r.get("status") != "archived" and key_date(r) and key_date(r) >= TODAY)
    overdue  = sum(1 for r in records
                   if r.get("status") != "archived" and key_date(r) and key_date(r) < TODAY)
    archived = sum(1 for r in records if r.get("status") == "archived")
    return {"total": total, "upcoming": upcoming, "overdue": overdue, "archived": archived}


def compute_monthly(records: list[dict]) -> tuple[list[str], list[int]]:
    from datetime import timedelta
    counts: dict[str, int] = defaultdict(int)
    for r in records:
        ts = r.get("timestamp", "")[:7]  # "YYYY-MM"
        if ts:
            counts[ts] += 1
    # Last 6 months
    months, values = [], []
    today = date.today()
    for i in range(5, -1, -1):
        d = date(today.year, today.month, 1)
        m = d.month - i
        y = d.year
        while m <= 0:
            m += 12
            y -= 1
        label = f"{y}-{m:02d}"
        months.append(date(y, m, 1).strftime("%b %Y"))
        values.append(counts.get(label, 0))
    return months, values


def compute_by_type(records: list[dict]) -> tuple[list[str], list[int], list[str]]:
    counts: Counter = Counter(r.get("doc_type", "other") for r in records)
    top = counts.most_common(6)
    labels  = [t for t, _ in top]
    values  = [c for _, c in top]
    colors  = [TYPE_COLORS.get(t, TYPE_COLORS["other"])[1] for t in labels]
    return labels, values, colors


def badge(text: str, css_class: str) -> str:
    return (f'<span class="inline-flex items-center px-2 py-0.5 rounded-full '
            f'text-xs font-medium {css_class}">{html_mod.escape(text)}</span>')


def build_table_rows(records: list[dict]) -> str:
    if not records:
        return ('<tr><td colspan="7" class="text-center py-10 text-slate-400">'
                'No documents processed yet.</td></tr>')
    rows = []
    for r in sorted(records, key=lambda x: x.get("timestamp", ""), reverse=True):
        doc_type = r.get("doc_type", "other")
        status   = r.get("status", "")
        kd       = key_date(r)
        kd_str   = kd.isoformat() if kd else "—"
        kd_class = ""
        if kd:
            if kd < TODAY and status != "archived":
                kd_class = "text-red-600 font-medium"
            elif kd <= date(TODAY.year, TODAY.month + 1 if TODAY.month < 12 else 1,
                            TODAY.day):
                kd_class = "text-amber-600 font-medium"

        type_badge   = badge(doc_type.replace("_", " "),
                             TYPE_COLORS.get(doc_type, TYPE_COLORS["other"])[0])
        status_badge = badge(status.replace("_", " "),
                             STATUS_COLORS.get(status, "bg-gray-100 text-gray-700"))

        row_class = "opacity-50" if status == "archived" else "hover:bg-slate-50"
        rows.append(f"""
        <tr class="border-b border-slate-100 {row_class}">
          <td class="py-3 px-4">{type_badge}</td>
          <td class="py-3 px-4 text-sm font-mono">{html_mod.escape(r.get('doc_ref') or '—')}</td>
          <td class="py-3 px-4 text-sm">{html_mod.escape((r.get('parties') or {}).get('issuer','') or '—')}</td>
          <td class="py-3 px-4 text-sm tabular-nums">{html_mod.escape(fmt_amount(r))}</td>
          <td class="py-3 px-4 text-sm tabular-nums {kd_class}">{kd_str}</td>
          <td class="py-3 px-4">{status_badge}</td>
          <td class="py-3 px-4">{gmail_link(r)}</td>
        </tr>""")
    return "\n".join(rows)


def generate(runs_path: Path = None, output_path: Path = None) -> None:
    runs_path   = runs_path   or TRACKER_DIR / "runs.jsonl"
    output_path = output_path or TRACKER_DIR / "dashboard.html"

    records       = load_records(runs_path)
    stats         = compute_stats(records)
    months, mvols = compute_monthly(records)
    tlabels, tvals, tcolors = compute_by_type(records)
    table_rows    = build_table_rows(records)
    now_str       = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    chart_data = json.dumps({
        "monthly": {"labels": months, "values": mvols},
        "byType":  {"labels": tlabels, "values": tvals, "colors": tcolors},
    })

    html = f"""<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Doc Radar Dashboard</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --radius: 0.5rem;
      --border: #e2e8f0;
      --card-shadow: 0 1px 3px 0 rgb(0 0 0 / .1), 0 1px 2px -1px rgb(0 0 0 / .1);
    }}
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }}
    .card {{ background:#fff; border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--card-shadow); }}
  </style>
</head>
<body class="h-full bg-slate-50 text-slate-900">

<div class="flex h-screen overflow-hidden">

  <!-- Sidebar -->
  <aside class="w-56 bg-white border-r border-slate-200 flex flex-col shrink-0">
    <div class="h-14 flex items-center px-5 border-b border-slate-200">
      <span class="text-lg font-semibold tracking-tight">⚡ Doc Radar</span>
    </div>
    <nav class="flex-1 px-3 py-4 space-y-1">
      <a href="#" class="flex items-center gap-2 px-3 py-2 rounded-md bg-slate-100 text-slate-900 text-sm font-medium">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
        Overview
      </a>
      <a href="#upcoming" class="flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm" onclick="filterTable('upcoming')">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
        Upcoming
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">{stats['upcoming']}</span>
      </a>
      <a href="#all" class="flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm" onclick="filterTable('all')">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
        All Documents
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">{stats['total']}</span>
      </a>
      <a href="#archived" class="flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm" onclick="filterTable('archived')">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/></svg>
        Archived
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">{stats['archived']}</span>
      </a>
    </nav>
    <div class="px-5 py-3 border-t border-slate-200 text-xs text-slate-400">
      Generated {now_str}
    </div>
  </aside>

  <!-- Main -->
  <main class="flex-1 overflow-y-auto">
    <header class="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <h1 class="text-base font-semibold">Dashboard</h1>
      <button onclick="exportJSON()" class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md border border-slate-200 hover:bg-slate-50 transition-colors">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
        Export JSON
      </button>
    </header>

    <div class="p-6 space-y-6">

      <!-- Stats Cards -->
      <div class="grid grid-cols-4 gap-4">
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Total Documents</p>
          <p class="mt-2 text-3xl font-bold tabular-nums">{stats['total']}</p>
          <p class="mt-1 text-xs text-slate-400">All time</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Upcoming</p>
          <p class="mt-2 text-3xl font-bold tabular-nums text-blue-600">{stats['upcoming']}</p>
          <p class="mt-1 text-xs text-slate-400">Future key dates</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Overdue</p>
          <p class="mt-2 text-3xl font-bold tabular-nums {'text-red-600' if stats['overdue'] > 0 else 'text-slate-900'}">{stats['overdue']}</p>
          <p class="mt-1 text-xs text-slate-400">Past key date, not archived</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Archived</p>
          <p class="mt-2 text-3xl font-bold tabular-nums text-slate-400">{stats['archived']}</p>
          <p class="mt-1 text-xs text-slate-400">Resolved / completed</p>
        </div>
      </div>

      <!-- Charts -->
      <div class="grid grid-cols-3 gap-4">
        <div class="card col-span-2 p-5">
          <h2 class="text-sm font-semibold mb-1">Documents Processed</h2>
          <p class="text-xs text-slate-400 mb-4">Last 6 months</p>
          <canvas id="barChart" height="160"></canvas>
        </div>
        <div class="card p-5">
          <h2 class="text-sm font-semibold mb-1">By Document Type</h2>
          <p class="text-xs text-slate-400 mb-4">All time</p>
          <canvas id="donutChart" height="160"></canvas>
        </div>
      </div>

      <!-- Table -->
      <div class="card overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-sm font-semibold">All Documents</h2>
          <input id="search" type="text" placeholder="Search ref, issuer…"
            oninput="searchTable(this.value)"
            class="text-sm border border-slate-200 rounded-md px-3 py-1.5 w-52 focus:outline-none focus:ring-2 focus:ring-slate-300">
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-slate-100 bg-slate-50">
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Type</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Reference</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Issuer</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Amount</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Key Date</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Source</th>
              </tr>
            </thead>
            <tbody id="tableBody">
              {table_rows}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </main>
</div>

<script>
const CHART_DATA = {chart_data};
const ALL_ROWS   = document.getElementById('tableBody').innerHTML;

// Bar chart — documents per month
new Chart(document.getElementById('barChart'), {{
  type: 'bar',
  data: {{
    labels: CHART_DATA.monthly.labels,
    datasets: [{{ label: 'Documents', data: CHART_DATA.monthly.values,
      backgroundColor: '#6366f1', borderRadius: 4, borderSkipped: false }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }},
      y: {{ beginAtZero: true, grid: {{ color: '#f1f5f9' }},
            ticks: {{ stepSize: 1, font: {{ size: 11 }} }} }}
    }}
  }}
}});

// Donut chart — by type
new Chart(document.getElementById('donutChart'), {{
  type: 'doughnut',
  data: {{
    labels: CHART_DATA.byType.labels,
    datasets: [{{ data: CHART_DATA.byType.values,
      backgroundColor: CHART_DATA.byType.colors, borderWidth: 2, borderColor: '#fff' }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ font: {{ size: 11 }}, padding: 10 }} }}
    }}
  }}
}});

// Table search
function searchTable(q) {{
  const rows = document.querySelectorAll('#tableBody tr');
  q = q.toLowerCase();
  rows.forEach(r => r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none');
}}

// Sidebar filter
function filterTable(mode) {{
  const tbody = document.getElementById('tableBody');
  if (mode === 'all') {{ tbody.innerHTML = ALL_ROWS; return; }}
  // Simple text-based filter on status cell (col 6)
  const parser = new DOMParser();
  const doc2   = parser.parseFromString('<table><tbody>' + ALL_ROWS + '</tbody></table>', 'text/html');
  const rows   = [...doc2.querySelectorAll('tr')];
  const keep   = rows.filter(r => {{
    const cells = r.querySelectorAll('td');
    if (!cells.length) return true;
    const status = cells[5]?.textContent.toLowerCase() || '';
    const kdate  = cells[4]?.textContent.trim();
    if (mode === 'upcoming') return !status.includes('archived') && kdate && kdate !== '—' && kdate >= '{TODAY.isoformat()}';
    if (mode === 'archived') return status.includes('archived');
    return true;
  }});
  tbody.innerHTML = keep.map(r => r.outerHTML).join('');
}}

// Export JSON
function exportJSON() {{
  const a = document.createElement('a');
  a.href = 'data:application/json,' + encodeURIComponent(JSON.stringify(CHART_DATA, null, 2));
  a.download = 'doc-radar-data.json';
  a.click();
}}
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    print(f"Dashboard written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate doc-radar HTML dashboard")
    parser.add_argument("--runs",   type=Path, default=TRACKER_DIR / "runs.jsonl")
    parser.add_argument("--output", type=Path, default=TRACKER_DIR / "dashboard.html")
    parser.add_argument("--open",   action="store_true", help="Open in browser after generating")
    args = parser.parse_args()
    generate(runs_path=args.runs, output_path=args.output)
    if args.open:
        webbrowser.open(f"file://{args.output.resolve()}")


if __name__ == "__main__":
    main()
```

**Step 4: Run tests to confirm they pass**

```bash
cd doc-radar && python -m pytest tests/test_dashboard.py -v
```

Expected: All PASS.

**Step 5: Run full test suite**

```bash
cd doc-radar && python -m pytest tests/ -v
```

**Step 6: Commit**

```bash
git add doc-radar/scripts/dashboard.py doc-radar/tests/test_dashboard.py
git commit -m "feat: add dashboard.py — self-contained HTML dashboard with Tailwind CDN and Chart.js"
```

---

### Task 10b: Create `doc-radar:dashboard` skill

**Files:**
- Create: `doc-radar/skills/dashboard/SKILL.md`

**Step 1: Create the skill directory and file**

```bash
mkdir -p doc-radar/skills/dashboard
```

Create `doc-radar/skills/dashboard/SKILL.md`:

```markdown
---
name: dashboard
description: Generate and open the Doc Radar HTML dashboard from runs.jsonl. Use when the user asks to see the dashboard, view documents visually, or open the report.
disable-model-invocation: true
---

Run the dashboard generator script:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/dashboard.py --open
```

Then report:
> "Dashboard generated at `.tracker/dashboard.html` and opened in your browser."

If the script fails (e.g. Python not found or runs.jsonl missing), report the
error and suggest running a Gmail scan first: invoke `doc-radar:legal-doc-detector`.
```

**Step 2: Verify the file exists**

```bash
ls doc-radar/skills/dashboard/SKILL.md
```

**Step 3: Commit**

```bash
git add doc-radar/skills/dashboard/SKILL.md
git commit -m "feat: add doc-radar:dashboard skill to generate and open HTML report"
```

---

### Task 11: Update script path references to use `${CLAUDE_SKILL_DIR}`

**Files:**
- Modify: `doc-radar/skills/doc-extractor/SKILL.md`
- Modify: `doc-radar/skills/deadline-scheduler/SKILL.md`

**Background:** Skills currently reference `~/.claude/plugins/doc-radar/scripts/...`. The official docs provide `${CLAUDE_SKILL_DIR}` — the absolute path to the skill's own directory at runtime. Scripts are two levels up from any skill dir: `${CLAUDE_SKILL_DIR}/../../scripts/`.

**Step 1: Replace hardcoded paths in `doc-extractor/SKILL.md`**

Use find-and-replace on all occurrences of:
```
~/.claude/plugins/doc-radar/scripts/
```
→
```
${CLAUDE_SKILL_DIR}/../../scripts/
```

**Step 2: Replace hardcoded paths in `deadline-scheduler/SKILL.md`**

Same substitution.

**Step 3: Verify** — grep to confirm no `~/.claude/plugins/doc-radar` remains in any SKILL.md:

```bash
grep -r "\.claude/plugins/doc-radar" doc-radar/skills/
```

Expected: No output.

**Step 4: Commit**

```bash
git add doc-radar/skills/doc-extractor/SKILL.md doc-radar/skills/deadline-scheduler/SKILL.md
git commit -m "fix: use \${CLAUDE_SKILL_DIR} for script paths — portable across install locations"
```

---

### Task 12: Push branch and open PR

**Step 1: Ensure on a feature branch**

```bash
git status
git checkout -b feat/doc-radar-enhancements-v2 2>/dev/null || git checkout feat/doc-radar-enhancements-v2
```

**Step 2: Push**

```bash
git push -u origin HEAD
```

**Step 3: Open PR**

```bash
gh pr create \
  --title "feat: skill discipline, PDF extraction, source linking & operational tools" \
  --body "$(cat <<'EOF'
## Summary

- **Skill-chain discipline**: gmail_scan.py and retry.py now instruct Claude to invoke doc-radar:legal-doc-detector rather than running scripts manually
- **PDF extraction**: legal-doc-detector uses Claude's built-in Read tool for PDF/DOCX attachments
- **Calendar source linking**: deadline-scheduler embeds Gmail URL in every event description
- **Confidence scoring**: doc-extractor adds per-field confidence levels
- **Null-date warning**: doc-extractor surfaces a visible warning when all date fields are null
- **Rate limit guidance**: gmail_scan.py includes HTTP 429 handling note
- **Dry-run mode**: deadline-scheduler supports --dry-run to preview events without inserting
- **Digest skill**: doc-radar:digest summarises upcoming deadlines from runs.jsonl
- **Archiver skill**: doc-radar:archiver marks documents as paid/completed/resolved
- **Dashboard**: self-contained HTML report (Tailwind CDN + Chart.js) — sidebar, stat cards, bar+donut charts, searchable table with Gmail source links
- **Path portability**: SKILL.md files use ${CLAUDE_SKILL_DIR}/../../scripts/ instead of hardcoded ~/.claude/plugins/doc-radar path

## Test plan
- [ ] All existing tests pass
- [ ] New: gmail_scan output contains doc-radar:legal-doc-detector, not hash_check.py
- [ ] New: retry output uses namespaced skill names
- [ ] New: gmail_scan output includes rate limit note
- [ ] New: dashboard generates valid HTML with stat cards and Gmail source links
- [ ] Manual: open generated dashboard.html in browser — verify charts, table, sidebar filters
- [ ] Manual: confirm calendar event descriptions include Gmail source URL
- [ ] Manual: /doc-radar:digest — upcoming deadlines table appears
- [ ] Manual: doc-radar:archiver — record status updated to archived
EOF
)"
```
