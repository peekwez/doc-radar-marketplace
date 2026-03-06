# doc-radar v1.1.0 Enhancement Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Harden junk filtering, add subscription renewals as a first-class doc type, redesign calendar event descriptions, and add error recovery with checkpointing and retry.

**Architecture:** Python script changes (hash_check, gmail_scan, two new scripts) handle infrastructure concerns; skill/agent markdown files handle Claude's behaviour. All changes are backwards-compatible — existing tracker files remain valid.

**Tech Stack:** Python 3.10+, pytest, gws CLI (Google Workspace CLI), Claude Code plugin system

**Design doc:** `docs/plans/2026-03-05-doc-radar-enhancements-design.md`

---

## Task 1: Fix `hash_check.py` — add `--check-only` flag

**Why:** Currently the hash is recorded as "seen" before calendar creation. If scheduling fails, the doc is permanently lost — marked seen but never scheduled. We need to separate "check for duplicate" from "record as seen".

**Files:**
- Modify: `scripts/hash_check.py`
- Create: `tests/test_hash_check.py`

---

**Step 1: Create tests directory and write failing tests**

Create `tests/__init__.py` (empty) and `tests/test_hash_check.py`:

```python
"""Tests for hash_check.py --check-only behaviour."""
import json
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "hash_check.py"


def run_hash_check(args: list[str], content: str = "test content") -> dict:
    """Run hash_check.py with given args, return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True, text=True
    )
    return json.loads(result.stdout)


def test_check_only_does_not_record(tmp_path, monkeypatch):
    """--check-only should return 'new' but NOT write to seen_hashes.jsonl."""
    hashes_file = tmp_path / "seen_hashes.jsonl"
    # Patch HASHES_LOG by passing a fake plugin dir structure
    import importlib, types
    # We test via subprocess so we need a temp hashes file
    # Use --file with a temp content file instead
    content_file = tmp_path / "doc.txt"
    content_file.write_text("unique content abc123")

    # Run with --check-only (hashes file should NOT be written)
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file), "--check-only"],
        capture_output=True, text=True,
        env={"HASH_CHECK_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    )
    output = json.loads(result.stdout)
    assert output["status"] == "new"
    assert not hashes_file.exists(), "check-only must not write to seen_hashes.jsonl"


def test_check_only_detects_existing_duplicate(tmp_path):
    """--check-only correctly identifies a previously recorded hash."""
    content_file = tmp_path / "doc.txt"
    content_file.write_text("duplicate content xyz")

    env = {"HASH_CHECK_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}

    # First: record without --check-only
    subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file)],
        capture_output=True, text=True, env=env
    )

    # Second: check-only on same content — should show duplicate
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file), "--check-only"],
        capture_output=True, text=True, env=env
    )
    output = json.loads(result.stdout)
    assert output["status"] == "duplicate"


def test_normal_mode_records_hash(tmp_path):
    """Without --check-only, hash IS written to seen_hashes.jsonl."""
    hashes_file = tmp_path / "seen_hashes.jsonl"
    content_file = tmp_path / "doc.txt"
    content_file.write_text("recordable content 999")

    env = {"HASH_CHECK_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--file", str(content_file)],
        capture_output=True, text=True, env=env
    )
    output = json.loads(result.stdout)
    assert output["status"] == "new"
    assert hashes_file.exists(), "normal mode must write to seen_hashes.jsonl"
```

**Step 2: Run tests to verify they fail**

```bash
cd /Users/kwesi/Desktop/doc-radar-marketplace/doc-radar
python -m pytest tests/test_hash_check.py -v 2>&1 | head -40
```

Expected: FAIL — `--check-only` flag does not exist yet.

---

**Step 3: Implement `--check-only` in `hash_check.py`**

In `hash_check.py`, make two changes:

1. Add `HASH_CHECK_TRACKER_DIR` env override so tests can inject a temp path:
```python
import os
# Near the top, after PLUGIN_DIR / TRACKER_DIR are defined:
_env_tracker = os.environ.get("HASH_CHECK_TRACKER_DIR")
if _env_tracker:
    TRACKER_DIR = Path(_env_tracker)
    HASHES_LOG  = TRACKER_DIR / "seen_hashes.jsonl"
```

2. Add `--check-only` argument and gate the `record_hash` call:
```python
# In the argument parser section, add:
parser.add_argument("--check-only", action="store_true",
                    help="Check for duplicate without recording to seen-hashes log")

# In main(), replace the else branch:
else:
    if not args.check_only:
        record_hash(digest, source_id=args.source_id or "unknown")
    result = {"status": "new", "hash": digest}
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_hash_check.py -v
```

Expected: 3 passed.

**Step 5: Commit**

```bash
git add scripts/hash_check.py tests/__init__.py tests/test_hash_check.py
git commit -m "feat: add --check-only flag to hash_check.py

Separates duplicate detection from hash recording. Pipeline now calls
--check-only first, and records only after successful calendar creation,
preventing silent document loss on scheduling failure.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 2: Add `scripts/checkpoint.py`

**Why:** Tracks per-document pipeline state in `.tracker/pending.jsonl`. Each doc writes a checkpoint after `detected`, `extracted`, `scheduled`, and `complete` stages. Items not yet at `complete` are surfaced for retry on next session.

**Files:**
- Create: `scripts/checkpoint.py`
- Create: `tests/test_checkpoint.py`

---

**Step 1: Write failing tests**

Create `tests/test_checkpoint.py`:

```python
"""Tests for checkpoint.py — per-doc pipeline state tracking."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "checkpoint.py"


def run_checkpoint(args: list[str], tmp_path: Path) -> dict:
    env = {"CHECKPOINT_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)] + args,
        capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def read_pending(tmp_path: Path) -> list[dict]:
    f = tmp_path / "pending.jsonl"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text().splitlines() if l.strip()]


def test_write_detected_checkpoint(tmp_path):
    """Writing a 'detected' checkpoint creates a pending.jsonl entry."""
    run_checkpoint([
        "--run-id", "run-001", "--sha256", "abc123", "--doc-ref", "INV-001",
        "--source-id", "gmail:msg1", "--stage", "detected"
    ], tmp_path)
    entries = read_pending(tmp_path)
    assert len(entries) == 1
    assert entries[0]["stage"] == "detected"
    assert entries[0]["run_id"] == "run-001"


def test_update_stage_in_place(tmp_path):
    """Updating stage for same run_id replaces the entry, not appends."""
    base_args = ["--run-id", "run-002", "--sha256", "def456",
                 "--doc-ref", "PO-002", "--source-id", "gmail:msg2"]
    run_checkpoint(base_args + ["--stage", "detected"], tmp_path)
    run_checkpoint(base_args + ["--stage", "extracted"], tmp_path)
    entries = read_pending(tmp_path)
    assert len(entries) == 1
    assert entries[0]["stage"] == "extracted"


def test_complete_stage_removes_entry(tmp_path):
    """Marking stage=complete removes the entry from pending.jsonl."""
    base_args = ["--run-id", "run-003", "--sha256", "ghi789",
                 "--doc-ref", "CTR-003", "--source-id", "file:/tmp/x.pdf"]
    run_checkpoint(base_args + ["--stage", "detected"], tmp_path)
    run_checkpoint(base_args + ["--stage", "complete"], tmp_path)
    entries = read_pending(tmp_path)
    assert entries == []


def test_multiple_docs_tracked_independently(tmp_path):
    """Multiple documents maintain independent checkpoint state."""
    run_checkpoint(["--run-id", "r1", "--sha256", "h1", "--doc-ref", "D1",
                    "--source-id", "s1", "--stage", "detected"], tmp_path)
    run_checkpoint(["--run-id", "r2", "--sha256", "h2", "--doc-ref", "D2",
                    "--source-id", "s2", "--stage", "extracted"], tmp_path)
    entries = read_pending(tmp_path)
    assert len(entries) == 2
    stages = {e["run_id"]: e["stage"] for e in entries}
    assert stages["r1"] == "detected"
    assert stages["r2"] == "extracted"
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_checkpoint.py -v 2>&1 | head -20
```

Expected: FAIL — script doesn't exist yet.

---

**Step 3: Create `scripts/checkpoint.py`**

```python
#!/usr/bin/env python3
"""
checkpoint.py
-------------
Writes and updates per-document pipeline checkpoints in .tracker/pending.jsonl.
Items at stage 'complete' are removed. All other stages are upserted in place.

Usage:
    python3 checkpoint.py --run-id <uuid> --sha256 <hash> --doc-ref <ref> \
                          --source-id <id> --stage <stage>

Stages: detected | extracted | scheduled | complete
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_DIR    = Path(__file__).parent.parent
TRACKER_DIR   = Path(os.environ.get("CHECKPOINT_TRACKER_DIR", PLUGIN_DIR / ".tracker"))
PENDING_LOG   = TRACKER_DIR / "pending.jsonl"

VALID_STAGES  = {"detected", "extracted", "scheduled", "complete"}

TRACKER_DIR.mkdir(parents=True, exist_ok=True)


def read_pending() -> list[dict]:
    if not PENDING_LOG.exists():
        return []
    entries = []
    for line in PENDING_LOG.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def write_pending(entries: list[dict]) -> None:
    tmp = PENDING_LOG.with_suffix(".jsonl.tmp")
    tmp.write_text("\n".join(json.dumps(e) for e in entries) + ("\n" if entries else ""))
    tmp.replace(PENDING_LOG)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id",    required=True)
    parser.add_argument("--sha256",    required=True)
    parser.add_argument("--doc-ref",   required=True)
    parser.add_argument("--source-id", required=True)
    parser.add_argument("--stage",     required=True, choices=VALID_STAGES)
    parser.add_argument("--error",     default=None)
    args = parser.parse_args()

    entries = read_pending()
    # Remove any existing entry for this run_id
    entries = [e for e in entries if e.get("run_id") != args.run_id]

    if args.stage != "complete":
        entries.append({
            "run_id":    args.run_id,
            "sha256":    args.sha256,
            "doc_ref":   args.doc_ref,
            "source_id": args.source_id,
            "stage":     args.stage,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error":     args.error,
        })

    write_pending(entries)
    print(json.dumps({"status": "ok", "run_id": args.run_id, "stage": args.stage}))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(json.dumps({"status": "error", "error": str(e)}))
        sys.exit(1)
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_checkpoint.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add scripts/checkpoint.py tests/test_checkpoint.py
git commit -m "feat: add checkpoint.py for per-doc pipeline state tracking

Writes/updates pending.jsonl with stage (detected|extracted|scheduled|
complete). Items at 'complete' are removed. Enables retry.py to surface
documents that failed mid-pipeline on next session start.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 3: Fix `scripts/gmail_scan.py` — query hardening + timestamp split

**Why:** Two bugs — (1) the Gmail query has unparenthesized `is:unread OR has:attachment` that ORs with the whole query; (2) `last_run` timestamp is updated at script start before processing, causing mid-run email loss.

**Files:**
- Modify: `scripts/gmail_scan.py`
- Modify: `.tracker/state.json`
- Create: `tests/test_gmail_scan.py`

---

**Step 1: Write failing tests**

Create `tests/test_gmail_scan.py`:

```python
"""Tests for gmail_scan.py query building and state management."""
import importlib.util
import json
import sys
from pathlib import Path

# Load gmail_scan as a module without executing main()
spec = importlib.util.spec_from_file_location(
    "gmail_scan",
    Path(__file__).parent.parent / "scripts" / "gmail_scan.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def test_query_wraps_unread_or_attachment():
    """is:unread OR has:attachment must be wrapped in parentheses."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    # The OR group must be parenthesized so it ANDs with the rest
    assert "(is:unread OR has:attachment)" in query


def test_query_excludes_forums_and_newsletters():
    """Query must include forums and newsletter exclusions."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    assert "-category:forums" in query
    assert "-label:^smartlabel_newsletters" in query


def test_query_excludes_promotional_subjects():
    """Query must have a subject-based exclusion for marketing terms."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    assert "-subject:" in query
    assert "% off" in query or "sale ends" in query


def test_query_includes_subscription_renewal_terms():
    """Query must include subscription renewal as a positive signal."""
    query = mod.build_gmail_query("2026/01/01", "2026/03/05")
    assert "subscription renewal" in query or "auto-renew" in query


def test_load_state_returns_split_timestamp_keys():
    """load_state must return last_scan_started and last_scan_completed."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        # No state file yet — check defaults
        state = mod.load_state(Path(d) / "state.json")
    assert "last_scan_started" in state
    assert "last_scan_completed" in state
    assert "last_run" not in state


def test_save_state_writes_scan_started_not_completed(tmp_path):
    """save_state_started sets last_scan_started but NOT last_scan_completed."""
    state_file = tmp_path / "state.json"
    state = mod.load_state(state_file)
    mod.save_state_started(state, state_file, "2026-03-05T10:00:00Z")
    saved = json.loads(state_file.read_text())
    assert saved["last_scan_started"] == "2026-03-05T10:00:00Z"
    assert saved.get("last_scan_completed") is None
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_gmail_scan.py -v 2>&1 | head -30
```

Expected: Multiple FAIL — functions have wrong signatures and query has bugs.

---

**Step 3: Update `gmail_scan.py`**

Replace the file content with the following (preserving existing structure, only changing the marked sections):

```python
#!/usr/bin/env python3
"""
gmail_scan.py — polls Gmail for unprocessed legal/financial documents.
"""
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PLUGIN_DIR  = Path(__file__).parent.parent
TRACKER_DIR = PLUGIN_DIR / ".tracker"
STATE_FILE  = TRACKER_DIR / "state.json"
RUNS_LOG    = TRACKER_DIR / "runs.jsonl"
SKIP_LOG    = TRACKER_DIR / "skipped.jsonl"
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"

TRACKER_DIR.mkdir(parents=True, exist_ok=True)

# ── Gmail query terms ─────────────────────────────────────────────────────────
LEGAL_POSITIVE_TERMS = (
    "agreement OR contract OR invoice OR \"purchase order\" OR \"PO#\" "
    "OR NDA OR \"statement of work\" OR SOW OR MSA OR amendment OR addendum "
    "OR lease OR retainer OR quotation OR \"legal notice\" OR \"amount due\" "
    "OR \"payment due\" OR \"net 30\" OR \"net 60\" "
    "OR \"subscription renewal\" OR \"auto-renew\" OR \"renews on\""
)

JUNK_SUBJECT_TERMS = (
    "\"% off\" OR \"sale ends\" OR \"limited time\" OR \"promo code\" "
    "OR \"unsubscribe\" OR \"flash sale\" OR \"black friday\" OR \"cyber monday\""
)


def load_state(state_file: Path = STATE_FILE) -> dict:
    if state_file.exists():
        data = json.loads(state_file.read_text())
        # Migrate old 'last_run' key to new split keys
        if "last_run" in data and "last_scan_started" not in data:
            data["last_scan_started"]   = data.pop("last_run")
            data["last_scan_completed"] = None
        return data
    return {
        "last_scan_started":   None,
        "last_scan_completed": None,
        "last_run_email_count": 0,
        "total_runs": 0,
    }


def save_state_started(state: dict, state_file: Path = STATE_FILE,
                       timestamp: str = None) -> None:
    """Write state with last_scan_started set. Does NOT set last_scan_completed."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    state["last_scan_started"] = ts
    state["total_runs"] = state.get("total_runs", 0) + 1
    state_file.write_text(json.dumps(state, indent=2))


def get_date_range(state: dict) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    base_ts = state.get("last_scan_started")
    if base_ts:
        last_dt  = datetime.fromisoformat(base_ts)
        after_dt = last_dt - timedelta(days=1)  # 1-day overlap buffer
    else:
        after_dt = now - timedelta(days=30)
    return after_dt.strftime("%Y/%m/%d"), now.strftime("%Y/%m/%d")


def build_gmail_query(after_date: str, before_date: str) -> str:
    return (
        f"({LEGAL_POSITIVE_TERMS}) "
        f"after:{after_date} before:{before_date} "
        f"-category:promotions -category:social -category:updates "
        f"-category:forums "
        f"-label:^smartlabel_newsletters "
        f"-subject:({JUNK_SUBJECT_TERMS}) "
        f"(is:unread OR has:attachment)"
    )


def append_jsonl(filepath: Path, record: dict) -> None:
    with open(filepath, "a") as f:
        f.write(json.dumps(record) + "\n")


def log_error(context: str, error: str) -> None:
    append_jsonl(ERROR_LOG, {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "context": context,
        "error": error,
    })


def main():
    state      = load_state()
    after_date, before_date = get_date_range(state)
    query      = build_gmail_query(after_date, before_date)
    now_iso    = datetime.now(timezone.utc).isoformat()

    list_cmd = (
        f"gws gmail users messages list "
        f"--params '{{\"userId\":\"me\",\"maxResults\":50,"
        f"\"q\":\"{query}\"}}' --page-all"
    )
    get_cmd = (
        "gws gmail users messages get "
        "--params '{\"userId\":\"me\",\"id\":\"<messageId>\",\"format\":\"full\"}'"
    )
    attachment_cmd = (
        "gws gmail users messages attachments get "
        "--params '{\"userId\":\"me\",\"messageId\":\"<msgId>\",\"id\":\"<attachId>\"}'"
    )

    last_completed = state.get("last_scan_completed", "Never")

    print(f"""
=== DOC RADAR: Daily Gmail Scan ===
Timestamp       : {now_iso}
Date range      : {after_date} -> {before_date}
Last scan start : {state.get('last_scan_started', 'Never (first run)')}
Last scan done  : {last_completed}

ACTION REQUIRED — run these gws commands via Bash:

Step 1 — List candidate messages:
  {list_cmd}

Step 2 — For each messageId returned, fetch full content:
  {get_cmd}

Step 3 — Download any attachments (PDF/DOCX):
  {attachment_cmd} > /tmp/attachment_<msgId>.<ext>

For each email/attachment retrieved:
1. Apply junk filter (see legal-doc-detector skill)
2. Run hash_check.py --check-only to detect duplicates
3. Run doc-extractor skill on each valid new document
4. Write checkpoint: detected -> extracted -> scheduled
5. Run deadline-scheduler skill to create calendar events
6. Run hash_check.py (without --check-only) to record hash permanently
7. Write checkpoint: complete
8. Log all results to .tracker/runs.jsonl

After ALL emails processed, update .tracker/state.json:
  Set last_scan_completed to: {now_iso}

NOTE: If gws is not installed, run:
  npm install -g @googleworkspace/cli && gws auth setup
""")

    # Record scan start (NOT completion — Claude updates last_scan_completed)
    save_state_started(state, timestamp=now_iso)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        log_error("gmail_scan.py:main", str(e))
        sys.exit(0)  # Never block Claude's session start
```

**Step 4: Update `.tracker/state.json`**

```json
{
  "last_scan_started": null,
  "last_scan_completed": null,
  "last_run_email_count": 0,
  "total_runs": 0,
  "plugin_version": "1.1.0",
  "created_at": "2026-03-05T00:00:00Z"
}
```

**Step 5: Run tests to verify they pass**

```bash
python -m pytest tests/test_gmail_scan.py -v
```

Expected: 5 passed.

**Step 6: Commit**

```bash
git add scripts/gmail_scan.py .tracker/state.json tests/test_gmail_scan.py
git commit -m "feat: harden gmail query and split scan timestamps

- Fix operator precedence: (is:unread OR has:attachment) now ANDs correctly
- Add -category:forums, -label:^smartlabel_newsletters, -subject: exclusions
- Add subscription renewal terms to positive query
- Split last_run into last_scan_started + last_scan_completed
- Claude updates last_scan_completed only after full successful run
- Migrate old last_run key automatically on load

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 4: Add `scripts/retry.py`

**Why:** On each session start, surfaces any documents stuck mid-pipeline from previous sessions so Claude can retry them.

**Files:**
- Create: `scripts/retry.py`
- Create: `tests/test_retry.py`

---

**Step 1: Write failing tests**

Create `tests/test_retry.py`:

```python
"""Tests for retry.py — surfaces pending items from previous sessions."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).parent.parent / "scripts" / "retry.py"


def run_retry(tmp_path: Path) -> str:
    env = {"RETRY_TRACKER_DIR": str(tmp_path), "PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, env=env
    )
    return result.stdout


def write_pending(tmp_path: Path, entries: list[dict]) -> None:
    f = tmp_path / "pending.jsonl"
    f.write_text("\n".join(json.dumps(e) for e in entries) + "\n")


def test_no_output_when_no_pending(tmp_path):
    """No pending.jsonl means no output (silent success)."""
    output = run_retry(tmp_path)
    assert output.strip() == ""


def test_empty_pending_file_produces_no_output(tmp_path):
    """Empty pending.jsonl produces no output."""
    (tmp_path / "pending.jsonl").write_text("")
    output = run_retry(tmp_path)
    assert output.strip() == ""


def test_outputs_retry_brief_when_pending_items_exist(tmp_path):
    """Pending items produce a retry brief on stdout."""
    write_pending(tmp_path, [
        {"run_id": "r1", "sha256": "abc", "doc_ref": "INV-001",
         "source_id": "gmail:msg1", "stage": "extracted",
         "timestamp": "2026-03-04T10:00:00Z", "error": None}
    ])
    output = run_retry(tmp_path)
    assert "DOC RADAR: Pending Retry" in output
    assert "INV-001" in output
    assert "extracted" in output


def test_complete_items_not_surfaced(tmp_path):
    """Items at stage=complete are not shown in retry brief."""
    write_pending(tmp_path, [
        {"run_id": "r1", "sha256": "abc", "doc_ref": "INV-001",
         "source_id": "s1", "stage": "complete",
         "timestamp": "2026-03-04T10:00:00Z", "error": None}
    ])
    output = run_retry(tmp_path)
    assert output.strip() == ""
```

**Step 2: Run tests to verify they fail**

```bash
python -m pytest tests/test_retry.py -v 2>&1 | head -20
```

Expected: FAIL — script doesn't exist.

---

**Step 3: Create `scripts/retry.py`**

```python
#!/usr/bin/env python3
"""
retry.py
--------
Reads .tracker/pending.jsonl and .tracker/errors.jsonl.
Outputs a retry brief to stdout if unresolved items exist,
injected into Claude's context via the SessionStart hook.

Produces no output if nothing needs retrying (silent = no unnecessary context).
"""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PLUGIN_DIR   = Path(__file__).parent.parent
TRACKER_DIR  = Path(os.environ.get("RETRY_TRACKER_DIR", PLUGIN_DIR / ".tracker"))
PENDING_LOG  = TRACKER_DIR / "pending.jsonl"
ERROR_LOG    = TRACKER_DIR / "errors.jsonl"


def read_jsonl(filepath: Path) -> list[dict]:
    if not filepath.exists():
        return []
    entries = []
    for line in filepath.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return entries


def main():
    pending = [e for e in read_jsonl(PENDING_LOG)
               if e.get("stage") != "complete"]

    if not pending:
        sys.exit(0)  # Nothing to retry — no output

    now_iso = datetime.now(timezone.utc).isoformat()

    lines = [
        "",
        "=== DOC RADAR: Pending Retry Items ===",
        f"Timestamp     : {now_iso}",
        f"Items pending : {len(pending)}",
        "",
        "The following documents were partially processed in a previous session.",
        "Process each through the pipeline starting from their current stage:",
        "  extracted -> deadline-scheduler -> checkpoint complete -> record hash",
        "  detected  -> doc-extractor -> deadline-scheduler -> checkpoint complete -> record hash",
        "",
    ]

    for i, item in enumerate(pending, 1):
        lines.append(
            f"{i}. [{item.get('stage','?').upper()}] {item.get('doc_ref','unknown')} "
            f"| source: {item.get('source_id','?')} "
            f"| since: {item.get('timestamp','?')[:10]}"
        )
        if item.get("error"):
            lines.append(f"   Error: {item['error']}")

    lines.append("")
    print("\n".join(lines))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        sys.exit(0)  # Never block session start
```

**Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_retry.py -v
```

Expected: 4 passed.

**Step 5: Commit**

```bash
git add scripts/retry.py tests/test_retry.py
git commit -m "feat: add retry.py to surface pending docs on session start

Reads pending.jsonl and outputs a retry brief if any documents are
stuck mid-pipeline from a previous session. Silent if nothing pending.
Injected via SessionStart hook alongside the gmail scan brief.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 5: Update `hooks/hooks.json`

**Why:** Add retry.py as a second SessionStart hook; use `${CLAUDE_PLUGIN_ROOT}` for reliable path resolution.

**Files:**
- Modify: `hooks/hooks.json`

---

**Step 1: Replace `hooks/hooks.json`**

```json
{
  "description": "doc-radar event hooks",
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/gmail_scan.py 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
          }
        ]
      },
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/retry.py 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/watch_folder.py --file \"$(echo $CLAUDE_HOOK_INPUT | python3 -c \"import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',''))\" 2>/dev/null)\" 2>> ${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
          }
        ]
      }
    ]
  }
}
```

**Step 2: Commit**

```bash
git add hooks/hooks.json
git commit -m "feat: add retry.py to SessionStart hooks, use CLAUDE_PLUGIN_ROOT

Retry brief is injected into Claude context on every session start if
pending.jsonl has unresolved items. CLAUDE_PLUGIN_ROOT replaces hardcoded
~/.claude/plugins/doc-radar path for reliable cross-environment resolution.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 6: Update `skills/legal-doc-detector/SKILL.md`

**Why:** Add subscription renewals as a detectable doc type; strengthen junk filter with expanded blocklist and explicit three-signal rules.

**Files:**
- Modify: `skills/legal-doc-detector/SKILL.md`

---

**Step 1: Replace the SKILL.md content**

Replace the full file with the following:

```markdown
---
name: legal-doc-detector
description: >
  Detects legal and financially binding documents in any context — Gmail scan
  output, file paths, attachment names, or pasted content. Triggers
  automatically when Claude encounters signals indicating a contract, invoice,
  PO, NDA, SOW, MSA, lease, retainer, amendment, quotation, or subscription
  renewal. Use PROACTIVELY whenever SessionStart hook injects Gmail scan
  results, or when a new file appears in the watched inbox folder.
  Immediately chains to doc-extractor.
---

# Legal Document Detector

## Purpose
Gate-keep what gets processed. Identify whether any document, email, or file
in the current context is a legal or financially binding document. If yes,
invoke the `doc-extractor` skill. If no, do nothing and do not log.

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

When a document passes the filter, immediately call the `doc-extractor` skill.
Pass the full available content: email subject, sender, body snippet, attachment
name, and any text already extracted from the attachment.

Process each detected document sequentially. At the end of a scan, report:
> "Scan complete. Found N documents. N new (processed). N duplicates (skipped).
> N junk (filtered). Created N calendar events."
```

**Step 2: Commit**

```bash
git add skills/legal-doc-detector/SKILL.md
git commit -m "feat: add subscription renewals to legal-doc-detector, harden junk filter

- Add subscription_renewal doc type with key signals
- Expand junk sender domain blocklist (marketo, intercom, drip added)
- Add body and subject-level junk pattern matching
- Strengthen three-signal test: any recurring amount qualifies
- Explicit subscription renewal special case rule
- Clarify consumer vs business subscription distinction

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 7: Update `skills/doc-extractor/SKILL.md`

**Why:** Add `subscription_renewal` as an extractable doc type with dedicated fields; add checkpoint writing instructions; update hash-check call to use `--check-only` first.

**Files:**
- Modify: `skills/doc-extractor/SKILL.md`

---

**Step 1: Update the SKILL.md**

Make these targeted additions to the existing file:

**In the frontmatter description**, add "subscription renewals":
```yaml
description: >
  Extracts structured date, party, and financial fields from legal and
  financially binding documents — contracts, invoices, purchase orders, NDAs,
  SOWs, MSAs, leases, amendments, quotations, subscription renewals. Computes
  a SHA-256 hash of the document content to detect duplicates before any
  processing occurs. Writes results to the JSONL run log. Use PROACTIVELY
  immediately after legal-doc-detector confirms a document should be processed.
```

**In Step 1**, change the hash check call to use `--check-only`:
```bash
python3 ~/.claude/plugins/doc-radar/scripts/hash_check.py --check-only --content "<raw_text>"
# or for a file:
python3 ~/.claude/plugins/doc-radar/scripts/hash_check.py --check-only --file "/path/to/file"
```
Add note: "Do NOT use the full (recording) call yet — hash is recorded permanently only after successful calendar creation in deadline-scheduler."

**In Step 2**, add `subscription_renewal` to the `doc_type` enum and add new fields:
```json
{
  "doc_type": "contract | msa | nda | sow | invoice | purchase_order | lease | retainer | amendment | legal_notice | quotation | subscription_renewal | other",
  ...
  "renewal_date":    "YYYY-MM-DD or null",
  "cancel_by_date":  "YYYY-MM-DD or null",
  "billing_cycle":   "monthly | annual | quarterly | null",
  "billing_method":  "credit card | ACH | PayPal | check | wire | null",
  "billing_last4":   "last 4 digits of card on file, or null",
  "bank_name":       "bank name if present in document, or null",
  "account_number":  "account number if present in document, or null",
  "routing_number":  "routing number if present in document, or null",
  "contact_email":   "issuer contact email if present, or null",
  "contact_phone":   "issuer contact phone if present, or null"
}
```

**Add a new Field Extraction section for Subscription Renewal:**
```
**Subscription Renewal**: Focus on `renewal_date` and `cancel_by_date`. The
cancel-by date is the last day the user can cancel to avoid being charged —
extract this if present ("cancel by", "to avoid charges", "must cancel before").
`billing_cycle` comes from frequency language ("monthly", "annually", "per year",
"per month"). `billing_last4` comes from masked card displays ("xxxx-1234").
```

**After Step 3 (Write to Run Log)**, add a new Step 3.5:
```
## Step 3.5 — Write Detected Checkpoint

After writing to runs.jsonl, write a pipeline checkpoint:

```bash
python3 ~/.claude/plugins/doc-radar/scripts/checkpoint.py \
  --run-id "<run_id>" \
  --sha256 "<sha256>" \
  --doc-ref "<doc_ref or 'unknown'>" \
  --source-id "<source_id>" \
  --stage extracted
```
```

**Step 2: Commit**

```bash
git add skills/doc-extractor/SKILL.md
git commit -m "feat: update doc-extractor for subscription renewals and checkpointing

- Add subscription_renewal doc type with billing_cycle, cancel_by_date,
  billing_method, billing_last4, bank_name, account/routing numbers,
  contact_email, contact_phone extraction fields
- Change hash check to --check-only (records only after scheduling)
- Add Step 3.5 checkpoint write after extraction

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 8: Update `skills/deadline-scheduler/SKILL.md`

**Why:** Remove emoji from event titles, add richer self-contained event description template with financial/action/party details, add subscription renewal reminder logic.

**Files:**
- Modify: `skills/deadline-scheduler/SKILL.md`

---

**Step 1: Replace the full SKILL.md**

```markdown
---
name: deadline-scheduler
description: >
  Creates Google Calendar events from structured document data produced by
  doc-extractor. Applies tiered reminder logic per document type (contracts,
  invoices, POs, NDAs, SOWs, leases, amendments, subscription renewals).
  Checks for duplicate calendar events before creating. Updates the JSONL
  run log with created event IDs. Records SHA-256 hash permanently after
  successful creation. Use PROACTIVELY immediately after doc-extractor
  returns extracted JSON.
---

# Deadline Scheduler

## Purpose
Take the structured JSON from `doc-extractor`, create the correct Google
Calendar events with the right reminder windows, check for duplicates,
write the event description as a self-contained briefing, record event IDs
back to the run log, write the pipeline checkpoint to complete, and
permanently record the SHA-256 hash.

All calendar operations use `gws` (Google Workspace CLI) via Bash.

---

## Calendar Access via gws

```bash
# Check schema before building JSON payloads
gws schema calendar.events.insert
gws schema calendar.events.list

# Always dry-run first when creating or modifying events
gws calendar events insert \
  --params '{"calendarId":"primary"}' \
  --json '{ ... }' \
  --dry-run

# Then execute for real (remove --dry-run)
gws calendar events insert \
  --params '{"calendarId":"primary"}' \
  --json '{ ... }'
```

---

## Step 1 — Duplicate Calendar Event Check

Before creating any event, search the calendar for an existing event:

```bash
gws calendar events list \
  --params '{
    "calendarId": "primary",
    "q": "<doc_ref or party names>",
    "timeMin": "<today in RFC3339>",
    "timeMax": "<expiry_date + 180 days in RFC3339>",
    "fields": "items(id,summary,start)"
  }'
```

If a matching event already exists: log `calendar_event_ids` from the existing
event, update the run log with `status: "calendar_duplicate_skipped"`, and stop.

---

## Step 2 — Event Title Format

No emoji. Professional, scannable titles.

| Doc Type | Title Format |
|----------|-------------|
| Contract / MSA / NDA / Lease / Retainer | `EXPIRES: [doc_type] [doc_ref] — [issuer] / [recipient]` |
| Invoice | `PAYMENT DUE: [doc_ref] — [issuer] — [currency] [amount]` |
| Purchase Order | `PO DELIVERY: [po_number] — [issuer] — [currency] [amount]` |
| SOW Final Delivery | `SOW DELIVERY: [doc_ref] — [recipient]` |
| SOW Milestone | `MILESTONE [N/total]: [doc_ref] — [recipient]` |
| Subscription Renewal | `SUBSCRIPTION RENEWS: [service] — [currency] [amount]/[cycle]` |
| Cancel-by | `CANCEL BY: [service] — Last day before auto-renewal` |
| Renewal Notice Window | `RENEWAL NOTICE DUE: [doc_ref] — [N] days before auto-renewal` |
| Quotation / Proposal | `QUOTE EXPIRES: [doc_ref] — [issuer] — [currency] [amount]` |
| Amendment | `AMENDED EXPIRES: [doc_ref] — [issuer] / [recipient]` |

---

## Step 3 — Event Description Template

Build the description as a self-contained briefing. Omit any section where
all fields are null — do not leave blank headings.

```
DOCUMENT SUMMARY
────────────────
[2-3 sentence plain-language description: what this document is, who the
parties are, and why it matters. Write as if the reader has never seen it.]

ACTION REQUIRED
───────────────
[Exactly what needs to happen and by when — be specific and imperative]
Examples:
  "Decide whether to renew or send non-renewal notice by 2026-02-20"
  "Pay invoice via wire transfer to account details below by 2026-03-15"
  "Cancel subscription in Adobe account portal by 2026-03-18 to avoid charge"

PARTIES
───────
Issuer    : [name] | [email] | [phone]
Recipient : [name] | [email]

FINANCIAL DETAILS
─────────────────
Amount    : [currency] [amount]
Payment   : [payment_terms]
Pay To    : [payee name / account name]
Bank      : [bank name]
Account   : [account number]
Routing   : [routing number]
Card      : xxxx-xxxx-xxxx-[last4]
Method    : [wire | ACH | credit card | check | PayPal]

KEY DATES
─────────
Effective : [date]
Expires   : [date]
Renewal   : [date]
Notice by : [date]
Cancel by : [date]
Milestones: [date — description, ...]

DOCUMENT DETAILS
────────────────
Type      : [doc_type]
Reference : [doc_ref]
Governing : [jurisdiction]
Source    : [gmail message link or file path]
SHA-256   : [first 12 chars of hash]
Processed : [ISO timestamp]
```

---

## Step 4 — Reminder Logic by Document Type

### Contract / MSA / NDA / Lease / Retainer

**Event 1 — Expiry Day** (all-day on `expiry_date`):
```json
{
  "summary": "EXPIRES: contract PSA-001 — Acme Corp / NorthGrid",
  "start": { "date": "<expiry_date>" },
  "end":   { "date": "<expiry_date + 1 day>" },
  "colorId": "11",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 43200 },
      { "method": "popup",  "minutes": 20160 },
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

**Event 2 — Renewal Notice Window** (if `auto_renewal: true`):
```json
{
  "summary": "RENEWAL NOTICE DUE: [doc_ref] — [N] days before auto-renewal",
  "start": { "date": "<renewal_date>" },
  "end":   { "date": "<renewal_date + 1 day>" },
  "colorId": "6",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 4320  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

### Invoice

**Event — Payment Due** (all-day on `due_date`):
```json
{
  "summary": "PAYMENT DUE: INV-001 — Acme Corp — USD 12500",
  "start": { "date": "<due_date>" },
  "end":   { "date": "<due_date + 1 day>" },
  "colorId": "5",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 4320  },
      { "method": "email",  "minutes": 1440  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

### Purchase Order

**Event — Delivery Deadline** (all-day on `expiry_date` or `due_date`):
```json
{
  "summary": "PO DELIVERY: PO-2026-001 — Acme Corp — USD 45000",
  "colorId": "9",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 20160 },
    { "method": "popup", "minutes": 10080 },
    { "method": "popup", "minutes": 1440  }
  ]}
}
```

### SOW

**Event — Final Delivery** (all-day on `expiry_date`):
```json
{
  "summary": "SOW DELIVERY: SOW-2026-001 — NorthGrid",
  "colorId": "10",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 43200 },
    { "method": "popup", "minutes": 20160 },
    { "method": "email", "minutes": 10080 },
    { "method": "popup", "minutes": 1440  }
  ]}
}
```

**Events — Milestones** (one per date in `milestone_dates[]`):
```json
{
  "summary": "MILESTONE [N/total]: SOW-2026-001 — NorthGrid",
  "colorId": "2",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 10080 },
    { "method": "popup", "minutes": 1440  }
  ]}
}
```

### Subscription Renewal

**Event 1 — Renewal Date** (all-day on `renewal_date`):
```json
{
  "summary": "SUBSCRIPTION RENEWS: Adobe Creative Cloud — USD 599.88/annual",
  "start": { "date": "<renewal_date>" },
  "end":   { "date": "<renewal_date + 1 day>" },
  "colorId": "7",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 20160 },
      { "method": "popup",  "minutes": 10080 },
      { "method": "email",  "minutes": 4320  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

**Event 2 — Cancel-by Date** (if `cancel_by_date` is present):
```json
{
  "summary": "CANCEL BY: Adobe Creative Cloud — Last day before auto-renewal",
  "start": { "date": "<cancel_by_date>" },
  "end":   { "date": "<cancel_by_date + 1 day>" },
  "colorId": "11",
  "reminders": {
    "useDefault": false,
    "overrides": [
      { "method": "email",  "minutes": 10080 },
      { "method": "popup",  "minutes": 4320  },
      { "method": "popup",  "minutes": 1440  }
    ]
  }
}
```

### Amendment
Same logic as the document type being amended. Prefix title with "AMENDED:".

### Quotation / Proposal

**Event — Valid Until** (all-day on `expiry_date`):
```json
{
  "summary": "QUOTE EXPIRES: QUO-2026-001 — Acme Corp — USD 8500",
  "colorId": "1",
  "reminders": { "useDefault": false, "overrides": [
    { "method": "email", "minutes": 4320 },
    { "method": "popup", "minutes": 1440 }
  ]}
}
```

---

## Step 5 — After Successful Event Creation

Run ALL of these steps after every event is created successfully:

**5a — Update run log with event IDs:**
```bash
python3 ~/.claude/plugins/doc-radar/scripts/update_log.py \
  --sha256 "<hash>" \
  --event-ids "<id1>,<id2>,..."
```

**5b — Record SHA-256 hash permanently** (this is the first time the hash is recorded):
```bash
python3 ~/.claude/plugins/doc-radar/scripts/hash_check.py \
  --content "<raw_text>" \
  --source-id "<source_id>"
```

**5c — Write complete checkpoint:**
```bash
python3 ~/.claude/plugins/doc-radar/scripts/checkpoint.py \
  --run-id "<run_id>" \
  --sha256 "<hash>" \
  --doc-ref "<doc_ref>" \
  --source-id "<source_id>" \
  --stage complete
```

**5d — Update state.json last_scan_completed** (after ALL documents in the session are done):
```bash
python3 -c "
import json
from pathlib import Path
from datetime import datetime, timezone
f = Path('~/.claude/plugins/doc-radar/.tracker/state.json').expanduser()
s = json.loads(f.read_text())
s['last_scan_completed'] = datetime.now(timezone.utc).isoformat()
f.write_text(json.dumps(s, indent=2))
print('state.json updated')
"
```

---

## Step 6 — Error Handling

If `gws calendar events insert` fails:
1. Log to `.tracker/errors.jsonl`
2. Update run log entry: `status: "calendar_error"`
3. Update checkpoint to `stage: scheduled` with the error message (NOT complete)
4. Do NOT record the hash — it should remain unrecorded so retry can process it
5. Continue processing other documents

```bash
python3 ~/.claude/plugins/doc-radar/scripts/checkpoint.py \
  --run-id "<run_id>" --sha256 "<hash>" --doc-ref "<doc_ref>" \
  --source-id "<source_id>" --stage scheduled \
  --error "gws calendar insert failed: <error message>"
```
```

**Step 2: Commit**

```bash
git add skills/deadline-scheduler/SKILL.md
git commit -m "feat: redesign deadline-scheduler — no emoji, richer events, subscription renewals

- Remove all emoji from event titles, use clean professional format
- Add self-contained event description template with DOCUMENT SUMMARY,
  ACTION REQUIRED, PARTIES, FINANCIAL DETAILS, KEY DATES, DOCUMENT DETAILS
- Add subscription_renewal reminder logic (renewal + cancel-by events)
- Move hash recording to after successful calendar creation (Step 5b)
- Add checkpoint complete write (Step 5c) and last_scan_completed update
- Add checkpoint error write on calendar failure (Step 6)

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 9: Update `agents/doc-radar-agent.md`

**Why:** Orchestration agent needs updated workflow reflecting checkpointing, the new hash-timing fix, retry item handling, and `last_scan_completed` update.

**Files:**
- Modify: `agents/doc-radar-agent.md`

---

**Step 1: Replace the workflow section**

Update the Workflow section in `agents/doc-radar-agent.md`:

```markdown
## Workflow

1. **Check for retry items** — if the SessionStart hook output contains a
   "DOC RADAR: Pending Retry Items" section, process those items first.
   For each: resume from their current stage (extracted -> schedule;
   detected -> extract then schedule).

2. **Receive scan context** — from SessionStart hook output (Gmail scan
   results) or a direct user request with document content/paths.

3. **Run legal-doc-detector** on all items. Separate into:
   - `to_process[]` — items that pass the legal doc test
   - `skipped_junk[]` — items filtered as promotional/noise

4. **For each item in `to_process[]`**, run in sequence:
   a. `doc-extractor` — uses `hash_check.py --check-only` to detect duplicates,
      extracts fields, writes run log entry, writes `detected` checkpoint
   b. If duplicate: note it, log to skipped.jsonl, continue to next item
   c. If new: update checkpoint to `extracted`
   d. `deadline-scheduler` — create calendar events via gws, then:
      - Record hash permanently via `hash_check.py` (without --check-only)
      - Write `complete` checkpoint
      - Update run log with event IDs
   e. If calendar creation fails: write `scheduled` checkpoint with error,
      do NOT record hash — item will surface for retry next session

5. **After ALL documents processed**, update `state.json`:
   Set `last_scan_completed` to current ISO timestamp.

6. **Report summary:**
   ```
   Doc Radar scan complete — [ISO date]
   ─────────────────────────────────────
   Emails/files scanned   : N
   Legal docs detected    : N
   New docs processed     : N
   Duplicates skipped     : N
   Junk filtered          : N
   Calendar events created: N
   Retry items resolved   : N
   Pending retry remaining: N
   ```

7. **List each processed document:**
   ```
   -> [doc_type] | [doc_ref] | [issuer] / [recipient] | Expires/Due/Renews: [date]
   ```
```

Update the Error Handling section:

```markdown
## Error Handling

- If hash_check.py --check-only fails: log to errors.jsonl, skip that doc
- If doc-extractor fails: write `detected` checkpoint with error, log, continue
- If `gws calendar events insert` fails: write `scheduled` checkpoint with error,
  log to errors.jsonl, mark run log `status: "calendar_error"`, do NOT record
  hash, continue processing others
- If checkpoint.py fails: log to errors.jsonl, continue (non-fatal)
- Never abort the full run because one document failed
- After the run, any items with stage != complete will be surfaced by retry.py
  on the next session start
```

**Step 2: Commit**

```bash
git add agents/doc-radar-agent.md
git commit -m "feat: update doc-radar-agent orchestration for v1.1.0

- Add retry item handling at start of workflow
- Update pipeline to use hash_check --check-only then record after success
- Add checkpoint writes at each stage (detected, extracted, complete)
- Add last_scan_completed update after all docs processed
- Update summary report with retry counts
- Clarify error handling: failed calendar = scheduled checkpoint, no hash record

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Task 10: Version bump and run full test suite

**Files:**
- Modify: `.claude-plugin/plugin.json`

---

**Step 1: Update plugin.json version**

Change `"version": "1.0.0"` to `"version": "1.1.0"` in `.claude-plugin/plugin.json`.

**Step 2: Run the full test suite**

```bash
python -m pytest tests/ -v
```

Expected output:
```
tests/test_checkpoint.py::test_write_detected_checkpoint PASSED
tests/test_checkpoint.py::test_update_stage_in_place PASSED
tests/test_checkpoint.py::test_complete_stage_removes_entry PASSED
tests/test_checkpoint.py::test_multiple_docs_tracked_independently PASSED
tests/test_gmail_scan.py::test_query_wraps_unread_or_attachment PASSED
tests/test_gmail_scan.py::test_query_excludes_forums_and_newsletters PASSED
tests/test_gmail_scan.py::test_query_excludes_promotional_subjects PASSED
tests/test_gmail_scan.py::test_query_includes_subscription_renewal_terms PASSED
tests/test_gmail_scan.py::test_load_state_returns_split_timestamp_keys PASSED
tests/test_gmail_scan.py::test_save_state_writes_scan_started_not_completed PASSED
tests/test_hash_check.py::test_check_only_does_not_record PASSED
tests/test_hash_check.py::test_check_only_detects_existing_duplicate PASSED
tests/test_hash_check.py::test_normal_mode_records_hash PASSED
tests/test_retry.py::test_no_output_when_no_pending PASSED
tests/test_retry.py::test_empty_pending_file_produces_no_output PASSED
tests/test_retry.py::test_outputs_retry_brief_when_pending_items_exist PASSED
tests/test_retry.py::test_complete_items_not_surfaced PASSED

17 passed
```

**Step 3: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "chore: bump version to 1.1.0

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```

---

## Summary

| Task | Files | Tests |
|------|-------|-------|
| 1. hash_check --check-only | `scripts/hash_check.py` | 3 tests |
| 2. checkpoint.py | `scripts/checkpoint.py` | 4 tests |
| 3. gmail_scan query + timestamps | `scripts/gmail_scan.py`, `state.json` | 6 tests |
| 4. retry.py | `scripts/retry.py` | 4 tests |
| 5. hooks.json | `hooks/hooks.json` | — |
| 6. legal-doc-detector skill | `skills/legal-doc-detector/SKILL.md` | — |
| 7. doc-extractor skill | `skills/doc-extractor/SKILL.md` | — |
| 8. deadline-scheduler skill | `skills/deadline-scheduler/SKILL.md` | — |
| 9. doc-radar-agent | `agents/doc-radar-agent.md` | — |
| 10. version bump + full suite | `plugin.json` | 17 total |
