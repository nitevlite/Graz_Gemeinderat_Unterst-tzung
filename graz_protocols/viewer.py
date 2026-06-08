from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="graz-protocols-viewer",
        description="Erzeugt eine lokale Doppelklick-HTML-Ansicht für die Parser-Ausgabe.",
    )
    parser.add_argument(
        "--records",
        type=Path,
        default=Path("out") / "agenda_items.jsonl",
        help="JSONL-Datei mit Einträgen. Standard: out/agenda_items.jsonl.",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=Path("out") / "summary.json",
        help="JSON-Datei mit Zusammenfassung. Standard: out/summary.json.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("viewer.html"),
        help="HTML-Ausgabedatei. Standard: viewer.html.",
    )
    args = parser.parse_args(argv)

    if not args.records.exists():
        print(f"Eintragsdatei nicht gefunden: {args.records}", file=sys.stderr)
        return 1

    records = read_jsonl(args.records)
    summary = read_json(args.summary) if args.summary.exists() else {}
    args.output.write_text(build_html(records, summary), encoding="utf-8")
    print(f"{args.output} mit {len(records)} Einträgen geschrieben.")
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
    data = json.dumps([viewer_record(record) for record in records], ensure_ascii=False)
    summary_data = json.dumps(viewer_summary(summary), ensure_ascii=False)
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
      grid-template-columns: minmax(220px, 1fr) 155px 155px 155px 155px 155px 150px 130px;
      gap: 10px;
      padding: 14px 28px;
      background: #eef2eb;
      border-bottom: 1px solid var(--line);
      position: sticky;
      top: 0;
      z-index: 2;
    }}
    input, select, button {{
      width: 100%;
      min-height: 38px;
      border: 1px solid #bfc8bd;
      border-radius: 6px;
      padding: 7px 10px;
      font: inherit;
      background: white;
      color: var(--ink);
    }}
    button {{
      cursor: pointer;
      background: var(--accent);
      border-color: var(--accent);
      color: white;
      font-weight: 600;
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
      font-size: 13px;
    }}
    tbody tr {{ cursor: pointer; }}
    tr:hover td {{ background: #fbfcfa; }}
    .title {{ min-width: 280px; font-weight: 600; }}
    .result {{
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
    .detail {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 16px;
    }}
    .detail h2 {{
      margin: 0 0 8px;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: repeat(3, minmax(160px, 1fr));
      gap: 10px 14px;
    }}
    .detail-field strong {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 3px;
    }}
    .detail-field span {{
      white-space: pre-wrap;
    }}
    .detail-empty {{
      color: var(--muted);
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
      .detail-grid {{ grid-template-columns: 1fr; }}
      th {{ position: static; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{ border-bottom: 1px solid var(--line); cursor: pointer; }}
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
      <span>Quelle: lokale Parser-Ausgabe plus DIGRA-Abgleich</span>
    </div>
  </header>
  <section class="toolbar">
    <input id="search" type="search" placeholder="Suchen: Thema, Straße, Geschäftszahl, Betrag">
    <select id="dateFilter"><option value="">Alle Daten</option></select>
    <select id="typeFilter"><option value="">Alle Typen</option></select>
    <select id="statusFilter"><option value="">Alle Status</option></select>
    <select id="sourceFilter"><option value="">Alle Quellen</option></select>
    <select id="amountFilter"><option value="">Alle Beträge</option><option value="mit">Mit Betrag</option><option value="ohne">Ohne Betrag</option></select>
    <select id="fileFilter"><option value="">Alle Dateien</option></select>
    <select id="sectionFilter"><option value="">Alle Abschnitte</option></select>
    <button id="csvExport" type="button">CSV Export</button>
  </section>
  <main>
    <section class="stats">
      <div class="stat"><b id="visibleCount">0</b><span>sichtbare Treffer</span></div>
      <div class="stat"><b id="totalCount">0</b><span>Einträge gesamt</span></div>
      <div class="stat"><b id="fileCount">0</b><span>Dateien mit Einträgen</span></div>
      <div class="stat"><b id="digraCount">0</b><span>DIGRA-Ergebnisse</span></div>
    </section>
    <section class="detail" id="detailWrap"></section>
    <div id="tableWrap"></div>
  </main>
  <script>
    const records = {data};
    const summary = {summary_data};
    const byId = (id) => document.getElementById(id);
    const search = byId('search');
    const dateFilter = byId('dateFilter');
    const typeFilter = byId('typeFilter');
    const statusFilter = byId('statusFilter');
    const sourceFilter = byId('sourceFilter');
    const amountFilter = byId('amountFilter');
    const fileFilter = byId('fileFilter');
    const sectionFilter = byId('sectionFilter');
    const csvExport = byId('csvExport');
    const tableWrap = byId('tableWrap');
    const detailWrap = byId('detailWrap');
    let sichtbareEintraege = [];
    let ausgewaehlterEintrag = null;

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
        record.datum,
        record.typ,
        record.abschnitt,
        record.stueck_nr,
        ...(record.geschaeftszahlen || []),
        record.titel,
        record.status,
        ...(record.betraege || []),
        ...(record.orte || []),
        record.ergebnis,
        record.ergebnisquelle,
        record.digra_einlagezahl
      ].join(' ').toLocaleLowerCase('de-AT');
    }}

    function joinList(values) {{
      return (values || []).filter(Boolean).join(', ') || '-';
    }}

    function detailField(label, value) {{
      return `<div class="detail-field"><strong>${{escapeHtml(label)}}</strong><span>${{escapeHtml(value || '-')}}</span></div>`;
    }}

    function csvCell(value) {{
      return `"${{String(value ?? '').replace(/"/g, '""')}}"`;
    }}

    function exportCsv() {{
      const headers = ['Datum', 'Typ', 'Abschnitt', 'Stück', 'Status', 'Ergebnisquelle', 'Geschäftszahlen', 'Titel', 'Ergebnis', 'Beträge', 'Orte', 'DIGRA-Einlagezahl', 'DIGRA-Link', 'Quelldatei'];
      const rows = sichtbareEintraege.map((record) => [
        record.datum,
        record.typ,
        record.abschnitt,
        record.stueck_nr,
        record.status,
        record.ergebnisquelle,
        joinList(record.geschaeftszahlen),
        record.titel,
        record.ergebnis,
        joinList(record.betraege),
        joinList(record.orte),
        record.digra_einlagezahl,
        record.digra_url,
        record.quell_datei
      ]);
      const csv = [headers, ...rows].map((row) => row.map(csvCell).join(';')).join('\\r\\n');
      const blob = new Blob(['\\ufeff', csv], {{ type: 'text/csv;charset=utf-8' }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = 'graz-gemeinderat-treffer.csv';
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }}

    function renderDetail(record) {{
      if (!record) {{
        detailWrap.innerHTML = '<div class="detail-empty">Eintrag auswählen, um Details zu sehen.</div>';
        return;
      }}
      detailWrap.innerHTML = `
        <h2>${{escapeHtml(record.titel || 'Eintrag')}}</h2>
        <div class="detail-grid">
          ${{detailField('Datum', record.datum)}}
          ${{detailField('Typ', record.typ)}}
          ${{detailField('Stück', record.stueck_nr)}}
          ${{detailField('Status', record.status)}}
          ${{detailField('Geschäftszahlen', joinList(record.geschaeftszahlen))}}
          ${{detailField('Ergebnisquelle', record.ergebnisquelle)}}
          ${{detailField('Ergebnis', record.ergebnis)}}
          ${{detailField('DIGRA-Einlagezahl', record.digra_einlagezahl)}}
          ${{detailField('DIGRA-Trefferwert', record.digra_trefferwert)}}
          ${{detailField('DIGRA-Link', record.digra_url)}}
          ${{detailField('Beträge', joinList(record.betraege))}}
          ${{detailField('Orte', joinList(record.orte))}}
          ${{detailField('Quelldatei', record.quell_datei)}}
        </div>
      `;
    }}

    function filteredRecords() {{
      const query = search.value.trim().toLocaleLowerCase('de-AT');
      return records.filter((record) => {{
        if (dateFilter.value && record.datum !== dateFilter.value) return false;
        if (typeFilter.value && record.typ !== typeFilter.value) return false;
        if (statusFilter.value && record.status !== statusFilter.value) return false;
        if (sourceFilter.value && record.ergebnisquelle !== sourceFilter.value) return false;
        if (amountFilter.value === 'mit' && !(record.betraege || []).length) return false;
        if (amountFilter.value === 'ohne' && (record.betraege || []).length) return false;
        if (fileFilter.value && record.quell_datei !== fileFilter.value) return false;
        if (sectionFilter.value && record.abschnitt !== sectionFilter.value) return false;
        if (query && !recordHaystack(record).includes(query)) return false;
        return true;
      }});
    }}

    function render() {{
      sichtbareEintraege = filteredRecords();
      if (ausgewaehlterEintrag && !sichtbareEintraege.includes(ausgewaehlterEintrag)) {{
        ausgewaehlterEintrag = null;
      }}
      byId('visibleCount').textContent = sichtbareEintraege.length;
      byId('totalCount').textContent = records.length;
      byId('fileCount').textContent = summary.dateien_mit_eintraegen ?? new Set(records.map((r) => r.quell_datei)).size;
      byId('digraCount').textContent = summary.digra_ergebnisse ?? records.filter((r) => r.ergebnisquelle === 'DIGRA').length;
      renderDetail(ausgewaehlterEintrag);

      if (!sichtbareEintraege.length) {{
        tableWrap.innerHTML = '<div class="empty">Keine Treffer für diese Filter.</div>';
        return;
      }}

      const rows = sichtbareEintraege.map((record, index) => `
        <tr data-index="${{index}}">
          <td data-label="Datum">${{escapeHtml(record.datum)}}</td>
          <td data-label="Typ"><span class="badge">${{escapeHtml(record.typ || '')}}</span></td>
          <td data-label="Stk.">${{escapeHtml(record.stueck_nr)}}</td>
          <td data-label="Status"><span class="badge">${{escapeHtml(record.status || '')}}</span></td>
          <td data-label="Geschäftszahl">${{escapeHtml((record.geschaeftszahlen || []).join(', '))}}</td>
          <td data-label="Titel" class="title">${{escapeHtml(record.titel)}}</td>
          <td data-label="Beträge" class="amount">${{escapeHtml((record.betraege || []).join(', '))}}</td>
          <td data-label="Orte">${{escapeHtml((record.orte || []).join(', '))}}</td>
          <td data-label="Ergebnisse" class="result">${{escapeHtml(record.ergebnis || '')}}<br><span class="badge">${{escapeHtml(record.ergebnisquelle || '')}}</span></td>
        </tr>
      `).join('');

      tableWrap.innerHTML = `
        <table>
          <thead>
            <tr>
              <th>Datum</th>
              <th>Typ</th>
              <th>Stk.</th>
              <th>Status</th>
              <th>Geschäftszahl</th>
              <th>Titel</th>
              <th>Beträge</th>
              <th>Orte</th>
              <th>Ergebnisse</th>
            </tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>
      `;
    }}

    fillSelect(dateFilter, records.map((record) => record.datum));
    fillSelect(typeFilter, records.map((record) => record.typ));
    fillSelect(statusFilter, records.map((record) => record.status));
    fillSelect(sourceFilter, records.map((record) => record.ergebnisquelle));
    fillSelect(fileFilter, records.map((record) => record.quell_datei));
    fillSelect(sectionFilter, records.map((record) => record.abschnitt));
    [search, dateFilter, typeFilter, statusFilter, sourceFilter, amountFilter, fileFilter, sectionFilter].forEach((el) => el.addEventListener('input', render));
    csvExport.addEventListener('click', exportCsv);
    tableWrap.addEventListener('click', (event) => {{
      const row = event.target.closest('tr[data-index]');
      if (!row) return;
      ausgewaehlterEintrag = sichtbareEintraege[Number(row.dataset.index)] || null;
      renderDetail(ausgewaehlterEintrag);
    }});
    render();
  </script>
</body>
</html>
"""


def viewer_record(record: dict) -> dict:
    return {
        "datum": record.get("meeting_date", ""),
        "typ": german_record_type(str(record.get("record_type", ""))),
        "abschnitt": record.get("section", ""),
        "stueck_nr": record.get("agenda_item_no", ""),
        "geschaeftszahlen": record.get("business_numbers", []),
        "titel": record.get("title", ""),
        "status": german_status(str(record.get("status", ""))),
        "ergebnis": record.get("result_text", ""),
        "ergebnisquelle": german_result_source(str(record.get("result_source", ""))),
        "digra_url": record.get("digra_url", ""),
        "digra_einlagezahl": record.get("digra_business_number", ""),
        "digra_trefferwert": format_score(record.get("digra_match_score", 0)),
        "betraege": record.get("amounts", []),
        "orte": record.get("locations", []),
        "quell_datei": record.get("source_file", ""),
    }


def viewer_summary(summary: dict) -> dict:
    return {
        "dateien_mit_eintraegen": summary.get("files_with_records", 0),
        "unklare_eintraege": summary.get("records_by_status", {}).get("unknown", 0),
        "digra_ergebnisse": summary.get("digra_results_used", 0),
    }


def german_record_type(value: str) -> str:
    return {
        "agenda_item": "Tagesordnungspunkt",
        "urgent_motion": "Dringlichkeitsantrag",
        "written_question": "Schriftliche Anfrage",
        "written_motion": "Schriftlicher Antrag",
    }.get(value, value)


def german_status(value: str) -> str:
    return {
        "accepted_unanimous": "einstimmig angenommen",
        "accepted_majority": "mehrheitlich angenommen",
        "accepted": "angenommen",
        "rejected_majority": "mehrheitlich abgelehnt",
        "rejected": "abgelehnt",
        "assigned": "zugewiesen",
        "postponed": "vertagt",
        "unknown": "unklar",
    }.get(value, value)


def german_result_source(value: str) -> str:
    return {
        "digra": "DIGRA",
        "digra_fehlt": "DIGRA fehlt",
        "protokoll": "Protokoll",
    }.get(value, value or "Protokoll")


def format_score(value: object) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "-"
    if score <= 0:
        return "-"
    return f"{score:.2f}"


if __name__ == "__main__":
    raise SystemExit(main())
