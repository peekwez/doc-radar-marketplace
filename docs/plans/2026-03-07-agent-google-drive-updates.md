# Agent Google Drive + Skill Reference Updates Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Update both `doc-radar-agent.md` files to (1) qualify all skill references with their namespace so the Skill tool is actually invoked, and (2) cover Google Drive scanning — add Drive tools, split the scan summary counter, and align the workflow description with what `scan_prompt.py` / `gmail_scan.py` actually inject at session start.

**Architecture:** Pure markdown edits to two agent instruction files. No scripts, no tests (markdown has no unit tests).

**Tech Stack:** Markdown only.

---

### Task 1: Update `doc-radar-cowork/agents/doc-radar-agent.md`

**Files:**
- Modify: `doc-radar-cowork/agents/doc-radar-agent.md`

Apply all six fixes below in a single edit pass.

---

**Fix 1 — YAML description: qualify skill names**

Current:
```
  Orchestrating agent for the doc-radar-cowork plugin. Chains
  legal-doc-detector → doc-extractor → deadline-scheduler in a single
  autonomous workflow.
```

Replace with:
```
  Orchestrating agent for the doc-radar-cowork plugin. Chains
  doc-radar-cowork:legal-doc-detector → doc-radar-cowork:doc-extractor →
  doc-radar-cowork:deadline-scheduler in a single autonomous workflow.
```

---

**Fix 2 — Workflow Step 2: scan context description**

Current:
```
2. **Receive scan context** — from SessionStart hook output (Gmail scan
   results via scan_prompt.py) or a direct user request with document
   content/paths.
```

Replace with:
```
2. **Receive scan context** — from SessionStart hook output (Gmail **and
   Google Drive** scan results via scan_prompt.py) or a direct user request
   with document content/paths.
```

---

**Fix 3 — Workflow Step 3 and Step 4: qualify skill names**

Current step 3:
```
3. **Run legal-doc-detector** on all items. Separate into:
```

Replace with:
```
3. **Invoke `doc-radar-cowork:legal-doc-detector`** on all items. Separate into:
```

Current step 4a:
```
   a. `doc-extractor` — uses `hash_check.py --check-only` to detect duplicates,
```

Replace with:
```
   a. `doc-radar-cowork:doc-extractor` — uses `hash_check.py --check-only` to detect duplicates,
```

Current step 4d:
```
   d. `deadline-scheduler` — create calendar events via `gcal_create_event`,
```

Replace with:
```
   d. `doc-radar-cowork:deadline-scheduler` — create calendar events via `gcal_create_event`,
```

---

**Fix 4 — Summary block: split "Emails/files scanned"**

Current:
```
   Emails/files scanned   : N
```

Replace with:
```
   Gmail messages scanned : N
   Drive files scanned    : N
```

---

**Fix 5 — Error handling and attachment note: qualify skill names**

Current error handling line:
```
- If doc-extractor fails: write `detected` checkpoint with error, log, continue
```

Replace with:
```
- If `doc-radar-cowork:doc-extractor` fails: write `detected` checkpoint with error, log, continue
```

Current attachment note:
```
  - ⚠️ Attachment download is NOT available — see legal-doc-detector for handling
```

Replace with:
```
  - ⚠️ Attachment download is NOT available — see `doc-radar-cowork:legal-doc-detector` for handling
```

---

**Fix 6 — Tools Available: add Google Drive section + update Prerequisites**

After the `- **Google Calendar MCP connector** — ...` block and before `- **Read** — ...`, insert:

```
- **Google Drive** (auto-injected by Claude app) — search and fetch Drive files:
  - `google_drive_search(api_query=..., order_by="modifiedTime desc", page_size=50)` — find legal document candidates by name/MIME/date
  - `google_drive_fetch(document_ids=[...])` — fetch text content of up to 10 files per call
  - Set `source='google_drive'` and `source_id='<fileId>'` when passing to `doc-radar-cowork:doc-extractor`
  - Drive file URL pattern: `https://drive.google.com/file/d/<fileId>/view`
```

Replace the Prerequisites verify block:

Current:
```
Verify connectivity by calling:
```
search_messages(query="label:inbox", max_results=1)
gcal_list_events(calendarId="primary", maxResults=1)
```

If either call fails with an auth error, re-authorise the connector in
Claude settings → Connectors.
```

Replace with:
```
Verify connectivity by calling:
```
search_messages(query="label:inbox", max_results=1)
gcal_list_events(calendarId="primary", maxResults=1)
google_drive_search(api_query="trashed=false", page_size=1)
```

If any call fails with an auth error, re-authorise the relevant connector
in Claude settings → Connectors. The Google Drive connector is
auto-injected by the Claude app when enabled — no `.mcp.json` entry is
needed for it.
```

---

**Step 1: Apply all six fixes to `doc-radar-cowork/agents/doc-radar-agent.md`**

**Step 2: Read the file back. Confirm:**
- All three skill names use `doc-radar-cowork:` prefix everywhere they appear
- "Gmail and Google Drive scan results" in step 2
- Summary has both `Gmail messages scanned` and `Drive files scanned`
- Google Drive tools block present between Calendar and Read
- `google_drive_search` verification call in Prerequisites

**Step 3: Commit**

```bash
git add doc-radar-cowork/agents/doc-radar-agent.md
git commit -m "feat(cowork): qualify skill names and add Google Drive to doc-radar-agent"
```

---

### Task 2: Update `doc-radar/agents/doc-radar-agent.md`

**Files:**
- Modify: `doc-radar/agents/doc-radar-agent.md`

Apply all five fixes below.

---

**Fix 1 — YAML description: qualify skill names**

Current:
```
  Orchestrating agent for the doc-radar plugin. Chains legal-doc-detector →
  doc-extractor → deadline-scheduler in a single autonomous workflow.
```

Replace with:
```
  Orchestrating agent for the doc-radar plugin. Chains
  doc-radar:legal-doc-detector → doc-radar:doc-extractor →
  doc-radar:deadline-scheduler in a single autonomous workflow.
```

---

**Fix 2 — Workflow Step 2: scan context description**

Current:
```
2. **Receive scan context** — from SessionStart hook output (Gmail scan
   results) or a direct user request with document content/paths.
```

Replace with:
```
2. **Receive scan context** — from SessionStart hook output (Gmail **and
   Google Drive** scan results via gmail_scan.py) or a direct user request
   with document content/paths.
```

---

**Fix 3 — Workflow Steps 3 and 4: qualify skill names**

Current step 3:
```
3. **Run legal-doc-detector** on all items. Separate into:
```

Replace with:
```
3. **Invoke `doc-radar:legal-doc-detector`** on all items. Separate into:
```

Current step 4a:
```
   a. `doc-extractor` — uses `hash_check.py --check-only` to detect duplicates,
```

Replace with:
```
   a. `doc-radar:doc-extractor` — uses `hash_check.py --check-only` to detect duplicates,
```

Current step 4d:
```
   d. `deadline-scheduler` — create calendar events via gws, then:
```

Replace with:
```
   d. `doc-radar:deadline-scheduler` — create calendar events via gws, then:
```

---

**Fix 4 — Summary block: split "Emails/files scanned"**

Current:
```
   Emails/files scanned   : N
```

Replace with:
```
   Gmail messages scanned : N
   Drive files scanned    : N
```

---

**Fix 5 — Error handling line: qualify skill name + add Drive error + gws Drive commands**

Current error handling line:
```
- If doc-extractor fails: write `detected` checkpoint with error, log, continue
```

Replace with:
```
- If `doc-radar:doc-extractor` fails: write `detected` checkpoint with error, log, continue
- If `gws drive files get` fails for a file: log to errors.jsonl with `source_id` and filename, skip that file, continue with remaining Drive files
```

In the Tools Available section, the current gws bullet ends with:
```
  - `gws calendar events insert` — create deadline/reminder events
  - Always use `--dry-run` first on insert/modify operations
```

Extend to add (inside the same bullet):
```
  - `gws drive files list` — list legal document candidates (supply Drive query from `build_drive_query()` in gmail_scan.py)
  - `gws drive files get --params '{"fileId":"<id>","alt":"media"}'` — download file to `/tmp/drive-<id>.<ext>`; use `Read` tool on the downloaded path for text extraction
```

---

**Step 1: Apply all five fixes to `doc-radar/agents/doc-radar-agent.md`**

**Step 2: Read the file back. Confirm:**
- All three skill names use `doc-radar:` prefix everywhere they appear
- "Gmail and Google Drive scan results" in step 2
- Summary has both `Gmail messages scanned` and `Drive files scanned`
- gws drive commands present in Tools Available

**Step 3: Commit**

```bash
git add doc-radar/agents/doc-radar-agent.md
git commit -m "feat(doc-radar): qualify skill names and add Google Drive to doc-radar-agent"
```

---

### Task 3: Push, create PR, and merge

**Step 1: Push both commits**

```bash
git push -u origin <current-branch>
```

**Step 2: Create PR targeting main**

```bash
gh pr create --title "feat: qualify skill names and add Drive scanning to both doc-radar-agent files" \
  --body "..." --base main
```

**Step 3: Merge**

```bash
gh pr merge <number> --merge --delete-branch
```
