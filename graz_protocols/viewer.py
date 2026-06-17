from __future__ import annotations

from pathlib import Path
import argparse
import html
import json
import re
import sys
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .background_update import PREFERRED_TARGETS, select_target
from .city_sources import archive_asset_title_from_url, is_attendance_asset
from .civic_services import civic_service_summary, load_civic_council, load_civic_services
from .mobility_sources import load_health_places, load_parking_garages, load_roadworks, mobility_source_summary
from .parser import extract_location_details, find_street_names_in_text
from .street_names import load_default_street_names, normalize_street_name


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

KNOWN_GRAZ_LOCATION_COORDS = {
    "Andreas-Hofer-Platz": {"lat": 47.0697, "lon": 15.4372},
    "Annenstraße": {"lat": 47.0708, "lon": 15.4243},
    "Andritz": {"lat": 47.1132, "lon": 15.4238},
    "Citypark": {"lat": 47.0589, "lon": 15.4243},
    "Conrad-von-Hötzendorf-Straße": {"lat": 47.0565, "lon": 15.4499},
    "Eggenberg": {"lat": 47.0735, "lon": 15.3916},
    "Franziskanerplatz": {"lat": 47.0705, "lon": 15.4374},
    "Fröbelpark": {"lat": 47.0748, "lon": 15.4156},
    "Geidorf": {"lat": 47.0862, "lon": 15.4408},
    "Griesplatz": {"lat": 47.0646, "lon": 15.4315},
    "Gösting": {"lat": 47.0997, "lon": 15.3975},
    "Hauptplatz": {"lat": 47.0707, "lon": 15.4386},
    "Herrengasse": {"lat": 47.0688, "lon": 15.4401},
    "Innere Stadt": {"lat": 47.0707, "lon": 15.4386},
    "Jakominiplatz": {"lat": 47.0671, "lon": 15.4422},
    "Jakomini": {"lat": 47.0574, "lon": 15.4474},
    "Kaiser-Josef-Platz": {"lat": 47.0707, "lon": 15.4455},
    "Kaiserfeldgasse": {"lat": 47.0678, "lon": 15.4389},
    "Körösistraße": {"lat": 47.0812, "lon": 15.4355},
    "Lend": {"lat": 47.0765, "lon": 15.4254},
    "Liebenau": {"lat": 47.0358, "lon": 15.4548},
    "Mariatrost": {"lat": 47.1053, "lon": 15.4937},
    "Lendplatz": {"lat": 47.0739, "lon": 15.4302},
    "Murpark": {"lat": 47.0406, "lon": 15.4648},
    "Neutorgasse": {"lat": 47.0683, "lon": 15.4371},
    "Peter-Tunner-Gasse": {"lat": 47.079, "lon": 15.423},
    "Plabutscherstraße": {"lat": 47.072, "lon": 15.388},
    "Puntigam": {"lat": 47.0248, "lon": 15.4324},
    "Radetzkystraße": {"lat": 47.0666, "lon": 15.4369},
    "Ries": {"lat": 47.0906, "lon": 15.4905},
    "Schmiedgasse": {"lat": 47.0692, "lon": 15.4396},
    "St. Leonhard": {"lat": 47.0759, "lon": 15.4554},
    "St. Peter": {"lat": 47.0504, "lon": 15.4765},
    "Stadtpark": {"lat": 47.0731, "lon": 15.4447},
    "Straßgang": {"lat": 47.0333, "lon": 15.3939},
    "Waltendorf": {"lat": 47.0702, "lon": 15.4875},
    "Wetzelsdorf": {"lat": 47.0522, "lon": 15.3886},
    "Weinzödl": {"lat": 47.1226, "lon": 15.4074},
    "Zinzendorfgasse": {"lat": 47.0752, "lon": 15.4454},
}

KNOWN_GRAZ_LOCATION_ALIASES = {
    "Andritz": ["andritz"],
    "Eggenberg": ["eggenberg"],
    "Geidorf": ["geidorf"],
    "Gösting": ["gösting", "goesting"],
    "Gries": ["gries"],
    "Innere Stadt": ["innere stadt"],
    "Jakomini": ["jakomini"],
    "Lend": ["lend"],
    "Liebenau": ["liebenau"],
    "Mariatrost": ["mariatrost"],
    "Puntigam": ["puntigam"],
    "Ries": ["ries"],
    "St. Leonhard": ["st. leonhard", "st leonhard", "sankt leonhard"],
    "St. Peter": ["st. peter", "st peter", "sankt peter"],
    "Straßgang": ["straßgang", "strassgang"],
    "Waltendorf": ["waltendorf"],
    "Wetzelsdorf": ["wetzelsdorf"],
    "Weinzödl": ["weinzödl", "weinzoedl"],
}


def paths_equal(left: Path, right: Path) -> bool:
    return left == right or left.resolve(strict=False) == right.resolve(strict=False)


def resolve_viewer_record_source(
    records: Path,
    summary: Path,
    *,
    records_was_explicit: bool,
    summary_was_explicit: bool,
    allow_nonpreferred_records: bool,
) -> tuple[Path, Path]:
    preferred = select_target()
    if preferred is None:
        return records, summary

    default_records = Path("out") / "agenda_items.jsonl"
    default_summary = Path("out") / "summary.json"
    if not records_was_explicit and paths_equal(records, default_records) and not records.exists():
        resolved_summary = preferred.summary if not summary_was_explicit and paths_equal(summary, default_summary) else summary
        return preferred.records, resolved_summary

    known_records = [target.records for target in PREFERRED_TARGETS]
    if (
        records_was_explicit
        and not allow_nonpreferred_records
        and any(paths_equal(records, known) for known in known_records)
        and not paths_equal(records, preferred.records)
    ):
        raise SystemExit(
            "Nicht bevorzugte lokale Datenbasis angegeben: "
            f"{records}. Bevorzugt ist aktuell {preferred.records}. "
            "Wenn das absichtlich ein Debug-Lauf ist, nutze --allow-nonpreferred-records."
        )

    return records, summary


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
    parser.add_argument(
        "--pharmacy-cache",
        type=Path,
        default=Path("out") / "apotheken_graz_osm.json",
        help="Optionaler Cache für Apotheken aus OpenStreetMap/Overpass.",
    )
    parser.add_argument(
        "--doctors-cache",
        type=Path,
        default=Path("out") / "aerzte_graz_osm.json",
        help="Optionaler Cache für Ordinationen aus OpenStreetMap/Overpass.",
    )
    parser.add_argument(
        "--allow-nonpreferred-records",
        action="store_true",
        help="Erlaubt explizite Viewer-Builds aus älteren bekannten lokalen DIGRA-Exporten.",
    )
    raw_args = list(argv) if argv is not None else sys.argv[1:]
    args = parser.parse_args(argv)
    args.records, args.summary = resolve_viewer_record_source(
        args.records,
        args.summary,
        records_was_explicit="--records" in raw_args,
        summary_was_explicit="--summary" in raw_args,
        allow_nonpreferred_records=args.allow_nonpreferred_records,
    )

    if not args.records.exists():
        print(f"Eintragsdatei nicht gefunden: {args.records}", file=sys.stderr)
        return 1

    records = read_jsonl(args.records)
    summary = read_json(args.summary) if args.summary.exists() else {}
    topics = read_json(args.topics) if args.topics and args.topics.exists() else []
    garages, parking_summary = load_parking_garages(args.parking_cache)
    roadworks, roadworks_summary = load_roadworks(args.roadworks_cache)
    pharmacies, pharmacies_summary = load_health_places("pharmacy", args.pharmacy_cache)
    doctors, doctors_summary = load_health_places("doctor", args.doctors_cache)
    civic_services, civic_services_summary = load_civic_services()
    civic_council = load_civic_council(fetch_live=True)
    mobility_summary = mobility_source_summary()
    mobility_summary["parking"]["records"] = parking_summary.get("records", 0)
    mobility_summary["parking"]["errors"] = parking_summary.get("errors", [])
    mobility_summary["roadworks"]["records"] = roadworks_summary.get("records", 0)
    mobility_summary["roadworks"]["errors"] = roadworks_summary.get("errors", [])
    mobility_summary["pharmacies"]["records"] = pharmacies_summary.get("records", 0)
    mobility_summary["pharmacies"]["errors"] = pharmacies_summary.get("errors", [])
    mobility_summary["doctors"]["records"] = doctors_summary.get("records", 0)
    mobility_summary["doctors"]["errors"] = doctors_summary.get("errors", [])
    mobility_summary["civic_services"] = civic_services_summary
    args.output.write_text(
        build_html(records, summary, topics, garages, mobility_summary, roadworks, pharmacies, doctors, civic_services, civic_council),
        encoding="utf-8",
    )
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


def build_preloaded_location_cache(
    records: list[dict],
    parking_garages: list[dict],
    roadworks: list[dict],
    pharmacies: list[dict],
    doctors: list[dict],
    civic_services: list[dict] | None = None,
) -> dict[str, dict[str, float]]:
    cache: dict[str, dict[str, float]] = {}

    def add(location: str, lat: object, lon: object) -> None:
        name = str(location or "").strip()
        if not name:
            return
        try:
            coords = {"lat": float(lat), "lon": float(lon)}
        except (TypeError, ValueError):
            return
        if not (-90 <= coords["lat"] <= 90 and -180 <= coords["lon"] <= 180):
            return
        cache.setdefault(name, coords)

    record_locations = {
        str(location).strip()
        for record in records
        for location in record.get("locations", [])
        if str(location).strip()
    }
    for location in record_locations:
        if location in KNOWN_GRAZ_LOCATION_COORDS:
            cache[location] = KNOWN_GRAZ_LOCATION_COORDS[location]

    for garage in parking_garages:
        add(str(garage.get("address", "")).removesuffix(", Graz"), garage.get("lat"), garage.get("lon"))
        add(garage.get("address", ""), garage.get("lat"), garage.get("lon"))
        add(garage.get("name", ""), garage.get("lat"), garage.get("lon"))
    for roadwork in roadworks:
        coords = roadwork.get("coords") or {}
        add(roadwork.get("location", "") or roadwork.get("title", ""), coords.get("lat"), coords.get("lon"))
    for place in [*pharmacies, *doctors]:
        add(place.get("address", ""), place.get("lat"), place.get("lon"))
        add(place.get("name", ""), place.get("lat"), place.get("lon"))
    for service in civic_services or []:
        add(service.get("address", ""), service.get("lat"), service.get("lon"))
        add(service.get("name", ""), service.get("lat"), service.get("lon"))

    return dict(sorted(cache.items(), key=lambda item: item[0].casefold()))


def build_html(
    records: list[dict],
    summary: dict,
    topics: list[dict] | None = None,
    parking_garages: list[dict] | None = None,
    mobility_sources: dict | None = None,
    roadworks: list[dict] | None = None,
    pharmacies: list[dict] | None = None,
    doctors: list[dict] | None = None,
    civic_services: list[dict] | None = None,
    civic_council: dict | None = None,
) -> str:
    data = json.dumps([viewer_record(record) for record in records], ensure_ascii=False)
    summary_data = json.dumps(viewer_summary(summary), ensure_ascii=False)
    topics_data = json.dumps([viewer_topic(topic) for topic in topics or []], ensure_ascii=False)
    parking_data = json.dumps(parking_garages or [], ensure_ascii=False)
    mobility_data = json.dumps(mobility_sources or mobility_source_summary(), ensure_ascii=False)
    roadworks_data = json.dumps(roadworks or [], ensure_ascii=False)
    pharmacies_data = json.dumps(pharmacies or [], ensure_ascii=False)
    doctors_data = json.dumps(doctors or [], ensure_ascii=False)
    civic_services_data = json.dumps(civic_services or load_civic_services()[0], ensure_ascii=False)
    civic_council_data = json.dumps(civic_council or load_civic_council(), ensure_ascii=False)
    if "civic_services" not in (mobility_sources or {}):
        mobility_sources = {**(mobility_sources or mobility_source_summary()), "civic_services": civic_service_summary()}
        mobility_data = json.dumps(mobility_sources, ensure_ascii=False)
    location_cache_data = json.dumps(
        build_preloaded_location_cache(
            records,
            parking_garages or [],
            roadworks or [],
            pharmacies or [],
            doctors or [],
            civic_services or load_civic_services()[0],
        ),
        ensure_ascii=False,
    )
    return f"""<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="robots" content="noindex, nofollow, noarchive">
  <meta name="googlebot" content="noindex, nofollow, noarchive">
  <title>Graz Gemeinderatsprotokolle</title>
  <meta name="application-name" content="Graz Protokolle">
  <meta name="apple-mobile-web-app-title" content="Graz Protokolle">
  <meta name="theme-color" content="#f7f8fa">
  <link rel="icon" type="image/png" sizes="16x16" href="bi/favicon-16.png">
  <link rel="icon" type="image/png" sizes="32x32" href="bi/favicon-32.png">
  <link rel="apple-touch-icon" sizes="180x180" href="bi/apple-touch-icon.png">
  <link rel="manifest" href="site.webmanifest">
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
      font-size: 13px;
      background: var(--bg);
      color: var(--ink);
    }}
    .app-shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 220px minmax(0, 1fr);
    }}
    .sidebar {{
      background: var(--panel);
      border-right: 1px solid var(--line);
      padding: 16px 14px;
      position: sticky;
      top: 0;
      height: 100vh;
    }}
    .brand {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      padding-bottom: 14px;
      margin-bottom: 14px;
      border-bottom: 1px solid var(--line);
    }}
    .brand-title {{
      display: block;
      font-size: 28px;
      font-weight: 800;
      letter-spacing: 0;
      color: var(--ink);
    }}
    .mobile-nav-toggle {{
      display: none;
      width: 34px;
      height: 34px;
      min-height: 34px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      color: var(--ink);
      padding: 0;
      cursor: pointer;
      align-items: center;
      justify-content: center;
      gap: 8px;
    }}
    .mobile-nav-toggle:hover {{
      border-color: #bfdbfe;
      color: var(--accent-dark);
      background: var(--accent-tint);
    }}
    .mobile-nav-icon {{
      width: 16px;
      height: 12px;
      display: inline-grid;
      gap: 3px;
    }}
    .mobile-nav-icon span {{
      display: block;
      height: 2px;
      border-radius: 999px;
      background: currentColor;
    }}
    .side-nav {{
      display: grid;
      gap: 4px;
      margin-bottom: 14px;
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
      padding: 8px 10px;
      font-size: 13px;
      font-weight: 650;
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
      font-size: 11px;
      line-height: 1.45;
      padding: 9px;
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
      padding: 16px 20px;
      background: var(--bg);
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
    }}
    h1 {{
      margin: 0 0 6px;
      font-size: 21px;
      font-weight: 700;
      letter-spacing: 0;
    }}
    .meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      color: var(--muted);
      font-size: 12px;
    }}
    .primary-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: auto;
      min-width: 124px;
      min-height: 34px;
      padding: 6px 9px;
      border: 1px solid var(--accent);
      border-radius: 8px;
      background: var(--accent);
      color: white;
      box-shadow: var(--shadow);
      font: inherit;
      font-weight: 600;
      text-decoration: none;
    }}
    .primary-link:hover {{
      background: var(--accent-dark);
      color: white;
    }}
    .toolbar {{
      display: grid;
      grid-template-columns: minmax(220px, 1.4fr) repeat(5, minmax(104px, 1fr)) minmax(112px, 0.8fr);
      gap: 8px;
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 10px;
      margin-bottom: 12px;
    }}
    .toolbar[hidden] {{
      display: none !important;
    }}
    .toolbar .wide {{
      grid-column: span 2;
    }}
    input, select, textarea, button {{
      width: 100%;
      min-height: 34px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      padding: 6px 9px;
      font: inherit;
      background: white;
      color: var(--ink);
      outline-color: var(--accent);
    }}
    textarea {{
      min-height: 92px;
      resize: vertical;
      line-height: 1.35;
    }}
    button {{
      cursor: pointer;
      background: var(--accent);
      border-color: var(--accent);
      color: white;
      font-weight: 600;
    }}
    button:hover {{ background: var(--accent-dark); }}
    main {{ padding: 14px 20px 26px; }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(4, minmax(150px, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }}
    .stat {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 10px;
    }}
    .stat b {{
      display: block;
      font-size: 19px;
      margin-bottom: 2px;
      color: #0f172a;
    }}
    .stat span {{ color: var(--muted); font-size: 11px; }}
    .table-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      overflow-x: auto;
      overflow-y: hidden;
      -webkit-overflow-scrolling: touch;
    }}
    .table-note {{
      margin: 0 0 8px;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      background: #eff6ff;
      color: #1e3a8a;
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
    }}
    table {{
      width: 100%;
      min-width: 1080px;
      border-collapse: collapse;
      background: transparent;
    }}
    th, td {{
      padding: 8px 9px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      text-align: left;
      font-size: 12px;
    }}
    th {{
      background: #f8fafc;
      color: #475569;
      font-size: 11px;
      font-weight: 700;
      white-space: nowrap;
    }}
    tbody tr {{ cursor: pointer; }}
      tbody tr:last-child td {{ border-bottom: 0; }}
      tr:hover td {{ background: #f8fbff; }}
    tbody tr.selected-record td {{
      background: #f1f5f9;
    }}
    .mobile-card-only {{
      display: none;
    }}
    .title {{ min-width: 190px; max-width: 300px; font-weight: 600; }}
    .date-col {{ width: 82px; min-width: 78px; max-width: 90px; white-space: nowrap; }}
    .type-col {{ width: 84px; min-width: 78px; max-width: 110px; }}
    .type-col .badge {{ white-space: normal; line-height: 1.18; }}
    .item-col {{ width: 46px; min-width: 42px; max-width: 54px; text-align: right; white-space: nowrap; }}
    .business-col {{ width: 124px; min-width: 112px; max-width: 150px; overflow-wrap: anywhere; word-break: break-word; }}
    .amount-col,
    .places-col {{ width: 180px; min-width: 165px; max-width: 250px; overflow-wrap: anywhere; word-break: break-word; }}
    .status-col {{ width: 168px; min-width: 148px; max-width: 210px; overflow-wrap: normal; }}
    .status-col .badge {{ white-space: nowrap; }}
    .status-col .source-link {{
      display: inline-block;
      margin-top: 5px;
      font-size: 11px;
    }}
    .results-col {{ min-width: 240px; width: 26%; }}
    .result {{
      color: var(--muted);
      max-width: 520px;
      line-height: 1.35;
      white-space: pre-line;
    }}
    .status-dot-col {{ width: 34px; text-align: center; }}
    .status-dot {{
      display: inline-block;
      width: 0.72rem;
      height: 0.72rem;
      border-radius: 999px;
      background: #94a3b8;
      box-shadow: 0 0 0 3px rgba(148, 163, 184, 0.16);
      vertical-align: middle;
    }}
    .status-dot.accepted {{
      background: #16a34a;
      box-shadow: 0 0 0 3px rgba(22, 163, 74, 0.16);
    }}
    .status-dot.rejected {{
      background: #dc2626;
      box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.16);
    }}
    .badge {{
      display: inline-block;
      padding: 2px 7px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font-size: 11px;
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
      padding: 10px;
      margin-bottom: 12px;
    }}
    .detail h2 {{
      margin: 0 0 8px;
      font-size: 15px;
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
    .participation-banner,
    .participation-card,
    .participation-detail,
    .participation-local-note {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    .participation-banner {{
      padding: 12px;
      margin-bottom: 12px;
      display: grid;
      gap: 8px;
      background: #f8fbff;
    }}
    .participation-banner h2,
    .participation-detail h2 {{
      margin: 0;
      font-size: 16px;
      letter-spacing: 0;
    }}
    .participation-banner p,
    .participation-local-note p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }}
    .participation-layout {{
      display: grid;
      grid-template-columns: minmax(260px, 0.95fr) minmax(320px, 1.45fr);
      gap: 12px;
      align-items: start;
    }}
    .participation-list {{
      display: grid;
      gap: 8px;
    }}
    .participation-card {{
      padding: 10px 11px;
      text-align: left;
      background: white;
      color: var(--ink);
      border-color: var(--line);
      font-weight: 400;
      display: grid;
      gap: 7px;
      line-height: 1.35;
    }}
    .participation-card:hover,
    .participation-card.active {{
      border-color: var(--accent);
      background: #eff6ff;
      color: var(--ink);
    }}
    .participation-card-title {{
      display: block;
      font-size: 13px;
      font-weight: 500;
      overflow-wrap: anywhere;
    }}
    .participation-card-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      align-items: center;
    }}
    .participation-card-chip {{
      border: 1px solid #e2e8f0;
      border-radius: 999px;
      background: #f8fafc;
      color: #475569;
      padding: 2px 6px;
      font-size: 11px;
      line-height: 1.2;
    }}
    .participation-card-feedback {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.3;
    }}
    .participation-detail {{
      padding: 12px;
      display: grid;
      gap: 10px;
    }}
    .participation-actions {{
      display: grid;
      grid-template-columns: repeat(3, minmax(90px, 1fr));
      gap: 8px;
    }}
    .participation-stance {{
      background: white;
      color: var(--ink);
      border-color: var(--line-strong);
    }}
    .participation-stance.active {{
      background: var(--accent);
      border-color: var(--accent);
      color: white;
    }}
    .participation-form {{
      display: grid;
      gap: 8px;
    }}
    .participation-form label {{
      display: grid;
      gap: 4px;
      color: var(--muted);
      font-size: 12px;
      font-weight: 600;
    }}
    .participation-form label > * {{
      color: var(--ink);
      font-weight: 400;
    }}
    .participation-local-note {{
      padding: 9px;
      background: #f8fafc;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.45;
    }}
    .participation-detail-cta {{
      margin-top: 12px;
      padding: 12px;
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      background: linear-gradient(180deg, #eff6ff 0%, #ffffff 100%);
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
    }}
    .participation-detail-copy {{
      min-width: min(100%, 260px);
      flex: 1 1 260px;
      display: grid;
      gap: 4px;
    }}
    .participation-detail-copy strong {{
      color: #1e3a8a;
      font-size: 13px;
    }}
    .participation-detail-copy p {{
      margin: 0;
      color: #334155;
      font-size: 12px;
      line-height: 1.4;
    }}
    .participation-detail-chip {{
      width: fit-content;
      border: 1px solid #bfdbfe;
      border-radius: 999px;
      background: #dbeafe;
      color: #1e40af;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 800;
    }}
    .participation-detail-cta button {{
      width: auto;
      white-space: nowrap;
    }}
    .civic-modal {{
      position: fixed;
      inset: 0;
      z-index: 50;
      display: none;
      place-items: center;
      padding: 18px;
      background: rgba(15, 23, 42, 0.48);
    }}
    .civic-modal.is-open {{
      display: grid;
    }}
    .civic-modal-card {{
      width: min(560px, 100%);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      box-shadow: 0 18px 55px rgba(15, 23, 42, 0.24);
      padding: 16px;
      display: grid;
      gap: 10px;
    }}
    .civic-modal-card h2 {{
      margin: 0;
      font-size: 18px;
      letter-spacing: 0;
    }}
    .civic-modal-card p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.45;
    }}
    .civic-modal-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      justify-content: flex-end;
    }}
    .civic-modal-actions button {{
      width: auto;
      min-width: 132px;
    }}
    .secondary-button {{
      background: white;
      color: var(--ink);
      border-color: var(--line-strong);
    }}
    .secondary-button:hover {{
      background: #f8fafc;
      color: var(--ink);
    }}
    .local-list {{
      display: grid;
      gap: 8px;
      margin-top: 10px;
    }}
    .local-item {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 8px 9px;
      background: #fbfdff;
    }}
    .local-item strong {{
      display: block;
      margin-bottom: 3px;
      font-size: 13px;
    }}
    .local-item small {{
      display: block;
      color: var(--muted);
      line-height: 1.45;
      overflow-wrap: anywhere;
    }}
    .local-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 7px;
    }}
    .local-actions button {{
      width: auto;
      min-height: 28px;
      border-radius: 6px;
      padding: 4px 9px;
      font-size: 12px;
    }}
    .subscription-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(140px, 1fr));
      gap: 8px;
      margin-top: 10px;
    }}
    .subscription-grid .wide {{
      grid-column: span 2;
    }}
    .subscription-status {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.4;
    }}
    .summary-blocks {{
      display: grid;
      gap: 9px;
      margin-top: 12px;
    }}
    .summary-block {{
      border: 1px solid #bfdbfe;
      border-radius: 8px;
      background: linear-gradient(180deg, #ffffff 0%, #f8fbff 100%);
      overflow: hidden;
      contain: layout paint;
      box-shadow: 0 10px 22px rgba(37, 99, 235, 0.07);
    }}
    .summary-block.easy {{
      border-color: #bbf7d0;
      background: linear-gradient(180deg, #ffffff 0%, #f7fef9 100%);
    }}
    .summary-toggle {{
      width: 100%;
      min-height: 0;
      border: 0;
      border-radius: 0;
      background: transparent;
      text-align: left;
      padding: 10px 12px 6px;
      font-weight: 850;
      color: #1e293b;
      display: grid;
      gap: 3px;
    }}
    .summary-toggle:hover {{
      background: var(--accent-tint);
      color: var(--accent-dark);
    }}
    .summary-toggle-label {{
      display: flex;
      align-items: center;
      gap: 7px;
      font-size: 14px;
      line-height: 1.25;
    }}
    .summary-toggle-label::before {{
      content: "";
      width: 8px;
      height: 8px;
      border-radius: 999px;
      background: #2563eb;
      flex: 0 0 auto;
    }}
    .summary-block.easy .summary-toggle-label::before {{
      background: #16a34a;
    }}
    .summary-toggle-sub {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 650;
      line-height: 1.35;
    }}
    .summary-text {{
      padding: 0 12px 10px;
      color: #334155;
      line-height: 1.42;
      max-height: 520px;
      overflow: auto;
      contain: layout paint;
      font-size: 14px;
    }}
    .summary-text p {{
      margin: 0 0 7px;
    }}
    .summary-text p:last-child {{
      margin-bottom: 0;
    }}
    .summary-text .summary-note {{
      color: var(--muted);
      font-size: 12px;
      border-top: 1px solid var(--line);
      padding-top: 8px;
      margin-top: 4px;
    }}
    .date-summary-detail .summary-text {{
      max-height: none;
      overflow: visible;
    }}
    .summary-list {{
      margin: 4px 0 12px;
      padding-left: 0;
      display: grid;
      gap: 6px;
      list-style: none;
    }}
    .summary-list li {{
      line-height: 1.45;
    }}
    .summary-filter-link {{
      appearance: none;
      width: auto;
      min-height: 0;
      border: 0;
      border-radius: 6px;
      padding: 2px 5px;
      background: transparent;
      color: var(--accent-dark);
      cursor: pointer;
      font: inherit;
      font-weight: 700;
      text-align: left;
      text-decoration: underline;
    }}
    .summary-filter-link:hover {{
      background: var(--accent-tint);
    }}
    .search-subtabs {{
      display: flex;
      flex-wrap: wrap;
      gap: 0;
      margin-bottom: 12px;
      border-bottom: 1px solid var(--line);
    }}
    .search-subtab {{
      width: auto;
      min-height: 36px;
      border: 0;
      border-bottom: 3px solid transparent;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      padding: 7px 14px;
      font-size: 13px;
      font-weight: 750;
    }}
    .search-subtab.active {{
      border-bottom-color: var(--accent);
      background: transparent;
      color: var(--accent-dark);
    }}
    .search-subtab:hover {{
      background: #f8fafc;
      color: var(--accent-dark);
    }}
    .search-subpanel[hidden] {{
      display: none;
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
      max-height: calc(100vh - 220px);
      overflow-y: auto;
    }}
    .start-panel {{
      place-items: center;
      align-content: center;
      min-height: clamp(420px, 68vh, 760px);
      padding: clamp(24px, 8vh, 72px) 0;
    }}
    .tab-panel.active.start-panel {{
      display: grid;
    }}
    .question-box {{
      width: min(920px, 100%);
      display: grid;
      gap: 16px;
      margin-inline: auto;
    }}
    .question-box h2 {{
      margin: 0;
      font-size: clamp(18px, 2vw, 24px);
      text-align: center;
    }}
    .question-row {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 136px;
      gap: 12px;
      align-items: start;
    }}
    .question-input-wrap {{
      position: relative;
      display: grid;
      gap: 8px;
      min-width: 0;
    }}
    .question-row input {{
      min-height: 58px;
      font-size: 17px;
      padding: 14px 16px;
    }}
    .question-row button {{
      min-height: 58px;
      font-size: 15px;
    }}
    .question-row[hidden] {{
      display: none;
    }}
    .question-suggestions {{
      border: 1px solid var(--line);
      border-radius: 10px;
      background: #fff;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.11);
      padding: 6px;
      display: grid;
      gap: 4px;
    }}
    .question-suggestions[hidden] {{
      display: none;
    }}
    .question-suggestion {{
      width: 100%;
      border: 0;
      border-radius: 7px;
      background: transparent;
      color: var(--ink);
      cursor: pointer;
      font: inherit;
      font-size: 14px;
      line-height: 1.35;
      padding: 9px 10px;
      text-align: left;
      overflow-wrap: anywhere;
    }}
    .question-suggestion:hover,
    .question-suggestion:focus-visible {{
      background: #eff6ff;
      color: #1e3a8a;
      outline: none;
    }}
    .question-result {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 14px;
      min-height: 58px;
      line-height: 1.45;
    }}
    .question-tabs {{
      display: grid;
      gap: 10px;
    }}
    .question-tabs[hidden] {{
      display: none;
    }}
    .question-tab-buttons {{
      display: flex;
      flex-wrap: wrap;
      gap: 0;
      border-bottom: 1px solid var(--line);
    }}
    .question-tab-button {{
      width: auto;
      min-height: 36px;
      border: 0;
      border-bottom: 3px solid transparent;
      border-radius: 0;
      background: transparent;
      color: var(--muted);
      padding: 7px 14px;
      font-size: 13px;
      font-weight: 750;
    }}
    .question-tab-button.active {{
      border-bottom-color: var(--accent);
      background: transparent;
      color: var(--accent-dark);
    }}
    .question-tab-button:hover {{
      background: #f8fafc;
      color: var(--accent-dark);
    }}
    .question-tab-panel[hidden] {{
      display: none;
    }}
    .answer-shell {{
      display: grid;
      gap: 18px;
    }}
    .answer-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      color: var(--muted);
      font-size: 12px;
    }}
    .answer-pill {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      background: #f8fafc;
    }}
    .answer-section {{
      display: grid;
      gap: 11px;
      padding-top: 16px;
      border-top: 3px solid #cbd5e1;
    }}
    .answer-section:first-of-type {{
      border-top: 0;
      padding-top: 0;
    }}
    .answer-section h3 {{
      margin: 0;
      font-size: 14px;
      line-height: 1.3;
      color: #0f172a;
    }}
    .answer-section p {{
      margin: 0;
      color: #334155;
      line-height: 1.68;
    }}
    .answer-section p + p {{
      margin-top: 8px;
    }}
    .answer-list {{
      list-style: none;
      display: grid;
      gap: 6px;
      padding: 0;
      margin: 0;
    }}
    .answer-item {{
      display: grid;
      gap: 7px;
      padding: 9px 10px;
      border: 1px solid #e2e8f0;
      border-left: 4px solid #bfdbfe;
      border-radius: 8px;
      background: #fff;
      box-shadow: none;
    }}
    .answer-item:first-child {{
      border-top: 1px solid #e2e8f0;
    }}
    .answer-item-title {{
      display: block;
      font-size: 13px;
      font-weight: 600;
      line-height: 1.42;
    }}
    .answer-title-link {{
      border: 0;
      background: transparent;
      color: inherit;
      cursor: pointer;
      display: inline;
      font: inherit;
      font-weight: 600;
      min-width: 0;
      padding: 0;
      text-align: left;
      text-decoration: underline;
      text-decoration-color: #cbd5e1;
      text-underline-offset: 3px;
    }}
    .answer-title-link:hover {{
      background: transparent;
      color: var(--accent-dark);
      text-decoration-color: var(--accent);
    }}
    .answer-more {{
      margin-top: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
      padding: 7px 9px;
    }}
    .answer-more summary {{
      cursor: pointer;
      color: var(--accent-dark);
      font-size: 12px;
      font-weight: 700;
    }}
    .answer-more .answer-list {{
      margin-top: 8px;
    }}
    .answer-item-meta {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.55;
    }}
    .answer-item-facts {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }}
    .answer-fact {{
      display: inline-flex;
      align-items: center;
      width: auto;
      min-height: 22px;
      border-radius: 999px;
      border: 1px solid #cbd5e1;
      background: #f8fafc;
      color: #334155;
      padding: 2px 7px;
      font-size: 11px;
      font-weight: 750;
      line-height: 1.2;
    }}
    .answer-ref {{
      color: var(--accent-dark);
      font-weight: 700;
      text-decoration: none;
      white-space: nowrap;
    }}
    .answer-note {{
      color: var(--muted);
      font-size: 12px;
    }}
    .question-result[hidden],
    .question-sources[hidden] {{
      display: none;
    }}
    .ai-disclaimer {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      text-align: center;
      margin-top: 8px;
    }}
    .global-ai-disclaimer {{
      position: fixed;
      left: calc(var(--sidebar-width) + 16px);
      right: 16px;
      bottom: 8px;
      z-index: 30;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.3;
      text-align: center;
      pointer-events: none;
    }}
    .question-sources {{
      display: grid;
      gap: 8px;
    }}
    .question-sources-list {{
      display: grid;
      gap: 8px;
    }}
    .question-sources-more {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #f8fafc;
      padding: 8px;
    }}
    .question-sources-more summary {{
      cursor: pointer;
      color: var(--accent-dark);
      font-size: 12px;
      font-weight: 800;
    }}
    .question-sources-more .question-sources-list {{
      margin-top: 8px;
    }}
    .question-source-note {{
      color: var(--muted);
      font-size: 12px;
      line-height: 1.35;
      margin: 2px 0 0;
    }}
    .source-card {{
      display: grid;
      grid-template-columns: 34px minmax(0, 1fr);
      gap: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
      padding: 11px;
      font-size: 13px;
      line-height: 1.35;
      color: inherit;
      text-decoration: none;
      width: 100%;
      text-align: left;
      font-family: inherit;
      cursor: pointer;
    }}
    .source-card[href]:hover,
    button.source-card:hover {{
      border-color: #bfdbfe;
      background: #f8fbff;
    }}
    .source-rank {{
      width: 26px;
      height: 26px;
      border-radius: 999px;
      display: grid;
      place-items: center;
      background: var(--accent-tint);
      color: var(--accent-dark);
      font-weight: 800;
      font-size: 12px;
    }}
    .source-body {{
      min-width: 0;
      display: grid;
      gap: 7px;
    }}
    .source-title {{
      display: grid;
      gap: 5px;
      font-weight: 650;
    }}
    .source-heading {{
      color: var(--text);
      font-size: 12px;
      line-height: 1.35;
    }}
    .source-facts {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
    }}
    .source-kind, .source-decision {{
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 2px 7px;
      color: #475569;
      background: white;
      font-size: 11px;
      font-weight: 700;
    }}
    .source-decision {{
      color: var(--accent-dark);
      background: var(--accent-tint);
      border-color: #bfdbfe;
    }}
    .source-meta {{
      color: var(--muted);
      font-size: 12px;
    }}
    .source-matches {{
      color: #475569;
      font-size: 12px;
    }}
    .source-action {{
      color: var(--accent-dark);
      font-size: 12px;
      font-weight: 800;
    }}
    .map-panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: var(--shadow);
      padding: 10px;
      margin-bottom: 12px;
    }}
    .map-head {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: flex-start;
      margin-bottom: 8px;
    }}
    .map-head-main {{
      min-width: 0;
    }}
    .map-actions {{
      display: flex;
      justify-content: flex-end;
      gap: 8px;
      flex-wrap: wrap;
      align-items: center;
      max-width: 360px;
    }}
    .map-action-note {{
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
      flex-basis: 100%;
    }}
    .map-head h2 {{
      margin: 0;
      font-size: 14px;
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
    .map-legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 10px;
    }}
    .legend-item {{
      width: auto;
      min-height: 32px;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 9px;
      color: #334155;
      background: white;
      border: 1px solid var(--line-strong);
    }}
    .legend-item.is-active {{
      border-color: var(--category-color, var(--accent));
      background: var(--accent-tint);
      color: var(--accent-dark);
    }}
    .legend-swatch {{
      width: 10px;
      height: 10px;
      border-radius: 999px;
      background: var(--category-color, var(--accent));
      flex: 0 0 auto;
    }}
    .map-note {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 8px;
      line-height: 1.4;
    }}
    .council-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(240px, 340px);
      gap: 12px;
      align-items: start;
    }}
    .council-kpis {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
      margin-bottom: 12px;
    }}
    .council-kpi {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 11px 12px;
      min-width: 0;
    }}
    .council-kpi strong {{
      display: block;
      color: #0f172a;
      font-size: 22px;
      line-height: 1.1;
      margin-bottom: 4px;
    }}
    .council-kpi span {{
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0;
    }}
    .council-stage {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
      padding: 14px;
      min-width: 0;
    }}
    .council-header {{
      display: flex;
      flex-wrap: wrap;
      justify-content: space-between;
      gap: 8px;
      align-items: baseline;
      margin-bottom: 12px;
    }}
    .council-header h3 {{
      margin: 0;
      font-size: 15px;
    }}
    .council-summary {{
      color: var(--muted);
      font-size: 12px;
      font-weight: 700;
    }}
    .council-dots {{
      position: relative;
      height: clamp(250px, 34vw, 390px);
      margin-bottom: 16px;
      border-bottom: 1px solid var(--line);
      overflow: visible;
    }}
    .council-majority-note {{
      display: flex;
      align-items: center;
      gap: 8px;
      margin: -4px 0 16px;
      color: #475569;
      font-size: 12px;
      font-weight: 750;
    }}
    .council-majority-note::before {{
      content: "";
      width: 34px;
      height: 3px;
      border-radius: 999px;
      background: var(--accent);
    }}
    .council-seat {{
      position: absolute;
      left: var(--seat-left);
      top: var(--seat-top);
      width: 74px;
      display: grid;
      justify-items: center;
      gap: 3px;
      transform: translate(-50%, -50%);
      transition: opacity 120ms ease;
    }}
    .council-seat.is-dimmed {{
      opacity: 0.24;
    }}
    .council-dot {{
      display: block;
      position: relative;
      width: 24px;
      height: 24px;
      min-width: 24px;
      padding: 0;
      box-sizing: border-box;
      border: 2px solid rgba(15, 23, 42, 0.22);
      border-radius: 999px;
      appearance: none;
      background: var(--party-color);
      color: var(--party-text);
      cursor: pointer;
      line-height: 1;
      outline: none;
      text-decoration: none;
      transition: transform 120ms ease, box-shadow 120ms ease, opacity 120ms ease;
    }}
    .council-dot:hover,
    .council-dot:focus-visible,
    .council-seat.is-focused .council-dot {{
      background: var(--party-color);
      color: var(--party-text);
      border-color: color-mix(in srgb, var(--party-color) 70%, #111827);
      transform: translateY(-2px) scale(1.08);
      box-shadow: 0 0 0 4px color-mix(in srgb, var(--party-color) 24%, transparent);
      z-index: 2;
    }}
    .council-dot::after {{
      content: attr(data-tooltip);
      position: absolute;
      left: 50%;
      bottom: calc(100% + 8px);
      transform: translateX(-50%);
      width: max-content;
      max-width: 220px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: #111827;
      color: #fff;
      padding: 7px 8px;
      font-size: 11px;
      line-height: 1.25;
      text-align: center;
      opacity: 0;
      pointer-events: none;
      transition: opacity 120ms ease;
      white-space: normal;
    }}
    .council-dot:hover::after,
    .council-dot:focus-visible::after {{
      opacity: 1;
    }}
    .council-seat-label {{
      width: 74px;
      color: #475569;
      font-size: 8px;
      font-weight: 850;
      line-height: 1.08;
      text-align: center;
      overflow-wrap: anywhere;
    }}
    .council-senate {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      justify-content: center;
      align-items: flex-start;
      margin-top: 8px;
      padding-bottom: 4px;
    }}
    .council-senate .council-seat {{
      position: static;
      left: auto;
      top: auto;
      width: 84px;
      transform: none;
    }}
    .council-senate .council-dot {{
      width: 24px;
      min-width: 24px;
      height: 42px;
      border-radius: 999px;
    }}
    .council-side {{
      display: grid;
      gap: 10px;
      min-width: 0;
    }}
    .council-histogram {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 12px;
      min-width: 0;
    }}
    .council-histogram h3 {{
      margin: 0 0 10px;
      font-size: 14px;
    }}
    .council-stage .council-histogram {{
      margin-top: 12px;
    }}
    .council-histogram-grid {{
      min-height: 220px;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(34px, 1fr));
      gap: 8px;
      align-items: end;
      padding-top: 8px;
    }}
    .council-column {{
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(110px, 1fr) auto auto;
      gap: 6px;
      align-items: end;
      justify-items: center;
      cursor: default;
    }}
    .council-column-percent {{
      color: #475569;
      font-size: 11px;
      font-weight: 850;
      line-height: 1.1;
      text-align: center;
    }}
    .council-column:hover,
    .council-column.is-focused {{
      background: color-mix(in srgb, var(--party-color) 10%, #ffffff);
    }}
    .council-column-track {{
      width: min(34px, 80%);
      height: 100%;
      min-height: 110px;
      display: flex;
      align-items: end;
      border-bottom: 1px solid var(--line-strong);
    }}
    .council-column-fill {{
      width: 100%;
      height: var(--column-height);
      min-height: 8px;
      border-radius: 7px 7px 0 0;
      background: var(--party-color);
    }}
    .council-column-label {{
      max-width: 100%;
      color: #1e293b;
      font-size: 11px;
      font-weight: 850;
      line-height: 1.1;
      text-align: center;
      overflow-wrap: anywhere;
    }}
    .council-column-value {{
      color: #1e293b;
      font-size: 12px;
      font-weight: 850;
      text-align: center;
    }}
    .council-histogram-note {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }}
    .council-faction-list {{
      display: grid;
      gap: 8px;
    }}
    .council-faction-card {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
      padding: 10px;
      transition: background 120ms ease, border-color 120ms ease;
    }}
    .council-faction-card:hover,
    .council-faction-card.is-focused {{
      border-color: color-mix(in srgb, var(--party-color) 44%, var(--line-strong));
      background: color-mix(in srgb, var(--party-color) 9%, #ffffff);
    }}
    .council-faction-top {{
      display: grid;
      grid-template-columns: 12px minmax(0, 1fr);
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }}
    .council-faction-swatch {{
      width: 12px;
      height: 12px;
      border-radius: 999px;
      background: var(--party-color);
    }}
    .council-faction-name {{
      color: #0f172a;
      font-size: 13px;
      font-weight: 850;
      overflow-wrap: anywhere;
    }}
    .council-faction-seats {{
      color: #0f172a;
      font-size: 12px;
      font-weight: 850;
      grid-column: 2;
    }}
    .council-faction-track {{
      height: 7px;
      border-radius: 999px;
      background: #e2e8f0;
      overflow: hidden;
    }}
    .council-faction-fill {{
      width: var(--faction-share);
      height: 100%;
      border-radius: inherit;
      background: var(--party-color);
    }}
    .council-faction-meta {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
    }}
    .council-links {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }}
    .council-links a {{
      width: auto;
      display: inline-flex;
      min-height: 30px;
      align-items: center;
      border: 1px solid #bfdbfe;
      border-radius: 999px;
      background: var(--accent-tint);
      color: var(--accent-dark);
      padding: 5px 10px;
      font-size: 12px;
      font-weight: 800;
      text-decoration: none;
    }}
    .council-links a:hover {{
      background: #dbeafe;
    }}
    .map-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 340px);
      gap: 10px;
      min-height: 0;
    }}
    #grazMap,
    #roadworksMap,
    #parkingMap,
    #pharmacyMap,
    #doctorsMap,
    #servicesMap {{
      height: min(62vh, 680px);
      min-height: 420px;
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #e2e8f0;
    }}
    .map-list {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
      max-height: min(62vh, 680px);
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
      padding: 7px 8px;
      text-align: left;
    }}
    .map-place:hover {{
      background: var(--accent-tint);
    }}
    .map-place strong {{
      display: block;
      font-size: 12px;
      margin-bottom: 2px;
    }}
    .map-place span {{
      color: var(--muted);
      font-size: 11px;
    }}
    .map-place small {{
      display: block;
      color: var(--muted);
      font-size: 10px;
      line-height: 1.25;
      margin-top: 2px;
    }}
    .map-place .hours {{
      color: #334155;
      white-space: normal;
    }}
    .parking-list {{
      display: block;
      padding: 0;
      background: #fbfdff;
    }}
    .parking-card {{
      width: 100%;
      border: 0;
      border-bottom: 1px solid var(--line);
      border-radius: 0;
      background: transparent;
      color: var(--ink);
      display: block;
      min-height: 0;
      min-width: 0;
      padding: 8px;
      text-align: left;
      box-shadow: none;
      line-height: 1.3;
      overflow-wrap: anywhere;
      word-break: normal;
    }}
    .parking-card:hover,
    .parking-card.active {{
      border-color: #99f6e4;
      background: #f0fdfa;
    }}
    .parking-card strong {{
      display: block;
      font-size: 12px;
      line-height: 1.25;
      margin-bottom: 3px;
      overflow-wrap: anywhere;
      min-width: 0;
    }}
    .parking-card-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 4px;
      min-width: 0;
      margin: 3px 0;
    }}
    .parking-pill {{
      display: inline-flex;
      align-items: center;
      max-width: 100%;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: #f8fafc;
      color: #475569;
      font-size: 10px;
      font-weight: 700;
      line-height: 1.25;
      padding: 2px 7px;
      overflow-wrap: anywhere;
      white-space: normal;
    }}
    .parking-address,
    .parking-note {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.3;
      overflow-wrap: anywhere;
      min-width: 0;
      white-space: normal;
      margin-top: 2px;
    }}
    .parking-card-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 5px;
      align-items: center;
      min-width: 0;
      margin-top: 6px;
    }}
    .parking-card-actions a {{
      width: auto;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 28px;
      min-width: 0;
      height: auto;
      max-width: 100%;
      border-radius: 999px;
      border: 1px solid #99f6e4;
      background: #f0fdfa;
      color: #0f766e;
      padding: 4px 9px;
      font-size: 10px;
      font-weight: 800;
      text-decoration: none;
      white-space: normal;
      overflow-wrap: anywhere;
      text-align: center;
      line-height: 1.2;
    }}
    .parking-card-actions a:hover {{
      background: #ccfbf1;
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
      font-size: 12px;
      line-height: 1.45;
    }}
    .roadwork-result-head {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      justify-content: space-between;
      gap: 8px;
      margin-bottom: 8px;
    }}
    .risk-badge {{
      display: inline-flex;
      align-items: center;
      width: auto;
      min-height: 0;
      border-radius: 999px;
      padding: 3px 8px;
      font-weight: 700;
      background: #e0f2fe;
      color: #075985;
    }}
    .risk-badge[data-risk="hoch"] {{
      background: #fee2e2;
      color: #991b1b;
    }}
    .risk-badge[data-risk="mittel"] {{
      background: #fef3c7;
      color: #92400e;
    }}
    .roadwork-result-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      margin-bottom: 8px;
    }}
    .roadwork-result-grid strong {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      margin-bottom: 2px;
    }}
    .roadwork-reasons {{
      margin: 8px 0 0;
      padding-left: 18px;
    }}
    .detour-hints {{
      margin-top: 10px;
      border: 1px solid #fde68a;
      border-radius: 8px;
      background: #fffbeb;
      padding: 9px 10px;
    }}
    .detour-hints strong {{
      display: block;
      color: #92400e;
      margin-bottom: 5px;
    }}
    .detour-hints ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .detour-streets {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin-top: 8px;
    }}
    .street-chip {{
      border: 1px solid #f59e0b;
      border-radius: 999px;
      background: #fff7ed;
      color: #92400e;
      padding: 3px 8px;
      font-size: 12px;
      cursor: help;
    }}
    .street-preview {{
      position: fixed;
      z-index: 80;
      width: 260px;
      border: 1px solid var(--line-strong);
      border-radius: 8px;
      background: white;
      box-shadow: 0 12px 28px rgba(15, 23, 42, 0.18);
      overflow: hidden;
      pointer-events: none;
    }}
    .street-preview img {{
      display: block;
      width: 100%;
      height: 150px;
      object-fit: cover;
      background: #e2e8f0;
    }}
    .street-preview div {{
      padding: 8px 10px;
      font-size: 12px;
      line-height: 1.35;
    }}
    .source-note {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 11px;
      line-height: 1.45;
    }}
    .traffic-source-panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfdff;
      margin: 10px 0 12px;
      padding: 8px 10px;
    }}
    .traffic-source-panel.pending {{
      background: #f8fafc;
      color: var(--muted);
    }}
    .traffic-source-panel summary {{
      cursor: pointer;
      font-weight: 650;
      color: #334155;
    }}
    .traffic-source-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 8px;
      margin-top: 8px;
    }}
    .traffic-source-list.compact .source-card {{
      padding: 7px 8px;
      font-size: 12px;
      background: #f8fafc;
    }}
    .traffic-source-note {{
      color: var(--muted);
      font-size: 11px;
      margin-top: 6px;
      line-height: 1.35;
    }}
    .modal {{
      width: min(760px, calc(100vw - 32px));
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 18px 55px rgba(15, 23, 42, 0.22);
      padding: 0;
      color: var(--ink);
    }}
    .modal::backdrop {{
      background: rgba(15, 23, 42, 0.38);
    }}
    .modal-head {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 14px;
      border-bottom: 1px solid var(--line);
    }}
    .modal-head h3 {{
      margin: 0;
      font-size: 16px;
    }}
    .modal-body {{
      padding: 14px;
    }}
    .secondary-button {{
      width: auto;
      background: white;
      color: var(--accent-dark);
      border-color: var(--line-strong);
    }}
    .secondary-button:hover {{
      background: var(--accent-tint);
    }}
    .password-note {{
      color: var(--muted);
      font-size: 11px;
      line-height: 1.35;
      margin: 0 0 10px;
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
    .active-filter button {{
      width: auto;
      min-height: 32px;
      padding: 5px 10px;
      font-size: 13px;
    }}
    .sr-label {{
      display: block;
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      margin-bottom: 5px;
    }}
    .filter-cell {{ min-width: 0; }}
    @media (max-width: 1280px) {{
      .app-shell {{ grid-template-columns: 190px minmax(0, 1fr); }}
      .toolbar {{
        grid-template-columns: minmax(220px, 1.2fr) repeat(3, minmax(104px, 1fr));
      }}
      .toolbar .wide {{ grid-column: span 2; }}
      .stats {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
      .map-layout {{ grid-template-columns: minmax(0, 1fr) 220px; }}
      table {{ min-width: 980px; }}
      th, td {{ padding: 7px 8px; font-size: 11px; }}
      .title {{ min-width: 200px; }}
      .results-col {{ min-width: 210px; }}
      .places-col {{ min-width: 150px; }}
      #grazMap,
      #roadworksMap,
      #parkingMap,
      #pharmacyMap,
      #doctorsMap,
      #servicesMap {{
        height: min(58vh, 620px);
        min-height: 380px;
      }}
      .map-list {{ max-height: min(58vh, 620px); }}
      .topic-filters {{ grid-template-columns: 1fr 1fr; }}
    }}
    @media (max-width: 920px) {{
      .app-shell {{ grid-template-columns: 1fr; }}
      .sidebar {{
        position: sticky;
        top: 0;
        z-index: 1000;
        height: auto;
        border-right: 0;
        border-bottom: 1px solid var(--line);
        padding: 10px 16px;
        box-shadow: 0 1px 2px rgba(15, 23, 42, 0.06);
      }}
      .brand {{
        padding-bottom: 0;
        margin-bottom: 0;
        border-bottom: 0;
      }}
      .brand-title {{ font-size: 22px; }}
      .mobile-nav-toggle {{ display: inline-flex; }}
      .side-nav {{
        display: none;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        margin: 10px 0 0;
        padding-top: 10px;
        border-top: 1px solid var(--line);
      }}
      .sidebar.nav-open .side-nav {{ display: grid; }}
      header, main {{ padding-left: 16px; padding-right: 16px; }}
      .toolbar {{ grid-template-columns: 1fr; }}
      .map-layout {{ grid-template-columns: 1fr; }}
      .council-layout {{ grid-template-columns: 1fr; }}
      .council-kpis {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
      .council-dots {{ height: 320px; }}
      table {{ min-width: 0; }}
      .table-card {{
        border: 0;
        background: transparent;
        box-shadow: none;
        overflow: visible;
      }}
      #grazMap,
      #roadworksMap,
      #parkingMap,
      #pharmacyMap,
      #doctorsMap,
      #servicesMap {{
        height: 52vh;
        min-height: 320px;
      }}
      .map-list {{ max-height: 260px; }}
      .toolbar .wide {{ grid-column: auto; }}
      .stats {{ grid-template-columns: repeat(2, minmax(130px, 1fr)); }}
      .detail-grid {{ grid-template-columns: 1fr; }}
      th {{ position: static; }}
      table, thead, tbody, tr, th, td {{ display: block; }}
      thead {{ display: none; }}
      tr {{
        position: relative;
        display: grid;
        gap: 6px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: var(--panel);
        box-shadow: var(--shadow);
        padding: 10px;
        margin-bottom: 10px;
        cursor: pointer;
      }}
      tr:hover td,
      tbody tr.selected-record td {{
        background: transparent;
      }}
      tbody tr.selected-record {{
        border-color: #bfdbfe;
        background: var(--accent-tint);
      }}
      td {{
        display: grid;
        grid-template-columns: 92px minmax(0, 1fr);
        gap: 8px;
        align-items: start;
        border-bottom: 0;
        padding: 0;
        font-size: 12px;
        line-height: 1.35;
        overflow-wrap: anywhere;
      }}
      .mobile-card-only {{ display: grid; }}
      td::before {{
        content: attr(data-label);
        display: block;
        color: var(--muted);
        font-size: 12px;
        margin: 0;
        font-weight: 650;
      }}
      td[data-label="Statuspunkt"] {{ display: none; }}
      td[data-label="Titel"] {{
        order: -10;
        display: block;
        font-size: 14px;
        line-height: 1.35;
        margin-bottom: 2px;
      }}
      td[data-label="Titel"]::before {{ display: none; }}
      td[data-label="Status"] {{ order: -9; }}
      td[data-label="Datum"] {{ order: -8; }}
      td[data-label="Typ"] {{ order: -7; }}
      td[data-label="Stk."] {{ order: -6; }}
      td[data-label="Geschäftszahl"] {{ order: -5; }}
      td[data-label="Orte"] {{ order: -4; }}
      td[data-label="Beträge"] {{ order: -3; }}
      td[data-label="Einbringer"] {{ order: -2; }}
      td[data-label="Zusammenfassung"] {{
        order: -1;
        display: block;
        padding-top: 4px;
        border-top: 1px solid var(--line);
      }}
      td[data-label="Zusammenfassung"]::before {{
        margin-bottom: 4px;
      }}
      td[data-label="Ergebnis"] {{ order: 0; }}
      td[data-label="Quelle"] {{ order: 1; }}
      .title {{ min-width: 0; }}
      .title .badge {{
        margin-top: 6px;
        white-space: normal;
      }}
      .amount-col,
      .places-col,
      .status-col,
      .results-col {{
        width: auto;
        min-width: 0;
        max-width: none;
      }}
    }}
    @media (max-width: 560px) {{
      body {{ font-size: 12px; }}
      header, main {{ padding-left: 10px; padding-right: 10px; }}
      .sidebar {{ padding: 10px; }}
      .brand-title {{ font-size: 20px; }}
      .mobile-nav-toggle {{
        width: 32px;
        height: 32px;
        min-height: 32px;
      }}
      .side-nav {{ grid-template-columns: 1fr; }}
      .side-item {{
        min-height: 40px;
        padding: 9px 10px;
      }}
      .council-kpis {{ grid-template-columns: 1fr; }}
      .council-dots {{ height: 280px; }}
      .council-seat {{ width: 58px; }}
      .council-seat-label {{ width: 58px; font-size: 7px; }}
      .question-row {{ grid-template-columns: 1fr; }}
      .split-form {{ grid-template-columns: 1fr; }}
      .stats {{ grid-template-columns: 1fr; }}
      #grazMap,
      #roadworksMap,
      #parkingMap,
      #pharmacyMap,
      #doctorsMap,
      #servicesMap {{
        height: 54vh;
        min-height: 300px;
      }}
      .global-ai-disclaimer {{
        left: 10px;
        right: 10px;
        bottom: 10px;
        padding: 8px 10px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.96);
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.12);
      }}
      .ai-disclaimer {{
        padding: 8px 10px;
        border: 1px solid var(--line);
        border-radius: 8px;
        background: #f8fafc;
      }}
    }}
  </style>
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <div class="brand">
        <span class="brand-title">Graz</span>
        <button class="mobile-nav-toggle" id="mobileNavToggle" type="button" aria-controls="sideNav" aria-expanded="false" aria-label="Navigation öffnen">
          <span class="mobile-nav-icon" aria-hidden="true"><span></span><span></span><span></span></span>
        </button>
      </div>
      <nav class="side-nav" id="sideNav" aria-label="Ansichten">
        <button class="side-item active" type="button" data-nav="start">Start</button>
        <button class="side-item" type="button" data-nav="search">Suche</button>
        <button class="side-item" type="button" data-nav="participation">Mitreden</button>
        <button class="side-item" type="button" data-nav="map">Karte</button>
        <button class="side-item" type="button" data-nav="council">Gemeinderat</button>
        <button class="side-item" type="button" data-nav="services">Services & Ämter</button>
        <button class="side-item" type="button" data-nav="roadworks">Baustellen</button>
        <button class="side-item" type="button" data-nav="parking">Tiefgaragen</button>
        <button class="side-item" type="button" data-nav="pharmacies">Apotheken</button>
        <button class="side-item" type="button" data-nav="doctors">Ärzte</button>
      </nav>
    </aside>
    <div class="content-shell">
      <header>
        <h1 id="viewTitle">Start</h1>
      </header>
      <main>
        <section class="toolbar" id="searchSection" aria-label="Filter" hidden>
          <label class="filter-cell wide"><span class="sr-label">Suche</span><input id="search" type="search" list="globalSuggestions" placeholder="Thema, Straße, Geschäftszahl, Betrag"></label>
          <label class="filter-cell"><span class="sr-label">Jahr</span><select id="yearFilter"><option value="">Alle Jahre</option></select></label>
          <label class="filter-cell"><span class="sr-label">Datum</span><select id="dateFilter"><option value="">Alle Daten</option></select></label>
          <label class="filter-cell"><span class="sr-label">Typ</span><select id="typeFilter"><option value="">Alle Typen</option><option value="Tagesordnungspunkt">Tagesordnungspunkt</option><option value="Mitteilung">Mitteilung</option><option value="Fragestunde">Fragestunde</option><option value="Dringlichkeitsantrag">Dringlichkeitsantrag</option><option value="Schriftliche Anfrage">Schriftliche Anfrage</option><option value="Schriftlicher Antrag">Schriftlicher Antrag</option><option value="Archiv-Tagesordnungspunkt">Archiv-Tagesordnungspunkt</option><option value="Archivquelle">Archivquelle</option><option value="Anwesenheitsliste">Anwesenheitsliste</option></select></label>
          <label class="filter-cell"><span class="sr-label">Status</span><select id="statusFilter"><option value="">Alle Status</option></select></label>
          <label class="filter-cell"><span class="sr-label">Thema</span><select id="categoryFilter"><option value="">Alle Themen</option></select></label>
          <label class="filter-cell"><span class="sr-label">Ergebnisquelle</span><select id="sourceFilter"><option value="">Alle Quellen</option></select></label>
          <label class="filter-cell"><span class="sr-label">Beträge</span><select id="amountFilter"><option value="">Alle Beträge</option><option value="mit">Mit Betrag</option><option value="ohne">Ohne Betrag</option></select></label>
        </section>
        <datalist id="globalSuggestions"></datalist>
        <datalist id="locationSuggestions"></datalist>
        <div class="active-filter" id="topicFilterNotice">
          <span id="topicFilterText">Themenfilter aktiv.</span>
          <button id="clearTopicFilter" type="button">Zurücksetzen</button>
        </div>
        <div class="active-filter archive-notice" id="archiveNotice">
          <span>Ältere Archivtreffer stammen nicht aus DIGRA. Die automatische Erkennung kann unvollständig sein, besonders wenn ein Archiv-PDF mehrere Stücke enthält. Bitte die verlinkte Originalquelle prüfen.</span>
        </div>
        <section class="tab-panel active start-panel" id="startPanel">
          <div class="question-box">
            <h2>Wobei kann ich behilflich sein?</h2>
            <div class="question-row">
              <div class="question-input-wrap">
                <input id="aiQuestion" type="search" autocomplete="off" aria-autocomplete="list" aria-controls="aiQuestionSuggestions" aria-expanded="false" placeholder="Welche Beschlüsse und Baustellen betreffen 2026 die Kärntner Straße?">
                <div class="question-suggestions" id="aiQuestionSuggestions" role="listbox" hidden></div>
              </div>
              <button id="aiAsk" type="button">Fragen</button>
            </div>
            <div class="question-tabs" id="aiResultTabs" hidden>
              <div class="question-tab-buttons" role="tablist" aria-label="Antwortbereich">
                <button class="question-tab-button active" type="button" role="tab" aria-selected="true" data-question-result-tab="answer">Antwort</button>
                <button class="question-tab-button" type="button" role="tab" aria-selected="false" data-question-result-tab="sources">Quellen</button>
              </div>
              <div class="question-tab-panel" id="aiAnswerPanel" role="tabpanel">
                <div class="question-result" id="aiAnswer" hidden></div>
              </div>
              <div class="question-tab-panel" id="aiSourcesPanel" role="tabpanel" hidden>
                <div class="question-sources" id="aiSources" hidden></div>
              </div>
            </div>
            <div class="ai-disclaimer">KI-generierte Antworten können Fehler enthalten. Bitte immer die Quellen prüfen.</div>
          </div>
        </section>
        <section class="tab-panel" id="searchPanel">
          <div class="search-subtabs" role="tablist" aria-label="Suchansicht">
            <button class="search-subtab active" type="button" role="tab" aria-selected="true" data-search-subtab="table">Filter & Tabelle</button>
            <button class="search-subtab" type="button" role="tab" aria-selected="false" data-search-subtab="details">Eintragsdetails</button>
            <button class="search-subtab" type="button" role="tab" aria-selected="false" data-search-subtab="summary">Gesamtzusammenfassung</button>
          </div>
          <div class="search-subpanel" id="searchTablePanel">
            <div id="tableWrap"></div>
          </div>
          <div class="search-subpanel" id="searchDetailPanel" hidden>
            <section class="detail" id="detailWrap"></section>
          </div>
          <div class="search-subpanel" id="searchSummaryPanel" hidden>
            <section class="detail date-summary-detail" id="dateSummaryWrap" hidden></section>
          </div>
        </section>
        <section class="tab-panel" id="participationPanel">
          <div class="participation-banner">
            <h2>Bürgerfeedback zu angekündigten Stücken</h2>
            <p>Diese Seite ist ein lokales Meinungsbild. Sie ist nicht amtlich, nicht verbindlich und ersetzt keine Gemeinderatsentscheidung.</p>
            <p>Rückmeldungen werden in dieser Demo nur in diesem Browser gespeichert und nicht an einen Server gesendet.</p>
          </div>
          <div class="participation-layout">
            <section class="participation-list" id="participationList" aria-label="Stücke zum Mitreden"></section>
            <section class="participation-detail" id="participationDetail" aria-label="Rückmeldung"></section>
          </div>
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
            <div class="map-head-main">
              <h2>Baustellen</h2>
              <div class="map-status" id="roadworksStatus">Öffentliche Baustelleninfos der Stadt Graz.</div>
            </div>
          </div>
          <div class="map-progress" id="roadworksProgress" aria-hidden="true">
            <div class="map-progress-bar" id="roadworksProgressBar"></div>
          </div>
          <div class="map-legend" id="roadworksLegend" aria-label="Baustellenstatus"></div>
          <div class="map-layout">
            <div id="roadworksMap" aria-label="Karte für Baustellenplanung"></div>
            <div class="map-list" id="roadworksList"></div>
          </div>
          <div class="source-note" id="roadworksSourceNote"></div>
        </section>
        <section class="tab-panel map-panel" id="councilPanel">
          <div class="map-head">
            <div class="map-head-main">
              <h2>Gemeinderat</h2>
              <div class="map-status" id="councilStatus">Sitzverteilung und Stadtregierungsmitglieder laut offiziellen Stadt-Graz-Seiten.</div>
            </div>
            <div class="map-actions">
              <a class="primary-link" href="https://www.graz.at/cms/beitrag/10379731/7768104/Gemeinderat_Mitglieder.html" target="_blank" rel="noopener noreferrer">Mitglieder öffnen</a>
              <a class="primary-link" href="https://www.graz.at/cms/ziel/7765844/DE/" target="_blank" rel="noopener noreferrer">Stadtregierungsmitglieder öffnen</a>
            </div>
          </div>
          <div class="council-layout">
            <div class="council-stage">
              <div class="council-kpis" id="councilKpis"></div>
              <div class="council-header">
                <h3>Sitzverteilung</h3>
                <div class="council-summary" id="councilSummary"></div>
              </div>
              <div class="council-dots" id="councilDots" aria-label="Sitzverteilung im Gemeinderat"></div>
              <div class="council-majority-note" id="councilMajorityNote"></div>
              <div class="council-header">
                <h3>Stadtregierungsmitglieder nach Fraktionen</h3>
                <div class="council-summary" id="senateSummary"></div>
              </div>
              <div class="council-senate" id="senateDots" aria-label="Stadtregierungsmitglieder nach Fraktionen"></div>
              <div id="councilMandates"></div>
              <div class="council-links" id="councilLinks"></div>
            </div>
            <div class="council-side" id="councilLegend"></div>
          </div>
          <div class="source-note" id="councilSourceNote"></div>
        </section>
        <section class="tab-panel map-panel" id="parkingPanel">
          <div class="map-head">
            <h2>Tiefgaragen</h2>
            <div class="map-status" id="parkingStatus">Verfügbarkeit: unbekannt.</div>
          </div>
          <div class="map-progress" id="parkingProgress" aria-hidden="true">
            <div class="map-progress-bar" id="parkingProgressBar"></div>
          </div>
          <div class="map-layout">
            <div id="parkingMap" aria-label="Karte mit Tiefgaragen und Parkhäusern"></div>
            <div class="map-list" id="parkingList"></div>
          </div>
          <div class="source-note" id="parkingSourceNote"></div>
        </section>
        <section class="tab-panel map-panel" id="pharmaciesPanel">
          <div class="map-head">
            <div class="map-head-main">
              <h2>Apotheken</h2>
              <div class="map-status" id="pharmacyStatus">OSM-Standorte; Nachtdienste offiziell prüfen.</div>
            </div>
            <div class="map-actions">
              <a class="primary-link" href="https://www.apothekerkammer.at/apothekensuche" target="_blank" rel="noopener noreferrer">Nachtdienst öffnen</a>
            </div>
          </div>
          <div class="map-progress" id="pharmacyProgress" aria-hidden="true">
            <div class="map-progress-bar" id="pharmacyProgressBar"></div>
          </div>
          <div class="map-layout">
            <div id="pharmacyMap" aria-label="Karte mit Apotheken"></div>
            <div class="map-list" id="pharmacyList"></div>
          </div>
          <div class="source-note" id="pharmacySourceNote"></div>
        </section>
        <section class="tab-panel map-panel" id="doctorsPanel">
          <div class="map-head">
            <div class="map-head-main">
              <h2>Ärzte</h2>
              <div class="map-status" id="doctorsStatus">OSM-Ordinationsstandorte; Zeiten offiziell prüfen.</div>
            </div>
            <div class="map-actions">
              <a class="primary-link" href="https://ordinationen.st/" target="_blank" rel="noopener noreferrer">Ordinationen.st öffnen</a>
            </div>
          </div>
          <div class="map-progress" id="doctorsProgress" aria-hidden="true">
            <div class="map-progress-bar" id="doctorsProgressBar"></div>
          </div>
          <section class="toolbar" aria-label="Ärztefilter">
            <label class="filter-cell"><span class="sr-label">Fachrichtung</span><select id="doctorsProfessionFilter"><option value="Allgemeinmedizin">Allgemeinmedizin</option></select></label>
          </section>
          <div class="map-layout">
            <div id="doctorsMap" aria-label="Karte mit Ordinationen"></div>
            <div class="map-list" id="doctorsList"></div>
          </div>
          <div class="source-note" id="doctorsSourceNote"></div>
        </section>
        <section class="tab-panel map-panel" id="servicesPanel">
          <div class="map-head">
            <div class="map-head-main">
              <h2>Services & Ämter</h2>
              <div class="map-status" id="servicesStatus">Offizielle Servicepunkte und Ämter der Stadt Graz.</div>
            </div>
            <div class="map-actions">
              <a class="primary-link" href="https://www.graz.at/cms/beitrag/10019383/7743948/Aemter_und_Politik.html" target="_blank" rel="noopener noreferrer">Ämterverzeichnis öffnen</a>
              <a class="primary-link" href="https://www.graz.at/termine" target="_blank" rel="noopener noreferrer">Termine prüfen</a>
            </div>
          </div>
          <section class="toolbar" aria-label="Servicefilter">
            <label class="filter-cell"><span class="sr-label">Service suchen</span><input id="servicesSearch" type="search" placeholder="Amt, Thema oder Adresse"></label>
            <label class="filter-cell"><span class="sr-label">Kategorie</span><select id="servicesCategoryFilter"><option value="">Alle Kategorien</option></select></label>
          </section>
          <div class="map-layout">
            <div id="servicesMap" aria-label="Karte mit Servicepunkten und Ämtern"></div>
            <div class="map-list" id="servicesList"></div>
          </div>
          <div class="source-note" id="servicesSourceNote"></div>
        </section>
      </main>
    </div>
  </div>
  <div class="global-ai-disclaimer">KI-generierte Inhalte können Fehler enthalten. Bitte immer Quellen prüfen.</div>
  <div class="civic-modal" id="civicFeedbackModal" role="dialog" aria-modal="true" aria-labelledby="civicFeedbackModalTitle">
    <div class="civic-modal-card">
      <h2 id="civicFeedbackModalTitle">Neue Stücke vor der Sitzung</h2>
      <p id="civicFeedbackModalText">Zu angekündigten Gemeinderatsstücken kann lokal ein Meinungsbild erfasst werden.</p>
      <p>Die Rückmeldung bleibt in dieser Demo in deinem Browser. Sie ist nicht amtlich und nicht verbindlich.</p>
      <div class="civic-modal-actions">
        <button class="secondary-button" id="civicFeedbackLater" type="button">Später</button>
        <button id="civicFeedbackOpen" type="button">Zur Mitreden-Seite</button>
      </div>
    </div>
  </div>
  <script>
    const records = {data};
    const summary = {summary_data};
    const topics = {topics_data};
    const parkingGarages = {parking_data};
    const officialRoadworks = {roadworks_data};
    const pharmacies = {pharmacies_data};
    const doctors = {doctors_data};
    const civicServices = {civic_services_data};
    const civicCouncil = {civic_council_data};
    const mobilitySources = {mobility_data};
    const preloadedLocationCache = {location_cache_data};
    const byId = (id) => document.getElementById(id);
    const search = byId('search');
    const yearFilter = byId('yearFilter');
    const dateFilter = byId('dateFilter');
    const typeFilter = byId('typeFilter');
    const statusFilter = byId('statusFilter');
    const categoryFilter = byId('categoryFilter');
    const sourceFilter = byId('sourceFilter');
    const amountFilter = byId('amountFilter');
    const searchSection = byId('searchSection');
    const tableWrap = byId('tableWrap');
    const dateSummaryWrap = byId('dateSummaryWrap');
    const searchTablePanel = byId('searchTablePanel');
    const searchDetailPanel = byId('searchDetailPanel');
    const searchSummaryPanel = byId('searchSummaryPanel');
    const detailWrap = byId('detailWrap');
    const participationList = byId('participationList');
    const participationDetail = byId('participationDetail');
    const civicFeedbackModal = byId('civicFeedbackModal');
    const civicFeedbackModalText = byId('civicFeedbackModalText');
    const civicFeedbackOpen = byId('civicFeedbackOpen');
    const civicFeedbackLater = byId('civicFeedbackLater');
    const aiQuestion = byId('aiQuestion');
    const aiQuestionSuggestions = byId('aiQuestionSuggestions');
    const aiAsk = byId('aiAsk');
    const aiResultTabs = byId('aiResultTabs');
    const aiAnswerPanel = byId('aiAnswerPanel');
    const aiSourcesPanel = byId('aiSourcesPanel');
    const aiAnswer = byId('aiAnswer');
    const aiSources = byId('aiSources');
    const mapStatus = byId('mapStatus');
    const mapProgress = byId('mapProgress');
    const mapProgressBar = byId('mapProgressBar');
    const mapLegend = byId('mapLegend');
    const mapPlaces = byId('mapPlaces');
    const roadworksStatus = byId('roadworksStatus');
    const roadworksProgress = byId('roadworksProgress');
    const roadworksProgressBar = byId('roadworksProgressBar');
    const roadworksLegend = byId('roadworksLegend');
    const roadworksList = byId('roadworksList');
    const trafficSourceList = byId('trafficSourceList');
    const parkingStatus = byId('parkingStatus');
    const parkingProgress = byId('parkingProgress');
    const parkingProgressBar = byId('parkingProgressBar');
    const parkingList = byId('parkingList');
    const pharmacyStatus = byId('pharmacyStatus');
    const pharmacyProgress = byId('pharmacyProgress');
    const pharmacyProgressBar = byId('pharmacyProgressBar');
    const pharmacyList = byId('pharmacyList');
    const doctorsStatus = byId('doctorsStatus');
    const doctorsProgress = byId('doctorsProgress');
    const doctorsProgressBar = byId('doctorsProgressBar');
    const doctorsList = byId('doctorsList');
    const doctorsProfessionFilter = byId('doctorsProfessionFilter');
    const councilStatus = byId('councilStatus');
    const councilKpis = byId('councilKpis');
    const councilSummary = byId('councilSummary');
    const councilMajorityNote = byId('councilMajorityNote');
    const senateSummary = byId('senateSummary');
    const councilDots = byId('councilDots');
    const senateDots = byId('senateDots');
    const councilLegend = byId('councilLegend');
    const councilMandates = byId('councilMandates');
    const councilLinks = byId('councilLinks');
    const servicesStatus = byId('servicesStatus');
    const servicesSearch = byId('servicesSearch');
    const servicesCategoryFilter = byId('servicesCategoryFilter');
    const servicesList = byId('servicesList');
    const topicFilterNotice = byId('topicFilterNotice');
    const topicFilterText = byId('topicFilterText');
    const clearTopicFilter = byId('clearTopicFilter');
    const archiveNotice = byId('archiveNotice');
    const viewTitle = byId('viewTitle');
    const sidebar = document.querySelector('.sidebar');
    const mobileNavToggle = byId('mobileNavToggle');
    const digraMatchedCount = byId('digraMatchedCount');
    const digraFallbackCount = byId('digraFallbackCount');
    const cityLinkCount = byId('cityLinkCount');
    const digraMissingCount = byId('digraMissingCount');
    const exportCsvButton = byId('exportCsv');
    const exportJsonButton = byId('exportJson');
    const exportRoadworksJsonButton = byId('exportRoadworksJson');
    const exportRoadworksCsvButton = byId('exportRoadworksCsv');
    const exportRoadworksIcsButton = byId('exportRoadworksIcs');
    const exportRoadworksRssButton = byId('exportRoadworksRss');
    const subscriptionStreet = byId('subscriptionStreet');
    const subscriptionDistrict = byId('subscriptionDistrict');
    const subscriptionStart = byId('subscriptionStart');
    const subscriptionEnd = byId('subscriptionEnd');
    const feedbackText = byId('feedbackText');
    const saveSubscriptionButton = byId('saveSubscription');
    const saveFeedbackButton = byId('saveFeedback');
    const exportSubscriptionsButton = byId('exportSubscriptions');
    const exportFeedbackButton = byId('exportFeedback');
    const subscriptionStatus = byId('subscriptionStatus');
    const subscriptionList = byId('subscriptionList');
    let sichtbareEintraege = [];
    let ausgewaehlterEintrag = null;
    let grazMap = null;
    let markerLayer = null;
    let roadworksMap = null;
    let roadworksLayer = null;
    let parkingMap = null;
    let parkingLayer = null;
    let pharmacyMap = null;
    let pharmacyLayer = null;
    let doctorsMap = null;
    let doctorsLayer = null;
    let servicesMap = null;
    let servicesLayer = null;
    const markersByLocation = new Map();
    const markerCacheByLocation = new Map();
    const coordsByLocation = new Map();
    const geocodePromisesByLocation = new Map();
    let highlightedLocations = new Set();
    let currentLocationIndex = buildLocationIndex(records);
    const subscriptionKey = 'grazViewerRoadworkSubscriptions';
    const feedbackKey = 'grazViewerRoadworkFeedback';
    const civicFeedbackKey = 'grazViewerCivicFeedbackV1';
    const civicFeedbackPopupKey = 'grazViewerCivicFeedbackPopupDismissedV1';
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
    let activeTabName = 'start';
    let lastMarkerLocationKey = '';
    let markerLoadRun = 0;
    let lastMapPlacesKey = '';
    let activeTopicRecordIds = null;
    let activeTopicLabel = '';
    let activeSearchSubtab = 'table';
    let selectedParticipationRecordId = '';
    const searchSubtabScroll = {{ table: 0, details: 0, summary: 0 }};
    let currentParkingGarages = [];
    let currentRoadworks = [];
    let activePharmacies = pharmacies;
    let activeDoctors = doctors;
    let currentPharmacyPlaces = activePharmacies;
    let currentDoctorPlaces = activeDoctors;
    let currentCivicServices = civicServices;
    let questionSuggestionValues = [];
    let councilRendered = false;
    const pharmacyFallbackPlaces = [
      {{ name: 'Adler Apotheke Graz', address: 'Hauptplatz 4, 8010 Graz', kind: 'Apotheke', profession: 'Apotheke', lat: 47.0707, lon: 15.4388, opening_hours: '', website: 'https://www.apothekerkammer.at/apothekensuche', source: 'lokaler Prüffallback', license: 'nur Standort-Hinweis' }},
      {{ name: 'Apotheke zum schwarzen Bären', address: 'Herrengasse 11, 8010 Graz', kind: 'Apotheke', profession: 'Apotheke', lat: 47.0697, lon: 15.4399, opening_hours: '', website: 'https://www.apothekerkammer.at/apothekensuche', source: 'lokaler Prüffallback', license: 'nur Standort-Hinweis' }},
      {{ name: 'Annen-Apotheke', address: 'Annenstraße 42, 8020 Graz', kind: 'Apotheke', profession: 'Apotheke', lat: 47.0718, lon: 15.4254, opening_hours: '', website: 'https://www.apothekerkammer.at/apothekensuche', source: 'lokaler Prüffallback', license: 'nur Standort-Hinweis' }},
      {{ name: 'LKH Apotheke Umgebung', address: 'Stiftingtalstraße 24, 8010 Graz', kind: 'Apotheke', profession: 'Apotheke', lat: 47.0815, lon: 15.4685, opening_hours: '', website: 'https://www.apothekerkammer.at/apothekensuche', source: 'lokaler Prüffallback', license: 'nur Standort-Hinweis' }},
      {{ name: 'Apotheke Puntigam', address: 'Triester Straße 367, 8055 Graz', kind: 'Apotheke', profession: 'Apotheke', lat: 47.0337, lon: 15.4235, opening_hours: '', website: 'https://www.apothekerkammer.at/apothekensuche', source: 'lokaler Prüffallback', license: 'nur Standort-Hinweis' }},
    ];
    let activeRoadworkStatus = '';
    const roadworkStatusLabels = {{
      aktuell: 'Aktuell',
      kuenftig: 'Künftig',
      abgeschlossen: 'Abgeschlossen',
      unklar: 'Unklar'
    }};
    const roadworkStatusColors = {{
      aktuell: '#dc2626',
      kuenftig: '#2563eb',
      abgeschlossen: '#64748b',
      unklar: '#7c3aed'
    }};
    const tableRenderLimit = 350;
    const roadworkFallbackCoords = [
      [/autaler straße/i, [47.022, 15.512], 'Autaler Straße, Abschnitt km 0,0 bis 3,1'],
      [/anton-leb-gasse|hilmteichstraße.*anton/i, [47.0806, 15.4586], 'Anton-Leb-Gasse / Hilmteichstraße'],
      [/hilmteichstraße.*mariatroster|mariatroster.*hilmgasse/i, [47.0828, 15.4576], 'Hilmteichstraße zwischen Mariatroster Straße und Hilmgasse'],
      [/göstinger straße 33/i, [47.0955, 15.4065], 'Göstinger Straße 33'],
      [/karl-morre-straße.*82a/i, [47.0669, 15.4107], 'Karl-Morre-Straße 82a'],
      [/kärntner straße 163/i, [47.041, 15.409], 'Kärntner Straße 163'],
      [/kärntner straße.*209/i, [47.033, 15.402], 'Kärntner Straße 209'],
      [/liebenauer hauptstraße.*puntigamer|karl-huber-gasse/i, [47.0308, 15.4467], 'Liebenauer Hauptstraße bei Karl-Huber-Gasse/Puntigamer Straße'],
      [/mariatroster straße 132/i, [47.101, 15.489], 'Mariatroster Straße 132'],
      [/peter-rosegger-straße 25/i, [47.054, 15.395], 'Peter-Rosegger-Straße 25'],
      [/peter-tunner-gasse/i, [47.079, 15.423], 'Peter-Tunner-Gasse zwischen Lastenstraße und Waagner-Biro-Straße'],
      [/plabutscher straße 47/i, [47.072, 15.388], 'Plabutscher Straße 47'],
      [/puntigamer straße.*herrgottwiesgasse|puntigamer brücke/i, [47.0318, 15.4265], 'Puntigamer Straße zwischen Puntigamer Brücke und Herrgottwiesgasse'],
      [/radegunder straße.*hans-auer-gasse|hans-auer-gasse/i, [47.106, 15.455], 'Radegunder Straße / Hans-Auer-Gasse'],
      [/rudersdorfer straße 58/i, [47.021, 15.426], 'Rudersdorfer Straße 58'],
      [/triester straße 25|triester straße.*30/i, [47.058, 15.433], 'Triester Straße 25 bis 30, ÖBB-Unterführung'],
      [/ulrich-lichtenstein-gasse.*ivica|ivica-osim-platz/i, [47.0437, 15.4547], 'Ulrich-Lichtenstein-Gasse bei Ivica-Osim-Platz'],
      [/ulrich-lichtenstein-gasse.*eisenbahnkreuzung|eisenbahnkreuzung öbb/i, [47.0424, 15.4548], 'Ulrich-Lichtenstein-Gasse, Eisenbahnkreuzung ÖBB'],
      [/wiener straße 159/i, [47.092, 15.413], 'Wiener Straße 159'],
      [/wiener straße 247|wiener straße 253/i, [47.105, 15.404], 'Wiener Straße 247 bis 253'],
    ];
    const parkingAvailabilityHints = [
      {{ pattern: /orpheum/i, text: 'Live-Verfügbarkeit extern bei Parken.at prüfen', url: 'https://www.parken.at/garage/1104/' }},
      {{ pattern: /gkb|köflacher/i, text: 'Live-Verfügbarkeit extern bei Parken.at prüfen', url: 'https://www.parken.at/garage/4390/' }},
      {{ pattern: /operngarage|opernring|hamerlinggasse/i, text: 'Live-Verfügbarkeit extern bei Parken.at prüfen', url: 'https://www.parken.at/garage/1057/' }},
      {{ pattern: /annenpassage|bahnhofgürtel|bahnhofguertel/i, text: 'Live-Verfügbarkeit extern bei Parken.at prüfen', url: 'https://www.parken.at/garage/1105/' }},
      {{ pattern: /bahnhof|europaplatz/i, text: 'Live-Verfügbarkeit extern bei Parken.at prüfen', url: 'https://www.parken.at/garage/1053/' }},
    ];
    const parkingDetailLinks = [
      {{ pattern: /orpheum/i, url: 'https://www.parken.at/garage/1104/', label: 'Parken.at Orpheum' }},
      {{ pattern: /operngarage|opernring|hamerlinggasse/i, url: 'https://www.parken.at/garage/1057/', label: 'Parken.at Operngarage' }},
      {{ pattern: /kastner|öhler|oehler|kaiser-franz-josef-kai/i, url: 'https://www.kastner-oehler.at/service/parken/', label: 'Kastner & Öhler Parken' }},
      {{ pattern: /annenpassage|bahnhofgürtel|bahnhofguertel/i, url: 'https://www.parken.at/garage/1105/', label: 'Parken.at Annenpassage' }},
      {{ pattern: /bahnhof|europaplatz/i, url: 'https://www.parken.at/garage/1053/', label: 'Parken.at Bahnhof' }},
      {{ pattern: /gkb|köflacher/i, url: 'https://www.parken.at/garage/4390/', label: 'Parken.at Köflacher Gasse' }},
      {{ pattern: /citypark|lazarettgürtel|lazarettguertel/i, url: 'https://www.citypark.at/de/nutzungsbedingungen-parken/', label: 'CITYPARK Parkinfo' }},
      {{ pattern: /lkh|stiftingtal/i, url: 'https://www.data.gv.at/katalog/dataset/92183c55-442b-405d-9046-d19b07ffc83a', label: 'OGD Parkgarage LKH' }},
      {{ pattern: /stadion|liebenau/i, url: 'https://www.granit-immobilien.at/stadiongarage/', label: 'Stadiongarage öffnen' }},
      {{ pattern: /brauquartier/i, url: 'https://www.cp-ag.at/cp-produkte/hochgarage-brauquartier-puntigam/', label: 'Brauquartier Parkinfo' }},
      {{ pattern: /gate17|triester/i, url: 'https://www.cp-ag.at/blog/2020/08/06/gate-17-triester-strasse-432-8055-graz/', label: 'GATE 17 öffnen' }},
      {{ pattern: /andreas-hofer/i, url: 'https://www.contipark.at/de/parken/graz/tiefgarage-andreas-hofer-platz/', label: 'Contipark Andreas-Hofer-Platz' }},
      {{ pattern: /dominikaner/i, url: 'https://www.contipark.at/de/parken/graz/', label: 'Contipark Graz' }},
      {{ pattern: /lendplatz/i, url: 'https://www.contipark.at/de/parken/graz/', label: 'Contipark Graz' }},
      {{ pattern: /st\\. peter|st peter/i, url: 'https://www.apcoa.at/kurzparken/standorte/graz/st-peter-hauptstrasse-graz-apcoa', label: 'APCOA St. Peter Hauptstraße' }},
      {{ pattern: /josef-pongratz/i, url: 'https://www.apcoa.at/kurzparken/standorte/graz/josef-pongratz-platz-graz-apcoa', label: 'APCOA Josef-Pongratz-Platz' }},
      {{ pattern: /rosegger/i, url: 'https://www.apcoa.at/kurzparken/standorte/graz/roseggerhaus-graz-apcoa', label: 'APCOA Roseggerhaus' }},
      {{ pattern: /eggenberger/i, url: 'https://www.apcoa.at/kurzparken/standorte/graz/eggenberger-guertel-graz', label: 'APCOA Eggenberger Gürtel' }},
      {{ pattern: /babenberger/i, url: 'https://www.apcoa.at/kurzparken/standorte/graz/babenbergerstrasse-graz-apcoa', label: 'APCOA Babenbergerstraße' }},
      {{ pattern: /airport|flughafen/i, url: 'https://www.apcoa.at/airport-graz', label: 'APCOA Graz Airport' }},
    ];
    const supplementalParkingGarages = [
      {{ name: 'TG St. Peter Hauptstraße', address: 'St. Peter Hauptstraße, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'APCOA Graz Standortseite', source_url: 'https://www.apcoa.at/graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'TG Josef-Pongratz-Platz', address: 'Josef-Pongratz-Platz, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'APCOA Graz Standortseite', source_url: 'https://www.apcoa.at/graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PH Citypark A+C', address: 'Lazarettgürtel 55, Graz', kind: 'Parkhaus', availability: 'unbekannt', source: 'APCOA/CITYPARK Standortseiten', source_url: 'https://www.citypark.at/de/nutzungsbedingungen-parken/', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PH Citypark B', address: 'Lazarettgürtel 55, Graz', kind: 'Parkhaus', availability: 'unbekannt', source: 'APCOA/CITYPARK Standortseiten', source_url: 'https://www.citypark.at/de/nutzungsbedingungen-parken/', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'TG Roseggerhaus', address: 'Roseggerhaus, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'APCOA Graz Standortseite', source_url: 'https://www.apcoa.at/graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'TG Eggenberger Gürtel', address: 'Eggenberger Gürtel, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'APCOA Graz Standortseite', source_url: 'https://www.apcoa.at/graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'TG Babenbergerstraße', address: 'Babenbergerstraße, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'APCOA Graz Standortseite', source_url: 'https://www.apcoa.at/graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PP Graz Airport P0', address: 'Graz Airport, Feldkirchen bei Graz', kind: 'Parkplatz', availability: 'unbekannt', source: 'APCOA Graz Airport Standortseite', source_url: 'https://www.apcoa.at/airport-graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PP Graz Airport P1', address: 'Graz Airport, Feldkirchen bei Graz', kind: 'Parkplatz', availability: 'unbekannt', source: 'APCOA Graz Airport Standortseite', source_url: 'https://www.apcoa.at/airport-graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PH Graz Airport P2', address: 'Graz Airport, Feldkirchen bei Graz', kind: 'Parkhaus', availability: 'unbekannt', source: 'APCOA Graz Airport Standortseite', source_url: 'https://www.apcoa.at/airport-graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PP Graz Airport P3', address: 'Graz Airport, Feldkirchen bei Graz', kind: 'Parkplatz', availability: 'unbekannt', source: 'APCOA Graz Airport Standortseite', source_url: 'https://www.apcoa.at/airport-graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PP Graz Airport P4', address: 'Graz Airport, Feldkirchen bei Graz', kind: 'Parkplatz', availability: 'unbekannt', source: 'APCOA Graz Airport Standortseite', source_url: 'https://www.apcoa.at/airport-graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PP Graz Airport P5', address: 'Graz Airport, Feldkirchen bei Graz', kind: 'Parkplatz', availability: 'unbekannt', source: 'APCOA Graz Airport Standortseite', source_url: 'https://www.apcoa.at/airport-graz', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'PP Andreas-Hofer-Platz', address: 'Andreas-Hofer-Platz, Graz', kind: 'Parkplatz', availability: 'unbekannt', source: 'Contipark Graz Standortseite', source_url: 'https://www.contipark.at/de/parken/graz/', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'TG Andreas-Hofer-Platz', address: 'Andreas-Hofer-Platz, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'Contipark Graz Standortseite', source_url: 'https://www.contipark.at/de/parken/graz/', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'TG Dominikanerkloster', address: 'Dominikanerkloster, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'Contipark Graz Standortseite', source_url: 'https://www.contipark.at/de/parken/graz/', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }},
      {{ name: 'TG Lendplatz', address: 'Lendplatz, Graz', kind: 'Tiefgarage', availability: 'unbekannt', source: 'Contipark Graz Standortseite', source_url: 'https://www.contipark.at/de/parken/graz/', license: 'Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären' }}
    ];
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
      const existing = new Set([...select.options].map((option) => option.value));
      [...new Set(values.filter(Boolean))].forEach((value) => {{
        if (existing.has(value)) return;
        const option = document.createElement('option');
        option.value = value;
        option.textContent = value;
        select.appendChild(option);
        existing.add(value);
      }});
    }}

    function fillDateSelect(select, values) {{
      const existing = new Set([...select.options].map((option) => option.value));
      [...new Set(values.filter(Boolean))]
        .sort((left, right) => String(right).localeCompare(String(left), 'de-AT'))
        .forEach((value) => {{
          if (existing.has(value)) return;
          const option = document.createElement('option');
          option.value = value;
          option.textContent = value;
          select.appendChild(option);
          existing.add(value);
        }});
    }}

    function fillYearSelect(select, values) {{
      const existing = new Set([...select.options].map((option) => option.value));
      [...new Set(values.filter(Boolean))]
        .sort((left, right) => String(right).localeCompare(String(left), 'de-AT'))
        .forEach((value) => {{
          if (existing.has(value)) return;
          const option = document.createElement('option');
          option.value = value;
          option.textContent = value;
          select.appendChild(option);
          existing.add(value);
        }});
    }}

    function defaultYearValue() {{
      const years = [...yearFilter.options].map((option) => option.value).filter(Boolean);
      return years[0] || '';
    }}

    function sortRecordsForTable(items) {{
      return [...items].sort((left, right) => (
        String(right.datum || '').localeCompare(String(left.datum || '')) ||
        typeSortRank(left) - typeSortRank(right) ||
        Number(left.stueck_nr || 0) - Number(right.stueck_nr || 0) ||
        String(left.titel || '').localeCompare(String(right.titel || ''), 'de-AT')
      ));
    }}

    function typeSortRank(record) {{
      const type = String(record.typ || '');
      const section = String(record.abschnitt || '').toLocaleLowerCase('de-AT');
      if (type === 'Mitteilung') return 10;
      if (type === 'Fragestunde') return 20;
      if (type === 'Tagesordnungspunkt') return 30;
      if ((type === 'Abänderungsantrag' || type === 'Zusatzantrag') && !section.includes('dring')) return 31;
      if (type === 'Dringlichkeitsantrag') return 40;
      if ((type === 'Abänderungsantrag' || type === 'Zusatzantrag') && section.includes('dring')) return 41;
      if (type === 'Schriftliche Anfrage') return 50;
      if (type === 'Schriftlicher Antrag') return 60;
      if (type === 'Archiv-Tagesordnungspunkt') return 85;
      if (type === 'Archivquelle') return 90;
      if (type === 'Anwesenheitsliste') return 95;
      return 80;
    }}

    function fillTypeSelect() {{
      const preferredTypes = [
        'Mitteilung',
        'Fragestunde',
        'Tagesordnungspunkt',
        'Abänderungsantrag',
        'Zusatzantrag',
        'Dringlichkeitsantrag',
        'Schriftliche Anfrage',
        'Schriftlicher Antrag',
        'Archiv-Tagesordnungspunkt',
        'Archivquelle',
        'Anwesenheitsliste'
      ];
      fillSelect(typeFilter, [...preferredTypes, ...records.map((record) => record.typ)]);
    }}

    function fillSourceSelect() {{
      const preferredSources = [
        'DIGRA',
        'DIGRA fehlt',
        'Stadt-Graz-Archiv',
        'Stadt-Graz-Protokoll'
      ];
      fillSelect(sourceFilter, [...preferredSources, ...records.map((record) => record.ergebnisquelle)]);
    }}

    function fillDatalist(id, values, limit = 900) {{
      const list = byId(id);
      if (!list) return;
      list.innerHTML = uniqueSuggestionValues(values, limit)
        .map((value) => `<option value="${{escapeHtml(value)}}"></option>`)
        .join('');
    }}

    function uniqueSuggestionValues(values, limit = 900) {{
      return [...new Set(values.map((value) => String(value || '').trim()).filter(Boolean))]
        .sort((a, b) => a.localeCompare(b, 'de-AT'))
        .slice(0, limit);
    }}

    function renderQuestionSuggestions() {{
      if (!aiQuestionSuggestions) return;
      const query = normalizeSearchText(aiQuestion.value);
      if (query.length < 2) {{
        hideQuestionSuggestions();
        return;
      }}
      const tokens = query.split(/\\s+/).filter((token) => token.length >= 2);
      const matches = questionSuggestionValues
        .map((value) => {{
          const normalized = normalizeSearchText(value);
          let score = 0;
          if (normalized === query) score += 100;
          if (normalized.startsWith(query)) score += 80;
          if (normalized.includes(query)) score += 55;
          tokens.forEach((token) => {{
            if (normalized.startsWith(token)) score += 18;
            else if (normalized.includes(token)) score += 8;
          }});
          return {{ value, score }};
        }})
        .filter((item) => item.score > 0)
        .sort((a, b) => b.score - a.score || a.value.length - b.value.length || a.value.localeCompare(b.value, 'de-AT'))
        .slice(0, 7);
      if (!matches.length) {{
        hideQuestionSuggestions();
        return;
      }}
      aiQuestionSuggestions.innerHTML = matches
        .map((item) => `<button class="question-suggestion" type="button" role="option" data-question-suggestion="${{escapeHtml(item.value)}}">${{escapeHtml(item.value)}}</button>`)
        .join('');
      aiQuestionSuggestions.hidden = false;
      aiQuestion.setAttribute('aria-expanded', 'true');
    }}

    function hideQuestionSuggestions() {{
      if (!aiQuestionSuggestions) return;
      aiQuestionSuggestions.hidden = true;
      aiQuestionSuggestions.innerHTML = '';
      aiQuestion?.setAttribute('aria-expanded', 'false');
    }}

    function activateQuestionResultTab(tabName = 'answer') {{
      const normalized = tabName === 'sources' ? 'sources' : 'answer';
      aiResultTabs?.querySelectorAll('[data-question-result-tab]').forEach((button) => {{
        const active = button.dataset.questionResultTab === normalized;
        button.classList.toggle('active', active);
        button.setAttribute('aria-selected', String(active));
      }});
      if (aiAnswerPanel) aiAnswerPanel.hidden = normalized !== 'answer';
      if (aiSourcesPanel) aiSourcesPanel.hidden = normalized !== 'sources';
    }}

    function showQuestionResultTabs(tabName = 'answer') {{
      if (aiResultTabs) aiResultTabs.hidden = false;
      activateQuestionResultTab(tabName);
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
        record.digra_einlagezahl,
        record.ki_zusammenfassung,
        record.ki_warum_interessant,
        summaryPointsText(record)
      ].join(' ').toLocaleLowerCase('de-AT');
    }}

    function joinList(values) {{
      return (values || []).filter(Boolean).join(', ') || '-';
    }}

    function readLocalJson(key, fallback) {{
      try {{
        const raw = localStorage.getItem(key);
        return raw ? JSON.parse(raw) : fallback;
      }} catch (error) {{
        return fallback;
      }}
    }}

    function writeLocalJson(key, value) {{
      localStorage.setItem(key, JSON.stringify(value));
    }}

    function todayIsoDate() {{
      const date = new Date();
      const year = date.getFullYear();
      const month = String(date.getMonth() + 1).padStart(2, '0');
      const day = String(date.getDate()).padStart(2, '0');
      return `${{year}}-${{month}}-${{day}}`;
    }}

    function isFinalCouncilOutcome(record) {{
      const status = `${{record.status_filter || ''}} ${{record.status || ''}} ${{record.ergebnis || ''}}`;
      return /angenommen|abgelehnt|zur kenntnis|quelle verfügbar|quelle verfuegbar/i.test(status);
    }}

    function isCivicFeedbackEligible(record) {{
      if (!record || !record.record_id || !record.digra_url) return false;
      if (/archiv|anwesenheit/i.test(record.typ || '')) return false;
      const date = String(record.datum || '').slice(0, 10);
      if (!/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(date)) return false;
      return date >= todayIsoDate();
    }}

    function civicFeedbackRecords() {{
      return records
        .filter(isCivicFeedbackEligible)
        .sort((left, right) => participationTypeRank(left) - participationTypeRank(right) || String(left.datum || '').localeCompare(String(right.datum || '')) || String(left.titel || '').localeCompare(String(right.titel || ''), 'de-AT'));
    }}

    function civicFeedbackStore() {{
      const value = readLocalJson(civicFeedbackKey, {{}});
      return value && typeof value === 'object' && !Array.isArray(value) ? value : {{}};
    }}

    function civicFeedbackFor(recordId) {{
      const store = civicFeedbackStore();
      const entry = store[recordId];
      return entry && typeof entry === 'object' ? entry : null;
    }}

    function writeCivicFeedback(recordId, entry) {{
      const store = civicFeedbackStore();
      store[recordId] = entry;
      writeLocalJson(civicFeedbackKey, store);
    }}

    function civicFeedbackLabel(value) {{
      return {{
        support: 'Dafür',
        oppose: 'Dagegen',
        unsure: 'Unsicher'
      }}[value] || 'Noch keine Rückmeldung';
    }}

    function participationReasonLabel(value) {{
      return {{
        safety: 'Sicherheit',
        climate: 'Klima und Umwelt',
        cost: 'Kosten',
        fairness: 'Fairness',
        accessibility: 'Barrierefreiheit',
        traffic: 'Verkehr',
        housing: 'Wohnen',
        other: 'Anderer Grund'
      }}[value] || '';
    }}

    function participationReasonText(feedback) {{
      return String(feedback?.reason_text || feedback?.comment || participationReasonLabel(feedback?.reason) || '').trim();
    }}

    function participationAffectednessLabel(value) {{
      return {{
        resident: 'Ich wohne in der Nähe',
        work: 'Ich arbeite in der Nähe',
        commute: 'Ich pendle dort regelmäßig',
        visitor: 'Ich nutze den Ort gelegentlich',
        citywide: 'Betrifft mich als Grazer:in allgemein',
        none: 'Kein direkter Bezug',
        other: 'Anderer Bezug'
      }}[value] || '';
    }}

    function participationAffectednessOptions(selected = '') {{
      const options = [
        ['', 'Bitte wählen, falls zutreffend'],
        ['resident', 'Ich wohne in der Nähe'],
        ['work', 'Ich arbeite in der Nähe'],
        ['commute', 'Ich pendle dort regelmäßig'],
        ['visitor', 'Ich nutze den Ort gelegentlich'],
        ['citywide', 'Betrifft mich als Grazer:in allgemein'],
        ['none', 'Kein direkter Bezug'],
        ['other', 'Anderer Bezug']
      ];
      return options.map(([value, label]) => `<option value="${{escapeHtml(value)}}"${{value === selected ? ' selected' : ''}}>${{escapeHtml(label)}}</option>`).join('');
    }}

    function participationRecordMeta(record) {{
      return [record.datum, record.typ, participationStatusText(record), record.kategorie].filter(Boolean).join(' · ');
    }}

    function participationStatusText(record) {{
      const result = String(record.ergebnis || '').trim();
      const status = String(record.status || '').trim();
      if (/^Ausschuss\\s+am\\s+/i.test(result)) {{
        const decision = result.replace(/^Ausschuss\\s+am\\s+[^:]+:\\s*/i, '').trim();
        return decision ? `Vorberatung im Ausschuss: ${{decision}}` : 'Vorberatung im Ausschuss';
      }}
      if (/Ausschuss/i.test(result) && /angenommen|abgelehnt|beschlossen/i.test(result)) {{
        return `Vorberatung im Ausschuss: ${{result}}`;
      }}
      return status;
    }}

    function participationTypeRank(record) {{
      const type = String(record.typ || '').toLocaleLowerCase('de-AT');
      if (type.includes('mitteilung')) return 1;
      if (type.includes('fragestunde')) return 2;
      if (type.includes('tagesordnung')) return 3;
      if (type.includes('dringlich')) return 4;
      if (type.includes('schriftlich')) return 5;
      return 99;
    }}

    function renderParticipationPage(recordId = selectedParticipationRecordId) {{
      if (!participationList || !participationDetail) return;
      const items = civicFeedbackRecords();
      if (!items.length) {{
        selectedParticipationRecordId = '';
        participationList.innerHTML = '<div class="empty">Aktuell sind keine zukünftigen DIGRA-Stücke für ein lokales Meinungsbild erkennbar.</div>';
        participationDetail.innerHTML = `
          <h2>Keine offenen Stücke</h2>
          <div class="participation-local-note"><p>Sobald DIGRA Stücke mit zukünftiger Sitzung enthält, erscheinen sie hier. Bereits sichtbare DIGRA-Ergebnisse können Vorberatung oder vorbereitete Beschlussvermerke sein.</p></div>
        `;
        return;
      }}
      const selected = items.find((record) => record.record_id === recordId) || items[0];
      selectedParticipationRecordId = selected.record_id;
      participationList.innerHTML = items.map((record) => {{
        const feedback = civicFeedbackFor(record.record_id);
        const metaItems = [record.datum, record.typ, participationStatusText(record), record.kategorie].filter(Boolean);
        const feedbackLine = feedback?.stance
          ? `<span class="participation-card-feedback">Rückmeldung: ${{escapeHtml(civicFeedbackLabel(feedback.stance))}}</span>`
          : '';
        return `
          <button class="participation-card${{record.record_id === selectedParticipationRecordId ? ' active' : ''}}" type="button" data-participation-record-id="${{escapeHtml(record.record_id)}}">
            <span class="participation-card-title">${{escapeHtml(record.titel || 'Unbenanntes Stück')}}</span>
            <span class="participation-card-meta">${{metaItems.map((item) => `<span class="participation-card-chip">${{escapeHtml(item)}}</span>`).join('')}}</span>
            ${{feedbackLine}}
          </button>
        `;
      }}).join('');
      renderParticipationDetail(selected);
    }}

    function renderParticipationDetail(record) {{
      const feedback = civicFeedbackFor(record.record_id) || {{}};
      const stance = feedback.stance || '';
      const reasonText = participationReasonText(feedback);
      const changeRequest = String(feedback.change_request || '').trim();
      participationDetail.innerHTML = `
        <h2>${{escapeHtml(record.titel || 'Unbenanntes Stück')}}</h2>
        <div class="detail-grid">
          ${{detailField('Datum', record.datum)}}
          ${{detailField('Typ', record.typ)}}
          ${{detailField('Status', participationStatusText(record))}}
          ${{detailLinkField('DIGRA-Link', record.digra_url)}}
          ${{detailField('Thema', record.kategorie)}}
          ${{detailField('Einbringer', record.einbringer)}}
        </div>
        <div class="participation-local-note">
          <p>Dieses Meinungsbild ist zählbar und sammelt qualitative Hinweise, ist aber nicht repräsentativ, nicht amtlich und nicht verbindlich. Bereits sichtbare DIGRA-Ergebnisse können Vorberatung oder vorbereitete Beschlussvermerke sein. Die Entscheidung trifft der Gemeinderat. Pro Stück wird lokal nur eine Rückmeldung gespeichert; erneutes Speichern aktualisiert sie.</p>
        </div>
        <div class="participation-actions" role="group" aria-label="Meinung">
          <button class="participation-stance${{stance === 'support' ? ' active' : ''}}" type="button" data-civic-stance="support">Dafür</button>
          <button class="participation-stance${{stance === 'oppose' ? ' active' : ''}}" type="button" data-civic-stance="oppose">Dagegen</button>
          <button class="participation-stance${{stance === 'unsure' ? ' active' : ''}}" type="button" data-civic-stance="unsure">Unsicher</button>
        </div>
        <div class="participation-form">
          <label>Mein Bezug
            <select id="participationAffectedness">${{participationAffectednessOptions(feedback.affectedness || '')}}</select>
          </label>
          <label>Warum?
            <textarea id="participationReasonText" maxlength="900" rows="6" placeholder="Was ist der wichtigste Grund für deine Einschätzung?">${{escapeHtml(reasonText)}}</textarea>
          </label>
          <label>Was müsste sich ändern?
            <textarea id="participationChangeRequest" maxlength="900" rows="4" placeholder="Welche Änderung würde das Stück aus deiner Sicht besser machen?">${{escapeHtml(changeRequest)}}</textarea>
          </label>
          <button id="participationSave" type="button">Lokal speichern</button>
        </div>
        <div class="participation-local-note" id="participationSavedNote">
          <p>${{feedback.updated_at ? `Gespeichert: ${{escapeHtml(civicFeedbackLabel(feedback.stance))}}${{feedback.affectedness ? ` · ${{escapeHtml(participationAffectednessLabel(feedback.affectedness))}}` : ''}}${{reasonText ? ` · ${{escapeHtml(reasonText.slice(0, 90))}}${{reasonText.length > 90 ? '…' : ''}}` : ''}} · ${{escapeHtml(formatDateTime(feedback.updated_at))}}` : 'Noch keine lokale Rückmeldung gespeichert.'}}</p>
        </div>
      `;
    }}

    function saveCurrentParticipationFeedback() {{
      const record = findRecordById(selectedParticipationRecordId);
      if (!record) return;
      const active = participationDetail.querySelector('[data-civic-stance].active');
      const stance = active?.dataset.civicStance || '';
      if (!stance) {{
        const note = byId('participationSavedNote');
        if (note) note.innerHTML = '<p>Bitte zuerst Dafür, Dagegen oder Unsicher wählen.</p>';
        return;
      }}
      const reasonText = (byId('participationReasonText')?.value || '').trim().slice(0, 900);
      if (reasonText.length < 40) {{
        const note = byId('participationSavedNote');
        if (note) note.innerHTML = '<p>Bitte begründe deine Rückmeldung mit mindestens 40 Zeichen.</p>';
        return;
      }}
      const previous = civicFeedbackFor(record.record_id);
      const now = new Date().toISOString();
      const affectedness = byId('participationAffectedness')?.value || '';
      const changeRequest = (byId('participationChangeRequest')?.value || '').trim().slice(0, 900);
      writeCivicFeedback(record.record_id, {{
        record_id: record.record_id,
        stance,
        affectedness,
        reason_text: reasonText,
        change_request: changeRequest,
        created_at: previous?.created_at || now,
        updated_at: now
      }});
      renderParticipationPage(record.record_id);
    }}

    function openParticipationForRecord(recordId = '') {{
      selectedParticipationRecordId = recordId || selectedParticipationRecordId;
      closeCivicFeedbackModal(true);
      activateTab('participation');
      renderParticipationPage(selectedParticipationRecordId);
      participationDetail?.scrollIntoView({{ behavior: 'auto', block: 'start' }});
    }}

    function civicFeedbackDetailCta(record) {{
      if (!isCivicFeedbackEligible(record)) return '';
      return `
        <div class="participation-detail-cta">
          <div class="participation-detail-copy">
            <span class="participation-detail-chip">Mitreden möglich</span>
            <strong>Lokale Rückmeldung zu diesem Stück</strong>
            <p>Dieses DIGRA-Stück liegt vor oder am Sitzungstag. Du kannst eine zählbare, qualitative Rückmeldung lokal in diesem Browser speichern.</p>
          </div>
          <button type="button" data-open-civic-feedback="${{escapeHtml(record.record_id)}}">Rückmeldung geben</button>
        </div>
      `;
    }}

    function maybeShowCivicFeedbackModal() {{
      const items = civicFeedbackRecords();
      if (!items.length || localStorage.getItem(civicFeedbackPopupKey)) return;
      if (civicFeedbackModalText) {{
        civicFeedbackModalText.textContent = `${{items.length}} angekündigte Stücke sind vor der Sitzung für ein lokales Meinungsbild verfügbar.`;
      }}
      civicFeedbackModal?.classList.add('is-open');
    }}

    function closeCivicFeedbackModal(markDismissed = false) {{
      civicFeedbackModal?.classList.remove('is-open');
      if (markDismissed) localStorage.setItem(civicFeedbackPopupKey, new Date().toISOString());
    }}

    function downloadText(filename, content, type = 'text/plain;charset=utf-8') {{
      const blob = new Blob([content], {{ type }});
      const url = URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(url);
    }}

    function roadworkDateStatus(startText, endText) {{
      if (!startText || !endText) return 'unklar';
      const today = new Date().toISOString().slice(0, 10);
      if (startText > endText) return 'unklar';
      if (today < startText) return 'kuenftig';
      if (today > endText) return 'abgeschlossen';
      return 'aktuell';
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
      return !/^(?:EZ\\b|KG\\b|Gdst\\.?\\b|Gst\\.?\\b|Grundstück\\b|Grundstueck\\b|Katastralgemeinde\\b|Einlagezahl\\b)/i.test(String(location || '').trim());
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
      highlightSelectedTableRow();
      if (focusMap && (record.orte || []).length) {{
        focusRecordLocations(record);
      }} else {{
        activateTab('search');
      }}
    }}

    function highlightSelectedTableRow() {{
      tableWrap.querySelectorAll('tr[data-index]').forEach((row) => {{
        const record = sichtbareEintraege[Number(row.dataset.index)] || null;
        row.classList.toggle('selected-record', Boolean(record && ausgewaehlterEintrag && record.record_id === ausgewaehlterEintrag.record_id));
      }});
    }}

    function selectedTableRowElement() {{
      if (!ausgewaehlterEintrag || !tableWrap) return null;
      return [...tableWrap.querySelectorAll('tr[data-index]')].find((row) => {{
        const record = sichtbareEintraege[Number(row.dataset.index)] || null;
        return Boolean(record && record.record_id === ausgewaehlterEintrag.record_id);
      }}) || null;
    }}

    function ensureSelectedTableRowVisible() {{
      const row = selectedTableRowElement();
      if (!row) return;
      const rect = row.getBoundingClientRect();
      const topLimit = 76;
      const bottomLimit = window.innerHeight - 20;
      if (rect.top < topLimit || rect.bottom > bottomLimit) {{
        row.scrollIntoView({{ behavior: 'auto', block: 'center' }});
      }}
    }}

    function setMobileNavOpen(open) {{
      if (!sidebar || !mobileNavToggle) return;
      sidebar.classList.toggle('nav-open', open);
      mobileNavToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    }}

    function activateTab(target) {{
      activeTabName = target;
      setMobileNavOpen(false);
      const viewTitles = {{
        start: 'Start',
        search: 'Suche',
        participation: 'Mitreden',
        map: 'Karte',
        council: 'Gemeinderat',
        roadworks: 'Baustellen',
        parking: 'Tiefgaragen',
        pharmacies: 'Apotheken',
        doctors: 'Ärzte',
        services: 'Services & Ämter'
      }};
      if (viewTitle) viewTitle.textContent = viewTitles[target] || 'Graz';
      if (searchSection) searchSection.hidden = !['search', 'map'].includes(target);
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
      if (target === 'participation') {{
        renderParticipationPage();
      }}
      if (target === 'roadworks') {{
        setTimeout(() => {{
          initRoadworksMap();
          roadworksMap?.invalidateSize();
        }}, 80);
      }}
      if (target === 'council') {{
        renderCouncil();
      }}
      if (target === 'parking') {{
        setTimeout(() => {{
          initParkingMap();
          invalidateMapSoon(parkingMap);
        }}, 80);
      }}
      if (target === 'pharmacies') {{
        setTimeout(() => {{
          initPharmacyMap();
          invalidateMapSoon(pharmacyMap);
        }}, 80);
      }}
      if (target === 'doctors') {{
        setTimeout(() => {{
          initDoctorsMap();
          invalidateMapSoon(doctorsMap);
        }}, 80);
      }}
      if (target === 'services') {{
        setTimeout(() => {{
          initServicesMap();
          invalidateMapSoon(servicesMap);
        }}, 80);
      }}
    }}

    function activateSearchSubtab(target, restoreScroll = true) {{
      if (!['table', 'details', 'summary'].includes(target)) return;
      searchSubtabScroll[activeSearchSubtab] = window.scrollY || 0;
      activeSearchSubtab = target;
      document.querySelectorAll('[data-search-subtab]').forEach((item) => {{
        const active = item.dataset.searchSubtab === target;
        item.classList.toggle('active', active);
        item.setAttribute('aria-selected', String(active));
      }});
      if (searchTablePanel) searchTablePanel.hidden = target !== 'table';
      if (searchDetailPanel) searchDetailPanel.hidden = target !== 'details';
      if (searchSummaryPanel) searchSummaryPanel.hidden = target !== 'summary';
      if (target === 'summary') renderDateSummary();
      if (restoreScroll) {{
        requestAnimationFrame(() => {{
          window.scrollTo({{ top: searchSubtabScroll[target] || 0, behavior: 'auto' }});
          if (target === 'table') requestAnimationFrame(ensureSelectedTableRowVisible);
        }});
      }}
    }}

    function invalidateMapSoon(map) {{
      if (!map) return;
      requestAnimationFrame(() => map.invalidateSize());
      setTimeout(() => map.invalidateSize(), 180);
      setTimeout(() => map.invalidateSize(), 420);
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
      renderTrafficSources();
      renderRoadworkContext();
    }}

    function initPharmacyMap() {{
      if (!window.L || pharmacyMap) return;
      pharmacyMap = L.map('pharmacyMap').setView([47.0707, 15.4395], 12);
      addBaseLayer(pharmacyMap);
      pharmacyLayer = L.layerGroup().addTo(pharmacyMap);
      const hasCachedPharmacies = activePharmacies.length > 0;
      if (!hasCachedPharmacies) activePharmacies = pharmacyFallbackPlaces;
      currentPharmacyPlaces = activePharmacies;
      renderHealthSourceNote('pharmacies', 'pharmacySourceNote', 'Nachtdienste und Bereitschaftsdienste werden nicht lokal berechnet. Für aktuelle Nachtapotheken bitte die offizielle Apothekensuche öffnen.');
      renderHealthPlaces(activePharmacies, pharmacyLayer, pharmacyList, pharmacyStatus, pharmacyProgress, pharmacyProgressBar, 'Apotheken', () => '#7c3aed');
      if (!hasCachedPharmacies) {{
        loadHealthPlacesFromOverpass('pharmacy', pharmacyStatus, true).then((places) => {{
          if (!places.length) return;
          activePharmacies = places;
          currentPharmacyPlaces = activePharmacies;
          renderHealthPlaces(activePharmacies, pharmacyLayer, pharmacyList, pharmacyStatus, pharmacyProgress, pharmacyProgressBar, 'Apotheken', () => '#7c3aed');
        }});
      }}
    }}

    function initDoctorsMap() {{
      if (!window.L || doctorsMap) return;
      doctorsMap = L.map('doctorsMap').setView([47.0707, 15.4395], 12);
      addBaseLayer(doctorsMap);
      doctorsLayer = L.layerGroup().addTo(doctorsMap);
      renderDoctorsProfessionFilter();
      renderHealthSourceNote('doctors', 'doctorsSourceNote', '');
      if (activeDoctors.length) {{
        renderDoctorsMap();
      }} else {{
        doctorsStatus.textContent = 'Ordinationen werden aus OpenStreetMap geladen...';
        loadHealthPlacesFromOverpass('doctor', doctorsStatus).then((places) => {{
          activeDoctors = places;
          renderDoctorsProfessionFilter();
          renderDoctorsMap();
        }});
      }}
    }}

    function renderCouncil() {{
      if (councilRendered) return;
      councilRendered = true;
      const groups = civicCouncil.groups || [];
      const senateGroups = civicCouncil.city_senate?.groups || [];
      const totalSeats = civicCouncil.total_seats || groups.reduce((sum, group) => sum + Number(group.seats || 0), 0);
      const senateSeats = civicCouncil.city_senate?.total_seats || senateGroups.reduce((sum, group) => sum + Number(group.seats || 0), 0);
      const majoritySeats = civicCouncil.majority_seats || Math.floor(totalSeats / 2) + 1;
      if (councilKpis) {{
        councilKpis.innerHTML = councilKpiHtml([
          [totalSeats, 'Mandate'],
          [groups.length, 'Parteien'],
          [senateSeats, 'Stadtregierungsmitglieder'],
        ]);
      }}
      if (councilSummary) {{
        councilSummary.textContent = `${{totalSeats}} Mandate · Mehrheit ab ${{majoritySeats}}`;
      }}
      if (councilMajorityNote) councilMajorityNote.textContent = `${{majoritySeats}} Sitze sind für eine Mehrheit erforderlich.`;
      if (senateSummary) senateSummary.textContent = `${{senateSeats}} Mitglieder`;
      if (councilStatus) councilStatus.textContent = `${{groups.length}} Parteien · Stand: ${{escapePlain(civicCouncil.period || 'graz.at')}}`;
      if (councilDots) councilDots.innerHTML = councilSeatHtml(groups, totalSeats, 'council');
      if (senateDots) senateDots.innerHTML = councilSeatHtml(senateGroups, senateSeats, 'senate');
      if (councilLegend) councilLegend.innerHTML = councilFactionListHtml(groups, totalSeats, senateGroups);
      if (councilMandates) councilMandates.innerHTML = councilMandatesHtml(groups, totalSeats, senateGroups);
      if (councilLinks) councilLinks.innerHTML = councilLinksHtml(civicCouncil.sources || {{}});
      renderCouncilSourceNote();
      bindCouncilHover();
    }}

    function councilKpiHtml(items) {{
      return items.map(([value, label]) => `
        <div class="council-kpi">
          <strong>${{escapeHtml(value)}}</strong>
          <span>${{escapeHtml(label)}}</span>
        </div>
      `).join('');
    }}

    function councilSeatHtml(groups, totalSeats, kind) {{
      const seats = groups.flatMap((group) =>
        Array.from({{ length: Number(group.seats || 0) }}, (_unused, index) => ({{
          group,
          member: councilMemberObject((group.members || [])[index], group, index),
        }}))
      );
      const positions = councilHemicyclePositions(seats.length, kind);
      return seats.map((seat, index) => councilDotHtml(seat.group, seat.member, totalSeats, positions[index] || {{ left: 50, top: 50 }})).join('');
    }}

    function councilMemberObject(member, group, index) {{
      if (member && typeof member === 'object') {{
        return {{
          name: member.name || `${{group.short_name || group.name}} Sitz ${{index + 1}}`,
          url: member.url || '',
        }};
      }}
      return {{
        name: member || `${{group.short_name || group.name}} Sitz ${{index + 1}}`,
        url: '',
      }};
    }}

    function councilDotHtml(group, member, totalSeats, position) {{
      const seats = Number(group.seats || 0);
      const share = totalSeats ? Math.round((seats / totalSeats) * 1000) / 10 : 0;
      const shortName = group.short_name || group.name;
      const tooltip = `${{member.name}} · ${{shortName}} · ${{seats}} ${{seats === 1 ? 'Mandat' : 'Mandate'}} (${{share.toLocaleString('de-AT')}} %)`;
      const dot = member.url
        ? `<a class="council-dot" href="${{escapeHtml(member.url)}}" target="_blank" rel="noopener noreferrer" data-tooltip="${{escapeHtml(tooltip)}}" aria-label="${{escapeHtml(tooltip)}}"></a>`
        : `<button class="council-dot" type="button" data-tooltip="${{escapeHtml(tooltip)}}" aria-label="${{escapeHtml(tooltip)}}"></button>`;
      return `
        <span class="council-seat"
          style="--seat-left: ${{position.left.toFixed(2)}}%; --seat-top: ${{position.top.toFixed(2)}}%; --party-color: ${{escapeHtml(group.color || '#64748b')}}; --party-text: ${{escapeHtml(group.text_color || '#ffffff')}}"
          data-council-group="${{escapeHtml(shortName)}}">
          ${{dot}}
          <span class="council-seat-label" aria-hidden="true">${{escapeHtml(member.name)}}</span>
        </span>
      `;
    }}

    function councilHemicyclePositions(total, kind) {{
      if (total <= 0) return [];
      if (kind === 'senate') return Array.from({{ length: total }}, () => ({{ left: 0, top: 0 }}));
      const rowSizes = total <= 20 ? [total] : [14, 13, 11, Math.max(0, total - 38)].filter(Boolean);
      const positions = [];
      rowSizes.forEach((rowSize, rowIndex) => {{
        const radiusX = 45 - rowIndex * 8;
        const radiusY = 80 - rowIndex * 14;
        const baseTop = 91 - rowIndex * 2;
        for (let index = 0; index < rowSize; index += 1) {{
          const angle = rowSize === 1 ? 270 : 202 + (136 * index / (rowSize - 1));
          positions.push({{
            left: 50 + Math.cos(angle * Math.PI / 180) * radiusX,
            top: baseTop + Math.sin(angle * Math.PI / 180) * radiusY,
          }});
        }}
      }});
      return positions.slice(0, total);
    }}

    function councilFactionListHtml(groups, totalSeats, senateGroups) {{
      return `
        <div class="council-histogram">
          <h3>Fraktionen</h3>
          <div class="council-faction-list">
            ${{groups.map((group) => councilFactionCardHtml(group, totalSeats, senateGroups)).join('')}}
          </div>
        </div>
      `;
    }}

    function councilMandatesHtml(groups, totalSeats, senateGroups) {{
      const maxSeats = Math.max(1, ...groups.map((group) => Number(group.seats || 0)));
      return `
        <div class="council-histogram">
          <h3>Mandate nach Fraktion</h3>
          <div class="council-histogram-grid">
            ${{groups.map((group) => councilColumnHtml(group, totalSeats, senateGroups, maxSeats)).join('')}}
          </div>
          <div class="council-histogram-note">Säulenhöhe relativ zur stärksten Fraktion; Hover zeigt dieselbe Gruppe im Halbkreis.</div>
        </div>
      `;
    }}

    function councilColumnHtml(group, totalSeats, senateGroups, maxSeats) {{
      const seats = Number(group.seats || 0);
      const share = totalSeats ? Math.round((seats / totalSeats) * 1000) / 10 : 0;
      const shortName = group.short_name || group.name;
      const senateGroup = senateGroups.find((item) => item.short_name === group.short_name);
      const senateText = senateGroup
        ? `${{senateGroup.seats}} Stadtregierungsmitglieder: ${{(senateGroup.members || []).join(', ')}}`
        : 'nicht mit Stadtregierungsmitgliedern vertreten';
      return `
        <div class="council-column"
          style="--party-color: ${{escapeHtml(group.color || '#64748b')}}; --column-height: ${{Math.max(5, Math.round((seats / maxSeats) * 100))}}%"
          data-council-card="${{escapeHtml(shortName)}}">
          <div class="council-column-percent">${{share.toLocaleString('de-AT')}} %</div>
          <div class="council-column-track" title="${{escapeHtml(`${{group.name}}: ${{seats}} Mandate · ${{share.toLocaleString('de-AT')}} % · ${{senateText}}`)}}">
            <div class="council-column-fill"></div>
          </div>
          <div class="council-column-value">${{seats}} Sitze</div>
          <div class="council-column-label">${{escapeHtml(shortName)}}</div>
        </div>
      `;
    }}

    function councilFactionCardHtml(group, totalSeats, senateGroups) {{
      const seats = Number(group.seats || 0);
      const share = totalSeats ? Math.round((seats / totalSeats) * 1000) / 10 : 0;
      const shortName = group.short_name || group.name;
      const senateGroup = senateGroups.find((item) => item.short_name === group.short_name);
      const senateSeats = Number(senateGroup?.seats || 0);
      const senateText = senateSeats
        ? `${{senateSeats}} Stadtregierungsmitglieder`
        : 'keine Stadtregierungsmitglieder';
      return `
        <div class="council-faction-card"
          style="--party-color: ${{escapeHtml(group.color || '#64748b')}}; --faction-share: ${{Math.max(3, share)}}%"
          data-council-card="${{escapeHtml(shortName)}}">
          <div class="council-faction-top">
            <span class="council-faction-swatch" aria-hidden="true"></span>
            <span class="council-faction-name">${{escapeHtml(group.name || shortName)}}</span>
            <span class="council-faction-seats">${{seats}} Sitze</span>
          </div>
          <div class="council-faction-track" aria-hidden="true"><div class="council-faction-fill"></div></div>
          <div class="council-faction-meta">${{share.toLocaleString('de-AT')}} % der Mandate · ${{escapeHtml(senateText)}}</div>
        </div>
      `;
    }}

    function councilLinksHtml(sources) {{
      return [
        [sources.members_url, 'GR-Mitglieder'],
        [sources.seats_url, 'Sitzverteilung'],
        [sources.city_government_url, 'Stadtregierungsmitglieder'],
      ].filter(([url]) => url).map(([url, label]) =>
        `<a href="${{escapeHtml(url)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(label)}}</a>`
      ).join('');
    }}

    function bindCouncilHover() {{
      const focus = (key) => {{
        document.querySelectorAll('[data-council-group], [data-council-card]').forEach((element) => {{
          const elementKey = element.dataset.councilGroup || element.dataset.councilCard || '';
          element.classList.toggle('is-focused', Boolean(key && elementKey === key));
          element.classList.toggle('is-dimmed', Boolean(key && element.dataset.councilGroup && elementKey !== key));
        }});
      }};
      document.querySelectorAll('[data-council-group], [data-council-card]').forEach((element) => {{
        const key = element.dataset.councilGroup || element.dataset.councilCard || '';
        element.addEventListener('mouseenter', () => focus(key));
        element.addEventListener('focusin', () => focus(key));
        element.addEventListener('mouseleave', () => focus(''));
        element.addEventListener('focusout', () => focus(''));
      }});
    }}

    function renderCouncilSourceNote() {{
      const source = civicCouncil.sources || {{}};
      byId('councilSourceNote').innerHTML = `
        Quelle: ${{externalLink(source.members_url || '', 'Gemeinderat: Mitglieder')}} ·
        ${{externalLink(source.city_government_url || '', 'Stadtregierungsmitglieder')}}.
        Lizenzhinweis: ${{escapeHtml(source.license || 'öffentliche Webseite, keine OGD-Lizenz gefunden')}}.
        ${{escapeHtml(source.reuse || 'Für Open Source werden nur kurze faktische Hinweise geführt; aktuelle Details offiziell prüfen.')}}
      `;
    }}

    function escapePlain(value) {{
      return String(value || '').replace(/\\s+/g, ' ').trim();
    }}

    function initServicesMap() {{
      if (!window.L || servicesMap) return;
      servicesMap = L.map('servicesMap').setView([47.0707, 15.4395], 12);
      addBaseLayer(servicesMap);
      servicesLayer = L.layerGroup().addTo(servicesMap);
      renderServicesCategoryFilter();
      renderCivicServices();
      renderServicesSourceNote();
    }}

    function renderServicesCategoryFilter() {{
      const current = servicesCategoryFilter.value;
      const categories = [...new Set(civicServices.map((item) => item.category).filter(Boolean))]
        .sort((left, right) => left.localeCompare(right, 'de-AT'));
      servicesCategoryFilter.innerHTML = '<option value="">Alle Kategorien</option>' + categories.map((category) =>
        `<option value="${{escapeHtml(category)}}">${{escapeHtml(category)}}</option>`
      ).join('');
      if (categories.includes(current)) servicesCategoryFilter.value = current;
    }}

    function renderCivicServices() {{
      if (!servicesLayer) return;
      servicesLayer.clearLayers();
      const query = normalizeSearchText(servicesSearch.value || '');
      const category = servicesCategoryFilter.value || '';
      const filtered = civicServices
        .map((service, index) => ({{ ...service, _index: index }}))
        .filter((service) => !category || service.category === category)
        .filter((service) => !query || normalizeSearchText([
          service.name,
          service.category,
          service.address,
          service.description,
          ...(service.services || []),
        ].join(' ')).includes(query));
      currentCivicServices = filtered;
      servicesStatus.textContent = `${{filtered.length}} Servicepunkte · Kontaktdaten offiziell prüfen`;
      servicesList.innerHTML = filtered.length ? filtered.map((service) => serviceListCardHtml(service)).join('') : '<div class="empty">Keine passenden Servicepunkte gefunden.</div>';
      const coordUses = new Map();
      filtered.forEach((service) => {{
        if (!Number.isFinite(service.lat) || !Number.isFinite(service.lon)) return;
        const coords = spreadRoadworkCoords({{ lat: service.lat, lon: service.lon }}, coordUses);
        const color = serviceColor(service.category);
        const marker = L.circleMarker([coords.lat, coords.lon], {{
          radius: 7,
          color,
          fillColor: color,
          fillOpacity: 0.82,
          weight: 2,
        }}).addTo(servicesLayer);
        marker.bindPopup(servicePopupHtml(service));
        marker.bindTooltip(`
          <strong>${{escapeHtml(service.name)}}</strong><br>
          ${{escapeHtml(service.category || 'Service')}}<br>
          ${{escapeHtml(service.address || '')}}
        `, {{ direction: 'top', sticky: true, opacity: 0.95 }});
        marker.on('click', () => highlightServiceList(service._index));
      }});
    }}

    function serviceListCardHtml(service) {{
      return `
        <button class="map-place" type="button" data-service-index="${{service._index}}">
          <strong>${{escapeHtml(service.name)}}</strong>
          <span>${{escapeHtml(service.category || 'Service')}} · ${{escapeHtml(service.address || 'Adresse auf offizieller Seite prüfen')}}</span>
          <small>${{escapeHtml(service.description || '')}}</small>
          <small>${{escapeHtml((service.services || []).join(', '))}}</small>
          <small>Quelle: ${{escapeHtml(service.source || 'Stadt Graz')}} · ${{escapeHtml(service.license || '')}}</small>
        </button>
      `;
    }}

    function servicePopupHtml(service) {{
      return `
        <strong>${{escapeHtml(service.name)}}</strong>
        <div>${{escapeHtml(service.category || 'Service')}}</div>
        <div>${{escapeHtml(service.address || '')}}</div>
        <div>${{escapeHtml(service.description || '')}}</div>
        <div>${{escapeHtml((service.services || []).join(', '))}}</div>
        <div>${{service.website ? externalLink(service.website, 'Website öffnen') : ''}}</div>
        <div>${{service.appointments_url ? externalLink(service.appointments_url, 'Termin/Öffnungszeiten prüfen') : ''}}</div>
        <div>Quelle: ${{externalLink(service.source_url || '', service.source || 'Stadt Graz')}} · ${{escapeHtml(service.license || '')}}</div>
      `;
    }}

    function serviceColor(category) {{
      const colors = {{
        'Bürgerservice': '#2563eb',
        'Meldewesen & Dokumente': '#7c3aed',
        'Bauen & Wohnen': '#ea580c',
        'Soziales': '#dc2626',
        'Familie & Bildung': '#db2777',
        'Gesundheit': '#0f766e',
        'Verkehr & Öffentlicher Raum': '#0891b2',
        'Umwelt': '#16a34a',
        'Abgaben & Finanzen': '#ca8a04',
        'Wirtschaft': '#475569',
        'Sicherheit & Notfälle': '#b91c1c',
        'Kommunale Services': '#4f46e5',
      }};
      return colors[category] || '#64748b';
    }}

    function highlightServiceList(index) {{
      servicesList.querySelectorAll('[data-service-index]').forEach((item) => {{
        item.classList.toggle('active', item.dataset.serviceIndex === String(index));
      }});
    }}

    function renderServicesSourceNote() {{
      const source = mobilitySources.civic_services || {{}};
      byId('servicesSourceNote').innerHTML = `
        Quelle: ${{externalLink(source.directory_url || 'https://www.graz.at/cms/beitrag/10019383/7743948/Aemter_und_Politik.html', 'Ämter + Politik')}} ·
        Telefonbuch: ${{externalLink(source.phonebook_url || 'https://www.graz.at/cms/ziel/7536192/', 'Telefonbuch der Stadt Graz')}} ·
        Termine: ${{externalLink(source.appointments_url || 'https://www.graz.at/termine', 'graz.at/termine')}}.
        Lizenzhinweis: ${{escapeHtml(source.license || 'öffentliche Webseite, keine OGD-Lizenz gefunden')}}.
        ${{escapeHtml(source.reuse || 'Für Open Source werden nur kurze faktische Hinweise geführt; aktuelle Details offiziell prüfen.')}}
      `;
    }}

    function renderDoctorsMap() {{
      const profession = doctorsProfessionFilter.value;
      const filtered = profession
        ? activeDoctors.filter((item) => doctorProfessionLabels(item).includes(profession))
        : activeDoctors;
      currentDoctorPlaces = filtered;
      renderHealthPlaces(filtered, doctorsLayer, doctorsList, doctorsStatus, doctorsProgress, doctorsProgressBar, 'Ordinationen', doctorColorForPlace);
    }}

    function renderDoctorsProfessionFilter() {{
      const current = doctorsProfessionFilter.value;
      const professions = [...new Set(activeDoctors.flatMap((item) =>
        doctorProfessionLabels(item)
      ))].sort((left, right) => left.localeCompare(right, 'de-AT'));
      doctorsProfessionFilter.innerHTML = '<option value="">Alle Fachrichtungen</option>' + professions.map((profession) =>
        `<option value="${{escapeHtml(profession)}}">${{escapeHtml(profession)}}</option>`
      ).join('');
      if (professions.includes(current)) doctorsProfessionFilter.value = current;
      else if (professions.includes('Allgemeinmedizin')) doctorsProfessionFilter.value = 'Allgemeinmedizin';
      else doctorsProfessionFilter.value = '';
    }}

    async function loadHealthPlacesFromOverpass(kind, status, force = false) {{
      const currentItems = kind === 'pharmacy' ? activePharmacies : activeDoctors;
      if (currentItems.length && !force) return [];
      status.textContent = `${{kind === 'pharmacy' ? 'Apotheken' : 'Ordinationen'}} werden aus OpenStreetMap geladen...`;
      const query = kind === 'pharmacy'
        ? '[out:json][timeout:20];(node["amenity"="pharmacy"](46.98,15.34,47.13,15.54);way["amenity"="pharmacy"](46.98,15.34,47.13,15.54);relation["amenity"="pharmacy"](46.98,15.34,47.13,15.54););out center tags;'
        : '[out:json][timeout:20];(node["amenity"="doctors"](46.98,15.34,47.13,15.54);way["amenity"="doctors"](46.98,15.34,47.13,15.54);relation["amenity"="doctors"](46.98,15.34,47.13,15.54);node["healthcare"="doctor"](46.98,15.34,47.13,15.54);way["healthcare"="doctor"](46.98,15.34,47.13,15.54);relation["healthcare"="doctor"](46.98,15.34,47.13,15.54);node["amenity"="veterinary"](46.98,15.34,47.13,15.54);way["amenity"="veterinary"](46.98,15.34,47.13,15.54);relation["amenity"="veterinary"](46.98,15.34,47.13,15.54);node["healthcare"="veterinary"](46.98,15.34,47.13,15.54);way["healthcare"="veterinary"](46.98,15.34,47.13,15.54);relation["healthcare"="veterinary"](46.98,15.34,47.13,15.54);node["amenity"="dentist"](46.98,15.34,47.13,15.54);way["amenity"="dentist"](46.98,15.34,47.13,15.54);relation["amenity"="dentist"](46.98,15.34,47.13,15.54);node["healthcare"="dentist"](46.98,15.34,47.13,15.54);way["healthcare"="dentist"](46.98,15.34,47.13,15.54);relation["healthcare"="dentist"](46.98,15.34,47.13,15.54););out center tags;';
      try {{
        const response = await fetch('https://overpass-api.de/api/interpreter', {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/x-www-form-urlencoded;charset=UTF-8' }},
          body: new URLSearchParams({{ data: query }}),
        }});
        if (!response.ok) throw new Error(`Overpass ${{response.status}}`);
        return parseOverpassHealthPlaces(await response.json(), kind);
      }} catch (error) {{
        status.textContent = `OSM-Liveabruf fehlgeschlagen; offizieller Link bleibt verfügbar.`;
        return [];
      }}
    }}

    function parseOverpassHealthPlaces(payload, kind) {{
      return (payload.elements || [])
        .map((element) => {{
          const tags = element.tags || {{}};
          const lat = element.lat ?? element.center?.lat;
          const lon = element.lon ?? element.center?.lon;
          const name = (tags.name || '').trim();
          if (!name || !Number.isFinite(lat) || !Number.isFinite(lon)) return null;
          return {{
            name,
            address: osmAddress(tags),
            kind: osmHealthKind(tags, kind),
            profession: osmHealthProfession(tags, kind),
            lat,
            lon,
            opening_hours: tags.opening_hours || '',
            phone: tags.phone || tags['contact:phone'] || '',
            website: healthWebsite(tags, name),
            source: 'OpenStreetMap',
            source_url: 'https://www.openstreetmap.org/copyright',
            license: 'ODbL',
          }};
        }})
        .filter(Boolean)
        .sort((left, right) => left.name.localeCompare(right.name, 'de-AT'));
    }}

    function osmHealthKind(tags, kind) {{
      if (kind === 'pharmacy') return 'Apotheke';
      if (tags.amenity === 'veterinary' || tags.healthcare === 'veterinary') return 'Tierarzt';
      if (tags.amenity === 'dentist' || tags.healthcare === 'dentist') return 'Zahnarzt';
      return 'Ordination';
    }}

    function osmHealthProfession(tags, kind) {{
      if (kind === 'pharmacy') return '';
      if (tags.amenity === 'veterinary' || tags.healthcare === 'veterinary') return 'Tierarzt';
      if (tags.amenity === 'dentist' || tags.healthcare === 'dentist') return 'Zahnarzt';
      const raw = tags['healthcare:speciality'] || tags.speciality || tags['healthcare:specialty'] || '';
      const values = String(raw).split(/[;,]/).map((part) => germanSpecialtyLabel(part)).filter(Boolean);
      return values.join(', ') || 'Allgemeinmedizin';
    }}

    function healthWebsite(tags, name) {{
      void name;
      for (const key of ['website', 'contact:website', 'url', 'contact:url', 'brand:website']) {{
        const website = normalizeWebsite(tags[key]);
        if (website) return website;
      }}
      return '';
    }}

    function normalizeWebsite(value) {{
      const website = String(value || '').trim();
      if (!website) return '';
      if (website.startsWith('http://')) return `https://${{website.slice(7)}}`;
      if (website.startsWith('https://')) return website;
      if (website.includes('.') && !/\\s/.test(website)) return `https://${{website}}`;
      return '';
    }}

    function germanSpecialtyLabel(value) {{
      const key = String(value || '').replace(/_/g, ' ').trim().toLocaleLowerCase('de-AT');
      const labels = {{
        doctor: 'Allgemeinmedizin',
        physician: 'Allgemeinmedizin',
        ordination: 'Allgemeinmedizin',
        'allgemeinmedizin': 'Allgemeinmedizin',
        'allgemeinmedizin/ordination': 'Allgemeinmedizin',
        'ordination/ärztin/arzt': 'Allgemeinmedizin',
        'ärztin/arzt': 'Allgemeinmedizin',
        arzt: 'Allgemeinmedizin',
        ärztin: 'Allgemeinmedizin',
        general: 'Allgemeinmedizin',
        'general practitioner': 'Allgemeinmedizin',
        'family medicine': 'Allgemeinmedizin',
        gp: 'Allgemeinmedizin',
        practice: 'Allgemeinmedizin',
        internal: 'Innere Medizin',
        'internal medicine': 'Innere Medizin',
        'innere medizin': 'Innere Medizin',
        cardiology: 'Kardiologie',
        kardiologie: 'Kardiologie',
        dermatology: 'Dermatologie',
        dermatologie: 'Dermatologie',
        'hautarzt': 'Dermatologie',
        'haut und geschlechtskrankheiten': 'Dermatologie',
        gynecology: 'Gynäkologie',
        gynaecology: 'Gynäkologie',
        gynaekologie: 'Gynäkologie',
        gynäkologie: 'Gynäkologie',
        'obstetrics and gynaecology': 'Gynäkologie und Geburtshilfe',
        obstetrics: 'Geburtshilfe',
        geburtshilfe: 'Geburtshilfe',
        ophthalmology: 'Augenheilkunde',
        optometry: 'Augenheilkunde',
        augenheilkunde: 'Augenheilkunde',
        orthopaedics: 'Orthopädie',
        orthopedics: 'Orthopädie',
        orthopaedic: 'Orthopädie',
        orthopedic: 'Orthopädie',
        orthopädie: 'Orthopädie',
        orthopaedie: 'Orthopädie',
        paediatrics: 'Kinderheilkunde',
        pediatrics: 'Kinderheilkunde',
        paediatric: 'Kinderheilkunde',
        pediatric: 'Kinderheilkunde',
        kinderheilkunde: 'Kinderheilkunde',
        psychiatry: 'Psychiatrie',
        psychiatrie: 'Psychiatrie',
        neurology: 'Neurologie',
        neurologie: 'Neurologie',
        radiology: 'Radiologie',
        radiologie: 'Radiologie',
        urology: 'Urologie',
        urologie: 'Urologie',
        surgery: 'Chirurgie',
        surgeon: 'Chirurgie',
        chirurgie: 'Chirurgie',
        'general surgery': 'Chirurgie',
        emergency: 'Notfallmedizin',
        'emergency medicine': 'Notfallmedizin',
        notfallmedizin: 'Notfallmedizin',
        anaesthetics: 'Anästhesiologie',
        anesthetics: 'Anästhesiologie',
        anaesthesiology: 'Anästhesiologie',
        anesthesiology: 'Anästhesiologie',
        anästhesiologie: 'Anästhesiologie',
        anaesthesiologie: 'Anästhesiologie',
        ent: 'Hals-Nasen-Ohren-Heilkunde',
        hno: 'Hals-Nasen-Ohren-Heilkunde',
        otolaryngology: 'Hals-Nasen-Ohren-Heilkunde',
        'ear nose throat': 'Hals-Nasen-Ohren-Heilkunde',
        'hals nasen ohren heilkunde': 'Hals-Nasen-Ohren-Heilkunde',
        oncology: 'Onkologie',
        onkologie: 'Onkologie',
        pulmonology: 'Lungenheilkunde',
        pneumology: 'Lungenheilkunde',
        pneumologie: 'Lungenheilkunde',
        lungenheilkunde: 'Lungenheilkunde',
        gastroenterology: 'Gastroenterologie',
        gastroenterologie: 'Gastroenterologie',
        nephrology: 'Nephrologie',
        nephrologie: 'Nephrologie',
        endocrinology: 'Endokrinologie',
        endokrinologie: 'Endokrinologie',
        rheumatology: 'Rheumatologie',
        rheumatologie: 'Rheumatologie',
        allergology: 'Allergologie',
        allergologie: 'Allergologie',
        psychology: 'Psychologie',
        psychologist: 'Psychologie',
        psychologie: 'Psychologie',
        psychotherapy: 'Psychotherapie',
        psychotherapist: 'Psychotherapie',
        psychotherapie: 'Psychotherapie',
        physiotherapy: 'Physiotherapie',
        physiotherapist: 'Physiotherapie',
        physiotherapie: 'Physiotherapie',
        occupational: 'Arbeitsmedizin',
        'occupational medicine': 'Arbeitsmedizin',
        arbeitsmedizin: 'Arbeitsmedizin',
        dentist: 'Zahnarzt',
        dentistry: 'Zahnarzt',
        zahnarzt: 'Zahnarzt',
        veterinary: 'Tierarzt',
        tierarzt: 'Tierarzt',
      }};
      return labels[key] || specialtyDisplayLabel(key);
    }}

    function specialtyDisplayLabel(value) {{
      const clean = String(value || '').replace(/[_/]+/g, ' ').replace(/\\s+/g, ' ').trim();
      if (!clean) return '';
      return clean.split(' ').map((word) => {{
        if (word.length <= 3 && word === word.toUpperCase()) return word;
        return word.charAt(0).toLocaleUpperCase('de-AT') + word.slice(1);
      }}).join(' ');
    }}

    function osmAddress(tags) {{
      const line = [tags['addr:street'], tags['addr:housenumber']].filter(Boolean).join(' ');
      const place = [tags['addr:postcode'], tags['addr:city'] || 'Graz'].filter(Boolean).join(' ');
      return [line, place].filter(Boolean).join(', ');
    }}

    async function renderHealthPlaces(items, layer, list, status, progress, progressBar, label, colorForItem) {{
      if (!layer) return;
      layer.clearLayers();
      const usable = (items || []).map((item, index) => ({{ ...item, _index: index }}));
      updateProgress(progress, progressBar, 0, usable.length, usable.length > 0);
      status.textContent = usable.length
        ? `${{usable.length}} ${{label}} aus OpenStreetMap · Zeiten je nach OSM-Pflege`
        : `Keine ${{label}} aus OSM-Cache geladen`;
      list.innerHTML = usable.length ? usable.map((item) => `
        <button class="map-place" type="button" data-health-index="${{item._index}}">
          <strong>${{escapeHtml(item.name)}}</strong>
          <span>${{escapeHtml(healthMeta(item, label))}}</span>
          <small class="hours">${{formatOpeningHoursHtml(item.opening_hours)}}</small>
          <small>${{escapeHtml(item.address || '')}}</small>
          <small>${{item.website ? `Website: ${{escapeHtml(item.website)}}` : ''}}</small>
        </button>
      `).join('') : '<div class="empty">Keine OSM-Daten geladen. Prüfe den Cache unter out/ oder nutze den offiziellen Link.</div>';
      let drawn = 0;
      for (const group of groupHealthPlacesByCoords(usable)) {{
        const coords = group.coords;
        drawn += 1;
        const first = group.items[0];
        const color = colorForItem(first);
        const marker = L.circleMarker([coords.lat, coords.lon], {{
          radius: 7,
          color,
          fillColor: color,
          fillOpacity: 0.78,
          weight: 2,
        }}).addTo(layer);
        marker.bindPopup(healthPopupHtml(group.items, label));
        marker.bindTooltip(`
          <strong>${{escapeHtml(first.name)}}${{group.items.length > 1 ? ` + ${{group.items.length - 1}} weitere` : ''}}</strong><br>
          ${{escapeHtml(healthMeta(first, label))}}<br>
          <span>Öffnungszeiten:</span><br>${{formatOpeningHoursHtml(first.opening_hours)}}
        `, {{ direction: 'top', sticky: true, opacity: 0.95 }});
        marker.on('click', () => highlightHealthList(list, first._index));
        status.textContent = `${{drawn}}/${{usable.length}} Standorte eingezeichnet · ${{usable.length}} ${{label}}`;
        updateProgress(progress, progressBar, drawn, usable.length, drawn < usable.length);
        if (drawn % 20 === 0) await nextFrame();
      }}
      status.textContent = `${{drawn}} Standorte · ${{usable.length}} ${{label}} · Zeiten je nach OSM-Pflege`;
      updateProgress(progress, progressBar, usable.length, usable.length, false);
    }}

    function groupHealthPlacesByCoords(items) {{
      const groups = new Map();
      items.forEach((item) => {{
        if (!Number.isFinite(item.lat) || !Number.isFinite(item.lon)) return;
        const key = `${{item.lat.toFixed(6)}},${{item.lon.toFixed(6)}}`;
        if (!groups.has(key)) groups.set(key, []);
        groups.get(key).push(item);
      }});
      return [...groups.values()].map((group) => ({{
        coords: {{ lat: group[0].lat, lon: group[0].lon }},
        items: group,
      }}));
    }}

    function healthPopupHtml(items, label) {{
      return items.map((item, index) => `
        <div class="health-popup-item">
          ${{index ? '<hr>' : ''}}
          <strong>${{escapeHtml(item.name)}}</strong>
          <div>${{escapeHtml(healthMeta(item, label))}}</div>
          <div>${{escapeHtml(item.address || '')}}</div>
          <div>Öffnungszeiten:<br>${{formatOpeningHoursHtml(item.opening_hours)}}</div>
          <div>${{item.phone ? `Tel.: ${{escapeHtml(item.phone)}}` : ''}}</div>
          <div>${{item.website ? externalLink(item.website, 'Website öffnen') : ''}}</div>
          <div>Quelle: ${{escapeHtml(item.source || 'OpenStreetMap')}} · ${{escapeHtml(item.license || 'ODbL')}}</div>
        </div>
      `).join('');
    }}

    function healthMeta(item, fallback) {{
      const profession = fallback === 'Ordination/Ärztin/Arzt'
        ? doctorProfessionLabels(item).join(', ')
        : item.profession;
      const values = [item.kind || fallback, profession].filter(Boolean);
      const seen = new Set();
      return values.filter((value) => {{
        const key = String(value).trim().toLocaleLowerCase('de-AT');
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      }}).join(' · ');
    }}

    function doctorProfessionLabels(item) {{
      return String(item.profession || item.kind || 'Allgemeinmedizin')
        .split(',')
        .map((part) => germanSpecialtyLabel(part.trim()))
        .filter(Boolean);
    }}

    function doctorLegendGroups(items) {{
      return [...new Set(items.flatMap((item) =>
        doctorProfessionLabels(item)
      ))].sort((left, right) => left.localeCompare(right, 'de-AT'));
    }}

    function doctorPrimaryGroup(item) {{
      return doctorProfessionLabels(item)[0] || 'Allgemeinmedizin';
    }}

    function doctorColorForPlace(item) {{
      return doctorColorForGroup(doctorPrimaryGroup(item));
    }}

    function doctorColorForGroup(group) {{
      const colors = {{
        'Allgemeinmedizin': '#2563eb',
        'Innere Medizin': '#0891b2',
        'Kardiologie': '#dc2626',
        'Dermatologie': '#ea580c',
        'Gynäkologie': '#be185d',
        'Augenheilkunde': '#7c3aed',
        'Orthopädie': '#16a34a',
        'Kinderheilkunde': '#ca8a04',
        'Psychiatrie': '#4f46e5',
        'Neurologie': '#9333ea',
        'Radiologie': '#0f766e',
        'Urologie': '#0369a1',
        'Zahnarzt': '#0d9488',
        'Tierarzt': '#65a30d',
      }};
      if (colors[group]) return colors[group];
      const palette = ['#0f766e', '#9333ea', '#b45309', '#be123c', '#047857', '#1d4ed8', '#c2410c', '#6d28d9', '#0e7490', '#a21caf'];
      let hash = 0;
      String(group || 'Fachrichtung').split('').forEach((char) => {{
        hash = ((hash * 31) + char.charCodeAt(0)) >>> 0;
      }});
      return palette[hash % palette.length];
    }}

    function formatOpeningHoursHtml(value) {{
      const text = String(value || '').trim();
      if (!text) return '<span>nicht in OSM</span>';
      return text
        .split(/;\\s*/)
        .filter(Boolean)
        .map((part) => `<span>${{escapeHtml(part)}}</span>`)
        .join('<br>');
    }}

    function highlightHealthList(list, index) {{
      list.querySelectorAll('[data-health-index]').forEach((item) => {{
        item.classList.toggle('active', item.dataset.healthIndex === String(index));
      }});
    }}

    function renderHealthSourceNote(sourceKey, targetId, note) {{
      const source = mobilitySources[sourceKey] || {{}};
      const officialSearch = sourceKey === 'pharmacies'
        ? externalButtonLink(source.official_search_url || 'https://www.apothekerkammer.at/apothekensuche', 'Nachtdienste öffnen')
        : externalLink(source.official_search_url || '', 'öffnen');
      byId(targetId).innerHTML = `
        Quelle: ${{externalLink(source.dataset_url || '', 'OpenStreetMap / ODbL')}} ·
        Lizenz: ${{escapeHtml(source.license || 'ODbL')}} ·
        Namensnennung: ${{escapeHtml(source.attribution || 'OpenStreetMap-Mitwirkende')}}.
        ${{note ? escapeHtml(note) : ''}}
        Offizielle Suche: ${{officialSearch}}.
      `;
    }}

    async function renderParkingGarages() {{
      if (!parkingLayer) return;
      parkingLayer.clearLayers();
      updateProgress(parkingProgress, parkingProgressBar, 0, 0, false);
      const sourceGarages = parkingGarages.length
        ? mergeParkingGarages(parkingGarages, supplementalParkingGarages)
        : mergeParkingGarages(parkingFallbackGarages, supplementalParkingGarages);
      currentParkingGarages = sourceGarages;
      const usable = sourceGarages.map((garage, index) => ({{ ...garage, _index: index }}));
      parkingStatus.textContent = `${{usable.length}} Garagen/Parkhäuser · Verfügbarkeit unbekannt`;
      updateProgress(parkingProgress, parkingProgressBar, 0, usable.length, true);
      parkingList.classList.toggle('parking-list', usable.length > 0);
      parkingList.innerHTML = usable.length
        ? usable.map((garage) => parkingListCardHtml(garage)).join('')
        : '<div class="empty">Keine Parkgaragen geladen. Prüfe den OGD-Cache oder die Netzwerkverbindung.</div>';
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
          <div>${{escapeHtml(parkingAvailabilityInfo(garage).text)}}</div>
          <div>${{externalLink(parkingDetailLink(garage).url, parkingDetailLink(garage).label)}}</div>
          <div>${{parkingAvailabilityInfo(garage).url ? externalLink(parkingAvailabilityInfo(garage).url, 'Live-Verfügbarkeit prüfen') : ''}}</div>
          <div>Quelle: ${{escapeHtml(garage.source || '')}} · ${{escapeHtml(garage.license || '')}}</div>
        `);
        marker.on('click', () => highlightParkingList(garage._index));
        parkingStatus.textContent = `${{drawn}}/${{usable.length}} Standorte eingezeichnet · Verfügbarkeit unbekannt`;
        updateProgress(parkingProgress, parkingProgressBar, drawn, usable.length, drawn < usable.length);
        if (drawn % 15 === 0) await nextFrame();
      }}
      parkingStatus.textContent = `${{drawn}}/${{usable.length}} Standorte · Verfügbarkeit unbekannt`;
      updateProgress(parkingProgress, parkingProgressBar, usable.length, usable.length, false);
      renderParkingSourceNote();
    }}

    function parkingListCardHtml(garage) {{
      const availability = parkingAvailabilityInfo(garage);
      const detailLink = parkingDetailLink(garage);
      const spaces = Number.isFinite(Number(garage.spaces)) && Number(garage.spaces) > 0 ? `${{Number(garage.spaces)}} Plätze` : 'Plätze unbekannt';
      return `
        <div class="parking-card" data-parking-index="${{garage._index}}" tabindex="0">
          <strong>${{escapeHtml(garage.name || 'Parkgarage')}}</strong>
          <span class="parking-card-meta">
            <span class="parking-pill">${{escapeHtml(garage.kind || 'Parkgarage')}}</span>
            <span class="parking-pill">${{escapeHtml(spaces)}}</span>
            <span class="parking-pill">${{escapeHtml(garage.supplemental ? 'Prüflink' : 'OGD')}}</span>
          </span>
          <span class="parking-address">${{escapeHtml(garage.address || 'Adresse nicht angegeben')}}</span>
          <span class="parking-note">${{escapeHtml(availability.text)}}</span>
          <span class="parking-card-actions">
            <a href="${{escapeHtml(detailLink.url)}}" target="_blank" rel="noopener noreferrer" data-parking-link="detail">${{escapeHtml(detailLink.label)}}</a>
            ${{availability.url && availability.url !== detailLink.url ? `<a href="${{escapeHtml(availability.url)}}" target="_blank" rel="noopener noreferrer" data-parking-link="availability">Live prüfen</a>` : ''}}
          </span>
        </div>
      `;
    }}

    function mergeParkingGarages(primary, supplemental) {{
      const merged = [...primary];
      const seen = new Set(primary.map(parkingIdentity));
      for (const garage of supplemental) {{
        const key = parkingIdentity(garage);
        if (seen.has(key)) continue;
        seen.add(key);
        merged.push({{ ...garage, supplemental: true }});
      }}
      return merged;
    }}

    function parkingIdentity(garage) {{
      const value = `${{garage.name || ''}} ${{garage.address || ''}}`
        .toLocaleLowerCase('de-AT')
        .normalize('NFD')
        .replace(/[\\u0300-\\u036f]/g, '')
        .replace(/\\b(ph|tg|pp|parkhaus|tiefgarage|parkplatz)\\b/g, '')
        .replace(/[^a-z0-9]+/g, ' ')
        .trim();
      return value;
    }}

    function parkingAvailabilityInfo(garage) {{
      const haystack = `${{garage.name || ''}} ${{garage.address || ''}}`.toLocaleLowerCase('de-AT');
      const hint = parkingAvailabilityHints.find((item) => item.pattern.test(haystack));
      if (hint) return hint;
      return {{ text: 'Live-Verfügbarkeit: unbekannt', url: '' }};
    }}

    function parkingDetailLink(garage) {{
      const explicit = normalizeWebsite(garage.source_url || garage.website || garage.url || '');
      const haystack = `${{garage.name || ''}} ${{garage.address || ''}}`;
      const match = parkingDetailLinks.find((item) => item.pattern.test(haystack));
      if (match) return match;
      if (explicit && !/data\\.gv\\.at|data\\.graz\\.gv\\.at|parkgaragen\\.csv/i.test(explicit)) {{
        return {{ url: explicit, label: garage.supplemental ? 'Betreiberseite öffnen' : 'Detailquelle öffnen' }};
      }}
      return {{
        url: explicit || (mobilitySources.parking || {{}}).dataset_url || 'https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html',
        label: 'Parkgarage prüfen'
      }};
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
        Parken.at wird nur verlinkt; Verfügbarkeit, Preise und Standortdaten werden wegen der Nutzungsbedingungen nicht übernommen.
        Zusätzliche Betreiberstandorte werden nur als Prüflinks ergänzt; Verfügbarkeit, Preise, Stellplatzzahlen und Scraping-Daten werden ohne Freigabe nicht übernommen.
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

    function renderTrafficSources() {{
      const sources = mobilitySources.traffic_data_audit || [];
      if (!trafficSourceList) return;
      trafficSourceList.innerHTML = sources.length ? sources.map((source) => `
        <div class="source-card">
          <strong>${{escapeHtml(source.name || 'Verkehrsdatenquelle')}}</strong>
          <div>${{escapeHtml([source.platform, source.coverage, source.license].filter(Boolean).join(' · '))}}</div>
          <div>${{escapeHtml(source.integration_status || 'geprüft, nicht integriert')}}</div>
          <div>${{escapeHtml((source.use_for || []).join(', '))}}</div>
          <div>${{escapeHtml(source.reuse || '')}}</div>
          <div>${{source.url ? externalLink(source.url, 'Quelle öffnen') : 'Quelle: lokal dokumentiert'}}</div>
        </div>
      `).join('') : '<div class="empty">Keine Verkehrsdatenquellen dokumentiert.</div>';
    }}

    async function renderRoadworkContext() {{
      if (!roadworksLayer) return;
      roadworksLayer.clearLayers();
      updateProgress(roadworksProgress, roadworksProgressBar, 0, 0, false);
      const combinedRoadworks = officialRoadworks;
      const roadworks = combinedRoadworks
        .map((roadwork, index) => ({{ ...roadwork, _index: index }}))
        .filter((roadwork) => (roadwork.location || roadwork.title) && (!activeRoadworkStatus || roadwork.time_status === activeRoadworkStatus))
        .map((roadwork, listIndex) => ({{ ...roadwork, _listIndex: listIndex }}));
      currentRoadworks = roadworks;
      renderRoadworksLegend();
      roadworksStatus.textContent = `${{roadworks.length}} Baustellen geladen`;
      updateProgress(roadworksProgress, roadworksProgressBar, 0, roadworks.length, true);
      roadworksList.innerHTML = roadworks.length ? roadworks.map((roadwork) => `
        <button class="map-place" type="button" data-roadwork-index="${{roadwork._listIndex}}">
          <strong>${{escapeHtml(roadwork.title || roadwork.location)}}</strong>
          <span>${{escapeHtml(roadworkStatusLabel(roadwork.time_status))}} · ${{escapeHtml(roadwork.period || 'Zeitraum nicht angegeben')}}</span>
          <small>${{escapeHtml([roadwork.description, roadwork.project].filter(Boolean).join(' · '))}}</small>
        </button>
      `).join('') : '<div class="empty">Keine Baustelleninfos geladen. Prüfe den lokalen Cache oder die Verbindung zu graz.at.</div>';
      let drawn = 0;
      const coordUses = new Map();
      for (const roadwork of roadworks) {{
        const location = roadwork.location || roadwork.title;
        const geocodeTarget = roadworkGeocodeTarget(roadwork);
        const coords = roadwork.coords || await roadworkCoords(roadwork);
        if (!coords) continue;
        const markerCoords = spreadRoadworkCoords(coords, coordUses);
        drawn += 1;
        const statusColor = roadworkStatusColor(roadwork.time_status);
        const marker = L.circleMarker([markerCoords.lat, markerCoords.lon], {{
          radius: 7,
          color: statusColor,
          fillColor: statusColor,
          fillOpacity: 0.82,
          weight: 2,
        }}).addTo(roadworksLayer);
        marker.bindPopup(`
          <strong>${{escapeHtml(roadwork.title || location)}}</strong>
          <div>Status: ${{escapeHtml(roadworkStatusLabel(roadwork.time_status))}}</div>
          <div>${{escapeHtml(roadwork.period || 'Zeitraum nicht angegeben')}}</div>
          <div>Positioniert nach: ${{escapeHtml(geocodeTarget.label)}}</div>
          <div>${{escapeHtml(roadwork.description || '')}}</div>
          <div>${{escapeHtml(roadwork.project || '')}}</div>
          <div>Quelle: ${{externalLink(roadwork.source_url || (mobilitySources.roadworks || {{}}).office_url || '', roadwork.source || 'Stadt Graz')}}</div>
        `);
        marker.on('click', () => highlightRoadworkList(roadwork._listIndex));
        if (drawn % 10 === 0) {{
          roadworksStatus.textContent = `${{drawn}}/${{roadworks.length}} Baustellen eingezeichnet`;
          updateProgress(roadworksProgress, roadworksProgressBar, drawn, roadworks.length, drawn < roadworks.length);
          await nextFrame();
        }}
      }}
      roadworksStatus.textContent = `${{drawn}}/${{roadworks.length}} Baustellen eingezeichnet`;
      updateProgress(roadworksProgress, roadworksProgressBar, roadworks.length, roadworks.length, false);
    }}

    function spreadRoadworkCoords(coords, coordUses) {{
      const key = `${{coords.lat.toFixed(5)}},${{coords.lon.toFixed(5)}}`;
      const count = coordUses.get(key) || 0;
      coordUses.set(key, count + 1);
      if (!count) return coords;
      const angle = ((count - 1) % 8) * (Math.PI / 4);
      const ring = Math.floor((count - 1) / 8) + 1;
      const offset = 0.00032 * ring;
      return {{
        lat: coords.lat + Math.sin(angle) * offset,
        lon: coords.lon + Math.cos(angle) * offset,
      }};
    }}

    function renderRoadworksLegend() {{
      if (!roadworksLegend) return;
      const counts = officialRoadworks.reduce((acc, roadwork) => {{
        const status = roadwork.time_status || 'unklar';
        acc[status] = (acc[status] || 0) + 1;
        return acc;
      }}, {{}});
      const items = [['', 'Alle'], ['aktuell', 'Aktuell'], ['kuenftig', 'Künftig'], ['abgeschlossen', 'Abgeschlossen'], ['unklar', 'Unklar']];
      roadworksLegend.innerHTML = items.map(([status, label]) => {{
        const count = status ? counts[status] || 0 : officialRoadworks.length;
        return `
          <button class="legend-item${{activeRoadworkStatus === status ? ' is-active' : ''}}" type="button" data-roadwork-status="${{escapeHtml(status)}}" style="--category-color: ${{roadworkStatusColor(status)}}">
            <span class="legend-swatch"></span>${{escapeHtml(label)}} (${{count}})
          </button>
        `;
      }}).join('');
    }}

    function roadworkStatusLabel(status) {{
      return roadworkStatusLabels[status] || roadworkStatusLabels.unklar;
    }}

    function roadworkStatusColor(status) {{
      return roadworkStatusColors[status] || roadworkStatusColors.unklar;
    }}

    function highlightRoadworkList(index) {{
      roadworksList.querySelectorAll('[data-roadwork-index]').forEach((item) => {{
        item.classList.toggle('active', item.dataset.roadworkIndex === String(index));
      }});
    }}

    async function roadworkCoords(roadworkOrLocation) {{
      const target = roadworkGeocodeTarget(roadworkOrLocation);
      if (target.coords) return target.coords;
      const coords = await geocodeLocation(target.query);
      return coords || target.fallbackCoords || null;
    }}

    function roadworkGeocodeTarget(roadworkOrLocation) {{
      const roadwork = typeof roadworkOrLocation === 'string'
        ? {{ title: roadworkOrLocation, location: roadworkOrLocation, description: '' }}
        : (roadworkOrLocation || {{}});
      const raw = [roadwork.location, roadwork.title, roadwork.description].filter(Boolean).join(' ');
      const normalized = String(raw || '').toLocaleLowerCase('de-AT');
      const title = String(roadwork.location || roadwork.title || '').trim();
      const description = String(roadwork.description || '').trim();
      const query = cleanRoadworkLocationForGeocoding(title, description);
      const fallback = roadworkFallbackCoords.find(([pattern]) => pattern.test(normalized));
      const fallbackCoords = fallback
        ? {{ lat: fallback[1][0], lon: fallback[1][1] }}
        : null;
      if (roadworkHasSpecificGeocodeQuery(query)) {{
        return {{
          query,
          label: query,
          coords: null,
          fallbackCoords,
          fallbackLabel: fallback ? fallback[2] : ''
        }};
      }}
      if (fallback) {{
        const [lat, lon] = fallback[1];
        return {{ query: fallback[2], label: fallback[2], coords: {{ lat, lon }} }};
      }}
      return {{ query, label: query, coords: null }};
    }}

    function cleanRoadworkLocationForGeocoding(title, description = '') {{
      let value = String(title || '').trim();
      const streetSuffix = '(?:straße|strasse|gasse|weg|platz|ring|gürtel|guertel|kai|allee)';
      const opposite = value.match(new RegExp(`^(.+?${{streetSuffix}})\\\\s+gegenüber\\\\s+(?:Nr\\\\.\\\\s*)?(\\\\d+[a-z]?)`, 'i'));
      if (opposite) return `${{opposite[1]}} ${{opposite[2]}}`;
      const streetRange = value.match(new RegExp(`^(.+?${{streetSuffix}})\\\\s+(\\\\d+[a-z]?)\\\\s*(?:bis|-|–)\\\\s*(\\\\d+[a-z]?)`, 'i'));
      if (streetRange) return `${{streetRange[1]}} ${{streetRange[2]}}`;
      const streetNumber = value.match(new RegExp(`^(.+?${{streetSuffix}})\\\\s+(\\\\d+[a-z]?)(?:\\\\b|\\\\s)`, 'i'));
      if (streetNumber) return `${{streetNumber[1]}} ${{streetNumber[2]}}`;
      value = value
        .replace(/\\bkm\\s*[\\d,.]+\\s*[-–]\\s*[\\d,.]+/i, '')
        .replace(/\\bim\\s+abschnitt\\b.+$/i, '')
        .replace(/\\bgegenüber\\b.+$/i, '')
        .replace(/\\s+-\\s+höhe\\b.+$/i, '')
        .replace(/\\([^)]*\\)/g, ' ')
        .replace(/\\s+/g, ' ')
        .trim();
      const crossing = title.match(/^(.+?(?:straße|gasse|weg|platz|ring|gürtel|kai))\\s+(?:Kreuzung|\\/|-)\\s*(.+?(?:straße|gasse|weg|platz|ring|gürtel|kai))/i);
      if (crossing) return `${{crossing[1]}} / ${{crossing[2]}}`;
      if (!value && description) value = String(description).split(';')[0].trim();
      return value || title || 'Graz';
    }}

    function roadworkHasSpecificGeocodeQuery(query) {{
      const value = String(query || '').trim();
      if (!value) return false;
      const streetSuffix = '(?:straße|strasse|gasse|weg|platz|ring|gürtel|guertel|kai|allee)';
      return new RegExp(`${{streetSuffix}}\\\\s+\\\\d+[a-z]?\\\\b`, 'i').test(value)
        || new RegExp(`${{streetSuffix}}\\\\s*\\\\/\\\\s*.+${{streetSuffix}}`, 'i').test(value);
    }}

    function periodsOverlap(startA, endA, startB, endB) {{
      if (!startA || !endA || !startB || !endB) return false;
      return startA <= endB && startB <= endA;
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

    function topLocalSources(question) {{
      return buildQuestionCandidateSet(question).displaySources;
    }}

    function buildQuestionCandidateSet(question) {{
      const query = normalizeSearchText(question);
      const tokens = relevantQuestionTokens(query);
      const focus = questionFocus(query);
      const allSources = allLocalQuestionSources();
      const scoredAll = allSources
        .map((source) => scoreQuestionSource(source, query, tokens, focus))
        .filter((source) => source.score >= minimumQuestionScore(tokens, query));
      const focused = focus.terms.length ? scoredAll.filter((source) => source.focusMatch) : scoredAll;
      const scorePool = focus.terms.length && (focused.length || focus.strict) ? focused : scoredAll;
      const scored = scorePool
        .sort((a, b) =>
          b.score - a.score ||
          b.coverage - a.coverage ||
          a.decisionPriority - b.decisionPriority ||
          String(b.date || '').localeCompare(String(a.date || '')) ||
          a.title.localeCompare(b.title, 'de-AT')
        );
      const displaySources = scored.slice(0, 40);
      const contextSources = balancedQuestionContextSources(scored);
      return {{
        scannedCount: allSources.length,
        candidateCount: scored.length,
        displaySources,
        contextSources,
        overview: questionCandidateOverview(scored),
        focusLabel: focus.label,
      }};
    }}

    function balancedQuestionContextSources(scored) {{
      const accepted = scored.filter((source) => source.decisionPriority === 0).slice(0, 18);
      const treated = scored.filter((source) => source.decisionPriority === 1).slice(0, 8);
      const rejected = scored.filter((source) => source.decisionPriority === 2).slice(0, 8);
      const open = scored.filter((source) => source.decisionPriority >= 3).slice(0, 18);
      const byId = new Map();
      [...accepted, ...treated, ...rejected, ...open, ...scored.slice(0, 24)].forEach((source) => {{
        const key = `${{source.kind}}|${{source.title}}|${{source.url}}`;
        if (!byId.has(key)) byId.set(key, source);
      }});
      return [...byId.values()].sort(answerSourceSort).slice(0, 48);
    }}

    function answerSourceSort(a, b) {{
      return (
        (b.score || 0) - (a.score || 0) ||
        String(b.date || '').localeCompare(String(a.date || '')) ||
        a.decisionPriority - b.decisionPriority ||
        String(a.title || '').localeCompare(String(b.title || ''), 'de-AT')
      );
    }}

    function questionCandidateOverview(scored) {{
      if (!scored.length) return 'Keine Kandidaten.';
      const byDecision = new Map();
      const byYear = new Map();
      scored.forEach((source) => {{
        const label = source.decisionLabel || 'sonstige Quelle';
        byDecision.set(label, (byDecision.get(label) || 0) + 1);
        const year = String(source.date || '').slice(0, 4) || 'ohne Jahr';
        byYear.set(year, (byYear.get(year) || 0) + 1);
      }});
      const decisionSummary = [...byDecision.entries()]
        .map(([label, count]) => `${{label}}: ${{count}}`)
        .join('; ');
      const yearSummary = [...byYear.entries()]
        .sort(([left], [right]) => left.localeCompare(right, 'de-AT'))
        .map(([year, count]) => `${{year}}: ${{count}}`)
        .join('; ');
      const acceptedTitles = scored
        .filter((source) => source.decisionPriority === 0)
        .slice(0, 10)
        .map((source) => source.title)
        .join(' | ');
      const openTitles = scored
        .filter((source) => source.decisionPriority >= 3)
        .slice(0, 10)
        .map((source) => source.title)
        .join(' | ');
      return [
        `Treffer nach Beschlusslage: ${{decisionSummary}}`,
        `Treffer nach Jahren: ${{yearSummary}}`,
        acceptedTitles ? `Wichtige beschlossene Treffer: ${{acceptedTitles}}` : '',
        openTitles ? `Wichtige offene/nicht beschlossene Treffer: ${{openTitles}}` : '',
      ].filter(Boolean).join('\\\\n');
    }}

    function allLocalQuestionSources() {{
      const businessIndex = recordsByListValue('geschaeftszahlen');
      const locationIndex = recordsByListValue('orte');
      const recordSources = records.map((record) => {{
        const title = record.titel || 'Eintrag';
        const decision = recordDecisionInfo(record);
        const voteSummary = voteSummaryForAi(record);
        const timeline = relatedRecordTimelineForAi(record, businessIndex, locationIndex);
        const sourceRole = recordSourceRoleForAi(record);
        const detailParts = [
          sourceRole,
          decision.label,
          record.typ,
          record.datum,
          userFacingStatusForAi(record),
          record.kategorie,
          userFacingResultForAi(record),
          voteSummary,
          (record.orte || []).join(', '),
          (record.geschaeftszahlen || []).join(', '),
          record.einbringer ? `Einbringer: ${{record.einbringer}}` : '',
          record.adressat ? `Adressat: ${{record.adressat}}` : '',
          record.ki_zusammenfassung,
          record.ki_warum_interessant,
          summaryPointsText(record),
        ];
        const contextParts = [
          `Typ: ${{record.typ || '-'}}`,
          sourceRole ? `Quellenart: ${{sourceRole}}` : '',
          `Datum: ${{record.datum || '-'}}`,
          record.kategorie ? `Thema: ${{record.kategorie}}` : '',
          record.einbringer ? `Einbringer: ${{record.einbringer}}` : '',
          record.adressat ? `Adressat: ${{record.adressat}}` : '',
          (record.geschaeftszahlen || []).length ? `Geschäftszahlen: ${{record.geschaeftszahlen.join(', ')}}` : '',
          (record.orte || []).length ? `Orte: ${{record.orte.join(', ')}}` : '',
          `Beschlusslage: ${{decision.label}}`,
          `Status: ${{userFacingStatusForAi(record)}}`,
          `Ergebnis: ${{userFacingResultForAi(record)}}`,
          voteSummary ? `Abstimmung: ${{voteSummary}}` : '',
          timeline ? `Verlauf/Folgebeschlüsse: ${{timeline}}` : '',
          record.ki_warum_interessant ? `Warum interessant: ${{record.ki_warum_interessant}}` : '',
          summaryPointsText(record) ? `Kernpunkte/offene Punkte: ${{summaryPointsText(record)}}` : '',
        ];
        return {{
          kind: 'Gemeinderatseintrag',
          decisionPriority: decision.priority,
          decisionLabel: decision.label,
          sourceRole,
          date: record.datum || '',
          title: `${{record.datum || '-'}} · ${{title}}`,
          recordType: record.typ || '',
          businessNumbers: record.geschaeftszahlen || [],
          recordId: record.record_id || '',
          places: record.orte || [],
          resultText: userFacingResultForAi(record),
          summaryText: '',
          detail: compactText(detailParts.join(' · '), 520),
          contextDetail: compactText(contextParts.filter(Boolean).join('\\\\n'), 1400),
          searchText: [
            recordHaystack(record),
            record.ki_zusammenfassung,
            record.ki_warum_interessant,
            summaryPointsText(record),
            voteSummary,
            timeline,
            sourceRole,
            record.adressat,
          ].join(' '),
          titleText: title,
          url: record.local_source_url || record.digra_url || record.source_url || ''
        }};
      }});
      const roadworkSources = officialRoadworks.map((roadwork) => {{
        const title = roadwork.title || roadwork.location || 'Baustelle';
        const contextParts = [
          `Status: ${{roadworkStatusLabel(roadwork.time_status)}}`,
          roadwork.location ? `Ort: ${{roadwork.location}}` : '',
          roadwork.period ? `Zeitraum: ${{roadwork.period}}` : '',
          roadwork.description ? `Beschreibung: ${{roadwork.description}}` : '',
          roadwork.project ? `Projekt: ${{roadwork.project}}` : '',
          roadwork.source ? `Quelle: ${{roadwork.source}}` : '',
        ];
        return {{
          kind: 'Baustelle',
          decisionPriority: 1,
          decisionLabel: 'keine Beschlussquelle',
          date: roadwork.start_date || '',
          title: `${{roadworkStatusLabel(roadwork.time_status)}} · ${{title}}`,
          detail: compactText([roadwork.period, roadwork.location, roadwork.description, roadwork.project].filter(Boolean).join(' · '), 520),
          contextDetail: compactText(contextParts.filter(Boolean).join('\\\\n'), 1200),
          searchText: [roadwork.title, roadwork.location, roadwork.description, roadwork.project, roadwork.period, roadwork.source].join(' '),
          titleText: title,
          url: roadwork.source_url || (mobilitySources.roadworks || {{}}).office_url || ''
        }};
      }});
      const parkingSources = parkingGarages.map((garage) => {{
        const title = garage.name || 'Parkgarage';
        const contextParts = [
          garage.kind ? `Typ: ${{garage.kind}}` : 'Typ: Tiefgarage/Parkhaus',
          garage.address ? `Adresse: ${{garage.address}}` : '',
          Number.isFinite(garage.spaces) ? `Stellplätze: ${{garage.spaces}}` : '',
          'Live-Verfügbarkeit: in den lokalen Daten nicht gesichert',
          garage.license ? `Lizenzhinweis: ${{garage.license}}` : '',
        ];
        return {{
          kind: 'Tiefgarage/Parkhaus',
          decisionPriority: 1,
          decisionLabel: 'keine Beschlussquelle',
          date: '',
          title,
          detail: compactText([garage.kind, garage.address, 'Verfügbarkeit: unbekannt'].filter(Boolean).join(' · '), 420),
          contextDetail: compactText(contextParts.filter(Boolean).join('\\\\n'), 900),
          searchText: [garage.name, garage.address, garage.kind, garage.license].join(' '),
          titleText: title,
          url: garage.source_url || (mobilitySources.parking || {{}}).dataset_url || ''
        }};
      }});
      const pharmacySources = pharmacies.map((place) => healthQuestionSource(place, 'Apotheke'));
      const doctorSources = doctors.map((place) => healthQuestionSource(place, 'Ordination/Ärztin/Arzt'));
      const civicServiceSources = civicServices.map(civicServiceQuestionSource);
      return [...recordSources, ...roadworkSources, ...parkingSources, ...pharmacySources, ...doctorSources, ...civicServiceSources];
    }}

    function civicServiceQuestionSource(service) {{
      const title = service.name || 'Service & Amt';
      const contextParts = [
        service.category ? `Kategorie: ${{service.category}}` : '',
        service.address ? `Adresse: ${{service.address}}` : '',
        service.description ? `Hinweis: ${{service.description}}` : '',
        (service.services || []).length ? `Services: ${{service.services.join(', ')}}` : '',
        service.appointments_url ? 'Termine und Öffnungszeiten bitte offiziell prüfen.' : '',
        service.license ? `Lizenzhinweis: ${{service.license}}` : '',
      ];
      return {{
        kind: 'Service & Amt',
        decisionPriority: 1,
        decisionLabel: 'Servicequelle, kein Beschluss',
        date: '',
        title,
        detail: compactText([service.category, service.address, service.description].filter(Boolean).join(' · '), 520),
        contextDetail: compactText(contextParts.filter(Boolean).join('\\\\n'), 1000),
        searchText: [service.name, service.category, service.address, service.description, ...(service.services || [])].join(' '),
        titleText: title,
        url: service.website || service.source_url || ''
      }};
    }}

    function healthQuestionSource(place, fallbackKind) {{
      const title = place.name || fallbackKind;
      const contextParts = [
        `Typ: ${{healthMeta(place, fallbackKind)}}`,
        place.address ? `Adresse: ${{place.address}}` : '',
        place.opening_hours ? `Öffnungszeiten laut OSM: ${{place.opening_hours}}` : '',
        place.phone ? `Telefon: ${{place.phone}}` : '',
        place.website ? `Website: ${{place.website}}` : '',
        fallbackKind === 'Apotheke' ? 'Nachtdienste bitte offiziell prüfen.' : '',
      ];
      return {{
        kind: fallbackKind,
        decisionPriority: 1,
        decisionLabel: 'keine Beschlussquelle',
        date: '',
        title,
        detail: compactText([healthMeta(place, fallbackKind), place.address, place.opening_hours].filter(Boolean).join(' · '), 420),
        contextDetail: compactText(contextParts.filter(Boolean).join('\\\\n'), 900),
        searchText: [place.name, place.kind, place.profession, place.address, place.opening_hours, place.phone, place.website].join(' '),
        titleText: title,
        url: place.website || ''
      }};
    }}

    function recordSourceRoleForAi(record) {{
      const type = String(record.typ || '');
      const submitter = String(record.einbringer || '').trim();
      const address = String(record.adressat || '').trim();
      const person = submitter || 'eine Person bzw. Fraktion im Gemeinderat';
      if (type === 'Schriftlicher Antrag') {{
        return `${{person}} stellte dazu einen selbständigen Antrag.`;
      }}
      if (type === 'Dringlichkeitsantrag') {{
        return `${{person}} stellte dazu einen Dringlichkeitsantrag.`;
      }}
      if (type === 'Abänderungsantrag' || type === 'Zusatzantrag') {{
        return `${{person}} brachte dazu einen ${{type}} ein.`;
      }}
      if (type === 'Schriftliche Anfrage') {{
        return address
          ? `${{person}} stellte dazu eine schriftliche Frage an ${{address}}. Das ist eine Anfrage und kein Beschluss. Wenn in den lokalen Daten keine Antwort steht, heißt das nur: In dieser Datenbasis ist keine Antwort erfasst. Es darf daraus nicht geschlossen werden, dass es keine Antwort gab.`
          : `${{person}} stellte dazu eine schriftliche Frage. Das ist eine Anfrage und kein Beschluss. Wenn in den lokalen Daten keine Antwort steht, heißt das nur: In dieser Datenbasis ist keine Antwort erfasst. Es darf daraus nicht geschlossen werden, dass es keine Antwort gab.`;
      }}
      if (type === 'Fragestunde') {{
        return address
          ? `${{person}} fragte dazu in der Fragestunde ${{address}}. Das ist eine Frage und kein Beschluss. Wenn in den lokalen Daten keine Antwort steht, heißt das nur: In dieser Datenbasis ist keine Antwort erfasst. Es darf daraus nicht geschlossen werden, dass es keine Antwort gab.`
          : `${{person}} stellte dazu in der Fragestunde eine Frage. Das ist eine Frage und kein Beschluss. Wenn in den lokalen Daten keine Antwort steht, heißt das nur: In dieser Datenbasis ist keine Antwort erfasst. Es darf daraus nicht geschlossen werden, dass es keine Antwort gab.`;
      }}
      if (type === 'Mitteilung') {{
        return submitter
          ? `Die Stadt bzw. die zuständige Stelle teilte dazu etwas mit; als Bearbeitung/Einbringung ist ${{submitter}} erfasst. Das ist eine Mitteilung, nicht automatisch ein Beschluss.`
          : 'Die Stadt bzw. die zuständige Stelle teilte dazu etwas mit. Das ist eine Mitteilung, nicht automatisch ein Beschluss.';
      }}
      if (type === 'Archiv-Tagesordnungspunkt') {{
        return 'Dieser Treffer stammt aus einer Tagesordnung in einem Archiv-PDF. Er belegt, dass das Stück auf der Tagesordnung stand; ein Beschluss oder Ergebnis muss aus Protokoll, DIGRA oder Folgebeschlüssen belegt werden.';
      }}
      return '';
    }}

    function recordsByListValue(field) {{
      const index = new Map();
      records.forEach((record) => {{
        (record[field] || []).forEach((value) => {{
          const key = normalizeSearchText(value);
          if (!key) return;
          if (!index.has(key)) index.set(key, []);
          index.get(key).push(record);
        }});
      }});
      return index;
    }}

    function recordDecisionInfo(record) {{
      const status = String(record.status_filter || record.status || '').toLocaleLowerCase('de-AT');
      const result = String(record.ergebnis || '').toLocaleLowerCase('de-AT');
      const combined = `${{status}} ${{result}}`;
      if (record.typ === 'Archiv-Tagesordnungspunkt') {{
        return {{ priority: 3, label: 'nur in Tagesordnung/Archivquelle belegt; kein Beschluss belegt' }};
      }}
      if (combined.includes('angenommen') || combined.includes('beschlossen')) {{
        return {{ priority: 0, label: 'beschlossen/angenommen' }};
      }}
      if (combined.includes('zur kenntnis') || combined.includes('quelle verfügbar')) {{
        return {{ priority: 1, label: 'behandelt, aber kein klassischer Beschluss' }};
      }}
      if (combined.includes('abgelehnt')) {{
        return {{ priority: 2, label: 'nicht beschlossen/abgelehnt' }};
      }}
      if (combined.includes('zugewiesen') || combined.includes('vertagt')) {{
        return {{ priority: 3, label: 'noch nicht beschlossen/offenes Verfahren' }};
      }}
      return {{ priority: 3, label: 'Beschlusslage in den lokalen Daten unklar' }};
    }}

    function voteSummaryForAi(record) {{
      const votes = Array.isArray(record.abstimmungen) ? record.abstimmungen : [];
      if (!votes.length) return '';
      return votes.map((vote) => {{
        const parts = [
          vote.gegenstimmen?.length ? `Gegenstimmen: ${{vote.gegenstimmen.join(', ')}}` : '',
          vote.enthaltungen?.length ? `Enthaltungen: ${{vote.enthaltungen.join(', ')}}` : '',
          vote.zustimmung?.length ? `Zustimmung: ${{vote.zustimmung.join(', ')}}` : '',
        ].filter(Boolean);
        return [vote.gegenstand, vote.ergebnis, ...parts].filter(Boolean).join(' - ');
      }}).join('; ');
    }}

    function relatedRecordTimelineForAi(record, businessIndex, locationIndex) {{
      const related = new Map();
      (record.geschaeftszahlen || []).forEach((value) => {{
        const key = normalizeSearchText(value);
        (businessIndex.get(key) || []).forEach((item) => {{
          if (item.record_id !== record.record_id) related.set(item.record_id, item);
        }});
      }});
      (record.orte || []).forEach((value) => {{
        const key = normalizeSearchText(value);
        (locationIndex.get(key) || []).forEach((item) => {{
          if (item.record_id !== record.record_id) related.set(item.record_id, item);
        }});
      }});
      const timeline = [...related.values()]
        .sort((a, b) =>
          String(a.datum || '').localeCompare(String(b.datum || '')) ||
          String(a.titel || '').localeCompare(String(b.titel || ''), 'de-AT')
        )
        .slice(0, 6)
        .map((item) => `${{item.datum || '-'}}: ${{item.titel || 'Eintrag'}} (${{recordDecisionInfo(item).label}}; ${{userFacingResultForAi(item)}})`);
      return timeline.join(' | ');
    }}

    function scoreQuestionSource(source, query, tokens, focus = {{ label: '', terms: [], strict: false }}) {{
      const haystack = normalizeSearchText(source.searchText || source.detail || '');
      const titleHaystack = normalizeSearchText(source.titleText || source.title || '');
      const matchedTokens = tokens.filter((token) => haystack.includes(token));
      const titleTokens = tokens.filter((token) => titleHaystack.includes(token));
      const focusMatch = questionFocusMatchesSource(focus, `${{titleHaystack}} ${{haystack}}`);
      const exactScore = query.length >= 6 && (haystack.includes(query) || titleHaystack.includes(query)) ? 8 : 0;
      const titleScore = titleTokens.length * 3;
      const detailScore = matchedTokens.length;
      const coverageBonus = tokens.length && matchedTokens.length === tokens.length ? 4 : 0;
      const focusScore = focusMatch ? 18 : 0;
      const score = exactScore + titleScore + detailScore + coverageBonus + focusScore;
      return {{
        ...source,
        score,
        coverage: matchedTokens.length,
        focusMatch,
        matchedTokens,
      }};
    }}

    function questionFocus(query) {{
      const manualFocuses = [
        ['Innere Stadt', ['innere stadt']],
        ['St. Leonhard', ['st leonhard', 'sankt leonhard', 'leonhard']],
        ['Geidorf', ['geidorf']],
        ['Lend', ['lend']],
        ['Gries', ['gries']],
        ['Jakomini', ['jakomini']],
        ['Liebenau', ['liebenau']],
        ['St. Peter', ['st peter', 'sankt peter']],
        ['Waltendorf', ['waltendorf']],
        ['Ries', ['ries']],
        ['Mariatrost', ['mariatrost']],
        ['Andritz', ['andritz']],
        ['Gösting', ['goesting', 'gösting']],
        ['Eggenberg', ['eggenberg']],
        ['Wetzelsdorf', ['wetzelsdorf']],
        ['Straßgang', ['strassgang', 'strasgang', 'straßgang']],
        ['Puntigam', ['puntigam']],
        ['Anrainerparken', ['anrainerparken', 'anrainerparkplatz', 'anwohnerparkzone', 'bewohnerparken']],
        ['Stadionbau/Stadion Liebenau', ['stadion liebenau', 'merkur arena', 'stadion graz', 'stadion']],
        ['Parken/Parkplätze', ['parkplatz', 'parkplaetze', 'parkplätze', 'parkzone', 'gruen zone', 'gruenzone', 'blaue zone', 'tiefgarage']],
        ['Baustellen', ['baustelle', 'baustellen', 'sperre', 'totalsperre', 'umleitung']],
        ['Apotheken', ['apotheke', 'apotheken', 'nachtdienst']],
        ['Ärzte/Ordinationen', ['arzt', 'ärztin', 'aerztin', 'ärzte', 'aerzte', 'ordination', 'ordinationen']],
        ['Services & Ämter', ['amt', 'aemter', 'ämter', 'service', 'buergeramt', 'bürgeramt', 'buergerinnenamt', 'bürgerinnenamt', 'meldezettel', 'hauptwohnsitz', 'pass', 'reisepass', 'termin', 'formular']],
      ];
      const dataFocuses = questionDataFocuses();
      const match = [...manualFocuses, ...dataFocuses]
        .sort((a, b) => b[1][0].length - a[1][0].length)
        .find(([, terms]) => terms.some((term) => query.includes(term)));
      if (match) return {{ label: match[0], terms: match[1], strict: Boolean(match[2]) }};
      const street = streetFocusMatch(query);
      if (street) {{
        const label = street[1].replace(/\\bstrasse\\b/g, 'straße');
        return {{ label, terms: [normalizeSearchText(street[1])], strict: true }};
      }}
      return {{ label: '', terms: [], strict: false }};
    }}

    function questionDataFocuses() {{
      const values = new Set();
      records.forEach((record) => (record.orte || []).forEach((value) => values.add(value)));
      officialRoadworks.forEach((roadwork) => {{
        [roadwork.location, roadwork.title, cleanRoadworkLocationForGeocoding(roadwork.title, roadwork.description).query].filter(Boolean).forEach((value) => values.add(value));
      }});
      parkingGarages.forEach((garage) => [garage.name, garage.address].filter(Boolean).forEach((value) => values.add(value)));
      pharmacies.forEach((place) => [place.name, place.address].filter(Boolean).forEach((value) => values.add(value)));
      doctors.forEach((place) => [place.name, place.address, place.profession].filter(Boolean).forEach((value) => values.add(value)));
      civicServices.forEach((service) => [service.name, service.address, service.category, ...(service.services || [])].filter(Boolean).forEach((value) => values.add(value)));
      return [...values]
        .map((value) => String(value || '').trim())
        .filter((value) => value.length >= 5 && value.length <= 80)
        .map((value) => {{
          const terms = questionFocusTermsForValue(value);
          return terms.length ? [value, terms, questionFocusLooksSpecific(terms)] : null;
        }})
        .filter(Boolean);
    }}

    function questionFocusTermsForValue(value) {{
      const normalized = normalizeSearchText(value);
      if (!normalized || normalized.length < 4) return [];
      const terms = [normalized];
      const street = streetFocusMatch(normalized);
      if (street && street[1] !== normalized) terms.push(street[1]);
      return [...new Set(terms)];
    }}

    function questionFocusMatchesSource(focus, haystack) {{
      if (!focus.terms.length) return true;
      if (focus.terms.some((term) => haystack.includes(term))) return true;
      if (!focus.strict) return false;
      const candidates = fuzzyFocusCandidates(haystack);
      return focus.terms
        .filter((term) => questionFocusLooksSpecific([term]))
        .some((term) => candidates.some((candidate) => isNearFocusMatch(term, candidate)));
    }}

    function streetFocusMatch(value) {{
      return String(value || '').match(/\\b((?:[\\p{{L}}0-9.-]+\\s+){{0,5}}[\\p{{L}}0-9.-]{{3,}}(?:strasse|straße|gasse|platz|weg|kai|ring|allee|guertel|gürtel)|[\\p{{L}}0-9.-]+(?:\\s+[\\p{{L}}0-9.-]+){{0,5}}\\s+(?:strasse|straße|gasse|platz|weg|kai|ring|allee|guertel|gürtel))\\b/u);
    }}

    function questionFocusLooksSpecific(terms) {{
      return terms.some((term) => {{
        const normalized = normalizeSearchText(term);
        return normalized.length >= 12 || Boolean(streetFocusMatch(normalized));
      }});
    }}

    function fuzzyFocusCandidates(haystack) {{
      const words = haystack.split(/\\s+/).filter((word) => word.length >= 4);
      const candidates = new Set(words);
      for (let index = 0; index < words.length - 1; index += 1) {{
        candidates.add(`${{words[index]}} ${{words[index + 1]}}`);
      }}
      return [...candidates].filter((candidate) => candidate.length >= 8);
    }}

    function isNearFocusMatch(term, candidate) {{
      const normalizedTerm = normalizeSearchText(term);
      const normalizedCandidate = normalizeSearchText(candidate);
      if (!normalizedTerm || !normalizedCandidate) return false;
      if (Math.abs(normalizedTerm.length - normalizedCandidate.length) > 2) return false;
      const maxDistance = normalizedTerm.length >= 14 ? 2 : 1;
      return boundedEditDistance(normalizedTerm, normalizedCandidate, maxDistance) <= maxDistance;
    }}

    function boundedEditDistance(left, right, maxDistance) {{
      let previous = Array.from({{ length: right.length + 1 }}, (_, index) => index);
      for (let i = 1; i <= left.length; i += 1) {{
        const current = [i];
        let rowMinimum = current[0];
        for (let j = 1; j <= right.length; j += 1) {{
          const substitution = previous[j - 1] + (left[i - 1] === right[j - 1] ? 0 : 1);
          const insertion = current[j - 1] + 1;
          const deletion = previous[j] + 1;
          const value = Math.min(substitution, insertion, deletion);
          current[j] = value;
          rowMinimum = Math.min(rowMinimum, value);
        }}
        if (rowMinimum > maxDistance) return maxDistance + 1;
        previous = current;
      }}
      return previous[right.length];
    }}

    function minimumQuestionScore(tokens, query) {{
      if (!tokens.length) return query.length >= 6 ? 2 : 1;
      if (tokens.length <= 2) return 1;
      return Math.max(2, Math.ceil(tokens.length * 0.35));
    }}

    function normalizeSearchText(value) {{
      return String(value || '')
        .toLocaleLowerCase('de-AT')
        .replace(/ß/g, 'ss')
        .replace(/[ä]/g, 'ae')
        .replace(/[ö]/g, 'oe')
        .replace(/[ü]/g, 'ue')
        .replace(/[^\\p{{L}}\\p{{N}}-]+/gu, ' ')
        .replace(/\\s+/g, ' ')
        .trim();
    }}

    function compactText(value, maxLength) {{
      const text = String(value || '').replace(/\\s+/g, ' ').trim();
      if (text.length <= maxLength) return text;
      return `${{text.slice(0, maxLength - 1).trim()}}…`;
    }}

    function relevantQuestionTokens(query) {{
      const stopwords = new Set([
        'also', 'alles', 'auch', 'bezirk', 'bezirke', 'dann', 'dass', 'dazu', 'deine',
        'einen', 'einer', 'eine', 'erzaehl', 'erzähle', 'gibt', 'hier', 'info', 'infos',
        'kann', 'kurz', 'mehr', 'nicht', 'oder', 'sage',
        'sag', 'sich', 'sind', 'über', 'ueber', 'und', 'warum', 'wenn', 'werden',
        'wird', 'wieso', 'zum'
      ]);
      const tokens = query
        .replace(/[^\\p{{L}}\\p{{N}}äöüß-]+/gu, ' ')
        .split(/\\s+/)
        .map((token) => token.trim())
        .filter((token) => token.length >= 4 && !stopwords.has(token));
      return [...new Set([...tokens, ...expandedQuestionTokens(tokens)])];
    }}

    function expandedQuestionTokens(tokens) {{
      const joined = tokens.join(' ');
      const expansions = [];
      if (/anrainer|anwohner|bewohner/.test(joined) && /park/.test(joined)) {{
        expansions.push('anwohnerparkzone', 'anrainerparkplatz', 'anrainerparken', 'parkzone', 'gruenzone', 'gruene', 'blaue', 'zone');
      }}
      if (/gruen|gruene|parkzone|park/.test(joined)) {{
        expansions.push('parkraumbewirtschaftung', 'bewohnerparken', 'parkraum');
      }}
      if (/stadion|arena/.test(joined)) {{
        expansions.push('stadion', 'stadion liebenau', 'stadion graz', 'merkur arena', 'merkur', 'arena');
      }}
      if (/amt|aemter|service|melde|hauptwohnsitz|pass|reisepass|termin|formular/.test(joined)) {{
        expansions.push('buergerinnenamt', 'buergeramt', 'meldewesen', 'dokumente', 'digitales amt', 'service');
      }}
      if (/muell|abfall|wasser|kanal|bim|bus|holding/.test(joined)) {{
        expansions.push('holding graz', 'kommunale services', 'abfall', 'wasser', 'oeffentlicher verkehr');
      }}
      return expansions;
    }}

    function userFacingStatusForAi(record) {{
      const questionStatus = questionAnswerStatus(record);
      if (questionStatus) return questionStatus;
      const status = String(record.status || '');
      if (['unklar', 'unbekannt', 'Unklar', 'Unbekannt'].includes(status)) return 'kein gesicherter Ergebnisstatus in den lokalen Daten';
      return status;
    }}

    function userFacingResultForAi(record) {{
      const questionStatus = questionAnswerStatus(record);
      if (questionStatus) return questionStatus;
      const result = String(record.ergebnis || '');
      if (!result || result === 'Unbekannt' || result.includes('DIGRA-Ergebnis fehlt')) {{
        return 'kein gesichertes Ergebnis in den lokalen Daten';
      }}
      return result;
    }}

    function questionAnswerStatus(record) {{
      if (!record || record.typ !== 'Fragestunde') return '';
      const votes = Array.isArray(record.abstimmungen) ? record.abstimmungen : [];
      const voteResult = votes.map((vote) => String(vote.ergebnis || '').toLocaleLowerCase('de-AT')).find((value) => value.includes('beantwortet'));
      if (voteResult) return voteResult.includes('mündlich') ? 'mündlich beantwortet' : 'schriftlich beantwortet';
      const result = String(record.ergebnis || '').toLocaleLowerCase('de-AT');
      if (result.includes('mündlich beantwortet')) return 'mündlich beantwortet';
      if (result.includes('schriftlich beantwortet')) return 'schriftlich beantwortet';
      return '';
    }}

    function renderAiSources(sources, options = {{}}) {{
      if (!sources.length) {{
        aiSources.hidden = false;
        aiSources.innerHTML = '<div class="empty">Keine lokalen Quellen gefunden.</div>';
        return;
      }}
      aiSources.hidden = false;
      const note = 'KI-generierte Antworten können Fehler enthalten. Bitte immer die Quellen prüfen.';
      const visible = sources.slice(0, 8);
      const hidden = sources.slice(8);
      aiSources.innerHTML = `
        <div class="question-source-note">${{escapeHtml(note)}}</div>
        <div class="question-sources-list">
          ${{visible.map((source, index) => sourceCardHtml(source, index)).join('')}}
        </div>
        ${{hidden.length ? `
          <details class="question-sources-more">
            <summary>Alle ${{escapeHtml(sources.length)}} Quellen anzeigen</summary>
            <div class="question-sources-list">
              ${{hidden.map((source, index) => sourceCardHtml(source, index + visible.length)).join('')}}
            </div>
          </details>
        ` : ''}}
      `;
    }}

    function sourceCardHtml(source, index) {{
      const recordId = source.recordId || '';
      const tag = recordId ? 'button' : (source.url ? 'a' : 'div');
      const attrs = recordId
        ? ` type="button" data-source-record-id="${{escapeHtml(recordId)}}"`
        : (source.url ? ` href="${{escapeHtml(source.url)}}" target="_blank" rel="noopener noreferrer"` : '');
      const matches = (source.matchedTokens || []).slice(0, 8).join(', ');
      const title = cleanAnswerTitle(source.titleText || source.title || source.kind || 'Quelle');
      const facts = sourceFacts(source).map((fact) => `<span class="source-kind">${{escapeHtml(fact)}}</span>`).join('');
      const description = sourceDescription(source);
      return `
        <${{tag}}${{attrs}} class="source-card">
          <span class="source-rank">${{index + 1}}</span>
          <span class="source-body">
            <span class="source-title">
              <span class="source-heading">${{escapeHtml(title)}}</span>
              ${{facts ? `<span class="source-facts">${{facts}}</span>` : ''}}
            </span>
            ${{description ? `<span class="source-meta">${{escapeHtml(description)}}</span>` : ''}}
            ${{matches ? `<span class="source-matches">Gefundene Begriffe: ${{escapeHtml(matches)}}</span>` : ''}}
            <span class="source-action">${{recordId ? 'Eintragsdetails öffnen' : (source.url ? 'Quelle öffnen' : 'Lokale Quelle')}}</span>
          </span>
        </${{tag}}>
      `;
    }}

    function sourceFacts(source) {{
      const facts = [];
      if (source.kind) facts.push(source.kind);
      if (source.date) facts.push(source.date);
      if (source.recordType && source.recordType !== source.kind) facts.push(source.recordType);
      if (source.decisionLabel) facts.push(source.decisionLabel);
      const business = Array.isArray(source.businessNumbers) ? source.businessNumbers.filter(Boolean).join(', ') : '';
      if (business) facts.push(`GZ ${{compactAnswerText(business, 46)}}`);
      const places = Array.isArray(source.places) ? source.places.filter(Boolean).join(', ') : '';
      if (places) facts.push(`Orte ${{compactAnswerText(places, 70)}}`);
      return facts.slice(0, 6);
    }}

    function sourceDescription(source) {{
      const parts = [];
      const role = conciseSourceRole(source);
      if (role) parts.push(role);
      const result = String(source.resultText || '').trim();
      if (result && !/kein gesichertes Ergebnis|DIGRA-Ergebnis fehlt|Unbekannt/i.test(result)) {{
        parts.push(`Ergebnis: ${{compactAnswerText(result, 130)}}`);
      }}
      return parts.join(' ');
    }}

    function rankSourcesFromAiAnswer(displaySources, contextSources, answer) {{
      const citedIndexes = citedSourceIndexes(answer);
      if (!citedIndexes.length) return displaySources;
      const ranked = [];
      const used = new Set();
      citedIndexes.forEach((sourceIndex) => {{
        const source = contextSources[sourceIndex - 1];
        if (!source) return;
        const key = sourceIdentity(source);
        if (used.has(key)) return;
        ranked.push(source);
        used.add(key);
      }});
      displaySources.forEach((source) => {{
        const key = sourceIdentity(source);
        if (used.has(key)) return;
        ranked.push(source);
        used.add(key);
      }});
      return ranked.slice(0, 40);
    }}

    function citedSourceIndexes(answer) {{
      const indexes = [];
      const seen = new Set();
      const patterns = [
        /\\[(\\d{{1,2}})\\]/g,
        /\\bQuelle\\s*(\\d{{1,2}})\\b/gi,
        /\\bQuellen\\s*(\\d{{1,2}})\\b/gi,
      ];
      patterns.forEach((pattern) => {{
        let match;
        while ((match = pattern.exec(answer))) {{
          const value = Number(match[1]);
          if (!Number.isInteger(value) || value < 1 || seen.has(value)) continue;
          seen.add(value);
          indexes.push(value);
        }}
      }});
      return indexes;
    }}

    function sourceIdentity(source) {{
      return `${{source.kind}}|${{source.title}}|${{source.url || ''}}`;
    }}

    function buildLocalQuestionAnswer(question, candidateSet) {{
      const sources = (candidateSet.answerSources || candidateSet.contextSources).slice(0, 30);
      const personAnswer = personContributionAnswer(question, sources, candidateSet);
      if (personAnswer) return personAnswer;
      const groups = groupedAnswerSources(sources);
      const sections = [
        answerSummarySection(groups, candidateSet),
        answerGroupHtml(
          'Beschlossen oder angenommen',
          groups.decided,
          'Diese Treffer haben in den lokalen Daten einen positiven Beschluss- oder Annahmestand.',
          'Zu dieser Frage finde ich keinen klar belegten Beschluss und keine belegte Umsetzung.'
        ),
        answerGroupHtml(
          'Behandelt oder mitgeteilt',
          groups.treated,
          'Diese Treffer zeigen, dass das Thema behandelt oder als Quelle erfasst wurde, aber nicht automatisch beschlossen ist.',
          ''
        ),
        answerGroupHtml(
          'Abgelehnt oder nur Verfahren',
          groups.rejected,
          'Diese Treffer sind abgelehnt oder in den lokalen Daten nur als Antrag, Anfrage oder Verfahren belegt.',
          ''
        ),
        answerGroupHtml(
          'Offene Anträge und Fragen',
          groups.open,
          'Diese Punkte sind für das Thema relevant, aber ohne gesicherten Umsetzungsstand in den lokalen Daten.',
          ''
        ),
      ].filter(Boolean).join('');
      const limits = answerSourceLimits(sources);
      return `
        <div class="answer-shell">
          <div class="answer-meta">
            ${{candidateSet.focusLabel ? `<span class="answer-pill">Fokus: ${{escapeHtml(candidateSet.focusLabel)}}</span>` : ''}}
          </div>
          ${{sections}}
          ${{limits ? `<div class="answer-note">Grenzen der Antwort: ${{escapeHtml(limits)}}</div>` : ''}}
        </div>
      `;
    }}

    function groupedAnswerSources(sources) {{
      const groups = {{ decided: [], treated: [], rejected: [], open: [] }};
      sources.forEach((source, index) => {{
        const item = {{ ...source, sourceIndex: index + 1, answerGroup: answerSourceGroup(source) }};
        groups[item.answerGroup].push(item);
      }});
      Object.keys(groups).forEach((key) => {{
        groups[key] = dedupeAnswerSources(groups[key]);
      }});
      return groups;
    }}

    function personContributionAnswer(question, sources, candidateSet) {{
      const query = normalizeSearchText(question);
      const year = questionYear(query);
      const person = detectedPersonName(query, candidateSet.rankedSources || sources);
      const wantsContributions = /\\b(eingebracht|eingebract|einbracht|hat|macht|antrag|antraege|anträge|gestellt|gemacht|berichtet|berichterstatt|gemeinderat|gemeinderaetin|gemeinderätin|robosch|pascuttini)\\b/i.test(query);
      if (!person || !wantsContributions) return '';
      const personKey = normalizeSearchText(person);
      const matching = personContributionSourcesFromList(candidateSet.rankedSources || sources, personKey, year)
        .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')) || String(a.title || '').localeCompare(String(b.title || ''), 'de-AT'));
      if (!matching.length) return '';
      const grouped = groupedAnswerSources(matching);
      const yearText = year ? ` im Jahr ${{year}}` : '';
      const motionCount = matching.filter((source) => /Antrag|Dringlichkeitsantrag/i.test(source.recordType || source.kind || '') || /Antrag/i.test(source.sourceRole || '')).length;
      const questionCount = matching.filter((source) => /Anfrage|Fragestunde|Frage/i.test(source.recordType || source.kind || '') || /Frage/i.test(source.sourceRole || '')).length;
      const decidedCount = grouped.decided.length;
      const openCount = grouped.open.length + grouped.rejected.length;
      const intro = [
        `Ich finde ${{matching.length}} lokale Gemeinderatseinträge, in denen ${{person}}${{yearText}} als Einbringerin, Fragestellerin oder Berichterstatterin erfasst ist.`,
        motionCount ? `Darunter sind ${{motionCount}} Anträge bzw. antragsähnliche Stücke.` : '',
        questionCount ? `${{questionCount}} Treffer sind Fragen oder Anfragen.` : '',
        decidedCount ? `${{decidedCount}} Treffer haben in den lokalen Daten einen positiven Beschluss- oder Annahmestand.` : '',
        openCount ? `${{openCount}} Treffer sind als offen, zugewiesen, abgelehnt oder nur als Verfahren zu lesen.` : '',
      ].filter(Boolean).join(' ');
      const sections = [
        `<section class="answer-section"><h3>Kurzantwort</h3><p>${{escapeHtml(intro)}}</p><p>${{escapeHtml('Wichtig: Berichterstattung bedeutet nicht automatisch, dass die Person den ursprünglichen Antrag politisch eingebracht hat. Bei Anträgen und Fragen ist das in den lokalen Daten direkter zuordenbar.')}}</p></section>`,
        answerGroupHtml('Beschlossen oder angenommen', grouped.decided, 'Diese Robosch-Treffer haben in den lokalen Daten einen positiven Beschluss- oder Annahmestand.', ''),
        answerGroupHtml('Behandelt oder mitgeteilt', grouped.treated, 'Diese Treffer wurden behandelt oder sind als Quelle erfasst, aber nicht automatisch ein eigener Beschluss.', ''),
        answerGroupHtml('Abgelehnt oder nur Verfahren', grouped.rejected, 'Diese Treffer sind abgelehnt oder nur als Verfahren belegt.', ''),
        answerGroupHtml('Offene Anträge und Fragen', grouped.open, 'Diese Punkte sind als Antrag, Anfrage oder offenes Verfahren erfasst.', ''),
      ].filter(Boolean).join('');
      return `
        <div class="answer-shell">
          <div class="answer-meta">
            <span class="answer-pill">${{matching.length}} passende Personentreffer</span>
            <span class="answer-pill">Person: ${{escapeHtml(person)}}</span>
            ${{year ? `<span class="answer-pill">Jahr: ${{escapeHtml(year)}}</span>` : ''}}
          </div>
          ${{sections}}
        </div>
      `;
    }}

    function questionYear(query) {{
      const match = String(query || '').match(/\\b(20\\d{{2}})\\b/);
      return match ? match[1] : '';
    }}

    function detectedPersonName(query, sources) {{
      const knownNames = [...new Set(sources.flatMap((source) => personNamesFromSource(source)))];
      const normalizedQuery = normalizeSearchText(query);
      const direct = knownNames.find((name) => {{
        const normalizedName = normalizeSearchText(name);
        const lastName = normalizedName.split(' ').pop();
        return normalizedQuery.includes(normalizedName) || (lastName && normalizedQuery.includes(lastName));
      }});
      return direct || '';
    }}

    function personNamesFromSource(source) {{
      const text = [source.submitter, source.sourceRole].filter(Boolean).join(' ');
      const names = [];
      const patterns = [
        /GR\\s+([A-ZÄÖÜ][\\p{{L}}.'-]+\\s+[A-ZÄÖÜ][\\p{{L}}.'-]+)/gu,
        /Klubob(?:frau|mann)\\s+[^A-ZÄÖÜ]*([A-ZÄÖÜ][\\p{{L}}.'-]+\\s+[A-ZÄÖÜ][\\p{{L}}.'-]+)/gu,
      ];
      patterns.forEach((pattern) => {{
        let match;
        while ((match = pattern.exec(text))) {{
          const name = compactAnswerText(match[1].replace(/\\s+/g, ' ').trim(), 80);
          if (name && !/Gemeinderat|Bürgermeister|Vize/i.test(name)) names.push(name);
        }}
      }});
      return names;
    }}

    function personContributionSources(question, candidateSet) {{
      const query = normalizeSearchText(question);
      const year = questionYear(query);
      const allRanked = candidateSet.rankedSources || [];
      const person = detectedPersonName(query, allRanked);
      if (!person) return [];
      return personContributionSourcesFromList(allRanked, normalizeSearchText(person), year)
        .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')) || String(a.title || '').localeCompare(String(b.title || ''), 'de-AT'));
    }}

    function personContributionSourcesFromList(sources, personKey, year) {{
      return sources.filter((source) => {{
        if (source.kind !== 'Gemeinderatseintrag') return false;
        const personText = normalizeSearchText([source.submitter, source.sourceRole].filter(Boolean).join(' '));
        if (!personText.includes(personKey)) return false;
        if (year && String(source.date || '').slice(0, 4) !== year) return false;
        return true;
      }});
    }}

    function answerSourceGroup(source) {{
      const role = String(source.sourceRole || '').toLocaleLowerCase('de-AT');
      const label = String(source.decisionLabel || '').toLocaleLowerCase('de-AT');
      if (source.decisionPriority === 0) return 'decided';
      if (source.decisionPriority === 2 || label.includes('abgelehnt') || label.includes('nicht beschlossen')) return 'rejected';
      if (role.includes('stellte dazu') || role.includes('brachte dazu') || role.includes('fragte dazu') || role.includes('schriftliche frage') || role.includes('fragestunde')) return 'open';
      if (source.decisionPriority === 1 || role.includes('teilte dazu')) return 'treated';
      return 'open';
    }}

    function dedupeAnswerSources(sources) {{
      const seen = new Set();
      const result = [];
      sources.forEach((source) => {{
        const key = sourceIdentity(source);
        if (seen.has(key)) return;
        seen.add(key);
        result.push(source);
      }});
      return result;
    }}

    function answerSummarySection(groups, candidateSet) {{
      const paragraphs = answerShortConclusion(groups, candidateSet)
        .filter(Boolean)
        .map((paragraph) => `<p>${{escapeHtml(paragraph)}}</p>`)
        .join('');
      return `
        <section class="answer-section">
          <h3>Kurzantwort</h3>
          ${{paragraphs}}
        </section>
      `;
    }}

    function answerGroupHtml(label, sources, lead, emptyText) {{
      if (!sources.length) {{
        return emptyText ? `
          <section class="answer-section">
            <h3>${{escapeHtml(label)}}</h3>
            <p>${{escapeHtml(emptyText)}}</p>
          </section>
        ` : '';
      }}
      const visible = sources.slice(0, 3);
      const hidden = sources.slice(3);
      const extra = hidden.length
        ? `
          <details class="answer-more">
            <summary>Alle ${{escapeHtml(sources.length)}} Treffer in diesem Abschnitt anzeigen</summary>
            <ul class="answer-list">${{hidden.map((source) => answerSourceHtml(source)).join('')}}</ul>
          </details>
        `
        : '';
      return `
        <section class="answer-section">
          <h3>${{escapeHtml(label)}}</h3>
          <p>${{escapeHtml(lead)}}</p>
          <ul class="answer-list">${{visible.map((source) => answerSourceHtml(source)).join('')}}</ul>
          ${{extra}}
        </section>
      `;
    }}

    function answerSourceHtml(source) {{
      const ref = `[${{source.sourceIndex}}]`;
      const title = cleanAnswerTitle(source.titleText || source.title || source.kind || 'Quelle');
      const role = conciseSourceRole(source);
      const detail = answerEvidenceDetail(source);
      const href = source.url ? ` href="${{escapeHtml(source.url)}}" target="_blank" rel="noopener noreferrer"` : '';
      const tag = source.url ? 'a' : 'span';
      const refHtml = `<${{tag}}${{href}} class="answer-ref answer-fact">${{escapeHtml(ref)}}</${{tag}}>`;
      const facts = [...answerEvidenceFacts(source).map((fact) => `<span class="answer-fact">${{escapeHtml(fact)}}</span>`), refHtml].join('');
      const titleHtml = source.recordId
        ? `<button class="answer-title-link" type="button" data-source-record-id="${{escapeHtml(source.recordId)}}">${{escapeHtml(title)}}</button>`
        : escapeHtml(title);
      return `
        <li class="answer-item">
          <div class="answer-item-title">${{titleHtml}}</div>
          <div class="answer-item-facts">${{facts}}</div>
          <div class="answer-item-meta">${{escapeHtml([role, detail].filter(Boolean).join(' '))}}</div>
        </li>
      `;
    }}

    function answerShortConclusion(groups, candidateSet) {{
      const decidedCount = groups.decided.length;
      const openCount = groups.open.length;
      const rejectedCount = groups.rejected.length;
      const treatedCount = groups.treated.length;
      const focus = answerFocusText(candidateSet);
      const decidedTheme = answerThemeText(groups.decided, focus);
      if (decidedCount) {{
        const decisionText = answerDecisionText(groups.decided);
        const statusText = answerOpenStatusText(openCount, rejectedCount, treatedCount);
        return [
          `${{focus ? `Zu ${{focus}}` : 'Zur Frage'}} finde ich in den lokalen Daten ${{decidedCount}} belegte positive Beschluss- oder Annahmetreffer. ${{decidedTheme}}`,
          `${{decisionText}} ${{answerLatestDecisionText(groups.decided)}}`,
          answerExampleSummaryText(groups.decided),
          statusText || 'In den priorisierten Quellen sind keine zusätzlichen offenen oder abgelehnten Punkte hervorgehoben.'
        ];
      }}
      if (treatedCount || openCount || rejectedCount) {{
        const statusText = answerOpenStatusText(openCount, rejectedCount, treatedCount);
        return [
          `${{focus ? `Zu ${{focus}}` : 'Zur Frage'}} finde ich lokale Treffer, aber keinen klar belegten Beschluss und keine belegte Umsetzung.`,
          statusText || 'Die vorhandenen Treffer sind deshalb als offene oder nur behandelte Punkte zu lesen.',
        ];
      }}
      return ['In den lokalen Quellen ist dazu kein belastbarer Treffer mit Beschlusslage erkennbar.'];
    }}

    function answerExampleSummaryText(sources) {{
      const examples = sources
        .slice()
        .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')) || String(a.title || '').localeCompare(String(b.title || ''), 'de-AT'))
        .slice(0, 3)
        .map((source) => {{
          const ref = source.sourceIndex ? ` [${{source.sourceIndex}}]` : '';
          const title = cleanAnswerTitle(source.titleText || source.title || source.kind || 'Quelle');
          const summary = sourceShortSummary(source);
          const titleText = compactAnswerText(title || 'ein Treffer', 150);
          return summary ? `${{titleText}}${{ref}} - ${{compactAnswerText(summary, 220)}}` : `${{titleText}}${{ref}}`;
        }})
        .filter(Boolean);
      return examples.length ? `Die jüngsten positiven Treffer betreffen ${{examples.join('; ')}}.` : '';
    }}

    function sourceShortSummary(source) {{
      const summary = String(source.summaryText || '').replace(/\\s+/g, ' ').trim();
      if (summary) return compactAnswerText(summary, 210);
      const result = String(source.resultText || '').replace(/\\s+/g, ' ').trim();
      if (result && !/kein gesichertes Ergebnis|DIGRA-Ergebnis fehlt|Unbekannt/i.test(result)) {{
        return `Ergebnis ${{compactAnswerText(result.replace(/\\s*:\\s*/g, ' '), 170)}}`;
      }}
      const role = conciseSourceRole(source);
      return role ? compactAnswerText(role, 170) : '';
    }}

    function answerFocusText(candidateSet) {{
      const label = String(candidateSet.focusLabel || '').trim();
      if (label) return label;
      return '';
    }}

    function answerThemeText(sources, focus) {{
      if (!sources.length) return 'Der genaue Inhalt muss in den Einzelquellen geprüft werden.';
      const titles = sources
        .slice()
        .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')))
        .slice(0, 6)
        .map((source) => cleanAnswerTitle(source.titleText || source.title))
        .filter(Boolean);
      const joined = titles.join(' ').toLocaleLowerCase('de-AT');
      if (/stadion|liebenau|merkurstadion/.test(joined)) {{
        return 'Inhaltlich geht es vor allem um das Stadion Liebenau, die Stadion Graz-Liebenau GmbH, Finanzierung, Verwaltung und vorbereitende Projekt- oder Modernisierungsschritte.';
      }}
      if (/parkplatz|parken|parkraum|garage/.test(joined)) {{
        return 'Inhaltlich geht es vor allem um Parkraum, Parkregelungen, betroffene Standorte und die Frage, ob daraus konkrete Maßnahmen wurden.';
      }}
      if (/sozial|pflege|armut|gesundheit|behinder/.test(joined)) {{
        return 'Inhaltlich geht es vor allem um soziale Leistungen, Zuständigkeiten, Versorgung oder sensible Verwaltungsbereiche.';
      }}
      if (/schule|kindergarten|bildung|jugend/.test(joined)) {{
        return 'Inhaltlich geht es vor allem um Bildung, Kinderbetreuung, Schulen oder Angebote für junge Menschen.';
      }}
      if (/budget|kosten|förder|foerder|finanz|euro/.test(joined)) {{
        return 'Inhaltlich geht es vor allem um öffentliche Mittel, Kosten, Genehmigungen oder finanzielle Kontrolle.';
      }}
      if (/verkehr|straße|strasse|rad|bus|bahn|mobilität|mobilitaet/.test(joined)) {{
        return 'Inhaltlich geht es vor allem um Verkehr, Mobilität, Infrastruktur oder die Nutzung des öffentlichen Raums.';
      }}
      if (focus) {{
        return `Die positiven Treffer betreffen mehrere Gemeinderatsstücke zu diesem Schwerpunkt und müssen im Zusammenhang gelesen werden.`;
      }}
      return 'Die positiven Treffer betreffen mehrere Gemeinderatsstücke mit ähnlichem Schwerpunkt.';
    }}

    function answerDecisionText(sources) {{
      const results = sources.map((source) => String(source.resultText || '').toLocaleLowerCase('de-AT')).join(' ');
      if (results.includes('einstimmig')) return 'Mehrere der gefundenen positiven Treffer sind als einstimmig angenommene Anträge dokumentiert.';
      if (results.includes('mehrheitlich') || results.includes('mehrstimmig')) return 'Die lokalen Daten weisen dabei mehrheitlich angenommene Beschlüsse aus.';
      return 'Die lokalen Daten belegen dabei positive Beschluss- oder Annahmestände, nicht nur Anträge oder Fragen.';
    }}

    function answerLatestDecisionText(sources) {{
      const latest = sources
        .slice()
        .sort((a, b) => String(b.date || '').localeCompare(String(a.date || '')))[0];
      if (!latest) return '';
      const date = latest.date ? `Der jüngste positive Treffer ist vom ${{latest.date}}` : 'Der jüngste positive Treffer';
      const result = latest.resultText ? `; als Ergebnis ist ${{compactAnswerText(latest.resultText, 120)}} erfasst` : '';
      const type = latest.recordType || latest.kind ? ` (${{latest.recordType || latest.kind}})` : '';
      return `${{date}}${{type}}${{result}}.`;
    }}

    function answerOpenStatusText(openCount, rejectedCount, treatedCount) {{
      const parts = [];
      if (treatedCount) parts.push(`${{treatedCount}} weitere Treffer sind behandelt oder mitgeteilt, aber kein klassischer Beschluss`);
      if (openCount) parts.push(`${{openCount}} relevante Punkte bleiben als Antrag, Anfrage oder offenes Verfahren einzuordnen`);
      if (rejectedCount) parts.push(`${{rejectedCount}} Treffer sind abgelehnt oder nicht beschlossen`);
      if (!parts.length) return '';
      return `Daneben gilt: ${{parts.join('; ')}}. Diese Trennung ist wichtig, weil Anträge und Fragen noch keine Umsetzung belegen.`;
    }}

    function answerEvidenceDetail(source) {{
      const parts = [];
      const places = Array.isArray(source.places) ? source.places.filter(Boolean).join(', ') : '';
      if (places) parts.push(`Orte: ${{compactAnswerText(places, 80)}}`);
      const result = String(source.resultText || '').trim();
      if (result && !/kein gesichertes Ergebnis|DIGRA-Ergebnis fehlt|Unbekannt/i.test(result)) {{
        parts.push(`Ergebnis: ${{compactAnswerText(result, 110)}}`);
      }}
      return parts.join(' · ');
    }}

    function answerEvidenceFacts(source) {{
      const facts = [];
      if (source.date) facts.push(source.date);
      if (source.recordType || source.kind) facts.push(source.recordType || source.kind);
      if (source.decisionLabel) facts.push(source.decisionLabel);
      const business = Array.isArray(source.businessNumbers) ? source.businessNumbers.filter(Boolean).join(', ') : '';
      if (business) facts.push(`GZ ${{compactAnswerText(business, 42)}}`);
      return facts.slice(0, 4);
    }}

    function cleanAnswerTitle(value) {{
      let text = String(value || 'Quelle').replace(/^\\d{{4}}-\\d{{2}}-\\d{{2}}\\s*·\\s*/, '').replace(/\\s+/g, ' ').trim();
      text = text.replace(/^(?:Berichterstatter(?:in|:in)?|Bearbeiter(?:in|:in)?|Einbringer(?:in|:in)?)\\s*:?\\s*[^:;]{{0,220}}?(?:\\((?:KPÖ|KPOE|Grüne|Gruene|SPÖ|SPOE|ÖVP|OEVP|FPÖ|FPOE|NEOS|KFG|GRÜNE)\\)|,?\\s(?:KPÖ|KPOE|Grüne|Gruene|SPÖ|SPOE|ÖVP|OEVP|FPÖ|FPOE|NEOS|KFG|GRÜNE))\\s+/i, '');
      text = text.replace(/\\s+(?:Sehr geehrte Frau|Sehr geehrter Herr|Sehr geehrte Damen und Herren).*$/i, '');
      return compactAnswerText(text, 150);
    }}

    function conciseSourceRole(source) {{
      const role = String(source.sourceRole || '').trim();
      if (!role) return '';
      if (role.includes('selbständigen Antrag')) return 'Schriftlicher Antrag.';
      if (role.includes('Dringlichkeitsantrag')) return 'Dringlichkeitsantrag.';
      if (role.includes('schriftliche Frage')) return 'Das ist eine schriftliche Anfrage und kein Beschluss.';
      if (role.includes('Fragestunde')) return 'Das ist eine Frage in der Fragestunde und kein Beschluss.';
      if (role.includes('teilte dazu')) return 'Das ist eine Mitteilung.';
      if (role.includes('Archiv-PDF')) return 'Das belegt die Behandlung im Archiv, aber nicht automatisch einen Beschluss.';
      return compactAnswerText(role, 180);
    }}

    function answerSourceLimits(sources) {{
      const hasDecision = sources.some((source) => source.decisionPriority === 0);
      const hasOpen = sources.some((source) => answerSourceGroup(source) === 'open');
      const notes = [];
      if (!hasDecision) notes.push('Eine Umsetzung ist nur dann genannt, wenn sie in den lokalen Quellen ausdrücklich belegt ist; aus einem Antrag oder einer Frage allein wird keine Umsetzung abgeleitet.');
      if (hasOpen) notes.push('Bei Anfragen und Fragestunden bedeutet "keine Antwort erfasst" nur, dass die Antwort in dieser lokalen Datenbasis fehlt.');
      return notes.join(' ');
    }}

    function compactAnswerText(value, maxLength) {{
      const text = String(value || '').replace(/\\s+/g, ' ').trim();
      if (text.length <= maxLength) return text;
      return `${{text.slice(0, maxLength - 1).trim()}}…`;
    }}

    async function askLocalAi() {{
      hideQuestionSuggestions();
      const question = aiQuestion.value.trim();
      showQuestionResultTabs('answer');
      if (!question) {{
        aiAnswer.hidden = false;
        aiAnswer.textContent = 'Bitte zuerst eine Frage eingeben.';
        aiSources.hidden = true;
        aiSources.innerHTML = '';
        return;
      }}
      const candidateSet = buildQuestionCandidateSet(question);
      const personSources = personContributionSources(question, candidateSet);
      const answerSources = personSources.length ? personSources : candidateSet.contextSources.slice(0, 30);
      candidateSet.answerSources = answerSources;
      renderAiSources(answerSources);
      if (!answerSources.length) {{
        aiAnswer.hidden = false;
        aiAnswer.innerHTML = `<div class="answer-shell"><section class="answer-section"><h3>Keine belastbaren Treffer</h3><p>Ich habe keine belastbaren Treffer zur Frage gefunden. Ohne Quellen wird keine Antwort erzeugt.</p></section></div>`;
        return;
      }}
      aiAnswer.hidden = false;
      aiAnswer.innerHTML = buildLocalQuestionAnswer(question, candidateSet);
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
      updateProgress(mapProgress, mapProgressBar, done, total, active);
    }}

    function updateProgress(progress, progressBar, done, total, active) {{
      if (!progress || !progressBar) return;
      const percent = total > 0 ? Math.round((done / total) * 100) : 0;
      progress.classList.toggle('is-active', Boolean(active && total > 0));
      progressBar.style.width = `${{Math.max(0, Math.min(100, percent))}}%`;
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
      const preloaded = preloadedLocationCache[location];
      if (preloaded && Number.isFinite(preloaded.lat) && Number.isFinite(preloaded.lon)) {{
        coordsByLocation.set(location, preloaded);
        return preloaded;
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
      return `<a href="${{escapeHtml(value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(text)}}</a>`;
    }}

    function externalLink(url, text) {{
      const value = String(url || '');
      if (!value.startsWith('https://')) return '-';
      return `<a href="${{escapeHtml(value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(text)}}</a>`;
    }}

    function externalButtonLink(url, text) {{
      const value = String(url || '');
      if (!value.startsWith('https://')) return '-';
      return `<a class="primary-link" href="${{escapeHtml(value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(text)}}</a>`;
    }}

    function localPdfLink(url, text) {{
      const value = String(url || '');
      if (!value || value.startsWith('http') || value.includes('..')) return '-';
      return `<a href="${{escapeHtml(value)}}" target="_blank" rel="noopener noreferrer">${{escapeHtml(text)}}</a>`;
    }}

    function pdfPageField(record) {{
      if (record.local_source_url) {{
        return localPdfLink(record.local_source_url, record.source_page ? `Seite ${{record.source_page}} öffnen` : 'PDF öffnen');
      }}
      return escapeHtml(record.source_page || '-');
    }}

    function statusDotClass(record) {{
      const status = String(record.status_filter || record.status || '').toLocaleLowerCase('de-AT');
      if (status.includes('angenommen')) return 'accepted';
      if (status.includes('abgelehnt')) return 'rejected';
      return 'neutral';
    }}

    function statusDotLabel(record) {{
      const status = String(record.status || record.status_filter || 'sonstiger Status');
      return status || 'sonstiger Status';
    }}

    function tableResultHtml(record) {{
      const rawResult = String(record.ergebnis || '');
      const missingDigra = rawResult.includes('DIGRA-Ergebnis fehlt');
      const resultText = missingDigra
        ? 'Kein Ergebnis in den lokalen DIGRA-Daten erfasst'
        : rawResult;
      const source = record.ergebnisquelle ? `<span class="badge">${{escapeHtml(record.ergebnisquelle)}}</span>` : '';
      const link = record.digra_url ? digraLink(record.digra_url, missingDigra ? 'DIGRA-Dokument öffnen' : 'DIGRA') : '';
      return `${{escapeHtml(resultText)}}${{source || link ? '<br>' : ''}}${{source}} ${{link}}`.trim();
    }}

    function tableStatusHtml(record) {{
      const status = `<span class="badge">${{tableStatusLabelHtml(record.status || '')}}</span>`;
      const link = record.digra_url
        ? digraLink(record.digra_url, record.ergebnisquelle || 'Quelle')
        : (record.source_url ? externalLink(record.source_url, 'Quelle') : '');
      return link ? `${{status}}<br><span class="source-link">${{link}}</span>` : status;
    }}

    function tableStatusLabelHtml(value) {{
      return escapeHtml(value);
    }}

    function tableMobileSummaryHtml(record) {{
      const summary = record.ki_zusammenfassung || '';
      if (summary) return escapeHtml(compactText(summary, 360));
      const result = String(record.ergebnis || '').trim();
      return result ? escapeHtml(compactText(result, 260)) : '-';
    }}

    function tableMobileSourceHtml(record) {{
      const links = [];
      if (record.digra_url) links.push(digraLink(record.digra_url, 'DIGRA öffnen'));
      if (record.source_url) links.push(externalLink(record.source_url, 'Quelle öffnen'));
      if (record.local_source_url) links.push(localPdfLink(record.local_source_url, 'PDF öffnen'));
      return links.filter((value) => value && value !== '-').join('<br>') || '-';
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
            <button class="summary-toggle" type="button" data-summary-kind="summary" aria-expanded="true">
              <span class="summary-toggle-label">Zusammenfassung</span>
              <span class="summary-toggle-sub">Inhalt, Einordnung und Ergebnisstand kompakt zusammengefasst.</span>
            </button>
            <div class="summary-text">${{summaryTextHtml(record, 'summary')}}</div>
          </div>
        `);
      }}
      return blocks.length ? `<div class="summary-blocks">${{blocks.join('')}}</div>` : '';
    }}

    function summaryTextHtml(record, kind) {{
      const text = clippedSummaryDisplayText(record, kind);
      const parts = splitSummaryParagraphs(text);
      return parts.map((part) => {{
        const className = part.startsWith('[Gekürzt') ? ' class="summary-note"' : '';
        return `<p${{className}}>${{escapeHtml(part)}}</p>`;
      }}).join('');
    }}

    function clippedSummaryDisplayText(record, kind, limit = 2200) {{
      const text = summaryDisplayText(record, kind);
      if (text.length <= limit) return text;
      return `${{text.slice(0, limit).trimEnd()}}\n\n[Gekürzt für flüssige Anzeige.]`;
    }}

    function splitSummaryParagraphs(value) {{
      const raw = String(value || '').replace(/\\s+/g, ' ').trim();
      if (!raw) return [];
      const sentences = raw.split(/(?<=[.!?])\\s+(?=[A-ZÄÖÜ„"'])/).filter(Boolean);
      if (sentences.length <= 2) return [raw];
      const paragraphs = [];
      for (let index = 0; index < sentences.length; index += 2) {{
        paragraphs.push(sentences.slice(index, index + 2).join(' '));
      }}
      return paragraphs;
    }}

    function summaryDisplayText(record, kind) {{
      return summaryBaseText(record, kind);
    }}

    function summaryBaseText(record, kind) {{
      return record?.ki_zusammenfassung || '';
    }}

    function summaryPointsText(record) {{
      void record;
      return '';
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

    function exportJson() {{
      downloadText('graz-gemeinderat-treffer.json', JSON.stringify({{
        generated_at: new Date().toISOString(),
        records: sichtbareEintraege
      }}, null, 2), 'application/json;charset=utf-8');
    }}

    function publicRoadworkFeed() {{
      const generatedAt = new Date().toISOString();
      const items = [
        ...officialRoadworks.map((roadwork) => ({{
          id: `official-${{roadwork.title || roadwork.location || ''}}-${{roadwork.period || ''}}`,
          title: roadwork.title || roadwork.location || '',
          location: roadwork.location || roadwork.title || '',
          kind: 'offizielle Baustelleninfo',
          period: roadwork.period || '',
          start_date: roadwork.start_date || '',
          end_date: roadwork.end_date || '',
          status: roadwork.time_status || 'unklar',
          impact: '',
          description: roadwork.description || '',
          source: roadwork.source || 'Stadt Graz',
          source_url: roadwork.source_url || (mobilitySources.roadworks || {{}}).office_url || '',
          license: roadwork.license || 'öffentliche Webseite, keine OGD-Lizenz gefunden',
          official_release: true,
          updated_at: generatedAt
        }}))
      ];
      return {{
        title: 'Graz Baustellen',
        generated_at: generatedAt,
        license_note: 'Offizielle Quellen prüfen; rohe Protokolle sind nicht enthalten.',
        sources: {{
          roadworks: mobilitySources.roadworks || {{}},
          parking: mobilitySources.parking || {{}}
        }},
        items
      }};
    }}

    function exportPublicJsonFeed() {{
      downloadText('graz-baustellen-feed.json', JSON.stringify(publicRoadworkFeed(), null, 2), 'application/json;charset=utf-8');
    }}

    function exportRoadworkCsv() {{
      const feed = publicRoadworkFeed();
      const headers = ['ID', 'Titel', 'Ort', 'Art', 'Zeitraum', 'Start', 'Ende', 'Status', 'Auswirkung', 'Beschreibung', 'Quelle', 'Link', 'Freigabe'];
      const rows = feed.items.map((item) => [
        item.id,
        item.title,
        item.location,
        item.kind,
        item.period,
        item.start_date,
        item.end_date,
        item.status,
        item.impact,
        item.description,
        item.source,
        item.source_url,
        item.official_release ? 'amtlich/öffentlich importiert' : 'lokal freigegeben'
      ]);
      const csv = [headers, ...rows].map((row) => row.map(csvCell).join(';')).join('\\r\\n');
      downloadText('graz-baustellen-feed.csv', `\\ufeff${{csv}}`, 'text/csv;charset=utf-8');
    }}

    function exportIcs() {{
      const lines = [
        'BEGIN:VCALENDAR',
        'VERSION:2.0',
        'PRODID:-//Graz Baustellen//Baustellen//DE'
      ];
      publicRoadworkFeed().items.forEach((item) => {{
        const start = String(item.start_date || '').replaceAll('-', '');
        const end = String(item.end_date || item.start_date || '').replaceAll('-', '');
        if (!start) return;
        lines.push('BEGIN:VEVENT');
        lines.push(`UID:${{item.id}}@graz-baustellen.local`);
        lines.push(`DTSTAMP:${{new Date().toISOString().replace(/[-:]/g, '').replace(/\\.\\d{{3}}Z$/, 'Z')}}`);
        lines.push(`DTSTART;VALUE=DATE:${{start}}`);
        if (end) lines.push(`DTEND;VALUE=DATE:${{end}}`);
        lines.push(`SUMMARY:${{icsText(item.title || item.location)}}`);
        lines.push(`DESCRIPTION:${{icsText([item.kind, item.period, item.description, item.source_url].filter(Boolean).join(' | '))}}`);
        lines.push('END:VEVENT');
      }});
      lines.push('END:VCALENDAR');
      downloadText('graz-baustellen.ics', lines.join('\\r\\n'), 'text/calendar;charset=utf-8');
    }}

    function exportRssFeed() {{
      const feed = publicRoadworkFeed();
      const items = feed.items.map((item) => `
        <item>
          <guid isPermaLink="false">${{rssXml(item.id)}}</guid>
          <title>${{rssXml(item.title || item.location)}}</title>
          <description>${{rssXml([item.kind, item.period, item.description, item.source_url].filter(Boolean).join(' | '))}}</description>
          <link>${{rssXml(item.source_url || '')}}</link>
          <pubDate>${{new Date(item.updated_at || feed.generated_at).toUTCString()}}</pubDate>
        </item>
      `).join('');
      const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>${{rssXml(feed.title)}}</title>
    <description>${{rssXml(feed.license_note)}}</description>
    <lastBuildDate>${{new Date(feed.generated_at).toUTCString()}}</lastBuildDate>
    <link>https://www.graz.at/</link>
    ${{items}}
  </channel>
</rss>`;
      downloadText('graz-baustellen-feed.rss', xml, 'application/rss+xml;charset=utf-8');
    }}

    function rssXml(value) {{
      return String(value || '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&apos;');
    }}

    function icsText(value) {{
      const backslash = String.fromCharCode(92);
      return String(value || '')
        .split(backslash).join(backslash + backslash)
        .replace(/;/g, backslash + ';')
        .replace(/,/g, backslash + ',')
        .replace(/\\r?\\n/g, backslash + 'n');
    }}

    function roadworkSubscriptions() {{
      return readLocalJson(subscriptionKey, []);
    }}

    function roadworkFeedback() {{
      return readLocalJson(feedbackKey, []);
    }}

    function saveRoadworkSubscription() {{
      const subscription = {{
        id: `subscription-${{Date.now()}}`,
        street: subscriptionStreet.value.trim(),
        district: subscriptionDistrict.value.trim(),
        start_date: subscriptionStart.value,
        end_date: subscriptionEnd.value,
        created_at: new Date().toISOString()
      }};
      if (!subscription.street && !subscription.district && !subscription.start_date && !subscription.end_date) {{
        subscriptionStatus.textContent = 'Bitte Straße, Bezirk oder Zeitraum für das Abo angeben.';
        return;
      }}
      writeLocalJson(subscriptionKey, [subscription, ...roadworkSubscriptions()]);
      subscriptionStreet.value = '';
      subscriptionDistrict.value = '';
      subscriptionStart.value = '';
      subscriptionEnd.value = '';
      renderSubscriptions();
    }}

    function saveRoadworkFeedback() {{
      const text = feedbackText.value.trim();
      if (!text) {{
        subscriptionStatus.textContent = 'Bitte einen Feedback-Hinweis eingeben.';
        return;
      }}
      const entry = {{
        id: `feedback-${{Date.now()}}`,
        text,
        created_at: new Date().toISOString(),
        publish_personal_data: false
      }};
      writeLocalJson(feedbackKey, [entry, ...roadworkFeedback()]);
      feedbackText.value = '';
      renderSubscriptions();
    }}

    function exportRoadworkSubscriptions() {{
      downloadText('graz-baustellen-abos.json', JSON.stringify({{
        generated_at: new Date().toISOString(),
        subscriptions: roadworkSubscriptions(),
        matching_items: matchingSubscribedRoadworks()
      }}, null, 2), 'application/json;charset=utf-8');
    }}

    function exportRoadworkFeedback() {{
      downloadText('graz-baustellen-feedback.json', JSON.stringify({{
        generated_at: new Date().toISOString(),
        privacy_note: 'Lokaler Feedbackexport; keine personenbezogene Veröffentlichung.',
        feedback: roadworkFeedback()
      }}, null, 2), 'application/json;charset=utf-8');
    }}

    function matchingSubscribedRoadworks() {{
      const subscriptions = roadworkSubscriptions();
      if (!subscriptions.length) return [];
      return publicRoadworkFeed().items.filter((item) =>
        subscriptions.some((subscription) => subscriptionMatchesRoadwork(subscription, item))
      );
    }}

    function subscriptionMatchesRoadwork(subscription, item) {{
      const haystack = [item.title, item.location, item.description].join(' ').toLocaleLowerCase('de-AT');
      if (subscription.street && !haystack.includes(subscription.street.toLocaleLowerCase('de-AT'))) return false;
      if (subscription.district && !haystack.includes(subscription.district.toLocaleLowerCase('de-AT'))) return false;
      if (subscription.start_date && item.end_date && item.end_date < subscription.start_date) return false;
      if (subscription.end_date && item.start_date && item.start_date > subscription.end_date) return false;
      return true;
    }}

    function renderSubscriptions() {{
      const subscriptions = roadworkSubscriptions();
      const feedback = roadworkFeedback();
      const matches = matchingSubscribedRoadworks();
      subscriptionStatus.textContent = `${{subscriptions.length}} lokale Abos, ${{feedback.length}} Feedbackeinträge, ${{matches.length}} passende öffentliche Einträge.`;
      const subscriptionItems = subscriptions.slice(0, 12).map((subscription) => `
        <div class="local-item">
          <strong>${{escapeHtml([subscription.street, subscription.district].filter(Boolean).join(' / ') || 'Zeitraum-Abo')}}</strong>
          <small>${{escapeHtml([subscription.start_date, subscription.end_date].filter(Boolean).join(' bis ') || 'ohne Zeitraum')}}</small>
        </div>
      `).join('');
      const feedbackItems = feedback.slice(0, 6).map((entry) => `
        <div class="local-item">
          <strong>Feedback ${{escapeHtml(formatDateTime(entry.created_at))}}</strong>
          <small>${{escapeHtml(entry.text)}}</small>
        </div>
      `).join('');
      subscriptionList.innerHTML = subscriptionItems || feedbackItems
        ? `${{subscriptionItems}}${{feedbackItems}}`
        : '<div class="empty">Noch keine lokalen Abos oder Feedbackeinträge.</div>';
    }}

    function formatDateTime(value) {{
      if (!value) return '';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return String(value);
      return date.toLocaleString('de-AT', {{ dateStyle: 'short', timeStyle: 'short' }});
    }}

    function renderDetail(record) {{
      if (!record) {{
        detailWrap.innerHTML = '';
        return;
      }}
      const submitterLabel = record.typ === 'Fragestunde'
        ? 'Fragestellerin'
        : (record.typ === 'Mitteilung' ? 'Bearbeiter/in' : 'Einbringer');
      detailWrap.innerHTML = `
        <h2>${{escapeHtml(record.titel || 'Eintrag')}}</h2>
        <div class="detail-grid">
          ${{detailField('Datum', record.datum)}}
          ${{detailField('Typ', record.typ)}}
          ${{detailField('Thema', record.kategorie)}}
          ${{detailField(submitterLabel, record.einbringer)}}
          ${{detailField('Adressat', record.adressat)}}
          ${{detailField('Stück', record.stueck_nr)}}
          ${{detailField('Status', record.status)}}
          ${{detailField('Geschäftszahlen', joinList(record.geschaeftszahlen))}}
          ${{detailField('Ergebnisquelle', record.ergebnisquelle)}}
          ${{detailField('Ergebnis', record.ergebnis)}}
          ${{detailField('DIGRA-Einlagezahl', record.digra_einlagezahl)}}
          ${{detailField('DIGRA-Trefferwert', record.digra_trefferwert)}}
          ${{detailLinkField('DIGRA-Link', record.digra_url)}}
          ${{detailHtmlField('Stadt-Graz-Link', externalLink(record.source_url, 'Quelle öffnen'))}}
          ${{detailHtmlField('PDF-Seite', pdfPageField(record))}}
          ${{detailField('Beträge', joinList(record.betraege))}}
          ${{detailHtmlField('Orte', locationLinks(record.orte))}}
          ${{detailField('Quelldatei', record.quell_datei)}}
        </div>
        ${{summaryBlocks(record)}}
        ${{civicFeedbackDetailCta(record)}}
      `;
    }}

    function renderDateSummary() {{
      if (!dateSummaryWrap) return;
      const dayRecords = sichtbareEintraege;
      const statusCounts = countBy(dayRecords, (record) => record.status_filter || record.status || 'Unbekannt');
      const typeCounts = countBy(dayRecords, (record) => record.typ || 'Unbekannt');
      const themeCounts = countBy(dayRecords, (record) => record.kategorie || 'Sonstiges');
      const accepted = (statusCounts.get('Angenommen') || 0);
      const rejected = (statusCounts.get('Abgelehnt') || 0);
      const assigned = [...statusCounts.entries()].filter(([label]) => /zugewiesen/i.test(label)).reduce((sum, [, count]) => sum + count, 0);
      const noted = [...statusCounts.entries()].filter(([label]) => /kenntnis|quelle verfügbar/i.test(label)).reduce((sum, [, count]) => sum + count, 0);
      const sourceSummary = countBy(dayRecords, (record) => record.ergebnisquelle || 'Protokoll');
      const topThemeItems = topCountLabels(themeCounts, 5);
      const topTypeItems = topCountLabels(typeCounts, 4);
      const topThemes = topThemeItems.join(', ') || '-';
      const topTypes = topTypeItems.join(', ') || '-';
      const sourceText = topCountLabels(sourceSummary, 4).join(', ') || '-';
      const dateSummaryHtml = sessionSummaryHtml(dayRecords, {{
        accepted,
        rejected,
        assigned,
        noted,
        topThemes,
        topTypes,
        topThemeItems,
        topTypeItems,
        sourceText,
      }});
      dateSummaryWrap.hidden = false;
      const summaryTitle = dateFilter.value
        ? `Gesamtzusammenfassung für ${{escapeHtml(dateFilter.value)}}`
        : `Gesamtzusammenfassung für die aktuelle Auswahl${{yearFilter.value ? ` (${{escapeHtml(yearFilter.value)}})` : ''}}`;
      dateSummaryWrap.innerHTML = `
        <h2>${{summaryTitle}}</h2>
        <div class="detail-grid">
          ${{detailField('Sichtbare Einträge', dayRecords.length)}}
          ${{detailField('Angenommen', accepted)}}
          ${{detailField('Abgelehnt', rejected)}}
          ${{detailField('Zugewiesen', assigned)}}
          ${{detailField('Zur Kenntnis/Quelle', noted)}}
          ${{detailField('Typen', topTypes)}}
          ${{detailField('Themen', topThemes)}}
          ${{detailField('Quellen', sourceText)}}
        </div>
        <div class="summary-blocks">
          <div class="summary-block">
            <button class="summary-toggle" type="button" data-date-summary aria-expanded="true">
              <span class="summary-toggle-label">Gesamtzusammenfassung</span>
              <span class="summary-toggle-sub">Ergebnisse, Schwerpunkte und offene Punkte dieser Auswahl.</span>
            </button>
            <div class="summary-text">${{dateSummaryHtml}}</div>
          </div>
        </div>
      `;
    }}

    function sessionSummaryHtml(dayRecords, stats) {{
      if (!dayRecords.length) return '<p>Für diese Auswahl wurden keine Einträge gefunden.</p>';
      const acceptedExamples = sessionExampleItems(dayRecords, (record) => /angenommen|beschlossen/i.test(`${{record.status_filter || ''}} ${{record.ergebnis || ''}}`), 4);
      const openExamples = sessionExampleItems(dayRecords, (record) => /zugewiesen|offen|unklar/i.test(`${{record.status_filter || ''}} ${{record.status || ''}} ${{record.ergebnis || ''}}`), 4);
      const rejectedExamples = sessionExampleItems(dayRecords, (record) => /abgelehnt/i.test(`${{record.status_filter || ''}} ${{record.ergebnis || ''}}`), 3);
      const themeItems = sessionSummaryFilterItems(stats.topThemeItems || sessionSummaryList(stats.topThemes), 'category');
      const typeItems = sessionSummaryFilterItems(stats.topTypeItems || sessionSummaryList(stats.topTypes), 'type');
      const outcomeItems = [
        `${{stats.accepted}} angenommene bzw. beschlossene Punkte`,
        `${{stats.noted}} zur Kenntnis genommene Punkte oder verfügbare Quellen`,
        `${{stats.assigned}} zugewiesene bzw. offene Verfahren`,
        `${{stats.rejected}} abgelehnte Punkte`,
      ];
      const sourceText = stats.sourceText && stats.sourceText !== '-' ? `Die Ergebnisquellen verteilen sich auf ${{stats.sourceText}}.` : '';
      const parts = [
        `<p>Für diese Sitzung sind ${{escapeHtml(dayRecords.length)}} sichtbare Einträge erfasst. Der Überblick fasst die Ergebnislage dieser gefilterten Sitzung zusammen; die vollständige Liste steht darunter in der Tabelle.</p>`,
        `<p><strong>Schwerpunkte</strong></p>${{summaryListHtml(themeItems)}}`,
        `<p><strong>Formate</strong></p>${{summaryListHtml(typeItems)}}`,
        `<p><strong>Ergebnislage</strong></p>${{summaryListHtml(outcomeItems)}}`,
      ];
      if (acceptedExamples.length) parts.push(`<p><strong>Beispiele für positive Ergebnisse</strong></p>${{summaryListHtml(acceptedExamples)}}`);
      if (openExamples.length) parts.push(`<p><strong>Offene oder zugewiesene Punkte</strong></p>${{summaryListHtml(openExamples)}}`);
      if (rejectedExamples.length) parts.push(`<p><strong>Abgelehnte oder nicht beschlossene Punkte</strong></p>${{summaryListHtml(rejectedExamples)}}`);
      if (sourceText) parts.push(`<p>${{escapeHtml(sourceText)}}</p>`);
      return parts.join('');
    }}

    function sessionExampleItems(records, predicate, limit) {{
      return records
        .filter(predicate)
        .slice(0, limit)
        .map((record) => ({{
          label: compactText(record.titel || record.typ || 'Eintrag', 140),
          kind: 'record',
          value: record.record_id,
        }}))
        .filter((item) => item.label && item.value);
    }}

    function sessionSummaryList(value) {{
      if (!value || value === '-') return [];
      return String(value).split(',').map((item) => item.trim()).filter(Boolean);
    }}

    function summaryListHtml(items) {{
      if (!items.length) return '<p>-</p>';
      return `<ul class="summary-list">${{items.map((item) => summaryListItemHtml(item)).join('')}}</ul>`;
    }}

    function summaryListItemHtml(item) {{
      if (typeof item === 'string') return `<li>${{escapeHtml(item)}}</li>`;
      const label = item.label || item.value || '';
      if (!item.kind || !item.value) return `<li>${{escapeHtml(label)}}</li>`;
      return `<li><button class="summary-filter-link" type="button" data-summary-filter="${{escapeHtml(item.kind)}}" data-summary-value="${{escapeHtml(item.value)}}">${{escapeHtml(label)}}</button></li>`;
    }}

    function sessionSummaryFilterItems(items, kind) {{
      return (items || []).map((item) => {{
        const text = String(item || '').trim();
        const value = text.replace(/\\s*\\(\\d+\\)\\s*$/, '');
        return {{ label: text, kind, value }};
      }}).filter((item) => item.value);
    }}

    function countBy(values, selector) {{
      const counts = new Map();
      values.forEach((value) => {{
        const label = selector(value);
        counts.set(label, (counts.get(label) || 0) + 1);
      }});
      return counts;
    }}

    function topCountLabels(counts, limit) {{
      return [...counts.entries()]
        .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0], 'de-AT'))
        .slice(0, limit)
        .map(([label, count]) => `${{label}} (${{count}})`);
    }}

    function scrollToRecordDetail() {{
      requestAnimationFrame(() => {{
        detailWrap.scrollIntoView({{ behavior: 'auto', block: 'start' }});
      }});
    }}

    function applySummaryFilter(kind, value) {{
      if (!value) return;
      if (kind === 'category') {{
        categoryFilter.value = value;
      }} else if (kind === 'type') {{
        typeFilter.value = value;
      }} else if (kind === 'record') {{
        const record = findRecordById(value);
        if (record) {{
          selectRecord(record);
          activateSearchSubtab('details', false);
          scrollToRecordDetail();
          return;
        }}
      }}
      activeTopicRecordIds = null;
      activeTopicLabel = '';
      render();
      activateSearchSubtab('table', false);
      requestAnimationFrame(() => window.scrollTo({{ top: searchSubtabScroll.table || 0, behavior: 'auto' }}));
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

    function updateArchiveNotice() {{
      if (!archiveNotice) return;
      const hasArchiveRecords = sichtbareEintraege.some((record) => isArchiveRecord(record));
      archiveNotice.classList.toggle('is-active', hasArchiveRecords);
    }}

    function isArchiveRecord(record) {{
      const source = String(record.ergebnisquelle || '').toLocaleLowerCase('de-AT');
      const type = String(record.typ || '').toLocaleLowerCase('de-AT');
      const date = String(record.datum || '');
      return source.includes('archiv') || type.includes('archiv') || (!record.digra_url && date && date < '2025-02-01');
    }}

    function render() {{
      sichtbareEintraege = sortRecordsForTable(filteredRecords());
      if (ausgewaehlterEintrag && !sichtbareEintraege.includes(ausgewaehlterEintrag)) {{
        ausgewaehlterEintrag = null;
      }}
      setOptionalText('visibleCount', sichtbareEintraege.length);
      setOptionalText('totalCount', records.length);
      setOptionalText('fileCount', summary.dateien_mit_eintraegen ?? new Set(records.map((r) => r.quell_datei)).size);
      setOptionalText('digraCount', summary.digra_ergebnisse ?? records.filter((r) => r.ergebnisquelle === 'DIGRA').length);
      if (digraMatchedCount) digraMatchedCount.textContent = summary.digra_treffer ?? records.filter((r) => r.digra_url).length;
      if (digraFallbackCount) digraFallbackCount.textContent = summary.digra_protokoll_fallbacks ?? records.filter((r) => r.ergebnisquelle === 'Protokoll').length;
      if (cityLinkCount) cityLinkCount.textContent = summary.stadt_graz_links ?? records.filter((r) => r.source_url).length;
      if (digraMissingCount) digraMissingCount.textContent = records.filter((r) => !r.ergebnis || r.status_filter === 'Unbekannt').length;
      currentLocationIndex = buildLocationIndex(sichtbareEintraege);
      updateTopicFilterNotice();
      updateArchiveNotice();
      renderMapPlaces();
      renderMapLegend();
      refreshMapMarkersIfNeeded();
      renderDateSummary();
      renderDetail(ausgewaehlterEintrag);

      if (!sichtbareEintraege.length) {{
        tableWrap.innerHTML = '<div class="empty">Keine Treffer für diese Filter.</div>';
        return;
      }}

      const tableRecords = sichtbareEintraege.slice(0, tableRenderLimit);
      const overflowCount = Math.max(0, sichtbareEintraege.length - tableRecords.length);
      const rows = tableRecords.map((record, index) => `
        <tr data-index="${{index}}" class="${{ausgewaehlterEintrag && record.record_id === ausgewaehlterEintrag.record_id ? 'selected-record' : ''}}">
          <td data-label="Statuspunkt" class="status-dot-col"><span class="status-dot ${{statusDotClass(record)}}" title="${{escapeHtml(statusDotLabel(record))}}"></span></td>
          <td data-label="Datum" class="date-col">${{escapeHtml(record.datum)}}</td>
          <td data-label="Typ" class="type-col"><span class="badge">${{escapeHtml(record.typ || '')}}</span></td>
          <td data-label="Stk." class="item-col">${{escapeHtml(record.stueck_nr)}}</td>
          <td data-label="Status" class="status-col">${{tableStatusHtml(record)}}</td>
          <td data-label="Geschäftszahl" class="business-col">${{escapeHtml((record.geschaeftszahlen || []).join(', '))}}</td>
          <td data-label="Titel" class="title">${{escapeHtml(record.titel)}}<br><span class="badge">${{escapeHtml(record.kategorie || '')}}</span></td>
          <td data-label="Beträge" class="amount amount-col">${{escapeHtml((record.betraege || []).join(', '))}}</td>
          <td data-label="Orte" class="places-col">${{locationLinks(record.orte)}}</td>
          <td data-label="Einbringer" class="mobile-card-only">${{escapeHtml(record.einbringer || '-')}}</td>
          <td data-label="Zusammenfassung" class="mobile-card-only">${{tableMobileSummaryHtml(record)}}</td>
          <td data-label="Ergebnis" class="mobile-card-only">${{tableResultHtml(record)}}</td>
          <td data-label="Quelle" class="mobile-card-only">${{tableMobileSourceHtml(record)}}</td>
        </tr>
      `).join('');

      tableWrap.innerHTML = `
        ${{overflowCount ? `<div class="table-note">${{escapeHtml(tableRecords.length)}} von ${{escapeHtml(sichtbareEintraege.length)}} Treffern werden angezeigt. Nutze Suche oder Filter, um die Liste weiter einzugrenzen.</div>` : ''}}
        <div class="table-card">
        <table>
          <thead>
            <tr>
              <th></th>
              <th>Datum</th>
              <th>Typ</th>
              <th>Stk.</th>
              <th>Status</th>
              <th>Geschäftszahl</th>
              <th>Titel</th>
              <th>Beträge</th>
              <th>Orte</th>
            </tr>
          </thead>
          <tbody>${{rows}}</tbody>
        </table>
        </div>
      `;
      highlightSelectedTableRow();
    }}

    function setOptionalText(id, value) {{
      const element = byId(id);
      if (element) element.textContent = value;
    }}

    fillYearSelect(yearFilter, records.map((record) => String(record.datum || '').slice(0, 4)));
    fillDateSelect(dateFilter, records.map((record) => record.datum));
    fillTypeSelect();
    fillSelect(statusFilter, records.map((record) => record.status_filter));
    fillSelect(categoryFilter, records.map((record) => record.kategorie));
    fillSourceSelect();
    yearFilter.value = defaultYearValue();
    dateFilter.value = '';
    fillDatalist('locationSuggestions', records.flatMap((record) => record.orte || []));
    const globalSuggestionValues = records.flatMap((record) => [
      record.titel,
      record.einbringer,
      record.kategorie,
      ...(record.orte || []),
      ...(record.geschaeftszahlen || []),
      ...(record.betraege || []),
    ]).concat(civicServices.flatMap((service) => [
      service.name,
      service.category,
      service.address,
      ...(service.services || []),
    ]));
    questionSuggestionValues = uniqueSuggestionValues(globalSuggestionValues, 900);
    fillDatalist('globalSuggestions', globalSuggestionValues);
    search.addEventListener('input', () => {{
      activeTopicRecordIds = null;
      activeTopicLabel = '';
      render();
    }});
    aiAsk.addEventListener('click', askLocalAi);
    aiQuestion.addEventListener('input', renderQuestionSuggestions);
    aiQuestion.addEventListener('focus', renderQuestionSuggestions);
    aiQuestion.addEventListener('blur', () => window.setTimeout(hideQuestionSuggestions, 120));
    aiQuestionSuggestions?.addEventListener('mousedown', (event) => {{
      event.preventDefault();
    }});
    aiQuestionSuggestions?.addEventListener('click', (event) => {{
      const suggestion = event.target.closest('[data-question-suggestion]');
      if (!suggestion) return;
      aiQuestion.value = suggestion.dataset.questionSuggestion || '';
      hideQuestionSuggestions();
      aiQuestion.focus();
    }});
    aiResultTabs?.addEventListener('click', (event) => {{
      const tab = event.target.closest('[data-question-result-tab]');
      if (!tab) return;
      activateQuestionResultTab(tab.dataset.questionResultTab || 'answer');
    }});
    aiQuestion.addEventListener('keydown', (event) => {{
      if (event.key !== 'Enter') return;
      event.preventDefault();
      hideQuestionSuggestions();
      askLocalAi();
    }});
    yearFilter.addEventListener('input', () => {{
      if (yearFilter.value && dateFilter.value && !dateFilter.value.startsWith(yearFilter.value + '-')) {{
        dateFilter.value = '';
      }}
      render();
    }});
    dateFilter.addEventListener('input', () => {{
      if (dateFilter.value && yearFilter.value && !dateFilter.value.startsWith(yearFilter.value + '-')) {{
        yearFilter.value = '';
      }}
      render();
    }});
    [typeFilter, statusFilter, categoryFilter, sourceFilter, amountFilter].forEach((el) => el.addEventListener('input', render));
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
      activateSearchSubtab('details', false);
      scrollToRecordDetail();
    }});
    detailWrap.addEventListener('click', (event) => {{
      const civicButton = event.target.closest('[data-open-civic-feedback]');
      if (civicButton) {{
        event.preventDefault();
        openParticipationForRecord(civicButton.dataset.openCivicFeedback || '');
        return;
      }}
      const summaryToggle = event.target.closest('[data-summary-kind]');
      if (summaryToggle) {{
        event.stopPropagation();
        const text = summaryToggle.nextElementSibling;
        if (!text) return;
        const isOpening = text.hidden;
        text.hidden = !isOpening;
        summaryToggle.setAttribute('aria-expanded', String(isOpening));
        return;
      }}
      const locationButton = event.target.closest('[data-location]');
      if (!locationButton) return;
      focusLocation(locationButton.dataset.location || '');
    }});
    participationList.addEventListener('click', (event) => {{
      const item = event.target.closest('[data-participation-record-id]');
      if (!item) return;
      selectedParticipationRecordId = item.dataset.participationRecordId || '';
      renderParticipationPage(selectedParticipationRecordId);
    }});
    participationDetail.addEventListener('click', (event) => {{
      const stanceButton = event.target.closest('[data-civic-stance]');
      if (stanceButton) {{
        participationDetail.querySelectorAll('[data-civic-stance]').forEach((item) => {{
          item.classList.toggle('active', item === stanceButton);
        }});
        return;
      }}
      if (event.target.closest('#participationSave')) {{
        saveCurrentParticipationFeedback();
      }}
    }});
    civicFeedbackOpen.addEventListener('click', () => openParticipationForRecord());
    civicFeedbackLater.addEventListener('click', () => closeCivicFeedbackModal(true));
    civicFeedbackModal.addEventListener('click', (event) => {{
      if (event.target === civicFeedbackModal) closeCivicFeedbackModal(true);
    }});
    dateSummaryWrap.addEventListener('click', (event) => {{
      const filterButton = event.target.closest('[data-summary-filter]');
      if (filterButton) {{
        event.preventDefault();
        applySummaryFilter(filterButton.dataset.summaryFilter || '', filterButton.dataset.summaryValue || '');
        return;
      }}
      const summaryToggle = event.target.closest('[data-date-summary]');
      if (!summaryToggle) return;
      const text = summaryToggle.nextElementSibling;
      if (!text) return;
      const isOpening = text.hidden;
      text.hidden = !isOpening;
      summaryToggle.setAttribute('aria-expanded', String(isOpening));
    }});
    document.querySelectorAll('[data-search-subtab]').forEach((item) => {{
      item.addEventListener('click', () => activateSearchSubtab(item.dataset.searchSubtab || 'table'));
    }});
    mapPlaces.addEventListener('click', (event) => {{
      const locationButton = event.target.closest('[data-location]');
      if (!locationButton) return;
      focusLocation(locationButton.dataset.location || '');
    }});
    parkingList.addEventListener('click', (event) => {{
      if (event.target.closest('[data-parking-link]')) return;
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
    pharmacyList.addEventListener('click', (event) => {{
      const item = event.target.closest('[data-health-index]');
      if (!item) return;
      const pharmacy = currentPharmacyPlaces[Number(item.dataset.healthIndex)];
      if (!pharmacy || !pharmacyMap) return;
      pharmacyMap.setView([pharmacy.lat, pharmacy.lon], 16);
      highlightHealthList(pharmacyList, item.dataset.healthIndex);
    }});
    doctorsProfessionFilter.addEventListener('input', renderDoctorsMap);
    doctorsList.addEventListener('click', (event) => {{
      const item = event.target.closest('[data-health-index]');
      if (!item) return;
      const doctor = currentDoctorPlaces[Number(item.dataset.healthIndex)];
      if (!doctor || !doctorsMap) return;
      doctorsMap.setView([doctor.lat, doctor.lon], 16);
      highlightHealthList(doctorsList, item.dataset.healthIndex);
    }});
    servicesSearch.addEventListener('input', renderCivicServices);
    servicesCategoryFilter.addEventListener('input', renderCivicServices);
    servicesList.addEventListener('click', (event) => {{
      const item = event.target.closest('[data-service-index]');
      if (!item) return;
      const service = civicServices[Number(item.dataset.serviceIndex)];
      if (!service || !servicesMap) return;
      servicesMap.setView([service.lat, service.lon], 16);
      highlightServiceList(item.dataset.serviceIndex);
    }});
    roadworksLegend.addEventListener('click', (event) => {{
      const statusButton = event.target.closest('[data-roadwork-status]');
      if (!statusButton) return;
      const status = statusButton.dataset.roadworkStatus || '';
      activeRoadworkStatus = activeRoadworkStatus === status ? '' : status;
      renderRoadworkContext();
    }});
    roadworksList.addEventListener('click', (event) => {{
      const item = event.target.closest('[data-roadwork-index]');
      if (!item) return;
      const roadwork = currentRoadworks[Number(item.dataset.roadworkIndex)];
      if (!roadwork || !roadworksMap) return;
      Promise.resolve(roadwork.coords || roadworkCoords(roadwork.location || roadwork.title)).then((coords) => {{
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
    function openSourceRecordDetails(event) {{
      const sourceButton = event.target.closest('[data-source-record-id]');
      if (!sourceButton) return false;
      const record = findRecordById(sourceButton.dataset.sourceRecordId);
      if (!record) return false;
      selectRecord(record);
      activateSearchSubtab('details', false);
      detailWrap.scrollIntoView({{ behavior: 'auto', block: 'start' }});
      return true;
    }}
    aiSources.addEventListener('click', openSourceRecordDetails);
    aiAnswer.addEventListener('click', openSourceRecordDetails);
    if (exportCsvButton) exportCsvButton.addEventListener('click', exportCsv);
    if (exportJsonButton) exportJsonButton.addEventListener('click', exportJson);
    if (exportRoadworksJsonButton) exportRoadworksJsonButton.addEventListener('click', exportPublicJsonFeed);
    if (exportRoadworksCsvButton) exportRoadworksCsvButton.addEventListener('click', exportRoadworkCsv);
    if (exportRoadworksIcsButton) exportRoadworksIcsButton.addEventListener('click', exportIcs);
    if (exportRoadworksRssButton) exportRoadworksRssButton.addEventListener('click', exportRssFeed);
    if (saveSubscriptionButton) saveSubscriptionButton.addEventListener('click', saveRoadworkSubscription);
    if (saveFeedbackButton) saveFeedbackButton.addEventListener('click', saveRoadworkFeedback);
    if (exportSubscriptionsButton) exportSubscriptionsButton.addEventListener('click', exportRoadworkSubscriptions);
    if (exportFeedbackButton) exportFeedbackButton.addEventListener('click', exportRoadworkFeedback);
    if (mobileNavToggle) {{
      mobileNavToggle.addEventListener('click', () => {{
        const isOpen = mobileNavToggle.getAttribute('aria-expanded') === 'true';
        setMobileNavOpen(!isOpen);
      }});
    }}
    document.addEventListener('keydown', (event) => {{
      if (event.key === 'Escape') {{
        setMobileNavOpen(false);
        closeCivicFeedbackModal(true);
      }}
    }});
    document.addEventListener('click', (event) => {{
      if (!sidebar || !sidebar.classList.contains('nav-open')) return;
      if (sidebar.contains(event.target)) return;
      setMobileNavOpen(false);
    }});
    document.querySelectorAll('[data-nav]').forEach((item) => {{
      item.addEventListener('click', () => {{
        const target = item.dataset.nav;
        activateTab(target);
      }});
    }});
    initMap();
    render();
    renderParticipationPage();
    maybeShowCivicFeedbackModal();
  </script>
</body>
</html>
"""


def viewer_record(record: dict) -> dict:
    category = classify_category(record)
    status = normalized_viewer_status(record)
    result_text = normalized_viewer_result_text(record, status)
    locations = inferred_viewer_locations(record, result_text)
    record_type = viewer_record_type(record)
    digra_url = canonical_digra_url(str(record.get("digra_url", "")))
    question_people = question_people_from_title(str(record.get("title", "") or ""))
    submitter = str(record.get("submitter", "") or "").strip()
    if record_type == "question_hour" and not submitter:
        submitter = question_people[0]
    return {
        "record_id": record.get("record_id", ""),
        "datum": record.get("meeting_date", ""),
        "typ": german_record_type(record_type),
        "abschnitt": record.get("section", ""),
        "stueck_nr": record.get("agenda_item_no", ""),
        "geschaeftszahlen": record.get("business_numbers", []),
        "titel": viewer_display_title(record),
        "status": german_status(status),
        "status_filter": german_status_filter(status),
        "kategorie": category,
        "einbringer": submitter,
        "adressat": question_recipient(record) or (question_people[1] if record_type == "question_hour" else ""),
        "ergebnis": result_text,
        "ergebnisquelle": german_result_source(str(record.get("result_source", "")), digra_url),
        "digra_url": digra_url,
        "digra_einlagezahl": record.get("digra_business_number", ""),
        "digra_trefferwert": format_score(record.get("digra_match_score", 0)),
        "source_url": record.get("source_url", ""),
        "source_page": record.get("source_page", 0),
        "local_source_url": record.get("local_source_url", ""),
        "betraege": record.get("amounts", []),
        "orte": locations,
        "abstimmungen": viewer_votes(record.get("votes", [])),
        "ki_zusammenfassung": viewer_ai_summary(record, result_text),
        "ki_warum_interessant": clean_viewer_text(record.get("ai_why_interesting", "")),
        "ki_kernpunkte": viewer_ai_key_points(record.get("ai_key_points", [])),
        "ki_offene_punkte": clean_viewer_text_list(record.get("ai_open_points", [])),
        "ki_quellenlimits": clean_viewer_text_list(record.get("ai_source_limits", [])),
        "quell_datei": german_source_file(str(record.get("source_file", ""))),
    }


def viewer_ai_summary(record: dict, result_text: str) -> str:
    value = str(record.get("ai_summary", "") or "").strip()
    if not value and viewer_record_type(record) in {"question_hour", "written_question"}:
        return fallback_question_summary(record, result_text)
    if not question_summary_is_bad(record, value):
        return normalize_summary_vote_consistency(value, record, result_text)
    return normalize_summary_vote_consistency(fallback_question_summary(record, result_text), record, result_text)


def normalize_summary_vote_consistency(value: str, record: dict | None = None, result_text: str = "") -> str:
    text = str(value or "")
    if not text:
        return ""
    if record is not None and summary_contradicts_record_result(text, record, result_text):
        return fallback_decision_summary(record, result_text)
    has_unanimous_accepted = re.search(r"\beinstimm\w*\s+angenommen\b", text, flags=re.IGNORECASE)
    has_against_votes = re.search(r"\b(?:gegen|dagegen|gegenstimmen?)\s*:", text, flags=re.IGNORECASE)
    if not (has_unanimous_accepted and has_against_votes):
        return text
    return re.sub(r"\beinstimm\w*\s+angenommen\b", "mehrheitlich angenommen", text, flags=re.IGNORECASE)


def summary_contradicts_record_result(value: str, record: dict, result_text: str) -> bool:
    text = re.sub(r"\s+", " ", value).strip().casefold()
    if not text or not summary_claims_decision_acceptance(text):
        return False
    status = normalized_viewer_status(record)
    result = re.sub(
        r"\s+",
        " ",
        " ".join(
            str(part or "")
            for part in (
                status,
                result_text,
                record.get("result_text", ""),
                record.get("raw_result_text", ""),
            )
        ),
    ).casefold()
    if status == "assigned" or re.search(r"\b(?:verfahren\s*:\s*)?zugewiesen\b", result):
        return True
    if status in {"rejected", "rejected_majority"}:
        return True
    return bool(
        re.search(r"\b(?:haupt)?antrag\s*:?\s*(?:mehrheitlich\s*)?abgelehnt\b", result)
        or re.search(r"\b(?:mehrheitlich\s+)?abgelehnt\b", result)
        or re.search(r"\bnicht\s+beschlossen\b", result)
    )


def summary_claims_decision_acceptance(value: str) -> bool:
    return bool(
        re.search(
            r"\b(?:angenommen|beschlossen|genehmigt|zugestimmt|akzeptiert)\b",
            value,
            flags=re.IGNORECASE,
        )
    )


def fallback_decision_summary(record: dict, result_text: str) -> str:
    record_type = german_record_type(viewer_record_type(record)).lower()
    title = viewer_display_title(record)
    if title and title not in {"Ohne Titel", "Frage in der Gemeinderatssitzung"}:
        subject = f"Der Punkt „{title}“"
    else:
        subject = f"Der Punkt {record_type}"
    status = normalized_viewer_status(record)
    if status == "assigned" or re.search(r"\bzugewiesen\b", result_text, flags=re.IGNORECASE):
        return f"{subject} ist als Verfahren zugewiesen; ein Beschluss ist in den lokalen Daten nicht erfasst."
    if status in {"rejected", "rejected_majority"} or re.search(r"\babgelehnt\b|\bnicht\s+beschlossen\b", result_text, flags=re.IGNORECASE):
        return f"{subject} wurde abgelehnt."
    cleaned_result = clean_viewer_text(result_text)
    if cleaned_result and cleaned_result != "Unbekannt":
        return f"Zum Punkt „{title or record_type}“ ist als Ergebnis erfasst: {cleaned_result}."
    return f"Zum Punkt „{title or record_type}“ ist keine belastbare KI-Zusammenfassung erfasst."


def viewer_ai_key_points(value: object) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return []
    points: list[dict[str, str]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        text = clean_viewer_text(item.get("text", ""))
        if not text:
            continue
        points.append(
            {
                "kind": clean_viewer_text(item.get("kind", "Kernpunkt")) or "Kernpunkt",
                "text": text,
                "simple": clean_viewer_text(item.get("simple", "")),
                "status": german_ai_point_status(str(item.get("status", ""))),
            }
        )
    return points


def clean_viewer_text_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for item in value if (text := clean_viewer_text(item))]


def clean_viewer_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def german_ai_point_status(value: str) -> str:
    return {
        "beschlossen": "beschlossen",
        "abgelehnt": "abgelehnt",
        "zugewiesen": "weitergegeben oder zugewiesen",
        "beantragt": "beantragt",
        "gefragt": "gefragt",
        "mitgeteilt": "mitgeteilt",
        "offen": "offen",
        "nicht_erfasst": "nicht erfasst",
    }.get(value, value.replace("_", " ") or "offen")


def question_summary_is_bad(record: dict, value: str) -> bool:
    if viewer_record_type(record) not in {"question_hour", "written_question"}:
        return False
    normalized = re.sub(r"\s+", " ", value).strip()
    if not normalized:
        return False
    return bool(
        re.search(r"\bFrage\s*:", normalized, flags=re.IGNORECASE)
        or re.search(
            r"\bWerter Herr|Herr Bürgermeister|sehr geehrt\w*|liebe Kolleg|meine Frage|in meiner Frage|folgende Frage",
            normalized,
            flags=re.IGNORECASE,
        )
        or re.search(r"originaltext der frage", normalized, flags=re.IGNORECASE)
        or re.search(r"betrifft\s+„[„\"']?(?:wie|was|warum|wieso|welche|mit welchen|in welcher|dürfen|duerfen|sind sie|haben sie|liegen|konnte)\b", normalized, flags=re.IGNORECASE)
        or re.search(r"Erfasste Antwort:\s*(?:Werter|Werte|Sehr geehrt|Liebe|Geschätzte|Geschaetzte)", normalized, flags=re.IGNORECASE)
        or "Das dokumentierte Ergebnis lautet: Unbekannt" in normalized
    )


def fallback_question_summary(record: dict, result_text: str) -> str:
    title = question_summary_title(record)
    type_label = "Fragestunde" if viewer_record_type(record) == "question_hour" else "schriftliche Anfrage"
    submitter = str(record.get("submitter", "") or "").strip()
    recipient = question_recipient(record)
    if submitter:
        parts: list[str] = [f"{submitter} fragt zum Thema „{title}“."]
    else:
        parts = [f"Die {type_label} fragt zum Thema „{title}“."]
    if recipient:
        parts.append(f"Adressiert ist die Frage an {recipient}.")
    answer = question_answer_text(record)
    if answer:
        parts.append(f"Erfasste Antwort: {short_text(answer)}")
    elif meaningful_viewer_result(result_text):
        if result_text == "Verfahren: zugewiesen":
            parts.append("In den lokalen Daten ist nur der Verfahrensstand „zugewiesen“ erfasst; eine inhaltliche Antwort ist dort nicht hinterlegt.")
        else:
            parts.append(f"Dokumentierter Stand: {result_text}.")
    else:
        parts.append("Eine Antwort ist in der lokalen Datenbasis nicht erfasst.")
    numbers = record.get("business_numbers", [])
    if isinstance(numbers, list) and numbers:
        parts.append(f"Geschäftszahl: {', '.join(str(number) for number in numbers[:2])}.")
    return " ".join(parts)


def question_summary_title(record: dict) -> str:
    title = viewer_display_title(record)
    normalized = re.sub(r"\s+", " ", title).strip()
    if not normalized:
        return "diese Frage"
    if re.match(r"^[„\"']?(?:sehr geehrt\w*|werter|werte|liebe kolleg)\b", normalized, flags=re.IGNORECASE):
        return "eine Frage in der Gemeinderatssitzung"
    if re.search(r"originaltext der frage", normalized, flags=re.IGNORECASE):
        return "eine Frage in der Gemeinderatssitzung"
    salutation = re.search(r"\s+(?:sehr geehrt\w*|werter|werte|liebe kolleg).*$", normalized, flags=re.IGNORECASE)
    if salutation and salutation.start() >= 8:
        normalized = normalized[: salutation.start()].strip(" ,.;:")
    if re.search(
        r"\b(Herr Bürgermeister|sehr geehrt\w*|liebe Kolleg|meine Frage|in meiner Frage|folgende Frage)\b",
        normalized,
        flags=re.IGNORECASE,
    ) or re.match(r"^[„\"']?(?:wie|was|warum|wieso|welche|mit welchen|in welcher|dürfen|duerfen|sind sie|haben sie|liegen|konnte)\b", normalized, flags=re.IGNORECASE):
        prefix = normalized.split(":", 1)[0].strip() if ":" in normalized else ""
        if prefix and len(prefix) <= 80 and re.search(r"\bGR\b|Gemeinder", prefix, flags=re.IGNORECASE):
            return f"eine Frage von {prefix}"
        return "eine Frage in der Gemeinderatssitzung"
    return normalized


def question_answer_text(record: dict) -> str:
    question_parts = record.get("question_parts", {})
    if not isinstance(question_parts, dict):
        return ""
    for key in ("answer", "followup_answer"):
        answer = clean_question_answer_text(str(question_parts.get(key) or ""))
        if answer:
            return answer
    return ""


def clean_question_answer_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"^(?:Antwort|Zusatzantwort)\s*:?\s*", "", text, flags=re.IGNORECASE).strip()
    text = remove_leading_question_salutation(text)
    text = trim_embedded_salutation(text)
    if looks_like_question_text(text):
        return ""
    return text


def trim_embedded_salutation(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if re.match(r"(?i)^(?:sehr geehrt\w*|werter|werte|liebe|geschätzte|geschaetzte|hoher gemeinderat)", text):
        return ""
    match = re.search(r"\b(?:sehr geehrt\w*|werter|werte|liebe kolleg|hoher gemeinderat)\b", text, flags=re.IGNORECASE)
    if match and match.start() <= 120:
        prefix = text[: match.start()].strip(" ,;:")
        if len(prefix) >= 12:
            return prefix
    return text


def remove_leading_question_salutation(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    text = re.sub(r"(?i)^(?:vielen herzlichen dank|vielen dank|danke)(?:[^.!?]{0,180}[.!?])?\s*", "", text).strip()
    text = re.sub(r"(?i)^(?:ja|nein|danke|selbstverständlich|selbstverstaendlich|selbstveständlich),?\s+", "", text).strip()
    if not re.match(
        r"(?i)^(?:sehr geehrt\w*|werter|werte|liebe|geschätzte|geschaetzte|frau |herr |danke für die frage|danke für deine frage|hoher gemeinderat)",
        text,
    ):
        return text
    stripped = re.sub(
        r"(?is)^(?:sehr geehrte?r?|werter|werte|liebe|geschätzte|geschaetzte|frau|herr|danke für die frage|danke für deine frage|hoher gemeinderat)"
        r"[^.!?]{0,220}[.!?]\s*",
        "",
        text,
        count=1,
    ).strip()
    return stripped or text


def looks_like_question_text(value: str) -> bool:
    text = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    return bool(
        re.search(
            r"\b(meine frage|in meiner frage|folgende frage|originaltext der frage|frage richtet sich|ich richte.*frage|zusatzfrage|darf zu meiner|zuerst eine frage|gleiche fragestellung)\b",
            text,
        )
        or text.endswith("?")
    )


def meaningful_viewer_result(result_text: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(result_text or "")).strip().casefold()
    return bool(normalized) and normalized not in {
        "unbekannt",
        "digra-ergebnis fehlt",
        "kein ergebnis in den lokalen digra-daten erfasst",
    }


def short_text(value: str, limit: int = 260) -> str:
    text = clean_question_answer_text(value) or re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= limit:
        return text if text.endswith(".") else f"{text}."
    return text[:limit].rsplit(" ", 1)[0].strip(" ,;:") + "."


def viewer_record_type(record: dict) -> str:
    record_type = str(record.get("record_type", ""))
    if is_attendance_asset(str(record.get("title", "")), str(record.get("source_url", ""))):
        return "attendance_list"
    return record_type


def viewer_display_title(record: dict) -> str:
    raw_title = clean_display_title(str(record.get("title", "")))
    title_is_role_only = role_only_display_title(str(record.get("title", "")))
    extracted_title = structured_title_from_record(record, allow_snippet=title_is_role_only)
    url_title = archive_asset_title_from_url(str(record.get("source_url", "")), raw_title)
    if extracted_title and (viewer_record_type(record) in {"archive_source", "attendance_list"} or generic_display_title(raw_title) or title_is_role_only):
        return extracted_title
    if url_title and generic_display_title(raw_title):
        return url_title
    if not raw_title and viewer_record_type(record) in {"question_hour", "written_question"}:
        return "Frage in der Gemeinderatssitzung"
    return raw_title or extracted_title or url_title or "Ohne Titel"


def structured_title_from_record(record: dict, allow_snippet: bool = False) -> str:
    for text in title_candidate_texts(record):
        match = re.search(r"(?im)^\s*(?:Thema|Betreff|Betr\.?)\s*:?\s*(?P<title>.+?)\s*$", text)
        title = clean_structured_title(match.group("title")) if match else (clean_snippet_title(text) if allow_snippet else "")
        if title:
            return title
    return ""


def title_candidate_texts(record: dict) -> list[str]:
    candidates: list[str] = []
    for key in ("source_snippet",):
        value = str(record.get(key, "") or "").strip()
        if value:
            candidates.append(value)
    question_parts = record.get("question_parts", {})
    if isinstance(question_parts, dict):
        candidates.extend(str(value).strip() for value in question_parts.values() if str(value).strip())
    return candidates


def clean_structured_title(value: str) -> str:
    title = re.split(r"\s{2,}|\s+-\s+|\s+–\s+", value, maxsplit=1)[0]
    title = re.sub(r"\s+", " ", title).strip(" ,;:-")
    return clean_display_title(title)


def clean_snippet_title(value: str) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip(" ,;:-")
    title = clean_display_title(title)
    title = re.split(
        r"\s+(?:I\.\s+Allgemeiner\s+Teil|II\.\s+Besonderer\s+Teil|Der\s+Gemeinderat\s+hat|Frau\s+GR|Herr\s+GR|Es\s+wird|Sehr geehrte Frau|Sehr geehrter Herr)\b",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:-")
    sentence_match = re.match(r"^(.{12,180}?[.!?])\s+(?:Der|Die|Das|Dieser|Diese|Dieses|Im|In|Es)\b", title)
    if sentence_match:
        title = sentence_match.group(1).strip(" ,;:-")
    if len(title) > 220:
        title = title[:220].rsplit(" ", 1)[0].strip(" ,;:-")
    if len(title.split()) < 2:
        return ""
    return title


def generic_display_title(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).strip(" ->").casefold()
    if not normalized:
        return True
    generic = {
        "antrag",
        "anträge",
        "antraege",
        "selbständiger antrag",
        "selbstaendiger antrag",
        "selbständiger antrag (§ 17 go-gr)",
        "selbstaendiger antrag (§ 17 go-gr)",
        "schriftlicher antrag",
        "schriftliche anträge",
        "schriftliche antraege",
        "schriftliche anfrage",
        "tagesordnung",
        "tagesordnungspunkt",
        "dringliche",
        "dringlicher antrag",
        "dringlichkeitsantrag",
        "dringlichkeitsantrag (§ 18 go-gr)",
        "dringlichkeitsanträge",
        "dringlichkeitsantraege",
        "dringlichkeitsanträge mit abstimmungsergebnissen",
        "dringlichkeitsantraege mit abstimmungsergebnissen",
        "frage für die fragestunde",
        "frage fuer die fragestunde",
        "frage für die fragestunde (§ 16a go-gr)",
        "frage fuer die fragestunde (§ 16a go-gr)",
        "mitteilung",
        "mitteilung an den gemeinderat",
        "mitteilung an den gemeinderat (§ 15 go-gr)",
        "antwort",
        "schriftliche antwort",
        "archivdokument",
        "archivquelle",
    }
    if normalized in generic:
        return True
    if role_only_display_title(value):
        return True
    return bool(re.fullmatch(r"(?:tagesordnung|anträge|antraege|dringliche|dringlichkeitsanträge|dringlichkeitsantraege)\s+\d+", normalized))


def role_only_display_title(value: str) -> bool:
    title = re.sub(r"\s+", " ", str(value or "")).strip(" ,;:-")
    if not title:
        return True
    return bool(re.match(r"^(?:Berichterstatter(?:in|:in)?|Bearbeiter(?:in|:in)?|Einbringer(?:in|:in)?)\s*:?\s*", title, re.IGNORECASE))


def viewer_votes(votes: object) -> list[dict]:
    if not isinstance(votes, list):
        return []
    cleaned: list[dict] = []
    for vote in votes:
        if not isinstance(vote, dict):
            continue
        cleaned.append(
            {
                "gegenstand": viewer_vote_subject(vote),
                "ergebnis": clean_viewer_text(vote.get("outcome_text", "")) or german_status(str(vote.get("outcome", ""))),
                "zustimmung": clean_vote_names(vote.get("approval", [])),
                "gegenstimmen": clean_vote_names(vote.get("against", [])),
                "enthaltungen": clean_vote_names(vote.get("abstention", [])),
            }
        )
    return cleaned


def viewer_vote_subject(vote: dict) -> str:
    organ = clean_viewer_text(vote.get("organ", ""))
    date = clean_viewer_text(vote.get("date", ""))
    if organ:
        return f"{organ} am {date}" if date else organ
    return clean_viewer_text(vote.get("subject", ""))


def clean_vote_names(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def inferred_viewer_locations(record: dict, result_text: str = "") -> list[str]:
    street_names = load_default_street_names()
    existing = [
        str(value).strip()
        for value in record.get("locations", [])
        if str(value).strip() and public_viewer_location(str(value)) and allowed_viewer_location(str(value), street_names)
    ]
    if broad_location_context(record, existing):
        direct_text = direct_location_text(record, result_text)
        existing = [value for value in existing if location_value_in_text(value, direct_text)]
    text = direct_location_text(record, result_text)
    inferred = [
        str(detail.get("value", "")).strip()
        for detail in extract_location_details(text, street_names=street_names)
        if public_viewer_location(str(detail.get("value", "")))
    ]
    inferred.extend(infer_street_locations_from_text(text, street_names=street_names))
    normalized_text = normalize_location_match_text(text)
    if street_names is None:
        for label, aliases in KNOWN_GRAZ_LOCATION_ALIASES.items():
            if any(
                re.search(rf"(?<!\w){re.escape(normalize_location_match_text(alias))}(?!\w)", normalized_text)
                for alias in aliases
            ):
                inferred.append(label)
    return unique_location_values([*existing, *inferred])


def allowed_viewer_location(value: str, street_names: set[str] | None = None) -> bool:
    if street_names is None:
        return True
    return normalize_street_name(value) in street_names


def direct_location_text(record: dict, result_text: str = "") -> str:
    attachment_titles = record.get("attachment_titles", [])
    if not isinstance(attachment_titles, list):
        attachment_titles = []
    return " ".join(
        str(value or "")
        for value in [
            record.get("title", ""),
            result_text,
            record.get("result_text", ""),
            record.get("section", ""),
            *attachment_titles,
        ]
    )


def broad_location_context(record: dict, existing_locations: list[str]) -> bool:
    details = record.get("location_details", [])
    detail_count = sum(
        1
        for detail in details
        if isinstance(detail, dict) and public_viewer_location(str(detail.get("value", "")))
    ) if isinstance(details, list) else 0
    text = " ".join(
        str(value or "")
        for value in [
            record.get("source_snippet", ""),
            record.get("ai_summary", ""),
            record.get("ai_easy_language", ""),
            record.get("ai_why_interesting", ""),
        ]
    )
    return len(existing_locations) >= 4 and (detail_count >= 4 or len(text) >= 1800)


def location_value_in_text(location: str, text: str) -> bool:
    normalized_location = normalize_location_match_text(location)
    normalized_text = normalize_location_match_text(text)
    return bool(re.search(rf"(?<!\w){re.escape(normalized_location)}(?!\w)", normalized_text))


def public_viewer_location(value: str) -> bool:
    location = re.sub(r"\s+", " ", str(value or "").strip(" ,.;:"))
    if not location:
        return False
    if location.casefold() in {"deckungsring"}:
        return False
    if re.match(r"^(?:EZ|KG|Gdst\.?|Gst\.?|Grundstück|Grundstueck|Katastralgemeinde|Einlagezahl)\b", location, re.IGNORECASE):
        return False
    if re.fullmatch(r"\d+(?:/\d+)?", location):
        return False
    return True


def normalize_location_match_text(value: str) -> str:
    return (
        value.casefold()
        .replace("ß", "ss")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
    )


def infer_street_locations_from_text(text: str, street_names: set[str] | None = None) -> list[str]:
    if street_names is not None:
        return unique_location_values([value for value, _start, _end in find_street_names_in_text(text, street_names)])
    suffixes = r"(?:Straße|Strasse|Gasse|Weg|Platz|Park|Brücke|Bruecke|Allee|Kai|Ufer|Ring|Gürtel|Guertel|Graben|Lände|Laende|Steig|Steg|Zeile)"
    patterns = [
        re.compile(rf"\b[A-ZÄÖÜ][\wÄÖÜäöüß.-]+(?:\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+){{0,3}}\s+{suffixes}\b"),
        re.compile(rf"\b[A-ZÄÖÜ][\wÄÖÜäöüß.-]+(?:[-–][A-ZÄÖÜ][\wÄÖÜäöüß.-]+){{0,3}}{suffixes.lower()}\b", re.IGNORECASE),
    ]
    values: list[str] = []
    for pattern in patterns:
        values.extend(match.group(0).strip() for match in pattern.finditer(text))
    return unique_location_values(values)


def unique_location_values(values: list[str], limit: int = 8) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        location = re.sub(r"\s+", " ", str(value or "").strip(" ,.;:"))
        if not location or len(location) > 80:
            continue
        if not public_viewer_location(location):
            continue
        key = normalize_location_match_text(location)
        if key in seen:
            continue
        seen.add(key)
        result.append(location)
        if len(result) >= limit:
            break
    return result


def question_recipient(record: dict) -> str:
    addressee = str(record.get("addressee", "") or "").strip()
    if plausible_question_recipient(addressee):
        return clean_question_recipient(addressee)
    question_parts = record.get("question_parts", {})
    if isinstance(question_parts, dict):
        respondent = str(question_parts.get("respondent", "")).strip()
        if plausible_question_recipient(respondent):
            return clean_question_recipient(respondent)
    record_type = str(record.get("record_type", ""))
    section = str(record.get("section", "")).casefold()
    if record_type == "written_question" and "anfragen an den bürgermeister" in section:
        return "Bürgermeister"
    inferred = infer_question_recipient_from_text(
        " ".join(
            str(record.get(key, "") or "")
            for key in ("title", "source_snippet", "ai_summary", "ai_easy_language")
        )
    )
    if inferred:
        return inferred
    return ""


QUESTION_TITLE_PARTY_RE = re.compile(
    r"^(?:KPÖ|KPOE|Grüne|Gruene|ÖVP|OEVP|SPÖ|SPOE|FPÖ|FPOE|NEOS|KFG|Eustacchio|Reininghaus)$",
    re.IGNORECASE,
)


def question_people_from_title(title: str) -> tuple[str, str]:
    match = re.search(r"\(([^()]+)\)\s*$", str(title or ""))
    if not match:
        return "", ""
    parts = [re.sub(r"\s+", " ", part).strip(" ,.;:") for part in match.group(1).split(",")]
    lowered = [part.casefold() for part in parts]
    if "an" not in lowered:
        return "", ""
    an_index = lowered.index("an")
    submitter = question_person_from_parts(parts[:an_index])
    recipient = question_person_from_parts(parts[an_index + 1 :])
    return submitter, recipient


def question_person_from_parts(parts: list[str]) -> str:
    values = [part for part in parts if part]
    if len(values) < 2:
        return ""
    party_index = next((index for index, part in enumerate(values) if QUESTION_TITLE_PARTY_RE.fullmatch(part)), -1)
    if party_index <= 0:
        return ""
    name = ", ".join(values[:party_index]).strip()
    party = values[party_index].strip()
    if not name or not party:
        return ""
    return f"{name} ({party})"


def infer_question_recipient_from_text(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or ""))
    patterns = [
        r"\ban\s+(?P<recipient>(?:Bürgermeisterin|Buergermeisterin|Bürgermeister|Buergermeister|StRin\.?|StR\.?|Stadträtin|Stadtraetin|Stadtrat|VzBgmin\.?|Bgm\.?)[^,.;:)\\n]{0,90})",
        r"\brichtet\s+sich\s+an\s+(?P<recipient>[^,.;:)\\n]{2,90})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if not match:
            continue
        recipient = clean_question_recipient(match.group("recipient"))
        if plausible_question_recipient(recipient):
            return recipient
    return ""


def clean_question_recipient(value: str) -> str:
    recipient = re.sub(r"\s+", " ", str(value or "")).strip(" ,.;:")
    normalized = recipient.casefold()
    if re.search(r"\bherr bürgermeister\b|\bherr buergermeister\b", normalized):
        return "Bürgermeister"
    if re.search(r"\bfrau bürgermeisterin\b|\bfrau buergermeisterin\b", normalized):
        return "Bürgermeisterin"
    if re.search(r"\b(meine frage|in meiner frage|folgende frage|nachdem|werter|sehr geehrt|liebe kolleg)\b", normalized):
        return ""
    return recipient


def plausible_question_recipient(value: str) -> bool:
    recipient = value.strip(" ,.;:")
    if not recipient or len(recipient) > 80:
        return False
    normalized = recipient.casefold()
    if re.search(r"\b(meine frage|in meiner frage|folgende frage|liebe kolleg)\b", normalized):
        return False
    if "bürgermeister" in normalized or "buergermeister" in normalized:
        return True
    if re.search(r"\b(?:str\.?|strin\.?|stadtrat|stadträtin|stadtraetin|bgin\.?|bgm\.?)\b", normalized):
        return True
    if re.match(r"^(?:mag\.?|maga\.?|dr\.?|dipl\.-ing\.?)\s+", normalized):
        return True
    return False


def normalized_viewer_status(record: dict) -> str:
    record_type = str(record.get("record_type", ""))
    status = str(record.get("status", ""))
    if record_type == "question_hour":
        answer_status = normalized_question_hour_answer_status(record)
        if answer_status:
            return answer_status
    if record_type in {"written_question", "written_motion", "amendment_motion", "additional_motion"} and status in {"", "unknown"}:
        return "assigned"
    return status


def normalized_viewer_result_text(record: dict, status: str) -> str:
    result_text = str(record.get("result_text", "") or "")
    if status == "answered_oral":
        return "mündlich beantwortet"
    if status == "answered_written":
        return "schriftlich beantwortet"
    if status == "answer_pending_written":
        return "wird schriftlich beantwortet"
    if status == "assigned" and result_text in {"", "Unbekannt", "DIGRA-Ergebnis fehlt"}:
        return "Verfahren: zugewiesen"
    return result_text


def normalized_question_hour_answer_status(record: dict) -> str:
    votes = record.get("votes", [])
    if isinstance(votes, list):
        for vote in votes:
            if not isinstance(vote, dict):
                continue
            text = str(vote.get("outcome_text", "") or vote.get("raw_text", "") or vote.get("outcome", "")).casefold()
            if "mündlich beantwortet" in text or "muendlich beantwortet" in text:
                return "answered_oral"
            if "wird schriftlich beantwortet" in text or "werden schriftlich beantwortet" in text:
                return "answer_pending_written"
            if "schriftlich beantwortet" in text:
                return "answered_written"
    combined = f"{record.get('result_text', '')} {record.get('raw_result_text', '')}".casefold()
    if "mündlich beantwortet" in combined or "muendlich beantwortet" in combined:
        return "answered_oral"
    if "wird schriftlich beantwortet" in combined or "werden schriftlich beantwortet" in combined:
        return "answer_pending_written"
    if "schriftlich beantwortet" in combined:
        return "answered_written"
    return ""


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
        "dates": topic.get("dates", []),
        "records": [
            {
                "meeting_date": record.get("meeting_date", ""),
                "type": german_record_type(str(record.get("record_type", ""))),
                "title": clean_display_title(str(record.get("title", ""))),
                "record_id": record.get("record_id", ""),
                "business_numbers": record.get("business_numbers", []),
                "business_number": " ".join(str(value) for value in record.get("business_numbers", [])),
                "result_source": german_result_source(str(record.get("result_source", "")), canonical_digra_url(str(record.get("digra_url", "")))),
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
        "archive_agenda_item": "Archiv-Tagesordnungspunkt",
        "archive_source": "Archivquelle",
        "attendance_list": "Anwesenheitsliste",
        "communication": "Mitteilung",
        "amendment_motion": "Abänderungsantrag",
        "additional_motion": "Zusatzantrag",
        "urgent_motion": "Dringlichkeitsantrag",
        "written_question": "Schriftliche Anfrage",
        "written_motion": "Schriftlicher Antrag",
        "question_hour": "Fragestunde",
    }.get(value, value)


def clean_display_title(value: str) -> str:
    title = re.sub(r"\s+", " ", value).strip(" ,;")
    title = re.sub(r"^(?:Frage|Antwort)\s*:\s*", "", title, flags=re.IGNORECASE).strip(" ,;:-")
    title = re.sub(r"\bvon deiner Seite\b", "von zuständiger Seite", title, flags=re.IGNORECASE)
    title = re.sub(r"\bdeinerseits\b", "von zuständiger Seite", title, flags=re.IGNORECASE)
    if re.match(r"^(?:Sehr geehrte|Sehr geehrter|Sehr geehrtes|Werter|Werte|Liebe)\b", title, flags=re.IGNORECASE):
        return ""
    title = strip_title_role_prefixes(title)
    prefixes = (
        "fragestunde",
        "schriftliche anfrage",
        "anfrage",
        "schriftlicher antrag",
        "dringlichkeitsantrag",
        "dringlicher antrag",
        "mitteilung",
        "mitteilungen",
        "tagesordnungspunkt",
        "protokolldokument",
        "archivdokument",
        "archivquelle",
    )
    pattern = r"^(?:" + "|".join(re.escape(prefix) for prefix in prefixes) + r")\s*:\s*"
    previous = ""
    while title and title != previous:
        previous = title
        title = re.sub(pattern, "", title, flags=re.IGNORECASE).strip(" ,;")
        title = strip_title_role_prefixes(title)
    title = strip_title_salutation_tail(title)
    return title


def strip_title_role_prefixes(value: str) -> str:
    title = value
    role_pattern = (
        r"^(?:Berichterstatter(?:in|:in)?|Bearbeiter(?:in|:in)?|Einbringer(?:in|:in)?)\s*:?\s*"
        r"[^:;]{0,220}?(?:\((?:KPÖ|KPOE|Grüne|Gruene|SPÖ|SPOE|ÖVP|OEVP|FPÖ|FPOE|NEOS|KFG|GRÜNE)\)|,?\s(?:KPÖ|KPOE|Grüne|Gruene|SPÖ|SPOE|ÖVP|OEVP|FPÖ|FPOE|NEOS|KFG|GRÜNE))\s+"
    )
    previous = ""
    while title and title != previous:
        previous = title
        title = re.sub(role_pattern, "", title, flags=re.IGNORECASE).strip(" ,;:-")
    return title


def strip_title_salutation_tail(value: str) -> str:
    title = re.sub(r"\s+(?:Sehr geehrte Frau|Sehr geehrter Herr|Sehr geehrte Damen und Herren)\b.*$", "", value, flags=re.IGNORECASE)
    return title.strip(" ,;:-")


def german_status(value: str) -> str:
    return {
        "accepted_unanimous": "angenommen (einstimmig)",
        "accepted_majority": "angenommen (mehrheitlich)",
        "accepted": "angenommen",
        "noted": "zur Kenntnis genommen",
        "rejected_majority": "mehrheitlich abgelehnt",
        "rejected": "abgelehnt",
        "source_available": "Quelle verfügbar",
        "answered_oral": "mündlich beantwortet",
        "answered_written": "schriftlich beantwortet",
        "answer_pending_written": "wird schriftlich beantwortet",
        "assigned": "zugewiesen",
        "postponed": "vertagt",
        "unknown": "unklar",
    }.get(value, value)


def german_status_filter(value: str) -> str:
    if value in {"accepted_unanimous", "accepted_majority", "accepted"}:
        return "Angenommen"
    if value in {"rejected_majority", "rejected"}:
        return "Abgelehnt"
    if value == "noted":
        return "Zur Kenntnis genommen"
    if value == "source_available":
        return "Quelle verfügbar"
    if value in {"answered_oral", "answered_written", "answer_pending_written"}:
        return "Beantwortet"
    return german_status(value).capitalize()


def german_result_source(value: str, digra_url: str = "") -> str:
    if value == "digra_fehlt" and digra_url:
        return "DIGRA"
    return {
        "archiv": "Stadt-Graz-Archiv",
        "digra": "DIGRA",
        "digra_fehlt": "DIGRA fehlt",
        "protokoll": "Stadt-Graz-Protokoll",
    }.get(value, value or "Stadt-Graz-Protokoll")


def german_source_file(value: str) -> str:
    if str(value or "").casefold().endswith((".docx", ".doc")):
        return ""
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
