from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
import csv
import io
import json
import re
from urllib.request import urlopen

from bs4 import BeautifulSoup
import requests

from .civic_services import civic_service_summary


PARKING_CSV_URL = "https://data.graz.gv.at/graz/wp-content/uploads/2024/06/Parkgaragen.csv"
PARKING_DATASET_URL = "https://www.data.gv.at/katalog/dataset/92183c55-442b-405d-9046-d19b07ffc83a"
PARKING_LICENSE = "CC BY 4.0"
PARKING_ATTRIBUTION = "Stadt Graz - data.graz.gv.at"
ROADWORKS_INFO_URL = "https://www.graz.at/cms/beitrag/10295878/8115447/Baustelleninformation.html"
ROADWORKS_OFFICE_URL = "https://www.graz.at/cms/beitrag/10028253/7755789/Baustellen_in_Graz.html"
OVERPASS_URL = "https://overpass.kumi.systems/api/interpreter"
OSM_COPYRIGHT_URL = "https://www.openstreetmap.org/copyright"
APOTHEKEN_SEARCH_URL = "https://www.apothekerkammer.at/apothekensuche"
ORDINATIONEN_ST_URL = "https://ordinationen.st/"
GRAZ_BBOX = (46.98, 15.34, 47.13, 15.54)
ROADWORKS_USAGE_NOTE = (
    "Die offiziellen Baustellen-Geodaten sind als Geoportal-Online-Service beschrieben, nicht als OGD-Datensatz. "
    "Die lokale HTML-Ansicht lädt deshalb nur aktuelle, öffentliche Baustelleninfos aus graz.at bzw. aus dem lokalen Cache."
)
TRAFFIC_DATA_SOURCES = [
    {
        "name": "Data Graz Verkehr",
        "url": "https://data.graz.gv.at/graz/verkehr/",
        "platform": "data.graz.gv.at",
        "coverage": "Graz",
        "license": "je Datensatz prüfen",
        "formats": [],
        "use_for": ["lokale OGD-Suche", "Graz-spezifische Verkehrsdaten"],
        "reuse": "Katalogeinstieg; einzelne offene Datensätze mit klarer Lizenz importieren. Parkgaragen aus Data Graz sind bereits eingebunden.",
        "integration_status": "teilweise integriert",
        "priority": "hoch",
    },
    {
        "name": "Kulturserver Graz Veranstaltungskalender",
        "url": "https://kultur.graz.at/kalender/",
        "platform": "kultur.graz.at",
        "coverage": "kulturelle Veranstaltungen im Stadtgebiet Graz",
        "license": "Nutzungsrechte/Lizenz vor Import klären",
        "formats": ["RSS", "HTML"],
        "use_for": ["Veranstaltungen", "Kulturkalender", "öffentlicher Raum"],
        "reuse": "Offizielle Stadt-Graz-Seite mit RSS-Feeds. Für Open-Source standardmäßig nur verlinken; strukturierter Import erst nach geklärter Weiterverwendung.",
        "integration_status": "Veranstaltungsquelle prüfen",
        "priority": "hoch",
    },
    {
        "name": "Graz Linien - Fahrplandaten und Haltestellen",
        "url": "https://data.europa.eu/data/datasets/7317b9ca-1349-4660-a2db-54e67160d469?locale=de",
        "platform": "data.gv.at / data.europa.eu",
        "coverage": "Graz",
        "license": "je Metadatensatz prüfen",
        "formats": ["GTFS"],
        "use_for": ["ÖV-Haltestellen", "Linien", "Fahrpläne"],
        "reuse": "Guter Kandidat für eine GTFS-Import-Schicht für Haltestellen, Linien und Fahrpläne; aktuelle Download-URL und Lizenz vor Import prüfen.",
        "integration_status": "GTFS-Adapter vorbereiten",
        "priority": "hoch",
    },
    {
        "name": "Radzählstellenbericht",
        "url": "https://mobilitaetsdaten.gv.at/en/daten/radz%C3%A4hlstellenbericht",
        "platform": "mobilitydata.gv.at",
        "coverage": "Österreich, inkl. Stadt Graz als Dateneigentümer",
        "license": "No licence - No contract",
        "formats": ["Bericht/PDF"],
        "use_for": ["Radverkehrskontext", "Jahresvergleich", "strategische Einschätzung"],
        "reuse": "Nur verlinken oder manuell auswerten; nicht als offenen Rohdatensatz importieren.",
        "priority": "mittel",
    },
    {
        "name": "Graphenintegrations-Plattform Österreich (GIP.at)",
        "url": "https://mobilitaetsdaten.gv.at/en/daten/graphenintegrations-plattform-%C3%B6sterreich-gipat",
        "platform": "mobilitydata.gv.at / data.gv.at",
        "coverage": "Österreich",
        "license": "No licence - No contract laut Mobilitydata-Eintrag; Data-access-Link gesondert prüfen",
        "formats": ["GIP", "sonstige Geodaten"],
        "use_for": ["Straßennetz", "Routing-Referenz", "Georeferenzierung"],
        "reuse": "Technisch sehr relevant, aber nicht ohne geklärte Nutzungsbedingungen importieren.",
        "priority": "mittel",
    },
    {
        "name": "Geplante Ereignismeldungen (EVIS.AT)",
        "url": "https://mobilitaetsdaten.gv.at/daten/geplante-ereignismeldungen-evisat",
        "platform": "mobilitydata.gv.at / EVIS.AT",
        "coverage": "Österreich, inkl. Stadt- und Gemeindestraßen",
        "license": "Nutzungsvertrag mit Nutzungsgebühr",
        "formats": ["DATEX II", "XML", "UTF-8"],
        "use_for": ["Baustellen", "Sperren", "Veranstaltungen", "geplante Verkehrsmaßnahmen"],
        "reuse": "Technisch als DATEX-II/XML-Adapter möglich, aber nicht für Open-Source-Import ohne Vertrag; als lizenzierter Zieladapter dokumentieren.",
        "integration_status": "lizenzierter DATEX-II-Adapter",
        "priority": "hoch",
    },
    {
        "name": "Ungeplante Ereignismeldungen (EVIS.AT)",
        "url": "https://mobilitaetsdaten.gv.at/en/daten/ungeplante-ereignismeldungen-evisat",
        "platform": "mobilitydata.gv.at / EVIS.AT",
        "coverage": "Österreich, inkl. Stadt- und Gemeindestraßen",
        "license": "Contract and Fee",
        "formats": ["DATEX II", "XML", "UTF-8"],
        "use_for": ["Unfälle", "Störungen", "Stau", "kurzfristige Sperren"],
        "reuse": "Nicht für Open-Source-Import ohne Vertrag; nur verlinken oder mit Zugang als lokaler Adapter.",
        "priority": "mittel",
    },
    {
        "name": "Verkehrslage (EVIS.AT)",
        "url": "https://mobilitaetsdaten.gv.at/daten/verkehrslage-evisat",
        "platform": "mobilitydata.gv.at / EVIS.AT",
        "coverage": "Österreich, inkl. Stadt- und Gemeindestraßen",
        "license": "Nutzungsvertrag mit Nutzungsgebühr",
        "formats": ["JSON", "UTF-8"],
        "use_for": ["Verkehrsaufkommen", "Geschwindigkeit", "Reisezeiten", "Level of Service"],
        "reuse": "Nicht für Open-Source-Import ohne Vertrag; für spätere lizenzierte Live-Bewertung geeignet.",
        "priority": "mittel",
    },
]
ROADWORK_LOCATION_RE = re.compile(
    r"\b(?:straße|strasse|gasse|weg|platz|ring|gürtel|guertel|kai|allee|brücke|bruecke|lände|laende|graben|ufer)\b",
    re.IGNORECASE,
)
ROADWORK_PERIOD_RE = re.compile(r"\b(?:Termin|Zeitraum)\s*:?\s*(?P<value>.+)", re.IGNORECASE)
ROADWORK_CURRENT_UNTIL_RE = re.compile(
    r"\b(?P<value>derzeit\s*(?:[-–]|bis)\s*(?:0?[1-9]|[12]\d|3[01])\.(?:0?[1-9]|1[0-2])\.?\s*\d{4})",
    re.IGNORECASE,
)
ROADWORK_DATE_RE = re.compile(
    r"(?P<day>0?[1-9]|[12]\d|3[01])\.(?P<month>0?[1-9]|1[0-2])\.?(?:\s*(?P<year>\d{4}))?(?!\d)"
)


@dataclass(frozen=True)
class ParkingGarage:
    name: str
    address: str
    kind: str
    provider: str
    lat: float
    lon: float
    spaces: int | None = None
    availability: str = "unbekannt"
    source: str = PARKING_ATTRIBUTION
    source_url: str = PARKING_DATASET_URL
    license: str = PARKING_LICENSE


@dataclass(frozen=True)
class RoadworkInfo:
    title: str
    location: str
    description: str
    period: str = ""
    start_date: str = ""
    end_date: str = ""
    time_status: str = "unklar"
    project: str = ""
    source: str = "Stadt Graz - Baustellen in Graz"
    source_url: str = ROADWORKS_OFFICE_URL
    license: str = "öffentliche Webseite, keine OGD-Lizenz gefunden"


@dataclass(frozen=True)
class HealthPlace:
    name: str
    address: str
    kind: str
    profession: str
    lat: float
    lon: float
    opening_hours: str = ""
    phone: str = ""
    website: str = ""
    source: str = "OpenStreetMap"
    source_url: str = OSM_COPYRIGHT_URL
    license: str = "ODbL"


def load_parking_garages(cache_path: Path | None = None, url: str = PARKING_CSV_URL) -> tuple[list[dict], dict]:
    errors: list[str] = []
    text = ""
    if cache_path and cache_path.exists():
        cache_bytes = cache_path.read_bytes()
        text = decode_parking_csv_bytes(cache_bytes)
    else:
        try:
            with urlopen(url, timeout=5) as response:  # noqa: S310 - fixed public OGD URL by default
                text = decode_parking_csv_bytes(response.read())
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(str(exc))

    garages = parse_parking_csv(text) if text else []
    summary = {
        "source_url": PARKING_DATASET_URL,
        "download_url": url,
        "license": PARKING_LICENSE,
        "attribution": PARKING_ATTRIBUTION,
        "records": len(garages),
        "availability": "unbekannt",
        "errors": errors,
    }
    return [asdict(garage) for garage in garages], summary


def load_health_places(
    kind: str,
    cache_path: Path | None = None,
    overpass_url: str = OVERPASS_URL,
) -> tuple[list[dict], dict]:
    errors: list[str] = []
    text = ""
    if cache_path and cache_path.exists():
        text = cache_path.read_text(encoding="utf-8")
    else:
        try:
            response = requests.post(
                overpass_url,
                data={"data": overpass_health_query(kind)},
                headers={"User-Agent": "graz-protocols-viewer/0.1"},
                timeout=12,
            )
            response.raise_for_status()
            text = response.text
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(str(exc))
    places = parse_osm_health_places(text, kind) if text else []
    summary = {
        "source_url": OSM_COPYRIGHT_URL,
        "download_url": overpass_url,
        "license": "ODbL",
        "attribution": "OpenStreetMap-Mitwirkende",
        "records": len(places),
        "errors": errors,
        "note": (
            "OSM-Grunddaten werden nur mit ODbL-Namensnennung genutzt. "
            "Nachtdienste, Bereitschaftsdienste und medizinische Verfügbarkeiten werden nicht lokal berechnet."
        ),
    }
    return [asdict(place) for place in places], summary


def overpass_health_query(kind: str) -> str:
    south, west, north, east = GRAZ_BBOX
    if kind == "pharmacy":
        selectors = (
            f'node["amenity"="pharmacy"]({south},{west},{north},{east});'
            f'way["amenity"="pharmacy"]({south},{west},{north},{east});'
            f'relation["amenity"="pharmacy"]({south},{west},{north},{east});'
        )
    else:
        selectors = (
            f'node["amenity"="doctors"]({south},{west},{north},{east});'
            f'way["amenity"="doctors"]({south},{west},{north},{east});'
            f'relation["amenity"="doctors"]({south},{west},{north},{east});'
            f'node["healthcare"="doctor"]({south},{west},{north},{east});'
            f'way["healthcare"="doctor"]({south},{west},{north},{east});'
            f'relation["healthcare"="doctor"]({south},{west},{north},{east});'
            f'node["amenity"="veterinary"]({south},{west},{north},{east});'
            f'way["amenity"="veterinary"]({south},{west},{north},{east});'
            f'relation["amenity"="veterinary"]({south},{west},{north},{east});'
            f'node["amenity"="dentist"]({south},{west},{north},{east});'
            f'way["amenity"="dentist"]({south},{west},{north},{east});'
            f'relation["amenity"="dentist"]({south},{west},{north},{east});'
            f'node["healthcare"="veterinary"]({south},{west},{north},{east});'
            f'way["healthcare"="veterinary"]({south},{west},{north},{east});'
            f'relation["healthcare"="veterinary"]({south},{west},{north},{east});'
            f'node["healthcare"="dentist"]({south},{west},{north},{east});'
            f'way["healthcare"="dentist"]({south},{west},{north},{east});'
            f'relation["healthcare"="dentist"]({south},{west},{north},{east});'
        )
    return (
        f'[out:json][timeout:15];'
        f'('
        f'{selectors}'
        f');out center tags;'
    )


def parse_osm_health_places(text: str, kind: str) -> list[HealthPlace]:
    if not text.strip():
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return []
    places: list[HealthPlace] = []
    for element in payload.get("elements", []):
        tags = element.get("tags") or {}
        if not osm_health_tag_matches(tags, kind):
            continue
        lat = element.get("lat") or (element.get("center") or {}).get("lat")
        lon = element.get("lon") or (element.get("center") or {}).get("lon")
        if lat is None or lon is None:
            continue
        name = clean_text(tags.get("name", ""))
        if not name:
            continue
        places.append(
            HealthPlace(
                name=name,
                address=osm_address(tags),
                kind=osm_health_kind(tags, kind),
                profession=osm_health_profession(tags, kind),
                lat=float(lat),
                lon=float(lon),
                opening_hours=clean_text(tags.get("opening_hours", "")),
                phone=clean_text(tags.get("phone", "") or tags.get("contact:phone", "")),
                website=osm_health_website(tags, name),
            )
        )
    return sorted(places, key=lambda place: (place.name.casefold(), place.address.casefold()))


def osm_health_tag_matches(tags: dict, kind: str) -> bool:
    if kind == "pharmacy":
        return tags.get("amenity") == "pharmacy"
    return tags.get("amenity") in {"doctors", "veterinary", "dentist"} or tags.get("healthcare") in {
        "doctor",
        "veterinary",
        "dentist",
    }


def osm_health_kind(tags: dict, kind: str) -> str:
    if kind == "pharmacy":
        return "Apotheke"
    if tags.get("amenity") == "veterinary" or tags.get("healthcare") == "veterinary":
        return "Tierarzt"
    if tags.get("amenity") == "dentist" or tags.get("healthcare") == "dentist":
        return "Zahnarzt"
    return "Ordination"


def osm_health_profession(tags: dict, kind: str) -> str:
    if kind == "pharmacy":
        return ""
    if tags.get("amenity") == "veterinary" or tags.get("healthcare") == "veterinary":
        return "Tierarzt"
    if tags.get("amenity") == "dentist" or tags.get("healthcare") == "dentist":
        return "Zahnarzt"
    raw = (
        tags.get("healthcare:speciality")
        or tags.get("speciality")
        or tags.get("healthcare:specialty")
        or tags.get("medical_system:speciality")
        or ""
    )
    values = [german_specialty_label(part) for part in re.split(r"[;,]", str(raw)) if clean_text(part)]
    return ", ".join(values) if values else "Allgemeinmedizin"


def osm_health_website(tags: dict, name: str) -> str:
    del name
    for key in ("website", "contact:website", "url", "contact:url", "brand:website"):
        website = normalize_website(tags.get(key, ""))
        if website:
            return website
    return ""


def normalize_website(value: str) -> str:
    website = clean_text(value)
    if not website:
        return ""
    if website.startswith("http://"):
        return "https://" + website.removeprefix("http://")
    if website.startswith("https://"):
        return website
    if "." in website and " " not in website:
        return "https://" + website
    return ""


def german_specialty_label(value: str) -> str:
    normalized = clean_text(str(value).replace("_", " ")).casefold()
    labels = {
        "doctor": "Allgemeinmedizin",
        "physician": "Allgemeinmedizin",
        "ordination": "Allgemeinmedizin",
        "allgemeinmedizin": "Allgemeinmedizin",
        "allgemeinmedizin/ordination": "Allgemeinmedizin",
        "ordination/ärztin/arzt": "Allgemeinmedizin",
        "ärztin/arzt": "Allgemeinmedizin",
        "arzt": "Allgemeinmedizin",
        "ärztin": "Allgemeinmedizin",
        "general": "Allgemeinmedizin",
        "general practitioner": "Allgemeinmedizin",
        "family medicine": "Allgemeinmedizin",
        "gp": "Allgemeinmedizin",
        "practice": "Allgemeinmedizin",
        "internal": "Innere Medizin",
        "internal medicine": "Innere Medizin",
        "innere medizin": "Innere Medizin",
        "cardiology": "Kardiologie",
        "kardiologie": "Kardiologie",
        "dermatology": "Dermatologie",
        "dermatologie": "Dermatologie",
        "hautarzt": "Dermatologie",
        "haut und geschlechtskrankheiten": "Dermatologie",
        "gynecology": "Gynäkologie",
        "gynaecology": "Gynäkologie",
        "gynaekologie": "Gynäkologie",
        "gynäkologie": "Gynäkologie",
        "obstetrics and gynaecology": "Gynäkologie und Geburtshilfe",
        "obstetrics": "Geburtshilfe",
        "geburtshilfe": "Geburtshilfe",
        "ophthalmology": "Augenheilkunde",
        "optometry": "Augenheilkunde",
        "augenheilkunde": "Augenheilkunde",
        "orthopaedics": "Orthopädie",
        "orthopedics": "Orthopädie",
        "orthopaedic": "Orthopädie",
        "orthopedic": "Orthopädie",
        "orthopädie": "Orthopädie",
        "orthopaedie": "Orthopädie",
        "paediatrics": "Kinderheilkunde",
        "pediatrics": "Kinderheilkunde",
        "paediatric": "Kinderheilkunde",
        "pediatric": "Kinderheilkunde",
        "kinderheilkunde": "Kinderheilkunde",
        "psychiatry": "Psychiatrie",
        "psychiatrie": "Psychiatrie",
        "neurology": "Neurologie",
        "neurologie": "Neurologie",
        "radiology": "Radiologie",
        "radiologie": "Radiologie",
        "urology": "Urologie",
        "urologie": "Urologie",
        "surgery": "Chirurgie",
        "surgeon": "Chirurgie",
        "chirurgie": "Chirurgie",
        "general surgery": "Chirurgie",
        "emergency": "Notfallmedizin",
        "emergency medicine": "Notfallmedizin",
        "notfallmedizin": "Notfallmedizin",
        "anaesthetics": "Anästhesiologie",
        "anesthetics": "Anästhesiologie",
        "anaesthesiology": "Anästhesiologie",
        "anesthesiology": "Anästhesiologie",
        "anästhesiologie": "Anästhesiologie",
        "anaesthesiologie": "Anästhesiologie",
        "ent": "Hals-Nasen-Ohren-Heilkunde",
        "hno": "Hals-Nasen-Ohren-Heilkunde",
        "otolaryngology": "Hals-Nasen-Ohren-Heilkunde",
        "ear nose throat": "Hals-Nasen-Ohren-Heilkunde",
        "hals nasen ohren heilkunde": "Hals-Nasen-Ohren-Heilkunde",
        "oncology": "Onkologie",
        "onkologie": "Onkologie",
        "pulmonology": "Lungenheilkunde",
        "pneumology": "Lungenheilkunde",
        "pneumologie": "Lungenheilkunde",
        "lungenheilkunde": "Lungenheilkunde",
        "gastroenterology": "Gastroenterologie",
        "gastroenterologie": "Gastroenterologie",
        "nephrology": "Nephrologie",
        "nephrologie": "Nephrologie",
        "endocrinology": "Endokrinologie",
        "endokrinologie": "Endokrinologie",
        "rheumatology": "Rheumatologie",
        "rheumatologie": "Rheumatologie",
        "allergology": "Allergologie",
        "allergologie": "Allergologie",
        "psychology": "Psychologie",
        "psychologist": "Psychologie",
        "psychologie": "Psychologie",
        "psychotherapy": "Psychotherapie",
        "psychotherapist": "Psychotherapie",
        "psychotherapie": "Psychotherapie",
        "physiotherapy": "Physiotherapie",
        "physiotherapist": "Physiotherapie",
        "physiotherapie": "Physiotherapie",
        "occupational": "Arbeitsmedizin",
        "occupational medicine": "Arbeitsmedizin",
        "arbeitsmedizin": "Arbeitsmedizin",
        "dentist": "Zahnarzt",
        "veterinary": "Tierarzt",
        "dentistry": "Zahnarzt",
        "zahnarzt": "Zahnarzt",
        "tierarzt": "Tierarzt",
    }
    return labels.get(normalized, specialty_display_label(value))


def specialty_display_label(value: str) -> str:
    clean = re.sub(r"\s+", " ", clean_text(value).replace("_", " ").replace("/", " ")).strip()
    if not clean:
        return ""
    return " ".join(part if part.isupper() and len(part) <= 3 else part[:1].upper() + part[1:] for part in clean.split())


def osm_address(tags: dict) -> str:
    street = clean_text(tags.get("addr:street", ""))
    house = clean_text(tags.get("addr:housenumber", ""))
    postcode = clean_text(tags.get("addr:postcode", ""))
    city = clean_text(tags.get("addr:city", "Graz"))
    line = " ".join(part for part in (street, house) if part)
    place = " ".join(part for part in (postcode, city) if part)
    return ", ".join(part for part in (line, place) if part)


def load_roadworks(cache_path: Path | None = None, url: str = ROADWORKS_OFFICE_URL) -> tuple[list[dict], dict]:
    errors: list[str] = []
    text = ""
    if cache_path and cache_path.exists():
        text = cache_path.read_text(encoding="utf-8")
    else:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            text = response.text
            if cache_path:
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
        except Exception as exc:  # pylint: disable=broad-except
            errors.append(str(exc))

    roadworks = parse_roadworks_html(text) if text else []
    summary = {
        "source_url": ROADWORKS_INFO_URL,
        "office_url": ROADWORKS_OFFICE_URL,
        "license": "öffentliche Webseite, keine OGD-Lizenz gefunden",
        "records": len(roadworks),
        "errors": errors,
        "note": ROADWORKS_USAGE_NOTE,
    }
    return [asdict(roadwork) for roadwork in roadworks], summary


def parse_roadworks_html(text: str) -> list[RoadworkInfo]:
    if not text.strip():
        return []
    soup = BeautifulSoup(text, "html.parser")
    roadworks: list[RoadworkInfo] = []
    wrappers = soup.select(".txtblock-wrapper")
    if not wrappers:
        wrappers = soup.find_all(["section", "article", "div"])
    seen: set[str] = set()
    for wrapper in wrappers:
        heading = wrapper.find(["h2", "h3", "h4"])
        if not heading:
            continue
        title = clean_text(heading.get_text(" ", strip=True))
        if not title or not looks_like_roadwork_location(title):
            continue
        content = wrapper.select_one(".txtblock-content") or wrapper
        lines = [
            clean_text(line)
            for line in content.get_text("\n", strip=True).splitlines()
            if clean_text(line) and clean_text(line) != title
        ]
        if not lines:
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        period = ""
        project = ""
        description_lines: list[str] = []
        for line in lines:
            period_match = ROADWORK_PERIOD_RE.search(line)
            if period_match:
                period = clean_text(period_match.group("value"))
                continue
            if "projekt:" in line.casefold():
                project = clean_text(re.sub(r"^\(?\s*Projekt\s*:\s*", "", line, flags=re.IGNORECASE).strip("() "))
                continue
            description_lines.append(line)
        if not period:
            period = infer_roadwork_period(description_lines)
        start_date, end_date = normalize_roadwork_period(period)
        roadworks.append(
            RoadworkInfo(
                title=title,
                location=title,
                description="; ".join(description_lines),
                period=period,
                start_date=start_date,
                end_date=end_date,
                time_status=roadwork_time_status(period),
                project=project,
            )
        )
    return roadworks


def looks_like_roadwork_location(value: str) -> bool:
    return bool(ROADWORK_LOCATION_RE.search(value))


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


def infer_roadwork_period(lines: list[str]) -> str:
    for line in lines:
        match = ROADWORK_CURRENT_UNTIL_RE.search(line)
        if match:
            return clean_text(match.group("value"))
    return ""


def decode_parking_csv_bytes(content: bytes) -> str:
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("utf-8-sig", errors="replace")


def parse_parking_csv(text: str) -> list[ParkingGarage]:
    if not text.strip():
        return []
    delimiter = ";" if text.splitlines()[0].count(";") >= text.splitlines()[0].count(",") else ","
    rows = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    garages: list[ParkingGarage] = []
    for row in rows:
        lat = parse_float(row.get("PHI", ""))
        lon = parse_float(row.get("LAMBDA", ""))
        if lat is None or lon is None:
            continue
        name = clean_name(row.get("NAME", ""))
        if not name:
            continue
        garages.append(
            ParkingGarage(
                name=name,
                address=str(row.get("ANSCHRIFT", "")).strip(),
                kind=str(row.get("KAT3", "")).strip(),
                provider=str(row.get("HERKUNFT", "")).strip() or PARKING_ATTRIBUTION,
                lat=lat,
                lon=lon,
            )
        )
    return garages


def parse_float(value: str) -> float | None:
    try:
        return float(str(value).strip().replace(",", "."))
    except ValueError:
        return None


def clean_name(value: str) -> str:
    value = str(value or "").strip()
    value = value.replace("(TG)", "TG").replace("(PH)", "PH").replace("(PP)", "PP")
    return " ".join(value.split())


def normalize_roadwork_period(period: str) -> tuple[str, str]:
    matches = list(ROADWORK_DATE_RE.finditer(period or ""))
    if not matches:
        return "", ""
    start_match = matches[0]
    end_match = matches[-1]
    end_year = end_match.group("year") or start_match.group("year")
    start_year = start_match.group("year") or end_year
    if not start_year or not end_year:
        return "", ""
    start = build_iso_date(start_match.group("day"), start_match.group("month"), start_year)
    end = build_iso_date(end_match.group("day"), end_match.group("month"), end_year)
    return start, end


def build_iso_date(day: str, month: str, year: str) -> str:
    try:
        return date(int(year), int(month), int(day)).isoformat()
    except ValueError:
        return ""


def roadwork_time_status(period: str, today: date | None = None) -> str:
    start_text, end_text = normalize_roadwork_period(period)
    current = today or date.today()
    if "derzeit" in (period or "").casefold() and end_text:
        end = date.fromisoformat(end_text)
        return "aktuell" if current <= end else "abgeschlossen"
    if not start_text or not end_text:
        return "unklar"
    start = date.fromisoformat(start_text)
    end = date.fromisoformat(end_text)
    if start > end:
        return "unklar"
    if start <= current <= end:
        return "aktuell"
    if start > current:
        return "kuenftig"
    return "abgeschlossen"


def mobility_source_summary() -> dict:
    return {
        "parking": {
            "dataset_url": PARKING_DATASET_URL,
            "download_url": PARKING_CSV_URL,
            "license": PARKING_LICENSE,
            "attribution": PARKING_ATTRIBUTION,
            "availability_status": "unbekannt",
            "reuse": "direkte Nutzung im Open-Source-Projekt mit Namensnennung möglich",
        },
        "pharmacies": {
            "dataset_url": OSM_COPYRIGHT_URL,
            "license": "ODbL",
            "attribution": "OpenStreetMap-Mitwirkende",
            "official_search_url": APOTHEKEN_SEARCH_URL,
            "reuse": "OSM-Standorte mit ODbL-Namensnennung nutzbar; Nachtdienste nur offiziell verlinken",
        },
        "doctors": {
            "dataset_url": OSM_COPYRIGHT_URL,
            "license": "ODbL",
            "attribution": "OpenStreetMap-Mitwirkende",
            "official_search_url": ORDINATIONEN_ST_URL,
            "reuse": "OSM-Ordinationsstandorte mit ODbL-Namensnennung nutzbar; Ordinationszeiten und Bereitschaftsdienste nur offiziell verlinken",
        },
        "civic_services": civic_service_summary(),
        "roadworks": {
            "info_url": ROADWORKS_INFO_URL,
            "office_url": ROADWORKS_OFFICE_URL,
            "license": "öffentliche Webseite, keine OGD-Lizenz gefunden",
            "reuse": "aktuelle Webseite nur zur lokalen Anzeige laden oder verlinken; keinen statischen Datensatz ins Repository legen",
            "note": ROADWORKS_USAGE_NOTE,
        },
        "traffic_data_audit": TRAFFIC_DATA_SOURCES,
    }


def write_mobility_source_summary(path: Path) -> dict:
    summary = mobility_source_summary()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary
