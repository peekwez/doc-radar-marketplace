# doc-radar Enhancement Design
**Date:** 2026-03-05
**Status:** Approved
**Scope:** Junk filtering, subscription renewals, richer calendar events, error recovery

---

## Problem Statement

The current doc-radar plugin processes 20-30 unnecessary promotional, social, and junk emails per session before filtering them at the Claude skill layer. Subscription renewal notices lack a dedicated doc type and calendar reminder flow. Calendar event descriptions are minimal and lack actionable context. Error recovery is shallow — mid-run failures silently drop documents and there is no retry mechanism.

---

## Goals

1. Eliminate unnecessary email processing by filtering junk before it reaches Claude
2. Add subscription renewals as a first-class document type with calendar reminders
3. Make calendar events self-contained briefings with all financial, party, and action details
4. Implement true error recovery: checkpointing, hash-recording timing fix, retry on next session

---

## Approach: Python Pre-filter + Richer Skills (Approach B)

Harden the Gmail query at the source, strengthen the skill-layer junk filter, add subscription renewals throughout the pipeline, redesign event descriptions, and add per-doc checkpoint state with a retry script.

---

## Section 1: Junk Filtering

### 1a. Gmail Query Hardening (`scripts/gmail_scan.py`)

**Current bug:** `is:unread OR has:attachment` is unparenthesized, causing it to OR with the entire preceding query rather than ANDing with it. This allows emails that are unread or have attachments to pass regardless of junk category.

**Fixed query structure:**
```
(agreement OR contract OR invoice OR "purchase order" OR "PO#"
 OR NDA OR "statement of work" OR SOW OR MSA OR amendment OR addendum
 OR lease OR retainer OR quotation OR "legal notice" OR "amount due"
 OR "payment due" OR "net 30" OR "net 60"
 OR "subscription renewal" OR "auto-renew" OR "renews on")
 after:{date} before:{date}
 -category:promotions
 -category:social
 -category:updates
 -category:forums
 -label:^smartlabel_newsletters
 -subject:("% off" OR "sale ends" OR "limited time" OR "promo code"
           OR "unsubscribe" OR "flash sale" OR "black friday" OR "cyber monday")
 (is:unread OR has:attachment)
```

Key changes:
- Wrap `(is:unread OR has:attachment)` in parentheses so it ANDs with the rest
- Add `-category:forums` and `-label:^smartlabel_newsletters`
- Add `-subject:(...)` to exclude obvious marketing subject lines at the Gmail API level
- Add subscription renewal terms to the positive query

### 1b. Stronger Junk Filter in `legal-doc-detector` Skill

Add an explicit expanded blocklist and tighten the three-signal test:

**Expanded auto-skip patterns:**
- Sender domains (unless body contains a legal signal word): mailchimp.com, klaviyo.com, sendgrid.net, constantcontact.com, campaignmonitor.com, hubspot.com, marketo.com, salesforce.com (marketing cloud), intercom.io, drip.com
- Subject patterns: anything matching `\d+% off`, `sale ends`, `deal of the day`, `limited time offer`, `coupon`, `promo code`, `black friday`, `cyber monday`, `flash sale`
- Body patterns: `unsubscribe`, `view in browser`, `email preferences`, `opt out`, `you're receiving this because`
- Small consumer receipts: amount < $500 AND no PO number AND no contract reference AND no named business counterparty

**Strengthened three-signal test (ALL three required):**
1. **Named counterparty** — a named organization or legal entity other than the recipient themselves
2. **Financial obligation** — $500+ one-time OR any recurring amount at any dollar level
3. **Actionable date** — expiry, due date, renewal date, cancel-by date, or delivery deadline

---

## Section 2: Subscription Renewals as a First-Class Document Type

Subscription renewal notices are added to all three skills.

### Detection Signals (`legal-doc-detector`)

| Type | Key Signals |
|------|-------------|
| Subscription Renewal | "subscription renewal", "auto-renew", "automatically renews", "renews on", "next billing date", "upcoming charge", "your subscription to", "billing cycle", "cancel by", "to avoid being charged", "recurring charge", "your plan renews" |

**Three-signal gate (all three required to process):**
1. Named service or vendor (not just "your subscription" — must name the product/service)
2. Dollar amount (any recurring amount qualifies as a financial obligation)
3. A date (renewal date, cancel-by date, or billing date)

**Correctly processed:** SaaS tools, professional subscriptions, annual software licenses, cloud service renewals, domain/hosting renewals.
**Correctly skipped:** Vague "manage your preferences" emails, generic upsell offers, free tier upgrade prompts, marketing trial invitations.

### Extraction Fields (`doc-extractor`)

```json
{
  "doc_type": "subscription_renewal",
  "doc_ref": "service name + account ID if present",
  "parties": {
    "issuer": "vendor/service name",
    "recipient": "account holder name"
  },
  "renewal_date": "YYYY-MM-DD",
  "cancel_by_date": "YYYY-MM-DD or null",
  "billing_cycle": "monthly | annual | quarterly | null",
  "value": {
    "amount": 599.88,
    "currency": "USD",
    "payment_terms": "annual | monthly | quarterly"
  },
  "billing_method": "credit card | ACH | PayPal | null",
  "billing_last4": "last 4 digits of card if shown, else null"
}
```

### Calendar Events (`deadline-scheduler`)

**Primary event — Renewal Date** (all-day on `renewal_date`):
```
SUBSCRIPTION RENEWS: [service] — [currency] [amount]/[cycle]
Reminders: 14 days (email), 7 days (popup), 3 days (email), 1 day (popup)
```

**Secondary event — Cancel-by Date** (if `cancel_by_date` is present):
```
CANCEL BY: [service] — Last day to cancel before auto-renewal
Reminders: 7 days (email), 3 days (popup), 1 day (popup)
```

---

## Section 3: Richer Calendar Events

All calendar events redesigned: no emoji in titles, self-contained briefing format with all financial, party, action, and document details.

### Event Title Format

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

### Event Description Template

Sections with no data are omitted entirely — no blank fields.

```
DOCUMENT SUMMARY
────────────────
[2-3 sentence plain-language description: what this document is,
 who the parties are, and why it matters to the recipient]

ACTION REQUIRED
───────────────
[What needs to happen and by when — be specific]
Examples:
  "Decide whether to renew or send non-renewal notice by 2026-02-20"
  "Pay invoice via wire transfer to account below by 2026-03-15"
  "Cancel in Adobe account portal by 2026-03-18 to avoid auto-charge"

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
Account   : [account number if present in document]
Routing   : [routing number if present in document]
Card      : xxxx-xxxx-xxxx-[last4]
Method    : [wire | ACH | credit card | check | PayPal]

KEY DATES
─────────
Effective : [date]
Expires   : [date]
Renewal   : [date]
Notice by : [date]  (must notify by this date to avoid auto-renewal)
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

## Section 4: Error Recovery

### Fix 1 — Hash Recording Timing (`scripts/hash_check.py`)

**Problem:** Hash is recorded at check time. If calendar creation fails after the hash check, the document is permanently marked as seen but never scheduled. Retrying will show "duplicate" and the doc is silently lost.

**Fix:** Add `--check-only` flag. Pipeline calls `--check-only` for duplicate detection. Only after successful calendar creation does it call without the flag to permanently record the hash.

```bash
# Check only (does not record):
python3 hash_check.py --check-only --content "..."

# Check and record (called after successful scheduling):
python3 hash_check.py --content "..."
```

### Fix 0 — Append-Only JSONL with Schema Headers (all `.tracker/*.jsonl` files)

All JSONL tracker files follow two invariants:

1. **Line 1 is always a schema record**, written once at file creation:
   ```json
   {"_type": "schema", "version": "1.0", "file": "<filename>.jsonl", "created_at": "<ISO>"}
   ```
2. **All subsequent writes are append-only** — no file is ever rewritten in place.

State is resolved by reading all records and taking the latest record per key (`sha256` for `runs.jsonl` and `seen_hashes.jsonl`, `run_id` for `pending.jsonl`). This makes files safe for concurrent access and provides a full audit trail.

`update_log.py` is updated to append an `_type: "update"` record instead of rewriting. `checkpoint.py` appends stage records; readers resolve the current stage by taking the latest entry per `run_id`.

### Fix 2 — Pipeline Checkpointing (new `scripts/checkpoint.py` + `.tracker/pending.jsonl`)

New checkpoint file tracks per-doc pipeline state. Each doc writes a checkpoint after each stage and updates it on completion.

**`pending.jsonl` schema entry (line 1, written once at creation):**
```json
{"_type": "schema", "version": "1.0", "file": "pending.jsonl", "created_at": "<ISO>"}
```

**Subsequent records — appended, latest per `run_id` wins:**
```json
{
  "_type":     "checkpoint",
  "run_id":    "uuid4",
  "sha256":    "...",
  "doc_ref":   "...",
  "doc_type":  "...",
  "source_id": "...",
  "stage":     "detected | extracted | scheduled | complete",
  "timestamp": "ISO 8601",
  "error":     null
}
```

Items not yet at `complete` (resolved as latest record per `run_id`) are surfaced for retry on next session. The same schema header pattern applies to all `.tracker/*.jsonl` files.

**`scripts/checkpoint.py` interface:**
```bash
# Write or update a checkpoint:
python3 checkpoint.py --run-id <uuid> --sha256 <hash> --doc-ref <ref> \
                      --source-id <id> --stage extracted

# Mark complete:
python3 checkpoint.py --run-id <uuid> --sha256 <hash> --stage complete
```

### Fix 3 — Scan Timestamp Fix (`scripts/gmail_scan.py`)

**Problem:** `last_run` is set at script start, before Claude processes anything. Mid-run failures leave the timestamp advanced, so affected emails fall outside the next scan's date window.

**Fix:** Split into two fields in `state.json`:
- `last_scan_started` — set at hook start, used to build the date range query
- `last_scan_completed` — set only after Claude confirms full processing is done

Claude is instructed in `doc-radar-agent.md` to update `last_scan_completed` in `state.json` at the end of a successful run. The next scan uses `last_scan_started` as its base (with the existing 1-day buffer).

**Updated `state.json` schema:**
```json
{
  "last_scan_started": "2026-03-05T10:00:00Z",
  "last_scan_completed": "2026-03-05T10:03:22Z",
  "last_run_email_count": 0,
  "total_runs": 0,
  "plugin_version": "1.1.0",
  "created_at": "2026-03-05T00:00:00Z"
}
```

### Fix 4 — Retry Script (new `scripts/retry.py`)

Reads `pending.jsonl` and `errors.jsonl`, groups unresolved items, and outputs a retry brief injected into SessionStart context (same stdout injection pattern as `gmail_scan.py`).

**Output format:**
```
=== DOC RADAR: Pending Retry Items ===
Timestamp : {now}
Items requiring retry: N

The following documents were partially processed in a previous session
and require retry. Process each through the full pipeline (doc-extractor
→ deadline-scheduler). Source IDs are provided to re-fetch if needed.

[list of pending items with stage, doc_ref, source_id, error if any]
```

### Updated `hooks.json`

Two sequential SessionStart hooks using `CLAUDE_PLUGIN_ROOT`:
```json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [{
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gmail_scan.py 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
        }]
      },
      {
        "hooks": [{
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/retry.py 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [{
          "type": "command",
          "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/watch_folder.py --file \"$(echo $CLAUDE_HOOK_INPUT | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))\" 2>/dev/null)\" 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
        }]
      }
    ]
  }
}
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `scripts/gmail_scan.py` | Modify | Fix query precedence bug, stronger exclusions, split timestamp fields |
| `scripts/hash_check.py` | Modify | Add `--check-only` flag to separate check from record |
| `scripts/update_log.py` | Modify | Minor: ensure compatibility with checkpoint flow |
| `scripts/checkpoint.py` | New | Write/update per-doc pipeline checkpoints to `pending.jsonl` |
| `scripts/retry.py` | New | Read `pending.jsonl` and `errors.jsonl`, output retry brief |
| `hooks/hooks.json` | Modify | Add retry.py to SessionStart, use `CLAUDE_PLUGIN_ROOT` |
| `skills/legal-doc-detector/SKILL.md` | Modify | Add subscription renewals, stronger junk filter rules |
| `skills/doc-extractor/SKILL.md` | Modify | Add `subscription_renewal` doc type and extraction fields |
| `skills/deadline-scheduler/SKILL.md` | Modify | No emoji titles, richer description template, subscription renewal events |
| `agents/doc-radar-agent.md` | Modify | Checkpointing instructions, hash-timing fix, retry handling |
| `.tracker/state.json` | Modify | Split `last_run` into `last_scan_started` / `last_scan_completed` |

---

## Non-Goals

- No Gmail label pre-configuration (Approach C complexity)
- No full job-queue system
- No changes to `watch_folder.py` (file drop flow unchanged)
- No UI dashboard

---

## Version

Plugin version bumps from `1.0.0` to `1.1.0` in `plugin.json`.
