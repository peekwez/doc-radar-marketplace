---
name: legal-doc-detector
description: >
  Detects legal and financially binding documents in any context — Gmail scan
  output, file paths, attachment names, or pasted content. Triggers
  automatically when Claude encounters signals indicating a contract, invoice,
  PO, NDA, SOW, MSA, lease, retainer, amendment, quotation, or subscription
  renewal. Use PROACTIVELY whenever SessionStart hook injects Gmail scan
  results, or when a new file appears in the watched inbox folder.
  Immediately chains to doc-radar:doc-extractor.
---

# Legal Document Detector

## Purpose
Gate-keep what gets processed. Identify whether any document, email, or file
in the current context is a legal or financially binding document. If yes,
invoke the `doc-radar:doc-extractor` skill. If no, do nothing and do not log.

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

## Gmail Access via gws

To fetch emails for scanning, use these gws commands via Bash:

```bash
# List messages matching the legal doc query
gws gmail users messages list \
  --params '{"userId":"me","maxResults":50,"q":"<QUERY>"}' \
  --page-all

# Fetch full message content (body + attachment metadata)
gws gmail users messages get \
  --params '{"userId":"me","id":"<messageId>","format":"full"}'

# Download an attachment to a local file
gws gmail users messages attachments get \
  --params '{"userId":"me","messageId":"<id>","id":"<attachmentId>"}' \
  > /tmp/doc-radar-attachment.pdf

# Label a processed email to avoid reprocessing
gws gmail users messages modify \
  --params '{"userId":"me","id":"<messageId>"}' \
  --json '{"addLabelIds":["doc-radar-processed"]}'
```

Always use `--dry-run` before modifying (modify/label) operations.

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

## Trigger Conditions

Fire this skill automatically when:
1. `SessionStart` hook output is injected into context (daily Gmail scan results)
2. A file is written to `~/legal-inbox/` (PostToolUse hook fires)
3. User pastes document content or uploads a file directly in conversation
4. Context contains phrases like "check contracts", "any new invoices", "process docs"

---

## Output

When a document passes the filter, immediately call the `doc-radar:doc-extractor` skill.
Pass the full available content: email subject, sender, body snippet, attachment
name, and any text already extracted from the attachment.

Process each detected document sequentially. At the end of a scan, report:
> "Scan complete. Found N documents. N new (processed). N duplicates (skipped).
> N junk (filtered). Created N calendar events."
