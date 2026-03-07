# doc-radar-cowork

MCP-native legal and financial document automation for the Claude desktop app (Cowork mode).

Scans Gmail for contracts, invoices, NDAs, SOWs, purchase orders, leases, and subscription renewals. Extracts key dates and parties, deduplicates via SHA-256, logs results to JSONL, and creates Google Calendar events with tiered reminders — all using built-in MCP connectors. No CLI installation required.

## Prerequisites

- Claude desktop app with Cowork mode enabled
- Gmail MCP connector authorised in Claude settings
- Google Calendar MCP connector authorised in Claude settings

## How It Works

On each session start, the `scan_prompt.py` hook generates instructions for Claude to:

1. Search Gmail for legal/financial documents using the `search_messages` MCP tool
2. Fetch full message content via `read_message`
3. Run each email through the skill chain: `legal-doc-detector` → `doc-extractor` → `deadline-scheduler`
4. Create Google Calendar events with tiered reminders via `gcal_create_event`

Files dropped into `~/legal-inbox/` are also processed automatically via the PostToolUse hook.

## Known Limitations

1. **No attachment download via Gmail MCP** — The Gmail MCP connector returns attachment metadata (name, MIME type, size) but cannot download attachment file content. If an email's primary document is a PDF or DOCX attachment, the skill chain applies the Three-Signal Test to the email body and subject only. Emails that fail the body test but have a legal-looking attachment filename are logged to `.tracker/skipped.jsonl` for manual review.

2. **No email labelling** — The Gmail MCP connector does not support applying labels or marking messages as read. Processed emails are tracked internally via SHA-256 deduplication in `.tracker/hashes.jsonl`; they are not marked in Gmail itself.

## Running Tests

```bash
pytest doc-radar-cowork/tests/ -v
```

34 tests, all passing.
