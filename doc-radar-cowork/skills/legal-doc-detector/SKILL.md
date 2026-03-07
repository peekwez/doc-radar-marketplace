---
name: legal-doc-detector
description: >
  Detects legal and financially binding documents in any context — Gmail scan
  output, file paths, attachment names, or pasted content. Triggers
  automatically when Claude encounters signals indicating a contract, invoice,
  PO, NDA, SOW, MSA, lease, retainer, amendment, quotation, or subscription
  renewal. Use PROACTIVELY whenever SessionStart hook injects Gmail scan
  results, or when a new file appears in the watched inbox folder.
  Immediately chains to doc-radar-cowork:doc-extractor.
---

# Legal Document Detector

## Purpose
Gate-keep what gets processed. Identify whether any document, email, or file
in the current context is a legal or financially binding document. If yes,
invoke the `doc-radar-cowork:doc-extractor` skill. If no, do nothing and do not log.

---

## Document Types to Detect

| Type | Key Signals |
|------|-------------|
| Contract / MSA | "agreement", "master services", "MSA", "contract", "terms and conditions", "governing law", "whereas", "in witness whereof" |
| NDA | "non-disclosure", "NDA", "confidentiality agreement", "proprietary information", "confidential information" |
| SOW | "statement of work", "SOW", "scope of work", "deliverables", "milestones", "acceptance criteria" |
| Invoice | "invoice", "INV-", "bill to", "amount due", "payment due", "remittance", "please remit", "net 30", "net 60" |
| Purchase Order | "purchase order", "PO#", "PO number", "order confirmation", "ship to", "vendor number", "requisition" |
| Lease / Retainer | "lease agreement", "retainer agreement", "monthly retainer", "tenancy", "rent", "premises" |
| Amendment | "amendment", "addendum", "modification to agreement", "change order", "supplement to" |
| Legal Notice | "legal notice", "cease and desist", "demand letter", "notice of termination", "notice of default" |
| Quotation / Proposal | "quotation", "quote #", "proposal", "valid until", "acceptance of this quote" |
| Subscription Renewal | "subscription renewal", "auto-renew", "automatically renews", "renews on", "next billing date", "upcoming charge", "your subscription to", "billing cycle", "cancel by", "to avoid being charged", "recurring charge", "your plan renews" |

---

## Gmail Access via MCP Connector

Use the Gmail MCP connector tools directly — no CLI or Bash required.

```
# Search for candidate messages
search_messages(
  query="<GMAIL_QUERY>",
  max_results=50
)
# Returns: list of { id, threadId, snippet }

# Fetch full message content
read_message(message_id="<messageId>")
# Returns: subject, sender, date, body (plain text), attachments[] metadata
```

**Attachment limitation:** The Gmail MCP connector does not support
downloading attachment file content. If an email has a PDF or DOCX
attachment, only its name, MIME type, and size are available.

When an attachment is the likely primary document:
1. Apply the Three-Signal Test to the email body + subject.
2. If the body alone passes → process as normal.
3. If the body alone fails but the attachment filename strongly suggests
   a legal doc (e.g. `MSA_2026.pdf`, `Invoice_INV-001.pdf`):
   → Log to `.tracker/skipped.jsonl` with `skip_reason: "attachment_not_downloadable"`
   → Do NOT invoke doc-extractor for this item.

Files dropped into `~/legal-inbox/` (watch_folder.py trigger) are
accessible via the `Read` tool — use that for local file content.

---

## Google Drive Access via MCP Connector

Use the Google Drive tools directly — no CLI or Bash required. These tools are
injected automatically when the Google Drive connector is enabled in Claude settings.

```
# Search for legal document candidates
google_drive_search(
  api_query="<DRIVE_QUERY>",
  order_by="modifiedTime desc",
  page_size=50
)
# Returns: list of { id, name, mimeType, modifiedTime, owners, webViewLink }

# Fetch file content (up to 10 IDs per call)
google_drive_fetch(document_ids=["<fileId>", ...])
# Returns: text content of each file directly
```

Set `source='google_drive'` and `source_id='<fileId>'` when passing to
`doc-radar-cowork:doc-extractor`.

---

## Junk and Promotional Filter — SKIP ENTIRELY

Do NOT process any email or document matching these patterns.

### Marketing & Promotional
- Body contains: "unsubscribe", "view in browser", "email preferences", "opt out", "you're receiving this because", "manage your email preferences"
- Body contains: "% off", "sale ends", "limited time", "deal of the day", "coupon", "promo code", "black friday", "cyber monday", "flash sale"
- Subject matches: `\d+% off`, "sale ends", "deal of the day", "limited time offer", "coupon", "promo code", "flash sale", "black friday", "cyber monday"
- Sender domains (unless body contains a legal signal word from the table above): mailchimp.com, klaviyo.com, sendgrid.net, constantcontact.com, campaignmonitor.com, hubspot.com, marketo.com, intercom.io, drip.com

### Automated System Noise
- CI/CD alerts, build failure emails, monitoring digests (Datadog, PagerDuty, New Relic, Grafana), GitHub PR notifications
- Password reset, account verification, 2FA codes
- Subscription renewal notices for personal consumer services (Netflix, Spotify, Apple, Amazon Prime) where the recipient is an individual consumer and no business counterparty is named

### Social & Platform Notifications
- LinkedIn connection requests, job alerts, InMail digests
- Twitter/X notifications, Slack digest emails, GitHub mention digests
- Google Analytics weekly reports, app usage summaries

### Small Consumer Transactions
- Receipts under $500 with no PO number, contract ID, or named business counterparty

### The Three-Signal Test — ALL THREE Required to Process

When in doubt, apply this test. ALL three must be present:

1. **Named counterparty** — a named organization or legal entity other than the recipient themselves (not just "you" or "customer")
2. **Financial obligation** — $500+ one-time amount, OR any recurring amount at any dollar level (a $9/month SaaS subscription qualifies)
3. **Actionable date** — an expiry, due date, renewal date, cancel-by date, or delivery deadline

If any signal is missing, skip and log to `.tracker/skipped.jsonl` with the missing signal noted.

**Subscription renewal special case:** A renewal email from a named vendor with a dollar amount and a renewal/cancel-by date passes all three signals and MUST be processed as `subscription_renewal` doc type.

---

## Attachment Handling

When an email has a PDF, DOCX, or plain-text attachment that has been
dropped into `~/legal-inbox/` (watched folder path):

1. Use the `Read` tool on the local file path to extract its text content.
   Claude's built-in Read tool handles PDFs natively — no OCR service needed.
2. Treat the extracted text as the document body for the Three-Signal Test
   and document type detection.
3. Pass both the email metadata (subject, sender, date) AND the extracted
   attachment text to `doc-radar-cowork:doc-extractor` as the document content.

If the `Read` tool cannot extract text (binary-only, encrypted, or corrupted
file), log to `.tracker/skipped.jsonl`:
```json
{
  "timestamp": "<ISO 8601 UTC>",
  "source_id": "<messageId or file path>",
  "skip_reason": "unreadable_attachment",
  "filename": "<attachment filename>"
}
```
Then stop — do not invoke `doc-radar-cowork:doc-extractor` for this item.

---

## Trigger Conditions

Fire this skill automatically when:
1. `SessionStart` hook output is injected into context (daily Gmail scan results)
2. A file is written to `~/legal-inbox/` (PostToolUse hook fires)
3. User pastes document content or uploads a file directly in conversation
4. Context contains phrases like "check contracts", "any new invoices", "process docs"
5. SessionStart hook output contains Google Drive scan results

---

## Output

When a document passes the filter, immediately call the `doc-radar-cowork:doc-extractor` skill.
Pass the full available content: email subject, sender, body snippet, attachment
name, and any text already extracted from the attachment.

Process each detected document sequentially. At the end of a scan, report:
> "Scan complete. Found N documents. N new (processed). N duplicates (skipped).
> N junk (filtered). Created N calendar events."
