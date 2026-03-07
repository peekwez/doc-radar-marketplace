# Google Drive Scanning Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add Google Drive scanning to both plugins so legal documents stored in Drive are found, hashed, and tracked alongside Gmail-sourced documents.

**Architecture:** Both scan scripts are extended to emit Drive scan instructions after the Gmail section. Drive uses the same SHA-256 hash/dedup pipeline as Gmail. A new `google_drive` source type is added to the `source` enum in doc-extractor and deadline-scheduler. For `doc-radar` this uses the `gws drive files list` + `gws drive files get` CLI commands; for `doc-radar-cowork` this uses the `google_drive_search` / `google_drive_fetch` tools injected by the Claude app's Drive connector.

**Tech Stack:** Python 3, gws CLI (doc-radar), claude.ai native Drive tools (doc-radar-cowork), existing SHA-256 dedup pipeline (hash_check.py)

---

## Key Facts Before Starting

**Google Drive tool signatures (doc-radar-cowork, Claude app injected — no URL or MCP config needed):**
```
google_drive_search(
  api_query: string,          # Google Drive API query syntax
  semantic_query?: string,    # natural language filter (optional)
  order_by?: string,          # e.g. "modifiedTime desc"
  page_size?: integer,        # default 10
  request_page_token?: bool,
  page_token?: string
)

google_drive_fetch(
  document_ids: string[]      # list of Drive file IDs or full doc URLs
)
```

**gws Drive commands (doc-radar, CLI):**
```bash
gws drive files list --params '{"q":"<query>","fields":"files(id,name,mimeType,modifiedTime,owners,webViewLink,size)","orderBy":"modifiedTime desc","pageSize":50}'
gws drive files get --params '{"fileId":"<id>","alt":"media"}' > /tmp/drive-<id>.pdf
```

**Drive API query for legal documents:**
```
(name contains 'contract' OR name contains 'invoice' OR name contains 'NDA'
 OR name contains 'agreement' OR name contains 'purchase order' OR name contains 'SOW'
 OR name contains 'MSA' OR name contains 'lease' OR name contains 'retainer'
 OR name contains 'amendment' OR name contains 'quotation')
AND (mimeType='application/pdf'
     OR mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document'
     OR mimeType='text/plain')
AND modifiedTime > '<after_date>T00:00:00'
AND trashed=false
```

**Source field additions:**
- `source`: add `google_drive` to enum → `"gmail | google_drive | file_drop | direct_paste"`
- `source_id` for Drive: the Drive file ID (e.g. `"1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgVE2upms"`)
- Calendar event SOURCE URL: `https://drive.google.com/file/d/<source_id>/view`

**No hooks.json changes needed:** `gmail_scan.py` (doc-radar) and `scan_prompt.py` (doc-radar-cowork) are extended in-place. The existing SessionStart hooks already call these scripts, so the Drive section is injected automatically.

---

## Task 1: Add Drive query builder to `doc-radar/scripts/gmail_scan.py`

**Files:**
- Modify: `doc-radar/scripts/gmail_scan.py`
- Test: `doc-radar/tests/test_gmail_scan.py`

**Step 1: Write the failing tests**

Add to `doc-radar/tests/test_gmail_scan.py`:

```python
def test_build_drive_query_contains_legal_name_terms():
    """Drive query must include legal document name signals."""
    query = mod.build_drive_query("2026-02-07")
    assert "contract" in query
    assert "invoice" in query
    assert "NDA" in query

def test_build_drive_query_filters_mime_types():
    """Drive query must restrict to PDF, DOCX, and plain text."""
    query = mod.build_drive_query("2026-02-07")
    assert "application/pdf" in query
    assert "openxmlformats" in query

def test_build_drive_query_excludes_trashed():
    """Drive query must exclude trashed files."""
    query = mod.build_drive_query("2026-02-07")
    assert "trashed=false" in query

def test_build_drive_query_uses_after_date():
    """Drive query must include the modifiedTime filter with the after_date."""
    query = mod.build_drive_query("2026-02-07")
    assert "2026-02-07" in query
    assert "modifiedTime" in query

def test_gmail_scan_output_includes_drive_section(capsys, tmp_path):
    """scan output must include a Google Drive scan section."""
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "Google Drive" in out
    assert "gws drive files list" in out

def test_gmail_scan_output_drive_source_is_google_drive(capsys, tmp_path):
    """Drive section must instruct Claude to set source='google_drive'."""
    import gmail_scan
    gmail_scan.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "google_drive" in out
```

**Step 2: Run tests to verify they fail**

```bash
cd doc-radar && python -m pytest tests/test_gmail_scan.py -k "drive" -v
```
Expected: FAIL — `build_drive_query` not defined, "Google Drive" not in output.

**Step 3: Add `build_drive_query` and extend `main()` in `gmail_scan.py`**

Add after the `build_gmail_query` function:

```python
DRIVE_LEGAL_NAMES = (
    "name contains 'contract' OR name contains 'invoice' OR name contains 'NDA' "
    "OR name contains 'agreement' OR name contains 'purchase order' OR name contains 'SOW' "
    "OR name contains 'MSA' OR name contains 'lease' OR name contains 'retainer' "
    "OR name contains 'amendment' OR name contains 'quotation'"
)

DRIVE_MIME_TYPES = (
    "mimeType='application/pdf' "
    "OR mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' "
    "OR mimeType='text/plain'"
)


def build_drive_query(after_date: str) -> str:
    """Build a Google Drive API query string for legal documents modified since after_date.
    after_date format: YYYY-MM-DD (e.g. '2026-02-07')
    """
    return (
        f"({DRIVE_LEGAL_NAMES}) "
        f"AND ({DRIVE_MIME_TYPES}) "
        f"AND modifiedTime > '{after_date}T00:00:00' "
        f"AND trashed=false"
    )
```

At the end of `main()`, after the Gmail section print, add:

```python
    drive_query = build_drive_query(after_date.replace("/", "-"))
    drive_params = json.dumps({
        "q": drive_query,
        "fields": "files(id,name,mimeType,modifiedTime,owners,webViewLink,size)",
        "orderBy": "modifiedTime desc",
        "pageSize": 50,
    })

    print(f"""
=== DOC RADAR: Google Drive Scan ===
Timestamp  : {now_iso}
Date range : modified after {after_date.replace("/", "-")}

STEP A — List legal document candidates from Google Drive:
  gws drive files list --params '{drive_params}'

  This returns a list of files with id, name, mimeType, modifiedTime,
  owners, webViewLink, and size.

STEP B — For each file returned, download content:
  gws drive files get --params '{{"fileId":"<fileId>","alt":"media"}}' \\
    > /tmp/drive-<fileId>.<ext>

  Use the file's mimeType to determine the extension:
    application/pdf                          -> .pdf
    application/vnd.openxmlformats-...docx  -> .docx
    text/plain                               -> .txt

STEP C — For each downloaded file, invoke the skill chain:

  Invoke `doc-radar:legal-doc-detector` on the file content.
  Set source='google_drive' and source_id='<fileId>' when passing to
  doc-extractor. The file's webViewLink can be used in calendar events.

  DO NOT run scripts directly. The skill chain manages all sub-steps.

NOTE: If gws drive returns HTTP 429 (rate limit):
  Wait 60 seconds before retrying.
  Process only files already downloaded — do not re-fetch.

NOTE: Files already processed are deduplicated via SHA-256. Re-scanning the
  same file will produce a duplicate hash and be skipped automatically.
""")
```

**Step 4: Run tests to verify they pass**

```bash
cd doc-radar && python -m pytest tests/test_gmail_scan.py -v
```
Expected: All tests PASS (including the 3 existing + 6 new = 9 total).

**Step 5: Commit**

```bash
git add doc-radar/scripts/gmail_scan.py doc-radar/tests/test_gmail_scan.py
git commit -m "feat(doc-radar): add Google Drive scan section to gmail_scan.py"
```

---

## Task 2: Add Drive query builder to `doc-radar-cowork/scripts/scan_prompt.py`

**Files:**
- Modify: `doc-radar-cowork/scripts/scan_prompt.py`
- Test: `doc-radar-cowork/tests/test_scan_prompt.py`

**Step 1: Write the failing tests**

Add to `doc-radar-cowork/tests/test_scan_prompt.py`:

```python
def test_build_drive_query_contains_legal_name_terms():
    """Drive query must include legal document name signals."""
    query = mod.build_drive_query("2026-02-07")
    assert "contract" in query
    assert "invoice" in query
    assert "NDA" in query

def test_build_drive_query_filters_mime_types():
    """Drive query must restrict to PDF, DOCX, and plain text."""
    query = mod.build_drive_query("2026-02-07")
    assert "application/pdf" in query
    assert "openxmlformats" in query

def test_build_drive_query_excludes_trashed():
    """Drive query must exclude trashed files."""
    query = mod.build_drive_query("2026-02-07")
    assert "trashed=false" in query

def test_build_drive_query_uses_after_date():
    """Drive query must include the modifiedTime filter with the after_date."""
    query = mod.build_drive_query("2026-02-07")
    assert "2026-02-07" in query
    assert "modifiedTime" in query

def test_scan_prompt_output_includes_drive_section(capsys, tmp_path):
    """scan output must include a Google Drive scan section."""
    import scan_prompt
    scan_prompt.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "Google Drive" in out
    assert "google_drive_search" in out
    assert "google_drive_fetch" in out

def test_scan_prompt_output_drive_source_is_google_drive(capsys, tmp_path):
    """Drive section must instruct Claude to set source='google_drive'."""
    import scan_prompt
    scan_prompt.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "google_drive" in out

def test_scan_prompt_drive_uses_no_gws(capsys, tmp_path):
    """Drive section must NOT reference gws — only MCP tool calls."""
    import scan_prompt
    scan_prompt.main(state_file=tmp_path / "state.json")
    out = capsys.readouterr().out
    assert "gws" not in out
```

**Step 2: Run tests to verify they fail**

```bash
cd doc-radar-cowork && python -m pytest tests/test_scan_prompt.py -k "drive" -v
```
Expected: FAIL — `build_drive_query` not defined, "Google Drive" not in output.

**Step 3: Add `build_drive_query` and extend `main()` in `scan_prompt.py`**

Add after the `build_gmail_query` function (identical query builder — same Drive API syntax):

```python
DRIVE_LEGAL_NAMES = (
    "name contains 'contract' OR name contains 'invoice' OR name contains 'NDA' "
    "OR name contains 'agreement' OR name contains 'purchase order' OR name contains 'SOW' "
    "OR name contains 'MSA' OR name contains 'lease' OR name contains 'retainer' "
    "OR name contains 'amendment' OR name contains 'quotation'"
)

DRIVE_MIME_TYPES = (
    "mimeType='application/pdf' "
    "OR mimeType='application/vnd.openxmlformats-officedocument.wordprocessingml.document' "
    "OR mimeType='text/plain'"
)


def build_drive_query(after_date: str) -> str:
    """Build a Google Drive API query string for legal documents modified since after_date.
    after_date format: YYYY-MM-DD (e.g. '2026-02-07')
    """
    return (
        f"({DRIVE_LEGAL_NAMES}) "
        f"AND ({DRIVE_MIME_TYPES}) "
        f"AND modifiedTime > '{after_date}T00:00:00' "
        f"AND trashed=false"
    )
```

At the end of `main()`, after the Gmail section print, add:

```python
    drive_query = build_drive_query(after_date.replace("/", "-"))

    print(f"""
=== DOC RADAR: Google Drive Scan ===
Timestamp  : {now_iso}
Date range : modified after {after_date.replace("/", "-")}

STEP A — Search Google Drive for legal document candidates:

  Call: google_drive_search(
    api_query="{drive_query}",
    order_by="modifiedTime desc",
    page_size=50
  )

  This returns a list of files with their IDs, names, MIME types,
  modification dates, and owners.

STEP B — Fetch content for each file returned:

  Call: google_drive_fetch(document_ids=["<fileId>", ...])

  This returns the text content of each file directly — no download needed.
  Pass up to 10 file IDs per call to avoid context overload.

STEP C — For each file fetched, invoke the skill chain:

  Invoke `doc-radar-cowork:legal-doc-detector` on the file content.
  Set source='google_drive' and source_id='<fileId>' when passing to
  doc-extractor. The Drive file URL is:
    https://drive.google.com/file/d/<fileId>/view

  DO NOT run scripts directly. The skill chain manages all sub-steps
  (deduplication, checkpointing, hash recording) internally.

NOTE: If google_drive_search is not available (tool not found):
  Ensure the Google Drive connector is authorised in Claude settings.
  The Drive connector is automatically available in the Claude app.

NOTE: Files already processed are deduplicated via SHA-256. Re-scanning the
  same file will produce a duplicate hash and be skipped automatically.
""")
```

**Step 4: Run tests to verify they pass**

```bash
cd doc-radar-cowork && python -m pytest tests/test_scan_prompt.py -v
```
Expected: All tests PASS.

**Step 5: Commit**

```bash
git add doc-radar-cowork/scripts/scan_prompt.py doc-radar-cowork/tests/test_scan_prompt.py
git commit -m "feat(doc-radar-cowork): add Google Drive scan section to scan_prompt.py"
```

---

## Task 3: Update `source` enum in both `doc-extractor/SKILL.md` files

**Files:**
- Modify: `doc-radar/skills/doc-extractor/SKILL.md`
- Modify: `doc-radar-cowork/skills/doc-extractor/SKILL.md`

No tests needed — these are skill markdown files.

**Step 1: In both files, find and update the source field line**

Find:
```
  "source": "gmail | file_drop | direct_paste",
  "source_id": "gmail message ID, full file path, or 'user_paste'",
```

Replace with:
```
  "source": "gmail | google_drive | file_drop | direct_paste",
  "source_id": "gmail message ID, Drive file ID, full file path, or 'user_paste'",
```

**Step 2: Verify change in both files**

```bash
grep -n "source" doc-radar/skills/doc-extractor/SKILL.md | head -5
grep -n "source" doc-radar-cowork/skills/doc-extractor/SKILL.md | head -5
```
Expected: both show `google_drive` in the source line.

**Step 3: Commit**

```bash
git add doc-radar/skills/doc-extractor/SKILL.md doc-radar-cowork/skills/doc-extractor/SKILL.md
git commit -m "feat: add google_drive to source enum in doc-extractor skills"
```

---

## Task 4: Update SOURCE URL in both `deadline-scheduler/SKILL.md` files

**Files:**
- Modify: `doc-radar/skills/deadline-scheduler/SKILL.md`
- Modify: `doc-radar-cowork/skills/deadline-scheduler/SKILL.md`

**Step 1: In both files, find and update the SOURCE block**

Find:
```
[construct URL based on source field:]
  gmail        -> https://mail.google.com/mail/u/0/#all/[source_id]
  file_drop    -> [source_id — full file path]
  direct_paste -> Pasted directly in conversation
```

Replace with:
```
[construct URL based on source field:]
  gmail        -> https://mail.google.com/mail/u/0/#all/[source_id]
  google_drive -> https://drive.google.com/file/d/[source_id]/view
  file_drop    -> [source_id — full file path]
  direct_paste -> Pasted directly in conversation
```

**Step 2: Verify**

```bash
grep -n "google_drive" doc-radar/skills/deadline-scheduler/SKILL.md
grep -n "google_drive" doc-radar-cowork/skills/deadline-scheduler/SKILL.md
```
Expected: one match in each file.

**Step 3: Commit**

```bash
git add doc-radar/skills/deadline-scheduler/SKILL.md doc-radar-cowork/skills/deadline-scheduler/SKILL.md
git commit -m "feat: add google_drive source URL to deadline-scheduler skills"
```

---

## Task 5: Update `legal-doc-detector/SKILL.md` in both plugins

**Files:**
- Modify: `doc-radar/skills/legal-doc-detector/SKILL.md`
- Modify: `doc-radar-cowork/skills/legal-doc-detector/SKILL.md`

**doc-radar version:**

After the "## Gmail Access via gws" section, add a new section:

```markdown
## Google Drive Access via gws

To scan Drive for legal documents, use these gws commands via Bash:

```bash
# List legal document candidates modified since last scan
gws drive files list \
  --params '{"q":"<DRIVE_QUERY>","fields":"files(id,name,mimeType,modifiedTime,owners,webViewLink,size)","orderBy":"modifiedTime desc","pageSize":50}'

# Download a file from Drive to a local path
gws drive files get \
  --params '{"fileId":"<fileId>","alt":"media"}' \
  > /tmp/drive-<fileId>.<ext>
```

Use the `Read` tool on the downloaded local file path to extract its text content.
Set `source='google_drive'` and `source_id='<fileId>'` when passing to `doc-radar:doc-extractor`.

Supported MIME types to download:
- `application/pdf` → `.pdf`
- `application/vnd.openxmlformats-officedocument.wordprocessingml.document` → `.docx`
- `text/plain` → `.txt`
```

**doc-radar-cowork version:**

After the "## Gmail Access via MCP Connector" section, add a new section:

```markdown
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
```

Also update the "## Trigger Conditions" section in both files — add:
```
5. SessionStart hook output contains Google Drive scan results
```

**Step 1: Edit both files as described above**

**Step 2: Verify**

```bash
grep -n "Google Drive" doc-radar/skills/legal-doc-detector/SKILL.md
grep -n "google_drive_search" doc-radar-cowork/skills/legal-doc-detector/SKILL.md
```

**Step 3: Commit**

```bash
git add doc-radar/skills/legal-doc-detector/SKILL.md doc-radar-cowork/skills/legal-doc-detector/SKILL.md
git commit -m "feat: add Google Drive scanning section to legal-doc-detector skills"
```

---

## Task 6: Update plugin descriptions and dashboard source link

**Files:**
- Modify: `doc-radar/.claude-plugin/plugin.json`
- Modify: `doc-radar-cowork/.claude-plugin/plugin.json`
- Modify: `doc-radar/scripts/dashboard.py`
- Modify: `doc-radar-cowork/scripts/dashboard.py`

**Step 1: Update plugin.json descriptions**

`doc-radar/plugin.json` — update description to include "Google Drive":
```
"description": "Automatically scans Gmail and Google Drive for legal and financially binding documents..."
```

`doc-radar-cowork/plugin.json` — update description:
```
"description": "Scans Gmail and Google Drive for legal/financial documents using native MCP connectors..."
```

**Step 2: Update dashboard `gmail_link` function in both `dashboard.py` files**

Find:
```python
def gmail_link(r: dict) -> str:
    if r.get("source") == "gmail" and r.get("source_id"):
        url = f"https://mail.google.com/mail/u/0/#all/{r['source_id']}"
        return f'<a href="{url}" target="_blank" class="text-blue-600 hover:underline text-xs">Open email ↗</a>'
    elif r.get("source") == "file_drop":
        return f'<span class="text-xs text-slate-500">{html_mod.escape(r.get("source_id", ""))}</span>'
    return '<span class="text-xs text-slate-400">Direct paste</span>'
```

Replace with:
```python
def gmail_link(r: dict) -> str:
    source    = r.get("source", "")
    source_id = r.get("source_id", "")
    if source == "gmail" and source_id:
        url = f"https://mail.google.com/mail/u/0/#all/{source_id}"
        return f'<a href="{url}" target="_blank" class="text-blue-600 hover:underline text-xs">Open email ↗</a>'
    elif source == "google_drive" and source_id:
        url = f"https://drive.google.com/file/d/{source_id}/view"
        return f'<a href="{url}" target="_blank" class="text-blue-600 hover:underline text-xs">Open in Drive ↗</a>'
    elif source == "file_drop":
        return f'<span class="text-xs text-slate-500">{html_mod.escape(source_id)}</span>'
    return '<span class="text-xs text-slate-400">Direct paste</span>'
```

**Step 3: Run dashboard tests**

```bash
python -m pytest doc-radar/tests/test_dashboard.py doc-radar-cowork/tests/test_dashboard.py -v
```
Expected: All PASS (existing dashboard tests don't test `gmail_link` with Drive source, so no new tests needed here).

**Step 4: Commit**

```bash
git add doc-radar/.claude-plugin/plugin.json doc-radar-cowork/.claude-plugin/plugin.json \
        doc-radar/scripts/dashboard.py doc-radar-cowork/scripts/dashboard.py
git commit -m "feat: add google_drive source link in dashboard and update plugin descriptions"
```

---

## Task 7: Run full test suite and verify

**Step 1: Run all tests**

```bash
python -m pytest doc-radar/tests/ doc-radar-cowork/tests/ -v
```
Expected: All tests pass (was 34 cowork + existing doc-radar tests, now with 6 new Drive tests per plugin = +12 total).

**Step 2: Spot-check Drive query output**

```bash
cd doc-radar && python3 scripts/gmail_scan.py 2>/dev/null | grep -A5 "Google Drive"
cd doc-radar-cowork && python3 scripts/scan_prompt.py 2>/dev/null | grep -A5 "Google Drive"
```
Expected: both print the Drive scan section with their respective tool/command references.

**Step 3: Final commit (if any loose ends)**

```bash
git add -A
git commit -m "chore: Google Drive scanning complete — all tests passing"
```
