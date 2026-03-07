---
name: doc-extractor
description: >
  Extracts structured date, party, and financial fields from legal and
  financially binding documents — contracts, invoices, purchase orders, NDAs,
  SOWs, MSAs, leases, amendments, quotations, subscription renewals. Computes
  a SHA-256 hash of the document content to detect duplicates before any
  processing occurs. Writes results to the JSONL run log. Use PROACTIVELY
  immediately after legal-doc-detector confirms a document should be processed.
---

# Document Extractor

## Purpose
Read a legal or financial document (email body, PDF text, DOCX content, or
raw text), extract all structured fields, compute the content hash for
deduplication, check the hash against the seen-hashes log, and either proceed
to `doc-radar:deadline-scheduler` or abort as a duplicate.

---

## Step 1 — Compute SHA-256 Hash

Before extracting anything, compute a SHA-256 hash of the document's raw
content. Use the Python script `scripts/hash_check.py` for this:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/hash_check.py --check-only --content "<raw_text>"
# or for a file:
python3 ${CLAUDE_SKILL_DIR}/../../scripts/hash_check.py --check-only --file "/path/to/file"
```

The script returns one of two responses:
- `{"status": "new", "hash": "<sha256>"}` — proceed with extraction
- `{"status": "duplicate", "hash": "<sha256>", "first_seen": "<ISO datetime>", "source_id": "<id>"}` — abort, do not process again

If duplicate: log to `.tracker/skipped.jsonl` with `skip_reason: "duplicate_hash"` and stop.

Do NOT record the hash yet — it is recorded permanently only after successful calendar creation in doc-radar-cowork:deadline-scheduler (Step 5b).

---

## Step 2 — Extract Fields

Extract the following fields from the document. Use `null` for any field that
cannot be confidently determined. Do NOT hallucinate dates or values — if
uncertain, use `null` and note it in `extraction_notes`.

```json
{
  "doc_type": "contract | msa | nda | sow | invoice | purchase_order | lease | retainer | amendment | legal_notice | quotation | subscription_renewal | other",
  "doc_ref": "contract/invoice/PO reference number if present, else null",
  "parties": {
    "issuer": "name of the party issuing/sending the document",
    "recipient": "name of the counterparty"
  },
  "effective_date": "YYYY-MM-DD or null",
  "expiry_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "renewal_date": "YYYY-MM-DD or null",
  "renewal_notice_days": "integer number of days notice required before auto-renewal, or null",
  "milestone_dates": ["YYYY-MM-DD", "..."],
  "value": {
    "amount": "numeric value as float or null",
    "currency": "CAD | USD | EUR | GBP | other | null",
    "payment_terms": "Net 30 | Net 60 | upon receipt | milestone-based | null"
  },
  "po_number": "string or null",
  "auto_renewal": true | false | null,
  "governing_law": "jurisdiction string or null",
  "source": "gmail | file_drop | direct_paste",
  "source_id": "gmail message ID, full file path, or 'user_paste'",
  "sha256": "<computed hash from Step 1>",
  "extraction_notes": "any caveats, ambiguities, or low-confidence fields noted here",
  "renewal_date":    "YYYY-MM-DD or null",
  "cancel_by_date":  "YYYY-MM-DD or null",
  "billing_cycle":   "monthly | annual | quarterly | null",
  "billing_method":  "credit card | ACH | PayPal | check | wire | null",
  "billing_last4":   "last 4 digits of card on file, or null",
  "bank_name":       "bank name if present in document, or null",
  "account_number":  "account number if present in document, or null",
  "routing_number":  "routing number if present in document, or null",
  "contact_email":   "issuer contact email if present, or null",
  "contact_phone":   "issuer contact phone if present, or null"
}
```

Additionally, append a `confidence` block to the extracted record:

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
- `high` — field is explicitly stated in a clearly formatted way (e.g., "Due: 2026-04-15")
- `medium` — field is inferred (e.g., "Net 30" from invoice date, or partial context)
- `low` — field is guessed from ambiguous language; flag in `extraction_notes`
- `null` — field not found; confidence is irrelevant

### Field Extraction Tips by Document Type

**Invoice**: Focus on `due_date` (not invoice date), `value.amount`, `po_number`,
`parties.issuer`. Payment terms like "Net 30" mean due_date = invoice_date + 30 days.

**Purchase Order**: `effective_date` is the order date. Look for delivery deadline
as `expiry_date`. `po_number` is always present if it's a real PO.

**Contract / MSA / NDA**: `expiry_date` is the term end date. Look for renewal
clauses — "automatically renews unless notice given X days prior" sets
`auto_renewal: true` and `renewal_notice_days: X`. Compute `renewal_date` as
`expiry_date - renewal_notice_days` to surface the action window.

**SOW**: Extract all milestone dates into `milestone_dates[]`. The final
delivery date becomes `expiry_date`. The project start date is `effective_date`.

**Lease / Retainer**: Treat term end as `expiry_date`. Monthly retainer amount
goes in `value.amount` with `payment_terms: "monthly"`.

**Amendment**: Extract the new expiry date if the amendment extends the term.
Link to the original document via `doc_ref`.

**Subscription Renewal**: Focus on `renewal_date` and `cancel_by_date`. The
cancel-by date is the last day to cancel to avoid being charged — extract if
present ("cancel by", "to avoid charges", "must cancel before").
`billing_cycle` comes from frequency language ("monthly", "annually", "per year").
`billing_last4` comes from masked card displays ("xxxx-1234").

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
Still invoke `doc-radar-cowork:deadline-scheduler` — it will create no events but
completes the pipeline cleanly.

---

## Step 3 — Write to Run Log

Append the extracted record to `.tracker/runs.jsonl`:

```json
{
  "timestamp": "<ISO 8601 UTC>",
  "run_id": "<uuid4>",
  "doc_type": "...",
  "doc_ref": "...",
  "sha256": "...",
  "parties": {...},
  "effective_date": "...",
  "expiry_date": "...",
  "due_date": "...",
  "renewal_date": "...",
  "value": {...},
  "source": "...",
  "source_id": "...",
  "calendar_event_ids": [],
  "status": "extracted",
  "confidence": {"overall": "high", "due_date": "high", "parties": "high"}
}
```

Leave `calendar_event_ids` as an empty array — `doc-radar:deadline-scheduler` will
populate this after creating events.

---

## Step 3.5 — Write Detected Checkpoint

After writing to runs.jsonl, write a pipeline checkpoint:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/checkpoint.py \
  --run-id "<run_id>" \
  --sha256 "<sha256>" \
  --doc-ref "<doc_ref or 'unknown'>" \
  --source-id "<source_id>" \
  --stage extracted
```

---

## Step 4 — Hand Off

Pass the full extracted JSON to the `doc-radar-cowork:deadline-scheduler` skill.
