# doc-radar-marketplace

doc-radar automatically monitors your Gmail inbox and a local watch folder for legal and financially binding documents. When it finds one, it extracts the key dates and parties, deduplicates it via SHA-256 so you never process the same document twice, logs the result to a JSONL audit trail, and creates Google Calendar events with tiered reminders so nothing slips through the cracks.

**Document types covered:** contracts, MSAs, NDAs, SOWs, invoices, purchase orders, leases, retainers, amendments, quotations, and subscription renewals.

**What gets created in your calendar:**
- Contract / NDA / lease expiry with 30/14/7/1-day reminders
- Auto-renewal notice windows (e.g. "send non-renewal notice by X")
- Invoice payment due dates with 7/3/1-day reminders
- SOW milestone dates and final delivery deadlines
- Subscription cancel-by dates before auto-charge

**Junk filtering built in:** marketing emails, CI/CD alerts, social notifications, and small consumer receipts are automatically skipped. A Three-Signal Test (named counterparty + financial obligation + actionable date) gates everything before processing.

Two plugins are available — choose based on how you use Claude:

## Plugins

| Plugin | Target | How It Works |
|--------|--------|--------------|
| [doc-radar](./doc-radar/) | **Claude Code** (terminal) | Uses the `gws` Google Workspace CLI to scan Gmail and create calendar events. Requires `npm install -g @googleworkspace/cli` and one-time OAuth setup. |
| [doc-radar-cowork](./doc-radar-cowork/) | **Claude Desktop App** (Cowork mode) | Uses Gmail and Google Calendar MCP connectors built into the Claude app. No CLI installation required — just authorise the connectors in Claude settings. |

Both plugins detect the same document types (contracts, invoices, NDAs, SOWs, purchase orders, leases, amendments, subscription renewals), apply the same SHA-256 deduplication, and create the same Google Calendar events with tiered reminders.

## Which Should I Use?

- **I use Claude in the terminal (Claude Code)** → install `doc-radar`
- **I use the Claude desktop app** → install `doc-radar-cowork`

## Installation

### Claude Code

```bash
/plugin marketplace add github:peekwez/doc-radar-marketplace
/plugin install doc-radar@doc-radar-marketplace
```

Then install the `gws` CLI and complete OAuth setup — see [doc-radar/README.md](./doc-radar/README.md).

### Claude Desktop App (Cowork)

```bash
/plugin marketplace add github:peekwez/doc-radar-marketplace
/plugin install doc-radar-cowork@doc-radar-marketplace
```

Authorise the Gmail and Google Calendar connectors in Claude settings — no other setup needed.

## Structure

```
doc-radar-marketplace/
├── .claude-plugin/marketplace.json
├── doc-radar/           # Claude Code plugin (gws CLI)
├── doc-radar-cowork/    # Claude desktop app plugin (MCP connectors)
└── README.md
```
