# doc-radar-marketplace

A plugin marketplace for automating legal and financial document tracking with Claude.
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
