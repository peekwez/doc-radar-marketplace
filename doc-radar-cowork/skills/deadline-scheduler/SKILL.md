---
name: deadline-scheduler
description: >
  Creates Google Calendar events from structured document data produced by
  doc-radar-cowork:doc-extractor. Applies tiered reminder logic per document
  type (contracts, invoices, POs, NDAs, SOWs, leases, amendments, subscription
  renewals). Checks for duplicate calendar events before creating. Updates the
  JSONL run log with created event IDs. Records SHA-256 hash permanently after
  successful creation. Use PROACTIVELY immediately after
  doc-radar-cowork:doc-extractor returns extracted JSON.
---

# Deadline Scheduler

## Purpose
Take the structured JSON from `doc-radar-cowork:doc-extractor`, create the
correct Google Calendar events with the right reminder windows, check for
duplicates, write the event description as a self-contained briefing, record
event IDs back to the run log, write the pipeline checkpoint to complete, and
permanently record the SHA-256 hash.

All calendar operations use the **Google Calendar MCP connector** — no CLI
or Bash required.

---

## Calendar Access via MCP Connector

Use these Google Calendar MCP tools directly:

```
# Duplicate check before creating any event
gcal_list_events(
  calendarId="primary",
  q="<doc_ref or party names>",
  timeMin="<today in RFC3339>",
  timeMax="<expiry_date + 180 days in RFC3339>"
)

# Create a calendar event
gcal_create_event(
  calendarId="primary",
  event={
    "summary": "<title>",
    "description": "<briefing>",
    "start": { "date": "<YYYY-MM-DD>" },
    "end":   { "date": "<YYYY-MM-DD>" },
    "colorId": "<1-11>",
    "reminders": {
      "useDefault": false,
      "overrides": [ ... ]
    }
  },
  sendUpdates="none"
)
```

> **Important:** `gcal_create_event` takes an `event` object — not a raw
> JSON string. Build the event dict and pass it as the `event` parameter.

---

## Dry-Run Mode

If the user's request or context includes `--dry-run` or `dry_run: true`:

1. Build all event payloads exactly as normal.
2. Do NOT call `gcal_create_event` — print a preview instead:

```
DRY RUN PREVIEW — no events were created
─────────────────────────────────────────
Doc         : [doc_ref] ([doc_type])
Events that would be created:
  [title]  |  [date]  |  [reminders summary]
```

3. Do NOT write to `runs.jsonl`, record the hash, or write checkpoints.
4. End with: "Dry run complete. Re-run without --dry-run to create these events."

---

## Step 1 — Duplicate Calendar Event Check

Before creating any event, call `gcal_list_events` to search for an
existing event with a matching summary or doc_ref:

```
gcal_list_events(
  calendarId="primary",
  q="<doc_ref>",
  timeMin="<today RFC3339>",
  timeMax="<expiry_date + 180 days RFC3339>"
)
```

If a matching event already exists: log `calendar_event_ids` from the
existing event, update the run log with `status: "calendar_duplicate_skipped"`,
and stop.

---

## Step 2 — Event Title Format

No emoji. Professional, scannable titles.

| Doc Type | Title Format |
|----------|-------------|
| Contract / MSA / NDA / Lease / Retainer | `EXPIRES: [doc_type] [doc_ref] — [issuer] / [recipient]` |
| Invoice | `PAYMENT DUE: [doc_ref] — [issuer] — [currency] [amount]` |
| Purchase Order | `PO DELIVERY: [po_number] — [issuer] — [currency] [amount]` |
| SOW Final Delivery | `SOW DELIVERY: [doc_ref] — [recipient]` |
| SOW Milestone | `MILESTONE [N/total]: [doc_ref] — [recipient]` |
| Subscription Renewal | `SUBSCRIPTION RENEWS: [service] — [currency] [amount]/[cycle]` |
| Cancel-by | `CANCEL BY: [service] — Last day before auto-renewal` |
| Renewal Notice Window | `RENEWAL NOTICE DUE: [doc_ref] — [N] days before auto-renewal` |
| Quotation / Proposal | `QUOTE EXPIRES: [doc_ref] — [issuer] — [currency] [amount]` |
| Amendment | `AMENDED EXPIRES: [doc_ref] — [issuer] / [recipient]` |

---

## Step 3 — Event Description Template

Build the description as a self-contained briefing. Omit any section where
all fields are null — do not leave blank headings.

**Source URL construction rule:**
Always include the SOURCE section. For Gmail sources:
`"https://mail.google.com/mail/u/0/#all/" + source_id`
This links the calendar event to the originating email for audit trail.

```
DOCUMENT SUMMARY
────────────────
[2-3 sentence plain-language description: what this document is, who the
parties are, and why it matters. Write as if the reader has never seen it.]

ACTION REQUIRED
───────────────
[Exactly what needs to happen and by when — be specific and imperative]
Examples:
  "Decide whether to renew or send non-renewal notice by 2026-02-20"
  "Pay invoice via wire transfer to account details below by 2026-03-15"
  "Cancel subscription in Adobe account portal by 2026-03-18 to avoid charge"

PARTIES
───────
Issuer    : [name] | [email] | [phone]
Recipient : [name] | [email]

FINANCIAL DETAILS
─────────────────
Amount    : [currency] [amount]
Payment   : [payment_terms]
Pay To    : [payee name / account name]
Bank      : [bank name]
Account   : [account number]
Routing   : [routing number]
Card      : xxxx-xxxx-xxxx-[last4]
Method    : [wire | ACH | credit card | check | PayPal]

KEY DATES
─────────
Effective : [date]
Expires   : [date]
Renewal   : [date]
Notice by : [date]
Cancel by : [date]
Milestones: [date — description, ...]

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
  google_drive -> https://drive.google.com/file/d/[source_id]/view
  file_drop    -> [source_id — full file path]
  direct_paste -> Pasted directly in conversation
```

---

## Step 4 — Reminder Logic by Document Type

### Contract / MSA / NDA / Lease / Retainer

**Event 1 — Expiry Day** (all-day on `expiry_date`):
```python
gcal_create_event(
  event={
    "summary": "EXPIRES: contract PSA-001 — Acme Corp / NorthGrid",
    "start": { "date": "<expiry_date>" },
    "end":   { "date": "<expiry_date + 1 day>" },
    "colorId": "11",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email",  "minutes": 43200 },
        { "method": "popup",  "minutes": 20160 },
        { "method": "email",  "minutes": 10080 },
        { "method": "popup",  "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

**Event 2 — Renewal Notice Window** (if `auto_renewal: true`):
```python
gcal_create_event(
  event={
    "summary": "RENEWAL NOTICE DUE: [doc_ref] — [N] days before auto-renewal",
    "start": { "date": "<renewal_date>" },
    "end":   { "date": "<renewal_date + 1 day>" },
    "colorId": "6",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email",  "minutes": 10080 },
        { "method": "popup",  "minutes": 4320  },
        { "method": "popup",  "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

### Invoice

**Event — Payment Due** (all-day on `due_date`):
```python
gcal_create_event(
  event={
    "summary": "PAYMENT DUE: INV-001 — Acme Corp — USD 12500",
    "start": { "date": "<due_date>" },
    "end":   { "date": "<due_date + 1 day>" },
    "colorId": "5",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email",  "minutes": 10080 },
        { "method": "popup",  "minutes": 4320  },
        { "method": "email",  "minutes": 1440  },
        { "method": "popup",  "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

### Purchase Order

**Event — Delivery Deadline** (all-day on `expiry_date` or `due_date`):
```python
gcal_create_event(
  event={
    "summary": "PO DELIVERY: PO-2026-001 — Acme Corp — USD 45000",
    "start": { "date": "<due_date>" },
    "end":   { "date": "<due_date + 1 day>" },
    "colorId": "9",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email", "minutes": 20160 },
        { "method": "popup", "minutes": 10080 },
        { "method": "popup", "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

### SOW

**Event — Final Delivery** (all-day on `expiry_date`):
```python
gcal_create_event(
  event={
    "summary": "SOW DELIVERY: SOW-2026-001 — NorthGrid",
    "start": { "date": "<expiry_date>" },
    "end":   { "date": "<expiry_date + 1 day>" },
    "colorId": "10",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email", "minutes": 43200 },
        { "method": "popup", "minutes": 20160 },
        { "method": "email", "minutes": 10080 },
        { "method": "popup", "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

**Events — Milestones** (one per date in `milestone_dates[]`):
```python
gcal_create_event(
  event={
    "summary": "MILESTONE [N/total]: SOW-2026-001 — NorthGrid",
    "start": { "date": "<milestone_date>" },
    "end":   { "date": "<milestone_date + 1 day>" },
    "colorId": "2",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email", "minutes": 10080 },
        { "method": "popup", "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

### Subscription Renewal

**Event 1 — Renewal Date** (all-day on `renewal_date`):
```python
gcal_create_event(
  event={
    "summary": "SUBSCRIPTION RENEWS: Adobe Creative Cloud — USD 599.88/annual",
    "start": { "date": "<renewal_date>" },
    "end":   { "date": "<renewal_date + 1 day>" },
    "colorId": "7",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email",  "minutes": 20160 },
        { "method": "popup",  "minutes": 10080 },
        { "method": "email",  "minutes": 4320  },
        { "method": "popup",  "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

**Event 2 — Cancel-by Date** (if `cancel_by_date` is present):
```python
gcal_create_event(
  event={
    "summary": "CANCEL BY: Adobe Creative Cloud — Last day before auto-renewal",
    "start": { "date": "<cancel_by_date>" },
    "end":   { "date": "<cancel_by_date + 1 day>" },
    "colorId": "11",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email",  "minutes": 10080 },
        { "method": "popup",  "minutes": 4320  },
        { "method": "popup",  "minutes": 1440  }
      ]
    }
  },
  sendUpdates="none"
)
```

### Amendment
Same logic as the document type being amended. Prefix title with "AMENDED:".

### Quotation / Proposal

**Event — Valid Until** (all-day on `expiry_date`):
```python
gcal_create_event(
  event={
    "summary": "QUOTE EXPIRES: QUO-2026-001 — Acme Corp — USD 8500",
    "start": { "date": "<expiry_date>" },
    "end":   { "date": "<expiry_date + 1 day>" },
    "colorId": "1",
    "reminders": {
      "useDefault": False,
      "overrides": [
        { "method": "email", "minutes": 4320 },
        { "method": "popup", "minutes": 1440 }
      ]
    }
  },
  sendUpdates="none"
)
```

---

## Step 5 — After Successful Event Creation

Run ALL of these steps after every event is created successfully:

**5a — Update run log with event IDs:**
```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/update_log.py \
  --sha256 "<hash>" \
  --event-ids "<id1>,<id2>,..."
```

**5b — Record SHA-256 hash permanently** (first time the hash is recorded):
```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/hash_check.py \
  --content "<raw_text>" \
  --source-id "<source_id>"
```

**5c — Write complete checkpoint:**
```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/checkpoint.py \
  --run-id "<run_id>" \
  --sha256 "<hash>" \
  --doc-ref "<doc_ref>" \
  --source-id "<source_id>" \
  --stage complete
```

> Tracker files are stored in `~/.doc-radar/` (created automatically on first use). Override with the `DOC_RADAR_TRACKER_DIR` environment variable.

**5d — Update state.json last_scan_completed** (after ALL documents in the session are done):
```bash
python3 -c "
import json
from pathlib import Path
from datetime import datetime, timezone
f = Path('~/.doc-radar/state.json')
s = json.loads(f.read_text())
s['last_scan_completed'] = datetime.now(timezone.utc).isoformat()
f.write_text(json.dumps(s, indent=2))
print('state.json updated')
"
```

---

## Step 6 — Error Handling

If `gcal_create_event` fails:
1. Log to `~/.doc-radar/errors.jsonl`
2. Update run log entry: `status: "calendar_error"`
3. Update checkpoint to `stage: scheduled` with the error message (NOT complete)
4. Do NOT record the hash — retry next session
5. Continue processing other documents

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/checkpoint.py \
  --run-id "<run_id>" --sha256 "<hash>" --doc-ref "<doc_ref>" \
  --source-id "<source_id>" --stage scheduled \
  --error "gcal_create_event failed: <error message>"
```
