# Git Migration to Marketplace Root Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Move the git repository from `doc-radar/` (the plugin subfolder) up to `doc-radar-marketplace/` (the marketplace root), mirroring the structure of `anthropics/claude-plugins-official`.

**Architecture:** The marketplace root becomes the git root, exactly like `anthropics/claude-plugins-official` where plugins live in subdirectories. The `doc-radar/` plugin stays in place as a subdirectory — only the `.git` moves up one level. Old history is preserved with a single restructure commit. A new GitHub repo (`peekwez/doc-radar-marketplace`) replaces the old `peekwez/doc-radar` remote.

**Tech Stack:** git, GitHub CLI (`gh`)

---

## Context: What exists today

```
doc-radar-marketplace/          <-- marketplace root, NO .git
├── .claude-plugin/
│   └── marketplace.json        <-- marketplace config, source: "./doc-radar"
├── .gitignore
├── doc-radar/                  <-- plugin dir, HAS .git (remote: peekwez/doc-radar)
│   ├── .git/                   <-- moving this UP one level
│   ├── .claude-plugin/
│   │   └── plugin.json         <-- homepage/repository point to peekwez/doc-radar
│   ├── .gitignore
│   ├── agents/, docs/, hooks/, scripts/, skills/, tests/
│   └── README.md
├── git-commit-gws.sh           <-- obsolete bootstrap scripts
└── git-init.sh                 <-- obsolete bootstrap scripts
```

## Target structure (mirrors claude-plugins-official)

```
doc-radar-marketplace/          <-- git root (remote: peekwez/doc-radar-marketplace)
├── .git/
├── .claude-plugin/
│   └── marketplace.json
├── .gitignore                  <-- merged from both levels
├── doc-radar/                  <-- plugin subdirectory, no .git
│   ├── .claude-plugin/
│   │   └── plugin.json         <-- updated: peekwez/doc-radar-marketplace
│   ├── agents/, docs/, hooks/, scripts/, skills/, tests/
│   └── README.md
└── README.md                   <-- new marketplace-level README
```

## Reference: How superpowers / claude-plugins-official do it

- `anthropics/claude-plugins-official` — git at repo root, plugins in `plugins/<name>/`
- `obra/superpowers` — single-plugin repo, git at root, plugin IS the root
- `obra/superpowers-marketplace` — separate marketplace listing repo (README + LICENSE only)

doc-radar fits the **single-plugin marketplace** pattern: one git repo that is also a marketplace with one plugin nested inside. This is valid and is what `claude-plugins-official` does for its own plugins.

---

### Task 1: Create the new GitHub repository

**Files:** none (GitHub operation)

**Step 1: Create `peekwez/doc-radar-marketplace` on GitHub**

```bash
gh repo create peekwez/doc-radar-marketplace \
  --public \
  --description "Claude Code marketplace for the doc-radar plugin — scans Gmail for legal/financial documents and creates calendar reminders"
```

Expected output: repo URL printed, e.g. `https://github.com/peekwez/doc-radar-marketplace`

**Step 2: Verify it was created**

```bash
gh repo view peekwez/doc-radar-marketplace --json url,description
```

Expected: JSON with the URL and description.

---

### Task 2: Move the `.git` directory up to the marketplace root

**Files:**
- Move: `doc-radar/.git/` → `doc-radar-marketplace/.git/`

**Step 1: Move the .git directory**

```bash
mv /Users/kwesi/Desktop/doc-radar-marketplace/doc-radar/.git \
   /Users/kwesi/Desktop/doc-radar-marketplace/.git
```

No output = success.

**Step 2: Verify git now sees the marketplace root as the repo**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace rev-parse --show-toplevel
```

Expected: `/Users/kwesi/Desktop/doc-radar-marketplace`

**Step 3: Confirm old plugin dir no longer has .git**

```bash
ls /Users/kwesi/Desktop/doc-radar-marketplace/doc-radar/.git 2>&1
```

Expected: `ls: ... No such file or directory`

---

### Task 3: Review git status — understand what changed

The git history tracked files relative to `doc-radar/` root (e.g. `skills/`, `agents/`). Now they're at `doc-radar/skills/`, `doc-radar/agents/`. Git will show all old files as deleted and all new paths as untracked.

**Step 1: Check status**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace status
```

Expected: All former tracked files shown as "deleted", marketplace-root files shown as "untracked".

This is expected — we will fix it in Task 5 with a restructure commit.

---

### Task 4: Merge .gitignore files

The marketplace root has a `.gitignore`, and `doc-radar/` has its own. Merge them into one at the root. The `doc-radar/` one can be deleted.

**Step 1: Read both files**

Read `/Users/kwesi/Desktop/doc-radar-marketplace/.gitignore`
Read `/Users/kwesi/Desktop/doc-radar-marketplace/doc-radar/.gitignore`

**Step 2: Write merged .gitignore at marketplace root**

Combine both, prefix `doc-radar/` to any patterns that are specific to the plugin internals (e.g. `doc-radar/.pytest_cache`, `doc-radar/.tracker/*.jsonl`). Keep generic patterns (`.DS_Store`, `__pycache__`) without prefix.

Example merged content:

```
.DS_Store
__pycache__
doc-radar/.pytest_cache
doc-radar/.tracker/*.jsonl
doc-radar/.claude/settings.local.json
```

Write to: `/Users/kwesi/Desktop/doc-radar-marketplace/.gitignore`

**Step 3: Delete the plugin-level .gitignore**

```bash
rm /Users/kwesi/Desktop/doc-radar-marketplace/doc-radar/.gitignore
```

---

### Task 5: Delete obsolete bootstrap scripts

`git-init.sh` and `git-commit-gws.sh` were one-time setup scripts for the old structure. They're no longer needed and would be confusing to anyone reading the repo.

**Step 1: Delete them**

```bash
rm /Users/kwesi/Desktop/doc-radar-marketplace/git-init.sh \
   /Users/kwesi/Desktop/doc-radar-marketplace/git-commit-gws.sh
```

---

### Task 6: Update plugin.json repository fields

`doc-radar/.claude-plugin/plugin.json` still points to `peekwez/doc-radar`. Update both URL fields to the new repo.

**Files:**
- Modify: `doc-radar/.claude-plugin/plugin.json`

**Step 1: Edit plugin.json**

Change:
```json
"homepage": "https://github.com/peekwez/doc-radar",
"repository": "https://github.com/peekwez/doc-radar"
```

To:
```json
"homepage": "https://github.com/peekwez/doc-radar-marketplace",
"repository": "https://github.com/peekwez/doc-radar-marketplace"
```

**Step 2: Verify the edit**

```bash
cat /Users/kwesi/Desktop/doc-radar-marketplace/doc-radar/.claude-plugin/plugin.json
```

Expected: both fields show `doc-radar-marketplace`.

---

### Task 7: Add marketplace-level README.md

The repo root needs a README so the GitHub page is useful.

**Files:**
- Create: `README.md` at marketplace root

**Step 1: Write README.md**

```markdown
# doc-radar-marketplace

A Claude Code plugin marketplace containing the `doc-radar` plugin.

## Plugins

| Plugin | Description |
|--------|-------------|
| [doc-radar](./doc-radar/) | Scans Gmail and watched folders for legal/financial documents. Extracts dates, deduplicates via SHA-256, logs to JSONL, creates Google Calendar events with tiered reminders. |

## Installation

```
/plugin install doc-radar@doc-radar-marketplace
```

## Structure

```
doc-radar-marketplace/
├── .claude-plugin/marketplace.json
├── doc-radar/                  # plugin source
└── README.md
```
```

---

### Task 8: Update git remote to new repo

**Step 1: Update origin remote**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace remote set-url origin \
  https://github.com/peekwez/doc-radar-marketplace.git
```

**Step 2: Verify**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace remote -v
```

Expected:
```
origin  https://github.com/peekwez/doc-radar-marketplace.git (fetch)
origin  https://github.com/peekwez/doc-radar-marketplace.git (push)
```

---

### Task 9: Stage and commit the restructure

**Step 1: Stage all changes**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace add -A
```

**Step 2: Review what will be committed**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace status
```

Expected: all `doc-radar/` plugin files staged as added, old root-relative paths staged as deleted, new files (README.md) staged as added.

**Step 3: Commit**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace commit -m "$(cat <<'EOF'
chore: restructure — move git root to marketplace level

Mirrors the anthropics/claude-plugins-official pattern where the
marketplace repo is the git root and plugins live in subdirectories.

- .git moved from doc-radar/ to marketplace root
- .gitignore merged (plugin-level deleted, marketplace-level updated)
- git-init.sh and git-commit-gws.sh deleted (obsolete bootstrap scripts)
- plugin.json homepage/repository updated to peekwez/doc-radar-marketplace
- Added marketplace-level README.md

Plugin source and all history preserved. Remote updated to
peekwez/doc-radar-marketplace.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

**Step 4: Verify commit**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace log --oneline -3
```

---

### Task 10: Push to new remote

**Step 1: Push main branch**

```bash
git -C /Users/kwesi/Desktop/doc-radar-marketplace push -u origin main
```

**Step 2: Verify on GitHub**

```bash
gh repo view peekwez/doc-radar-marketplace --json url,defaultBranchRef
```

Expected: URL confirmed, branch `main`.

---

### Task 11: Archive the old repo (optional, user decision)

The old `peekwez/doc-radar` repo still exists on GitHub. Options:
1. **Archive it** — mark as read-only with a note pointing to the new repo
2. **Leave it** — no action needed
3. **Delete it** — only if you're sure no one has it installed

Recommended: archive with a description update.

```bash
gh repo archive peekwez/doc-radar --yes
gh repo edit peekwez/doc-radar \
  --description "ARCHIVED: moved to https://github.com/peekwez/doc-radar-marketplace"
```

---

## Verification Checklist

After all tasks complete:

- [ ] `git -C ~/Desktop/doc-radar-marketplace rev-parse --show-toplevel` returns marketplace path
- [ ] `doc-radar-marketplace/doc-radar/.git` does NOT exist
- [ ] `git remote -v` shows `peekwez/doc-radar-marketplace`
- [ ] `plugin.json` has updated `homepage` and `repository` URLs
- [ ] `git log --oneline` shows full old history + restructure commit
- [ ] GitHub shows the new repo with all files visible under `doc-radar/`
- [ ] `marketplace.json` `source: "./doc-radar"` still resolves correctly
