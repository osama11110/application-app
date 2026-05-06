"""
View your job application history.

Usage:
  python history.py              # show all applications
  python history.py --applied    # only successful applications
  python history.py --today      # only today's applications
  python history.py --html       # generate history.html and open in browser
"""
import argparse
import os
import sqlite3
import webbrowser
from datetime import datetime, date

DB_PATH = "applications.db"

SITE_LABELS = {
    "karriere_at":  "karriere.at",
    "stepstone_at": "stepstone.at",
    "jobs_at":      "jobs.at",
    "indeed":       "indeed.at",
    "linkedin":     "LinkedIn",
    "willhaben":    "willhaben.at",
    "hokify":       "hokify.at",
    "xing":         "XING",
    "monster":      "monster.at",
}

STATUS_COLORS = {
    "applied":            "\033[92m",   # green
    "skipped_low_score":  "\033[93m",   # yellow
    "failed":             "\033[91m",   # red
    "error":              "\033[91m",   # red
}
RESET = "\033[0m"
BOLD  = "\033[1m"


def fetch(filter_status: str = None, only_today: bool = False) -> list[dict]:
    if not os.path.exists(DB_PATH):
        return []
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    query = "SELECT * FROM applications"
    params = []
    conditions = []
    if filter_status:
        conditions.append("status = ?")
        params.append(filter_status)
    if only_today:
        conditions.append("applied_at LIKE ?")
        params.append(f"{date.today().isoformat()}%")
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY applied_at DESC"
    rows = [dict(r) for r in conn.execute(query, params).fetchall()]
    conn.close()
    return rows


def format_date(iso: str) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%d %b %Y  %H:%M")
    except Exception:
        return iso[:16]


def print_table(rows: list[dict]):
    if not rows:
        print("  No applications found.")
        return

    # Column widths
    W = {"#": 4, "date": 18, "title": 36, "company": 24, "location": 20, "site": 14, "status": 10, "score": 6}

    header = (
        f"{'#':>{W['#']}}  "
        f"{'Date':<{W['date']}}  "
        f"{'Job Title':<{W['title']}}  "
        f"{'Company':<{W['company']}}  "
        f"{'Location':<{W['location']}}  "
        f"{'Platform':<{W['site']}}  "
        f"{'Status':<{W['status']}}  "
        f"{'Score':>{W['score']}}"
    )
    sep = "─" * len(header)

    print(f"\n{BOLD}{header}{RESET}")
    print(sep)

    for i, r in enumerate(rows, 1):
        status = r.get("status", "")
        color  = STATUS_COLORS.get(status, "")
        site   = SITE_LABELS.get(r.get("site", ""), r.get("site", ""))
        score  = r.get("match_score", 0) or 0
        score_str = f"{score}%" if score else "  —"
        location = (r.get("location") or "")[:W["location"]]

        print(
            f"{i:>{W['#']}}  "
            f"{format_date(r['applied_at']):<{W['date']}}  "
            f"{(r.get('title') or '')[:W['title']]:<{W['title']}}  "
            f"{(r.get('company') or '')[:W['company']]:<{W['company']}}  "
            f"{location:<{W['location']}}  "
            f"{site:<{W['site']}}  "
            f"{color}{status:<{W['status']}}{RESET}  "
            f"{score_str:>{W['score']}}"
        )

    print(sep)
    applied  = sum(1 for r in rows if r["status"] == "applied")
    skipped  = sum(1 for r in rows if r["status"] == "skipped_low_score")
    failed   = sum(1 for r in rows if r["status"] in ("failed", "error"))
    print(f"\n  Total: {len(rows)}  |  "
          f"\033[92mApplied: {applied}\033[0m  |  "
          f"\033[93mSkipped: {skipped}\033[0m  |  "
          f"\033[91mFailed: {failed}\033[0m\n")


# ------------------------------------------------------------------ HTML report
STATUS_HTML_COLORS = {
    "applied":           ("#d1fae5", "#065f46"),
    "skipped_low_score": ("#fef9c3", "#713f12"),
    "failed":            ("#fee2e2", "#991b1b"),
    "error":             ("#fee2e2", "#991b1b"),
}


def generate_html(rows: list[dict], output: str = "history.html"):
    total    = len(rows)
    applied  = sum(1 for r in rows if r["status"] == "applied")
    skipped  = sum(1 for r in rows if r["status"] == "skipped_low_score")
    failed   = sum(1 for r in rows if r["status"] in ("failed", "error"))
    generated = datetime.now().strftime("%d %b %Y %H:%M")

    rows_html = ""
    for i, r in enumerate(rows, 1):
        status = r.get("status", "")
        bg, fg = STATUS_HTML_COLORS.get(status, ("#f3f4f6", "#374151"))
        site   = SITE_LABELS.get(r.get("site", ""), r.get("site", ""))
        score  = r.get("match_score") or 0
        score_str = f"{score}%" if score else "—"
        url    = r.get("url", "#")
        title  = r.get("title") or "—"
        company = r.get("company") or "—"

        location = r.get("location") or "—"
        rows_html += f"""
        <tr>
          <td style="color:#6b7280">{i}</td>
          <td>{format_date(r.get('applied_at',''))}</td>
          <td><a href="{url}" target="_blank" style="color:#2563eb;text-decoration:none">{title}</a></td>
          <td>{company}</td>
          <td style="color:#475569">{location}</td>
          <td><span class="badge site">{site}</span></td>
          <td><span class="badge" style="background:{bg};color:{fg}">{status.replace('_',' ')}</span></td>
          <td style="text-align:center;font-weight:600">{score_str}</td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Job Application History</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #f8fafc; color: #1e293b; padding: 32px 24px; }}
  h1   {{ font-size: 1.6rem; font-weight: 700; margin-bottom: 4px; }}
  .sub {{ color: #64748b; font-size: 0.88rem; margin-bottom: 28px; }}

  .stats {{ display: flex; gap: 16px; margin-bottom: 28px; flex-wrap: wrap; }}
  .stat  {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px;
            padding: 16px 24px; min-width: 110px; text-align: center; }}
  .stat .n {{ font-size: 2rem; font-weight: 700; line-height: 1; }}
  .stat .l {{ font-size: 0.78rem; color: #64748b; margin-top: 4px; text-transform: uppercase; letter-spacing: .05em; }}
  .green {{ color: #16a34a; }}
  .yellow{{ color: #ca8a04; }}
  .red   {{ color: #dc2626; }}
  .blue  {{ color: #2563eb; }}

  .search-bar {{ margin-bottom: 16px; }}
  .search-bar input {{
    width: 100%; max-width: 420px;
    padding: 9px 14px; border: 1px solid #cbd5e1; border-radius: 8px;
    font-size: 0.9rem; outline: none;
  }}
  .search-bar input:focus {{ border-color: #2563eb; }}

  table {{ width: 100%; border-collapse: collapse; background: #fff;
           border-radius: 12px; overflow: hidden;
           box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
  thead {{ background: #f1f5f9; }}
  th    {{ padding: 11px 14px; text-align: left; font-size: 0.78rem;
           text-transform: uppercase; letter-spacing: .06em; color: #64748b;
           font-weight: 600; border-bottom: 1px solid #e2e8f0; }}
  td    {{ padding: 11px 14px; font-size: 0.88rem; border-bottom: 1px solid #f1f5f9; vertical-align: middle; }}
  tr:last-child td {{ border-bottom: none; }}
  tr:hover td {{ background: #f8fafc; }}

  .badge {{ display: inline-block; padding: 3px 10px; border-radius: 999px;
            font-size: 0.76rem; font-weight: 600; white-space: nowrap; }}
  .badge.site {{ background: #eff6ff; color: #1d4ed8; }}

  .footer {{ margin-top: 20px; font-size: 0.8rem; color: #94a3b8; text-align: right; }}
</style>
</head>
<body>

<h1>Job Application History</h1>
<p class="sub">Generated {generated} &nbsp;·&nbsp; Austria Job Automation</p>

<div class="stats">
  <div class="stat"><div class="n blue">{total}</div><div class="l">Total</div></div>
  <div class="stat"><div class="n green">{applied}</div><div class="l">Applied</div></div>
  <div class="stat"><div class="n yellow">{skipped}</div><div class="l">Skipped</div></div>
  <div class="stat"><div class="n red">{failed}</div><div class="l">Failed</div></div>
</div>

<div class="search-bar">
  <input type="text" id="search" placeholder="Filter by job title, company, or platform..." oninput="filterTable()">
</div>

<table id="appTable">
  <thead>
    <tr>
      <th>#</th>
      <th>Date Applied</th>
      <th>Job Title</th>
      <th>Company</th>
      <th>Location</th>
      <th>Platform</th>
      <th>Status</th>
      <th>Match</th>
    </tr>
  </thead>
  <tbody id="tableBody">
    {rows_html}
  </tbody>
</table>

<div class="footer">applications.db &nbsp;·&nbsp; {total} records</div>

<script>
function filterTable() {{
  const q = document.getElementById('search').value.toLowerCase();
  document.querySelectorAll('#tableBody tr').forEach(row => {{
    row.style.display = row.innerText.toLowerCase().includes(q) ? '' : 'none';
  }});
}}
</script>
</body>
</html>"""

    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    return output


# ------------------------------------------------------------------ main
def main():
    parser = argparse.ArgumentParser(description="View job application history")
    parser.add_argument("--applied", action="store_true", help="Show only applied jobs")
    parser.add_argument("--today",   action="store_true", help="Show only today's entries")
    parser.add_argument("--html",    action="store_true", help="Open interactive HTML report in browser")
    args = parser.parse_args()

    status_filter = "applied" if args.applied else None
    rows = fetch(filter_status=status_filter, only_today=args.today)

    if args.html:
        all_rows = fetch()   # HTML report always shows everything
        path = os.path.abspath(generate_html(all_rows))
        print(f"  Report saved: {path}")
        webbrowser.open(f"file:///{path}")
    else:
        print_table(rows)


if __name__ == "__main__":
    main()
