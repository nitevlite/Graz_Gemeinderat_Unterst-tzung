from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import csv
import io
import json
import re
from urllib.request import urlopen

from bs4 import BeautifulSoup
import requests


PARKING_CSV_URL = "https://data.graz.gv.at/graz/wp-content/uploads/2024/06/Parkgaragen.csv"
PARKING_DATASET_URL = "https://www.data.gv.at/katalog/dataset/92183c55-442b-405d-9046-d19b07ffc83a"
PARKING_LICENSE = "CC BY 4.0"
PARKING_ATTRIBUTION = "Stadt Graz - data.graz.gv.at"
ROADWORKS_INFO_URL = "https://www.graz.at/cms/beitrag/10295878/8115447/Baustelleninformation.html"
ROADWORKS_OFFICE_URL = "https://www.graz.at/cms/beitrag/10028253/7755789/Baustellen_in_Graz.html"
ROADWORKS_USAGE_NOTE = (
    "Die offiziellen Baustellen-Geodaten sind als Geoportal-Online-Service beschrieben, nicht als OGD-Datensatz. "
    "Die lokale HTML-Ansicht lädt deshalb nur aktuelle, öffentliche Baustelleninfos aus graz.at bzw. aus dem lokalen Cache."
)
ROADWORK_LOCATION_RE = re.compile(
    r"\b(?:straße|strasse|gasse|weg|platz|ring|gürtel|guertel|kai|allee|brücke|bruecke|lände|laende|graben|ufer)\b",
    re.IGNORECASE,
)
ROADWORK_PERIOD_RE = re.compile(r"\b(?:Termin|Zeitraum)\s*:?\s*(?P<value>.+)", re.IGNORECASE)


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
    project: str = ""
    source: str = "Stadt Graz - Baustellen in Graz"
    source_url: str = ROADWORKS_OFFICE_URL
    license: str = "öffentliche Webseite, keine OGD-Lizenz gefunden"


def load_parking_garages(cache_path: Path | None = None, url: str = PARKING_CSV_URL) -> tuple[list[dict], dict]:
    errors: list[str] = []
    text = ""
    if cache_path and cache_path.exists():
        text = cache_path.read_text(encoding="utf-8-sig")
    else:
        try:
            with urlopen(url, timeout=5) as response:  # noqa: S310 - fixed public OGD URL by default
                text = response.read().decode("utf-8-sig")
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
        roadworks.append(
            RoadworkInfo(
                title=title,
                location=title,
                description="; ".join(description_lines),
                period=period,
                project=project,
            )
        )
    return roadworks


def looks_like_roadwork_location(value: str) -> bool:
    return bool(ROADWORK_LOCATION_RE.search(value))


def clean_text(value: str) -> str:
    return " ".join(str(value or "").replace("\xa0", " ").split())


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
        "roadworks": {
            "info_url": ROADWORKS_INFO_URL,
            "office_url": ROADWORKS_OFFICE_URL,
            "license": "öffentliche Webseite, keine OGD-Lizenz gefunden",
            "reuse": "aktuelle Webseite nur zur lokalen Anzeige laden oder verlinken; keinen statischen Datensatz ins Repository legen",
            "note": ROADWORKS_USAGE_NOTE,
        },
    }


def write_mobility_source_summary(path: Path) -> dict:
    summary = mobility_source_summary()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return summary
