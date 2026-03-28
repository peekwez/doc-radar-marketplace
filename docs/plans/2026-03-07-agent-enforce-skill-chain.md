# Agent: Enforce Skill Chain + Dashboard Step

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make both `doc-radar-agent.md` files (1) enforce that all three skills are always invoked in full for every document — no inlining, no skipping — and (2) always invoke the dashboard skill as the final step after every run.

**Architecture:** Markdown edits only. No scripts, no tests.

**Tech Stack:** Markdown only.

---

### Task 1: Update `doc-radar-cowork/agents/doc-radar-agent.md`

**Files:**
- Modify: `doc-radar-cowork/agents/doc-radar-agent.md`

Apply the three changes below.

---

**Change 1 — Add a Mandatory Rules section immediately after the `## Workflow` heading**

Insert this block between `## Workflow` and the first numbered step (`1. **Check for retry items**`):

```
> **MANDATORY:** The skill chain MUST be invoked in full for every document that
> passes detection. Do NOT inline any logic from these skills or skip any step.
> The only permitted short-circuits are:
> - Stop after `doc-radar-cowork:legal-doc-detector` if the item is junk (filtered out)
> - Stop after `doc-radar-cowork:doc-extractor` if the item is a duplicate hash
>
> For every non-duplicate legal document, all three skills MUST run:
> `doc-radar-cowork:legal-doc-detector` → `doc-radar-cowork:doc-extractor` → `doc-radar-cowork:deadline-scheduler`

```

(One blank line before the first numbered step.)

---

**Change 2 — Rewrite step 4 to use an explicit per-item checklist**

Current step 4:
```
4. **For each item in `to_process[]`**, run in sequence:
   a. `doc-radar-cowork:doc-extractor` — uses `hash_check.py --check-only` to detect duplicates,
      extracts fields, writes run log entry, writes `detected` checkpoint
   b. If duplicate: note it, log to skipped.jsonl, continue to next item
   c. If new: update checkpoint to `extracted`
   d. `doc-radar-cowork:deadline-scheduler` — create calendar events via `gcal_create_event`,
      then:
      - Record hash permanently via `hash_check.py` (without --check-only)
      - Write `complete` checkpoint
      - Update run log with event IDs
   e. If calendar creation fails: write `scheduled` checkpoint with error,
      do NOT record hash — item will surface for retry next session
```

Replace with:
```
4. **For each item in `to_process[]`**, run ALL steps in sequence — do not skip:

   **Step A — INVOKE `doc-radar-cowork:doc-extractor`** (mandatory)
   - Runs `hash_check.py --check-only` to detect duplicates
   - Extracts all structured fields
   - Writes run log entry and `detected` checkpoint
   - If duplicate → log to skipped.jsonl, **stop here for this item**
   - If new → update checkpoint to `extracted`, continue to Step B

   **Step B — INVOKE `doc-radar-cowork:deadline-scheduler`** (mandatory for all non-duplicates)
   - Creates calendar events via `gcal_create_event`
   - Records hash permanently via `hash_check.py` (without --check-only)
   - Writes `complete` checkpoint
   - Updates run log with event IDs
   - If calendar creation fails → write `scheduled` checkpoint with error,
     do NOT record hash — item will surface for retry next session

   **Self-check before moving to next item:** Both Step A and Step B were invoked
   (or the item was legitimately stopped at Step A as a duplicate).
```

---

**Change 3 — Add dashboard step after step 7**

Current step 7 (last step):
```
7. **List each processed document:**
   ```
   -> [doc_type] | [doc_ref] | [issuer] / [recipient] | Expires/Due/Renews: [date]
   ```
```

Add a new step 8 immediately after:
```
8. **Invoke `doc-radar-cowork:dashboard`** — generate and open the HTML dashboard
   so the user can see all processed documents visually.
   - This is mandatory after every run, including runs where 0 new documents were found.
   - If the dashboard skill fails, report the error but do not retry — the run is still complete.
```

---

**Step 1: Apply all three changes**

**Step 2: Read the file back and confirm:**
- The `> **MANDATORY:**` callout block is present immediately after `## Workflow`
- Step 4 now has "Step A" and "Step B" with "INVOKE" language and a self-check
- Step 8 exists and invokes `doc-radar-cowork:dashboard`
- No regressions to existing steps 1–3, 5–7, Error Handling, Tools Available, Prerequisites

**Step 3: Commit**
```bash
git add doc-radar-cowork/agents/doc-radar-agent.md
git commit -m "feat(cowork): enforce skill chain and add dashboard step to doc-radar-agent"
```

---

### Task 2: Update `doc-radar/agents/doc-radar-agent.md`

**Files:**
- Modify: `doc-radar/agents/doc-radar-agent.md`

Apply the same three structural changes with `doc-radar:` namespace.

---

**Change 1 — Add Mandatory Rules section immediately after `## Workflow`**

Insert between `## Workflow` and `1. **Check for retry items**`:

```
> **MANDATORY:** The skill chain MUST be invoked in full for every document that
> passes detection. Do NOT inline any logic from these skills or skip any step.
> The only permitted short-circuits are:
> - Stop after `doc-radar:legal-doc-detector` if the item is junk (filtered out)
> - Stop after `doc-radar:doc-extractor` if the item is a duplicate hash
>
> For every non-duplicate legal document, all three skills MUST run:
> `doc-radar:legal-doc-detector` → `doc-radar:doc-extractor` → `doc-radar:deadline-scheduler`

```

---

**Change 2 — Rewrite step 4 with explicit per-item checklist**

Current step 4:
```
4. **For each item in `to_process[]`**, run in sequence:
   a. `doc-radar:doc-extractor` — uses `hash_check.py --check-only` to detect duplicates,
      extracts fields, writes run log entry, writes `detected` checkpoint
   b. If duplicate: note it, log to skipped.jsonl, continue to next item
   c. If new: update checkpoint to `extracted`
   d. `doc-radar:deadline-scheduler` — create calendar events via gws, then:
      - Record hash permanently via `hash_check.py` (without --check-only)
      - Write `complete` checkpoint
      - Update run log with event IDs
   e. If calendar creation fails: write `scheduled` checkpoint with error,
      do NOT record hash — item will surface for retry next session
```

Replace with:
```
4. **For each item in `to_process[]`**, run ALL steps in sequence — do not skip:

   **Step A — INVOKE `doc-radar:doc-extractor`** (mandatory)
   - Runs `hash_check.py --check-only` to detect duplicates
   - Extracts all structured fields
   - Writes run log entry and `detected` checkpoint
   - If duplicate → log to skipped.jsonl, **stop here for this item**
   - If new → update checkpoint to `extracted`, continue to Step B

   **Step B — INVOKE `doc-radar:deadline-scheduler`** (mandatory for all non-duplicates)
   - Creates calendar events via gws
   - Records hash permanently via `hash_check.py` (without --check-only)
   - Writes `complete` checkpoint
   - Updates run log with event IDs
   - If calendar creation fails → write `scheduled` checkpoint with error,
     do NOT record hash — item will surface for retry next session

   **Self-check before moving to next item:** Both Step A and Step B were invoked
   (or the item was legitimately stopped at Step A as a duplicate).
```

---

**Change 3 — Add dashboard step after step 7**

Add new step 8 after step 7:
```
8. **Invoke `doc-radar:dashboard`** — generate and open the HTML dashboard
   so the user can see all processed documents visually.
   - This is mandatory after every run, including runs where 0 new documents were found.
   - If the dashboard skill fails, report the error but do not retry — the run is still complete.
```

---

**Step 1: Apply all three changes**

**Step 2: Read the file back and confirm:**
- The `> **MANDATORY:**` callout block is present immediately after `## Workflow`
- Step 4 now has "Step A" and "Step B" with "INVOKE" language and a self-check
- Step 8 exists and invokes `doc-radar:dashboard`
- No regressions

**Step 3: Commit**
```bash
git add doc-radar/agents/doc-radar-agent.md
git commit -m "feat(doc-radar): enforce skill chain and add dashboard step to doc-radar-agent"
```

---

### Task 3: Push, create PR, and merge

```bash
git push -u origin <current-branch>
gh pr create --title "feat: enforce skill chain and add dashboard step to both doc-radar-agent files" --body "..." --base main
gh pr merge <number> --merge --delete-branch
```
