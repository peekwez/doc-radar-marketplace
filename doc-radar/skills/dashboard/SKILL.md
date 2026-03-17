---
name: dashboard
description: Generate and open the Doc Radar HTML dashboard from runs.jsonl. Use when the user asks to see the dashboard, view documents visually, or open the report.
disable-model-invocation: true
---

Run the dashboard generator script:

```bash
python3 ${CLAUDE_SKILL_DIR}/../../scripts/dashboard.py --open
```

Then report:
> Tracker files are stored in `~/.doc-radar/` (created automatically on first use). Override with the `DOC_RADAR_TRACKER_DIR` environment variable.

> "Dashboard generated at `~/.doc-radar/dashboard.html` and opened in your browser."

If the script fails (e.g. Python not found or runs.jsonl missing), report the
error and suggest running a Gmail scan first: invoke `doc-radar:legal-doc-detector`.
