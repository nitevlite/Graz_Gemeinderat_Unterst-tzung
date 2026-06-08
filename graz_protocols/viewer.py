from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="graz-protocols-viewer",
        description="Build a local double-click HTML viewer for parser output.",
    )
    parser.add_argument(
        "--records",
        type=Path,
        default=Path("out") / "agenda_items.jsonl",
        help="JSONL records file. Defaults to out/agenda_items.jsonl.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("out") / "summary.json",
        help="Summary JSON file. Defaults to out/summary.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("viewer.html"),
        help="HTML output file. Defaults to viewer.html.",
    )
    args = parser.parse_args(argv)

    if not args.records.exists():
        print(f"Records file not found: {args.records}", file=sys.stderr)
        return 1

    records = read_jsonl(args.records)
    summary = read_json(args.summary) if args.summary.exists() else {}
    args.output.write_text(build_html(records, summary), encoding="utf-8")
    print(f"Wrote {args.output} with {len(records)} records.")
    return 0


def read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_html(records: list[dict], summary: dict) -> str:
    data = json.dumps(records, ensure_ascii=False)
    summary_data = json.dumps(summary, ensure_ascii=False)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Graz Gemeinderatsprotokolle MVP</title>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f6f7f4;
      --panel: #ffffff;
      --ink: #1f2428;
      --muted: #65717b;
      --line: #d9ded6;
      --accent: #0d6b57;
      --accent-soft: #e3f0ec;
      --warn: #a75d10;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Segoe UI, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    header {{
      padding: 24px 28px 18px;
      background: #fdfdfb;
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 24px;
      font-weight: 650;
      letter-spacing: 0;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 14px;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(220px, 1fr) 180px 180px 160px;
      gap: 10px;
      padding: 14px 28px;
      background: #eef2eb;
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    input, select {{
      width: 100%;
      min-height: 38px;
      border: 1px solid #bfc8bd;
      border-radius: 6px;
      padding: 7px 10px;
      font: inherit;
      background: white;
      color: var(--ink);
    }}
    main {{ padding: 18px 28px 32px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(130px, 1fr));
      gap: 10px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
    }}
    .stat b {{
      display: block;
      font-size: 22px;
      margin-bottom: 2px;
    }}
    .stat span {{ color: var(--muted); font-size: 13px; }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 9px 10px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
      font-size: 14px;
    }}
    th {{
      background: #e9eee6;
      position: sticky;
      top: 67px;
      z-index: 1;
      font-size: 13px;
    }}
    tr:hover td {{ background: #fbfcfa; }}
    .title {{ min-width: 280px; font-weight: 600; }}
    .snippet {{
      color: var(--muted);
      max-width: 520px;
      line-height: 1.35;
    }}
    .badge {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 12px;
      white-space: nowrap;
    }}
    .amount {{
      color: var(--warn);
      font-weight: 600;
      white-space: nowrap;
    }}
    .empty {{
      padding: 28px;
      text-align: center;
      color: var(--muted);
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }}
    @media (max-width: 920px) {{
      .toolbar {{ grid-template-columns: 1fr; position: static; }}
      .stats {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
      th {{ position: static; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid var(--line); }}
      td {{ border-bottom: 0; }}
      td::before {{
        content: attr(data-label);
        display: block;
        color: var(--muted);
        font-size: 12px;
        margin-bottom: 3px;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Graz Gemeinderatsprotokolle MVP</h1>
    <div class="meta">
      <span>Lokale HTML-Ansicht</span>
      <span>Keine Protokolle im Git</span>
      <span>Quelle: Parser-Output aus <code>out/agenda_items.jsonl</code></span>
    </div>
  </header>
  <section class="toolbar">
    <input id="search" type="search" placeholder="Suchen: Thema, Straße, Geschäftszahl, Betrag">
    <select id="dateFilter"><option value="">Alle Daten</option></select>
    <select id="statusFilter"><option value="">Alle Status</option></select>
    <select id="sectionFilter"><option value="">Alle Abschnitte</option></select>
  </section>
  <main>
    <section class="stats">
      <div class="stat"><b id="visibleCount">0</b><span>sichtbare Treffer</span></div>
      <div class="stat"><b id="totalCount">0</b><span>Records gesamt</span></div>
      <div class="stat"><b id="fileCount">0</b><span>Dateien mit Records</span></div>
      <div class="stat"><b id="unknownCount">0</b><span>unklarer Status</span></div>
    </section>
    <div id="tableWrap"></div>
  </main>
  <script>
    const records = {data};
    const summary = {summary_data};
    const byId = (id) => document.getElementById(id);
    const search = byId('search');
    const dateFilter = byId('dateFilter');
    const statusFilter = byId('statusFilter');
    const sectionFilter = byId('sectionFilter');
    const tableWrap = byId('tableWrap');

    function escapeHtml(value) {{
      return String(value ?? '').replace(/[&<>"']/g, (char) => ({{
        '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
      }}[char]));
    }}

    function fillSelect(select, values) {{
      [...new Set(values.filter(Boolean))].sort().forEach((value) => {{
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
      }});
    }}

    function recordHaystack(record) {{
      return [
        record.meeting_date,
        record.section,
        record.agenda_item_no,
        ...(record.business_numbers || []),
        record.title,
        record.status,
        ...(record.amounts || []),
        ...(record.locations || []),
        record.source_snippet
      ].join(' ').toLocaleLowerCase('de-AT');
    }}

    function filteredRecords() {{
      const query = search.value.trim().toLocaleLowerCase('de-AT');
      return records.filter((record) => {{
        if (dateFilter.value && record.meeting_date !== dateFilter.value) return false;
        if (statusFilter.value && record.status !== statusFilter.value) return false;
        if (sectionFilter.value && record.section !== sectionFilter.value) return false;
        if (query && !recordHaystack(record).includes(query)) return false;
        return true;
      }});
    }}

    function render() {{
      const visible = filteredRecords();
      byId('visibleCount').textContent = visible.length;
      byId('totalCount').textContent = records.length;
      byId('fileCount').textContent = summary.files_with_records ?? new Set(records.map((r) => r.source_file)).size;
      byId('unknownCount').textContent = summary.records_by_status?.unknown ?? records.filter((r) => r.status === 'unknown').length;

      if (!visible.length) {{
        tableWrap.innerHTML = '<div class="empty">Keine Treffer für diese Filter.</div>';
        return;
      }}

      const rows = visible.map((record) => `
        <tr>
          <td data-label="Datum">${{escapeHtml(record.meeting_date)}}</td>
          <td data-label="Stk.">${{escapeHtml(record.agenda_item_no)}}</td>
          <td data-label="Status"><span class="badge">${{escapeHtml(record.status)}}</span></td>
          <td data-label="Geschäftszahl">${{escapeHtml((record.business_numbers || []).join(', '))}}</td>
          <td data-label="Titel" class="title">${{escapeHtml(record.title)}}</td>
          <td data-label="Beträge" class="amount">${{escapeHtml((record.amounts || []).join(', '))}}</td>
          <td data-label="Orte">${{escapeHtml((record.locations || []).join(', '))}}</td>
          <td data-label="Quelle" class="snippet">${{escapeHtml(record.source_snippet)}}</td>
        </tr>
      `).join('');

      tableWrap.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Stk.</th>
              <th>Status</th>
              <th>Geschäftszahl</th>
              <th>Titel</th>
              <th>Beträge</th>
              <th>Orte</th>
              <th>Quelle</th>
            </tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>
      `;
    }}

    fillSelect(dateFilter, records.map((record) => record.meeting_date));
    fillSelect(statusFilter, records.map((record) => record.status));
    fillSelect(sectionFilter, records.map((record) => record.section));
    [search, dateFilter, statusFilter, sectionFilter].forEach((el) => el.addEventListener('input', render));
    render();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    raise SystemExit(main())
