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

> Tracker files are stored in `~/.doc-radar/` (created automatically on first use). Override with the `DOC_RADAR_TRACKER_DIR` environment variable.

Read `~/.doc-radar/runs.jsonl` using the `Read` tool
(`~/.doc-radar/runs.jsonl`).
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
