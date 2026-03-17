---
name: digest
description: Show a summary of upcoming deadlines from the doc-radar run log. Use when the user asks for a deadline summary, what is coming up, or what documents need attention.
disable-model-invocation: true
---

> Tracker files are stored in `~/.doc-radar/` (created automatically on first use). Override with the `DOC_RADAR_TRACKER_DIR` environment variable.

Read `~/.doc-radar/runs.jsonl` using the `Read` tool (path:
`~/.doc-radar/runs.jsonl`).

Filter records: exclude `status` values of `"duplicate_hash"`,
`"calendar_duplicate_skipped"`, and `"archived"`.

For each record, find the earliest upcoming date across:
`due_date`, `expiry_date`, `renewal_date`, `cancel_by_date`.

Sort by that date ascending. Group into three time horizons:

**THIS WEEK** (next 7 days)
**THIS MONTH** (next 8–30 days)
**LATER** (beyond 30 days)

Output a formatted digest:

```
DOC RADAR DIGEST — Upcoming Deadlines
Generated: [ISO date]
══════════════════════════════════════

THIS WEEK
─────────
[date]  [doc_type]  [doc_ref]  [parties.issuer]  [currency] [amount]
        Source: https://mail.google.com/mail/u/0/#all/[source_id]

THIS MONTH
──────────
...

LATER
─────
...
```

End with:
> "[N] upcoming deadlines. Next: [doc_ref] on [date]."

If `runs.jsonl` does not exist or has no actionable records:
> "No upcoming deadlines found. Run a Gmail scan to process documents."
