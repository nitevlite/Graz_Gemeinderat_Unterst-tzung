from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
import re
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
        "--topics",
        type=Path,
        default=None,
        help="Optionale JSON-Datei mit Themenkandidaten, z.B. out/topic_candidates.json.",
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
    topics = read_json(args.topics) if args.topics and args.topics.exists() else []
    args.output.write_text(build_html(records, summary, topics), encoding="utf-8")
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


def build_html(records: list[dict], summary: dict, topics: list[dict] | None = None) -> str:
    data = json.dumps([viewer_record(record) for record in records], ensure_ascii=False)
    summary_data = json.dumps(viewer_summary(summary), ensure_ascii=False)
    topics_data = json.dumps([viewer_topic(topic) for topic in topics or []], ensure_ascii=False)
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Graz Gemeinderatsprotokolle</title>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <style>
    :root {{
      color-scheme: light;
      --bg: #f7f8fa;
      --panel: #ffffff;
      --ink: #171923;
      --muted: #687384;
      --line: #e2e8f0;
      --line-strong: #cbd5e1;
      --accent: #2563eb;
      --accent-dark: #1d4ed8;
      --accent-soft: #dbeafe;
      --accent-tint: #eff6ff;
      --warn: #9a5b12;
      --shadow: 0 1px 2px rgba(15, 23, 42, 0.05);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Segoe UI, system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg);
      color: var(--ink);
    }}
    .app-shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
    }}
    .sidebar {{
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 22px 18px;
      position: sticky;
      top: 0;
      height: 100vh;
    }}
    .brand {{
      display: flex;
      gap: 10px;
      align-items: center;
      padding-bottom: 18px;
      margin-bottom: 18px;
      border-bottom: 1px solid var(--line);
    }}
    .brand-mark {{
      display: grid;
      place-items: center;
      width: 38px;
      height: 38px;
      border-radius: 8px;
      background: var(--accent);
      color: white;
      font-weight: 750;
    }}
    .brand-title {{
      display: block;
      font-size: 15px;
      font-weight: 700;
    }}
    .brand-subtitle {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      margin-top: 2px;
    }}
    .side-nav {{
      display: grid;
      gap: 6px;
      margin-bottom: 20px;
    }}
    .side-item {{
      width: 100%;
      min-height: auto;
      border: 0;
      border-radius: 8px;
      color: #334155;
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 10px 11px;
      font-size: 14px;
      font-weight: 600;
      background: transparent;
      cursor: pointer;
      text-align: left;
    }}
    .side-item.active {{
      background: var(--accent-tint);
      color: var(--accent-dark);
    }}
    .side-item:hover {{
      background: #f1f5f9;
      color: var(--accent-dark);
    }}
    .side-dot {{
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: currentColor;
    }}
    .side-note {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
    }}
    .content-shell {{
      min-width: 0;
      display: flex;
      flex-direction: column;
    }}
    header {{
      padding: 22px 28px;
      background: var(--bg);
      border-bottom: 1px solid var(--line);
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 26px;
      font-weight: 700;
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
      grid-template-columns: minmax(260px, 1.4fr) repeat(4, minmax(130px, 1fr)) minmax(128px, 0.8fr);
      gap: 12px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 14px;
      margin-bottom: 16px;
    }}
    .toolbar .wide {{
      grid-column: span 2;
    }}
    input, select, button {{
      width: 100%;
      min-height: 40px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      padding: 8px 11px;
      font: inherit;
      background: white;
      color: var(--ink);
      outline-color: var(--accent);
    }}
    button {{
      cursor: pointer;
      background: var(--accent);
      border-color: var(--accent);
      color: white;
      font-weight: 600;
    }}
    button:hover {{ background: var(--accent-dark); }}
    main {{ padding: 18px 28px 32px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 14px;
    }}
    .stat b {{
      display: block;
      font-size: 24px;
      margin-bottom: 2px;
      color: #0f172a;
    }}
    .stat span {{ color: var(--muted); font-size: 13px; }}
    .table-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: transparent;
    }}
    th, td {{
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
      font-size: 14px;
    }}
    th {{
      background: #f8fafc;
      color: #475569;
      font-size: 13px;
      font-weight: 700;
      white-space: nowrap;
    }}
    tbody tr {{ cursor: pointer; }}
    tbody tr:last-child td {{ border-bottom: 0; }}
    tr:hover td {{ background: #f8fbff; }}
    .title {{ min-width: 280px; font-weight: 600; }}
    .amount-col {{ width: 110px; max-width: 130px; }}
    .places-col {{ min-width: 220px; max-width: 320px; }}
    .results-col {{ min-width: 300px; width: 28%; }}
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
      box-shadow: var(--shadow);
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
    .link-button {{
      appearance: none;
      width: auto;
      min-height: 0;
      border: 0;
      border-radius: 0;
      padding: 0;
      background: transparent;
      color: var(--accent-dark);
      cursor: pointer;
      font: inherit;
      font-weight: 650;
      text-decoration: underline;
    }}
    .link-button:hover {{
      background: transparent;
      color: #0f3ca8;
    }}
    .link-list {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
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
    .topics {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 14px;
      margin-bottom: 16px;
    }}
    .map-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 14px;
      margin-bottom: 16px;
    }}
    .map-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 10px;
    }}
    .map-head h2 {{
      margin: 0;
      font-size: 16px;
    }}
    .map-status {{
      color: var(--muted);
      font-size: 12px;
      text-align: right;
    }}
    .map-note {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 8px;
      line-height: 1.4;
    }}
    .map-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 260px;
      gap: 12px;
      min-height: 430px;
    }}
    #grazMap {{
      min-height: 430px;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #e2e8f0;
    }}
    .map-list {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
      max-height: 430px;
      background: #fbfdff;
    }}
    .map-place {{
      width: 100%;
      border: 0;
      border-bottom: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      color: var(--ink);
      display: block;
      min-height: 0;
      padding: 9px 10px;
      text-align: left;
    }}
    .map-place:hover {{
      background: var(--accent-tint);
    }}
    .map-place strong {{
      display: block;
      font-size: 13px;
      margin-bottom: 2px;
    }}
    .map-place span {{
      color: var(--muted);
      font-size: 12px;
    }}
    .popup-list {{
      display: grid;
      gap: 6px;
      max-width: 280px;
    }}
    .popup-list button {{
      width: 100%;
      min-height: 0;
      padding: 5px 7px;
      border-radius: 6px;
      text-align: left;
      background: white;
      color: var(--accent-dark);
      border: 1px solid #bfdbfe;
      font-size: 12px;
    }}
    .leaflet-interactive.place-dot {{
      stroke: #1d4ed8;
      stroke-width: 2;
      fill: #2563eb;
      fill-opacity: 0.8;
    }}
    .topics h2 {{
      margin: 0 0 10px;
      font-size: 16px;
    }}
    .topic-list {{
      display: grid;
      gap: 10px;
    }}
    .topic {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfdff;
    }}
    .topic-head {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      font-weight: 700;
      margin-bottom: 5px;
    }}
    .topic-label {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
    }}
    .topic-meta {{
      color: var(--muted);
      font-size: 12px;
      margin-bottom: 12px;
    }}
    .timeline {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 10px;
      position: relative;
    }}
    .timeline-step {{
      appearance: none;
      text-align: left;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      color: var(--ink);
      min-height: 94px;
      padding: 10px 11px 10px 34px;
      position: relative;
      cursor: pointer;
      box-shadow: none;
    }}
    .timeline-step:hover {{
      background: var(--accent-tint);
      border-color: #bfdbfe;
    }}
    .timeline-step::before {{
      content: "";
      position: absolute;
      left: 12px;
      top: 14px;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--accent);
      box-shadow: 0 0 0 4px var(--accent-soft);
    }}
    .timeline-date {{
      display: block;
      color: var(--accent-dark);
      font-size: 12px;
      font-weight: 750;
      margin-bottom: 5px;
    }}
    .timeline-title {{
      display: block;
      color: #1e293b;
      font-size: 13px;
      font-weight: 650;
      line-height: 1.3;
      margin-bottom: 7px;
    }}
    .timeline-result {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.3;
    }}
    .topic-action {{
      margin-top: 10px;
      width: auto;
      min-height: 32px;
      padding: 5px 10px;
      font-size: 13px;
      background: white;
      color: var(--accent-dark);
      border-color: #bfdbfe;
    }}
    .topic-action:hover {{
      background: var(--accent-tint);
    }}
    .sr-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      margin-bottom: 5px;
    }}
    .filter-cell {{ min-width: 0; }}
    @media (max-width: 920px) {{
      .app-shell {{ grid-template-columns: 1fr; }}
      .sidebar {{
        position: static;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }}
      .side-nav {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      .toolbar {{ grid-template-columns: 1fr; }}
      .map-layout {{ grid-template-columns: 1fr; }}
      .toolbar .wide {{ grid-column: auto; }}
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
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">GR</div>
        <div>
          <span class="brand-title">Graz Gemeinderat</span>
          <span class="brand-subtitle">Entscheidungsregister</span>
        </div>
      </div>
      <nav class="side-nav" aria-label="Ansichten">
        <button class="side-item active" type="button" data-nav="overview"><span class="side-dot"></span>Übersicht</button>
        <button class="side-item" type="button" data-nav="search"><span class="side-dot"></span>Suche</button>
        <button class="side-item" type="button" data-nav="digra"><span class="side-dot"></span>DIGRA</button>
        <button class="side-item" type="button" data-nav="export"><span class="side-dot"></span>Export</button>
      </nav>
    </aside>
    <div class="content-shell">
      <header>
        <h1>Gemeinderatsprotokolle</h1>
        <div class="meta">
          <span>Lokale HTML-Ansicht</span>
          <span>Ergebnisse bevorzugt aus DIGRA</span>
          <span>Parser-Fallback nur bei fehlenden DIGRA-Daten</span>
        </div>
      </header>
      <main>
        <section class="stats" id="overviewSection">
          <div class="stat"><b id="visibleCount">0</b><span>sichtbare Treffer</span></div>
          <div class="stat"><b id="totalCount">0</b><span>Einträge gesamt</span></div>
          <div class="stat"><b id="fileCount">0</b><span>Dateien mit Einträgen</span></div>
          <div class="stat"><b id="digraCount">0</b><span>DIGRA-Ergebnisse</span></div>
        </section>
        <section class="toolbar" id="searchSection" aria-label="Filter">
          <label class="filter-cell wide"><span class="sr-label">Suche</span><input id="search" type="search" placeholder="Thema, Straße, Geschäftszahl, Betrag"></label>
          <label class="filter-cell"><span class="sr-label">Datum</span><select id="dateFilter"><option value="">Alle Daten</option></select></label>
          <label class="filter-cell"><span class="sr-label">Typ</span><select id="typeFilter"><option value="">Alle Typen</option></select></label>
          <label class="filter-cell"><span class="sr-label">Status</span><select id="statusFilter"><option value="">Alle Status</option></select></label>
          <label class="filter-cell"><span class="sr-label">Ergebnisquelle</span><select id="sourceFilter"><option value="">Alle Quellen</option></select></label>
          <label class="filter-cell"><span class="sr-label">Beträge</span><select id="amountFilter"><option value="">Alle Beträge</option><option value="mit">Mit Betrag</option><option value="ohne">Ohne Betrag</option></select></label>
          <label class="filter-cell"><span class="sr-label">Dateien</span><select id="fileFilter"><option value="">Alle Dateien</option></select></label>
          <label class="filter-cell"><span class="sr-label">Abschnitte</span><select id="sectionFilter"><option value="">Alle Abschnitte</option></select></label>
          <label class="filter-cell"><span class="sr-label">Export</span><button id="csvExport" type="button">CSV Export</button></label>
        </section>
        <section class="detail" id="detailWrap"></section>
        <section class="map-panel" id="mapSection">
          <div class="map-head">
            <h2>Graz-Karte</h2>
            <div class="map-status" id="mapStatus">Orte werden bei Bedarf geladen.</div>
          </div>
          <div class="map-layout">
            <div id="grazMap" aria-label="Karte mit erkannten Orten"></div>
            <div class="map-list" id="mapPlaces"></div>
          </div>
          <div class="map-note">Die Karte nutzt Online-Geocoding. Wenn ein Ort ungenau sitzt, liegt das meist an mehrdeutigen Ortsnamen oder daran, dass die Protokoll-Ortserkennung zu viel Kontext erwischt.</div>
        </section>
        <section class="topics" id="topicsWrap"></section>
        <div id="tableWrap"></div>
      </main>
    </div>
  </div>
  <script>
    const records = {data};
    const summary = {summary_data};
    const topics = {topics_data};
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
    const mapStatus = byId('mapStatus');
    const mapPlaces = byId('mapPlaces');
    let sichtbareEintraege = [];
    let ausgewaehlterEintrag = null;
    let grazMap = null;
    let markerLayer = null;
    const markersByLocation = new Map();
    const locationIndex = buildLocationIndex(records);

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

    function buildLocationIndex(allRecords) {{
      const index = new Map();
      allRecords.forEach((record) => {{
        (record.orte || []).forEach((location) => {{
          if (!location) return;
          if (!mappableLocation(location)) return;
          if (!index.has(location)) index.set(location, []);
          index.get(location).push(record);
        }});
      }});
      return index;
    }}

    function mappableLocation(location) {{
      return !/^(?:EZ\\s+|KG\\s+|Gdst\\.?\\s*Nr)/i.test(String(location || '').trim());
    }}

    function locationLinks(locations) {{
      const values = (locations || []).filter(Boolean);
      if (!values.length) return '-';
      return `<span class="link-list">${{values.map((location) =>
        `<button class="link-button" type="button" data-location="${{escapeHtml(location)}}">${{escapeHtml(location)}}</button>`
      ).join('')}}</span>`;
    }}

    function findRecordById(recordId) {{
      return records.find((record) => record.record_id === recordId) || null;
    }}

    function selectRecord(record, focusMap = false) {{
      if (!record) return;
      ausgewaehlterEintrag = record;
      renderDetail(record);
      detailWrap.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
      if (focusMap && (record.orte || []).length) {{
        focusLocation(record.orte[0]);
      }}
    }}

    function setActiveNav(target) {{
      document.querySelectorAll('[data-nav]').forEach((item) => {{
        item.classList.toggle('active', item.dataset.nav === target);
      }});
    }}

    function scrollToElement(elementId, navTarget) {{
      const element = byId(elementId);
      if (!element) return;
      setActiveNav(navTarget);
      element.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    function initMap() {{
      if (!window.L) {{
        mapStatus.textContent = 'Kartenbibliothek konnte nicht geladen werden.';
        return;
      }}
      grazMap = L.map('grazMap').setView([47.0707, 15.4395], 12);
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
      }}).addTo(grazMap);
      markerLayer = L.layerGroup().addTo(grazMap);
      renderMapPlaces();
      loadVisibleMapMarkers();
    }}

    function renderMapPlaces() {{
      const places = [...locationIndex.entries()]
        .map(([location, locationRecords]) => ({{ location, count: locationRecords.length }}))
        .sort((a, b) => b.count - a.count || a.location.localeCompare(b.location, 'de-AT'))
        .slice(0, 80);
      if (!places.length) {{
        mapPlaces.innerHTML = '<div class="empty">Keine Orte erkannt.</div>';
        return;
      }}
      mapPlaces.innerHTML = places.map((place) => `
        <button class="map-place" type="button" data-location="${{escapeHtml(place.location)}}">
          <strong>${{escapeHtml(place.location)}}</strong>
          <span>${{place.count}} Eintrag${{place.count === 1 ? '' : 'e'}}</span>
        </button>
      `).join('');
    }}

    async function loadVisibleMapMarkers() {{
      const places = [...locationIndex.keys()].slice(0, 120);
      let loaded = 0;
      for (const place of places) {{
        const coords = await geocodeLocation(place);
        if (coords) {{
          addLocationMarker(place, coords);
          loaded += 1;
          mapStatus.textContent = `${{loaded}} Orte auf der Karte`;
        }}
      }}
    }}

    async function geocodeLocation(location) {{
      const cacheKey = `graz-location:${{location}}`;
      const cached = localStorage.getItem(cacheKey);
      if (cached) {{
        try {{
          return JSON.parse(cached);
        }} catch {{
          localStorage.removeItem(cacheKey);
        }}
      }}
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=at&q=${{encodeURIComponent(location + ', Graz, Österreich')}}`;
      try {{
        const response = await fetch(url);
        if (!response.ok) return null;
        const results = await response.json();
        const first = results[0];
        if (!first) return null;
        const coords = {{ lat: Number(first.lat), lon: Number(first.lon) }};
        if (!Number.isFinite(coords.lat) || !Number.isFinite(coords.lon)) return null;
        localStorage.setItem(cacheKey, JSON.stringify(coords));
        await new Promise((resolve) => setTimeout(resolve, 250));
        return coords;
      }} catch {{
        mapStatus.textContent = 'Online-Geocoding nicht verfügbar.';
        return null;
      }}
    }}

    function addLocationMarker(location, coords) {{
      if (!grazMap || !markerLayer || markersByLocation.has(location)) return;
      const locationRecords = locationIndex.get(location) || [];
      const popupRecords = locationRecords.slice(0, 6).map((record) => `
        <button type="button" data-popup-record-id="${{escapeHtml(record.record_id)}}">${{escapeHtml(record.datum)}} · ${{escapeHtml(record.titel)}}</button>
      `).join('');
      const marker = L.circleMarker([coords.lat, coords.lon], {{
        radius: Math.min(11, 5 + Math.sqrt(locationRecords.length)),
        color: '#1d4ed8',
        weight: 2,
        fillColor: '#2563eb',
        fillOpacity: 0.78,
        className: 'place-dot'
      }}).bindPopup(`
        <strong>${{escapeHtml(location)}}</strong>
        <div class="popup-list">${{popupRecords}}</div>
      `);
      marker.addTo(markerLayer);
      markersByLocation.set(location, marker);
    }}

    async function focusLocation(location) {{
      const coords = await geocodeLocation(location);
      if (!coords || !grazMap) return;
      addLocationMarker(location, coords);
      const marker = markersByLocation.get(location);
      grazMap.setView([coords.lat, coords.lon], 16);
      if (marker) marker.openPopup();
      setActiveNav('digra');
      byId('mapSection').scrollIntoView({{ behavior: 'smooth', block: 'start' }});
    }}

    function detailField(label, value) {{
      return `<div class="detail-field"><strong>${{escapeHtml(label)}}</strong><span>${{escapeHtml(value || '-')}}</span></div>`;
    }}

    function digraLink(url, text = 'DIGRA öffnen') {{
      const value = String(url || '');
      if (!value.startsWith('https://digra.graz.at/')) {{
        return '-';
      }}
      return `<a href="${{escapeHtml(value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(text)}}</a>`;
    }}

    function detailLinkField(label, url) {{
      return `<div class="detail-field"><strong>${{escapeHtml(label)}}</strong><span>${{digraLink(url)}}</span></div>`;
    }}

    function detailHtmlField(label, htmlValue) {{
      return `<div class="detail-field"><strong>${{escapeHtml(label)}}</strong><span>${{htmlValue || '-'}}</span></div>`;
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
          ${{detailLinkField('DIGRA-Link', record.digra_url)}}
          ${{detailField('Beträge', joinList(record.betraege))}}
          ${{detailHtmlField('Orte', locationLinks(record.orte))}}
          ${{detailField('Quelldatei', record.quell_datei)}}
        </div>
      `;
    }}

    function renderTopics() {{
      if (!topics.length) {{
        byId('topicsWrap').style.display = 'none';
        return;
      }}
      const rendered = topics.slice(0, 8).map((topic) => {{
        const timeline = (topic.records || []).slice(0, 6).map((record) => `
          <button class="timeline-step" type="button" data-record-id="${{escapeHtml(record.record_id || '')}}">
            <span class="timeline-date">${{escapeHtml(record.meeting_date || '-')}}</span>
            <span class="timeline-title">${{escapeHtml(record.title || '-')}}</span>
            <span class="timeline-result">${{escapeHtml(record.result_text || record.result_source || '')}}</span>
          </button>
        `).join('');
        return `
          <article class="topic">
            <div class="topic-head">
              <span class="topic-label">
                <span>${{escapeHtml(topic.label || 'Thema')}}</span>
                <span class="badge">${{escapeHtml(topic.reason || '')}}</span>
              </span>
              <span class="badge">${{escapeHtml(topic.confidence || '')}}</span>
            </div>
            <div class="topic-meta">
              Zeitstrahl: ${{escapeHtml((topic.dates || []).join(' bis '))}}
              ${{topic.business_number ? ` · Geschäftszahl: ${{escapeHtml(topic.business_number)}}` : ''}}
            </div>
            <div class="timeline">${{timeline}}</div>
            <button class="topic-action" type="button" data-topic-query="${{escapeHtml(topic.label || '')}}">Einträge dazu filtern</button>
          </article>
        `;
      }}).join('');
      byId('topicsWrap').innerHTML = `<h2>Themenverläufe</h2><div class="topic-list">${{rendered}}</div>`;
    }}

    function filteredRecords() {{
      const query = search.value.trim().toLocaleLowerCase('de-AT');
      return records.filter((record) => {{
        if (dateFilter.value && record.datum !== dateFilter.value) return false;
        if (typeFilter.value && record.typ !== typeFilter.value) return false;
        if (statusFilter.value && record.status_filter !== statusFilter.value) return false;
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
          <td data-label="Beträge" class="amount amount-col">${{escapeHtml((record.betraege || []).join(', '))}}</td>
          <td data-label="Orte" class="places-col">${{locationLinks(record.orte)}}</td>
          <td data-label="Ergebnisse" class="result results-col">${{escapeHtml(record.ergebnis || '')}}<br><span class="badge">${{escapeHtml(record.ergebnisquelle || '')}}</span> ${{record.digra_url ? digraLink(record.digra_url, 'DIGRA') : ''}}</td>
        </tr>
      `).join('');

      tableWrap.innerHTML = `
        <div class="table-card">
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
        </div>
      `;
    }}

    fillSelect(dateFilter, records.map((record) => record.datum));
    fillSelect(typeFilter, records.map((record) => record.typ));
    fillSelect(statusFilter, records.map((record) => record.status_filter));
    fillSelect(sourceFilter, records.map((record) => record.ergebnisquelle));
    fillSelect(fileFilter, records.map((record) => record.quell_datei));
    fillSelect(sectionFilter, records.map((record) => record.abschnitt));
    [search, dateFilter, typeFilter, statusFilter, sourceFilter, amountFilter, fileFilter, sectionFilter].forEach((el) => el.addEventListener('input', render));
    csvExport.addEventListener('click', exportCsv);
    tableWrap.addEventListener('click', (event) => {{
      const locationButton = event.target.closest('[data-location]');
      if (locationButton) {{
        event.stopPropagation();
        focusLocation(locationButton.dataset.location || '');
        return;
      }}
      const row = event.target.closest('tr[data-index]');
      if (!row) return;
      ausgewaehlterEintrag = sichtbareEintraege[Number(row.dataset.index)] || null;
      selectRecord(ausgewaehlterEintrag, true);
    }});
    detailWrap.addEventListener('click', (event) => {{
      const locationButton = event.target.closest('[data-location]');
      if (!locationButton) return;
      focusLocation(locationButton.dataset.location || '');
    }});
    mapPlaces.addEventListener('click', (event) => {{
      const locationButton = event.target.closest('[data-location]');
      if (!locationButton) return;
      focusLocation(locationButton.dataset.location || '');
    }});
    byId('grazMap').addEventListener('click', (event) => {{
      const recordButton = event.target.closest('[data-popup-record-id]');
      if (!recordButton) return;
      selectRecord(findRecordById(recordButton.dataset.popupRecordId));
    }});
    byId('topicsWrap').addEventListener('click', (event) => {{
      const step = event.target.closest('[data-record-id]');
      if (step) {{
        selectRecord(findRecordById(step.dataset.recordId), true);
        return;
      }}
      const action = event.target.closest('[data-topic-query]');
      if (action) {{
        search.value = action.dataset.topicQuery || '';
        render();
      }}
    }});
    document.querySelectorAll('[data-nav]').forEach((item) => {{
      item.addEventListener('click', () => {{
        const target = item.dataset.nav;
        if (target === 'overview') scrollToElement('overviewSection', 'overview');
        if (target === 'search') scrollToElement('searchSection', 'search');
        if (target === 'digra') scrollToElement('mapSection', 'digra');
        if (target === 'export') {{
          setActiveNav('export');
          exportCsv();
        }}
      }});
    }});
    renderTopics();
    initMap();
    render();
  </script>
</body>
</html>
"""


def viewer_record(record: dict) -> dict:
    return {
        "record_id": record.get("record_id", ""),
        "datum": record.get("meeting_date", ""),
        "typ": german_record_type(str(record.get("record_type", ""))),
        "abschnitt": record.get("section", ""),
        "stueck_nr": record.get("agenda_item_no", ""),
        "geschaeftszahlen": record.get("business_numbers", []),
        "titel": record.get("title", ""),
        "status": german_status(str(record.get("status", ""))),
        "status_filter": german_status_filter(str(record.get("status", ""))),
        "ergebnis": record.get("result_text", ""),
        "ergebnisquelle": german_result_source(str(record.get("result_source", ""))),
        "digra_url": record.get("digra_url", ""),
        "digra_einlagezahl": record.get("digra_business_number", ""),
        "digra_trefferwert": format_score(record.get("digra_match_score", 0)),
        "betraege": record.get("amounts", []),
        "orte": record.get("locations", []),
        "quell_datei": german_source_file(str(record.get("source_file", ""))),
    }


def viewer_summary(summary: dict) -> dict:
    return {
        "dateien_mit_eintraegen": summary.get("files_with_records", 0),
        "unklare_eintraege": summary.get("records_by_status", {}).get("unknown", 0),
        "digra_ergebnisse": summary.get("digra_results_used", 0),
    }


def viewer_topic(topic: dict) -> dict:
    return {
        "topic_id": topic.get("topic_id", ""),
        "label": topic.get("label", ""),
        "business_number": topic.get("business_number", ""),
        "reason": topic.get("reason", ""),
        "confidence": format_score(topic.get("confidence", 0)),
        "dates": topic.get("dates", []),
        "records": [
            {
                "meeting_date": record.get("meeting_date", ""),
                "title": record.get("title", ""),
                "record_id": record.get("record_id", ""),
                "result_source": german_result_source(str(record.get("result_source", ""))),
                "result_text": record.get("result_text", ""),
            }
            for record in topic.get("records", [])
            if isinstance(record, dict)
        ],
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
        "accepted_unanimous": "angenommen (einstimmig)",
        "accepted_majority": "angenommen (mehrheitlich)",
        "accepted": "angenommen",
        "rejected_majority": "mehrheitlich abgelehnt",
        "rejected": "abgelehnt",
        "assigned": "zugewiesen",
        "postponed": "vertagt",
        "unknown": "unklar",
    }.get(value, value)


def german_status_filter(value: str) -> str:
    if value in {"accepted_unanimous", "accepted_majority", "accepted"}:
        return "Angenommen"
    if value in {"rejected_majority", "rejected"}:
        return "Abgelehnt"
    return german_status(value).capitalize()


def german_result_source(value: str) -> str:
    return {
        "digra": "DIGRA",
        "digra_fehlt": "DIGRA fehlt",
        "protokoll": "Protokoll",
    }.get(value, value or "Protokoll")


def german_source_file(value: str) -> str:
    match = re.search(r"(?P<date>\d{4}-\d{2}-\d{2})", value)
    if match:
        return f"Protokoll {match.group('date')}.docx"
    fallback = re.search(r"(?P<day>\d{2})[._-](?P<month>\d{2})[._-](?P<year>\d{2,4})", value)
    if fallback:
        year = fallback.group("year")
        if len(year) == 2:
            year = f"20{year}"
        return f"Protokoll {year}-{fallback.group('month')}-{fallback.group('day')}.docx"
    return value


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
