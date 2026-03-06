# doc-radar

A Claude Code plugin that automatically scans Gmail and watched folders for
legal and financially binding documents, extracts key dates, deduplicates
via SHA-256 content hashing, and creates Google Calendar events with
tiered reminders.

## Document Types Covered

| Type | Key Dates | Calendar Events |
|------|-----------|-----------------|
| Contract / MSA | Effective, Expiry, Auto-renewal | Expiry + 30/14/7/1d reminders; renewal notice window |
| NDA | Effective, Expiry | Expiry + 30/7/1d reminders |
| SOW | Start, Milestones, Delivery | Each milestone + final delivery |
| Invoice | Issue, Due date | Due date + 7/3/1d reminders |
| Purchase Order | Order date, Delivery deadline | Delivery + 14/7/1d reminders |
| Lease / Retainer | Effective, Term end | Same as contract |
| Amendment | Amendment date, New expiry | Updates existing contract logic |
| Quotation | Issue, Valid until | Valid-until + 3/1d reminders |

---

## Prerequisites

### gws — Google Workspace CLI (Required)

doc-radar uses `gws` for all Gmail and Calendar operations. It provides
structured JSON output, handles OAuth securely via the OS keyring, and
works reliably from shell scripts and hooks — no MCP connector URLs needed.

**Install:**
```bash
npm install -g @googleworkspace/cli
```

**Authenticate (one-time setup):**
```bash
gws auth setup
# Requires the gcloud CLI: https://cloud.google.com/sdk/docs/install
# Creates a Google Cloud project, enables APIs, and logs you in via OAuth.
```

**Manual OAuth (if gcloud is unavailable):**
1. Open [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Create an OAuth Desktop app credential
3. Download the client JSON to `~/.config/gws/client_secret.json`
4. Run `gws auth login`

**Verify it's working:**
```bash
gws gmail users messages list --params '{"userId":"me","maxResults":1}'
gws calendar events list --params '{"calendarId":"primary","maxResults":1}'
```

Once authenticated, all doc-radar scripts and hooks inherit credentials
automatically. No tokens to manage, no connector URLs to configure.

---

## How It Works

1. **SessionStart hook** fires every time Claude Code opens. `scripts/gmail_scan.py`
   reads `.tracker/state.json` for the last-run timestamp, builds a Gmail
   date-range query, and injects the scan brief (including concrete `gws`
   commands) into Claude's context.

2. **Claude processes the scan** using three chained skills:
   - `legal-doc-detector` — identifies legal docs, filters junk, provides
     `gws gmail` commands for fetching and labelling emails
   - `doc-extractor` — computes SHA-256, checks for duplicates, extracts fields
   - `deadline-scheduler` — creates calendar events via `gws calendar events insert`,
     updates run log

3. **PostToolUse/Write hook** watches `~/legal-inbox/` for new files and
   triggers the same pipeline on any supported file dropped there.

---

## Installation (Claude Code)

```bash
# From local directory (development)
/plugin marketplace add ~/Desktop/doc-radar-marketplace
/plugin install doc-radar@doc-radar-marketplace

# From GitHub (once published)
/plugin marketplace add github:peekwez/doc-radar-marketplace
/plugin install doc-radar@doc-radar-marketplace
```

---

## Tracker Folder (`.tracker/`)

| File | Purpose |
|------|---------|
| `state.json` | Last run timestamp + run count |
| `runs.jsonl` | Full record of every processed document |
| `seen_hashes.jsonl` | SHA-256 hashes of all seen content (dedup) |
| `skipped.jsonl` | Junk-filtered + duplicate-skipped items |
| `errors.jsonl` | Non-fatal errors (scan continues on error) |

---

## File Drop

Place files in `~/legal-inbox/` for automatic processing. Supported formats:
`.pdf`, `.docx`, `.doc`, `.txt`, `.eml`, `.msg`, `.xlsx`, `.xls`, `.csv`

---

## Junk Filter

The following are automatically skipped and logged to `skipped.jsonl`:
- Marketing/promotional emails (% off, promo codes, newsletters)
- Automated system noise (CI/CD, monitoring alerts, password resets)
- Social/platform notifications (LinkedIn, GitHub digests)
- Small consumer receipts under $500 with no contract reference

Legal override: if strong legal signal words appear in the email body,
the email is processed even if the sender domain matches a junk domain.

---

## Rolling Back

This repo is managed with git. To revert to the MCP-based version:

```bash
cd ~/Desktop/doc-radar-marketplace
git log --oneline          # find the commit to revert to
git checkout <commit-sha>  # inspect that version
git checkout main          # return to latest
git revert HEAD            # undo the last commit non-destructively
```
