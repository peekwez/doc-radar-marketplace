#!/usr/bin/env python3
"""
dashboard.py
------------
Generates a self-contained HTML dashboard from .tracker/runs.jsonl.
Uses Tailwind CSS Play CDN and Chart.js CDN — no build step required.

Usage:
  python3 dashboard.py [--runs PATH] [--output PATH] [--open]
"""
import argparse
import html as html_mod
import json
import webbrowser
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

PLUGIN_DIR  = Path(__file__).parent.parent
TRACKER_DIR = PLUGIN_DIR / ".tracker"
TODAY       = date.today()

# shadcn/ui design token colours for badge types
TYPE_COLORS = {
    "invoice":             ("bg-blue-100 text-blue-800",    "#3b82f6"),
    "contract":            ("bg-purple-100 text-purple-800", "#8b5cf6"),
    "msa":                 ("bg-purple-100 text-purple-800", "#8b5cf6"),
    "nda":                 ("bg-yellow-100 text-yellow-800", "#f59e0b"),
    "sow":                 ("bg-green-100 text-green-800",   "#10b981"),
    "purchase_order":      ("bg-orange-100 text-orange-800", "#f97316"),
    "lease":               ("bg-pink-100 text-pink-800",     "#ec4899"),
    "retainer":            ("bg-pink-100 text-pink-800",     "#ec4899"),
    "amendment":           ("bg-gray-100 text-gray-800",     "#6b7280"),
    "legal_notice":        ("bg-red-100 text-red-800",       "#ef4444"),
    "quotation":           ("bg-teal-100 text-teal-800",     "#14b8a6"),
    "subscription_renewal":("bg-indigo-100 text-indigo-800", "#6366f1"),
    "other":               ("bg-gray-100 text-gray-800",     "#6b7280"),
}

STATUS_COLORS = {
    "complete":                   "bg-green-100 text-green-800",
    "extracted":                  "bg-blue-100 text-blue-800",
    "archived":                   "bg-gray-100 text-gray-500 line-through",
    "no_dates_extracted":         "bg-yellow-100 text-yellow-800",
    "calendar_error":             "bg-red-100 text-red-800",
    "calendar_duplicate_skipped": "bg-gray-100 text-gray-600",
    "all_events_past":            "bg-gray-100 text-gray-600",
}


def load_records(runs_path: Path) -> list:
    if not runs_path.exists():
        return []
    records = []
    for line in runs_path.read_text().splitlines():
        line = line.strip()
        if line:
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return records


def key_date(r: dict):
    for field in ("due_date", "expiry_date", "renewal_date", "cancel_by_date"):
        val = r.get(field)
        if val:
            try:
                return date.fromisoformat(val)
            except ValueError:
                pass
    return None


def gmail_link(r: dict) -> str:
    if r.get("source") == "gmail" and r.get("source_id"):
        url = f"https://mail.google.com/mail/u/0/#all/{r['source_id']}"
        return f'<a href="{url}" target="_blank" class="text-blue-600 hover:underline text-xs">Open email ↗</a>'
    elif r.get("source") == "file_drop":
        return f'<span class="text-xs text-slate-500">{html_mod.escape(r.get("source_id", ""))}</span>'
    return '<span class="text-xs text-slate-400">Direct paste</span>'


def fmt_amount(r: dict) -> str:
    v = r.get("value") or {}
    amt = v.get("amount")
    cur = v.get("currency") or ""
    if amt is None:
        return "—"
    return f"{cur} {amt:,.2f}"


def compute_stats(records: list) -> dict:
    total    = len(records)
    upcoming = sum(1 for r in records
                   if r.get("status") != "archived" and key_date(r) and key_date(r) >= TODAY)
    overdue  = sum(1 for r in records
                   if r.get("status") != "archived" and key_date(r) and key_date(r) < TODAY)
    archived = sum(1 for r in records if r.get("status") == "archived")
    return {"total": total, "upcoming": upcoming, "overdue": overdue, "archived": archived}


def compute_monthly(records: list):
    counts: dict = defaultdict(int)
    for r in records:
        ts = r.get("timestamp", "")[:7]  # "YYYY-MM"
        if ts:
            counts[ts] += 1
    months, values = [], []
    today = date.today()
    for i in range(5, -1, -1):
        m = today.month - i
        y = today.year
        while m <= 0:
            m += 12
            y -= 1
        label = f"{y}-{m:02d}"
        months.append(date(y, m, 1).strftime("%b %Y"))
        values.append(counts.get(label, 0))
    return months, values


def compute_by_type(records: list):
    counts: Counter = Counter(r.get("doc_type", "other") for r in records)
    top     = counts.most_common(6)
    labels  = [t for t, _ in top]
    values  = [c for _, c in top]
    colors  = [TYPE_COLORS.get(t, TYPE_COLORS["other"])[1] for t in labels]
    return labels, values, colors


def badge(text: str, css_class: str) -> str:
    return (f'<span class="inline-flex items-center px-2 py-0.5 rounded-full '
            f'text-xs font-medium {css_class}">{html_mod.escape(text)}</span>')


def build_table_rows(records: list) -> str:
    if not records:
        return ('<tr><td colspan="7" class="text-center py-10 text-slate-400">'
                'No documents processed yet.</td></tr>')
    rows = []
    for r in sorted(records, key=lambda x: x.get("timestamp", ""), reverse=True):
        doc_type = r.get("doc_type", "other")
        status   = r.get("status", "")
        kd       = key_date(r)
        kd_str   = kd.isoformat() if kd else "—"
        kd_class = ""
        if kd:
            if kd < TODAY and status != "archived":
                kd_class = "text-red-600 font-medium"
            elif kd.year == TODAY.year and kd.month == (TODAY.month % 12 + 1 if TODAY.month == 12 else TODAY.month + 1):
                kd_class = "text-amber-600 font-medium"

        type_badge   = badge(doc_type.replace("_", " "),
                             TYPE_COLORS.get(doc_type, TYPE_COLORS["other"])[0])
        status_badge = badge(status.replace("_", " "),
                             STATUS_COLORS.get(status, "bg-gray-100 text-gray-700"))

        row_class = "opacity-50" if status == "archived" else "hover:bg-slate-50"
        rows.append(f"""
        <tr class="border-b border-slate-100 {row_class}">
          <td class="py-3 px-4">{type_badge}</td>
          <td class="py-3 px-4 text-sm font-mono">{html_mod.escape(r.get('doc_ref') or '—')}</td>
          <td class="py-3 px-4 text-sm">{html_mod.escape((r.get('parties') or {}).get('issuer', '') or '—')}</td>
          <td class="py-3 px-4 text-sm tabular-nums">{html_mod.escape(fmt_amount(r))}</td>
          <td class="py-3 px-4 text-sm tabular-nums {kd_class}">{kd_str}</td>
          <td class="py-3 px-4">{status_badge}</td>
          <td class="py-3 px-4">{gmail_link(r)}</td>
        </tr>""")
    return "\n".join(rows)


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

    chart_data = json.dumps({
        "monthly": {"labels": months, "values": mvols},
        "byType":  {"labels": tlabels, "values": tvals, "colors": tcolors},
    })

    overdue_color = "text-red-600" if stats["overdue"] > 0 else "text-slate-900"

    html = f"""<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Document Radar Dashboard</title>
  <script>
    tailwind.config = {{
      safelist: [
        'bg-blue-100','text-blue-800','bg-purple-100','text-purple-800',
        'bg-yellow-100','text-yellow-800','bg-green-100','text-green-800',
        'bg-orange-100','text-orange-800','bg-pink-100','text-pink-800',
        'bg-gray-100','text-gray-800','text-gray-500','text-gray-600','text-gray-700',
        'bg-red-100','text-red-800','text-red-600',
        'bg-teal-100','text-teal-800','bg-indigo-100','text-indigo-800',
        'line-through','opacity-50','text-amber-600','font-medium',
      ]
    }}
  </script>
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <style>
    :root {{
      --radius: 0.5rem;
      --border: #e2e8f0;
      --card-shadow: 0 1px 3px 0 rgb(0 0 0 / .1), 0 1px 2px -1px rgb(0 0 0 / .1);
    }}
    body {{ font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }}
    .card {{ background:#fff; border:1px solid var(--border); border-radius:var(--radius); box-shadow:var(--card-shadow); }}
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
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">{stats['upcoming']}</span>
      </a>
      <a href="#" onclick="filterTable('all', this); return false;" class="nav-item flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm">
        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/></svg>
        All Documents
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">{stats['total']}</span>
      </a>
      <a href="#" onclick="filterTable('archived', this); return false;" class="nav-item flex items-center gap-2 px-3 py-2 rounded-md text-slate-600 hover:bg-slate-50 text-sm">
        <svg class="w-4 h-4 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 8h14M5 8a2 2 0 110-4h14a2 2 0 110 4M5 8v10a2 2 0 002 2h10a2 2 0 002-2V8m-9 4h4"/></svg>
        Archived
        <span class="ml-auto text-xs bg-slate-200 rounded-full px-2 py-0.5">{stats['archived']}</span>
      </a>
    </nav>
    <div class="px-5 py-3 border-t border-slate-200 text-xs text-slate-400">
      Generated {now_str}
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
          <p class="mt-2 text-3xl font-bold tabular-nums">{stats['total']}</p>
          <p class="mt-1 text-xs text-slate-400">All time</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Upcoming</p>
          <p class="mt-2 text-3xl font-bold tabular-nums text-blue-600">{stats['upcoming']}</p>
          <p class="mt-1 text-xs text-slate-400">Future key dates</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Overdue</p>
          <p class="mt-2 text-3xl font-bold tabular-nums {overdue_color}">{stats['overdue']}</p>
          <p class="mt-1 text-xs text-slate-400">Past key date, not archived</p>
        </div>
        <div class="card p-5">
          <p class="text-xs font-medium text-slate-500 uppercase tracking-wide">Archived</p>
          <p class="mt-2 text-3xl font-bold tabular-nums text-slate-400">{stats['archived']}</p>
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
              {table_rows}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </main>
</div>

<script>
const CHART_DATA = {chart_data};
const ALL_ROWS   = document.getElementById('tableBody').innerHTML;

// Bar chart — documents per month
new Chart(document.getElementById('barChart'), {{
  type: 'bar',
  data: {{
    labels: CHART_DATA.monthly.labels,
    datasets: [{{ label: 'Documents', data: CHART_DATA.monthly.values,
      backgroundColor: '#6366f1', borderRadius: 4, borderSkipped: false }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{ legend: {{ display: false }} }},
    scales: {{
      x: {{ grid: {{ display: false }}, ticks: {{ font: {{ size: 11 }} }} }},
      y: {{ beginAtZero: true, grid: {{ color: '#f1f5f9' }},
            ticks: {{ stepSize: 1, font: {{ size: 11 }} }} }}
    }}
  }}
}});

// Donut chart — by type
new Chart(document.getElementById('donutChart'), {{
  type: 'doughnut',
  data: {{
    labels: CHART_DATA.byType.labels,
    datasets: [{{ data: CHART_DATA.byType.values,
      backgroundColor: CHART_DATA.byType.colors, borderWidth: 2, borderColor: '#fff' }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    plugins: {{
      legend: {{ position: 'bottom', labels: {{ font: {{ size: 11 }}, padding: 10 }} }}
    }}
  }}
}});

// Table search
function searchTable(q) {{
  const rows = document.querySelectorAll('#tableBody tr');
  q = q.toLowerCase();
  rows.forEach(r => r.style.display = r.textContent.toLowerCase().includes(q) ? '' : 'none');
}}

// Sidebar filter
function filterTable(mode, el) {{
  // Update active nav highlight
  document.querySelectorAll('#sideNav .nav-item').forEach(a => {{
    a.classList.remove('bg-slate-100', 'text-slate-900', 'font-medium');
    a.classList.add('text-slate-600');
  }});
  if (el) {{
    el.classList.remove('text-slate-600');
    el.classList.add('bg-slate-100', 'text-slate-900', 'font-medium');
  }}

  const tbody = document.getElementById('tableBody');
  if (mode === 'all') {{ tbody.innerHTML = ALL_ROWS; return; }}
  const parser = new DOMParser();
  const doc2   = parser.parseFromString('<table><tbody>' + ALL_ROWS + '</tbody></table>', 'text/html');
  const rows   = [...doc2.querySelectorAll('tr')];
  const keep   = rows.filter(r => {{
    const cells = r.querySelectorAll('td');
    if (!cells.length) return true;
    const status = cells[5]?.textContent.toLowerCase() || '';
    const kdate  = cells[4]?.textContent.trim();
    if (mode === 'upcoming') return !status.includes('archived') && kdate && kdate !== '—' && kdate >= '{today_iso}';
    if (mode === 'archived') return status.includes('archived');
    return true;
  }});
  tbody.innerHTML = keep.length ? keep.map(r => r.outerHTML).join('') :
    '<tr><td colspan="7" class="text-center py-10 text-slate-400">No documents match this filter.</td></tr>';
}}

// Export JSON
function exportJSON() {{
  const a = document.createElement('a');
  a.href = 'data:application/json,' + encodeURIComponent(JSON.stringify(CHART_DATA, null, 2));
  a.download = 'document-radar-data.json';
  a.click();
}}
</script>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html)
    print(f"Dashboard written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Generate doc-radar HTML dashboard")
    parser.add_argument("--runs",   type=Path, default=TRACKER_DIR / "runs.jsonl")
    parser.add_argument("--output", type=Path, default=TRACKER_DIR / "dashboard.html")
    parser.add_argument("--open",   action="store_true", help="Open in browser after generating")
    args = parser.parse_args()
    generate(runs_path=args.runs, output_path=args.output)
    if args.open:
        webbrowser.open(f"file://{args.output.resolve()}")


if __name__ == "__main__":
    main()
