# Global Tracker Directory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace all hardcoded `PLUGIN_DIR / ".tracker"` defaults with `~/.doc-radar/` (global user-owned directory). Consolidate the five per-script env var overrides (`HASH_CHECK_TRACKER_DIR`, `CHECKPOINT_TRACKER_DIR`, `RETRY_TRACKER_DIR`, plus three scripts with no env var at all) into a single `DOC_RADAR_TRACKER_DIR` env var. Update hooks, tests, and all skill SKILL.md files to reference the global path.

**Architecture:**
- Global default: `Path.home() / ".doc-radar"` — auto-created on first use by every script
- Override: `DOC_RADAR_TRACKER_DIR` env var (used by tests to redirect to `tmp_path`)
- Local `.tracker/` in each plugin remains for development reference but is no longer the runtime default
- Both plugins share the same global path so data is never split

**Tech Stack:** Python (scripts), JSON (hooks), Markdown (skills).

**Standard TRACKER_DIR pattern for every script:**
```python
import os
from pathlib import Path
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
```

---

### Task 1: Update doc-radar scripts

**Files:**
- Modify: `doc-radar/scripts/gmail_scan.py`
- Modify: `doc-radar/scripts/hash_check.py`
- Modify: `doc-radar/scripts/checkpoint.py`
- Modify: `doc-radar/scripts/retry.py`
- Modify: `doc-radar/scripts/update_log.py`
- Modify: `doc-radar/scripts/watch_folder.py`
- Modify: `doc-radar/scripts/dashboard.py`

**For each script, apply the standard TRACKER_DIR pattern.**

**gmail_scan.py**

Current:
```python
TRACKER_DIR = PLUGIN_DIR / ".tracker"
STATE_FILE  = TRACKER_DIR / "state.json"
RUNS_LOG    = TRACKER_DIR / "runs.jsonl"
SKIP_LOG    = TRACKER_DIR / "skipped.jsonl"
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"
```
Replace with:
```python
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
STATE_FILE  = TRACKER_DIR / "state.json"
RUNS_LOG    = TRACKER_DIR / "runs.jsonl"
SKIP_LOG    = TRACKER_DIR / "skipped.jsonl"
ERROR_LOG   = TRACKER_DIR / "errors.jsonl"
```

**hash_check.py**

Current (two-step conditional pattern):
```python
TRACKER_DIR  = PLUGIN_DIR / ".tracker"
HASHES_LOG   = TRACKER_DIR / "seen_hashes.jsonl"

_env_tracker = os.environ.get("HASH_CHECK_TRACKER_DIR")
if _env_tracker:
    TRACKER_DIR = Path(_env_tracker)
    HASHES_LOG  = TRACKER_DIR / "seen_hashes.jsonl"
```
Replace with the single standard pattern:
```python
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
HASHES_LOG  = TRACKER_DIR / "seen_hashes.jsonl"
```

**checkpoint.py**

Current:
```python
TRACKER_DIR  = Path(os.environ.get("CHECKPOINT_TRACKER_DIR", str(PLUGIN_DIR / ".tracker")))
```
Replace with:
```python
TRACKER_DIR  = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
```

**retry.py**

Current (inside main()):
```python
tracker_dir = Path(os.environ.get("RETRY_TRACKER_DIR", str(PLUGIN_DIR / ".tracker")))
```
Replace with:
```python
tracker_dir = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
```

**update_log.py**

Current:
```python
TRACKER_DIR = PLUGIN_DIR / ".tracker"
```
Replace with:
```python
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
```
Also ensure `import os` is present at the top.

**watch_folder.py**

Current:
```python
TRACKER_DIR = PLUGIN_DIR / ".tracker"
```
Replace with:
```python
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
```
Also ensure `import os` is present at the top.

**dashboard.py**

Current:
```python
TRACKER_DIR = PLUGIN_DIR / ".tracker"
```
Replace with:
```python
TRACKER_DIR = Path(os.environ.get("DOC_RADAR_TRACKER_DIR", str(Path.home() / ".doc-radar")))
```
Also ensure `import os` is present at the top.

**Step 1: Read each script, apply the change, verify TRACKER_DIR line is correct**

**Step 2: Verify no script still references `HASH_CHECK_TRACKER_DIR`, `CHECKPOINT_TRACKER_DIR`, or `RETRY_TRACKER_DIR`**

**Step 3: Commit**
```bash
git add doc-radar/scripts/
git commit -m "feat(doc-radar): use DOC_RADAR_TRACKER_DIR defaulting to ~/.doc-radar"
```

---

### Task 2: Update doc-radar-cowork scripts

**Files:**
- Modify: `doc-radar-cowork/scripts/scan_prompt.py`
- Modify: `doc-radar-cowork/scripts/hash_check.py`
- Modify: `doc-radar-cowork/scripts/checkpoint.py`
- Modify: `doc-radar-cowork/scripts/retry.py`
- Modify: `doc-radar-cowork/scripts/update_log.py`
- Modify: `doc-radar-cowork/scripts/watch_folder.py`
- Modify: `doc-radar-cowork/scripts/dashboard.py`

Apply the exact same changes as Task 1 but in the `doc-radar-cowork/scripts/` directory. Same rules, same pattern, same env var name.

**Step 1: Read each script, apply the change**

**Step 2: Verify no script still references `HASH_CHECK_TRACKER_DIR`, `CHECKPOINT_TRACKER_DIR`, or `RETRY_TRACKER_DIR`**

**Step 3: Commit**
```bash
git add doc-radar-cowork/scripts/
git commit -m "feat(doc-radar-cowork): use DOC_RADAR_TRACKER_DIR defaulting to ~/.doc-radar"
```

---

### Task 3: Update doc-radar tests and hooks.json

**Files:**
- Modify: `doc-radar/tests/test_hash_check.py`
- Modify: `doc-radar/tests/test_checkpoint.py`
- Modify: `doc-radar/tests/test_retry.py`
- Modify: `doc-radar/hooks/hooks.json`

**test_hash_check.py**

Find all occurrences of `"HASH_CHECK_TRACKER_DIR"` and replace with `"DOC_RADAR_TRACKER_DIR"`.

**test_checkpoint.py**

Find all occurrences of `"CHECKPOINT_TRACKER_DIR"` and replace with `"DOC_RADAR_TRACKER_DIR"`.

**test_retry.py**

Find all occurrences of `"RETRY_TRACKER_DIR"` (in subprocess env dicts and monkeypatch.setenv calls) and replace with `"DOC_RADAR_TRACKER_DIR"`.

**hooks/hooks.json**

Current (two places):
```
"${CLAUDE_PLUGIN_ROOT}/.tracker/errors.jsonl"
```
Replace both with:
```
"${HOME}/.doc-radar/errors.jsonl"
```

**Step 1: Apply all four changes**

**Step 2: Run tests to verify they still pass**
```bash
cd /Users/kwesi/Desktop/doc-radar-marketplace && python -m pytest doc-radar/tests/ -q
```
Expected: all tests pass.

**Step 3: Commit**
```bash
git add doc-radar/tests/ doc-radar/hooks/hooks.json
git commit -m "feat(doc-radar): update tests and hooks to use DOC_RADAR_TRACKER_DIR / ~/.doc-radar"
```

---

### Task 4: Update doc-radar-cowork tests and hooks.json

**Files:**
- Modify: `doc-radar-cowork/tests/test_hash_check.py`
- Modify: `doc-radar-cowork/tests/test_checkpoint.py`
- Modify: `doc-radar-cowork/tests/test_retry.py`
- Modify: `doc-radar-cowork/hooks/hooks.json`

Apply the exact same changes as Task 3 but in the `doc-radar-cowork/` directory.

**Step 1: Apply all four changes**

**Step 2: Run tests**
```bash
python -m pytest doc-radar-cowork/tests/ -q
```
Expected: all tests pass.

**Step 3: Commit**
```bash
git add doc-radar-cowork/tests/ doc-radar-cowork/hooks/hooks.json
git commit -m "feat(doc-radar-cowork): update tests and hooks to use DOC_RADAR_TRACKER_DIR / ~/.doc-radar"
```

---

### Task 5: Update all skill SKILL.md files (both plugins)

**Files (12 total):**
- Modify: `doc-radar/skills/legal-doc-detector/SKILL.md`
- Modify: `doc-radar/skills/doc-extractor/SKILL.md`
- Modify: `doc-radar/skills/deadline-scheduler/SKILL.md`
- Modify: `doc-radar/skills/archiver/SKILL.md`
- Modify: `doc-radar/skills/dashboard/SKILL.md`
- Modify: `doc-radar/skills/digest/SKILL.md`
- Modify: `doc-radar-cowork/skills/legal-doc-detector/SKILL.md`
- Modify: `doc-radar-cowork/skills/doc-extractor/SKILL.md`
- Modify: `doc-radar-cowork/skills/deadline-scheduler/SKILL.md`
- Modify: `doc-radar-cowork/skills/archiver/SKILL.md`
- Modify: `doc-radar-cowork/skills/dashboard/SKILL.md`
- Modify: `doc-radar-cowork/skills/digest/SKILL.md`

**Rule:** Replace every occurrence of `.tracker/` with `~/.doc-radar/` throughout all 12 files. This includes:
- Log file references: `.tracker/runs.jsonl` → `~/.doc-radar/runs.jsonl`
- Skipped log: `.tracker/skipped.jsonl` → `~/.doc-radar/skipped.jsonl`
- Errors log: `.tracker/errors.jsonl` → `~/.doc-radar/errors.jsonl`
- Hashes log: `.tracker/seen_hashes.jsonl` → `~/.doc-radar/seen_hashes.jsonl`
- State file: `.tracker/state.json` → `~/.doc-radar/state.json`
- Dashboard output: `.tracker/dashboard.html` → `~/.doc-radar/dashboard.html`
- Pending log: `.tracker/pending.jsonl` → `~/.doc-radar/pending.jsonl`

Also add a note in each skill's preamble or first section (where it first references the tracker) — one line:
```
> All tracker files are stored in `~/.doc-radar/` (created automatically on first use).
> Override with the `DOC_RADAR_TRACKER_DIR` environment variable.
```

Place this note immediately before the first `~/.doc-radar/` path reference in each skill file.

**Step 1: Read each file, apply replacements and add the note**

**Step 2: Verify — grep for any remaining `.tracker/` references across both skill directories**
```bash
grep -r "\.tracker/" doc-radar/skills/ doc-radar-cowork/skills/
```
Expected: no matches.

**Step 3: Commit**
```bash
git add doc-radar/skills/ doc-radar-cowork/skills/
git commit -m "docs: update all skill files to reference ~/.doc-radar global tracker path"
```

---

### Task 6: Final verification, push, PR, merge

**Step 1: Run both test suites in full**
```bash
python -m pytest doc-radar/tests/ doc-radar-cowork/tests/ -q
```
Expected: all tests pass.

**Step 2: Verify no old env var names remain in scripts or tests**
```bash
grep -r "HASH_CHECK_TRACKER_DIR\|CHECKPOINT_TRACKER_DIR\|RETRY_TRACKER_DIR" doc-radar/scripts/ doc-radar/tests/ doc-radar-cowork/scripts/ doc-radar-cowork/tests/
```
Expected: no matches.

**Step 3: Verify no `.tracker/` in skill files**
```bash
grep -r "\.tracker/" doc-radar/skills/ doc-radar-cowork/skills/
```
Expected: no matches.

**Step 4: Push, create PR, merge**
```bash
git push -u origin <current-branch>
gh pr create --title "feat: global ~/.doc-radar tracker dir for both plugins" --base main
gh pr merge <number> --merge --delete-branch
```
