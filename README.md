# doc-radar-marketplace

A Claude Code plugin marketplace containing the `doc-radar` plugin.

## Plugins

| Plugin                    | Description                                                                                                                                                                   |
| ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| [doc-radar](./doc-radar/) | Scans Gmail and watched folders for legal/financial documents. Extracts dates, deduplicates via SHA-256, logs to JSONL, creates Google Calendar events with tiered reminders. |

## Installation

```
/plugin install doc-radar@doc-radar-marketplace
```

## Structure

```
doc-radar-marketplace/
├── .claude-plugin/marketplace.json
├── doc-radar/
└── README.md
```
