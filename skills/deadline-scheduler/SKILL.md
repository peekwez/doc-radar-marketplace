---
name: deadline-scheduler
description: >
  Creates Google Calendar events from structured document data produced by
  doc-extractor. Applies tiered reminder logic per document type (contracts,
  invoices, POs, NDAs, SOWs, leases, amendments, subscription renewals).
  Checks for duplicate calendar events before creating. Updates the JSONL
  run log with created event IDs. Records SHA-256 hash permanently after
  successful creation. Use PROACTIVELY immediately after doc-extractor
  returns extracted JSON.
---

# Deadline Scheduler

## Purpose
Take the structured JSON from `doc-extractor`, create the correct Google
Calendar events with the right reminder windows, check for duplicates,
write the event description as a self-contained briefing, record event IDs
back to the run log, write the pipeline checkpoint to complete, and
permanently record the SHA-256 hash.

All calendar operations use `gws` (Google Workspace CLI) via Bash.

---

## Calendar Access via gws

```bash
# Check schema before building JSON payloads
gws schema calendar.events.insert
gws schema calendar.events.list

# Always dry-run first when creating or modifying events
gws calendar events insert \
  --params '{"calendarId":"primary"}' \
  --json '{ ... }' \
  --dry-run

# Then execute for real (remove --dry-run)
gws calendar events insert \
  --params '{"calendarId":"primary"}' \
  --json '{ ... }'
```

---

## Step 1 — Duplicate Calendar Event Check

Before creating any event, search the calendar for an existing event:

```bash
gws calendar events list \
  --params '{
    "calendarId": "primary",
    "q": "<doc_ref or party names>",
    "timeMin": "<today in RFC3339>",
    "timeMax": "<expiry_date + 180 days in RFC3339>",
    "fields": "items(id,summary,start)"
  }'
```

If a matching event already exists: log `calendar_event_ids` from the existing
event, update the run log with `status: "calendar_duplicate_skipped"`, and stop.

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
Source    : [gmail message link or file path]
SHA-256   : [first 12 chars of hash]
Processed : [ISO timestamp]
```

---

## Step 4 — Reminder Logic by Document Type

### Contract / MSA / NDA / Lease / Retainer

**Event 1 — Expiry Day** (all-day on `expiry_date`):
```json
{
  "summary": "EXPIRES: contract PSA-001 — Acme Corp / NorthGrid",
  "start": { "date": "<expiry_date>" },
  "end":   { "date": "<expiry_date + 1 day>" },
  "colorId": "11",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 43200 },
      { "method": "popup",  "minutes": 20160 },
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

**Event 2 — Renewal Notice Window** (if `auto_renewal: true`):
```json
{
  "summary": "RENEWAL NOTICE DUE: [doc_ref] — [N] days before auto-renewal",
  "start": { "date": "<renewal_date>" },
  "end":   { "date": "<renewal_date + 1 day>" },
  "colorId": "6",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 4320  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

### Invoice

**Event — Payment Due** (all-day on `due_date`):
```json
{
  "summary": "PAYMENT DUE: INV-001 — Acme Corp — USD 12500",
  "start": { "date": "<due_date>" },
  "end":   { "date": "<due_date + 1 day>" },
  "colorId": "5",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 4320  },
      { "method": "email",  "minutes": 1440  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

### Purchase Order

**Event — Delivery Deadline** (all-day on `expiry_date` or `due_date`):
```json
{
  "summary": "PO DELIVERY: PO-2026-001 — Acme Corp — USD 45000",
  "colorId": "9",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 20160 },
    { "method": "popup", "minutes": 10080 },
    { "method": "popup", "minutes": 1440  }
  ]}
}
```

### SOW

**Event — Final Delivery** (all-day on `expiry_date`):
```json
{
  "summary": "SOW DELIVERY: SOW-2026-001 — NorthGrid",
  "colorId": "10",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 43200 },
    { "method": "popup", "minutes": 20160 },
    { "method": "email", "minutes": 10080 },
    { "method": "popup", "minutes": 1440  }
  ]}
}
```

**Events — Milestones** (one per date in `milestone_dates[]`):
```json
{
  "summary": "MILESTONE [N/total]: SOW-2026-001 — NorthGrid",
  "colorId": "2",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 10080 },
    { "method": "popup", "minutes": 1440  }
  ]}
}
```

### Subscription Renewal

**Event 1 — Renewal Date** (all-day on `renewal_date`):
```json
{
  "summary": "SUBSCRIPTION RENEWS: Adobe Creative Cloud — USD 599.88/annual",
  "start": { "date": "<renewal_date>" },
  "end":   { "date": "<renewal_date + 1 day>" },
  "colorId": "7",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 20160 },
      { "method": "popup",  "minutes": 10080 },
      { "method": "email",  "minutes": 4320  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

**Event 2 — Cancel-by Date** (if `cancel_by_date` is present):
```json
{
  "summary": "CANCEL BY: Adobe Creative Cloud — Last day before auto-renewal",
  "start": { "date": "<cancel_by_date>" },
  "end":   { "date": "<cancel_by_date + 1 day>" },
  "colorId": "11",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 4320  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

### Amendment
Same logic as the document type being amended. Prefix title with "AMENDED:".

### Quotation / Proposal

**Event — Valid Until** (all-day on `expiry_date`):
```json
{
  "summary": "QUOTE EXPIRES: QUO-2026-001 — Acme Corp — USD 8500",
  "colorId": "1",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 4320 },
    { "method": "popup", "minutes": 1440 }
  ]}
}
```

---

## Step 5 — After Successful Event Creation

Run ALL of these steps after every event is created successfully:

**5a — Update run log with event IDs:**
```bash
python3 ~/.claude/plugins/doc-radar/scripts/update_log.py \
  --sha256 "<hash>" \
  --event-ids "<id1>,<id2>,..."
```

**5b — Record SHA-256 hash permanently** (first time the hash is recorded):
```bash
python3 ~/.claude/plugins/doc-radar/scripts/hash_check.py \
  --content "<raw_text>" \
  --source-id "<source_id>"
```

**5c — Write complete checkpoint:**
```bash
python3 ~/.claude/plugins/doc-radar/scripts/checkpoint.py \
  --run-id "<run_id>" \
  --sha256 "<hash>" \
  --doc-ref "<doc_ref>" \
  --source-id "<source_id>" \
  --stage complete
```

**5d — Update state.json last_scan_completed** (after ALL documents in the session are done):
```bash
python3 -c "
import json
from pathlib import Path
from datetime import datetime, timezone
f = Path('~/.claude/plugins/doc-radar/.tracker/state.json').expanduser()
s = json.loads(f.read_text())
s['last_scan_completed'] = datetime.now(timezone.utc).isoformat()
f.write_text(json.dumps(s, indent=2))
print('state.json updated')
"
```

---

## Step 6 — Error Handling

If `gws calendar events insert` fails:
1. Log to `.tracker/errors.jsonl`
2. Update run log entry: `status: "calendar_error"`
3. Update checkpoint to `stage: scheduled` with the error message (NOT complete)
4. Do NOT record the hash — retry next session
5. Continue processing other documents

```bash
python3 ~/.claude/plugins/doc-radar/scripts/checkpoint.py \
  --run-id "<run_id>" --sha256 "<hash>" --doc-ref "<doc_ref>" \
  --source-id "<source_id>" --stage scheduled \
  --error "gws calendar insert failed: <error message>"
```
