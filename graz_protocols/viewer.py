from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
import re
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .mobility_sources import load_parking_garages, load_roadworks, mobility_source_summary


CATEGORY_RULES = [
    (
        "Kultur, Sport & Veranstaltungen",
        re.compile(
            r"\b(kultur|literaturhaus|museum|sport|stadion|veranstaltung|fest|theater|kunst|musik|"
            r"eiskrippe|krampuslauf|fußball|fussball)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Bauen & Stadtplanung",
        re.compile(
            r"\b(bebauungsplan|flächenwidmungsplan|flaechenwidmungsplan|bausperre|stadtteilentwicklung|"
            r"rahmenplan|stadtplanung|entwicklungskonzept|widmung|gdst|grundstück|grundstueck|"
            r"liegenschaft|dienstbarkeit|baurecht|bauprojekt|quartier)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Kanal, Wasser & Infrastruktur",
        re.compile(
            r"\b(abwasser|kanal|wasserwirtschaft|gewässer|gewaesser|mur|mühlgang|muehlgang|hochwasser|"
            r"hochwasserschutz|leitung|fernwärme|fernwaerme|sammler|entsorgungsanlage|infrastruktur)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Verkehr & Mobilität",
        re.compile(
            r"\b(mobilität|mobilitaet|verkehr|verkehrsplanung|verkehrssicherheit|straße|strasse|gasse|weg|"
            r"schutzweg|zebrastreifen|rad|fahrrad|straßenbahn|strassenbahn|straßenbahnlinie|"
            r"strassenbahnlinie|tram|bus|öffi|oeffi|"
            r"haltestelle|parkplatz|parken|tempo|geschwindigkeit|einbahn|kreuzung|gehsteig|"
            r"fußverkehr|fussverkehr|s-bahn|tunnel)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Kanal, Wasser & Infrastruktur",
        re.compile(
            r"\b(abwasser|kanal|wasserwirtschaft|gewässer|gewaesser|mur|mühlgang|muehlgang|hochwasser|"
            r"hochwasserschutz|leitung|fernwärme|fernwaerme|sammler|entsorgungsanlage|infrastruktur)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Budget & Förderungen",
        re.compile(
            r"\b(budget|budgetvorsorge|förderung|foerderung|förderungsvertrag|foerderungsvertrag|"
            r"projektgenehmigung|aufwandsgenehmigung|euro|darlehen|kredit|jahresabschluss|"
            r"investition|kosten|tarif|abgangsdeckung|finanzierung|steuer)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Beteiligungen & Unternehmen",
        re.compile(
            r"\b(gmbh|holding|itg|gbg|energie graz|aufsichtsrat|generalversammlung|stimmrecht|"
            r"umlaufbeschluss|abschlussprüfer|abschlusspruefer|bestellung|abberufung)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Verwaltung & Recht",
        re.compile(
            r"\b(statut|verordnung|geschäftsordnung|geschaeftsordnung|ausschuss|stadtsenat|"
            r"vertretung|entsendung|kommission|kuratorium|volksbefragung|"
            r"volksabstimmung|petition|landtag|richtlinie)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Bildung & Jugend",
        re.compile(
            r"\b(bildung|kindergarten|kinderkrippe|schule|volksschule|mittelschule|jugend|kinder|"
            r"kinderbetreuung|kinderbetreuungseinrichtung|radlbonus|betreuung|tarifsystem|pflichtschule|lehrstelle)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Soziales & Gesundheit",
        re.compile(
            r"\b(sozial|pflege|gesundheit|krankenversicherung|bestattung|hilfe in besonderen lebenslagen|"
            r"behindert|inklusion|senior|armut|barrierefrei|kfa)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Umwelt, Klima & Energie",
        re.compile(
            r"\b(umwelt|klima|energie|energieeffizienz|grünraum|gruenraum|baum|baumschutz|naturschutz|"
            r"vogelschutz|emission|nachhaltig|photovoltaik|schatten|begrünung|begruenung)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Kultur, Sport & Veranstaltungen",
        re.compile(
            r"\b(kultur|literaturhaus|museum|sport|stadion|veranstaltung|fest|theater|kunst|musik|"
            r"eiskrippe|krampuslauf|fußball|fussball)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Wohnen & Gebäude",
        re.compile(
            r"\b(wohnen|wohnbau|wohnhaus|wohnraum|gemeindewohnung|wohnkostenmodell|immobilien|"
            r"gebäude|gebaeude|sanierung|miete|wc-anlage|baumanagement)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "Sicherheit & Ordnung",
        re.compile(
            r"\b(sicherheit|ordnung|ordnungswache|unfall|kriminal|polizei|alkohol|lärm|laerm|"
            r"vandalismus|wildparker|kontrolle|abfuhrordnung|mistkübel|mistkuebel)\b",
            re.IGNORECASE,
        ),
    ),
]


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
    parser.add_argument(
        "--parking-cache",
        type=Path,
        default=Path("out") / "parkgaragen_graz.csv",
        help="Optionaler Cache für den OGD-Datensatz Parkgaragen Graz.",
    )
    parser.add_argument(
        "--roadworks-cache",
        type=Path,
        default=Path("out") / "baustellen_graz.html",
        help="Optionaler Cache für die offizielle Baustellen-Seite der Stadt Graz.",
    )
    args = parser.parse_args(argv)

    if not args.records.exists():
        print(f"Eintragsdatei nicht gefunden: {args.records}", file=sys.stderr)
        return 1

    records = read_jsonl(args.records)
    summary = read_json(args.summary) if args.summary.exists() else {}
    topics = read_json(args.topics) if args.topics and args.topics.exists() else []
    garages, parking_summary = load_parking_garages(args.parking_cache)
    roadworks, roadworks_summary = load_roadworks(args.roadworks_cache)
    mobility_summary = mobility_source_summary()
    mobility_summary["parking"]["records"] = parking_summary.get("records", 0)
    mobility_summary["parking"]["errors"] = parking_summary.get("errors", [])
    mobility_summary["roadworks"]["records"] = roadworks_summary.get("records", 0)
    mobility_summary["roadworks"]["errors"] = roadworks_summary.get("errors", [])
    args.output.write_text(build_html(records, summary, topics, garages, mobility_summary, roadworks), encoding="utf-8")
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


def build_html(
    records: list[dict],
    summary: dict,
    topics: list[dict] | None = None,
    parking_garages: list[dict] | None = None,
    mobility_sources: dict | None = None,
    roadworks: list[dict] | None = None,
) -> str:
    data = json.dumps([viewer_record(record) for record in records], ensure_ascii=False)
    summary_data = json.dumps(viewer_summary(summary), ensure_ascii=False)
    topics_data = json.dumps([viewer_topic(topic) for topic in topics or []], ensure_ascii=False)
    parking_data = json.dumps(parking_garages or [], ensure_ascii=False)
    mobility_data = json.dumps(mobility_sources or mobility_source_summary(), ensure_ascii=False)
    roadworks_data = json.dumps(roadworks or [], ensure_ascii=False)
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
      gap: 0;
      padding: 11px 12px;
      font-size: 16px;
      font-weight: 700;
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
      display: none;
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
    .tab-panel {{
      display: none;
    }}
    .tab-panel.active {{
      display: block;
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
      grid-template-columns: minmax(260px, 1.4fr) repeat(5, minmax(120px, 1fr)) minmax(128px, 0.8fr);
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
    .amount-col {{ width: 105px; min-width: 95px; max-width: 115px; overflow-wrap: anywhere; word-break: break-word; }}
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
      white-space: normal;
      overflow-wrap: anywhere;
      word-break: break-word;
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
    .summary-blocks {{
      display: grid;
      gap: 10px;
      margin-top: 14px;
    }}
    .summary-block {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
      overflow: hidden;
      contain: layout paint;
    }}
    .summary-toggle {{
      width: 100%;
      min-height: 0;
      border: 0;
      border-radius: 0;
      background: transparent;
      text-align: left;
      padding: 10px 12px;
      font-weight: 700;
      color: #1e293b;
    }}
    .summary-toggle:hover {{
      background: var(--accent-tint);
      color: var(--accent-dark);
    }}
    .summary-text {{
      padding: 0 12px 12px;
      color: #334155;
      line-height: 1.45;
      white-space: pre-wrap;
      contain: layout paint;
    }}
    .summary-text[hidden] {{
      display: none;
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
    .source-url {{
      display: block;
      max-width: 260px;
      overflow-wrap: anywhere;
      color: var(--muted);
      font-size: 11px;
      margin-top: 3px;
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
    .map-progress {{
      height: 6px;
      border-radius: 999px;
      overflow: hidden;
      background: #dbeafe;
      margin-bottom: 10px;
      display: none;
    }}
    .map-progress.is-active {{
      display: block;
    }}
    .map-progress-bar {{
      height: 100%;
      width: 0%;
      background: var(--accent);
      transition: width 160ms ease;
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
      min-height: 720px;
    }}
    #grazMap,
    #roadworksMap,
    #parkingMap {{
      min-height: 720px;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #e2e8f0;
    }}
    .map-list {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
      max-height: 720px;
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
    .map-place small {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.25;
      margin-top: 2px;
    }}
    .split-form {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }}
    .split-form .wide {{
      grid-column: 1 / -1;
    }}
    .check-result {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
      padding: 10px;
      margin-bottom: 12px;
      font-size: 13px;
      line-height: 1.45;
    }}
    .source-note {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
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
      stroke-width: 2;
      fill-opacity: 0.8;
    }}
    .leaflet-interactive.place-dot.related-place {{
      stroke: #047857;
      fill: #10b981;
      fill-opacity: 0.9;
    }}
    .map-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin-bottom: 10px;
    }}
    .legend-item {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #fbfdff;
      padding: 4px 8px;
      color: #334155;
      font-size: 12px;
      font-weight: 650;
      min-height: 0;
      width: auto;
      cursor: pointer;
    }}
    .legend-item.is-active {{
      border-color: var(--category-color, var(--accent));
      background: var(--accent-tint);
      color: var(--accent-dark);
    }}
    .legend-item:hover {{
      border-color: var(--category-color, var(--accent));
      background: #f8fafc;
    }}
    .legend-swatch {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--category-color, #64748b);
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
    .active-filter {{
      display: none;
      align-items: center;
      gap: 8px;
      margin: 0 0 12px;
      padding: 8px 10px;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      background: var(--accent-tint);
      color: var(--accent-dark);
      font-size: 13px;
    }}
    .active-filter.is-active {{
      display: flex;
    }}
    .active-filter button,
    #roadworkCheck {{
      width: auto;
      min-height: 32px;
      padding: 5px 10px;
      font-size: 13px;
    }}
    #roadworkCheck {{
      justify-self: start;
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
        <button class="side-item active" type="button" data-nav="search">Suche</button>
        <button class="side-item" type="button" data-nav="overview">Zeitstrahlen</button>
        <button class="side-item" type="button" data-nav="map">Karte</button>
        <button class="side-item" type="button" data-nav="roadworks">Baustellen</button>
        <button class="side-item" type="button" data-nav="parking">Tiefgaragen</button>
        <button class="side-item" type="button" data-nav="export">Export</button>
      </nav>
    </aside>
    <div class="content-shell">
      <header>
        <h1>Gemeinderatsprotokolle</h1>
      </header>
      <main>
        <section class="toolbar" id="searchSection" aria-label="Filter">
          <label class="filter-cell wide"><span class="sr-label">Suche</span><input id="search" type="search" list="globalSuggestions" placeholder="Thema, Straße, Geschäftszahl, Betrag"></label>
          <label class="filter-cell"><span class="sr-label">Jahr</span><select id="yearFilter"><option value="">Alle Jahre</option></select></label>
          <label class="filter-cell"><span class="sr-label">Datum</span><select id="dateFilter"><option value="">Alle Daten</option></select></label>
          <label class="filter-cell"><span class="sr-label">Typ</span><select id="typeFilter"><option value="">Alle Typen</option></select></label>
          <label class="filter-cell"><span class="sr-label">Status</span><select id="statusFilter"><option value="">Alle Status</option></select></label>
          <label class="filter-cell"><span class="sr-label">Thema</span><select id="categoryFilter"><option value="">Alle Themen</option></select></label>
          <label class="filter-cell"><span class="sr-label">Ergebnisquelle</span><select id="sourceFilter"><option value="">Alle Quellen</option></select></label>
          <label class="filter-cell"><span class="sr-label">Beträge</span><select id="amountFilter"><option value="">Alle Beträge</option><option value="mit">Mit Betrag</option><option value="ohne">Ohne Betrag</option></select></label>
          <label class="filter-cell"><span class="sr-label">Dateien</span><select id="fileFilter"><option value="">Alle Dateien</option></select></label>
          <label class="filter-cell"><span class="sr-label">Abschnitte</span><select id="sectionFilter"><option value="">Alle Abschnitte</option></select></label>
        </section>
        <datalist id="globalSuggestions"></datalist>
        <datalist id="locationSuggestions"></datalist>
        <div class="active-filter" id="topicFilterNotice">
          <span id="topicFilterText">Themenfilter aktiv.</span>
          <button id="clearTopicFilter" type="button">Zurücksetzen</button>
        </div>
        <section class="tab-panel active" id="searchPanel">
          <section class="detail" id="detailWrap"></section>
          <div id="tableWrap"></div>
        </section>
        <section class="tab-panel" id="overviewPanel">
          <section class="stats" id="overviewSection">
            <div class="stat"><b id="visibleCount">0</b><span>sichtbare Treffer</span></div>
            <div class="stat"><b id="totalCount">0</b><span>Einträge gesamt</span></div>
            <div class="stat"><b id="fileCount">0</b><span>Dateien mit Einträgen</span></div>
            <div class="stat"><b id="digraCount">0</b><span>DIGRA-Ergebnisse</span></div>
          </section>
          <section class="topics" id="topicsWrap"></section>
        </section>
        <section class="tab-panel map-panel" id="mapPanel">
          <div class="map-head">
            <h2>Graz-Karte</h2>
            <div class="map-status" id="mapStatus">Orte werden bei Bedarf geladen.</div>
          </div>
          <div class="map-progress" id="mapProgress" aria-hidden="true">
            <div class="map-progress-bar" id="mapProgressBar"></div>
          </div>
          <div class="map-legend" id="mapLegend" aria-label="Kartenlegende"></div>
          <div class="map-layout">
            <div id="grazMap" aria-label="Karte mit erkannten Orten"></div>
            <div class="map-list" id="mapPlaces"></div>
          </div>
          <div class="map-note">Die Karte nutzt Online-Geocoding. Wenn ein Ort ungenau sitzt, liegt das meist an mehrdeutigen Ortsnamen oder daran, dass die Protokoll-Ortserkennung zu viel Kontext erwischt.</div>
        </section>
        <section class="tab-panel map-panel" id="roadworksPanel">
          <div class="map-head">
            <h2>Baustellenplanung</h2>
            <div class="map-status" id="roadworksStatus">Eigene Baustelle eingeben und Konflikte prüfen.</div>
          </div>
          <div class="split-form">
            <label class="filter-cell"><span class="sr-label">Straße oder Ort</span><input id="roadworkLocation" type="text" list="locationSuggestions" placeholder="z. B. Conrad-von-Hötzendorf-Straße"></label>
            <label class="filter-cell"><span class="sr-label">Art</span><select id="roadworkKind"><option>Baustelle</option><option>Totalsperre</option><option>Fahrstreifensperre</option><option>Materiallagerung</option><option>Veranstaltung</option></select></label>
            <label class="filter-cell"><span class="sr-label">Start</span><input id="roadworkStart" type="date"></label>
            <label class="filter-cell"><span class="sr-label">Ende</span><input id="roadworkEnd" type="date"></label>
            <label class="filter-cell wide"><span class="sr-label">Beschreibung</span><input id="roadworkDescription" type="text" placeholder="kurz: Sperre, Umleitung, betroffene Abschnitte"></label>
            <button id="roadworkCheck" type="button">Prüfen</button>
          </div>
          <div class="check-result" id="roadworkResult">Noch keine Baustelle geprüft.</div>
          <div class="map-layout">
            <div id="roadworksMap" aria-label="Karte für Baustellenplanung"></div>
            <div class="map-list" id="roadworksList"></div>
          </div>
          <div class="source-note" id="roadworksSourceNote"></div>
        </section>
        <section class="tab-panel map-panel" id="parkingPanel">
          <div class="map-head">
            <h2>Tiefgaragen</h2>
            <div class="map-status" id="parkingStatus">Verfügbarkeit: unbekannt.</div>
          </div>
          <div class="map-layout">
            <div id="parkingMap" aria-label="Karte mit Tiefgaragen und Parkhäusern"></div>
            <div class="map-list" id="parkingList"></div>
          </div>
          <div class="source-note" id="parkingSourceNote"></div>
        </section>
        <section class="tab-panel" id="exportPanel">
          <section class="detail">
            <h2>Export</h2>
            <div class="detail-grid">
              <div class="detail-field"><strong>Aktuelle Auswahl</strong><span id="exportCount">0 Einträge</span></div>
              <div class="detail-field"><strong>Format</strong><span>CSV mit den sichtbaren Treffern</span></div>
              <div class="detail-field"><strong>Aktion</strong><span><button id="csvExport" type="button">CSV Export</button></span></div>
            </div>
          </section>
        </section>
      </main>
    </div>
  </div>
  <script>
    const records = {data};
    const summary = {summary_data};
    const topics = {topics_data};
    const parkingGarages = {parking_data};
    const officialRoadworks = {roadworks_data};
    const mobilitySources = {mobility_data};
    const byId = (id) => document.getElementById(id);
    const search = byId('search');
    const yearFilter = byId('yearFilter');
    const dateFilter = byId('dateFilter');
    const typeFilter = byId('typeFilter');
    const statusFilter = byId('statusFilter');
    const categoryFilter = byId('categoryFilter');
    const sourceFilter = byId('sourceFilter');
    const amountFilter = byId('amountFilter');
    const fileFilter = byId('fileFilter');
    const sectionFilter = byId('sectionFilter');
    const csvExport = byId('csvExport');
    const tableWrap = byId('tableWrap');
    const detailWrap = byId('detailWrap');
    const mapStatus = byId('mapStatus');
    const mapProgress = byId('mapProgress');
    const mapProgressBar = byId('mapProgressBar');
    const mapLegend = byId('mapLegend');
    const mapPlaces = byId('mapPlaces');
    const roadworksStatus = byId('roadworksStatus');
    const roadworksList = byId('roadworksList');
    const roadworkLocation = byId('roadworkLocation');
    const roadworkKind = byId('roadworkKind');
    const roadworkStart = byId('roadworkStart');
    const roadworkEnd = byId('roadworkEnd');
    const roadworkDescription = byId('roadworkDescription');
    const roadworkResult = byId('roadworkResult');
    const roadworkCheck = byId('roadworkCheck');
    const parkingStatus = byId('parkingStatus');
    const parkingList = byId('parkingList');
    const topicFilterNotice = byId('topicFilterNotice');
    const topicFilterText = byId('topicFilterText');
    const clearTopicFilter = byId('clearTopicFilter');
    const exportCount = byId('exportCount');
    const digraMatchedCount = byId('digraMatchedCount');
    const digraFallbackCount = byId('digraFallbackCount');
    const cityLinkCount = byId('cityLinkCount');
    const digraMissingCount = byId('digraMissingCount');
    let sichtbareEintraege = [];
    let ausgewaehlterEintrag = null;
    let grazMap = null;
    let markerLayer = null;
    let roadworksMap = null;
    let roadworksLayer = null;
    let parkingMap = null;
    let parkingLayer = null;
    const markersByLocation = new Map();
    const markerCacheByLocation = new Map();
    const coordsByLocation = new Map();
    const geocodePromisesByLocation = new Map();
    let highlightedLocations = new Set();
    let currentLocationIndex = buildLocationIndex(records);
    const categoryColors = {{
      'Bauen & Stadtplanung': '#7c3aed',
      'Verkehr & Mobilität': '#2563eb',
      'Kanal, Wasser & Infrastruktur': '#0891b2',
      'Budget & Förderungen': '#ca8a04',
      'Beteiligungen & Unternehmen': '#475569',
      'Verwaltung & Recht': '#64748b',
      'Bildung & Jugend': '#db2777',
      'Soziales & Gesundheit': '#dc2626',
      'Umwelt, Klima & Energie': '#16a34a',
      'Kultur, Sport & Veranstaltungen': '#9333ea',
      'Wohnen & Gebäude': '#ea580c',
      'Sicherheit & Ordnung': '#b91c1c',
      'Sonstiges': '#6b7280'
    }};
    let activeTabName = 'search';
    let lastMarkerLocationKey = '';
    let markerLoadRun = 0;
    let lastMapPlacesKey = '';
    let activeTopicRecordIds = null;
    let activeTopicLabel = '';
    let currentParkingGarages = [];
    let currentRoadworks = [];
    const parkingFallbackGarages = [
      {{ name: 'TG Operngarage', address: 'Opernring Hamerlinggasse, Graz', kind: 'Tiefgarage', lat: 47.0672, lon: 15.4451, spaces: 411, availability: 'unbekannt', source: 'Stadt Graz Garagenliste', source_url: 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html', license: 'Webseite, Weiterverwendung prüfen' }},
      {{ name: 'TG Kastner&Öhler', address: 'Kaiser-Franz-Josef-Kai 8, Graz', kind: 'Tiefgarage', lat: 47.0717, lon: 15.4359, spaces: 600, availability: 'unbekannt', source: 'Stadt Graz Garagenliste', source_url: 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html', license: 'Webseite, Weiterverwendung prüfen' }},
      {{ name: 'PH LKH', address: 'Stiftingtalstraße 30, Graz', kind: 'Parkhaus', lat: 47.081341, lon: 15.468616, spaces: 401, availability: 'unbekannt', source: 'Parkgaragen Graz OGD / Stadt Graz', source_url: 'https://www.data.gv.at/katalog/dataset/92183c55-442b-405d-9046-d19b07ffc83a', license: 'CC BY 4.0' }},
      {{ name: 'TG Annenpassage', address: 'Bahnhofgürtel 89, Graz', kind: 'Tiefgarage', lat: 47.0717, lon: 15.4188, spaces: 389, availability: 'unbekannt', source: 'Stadt Graz Garagenliste', source_url: 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html', license: 'Webseite, Weiterverwendung prüfen' }},
      {{ name: 'TG Bahnhof', address: 'Europaplatz 12, Graz', kind: 'Tiefgarage', lat: 47.0723, lon: 15.4178, spaces: 368, availability: 'unbekannt', source: 'Stadt Graz Garagenliste', source_url: 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html', license: 'Webseite, Weiterverwendung prüfen' }},
      {{ name: 'TG Stadion Liebenau', address: 'Stadionplatz 1, Graz', kind: 'Tiefgarage', lat: 47.0462, lon: 15.4546, spaces: 650, availability: 'unbekannt', source: 'Stadt Graz Garagenliste', source_url: 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html', license: 'Webseite, Weiterverwendung prüfen' }},
      {{ name: 'TG Brauquartier', address: 'Brauquartier, Graz', kind: 'Tiefgarage', lat: 47.0397, lon: 15.4119, spaces: 461, availability: 'unbekannt', source: 'Stadt Graz Garagenliste', source_url: 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html', license: 'Webseite, Weiterverwendung prüfen' }},
      {{ name: 'TG Gate17', address: 'Triester Straße 432, Graz', kind: 'Tiefgarage', lat: 47.0155, lon: 15.4118, spaces: 228, availability: 'unbekannt', source: 'Stadt Graz Garagenliste', source_url: 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html', license: 'Webseite, Weiterverwendung prüfen' }}
    ];

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

    function fillDatalist(id, values, limit = 900) {{
      const list = byId(id);
      if (!list) return;
      list.innerHTML = [...new Set(values.filter(Boolean))]
        .sort((a, b) => String(a).localeCompare(String(b), 'de-AT'))
        .slice(0, limit)
        .map((value) => `<option value="${{escapeHtml(value)}}"></option>`)
        .join('');
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
        record.kategorie,
        record.einbringer,
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

    function primaryCategoryForLocation(locationRecords) {{
      const counts = new Map();
      (locationRecords || []).forEach((record) => {{
        const category = record.kategorie || 'Sonstiges';
        counts.set(category, (counts.get(category) || 0) + 1);
      }});
      return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'de-AT'))[0]?.[0] || 'Sonstiges';
    }}

    function categoryColor(category) {{
      return categoryColors[category] || categoryColors.Sonstiges;
    }}

    function renderMapLegend() {{
      if (!mapLegend) return;
      const categories = [...new Set(sichtbareEintraege.map((record) => record.kategorie || 'Sonstiges'))]
        .sort((a, b) => a.localeCompare(b, 'de-AT'));
      mapLegend.innerHTML = categories.map((category) => `
        <button class="legend-item${{categoryFilter.value === category ? ' is-active' : ''}}" type="button" data-map-category="${{escapeHtml(category)}}" style="--category-color: ${{categoryColor(category)}}">
          <span class="legend-swatch"></span>${{escapeHtml(category)}}
        </button>
      `).join('');
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
      if (focusMap && (record.orte || []).length) {{
        focusRecordLocations(record);
      }} else {{
        activateTab('search');
      }}
    }}

    function activateTab(target) {{
      activeTabName = target;
      document.querySelectorAll('[data-nav]').forEach((item) => {{
        item.classList.toggle('active', item.dataset.nav === target);
      }});
      document.querySelectorAll('.tab-panel').forEach((panel) => {{
        panel.classList.toggle('active', panel.id === `${{target}}Panel`);
      }});
      if (target === 'map' && grazMap) {{
        setTimeout(() => {{
          grazMap.invalidateSize();
          refreshMapMarkersIfNeeded();
          if (ausgewaehlterEintrag) focusRecordLocations(ausgewaehlterEintrag, false);
        }}, 80);
      }}
      if (target === 'roadworks') {{
        setTimeout(() => {{
          initRoadworksMap();
          roadworksMap?.invalidateSize();
        }}, 80);
      }}
      if (target === 'parking') {{
        setTimeout(() => {{
          initParkingMap();
          parkingMap?.invalidateSize();
        }}, 80);
      }}
    }}

    function initMap() {{
      if (!window.L) {{
        mapStatus.textContent = 'Kartenbibliothek konnte nicht geladen werden.';
        return;
      }}
      grazMap = L.map('grazMap').setView([47.0707, 15.4395], 12);
      addBaseLayer(grazMap);
      markerLayer = L.layerGroup().addTo(grazMap);
      renderMapPlaces();
      refreshMapMarkersIfNeeded();
    }}

    function addBaseLayer(map) {{
      L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap'
      }}).addTo(map);
    }}

    function initParkingMap() {{
      if (!window.L || parkingMap) return;
      parkingMap = L.map('parkingMap').setView([47.0707, 15.4395], 12);
      addBaseLayer(parkingMap);
      parkingLayer = L.layerGroup().addTo(parkingMap);
      renderParkingGarages();
    }}

    function initRoadworksMap() {{
      if (!window.L || roadworksMap) return;
      roadworksMap = L.map('roadworksMap').setView([47.0707, 15.4395], 12);
      addBaseLayer(roadworksMap);
      roadworksLayer = L.layerGroup().addTo(roadworksMap);
      renderRoadworksSourceNote();
      renderRoadworkContext();
    }}

    async function renderParkingGarages() {{
      if (!parkingLayer) return;
      parkingLayer.clearLayers();
      const sourceGarages = parkingGarages.length ? parkingGarages : parkingFallbackGarages;
      currentParkingGarages = sourceGarages;
      const usable = sourceGarages.map((garage, index) => ({{ ...garage, _index: index }}));
      parkingStatus.textContent = `${{usable.length}} Garagen/Parkhäuser · Verfügbarkeit unbekannt`;
      parkingList.innerHTML = usable.length ? usable.map((garage) => `
        <button class="map-place" type="button" data-parking-index="${{garage._index}}">
          <strong>${{escapeHtml(garage.name)}}</strong>
          <span>${{escapeHtml(garage.kind || 'Parkgarage')}} · ${{garage.spaces ? `${{garage.spaces}} Plätze · ` : ''}}verfügbar: unbekannt</span>
          <small>${{escapeHtml(garage.address || '')}}</small>
        </button>
      `).join('') : '<div class="empty">Keine Parkgaragen geladen. Prüfe den OGD-Cache oder die Netzwerkverbindung.</div>';
      let drawn = 0;
      for (const garage of usable) {{
        let coords = Number.isFinite(garage.lat) && Number.isFinite(garage.lon)
          ? {{ lat: garage.lat, lon: garage.lon }}
          : await geocodeLocation(garage.address || garage.name);
        if (!coords) continue;
        drawn += 1;
        const marker = L.circleMarker([coords.lat, coords.lon], {{
          radius: 7,
          color: '#0f766e',
          fillColor: '#14b8a6',
          fillOpacity: 0.82,
          weight: 2,
        }}).addTo(parkingLayer);
        marker.bindPopup(`
          <strong>${{escapeHtml(garage.name)}}</strong>
          <div>${{escapeHtml(garage.kind || 'Parkgarage')}}</div>
          <div>${{escapeHtml(garage.address || '')}}</div>
          <div>${{garage.spaces ? `${{escapeHtml(garage.spaces)}} Plätze` : ''}}</div>
          <div>Verfügbarkeit: unbekannt</div>
          <div>Quelle: ${{escapeHtml(garage.source || '')}} · ${{escapeHtml(garage.license || '')}}</div>
        `);
        marker.on('click', () => highlightParkingList(garage._index));
        if (drawn % 15 === 0) await nextFrame();
      }}
      parkingStatus.textContent = `${{drawn}}/${{usable.length}} Standorte · Verfügbarkeit unbekannt`;
      renderParkingSourceNote();
    }}

    function highlightParkingList(index) {{
      parkingList.querySelectorAll('[data-parking-index]').forEach((item) => {{
        item.classList.toggle('active', item.dataset.parkingIndex === String(index));
      }});
    }}

    function renderParkingSourceNote() {{
      const source = mobilitySources.parking || {{}};
      byId('parkingSourceNote').innerHTML = `
        Quelle: ${{externalLink(source.dataset_url || '', 'Parkgaragen Graz / data.gv.at')}} ·
        Lizenz: ${{escapeHtml(source.license || 'unbekannt')}} ·
        Namensnennung: ${{escapeHtml(source.attribution || '-') }}.
        Live-Verfügbarkeit wird nicht übernommen, weil keine offene Live-API mit klarer Weiterverwendungsfreigabe gefunden wurde.
      `;
    }}

    function renderRoadworksSourceNote() {{
      const source = mobilitySources.roadworks || {{}};
      byId('roadworksSourceNote').innerHTML = `
        Offizielle Info: ${{externalLink(source.info_url || '', 'Baustelleninformation Graz')}} ·
        Straßenamt: ${{externalLink(source.office_url || '', 'Baustellen & temporäre Nutzungen')}}.
        Geladene Baustellen: ${{escapeHtml(source.records ?? officialRoadworks.length)}}.
        Hinweis: ${{escapeHtml(source.note || '')}}
      `;
    }}

    async function renderRoadworkContext() {{
      if (!roadworksLayer) return;
      roadworksLayer.clearLayers();
      const roadworks = officialRoadworks
        .map((roadwork, index) => ({{ ...roadwork, _index: index }}))
        .filter((roadwork) => roadwork.location || roadwork.title);
      currentRoadworks = roadworks;
      roadworksStatus.textContent = `${{roadworks.length}} offizielle Baustelleninfos geladen`;
      roadworksList.innerHTML = roadworks.length ? roadworks.map((roadwork) => `
        <button class="map-place" type="button" data-roadwork-index="${{roadwork._index}}">
          <strong>${{escapeHtml(roadwork.title || roadwork.location)}}</strong>
          <span>${{escapeHtml(roadwork.period || 'Zeitraum nicht angegeben')}}</span>
          <small>${{escapeHtml([roadwork.description, roadwork.project].filter(Boolean).join(' · '))}}</small>
        </button>
      `).join('') : '<div class="empty">Keine offiziellen Baustelleninfos geladen. Prüfe den lokalen Cache oder die Verbindung zu graz.at.</div>';
      let drawn = 0;
      for (const roadwork of roadworks) {{
        const location = roadwork.location || roadwork.title;
        const coords = await geocodeLocation(location);
        if (!coords) continue;
        drawn += 1;
        const marker = L.circleMarker([coords.lat, coords.lon], {{
          radius: 7,
          color: '#92400e',
          fillColor: '#f59e0b',
          fillOpacity: 0.82,
          weight: 2,
        }}).addTo(roadworksLayer);
        marker.bindPopup(`
          <strong>${{escapeHtml(roadwork.title || location)}}</strong>
          <div>${{escapeHtml(roadwork.period || 'Zeitraum nicht angegeben')}}</div>
          <div>${{escapeHtml(roadwork.description || '')}}</div>
          <div>${{escapeHtml(roadwork.project || '')}}</div>
          <div>Quelle: ${{externalLink(roadwork.source_url || (mobilitySources.roadworks || {{}}).office_url || '', roadwork.source || 'Stadt Graz')}}</div>
        `);
        marker.on('click', () => highlightRoadworkList(roadwork._index));
        if (drawn % 10 === 0) {{
          roadworksStatus.textContent = `${{drawn}}/${{roadworks.length}} Baustellen eingezeichnet`;
          await nextFrame();
        }}
      }}
      roadworksStatus.textContent = `${{drawn}}/${{roadworks.length}} Baustellen eingezeichnet`;
    }}

    function highlightRoadworkList(index) {{
      roadworksList.querySelectorAll('[data-roadwork-index]').forEach((item) => {{
        item.classList.toggle('active', item.dataset.roadworkIndex === String(index));
      }});
    }}

    async function checkRoadworkPlan() {{
      const location = roadworkLocation.value.trim();
      if (!location) {{
        roadworkResult.textContent = 'Bitte zuerst eine Straße oder einen Ort eingeben.';
        return;
      }}
      initRoadworksMap();
      const coords = await geocodeLocation(location);
      const nearby = findNearbyRoadworks(location);
      const hasFullClosure = roadworkKind.value === 'Totalsperre';
      const timeText = [roadworkStart.value, roadworkEnd.value].filter(Boolean).join(' bis ') || 'Zeitraum nicht gesetzt';
      const risk = hasFullClosure && nearby.length ? 'kritisch' : nearby.length >= 3 ? 'prüfen' : 'voraussichtlich möglich';
      roadworkResult.innerHTML = `
        <strong>${{escapeHtml(risk)}}</strong><br>
        ${{escapeHtml(roadworkKind.value)}} bei ${{escapeHtml(location)}} · ${{escapeHtml(timeText)}}<br>
        ${{nearby.length ? `${{nearby.length}} offizielle Baustelleninfos im Umfeld gefunden. Prüfe, ob Sperren, Umleitungen oder Bauzeiten zusammengelegt werden können.` : 'Keine nahen offiziellen Baustelleninfos in den geladenen Daten gefunden.'}}
      `;
      if (coords && roadworksLayer && roadworksMap) {{
        roadworksLayer.clearLayers();
        const marker = L.circleMarker([coords.lat, coords.lon], {{
          radius: 9,
          color: hasFullClosure ? '#b91c1c' : '#ca8a04',
          fillColor: hasFullClosure ? '#ef4444' : '#facc15',
          fillOpacity: 0.86,
          weight: 3,
        }}).addTo(roadworksLayer);
        marker.bindPopup(`
          <strong>${{escapeHtml(location)}}</strong>
          <div>${{escapeHtml(roadworkKind.value)}} · ${{escapeHtml(timeText)}}</div>
          <div>${{escapeHtml(roadworkDescription.value || 'Keine Beschreibung')}}</div>
          <div>Bewertung: ${{escapeHtml(risk)}}</div>
        `).openPopup();
        roadworksMap.setView([coords.lat, coords.lon], 15);
        nearby.forEach((roadwork) => {{
          geocodeLocation(roadwork.location || roadwork.title).then((nearCoords) => {{
            if (!nearCoords || !roadworksLayer) return;
            L.circleMarker([nearCoords.lat, nearCoords.lon], {{
              radius: 7,
              color: '#92400e',
              fillColor: '#f59e0b',
              fillOpacity: 0.72,
              weight: 2,
            }}).bindPopup(`
              <strong>${{escapeHtml(roadwork.title || roadwork.location)}}</strong>
              <div>${{escapeHtml(roadwork.period || 'Zeitraum nicht angegeben')}}</div>
              <div>${{escapeHtml(roadwork.description || '')}}</div>
            `).addTo(roadworksLayer);
          }});
        }});
      }}
      roadworksList.innerHTML = nearby.length ? nearby.map((roadwork) => `
        <button class="map-place" type="button" data-roadwork-index="${{roadwork._index}}">
          <strong>${{escapeHtml(roadwork.title || roadwork.location)}}</strong>
          <span>${{escapeHtml(roadwork.period || 'Zeitraum nicht angegeben')}}</span>
          <small>${{escapeHtml([roadwork.description, roadwork.project].filter(Boolean).join(' · '))}}</small>
        </button>
      `).join('') : '<div class="empty">Keine Konfliktkandidaten gefunden.</div>';
    }}

    function findNearbyRoadworks(location) {{
      const query = location.toLocaleLowerCase('de-AT');
      const tokens = query.split(/\\s+/).filter((token) => token.length >= 4);
      return currentRoadworks.filter((roadwork) => {{
        const haystack = [roadwork.location, roadwork.title, roadwork.description, roadwork.project]
          .join(' ')
          .toLocaleLowerCase('de-AT');
        return haystack.includes(query) || tokens.some((token) => haystack.includes(token));
      }}).slice(0, 30);
    }}

    function renderMapPlaces() {{
      if (activeTabName !== 'map') return;
      const placeKey = [...currentLocationIndex.keys()].sort().join('|');
      if (placeKey === lastMapPlacesKey) return;
      lastMapPlacesKey = placeKey;
      const places = [...currentLocationIndex.entries()]
        .map(([location, locationRecords]) => ({{
          location,
          count: locationRecords.length,
          types: [...new Set(locationRecords.map((record) => record.typ).filter(Boolean))].join(', '),
          category: primaryCategoryForLocation(locationRecords)
        }}))
        .sort((a, b) => b.count - a.count || a.location.localeCompare(b.location, 'de-AT'));
      if (!places.length) {{
        mapPlaces.innerHTML = '<div class="empty">Keine Orte erkannt.</div>';
        return;
      }}
      mapPlaces.innerHTML = places.map((place) => `
        <button class="map-place" type="button" data-location="${{escapeHtml(place.location)}}">
          <strong>${{escapeHtml(place.location)}}</strong>
          <span>${{place.count}} Eintrag${{place.count === 1 ? '' : 'e'}} · ${{escapeHtml(place.category)}}</span>
          <small>${{escapeHtml(place.types)}}</small>
        </button>
      `).join('');
    }}

    async function loadVisibleMapMarkers() {{
      if (!markerLayer) return;
      const markerLocationKey = [...currentLocationIndex.keys()].sort().join('|');
      if (markerLocationKey === lastMarkerLocationKey) return;
      lastMarkerLocationKey = markerLocationKey;
      const runId = ++markerLoadRun;
      markerLayer.clearLayers();
      markersByLocation.clear();
      const places = [...currentLocationIndex.keys()];
      if (!places.length) {{
        mapStatus.textContent = 'Keine Orte für diese Filter.';
        updateMapProgress(0, 0, false);
        return;
      }}
      let loaded = 0;
      let fromCache = 0;
      const missingPlaces = [];
      mapStatus.textContent = `0/${{places.length}} Orte auf der Karte`;
      updateMapProgress(0, places.length, true);
      for (const [index, place] of places.entries()) {{
        if (runId !== markerLoadRun) return;
        const cachedCoords = cachedCoordsForLocation(place);
        if (cachedCoords) {{
          loaded += 1;
          fromCache += 1;
          addLocationMarker(place, cachedCoords);
          if ((index + 1) % 50 === 0) await nextFrame();
          continue;
        }}
        missingPlaces.push(place);
      }}
      if (fromCache) {{
        mapStatus.textContent = `${{fromCache}}/${{places.length}} Orte aus Cache`;
        updateMapProgress(loaded, places.length, Boolean(missingPlaces.length));
        updateMarkerHighlights();
        await nextFrame();
      }}
      if (!missingPlaces.length) {{
        if (runId === markerLoadRun) {{
          updateMarkerHighlights();
          mapStatus.textContent = `${{markersByLocation.size}}/${{places.length}} Orte auf der Karte`;
          updateMapProgress(places.length, places.length, false);
        }}
        return;
      }}
      for (const place of missingPlaces) {{
        if (runId !== markerLoadRun) return;
        const coords = await geocodeLocation(place);
        if (runId !== markerLoadRun) return;
        loaded += 1;
        if (coords) {{
          addLocationMarker(place, coords);
        }}
        mapStatus.textContent = `${{loaded}}/${{places.length}} Orte geprüft`;
        updateMapProgress(loaded, places.length, loaded < places.length);
        if (loaded % 25 === 0) {{
          updateMarkerHighlights();
          await nextFrame();
        }}
      }}
      if (runId === markerLoadRun) {{
        updateMarkerHighlights();
        mapStatus.textContent = `${{markersByLocation.size}}/${{places.length}} Orte auf der Karte`;
        updateMapProgress(places.length, places.length, false);
      }}
    }}

    function nextFrame() {{
      return new Promise((resolve) => requestAnimationFrame(resolve));
    }}

    function updateMapProgress(done, total, active) {{
      if (!mapProgress || !mapProgressBar) return;
      const percent = total > 0 ? Math.round((done / total) * 100) : 0;
      mapProgress.classList.toggle('is-active', Boolean(active && total > 0));
      mapProgressBar.style.width = `${{Math.max(0, Math.min(100, percent))}}%`;
    }}

    function refreshMapMarkersIfNeeded() {{
      if (activeTabName !== 'map') {{
        mapStatus.textContent = 'Karte wird beim Öffnen aktualisiert.';
        return;
      }}
      renderMapPlaces();
      loadVisibleMapMarkers();
    }}

    function locationCacheKey(location) {{
      return `graz-location:${{location}}`;
    }}

    function cachedCoordsForLocation(location) {{
      if (coordsByLocation.has(location)) {{
        return coordsByLocation.get(location);
      }}
      const cacheKey = locationCacheKey(location);
      const cached = localStorage.getItem(cacheKey);
      if (!cached) return null;
      try {{
        const coords = JSON.parse(cached);
        if (!Number.isFinite(coords?.lat) || !Number.isFinite(coords?.lon)) {{
          localStorage.removeItem(cacheKey);
          return null;
        }}
        coordsByLocation.set(location, coords);
        return coords;
      }} catch {{
        localStorage.removeItem(cacheKey);
        return null;
      }}
    }}

    async function geocodeLocation(location) {{
      const cachedCoords = cachedCoordsForLocation(location);
      if (cachedCoords) return cachedCoords;
      if (geocodePromisesByLocation.has(location)) {{
        return geocodePromisesByLocation.get(location);
      }}
      const url = `https://nominatim.openstreetmap.org/search?format=json&limit=1&countrycodes=at&q=${{encodeURIComponent(location + ', Graz, Österreich')}}`;
      const promise = (async () => {{
        const response = await fetch(url);
        if (!response.ok) return null;
        const results = await response.json();
        const first = results[0];
        if (!first) return null;
        const coords = {{ lat: Number(first.lat), lon: Number(first.lon) }};
        if (!Number.isFinite(coords.lat) || !Number.isFinite(coords.lon)) return null;
        localStorage.setItem(locationCacheKey(location), JSON.stringify(coords));
        coordsByLocation.set(location, coords);
        await new Promise((resolve) => setTimeout(resolve, 250));
        return coords;
      }})();
      geocodePromisesByLocation.set(location, promise);
      try {{
        return await promise;
      }} catch {{
        mapStatus.textContent = 'Online-Geocoding nicht verfügbar.';
        return null;
      }} finally {{
        geocodePromisesByLocation.delete(location);
      }}
    }}

    function addLocationMarker(location, coords) {{
      if (!grazMap || !markerLayer || markersByLocation.has(location)) return;
      const locationRecords = currentLocationIndex.get(location) || [];
      const popupRecords = locationRecords.slice(0, 6).map((record) => `
        <button type="button" data-popup-record-id="${{escapeHtml(record.record_id)}}">${{escapeHtml(record.typ)}} · ${{escapeHtml(record.datum)}} · ${{escapeHtml(record.titel)}}</button>
      `).join('');
      const typeSummary = [...new Set(locationRecords.map((record) => record.typ).filter(Boolean))].join(', ');
      const category = primaryCategoryForLocation(locationRecords);
      const color = categoryColor(category);
      const popupHtml = `
        <strong>${{escapeHtml(location)}}</strong>
        <div>${{escapeHtml(category)}}</div>
        <div>${{escapeHtml(typeSummary)}}</div>
        <div class="popup-list">${{popupRecords}}</div>
      `;
      let marker = markerCacheByLocation.get(location);
      if (!marker) {{
        marker = L.circleMarker([coords.lat, coords.lon], {{
          radius: Math.min(11, 5 + Math.sqrt(locationRecords.length)),
          color,
          weight: 2,
          fillColor: color,
          fillOpacity: 0.78,
          className: 'place-dot'
        }});
        markerCacheByLocation.set(location, marker);
      }}
      marker.setRadius(Math.min(11, 5 + Math.sqrt(locationRecords.length)));
      marker.setStyle(markerStyle(location, highlightedLocations.has(location)));
      marker.bindPopup(popupHtml);
      if (!markerLayer.hasLayer(marker)) marker.addTo(markerLayer);
      markersByLocation.set(location, marker);
      applyMarkerHighlight(location, marker);
    }}

    function markerStyle(location, isHighlighted) {{
      const category = primaryCategoryForLocation(currentLocationIndex.get(location) || []);
      const color = categoryColor(category);
      return isHighlighted
        ? {{ color: '#047857', fillColor: '#10b981', fillOpacity: 0.9, weight: 3, className: 'place-dot related-place' }}
        : {{ color, fillColor: color, fillOpacity: 0.78, weight: 2, className: 'place-dot' }};
    }}

    function applyMarkerHighlight(location, marker) {{
      if (!marker?.setStyle) return;
      marker.setStyle(markerStyle(location, highlightedLocations.has(location)));
    }}

    function updateMarkerHighlights() {{
      markersByLocation.forEach((marker, location) => applyMarkerHighlight(location, marker));
    }}

    async function focusLocation(location) {{
      const coords = await geocodeLocation(location);
      if (!coords || !grazMap) return;
      addLocationMarker(location, coords);
      const marker = markersByLocation.get(location);
      grazMap.setView([coords.lat, coords.lon], 16);
      if (marker) marker.openPopup();
      activateTab('map');
    }}

    async function focusRecordLocations(record, switchTab = true) {{
      if (!record || !grazMap) return;
      const locations = [...new Set((record.orte || []).filter(Boolean).filter(mappableLocation))];
      if (!locations.length) return;
      if (switchTab) activateTab('map');
      highlightedLocations = new Set(locations);
      updateMarkerHighlights();
      const points = [];
      for (const [index, location] of locations.entries()) {{
        const coords = await geocodeLocation(location);
        if (!coords) continue;
        addLocationMarker(location, coords);
        applyMarkerHighlight(location, markersByLocation.get(location));
        points.push([coords.lat, coords.lon]);
        if ((index + 1) % 10 === 0) await nextFrame();
      }}
      if (!points.length) return;
      if (points.length > 1) {{
        grazMap.fitBounds(points, {{ padding: [44, 44], maxZoom: 15 }});
      }} else {{
        grazMap.setView(points[0], 16);
      }}
      const firstMarker = markersByLocation.get(locations[0]);
      if (firstMarker) firstMarker.openPopup();
    }}

    function detailField(label, value) {{
      return `<div class="detail-field"><strong>${{escapeHtml(label)}}</strong><span>${{escapeHtml(value || '-')}}</span></div>`;
    }}

    function digraLink(url, text = 'DIGRA öffnen') {{
      const value = String(url || '');
      if (!value.startsWith('https://digra.graz.at/')) {{
        return '-';
      }}
      return `<a href="${{escapeHtml(value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(text)}}</a> <span class="source-url">${{escapeHtml(value)}}</span>`;
    }}

    function externalLink(url, text) {{
      const value = String(url || '');
      if (!value.startsWith('https://')) return '-';
      return `<a href="${{escapeHtml(value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(text)}}</a>`;
    }}

    function detailLinkField(label, url) {{
      return `<div class="detail-field"><strong>${{escapeHtml(label)}}</strong><span>${{digraLink(url)}}</span></div>`;
    }}

    function detailHtmlField(label, htmlValue) {{
      return `<div class="detail-field"><strong>${{escapeHtml(label)}}</strong><span>${{htmlValue || '-'}}</span></div>`;
    }}

    function summaryBlocks(record) {{
      const blocks = [];
      if (record.ki_zusammenfassung) {{
        blocks.push(`
          <div class="summary-block">
            <button class="summary-toggle" type="button" data-summary-kind="summary" aria-expanded="false">KI-Zusammenfassung</button>
            <div class="summary-text" hidden></div>
          </div>
        `);
      }}
      if (record.ki_einfache_sprache) {{
        blocks.push(`
          <div class="summary-block">
            <button class="summary-toggle" type="button" data-summary-kind="easy" aria-expanded="false">Einfache Sprache</button>
            <div class="summary-text" hidden></div>
          </div>
        `);
      }}
      return blocks.length ? `<div class="summary-blocks">${{blocks.join('')}}</div>` : '';
    }}

    function summaryDisplayText(record, kind) {{
      const text = kind === 'easy'
        ? (record?.ki_einfache_sprache || '')
        : (record?.ki_zusammenfassung || '');
      const needsContext = record?.einbringer && ['Schriftlicher Antrag', 'Schriftliche Anfrage', 'Dringlichkeitsantrag'].includes(record?.typ);
      if (!needsContext) return text;
      const lead = kind === 'easy'
        ? `Das ist die Sicht oder Forderung von ${{record.einbringer}}.`
        : `Einordnung: ${{record.einbringer}} bringt diesen Punkt ein; die Zusammenfassung beschreibt daher Antrag, Anfrage oder Forderung dieser Einbringung.`;
      return `${{lead}}\n\n${{text}}`;
    }}

    function csvCell(value) {{
      return `"${{String(value ?? '').replace(/"/g, '""')}}"`;
    }}

    function exportCsv() {{
      const headers = ['Datum', 'Typ', 'Abschnitt', 'Stück', 'Status', 'Thema', 'Einbringer', 'Ergebnisquelle', 'Geschäftszahlen', 'Titel', 'Ergebnis', 'Beträge', 'Orte', 'DIGRA-Einlagezahl', 'DIGRA-Link', 'Quelldatei'];
      const rows = sichtbareEintraege.map((record) => [
        record.datum,
        record.typ,
        record.abschnitt,
        record.stueck_nr,
        record.status,
        record.kategorie,
        record.einbringer,
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
          ${{detailField('Thema', record.kategorie)}}
          ${{detailField('Einbringer', record.einbringer)}}
          ${{detailField('Stück', record.stueck_nr)}}
          ${{detailField('Status', record.status)}}
          ${{detailField('Geschäftszahlen', joinList(record.geschaeftszahlen))}}
          ${{detailField('Ergebnisquelle', record.ergebnisquelle)}}
          ${{detailField('Ergebnis', record.ergebnis)}}
          ${{detailField('DIGRA-Einlagezahl', record.digra_einlagezahl)}}
          ${{detailField('DIGRA-Trefferwert', record.digra_trefferwert)}}
          ${{detailLinkField('DIGRA-Link', record.digra_url)}}
          ${{detailHtmlField('Stadt-Graz-Link', externalLink(record.source_url, 'Quelle öffnen'))}}
          ${{detailField('Beträge', joinList(record.betraege))}}
          ${{detailHtmlField('Orte', locationLinks(record.orte))}}
          ${{detailField('Quelldatei', record.quell_datei)}}
        </div>
        ${{summaryBlocks(record)}}
      `;
    }}

    function topicRecordMatchesFilters(record) {{
      const meetingDate = String(record.meeting_date || '');
      if (dateFilter.value && meetingDate !== dateFilter.value) return false;
      if (yearFilter.value && !meetingDate.startsWith(yearFilter.value + '-')) return false;
      const query = search.value.trim().toLocaleLowerCase('de-AT');
      if (!query) return true;
      const haystack = [
        record.title,
        record.business_number,
        ...(record.business_numbers || []),
        record.result_text,
        record.result_source,
        record.record_id,
      ].join(' ').toLocaleLowerCase('de-AT');
      return haystack.includes(query);
    }}

    function renderTopics() {{
      if (!topics.length) {{
        byId('topicsWrap').style.display = 'none';
        return;
      }}
      const visibleTopics = topics.map((topic) => ({{
        ...topic,
        visibleRecords: (topic.records || []).filter(topicRecordMatchesFilters),
      }})).filter((topic) => topic.visibleRecords.length >= 2);

      if (!visibleTopics.length) {{
        byId('topicsWrap').style.display = '';
        byId('topicsWrap').innerHTML = '<h2>Themenverläufe</h2><div class="empty">Keine Themen für diese Filter.</div>';
        return;
      }}

      const rendered = visibleTopics.slice(0, 8).map((topic) => {{
        const timeline = topic.visibleRecords.slice(0, 6).map((record) => `
          <button class="timeline-step" type="button" data-record-id="${{escapeHtml(record.record_id || '')}}">
            <span class="timeline-date">${{escapeHtml(record.meeting_date || '-')}}</span>
            <span class="timeline-title">${{escapeHtml(record.title || '-')}}</span>
            <span class="timeline-result">Abstimmung: ${{escapeHtml(record.result_text || 'kein Ergebnis')}} ${{record.result_source ? `(${{escapeHtml(record.result_source)}})` : ''}}</span>
          </button>
        `).join('');
        const topicDates = [...new Set(topic.visibleRecords.map((record) => record.meeting_date).filter(Boolean))].sort();
        const news = (topic.news || []).slice(0, 3).map((item) => `
          <a href="${{escapeHtml(item.url || '')}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(item.title || '')}}</a>
        `).join('');
        const aiInfo = topic.ai_reason ? `<div class="topic-meta">KI-Hinweis: ${{escapeHtml(topic.ai_reason)}}</div>` : '';
        const statusInfo = topic.latest_result ? `<div class="topic-meta">Letzter Stand: ${{escapeHtml(topic.latest_result)}}${{topic.latest_date ? ` am ${{escapeHtml(topic.latest_date)}}` : ''}}</div>` : '';
        return `
          <article class="topic">
            <div class="topic-head">
              <span class="topic-label">
                <span>${{escapeHtml(topic.label || 'Thema')}}</span>
              </span>
              <span class="badge">${{escapeHtml(topic.confidence || '')}}</span>
            </div>
            <div class="topic-meta">
              Zeitstrahl: ${{escapeHtml(topicDates.join(' bis '))}}
              ${{topic.business_number ? ` · Geschäftszahl: ${{escapeHtml(topic.business_number)}}` : ''}}
            </div>
            ${{aiInfo}}
            ${{statusInfo}}
            <div class="timeline">${{timeline}}</div>
            ${{news ? `<div class="topic-meta">Aktuelle Hinweise: ${{news}}</div>` : ''}}
            <button class="topic-action" type="button" data-topic-id="${{escapeHtml(topic.topic_id || '')}}">Einträge dazu filtern</button>
          </article>
        `;
      }}).join('');
      byId('topicsWrap').innerHTML = `<h2>Themenverläufe</h2><div class="topic-list">${{rendered}}</div>`;
    }}

    function filteredRecords() {{
      const query = search.value.trim().toLocaleLowerCase('de-AT');
      return records.filter((record) => {{
        if (activeTopicRecordIds && !activeTopicRecordIds.has(record.record_id)) return false;
        if (dateFilter.value && record.datum !== dateFilter.value) return false;
        if (yearFilter.value && !String(record.datum || '').startsWith(yearFilter.value + '-')) return false;
        if (typeFilter.value && record.typ !== typeFilter.value) return false;
        if (statusFilter.value && record.status_filter !== statusFilter.value) return false;
        if (categoryFilter.value && record.kategorie !== categoryFilter.value) return false;
        if (sourceFilter.value && record.ergebnisquelle !== sourceFilter.value) return false;
        if (amountFilter.value === 'mit' && !(record.betraege || []).length) return false;
        if (amountFilter.value === 'ohne' && (record.betraege || []).length) return false;
        if (fileFilter.value && record.quell_datei !== fileFilter.value) return false;
        if (sectionFilter.value && record.abschnitt !== sectionFilter.value) return false;
        if (query && !recordHaystack(record).includes(query)) return false;
        return true;
      }});
    }}

    function updateTopicFilterNotice() {{
      if (!topicFilterNotice) return;
      topicFilterNotice.classList.toggle('is-active', Boolean(activeTopicRecordIds));
      topicFilterText.textContent = activeTopicLabel
        ? `Themenfilter aktiv: ${{activeTopicLabel}}`
        : 'Themenfilter aktiv.';
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
      if (exportCount) exportCount.textContent = `${{sichtbareEintraege.length}} Einträge`;
      if (digraMatchedCount) digraMatchedCount.textContent = summary.digra_treffer ?? records.filter((r) => r.digra_url).length;
      if (digraFallbackCount) digraFallbackCount.textContent = summary.digra_protokoll_fallbacks ?? records.filter((r) => r.ergebnisquelle === 'Protokoll').length;
      if (cityLinkCount) cityLinkCount.textContent = summary.stadt_graz_links ?? records.filter((r) => r.source_url).length;
      if (digraMissingCount) digraMissingCount.textContent = records.filter((r) => !r.ergebnis || r.status_filter === 'Unbekannt').length;
      currentLocationIndex = buildLocationIndex(sichtbareEintraege);
      updateTopicFilterNotice();
      renderMapPlaces();
      renderMapLegend();
      refreshMapMarkersIfNeeded();
      renderDetail(ausgewaehlterEintrag);
      renderTopics();

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
          <td data-label="Titel" class="title">${{escapeHtml(record.titel)}}<br><span class="badge">${{escapeHtml(record.kategorie || '')}}</span></td>
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

    fillSelect(yearFilter, records.map((record) => String(record.datum || '').slice(0, 4)));
    fillSelect(dateFilter, records.map((record) => record.datum));
    fillSelect(typeFilter, records.map((record) => record.typ));
    fillSelect(statusFilter, records.map((record) => record.status_filter));
    fillSelect(categoryFilter, records.map((record) => record.kategorie));
    fillSelect(sourceFilter, records.map((record) => record.ergebnisquelle));
    fillSelect(fileFilter, records.map((record) => record.quell_datei));
    fillSelect(sectionFilter, records.map((record) => record.abschnitt));
    fillDatalist('locationSuggestions', records.flatMap((record) => record.orte || []));
    fillDatalist('globalSuggestions', records.flatMap((record) => [
      record.titel,
      record.einbringer,
      record.kategorie,
      ...(record.orte || []),
      ...(record.geschaeftszahlen || []),
      ...(record.betraege || []),
    ]));
    search.addEventListener('input', () => {{
      activeTopicRecordIds = null;
      activeTopicLabel = '';
      render();
    }});
    [yearFilter, dateFilter, typeFilter, statusFilter, categoryFilter, sourceFilter, amountFilter, fileFilter, sectionFilter].forEach((el) => el.addEventListener('input', render));
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
      selectRecord(ausgewaehlterEintrag);
    }});
    detailWrap.addEventListener('click', (event) => {{
      const summaryToggle = event.target.closest('[data-summary-kind]');
      if (summaryToggle) {{
        event.stopPropagation();
        const text = summaryToggle.nextElementSibling;
        if (!text) return;
        const isOpening = text.hidden;
        if (isOpening && !text.textContent) {{
          const kind = summaryToggle.dataset.summaryKind;
          text.textContent = summaryDisplayText(ausgewaehlterEintrag, kind);
        }}
        text.hidden = !isOpening;
        summaryToggle.setAttribute('aria-expanded', String(isOpening));
        return;
      }}
      const locationButton = event.target.closest('[data-location]');
      if (!locationButton) return;
      focusLocation(locationButton.dataset.location || '');
    }});
    mapPlaces.addEventListener('click', (event) => {{
      const locationButton = event.target.closest('[data-location]');
      if (!locationButton) return;
      focusLocation(locationButton.dataset.location || '');
    }});
    parkingList.addEventListener('click', (event) => {{
      const item = event.target.closest('[data-parking-index]');
      if (!item) return;
      const garage = currentParkingGarages[Number(item.dataset.parkingIndex)];
      if (!garage || !parkingMap) return;
      const embeddedCoords = Number.isFinite(garage.lat) && Number.isFinite(garage.lon)
        ? {{ lat: garage.lat, lon: garage.lon }}
        : null;
      Promise.resolve(embeddedCoords || geocodeLocation(garage.address || garage.name)).then((coords) => {{
        if (!coords) return;
        parkingMap.setView([coords.lat, coords.lon], 16);
        highlightParkingList(item.dataset.parkingIndex);
      }});
    }});
    roadworkCheck.addEventListener('click', checkRoadworkPlan);
    roadworksList.addEventListener('click', (event) => {{
      const item = event.target.closest('[data-roadwork-index]');
      if (!item) return;
      const roadwork = currentRoadworks[Number(item.dataset.roadworkIndex)];
      if (!roadwork || !roadworksMap) return;
      geocodeLocation(roadwork.location || roadwork.title).then((coords) => {{
        if (!coords) return;
        roadworksMap.setView([coords.lat, coords.lon], 16);
        highlightRoadworkList(item.dataset.roadworkIndex);
      }});
    }});
    clearTopicFilter.addEventListener('click', () => {{
      activeTopicRecordIds = null;
      activeTopicLabel = '';
      render();
      activateTab('search');
    }});
    mapLegend.addEventListener('click', (event) => {{
      const categoryButton = event.target.closest('[data-map-category]');
      if (!categoryButton) return;
      const category = categoryButton.dataset.mapCategory || '';
      categoryFilter.value = categoryFilter.value === category ? '' : category;
      activeTopicRecordIds = null;
      activeTopicLabel = '';
      render();
    }});
    byId('grazMap').addEventListener('click', (event) => {{
      const recordButton = event.target.closest('[data-popup-record-id]');
      if (!recordButton) return;
      selectRecord(findRecordById(recordButton.dataset.popupRecordId));
    }});
    byId('topicsWrap').addEventListener('click', (event) => {{
      const step = event.target.closest('[data-record-id]');
      if (step) {{
        selectRecord(findRecordById(step.dataset.recordId));
        return;
      }}
      const action = event.target.closest('[data-topic-id]');
      if (action) {{
        const topic = topics.find((item) => item.topic_id === action.dataset.topicId);
        activeTopicRecordIds = new Set((topic?.records || []).map((record) => record.record_id).filter(Boolean));
        activeTopicLabel = topic?.label || 'Thema';
        search.value = '';
        render();
        activateTab('search');
      }}
    }});
    document.querySelectorAll('[data-nav]').forEach((item) => {{
      item.addEventListener('click', () => {{
        const target = item.dataset.nav;
        activateTab(target);
      }});
    }});
    initMap();
    render();
  </script>
</body>
</html>
"""


def viewer_record(record: dict) -> dict:
    category = classify_category(record)
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
        "kategorie": category,
        "einbringer": record.get("submitter", ""),
        "ergebnis": record.get("result_text", ""),
        "ergebnisquelle": german_result_source(str(record.get("result_source", ""))),
        "digra_url": canonical_digra_url(str(record.get("digra_url", ""))),
        "digra_einlagezahl": record.get("digra_business_number", ""),
        "digra_trefferwert": format_score(record.get("digra_match_score", 0)),
        "source_url": record.get("source_url", ""),
        "betraege": record.get("amounts", []),
        "orte": record.get("locations", []),
        "ki_zusammenfassung": record.get("ai_summary", ""),
        "ki_einfache_sprache": record.get("ai_easy_language", ""),
        "quell_datei": german_source_file(str(record.get("source_file", ""))),
    }


def classify_category(record: dict) -> str:
    text = " ".join(
        str(value or "")
        for value in (
            record.get("title", ""),
            record.get("ai_summary", ""),
            record.get("source_snippet", ""),
        )
    )
    for label, pattern in CATEGORY_RULES:
        if pattern.search(text):
            return label
    return "Sonstiges"


def viewer_summary(summary: dict) -> dict:
    return {
        "dateien_mit_eintraegen": summary.get("files_with_records", 0),
        "unklare_eintraege": summary.get("records_by_status", {}).get("unknown", 0),
        "digra_ergebnisse": summary.get("digra_results_used", 0),
        "digra_treffer": summary.get("digra_records_matched", 0),
        "digra_protokoll_fallbacks": summary.get("digra_protocol_fallbacks", 0),
        "stadt_graz_links": summary.get("city_archive_links_applied", 0),
    }


def canonical_digra_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value.strip())
    if parsed.netloc != "digra.graz.at" or parsed.path != "/document":
        return ""
    ref = parse_qs(parsed.query).get("ref", [""])[0]
    if not ref:
        return ""
    return urlunparse(("https", "digra.graz.at", "/document", "", urlencode({"ref": ref}), ""))


def viewer_topic(topic: dict) -> dict:
    records = [record for record in topic.get("records", []) if isinstance(record, dict)]
    latest_record = max(records, key=lambda record: (record.get("meeting_date", ""), record.get("record_id", "")), default={})
    return {
        "topic_id": topic.get("topic_id", ""),
        "label": topic.get("label", ""),
        "business_number": topic.get("business_number", ""),
        "reason": "",
        "ai_reason": meaningful_ai_reason(str(topic.get("ai_reason", ""))),
        "label_source": topic.get("label_source", ""),
        "latest_date": latest_record.get("meeting_date", ""),
        "latest_result": latest_record.get("result_text", ""),
        "confidence": format_score(topic.get("confidence", 0)),
        "dates": topic.get("dates", []),
        "records": [
            {
                "meeting_date": record.get("meeting_date", ""),
                "title": record.get("title", ""),
                "record_id": record.get("record_id", ""),
                "business_numbers": record.get("business_numbers", []),
                "business_number": " ".join(str(value) for value in record.get("business_numbers", [])),
                "result_source": german_result_source(str(record.get("result_source", ""))),
                "result_text": record.get("result_text", ""),
                "status": german_status(str(record.get("status", ""))),
            }
            for record in records
        ],
        "news": topic.get("news", []),
    }


def meaningful_ai_reason(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        return ""
    normalized = re.sub(r"\s+", " ", cleaned.casefold()).strip(" .")
    generic_patterns = [
        "kurze bezeichnung des themas",
        "kompakte beschreibung des gemeinsamen themas",
        "kompakt und beinhaltet den wesentlichen inhalt",
        "kompakte beschreibung des gemeinsamen inhalts",
        "kurze zusammenfassung der beiden themen",
        "gleiche geschäftszahl-basis",
        "gleiche geschaeftszahl-basis",
    ]
    if any(pattern in normalized for pattern in generic_patterns):
        return ""
    if len(normalized.split()) <= 3 and ("kurz" in normalized or "kompakt" in normalized):
        return ""
    return cleaned


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
