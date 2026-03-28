# Dashboard Template, Geist Font & Script Co-location Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:**
1. Add Geist font to the dashboard
2. Extract the 200-line HTML f-string into a `dashboard.html` template file; interpolate values using `string.Template` (avoids JS/Tailwind brace-escaping hell)
3. Move `dashboard.py` into `skills/dashboard/scripts/` and keep `dashboard.html` at `skills/dashboard/` root — the official skill folder structure puts scripts in `scripts/` and templates at the skill root (per Claude Code plugin docs)
4. Move `gmail_scan.py` (doc-radar) and `scan_prompt.py` (doc-radar-cowork) into their respective `skills/legal-doc-detector/scripts/` folders — official skill structure puts scripts in `scripts/` subdirectory
5. Shared infrastructure scripts (`hash_check.py`, `checkpoint.py`, `update_log.py`, `jsonl_utils.py`, `retry.py`, `watch_folder.py`) stay in `scripts/` — they are used by multiple skills/hooks

**Architecture:**
- `string.Template` uses `$identifier` syntax → no `{{`/`}}` escaping needed for JavaScript or Tailwind in the template file
- Template is loaded via `Path(__file__).parent / "dashboard.html"` — co-located, no path guessing
- Moved scripts update `${CLAUDE_SKILL_DIR}/scripts/...` references in their SKILL.md (skill dir = `skills/<name>/`, scripts live in `scripts/` sub-folder)
- Moved hook scripts update `${CLAUDE_PLUGIN_ROOT}/skills/.../scripts/...` references in hooks.json
- Test files use `SCRIPT = Path(__file__).parent.parent / "skills" / "..." / "scripts" / "..."` for moved scripts

**Tech Stack:** Python (`string.Template`), HTML/CSS/JS, Tailwind CDN Play, Chart.js, Google Fonts (Geist).

**Geist font CDN:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
```
Body: `font-family: 'Geist', ui-sans-serif, system-ui, sans-serif;`
Monospace elements: `font-family: 'Geist Mono', ui-monospace, monospace;`

---

## Template variable mapping

`string.Template` substitutes `$name` or `${name}`. Map Python values to template vars:

| Template var | Python expression |
|---|---|
| `$stats_total` | `str(stats['total'])` |
| `$stats_upcoming` | `str(stats['upcoming'])` |
| `$stats_overdue` | `str(stats['overdue'])` |
| `$stats_archived` | `str(stats['archived'])` |
| `$overdue_color` | `overdue_color` (the CSS class string) |
| `$now_str` | `now_str` |
| `$today_iso` | `today_iso` |
| `$chart_data_json` | `chart_data` (the JSON string) |
| `$table_rows` | `table_rows` (pre-rendered HTML string) |
| `$tailwind_safelist` | The JSON array string of safelist classes |

---

### Task 1: Create dashboard.html template + update dashboard.py for doc-radar

**Files:**
- Create: `doc-radar/skills/dashboard/dashboard.html`
- Modify: `doc-radar/scripts/dashboard.py`

**Step 1: Create `doc-radar/skills/dashboard/dashboard.html`**

This is the full dashboard HTML with `string.Template` placeholders instead of f-string expressions. Key differences from current `dashboard.py`:
- All `{{` and `}}` (escaped braces for f-string) become `{` and `}` (literal braces — Template ignores them)
- All Python interpolated values become `$varname` placeholders
- Geist font link tags added in `<head>` before Tailwind
- Body font updated to Geist
- Monospace font updated to Geist Mono

Full template content:

```html
<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document Radar Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Geist:wght@300;400;500;600;700&family=Geist+Mono:wght@400;500&display=swap" rel="stylesheet">
  <script>
    tailwind.config = {
      safelist: $tailwind_safelist
    }
  </script>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    :root {
      --radius: 0.5rem;
      --border: #e2e8f0;
      --card-shadow: 0 1px 3px 0 rgb(0 0 0 / .1), 0 1px 2px -1px rgb(0 0 0 / .1);
    }
    body { font-family: 'Geist', ui-sans-serif, system-ui, -apple-system, sans-serif; }
    code, .font-mono { font-family: 'Geist Mono', ui-monospace, monospace; }
    .card { background:#fff; border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--card-shadow); }
  </style>
</head>
<body class="h-full bg-slate-50 text-slate-900">

<div class="flex h-screen overflow-hidden">

  <!-- Sidebar -->
  <aside class="w-56 bg-white border-r border-slate-200 flex flex-col shrink-0">
    <div class="h-14 flex items-center px-5 border-b border-slate-200">
      <span class="text-lg font-semibold tracking-tight">Document Radar</span>
    </div>
    <nav class="flex-1 px-3 py-4 space-y-1" id="sideNav">
      <a href="#" onclick="filterTable('all', this); return false;" class="nav-item flex items-center gap-2 px-3 py-2 rounded-md bg-slate-100 text-slate-900 text-sm font-medium">
        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/></svg>
        Overview
      </a>
      <a href="#" onclick="filterTable('upcoming', this); return false;" class="nav-item flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm">
        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 7V3m8 4V3m-9 8h10M5 21h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"/></svg>
        Upcoming
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">$stats_upcoming</span>
      </a>
      <a href="#" onclick="filterTable('all', this); return false;" class="nav-item flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm">
        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
        All Documents
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">$stats_total</span>
      </a>
      <a href="#" onclick="filterTable('archived', this); return false;" class="nav-item flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm">
        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/></svg>
        Archived
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">$stats_archived</span>
      </a>
    </nav>
    <div class="px-5 py-3 border-t border-slate-200 text-xs text-slate-400">
      Generated $now_str
    </div>
  </aside>

  <!-- Main -->
  <main class="flex-1 overflow-y-auto">
    <header class="h-14 bg-white border-b border-slate-200 flex items-center justify-between px-6">
      <h1 class="text-base font-semibold">Dashboard</h1>
      <button onclick="exportJSON()" class="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-md border border-slate-200 hover:bg-slate-50 transition-colors">
        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/></svg>
        Export JSON
      </button>
    </header>

    <div class="p-6 space-y-6">

      <!-- Stats Cards -->
      <div class="grid grid-cols-4 gap-4">
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Total Documents</p>
          <p class="mt-2 text-3xl font-bold tabular-nums">$stats_total</p>
          <p class="mt-1 text-xs text-slate-400">All time</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Upcoming</p>
          <p class="mt-2 text-3xl font-bold tabular-nums text-blue-600">$stats_upcoming</p>
          <p class="mt-1 text-xs text-slate-400">Future key dates</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Overdue</p>
          <p class="mt-2 text-3xl font-bold tabular-nums $overdue_color">$stats_overdue</p>
          <p class="mt-1 text-xs text-slate-400">Past key date, not archived</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Archived</p>
          <p class="mt-2 text-3xl font-bold tabular-nums text-slate-400">$stats_archived</p>
          <p class="mt-1 text-xs text-slate-400">Resolved / completed</p>
        </div>
      </div>

      <!-- Charts -->
      <div class="grid grid-cols-3 gap-4">
        <div class="card col-span-2 p-5">
          <h2 class="text-sm font-semibold mb-1">Documents Processed</h2>
          <p class="text-xs text-slate-400 mb-4">Last 6 months</p>
          <div style="position:relative;height:200px"><canvas id="barChart"></canvas></div>
        </div>
        <div class="card p-5">
          <h2 class="text-sm font-semibold mb-1">By Document Type</h2>
          <p class="text-xs text-slate-400 mb-4">All time</p>
          <div style="position:relative;height:200px"><canvas id="donutChart"></canvas></div>
        </div>
      </div>

      <!-- Table -->
      <div class="card overflow-hidden">
        <div class="px-5 py-4 border-b border-slate-100 flex items-center justify-between">
          <h2 class="text-sm font-semibold">All Documents</h2>
          <input id="search" type="text" placeholder="Search ref, issuer..."
            oninput="searchTable(this.value)"
            class="text-sm border border-slate-200 rounded-md px-3 py-1.5 w-52 focus:outline-none focus:ring-2 focus:ring-slate-300">
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-slate-100 bg-slate-50">
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Type</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Reference</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Issuer</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Amount</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Key Date</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Status</th>
                <th class="text-left py-3 px-4 text-xs font-medium text-slate-500 uppercase tracking-wide">Source</th>
              </tr>
            </thead>
            <tbody id="tableBody">
              $table_rows
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </main>
</div>

<script>
const CHART_DATA = $chart_data_json;
const ALL_ROWS   = document.getElementById('tableBody').innerHTML;

// Bar chart — documents per month
new Chart(document.getElementById('barChart'), {
  type: 'bar',
  data: {
    labels: CHART_DATA.monthly.labels,
    datasets: [{ label: 'Documents', data: CHART_DATA.monthly.values,
      backgroundColor: '#6366f1', borderRadius: 4, borderSkipped: false }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: { legend: { display: false } },
    scales: {
      x: { grid: { display: false }, ticks: { font: { size: 11 } } },
      y: { beginAtZero: true, grid: { color: '#f1f5f9' },
            ticks: { stepSize: 1, font: { size: 11 } } }
    }
  }
});

// Donut chart — by type
new Chart(document.getElementById('donutChart'), {
  type: 'doughnut',
  data: {
    labels: CHART_DATA.byType.labels,
    datasets: [{ data: CHART_DATA.byType.values,
      backgroundColor: CHART_DATA.byType.colors, borderWidth: 2, borderColor: '#fff' }]
  },
  options: {
    responsive: true, maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom', labels: { font: { size: 11 }, padding: 10 } }
    }
  }
});

// Table search
function searchTable(q) {
  const rows = document.querySelectorAll('#tableBody tr');
  q = q.toLowerCase();
  rows.forEach(r => r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none');
}

// Sidebar filter
function filterTable(mode, el) {
  // Update active nav highlight
  document.querySelectorAll('#sideNav .nav-item').forEach(a => {
    a.classList.remove('bg-slate-100', 'text-slate-900', 'font-medium');
    a.classList.add('text-slate-600');
  });
  if (el) {
    el.classList.remove('text-slate-600');
    el.classList.add('bg-slate-100', 'text-slate-900', 'font-medium');
  }

  const tbody = document.getElementById('tableBody');
  if (mode === 'all') { tbody.innerHTML = ALL_ROWS; return; }
  const parser = new DOMParser();
  const doc2   = parser.parseFromString('<table><tbody>' + ALL_ROWS + '</tbody></table>', 'text/html');
  const rows   = [...doc2.querySelectorAll('tr')];
  const keep   = rows.filter(r => {
    const cells = r.querySelectorAll('td');
    if (!cells.length) return true;
    const status = cells[5]?.textContent.toLowerCase() || '';
    const kdate  = cells[4]?.textContent.trim();
    if (mode === 'upcoming') return !status.includes('archived') && kdate && kdate !== '—' && kdate >= '$today_iso';
    if (mode === 'archived') return status.includes('archived');
    return true;
  });
  tbody.innerHTML = keep.length ? keep.map(r => r.outerHTML).join('') :
    '<tr><td colspan="7" class="text-center py-10 text-slate-400">No documents match this filter.</td></tr>';
}

// Export JSON
function exportJSON() {
  const a = document.createElement('a');
  a.href = 'data:application/json,' + encodeURIComponent(JSON.stringify(CHART_DATA, null, 2));
  a.download = 'document-radar-data.json';
  a.click();
}
</script>
</body>
</html>
```

**Step 2: Rewrite `generate()` in `doc-radar/scripts/dashboard.py`**

Replace the entire f-string in `generate()` with template loading and substitution:

```python
import string   # add to imports at top

def generate(runs_path: Path = None, output_path: Path = None) -> None:
    runs_path   = runs_path   or TRACKER_DIR / "runs.jsonl"
    output_path = output_path or TRACKER_DIR / "dashboard.html"

    records                 = load_records(runs_path)
    stats                   = compute_stats(records)
    months, mvols           = compute_monthly(records)
    tlabels, tvals, tcolors = compute_by_type(records)
    table_rows              = build_table_rows(records)
    now_str                 = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    today_iso               = TODAY.isoformat()

    chart_data_json = json.dumps({
        "monthly": {"labels": months, "values": mvols},
        "byType":  {"labels": tlabels, "values": tvals, "colors": tcolors},
    })

    overdue_color = "text-red-600" if stats["overdue"] > 0 else "text-slate-900"

    tailwind_safelist = json.dumps([
        'bg-blue-100','text-blue-800','bg-purple-100','text-purple-800',
        'bg-yellow-100','text-yellow-800','bg-green-100','text-green-800',
        'bg-orange-100','text-orange-800','bg-pink-100','text-pink-800',
        'bg-gray-100','text-gray-800','text-gray-500','text-gray-600','text-gray-700',
        'bg-red-100','text-red-800','text-red-600',
        'bg-teal-100','text-teal-800','bg-indigo-100','text-indigo-800',
        'line-through','opacity-50','text-amber-600','font-medium',
    ])

    template_path = Path(__file__).parent.parent / "skills" / "dashboard" / "dashboard.html"
    tmpl = string.Template(template_path.read_text())
    html = tmpl.substitute(
        stats_total     = stats['total'],
        stats_upcoming  = stats['upcoming'],
        stats_overdue   = stats['overdue'],
        stats_archived  = stats['archived'],
        overdue_color   = overdue_color,
        now_str         = now_str,
        today_iso       = today_iso,
        chart_data_json = chart_data_json,
        table_rows      = table_rows,
        tailwind_safelist = tailwind_safelist,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    print(f"Dashboard written to: {output_path}")
```

Remove `import string` if already present; add it if not. Remove the old `html = f"""..."""` block entirely.

**Step 3: Run tests**
```bash
python -m pytest doc-radar/tests/test_dashboard.py -q
```
Expected: all pass.

**Step 4: Commit**
```bash
git add doc-radar/skills/dashboard/dashboard.html doc-radar/scripts/dashboard.py
git commit -m "feat(doc-radar): extract dashboard HTML template, add Geist font"
```

---

### Task 2: Create dashboard.html template + update dashboard.py for doc-radar-cowork

**Files:**
- Create: `doc-radar-cowork/skills/dashboard/dashboard.html`
- Modify: `doc-radar-cowork/scripts/dashboard.py`

Apply the exact same changes as Task 1, but:
- Template path in `generate()`: `Path(__file__).parent.parent / "skills" / "dashboard" / "dashboard.html"`
- The cowork `dashboard.py` is identical to doc-radar's after the global tracker change, so the same rewrite applies

**Step 1: Create `doc-radar-cowork/skills/dashboard/dashboard.html`** (same content as Task 1)

**Step 2: Rewrite `generate()` in `doc-radar-cowork/scripts/dashboard.py`** (same as Task 1)

**Step 3: Run tests**
```bash
python -m pytest doc-radar-cowork/tests/test_dashboard.py -q
```
Expected: all pass.

**Step 4: Commit**
```bash
git add doc-radar-cowork/skills/dashboard/dashboard.html doc-radar-cowork/scripts/dashboard.py
git commit -m "feat(doc-radar-cowork): extract dashboard HTML template, add Geist font"
```

---

### Task 3: Move dashboard.py into skills/dashboard/ for both plugins

**Files:**
- Move: `doc-radar/scripts/dashboard.py` → `doc-radar/skills/dashboard/scripts/dashboard.py`
- Move: `doc-radar-cowork/scripts/dashboard.py` → `doc-radar-cowork/skills/dashboard/scripts/dashboard.py`
- Modify: `doc-radar/skills/dashboard/SKILL.md`
- Modify: `doc-radar-cowork/skills/dashboard/SKILL.md`
- Modify: `doc-radar/tests/test_dashboard.py`
- Modify: `doc-radar-cowork/tests/test_dashboard.py`

**Step 1: Move the scripts using git mv**
```bash
mkdir -p doc-radar/skills/dashboard/scripts doc-radar-cowork/skills/dashboard/scripts
git mv doc-radar/scripts/dashboard.py doc-radar/skills/dashboard/scripts/dashboard.py
git mv doc-radar-cowork/scripts/dashboard.py doc-radar-cowork/skills/dashboard/scripts/dashboard.py
```

**Step 2: Update template path in both moved scripts**

The script now lives at `skills/dashboard/scripts/dashboard.py`. The template is one directory up (at the skill root `skills/dashboard/`):

Find in both moved scripts:
```python
template_path = Path(__file__).parent.parent / "skills" / "dashboard" / "dashboard.html"
```
Replace with:
```python
template_path = Path(__file__).parent.parent / "dashboard.html"
```
(`Path(__file__).parent` = `skills/dashboard/scripts/`, `.parent.parent` = `skills/dashboard/`, then `/ "dashboard.html"` = `skills/dashboard/dashboard.html`)

Also update `PLUGIN_DIR`: was `Path(__file__).parent.parent` (from `scripts/`), now the script is 4 levels deep. Check the script: `PLUGIN_DIR = Path(__file__).parent.parent` becomes `PLUGIN_DIR = Path(__file__).parent.parent.parent.parent`.
(`.parent` = `skills/dashboard/scripts/`, `.parent.parent` = `skills/dashboard/`, `.parent.parent.parent` = `skills/`, `.parent.parent.parent.parent` = plugin root)

**Step 3: Update SKILL.md path references**

In `doc-radar/skills/dashboard/SKILL.md`, find:
```
python3 ${CLAUDE_SKILL_DIR}/../../scripts/dashboard.py --open
```
Replace with:
```
python3 ${CLAUDE_SKILL_DIR}/scripts/dashboard.py --open
```
(`${CLAUDE_SKILL_DIR}` = `skills/dashboard/` per Claude Code plugin docs; script lives in `scripts/` under that)

Same for `doc-radar-cowork/skills/dashboard/SKILL.md`.

**Step 4: Update test SCRIPT paths**

In `doc-radar/tests/test_dashboard.py`, find:
```python
SCRIPT = Path(__file__).parent.parent / "scripts" / "dashboard.py"
```
Replace with:
```python
SCRIPT = Path(__file__).parent.parent / "skills" / "dashboard" / "scripts" / "dashboard.py"
```

Same for `doc-radar-cowork/tests/test_dashboard.py`.

**Step 5: Run tests**
```bash
python -m pytest doc-radar/tests/test_dashboard.py doc-radar-cowork/tests/test_dashboard.py -q
```
Expected: all pass.

**Step 6: Commit**
```bash
git add doc-radar/skills/dashboard/scripts/ doc-radar-cowork/skills/dashboard/scripts/ doc-radar/tests/test_dashboard.py doc-radar-cowork/tests/test_dashboard.py
git commit -m "refactor: move dashboard.py into skills/dashboard/scripts/ for both plugins"
```

---

### Task 4: Move gmail_scan.py / scan_prompt.py into skills/legal-doc-detector/

**Files:**
- Move: `doc-radar/scripts/gmail_scan.py` → `doc-radar/skills/legal-doc-detector/scripts/gmail_scan.py`
- Move: `doc-radar-cowork/scripts/scan_prompt.py` → `doc-radar-cowork/skills/legal-doc-detector/scripts/scan_prompt.py`
- Modify: `doc-radar/hooks/hooks.json`
- Modify: `doc-radar-cowork/hooks/hooks.json`
- Modify: `doc-radar/tests/test_gmail_scan.py`
- Modify: `doc-radar-cowork/tests/test_scan_prompt.py`

**Step 1: Move the scripts**
```bash
mkdir -p doc-radar/skills/legal-doc-detector/scripts doc-radar-cowork/skills/legal-doc-detector/scripts
git mv doc-radar/scripts/gmail_scan.py doc-radar/skills/legal-doc-detector/scripts/gmail_scan.py
git mv doc-radar-cowork/scripts/scan_prompt.py doc-radar-cowork/skills/legal-doc-detector/scripts/scan_prompt.py
```

**Step 2: Update PLUGIN_DIR path in both moved scripts**

`gmail_scan.py` has `PLUGIN_DIR = Path(__file__).parent.parent`. After moving to `skills/legal-doc-detector/scripts/`, it's now 4 levels from the plugin root:
(`.parent` = `skills/legal-doc-detector/scripts/`, `.parent.parent` = `skills/legal-doc-detector/`, `.parent.parent.parent` = `skills/`, `.parent.parent.parent.parent` = plugin root)

Find in `doc-radar/skills/legal-doc-detector/scripts/gmail_scan.py`:
```python
PLUGIN_DIR  = Path(__file__).parent.parent
```
Replace with:
```python
PLUGIN_DIR  = Path(__file__).parent.parent.parent.parent
```

Same for `doc-radar-cowork/skills/legal-doc-detector/scripts/scan_prompt.py`:
```python
PLUGIN_DIR  = Path(__file__).parent.parent
```
Replace with:
```python
PLUGIN_DIR  = Path(__file__).parent.parent.parent.parent
```

**Step 3: Update hooks.json in both plugins**

In `doc-radar/hooks/hooks.json`, find:
```
${CLAUDE_PLUGIN_ROOT}/scripts/gmail_scan.py
```
Replace with:
```
${CLAUDE_PLUGIN_ROOT}/skills/legal-doc-detector/scripts/gmail_scan.py
```

In `doc-radar-cowork/hooks/hooks.json`, find:
```
${CLAUDE_PLUGIN_ROOT}/scripts/scan_prompt.py
```
Replace with:
```
${CLAUDE_PLUGIN_ROOT}/skills/legal-doc-detector/scripts/scan_prompt.py
```

**Step 4: Update test SCRIPT paths**

In `doc-radar/tests/test_gmail_scan.py`, find:
```python
SCRIPT = Path(__file__).parent.parent / "scripts" / "gmail_scan.py"
```
(or however it references the script — read the file first)
Replace with:
```python
SCRIPT = Path(__file__).parent.parent / "skills" / "legal-doc-detector" / "scripts" / "gmail_scan.py"
```

In `doc-radar-cowork/tests/test_scan_prompt.py`, the import uses `importlib`:
```python
Path(__file__).parent.parent / "scripts" / "scan_prompt.py"
```
Replace with:
```python
Path(__file__).parent.parent / "skills" / "legal-doc-detector" / "scripts" / "scan_prompt.py"
```

**Step 5: Run tests**
```bash
python -m pytest doc-radar/tests/test_gmail_scan.py doc-radar-cowork/tests/test_scan_prompt.py -q
```
Expected: all pass.

**Step 6: Commit**
```bash
git add doc-radar/skills/legal-doc-detector/scripts/ doc-radar-cowork/skills/legal-doc-detector/scripts/ \
        doc-radar/hooks/hooks.json doc-radar-cowork/hooks/hooks.json \
        doc-radar/tests/test_gmail_scan.py doc-radar-cowork/tests/test_scan_prompt.py
git commit -m "refactor: move gmail_scan.py / scan_prompt.py into skills/legal-doc-detector/scripts/"
```

---

### Task 5: Full verification, push, PR, merge

**Step 1: Run full test suite**
```bash
python -m pytest doc-radar/tests/ doc-radar-cowork/tests/ -q
```
Expected: all 81 tests pass.

**Step 2: Verify no stale script references in SKILL.md files**
```bash
# Should not find top-level scripts/ references — only skills/.../scripts/ is valid now
grep -r "\"scripts/dashboard\.py\|\"scripts/gmail_scan\.py\|\"scripts/scan_prompt\.py" doc-radar/skills/ doc-radar-cowork/skills/
```
Expected: no matches (all references should now say `skills/dashboard/scripts/` or `${CLAUDE_SKILL_DIR}/scripts/`).

**Step 3: Verify no stale hook references pointing to top-level scripts/**
```bash
grep -r "PLUGIN_ROOT}/scripts/gmail_scan\|PLUGIN_ROOT}/scripts/scan_prompt" doc-radar/hooks/ doc-radar-cowork/hooks/
```
Expected: no matches (hooks now reference `skills/legal-doc-detector/scripts/`).

**Step 4: Push, create PR, merge**
```bash
git push -u origin <current-branch>
gh pr create --title "feat: Geist font, HTML template, scripts co-located with skills" --base main
gh pr merge <number> --merge --delete-branch
```
