# doc-radar-cowork

MCP-native version of doc-radar for the Claude desktop app (Cowork mode).

Identical functionality to `doc-radar` but uses Gmail, Google Calendar, and
Google Drive MCP connectors instead of the `gws` CLI. No CLI installation required.

## Requirements

Connect the following in the Claude desktop app:
- Gmail connector
- Google Calendar connector
- Google Drive connector (optional — for Drive attachment reading)

## Known limitations vs doc-radar

- **Attachment download**: The Gmail MCP connector does not support downloading
  binary attachments. Inline email content is processed fully; PDF/DOCX
  attachments are noted but not extracted. If files are also in Google Drive,
  the Drive connector can read them.
- **Email labelling**: The Gmail MCP connector does not support modifying labels.
  Deduplication relies entirely on SHA-256 content hashing (which is the primary
  deduplication mechanism in both versions).
