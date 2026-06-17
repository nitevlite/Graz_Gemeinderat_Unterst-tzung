from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace
import hashlib
from email.utils import parsedate_to_datetime
from pathlib import Path
import json
import re
from urllib.parse import unquote, urljoin
import xml.etree.ElementTree as ET

from bs4 import BeautifulSoup
import requests

from .parser import AgendaRecord


ARCHIVE_URL = "https://www.graz.at/cms/beitrag/10142612/7768104"
LEGACY_ARCHIVE_URL = "https://www.graz.at/cms/beitrag/10134085/7768145/Gemeinderat_ArchivNachlese.html"
RSS_URL = "https://www.graz.at/rss"


@dataclass(frozen=True)
class CityArchiveLink:
    meeting_date: str
    title: str
    url: str


@dataclass(frozen=True)
class CityMeetingPage:
    meeting_date: str
    title: str
    url: str
    source_url: str


@dataclass(frozen=True)
class CityArchiveAsset:
    meeting_date: str
    title: str
    url: str
    source_url: str
    kind: str


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    published: str
    description: str


def enrich_records_with_city_links(
    records: list[AgendaRecord],
    *,
    archive_url: str = ARCHIVE_URL,
    cache_path: Path | None = None,
) -> tuple[list[AgendaRecord], dict]:
    from dataclasses import replace

    links = load_or_fetch_archive_links(archive_url=archive_url, cache_path=cache_path)
    links_by_date = best_links_by_date(links)
    enriched: list[AgendaRecord] = []
    applied = 0
    for record in records:
        link = links_by_date.get(record.meeting_date)
        if link and not record.source_url:
            applied += 1
            enriched.append(replace(record, source_url=link.url))
        else:
            enriched.append(record)
    return enriched, {"city_archive_links_total": len(links), "city_archive_links_applied": applied}


def load_or_fetch_archive_links(*, archive_url: str = ARCHIVE_URL, cache_path: Path | None = None) -> list[CityArchiveLink]:
    if cache_path and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        return [CityArchiveLink(**item) for item in payload.get("links", [])]
    links = fetch_archive_links(archive_url)
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps({"archive_url": archive_url, "links": [link.__dict__ for link in links]}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return links


def fetch_archive_links(archive_url: str = ARCHIVE_URL) -> list[CityArchiveLink]:
    response = requests.get(archive_url, timeout=20)
    response.raise_for_status()
    return parse_archive_links(response.text, archive_url)


def fetch_city_meeting_pages(
    *,
    archive_url: str = ARCHIVE_URL,
    legacy_archive_url: str = LEGACY_ARCHIVE_URL,
    limit_pages: int = 40,
) -> list[CityMeetingPage]:
    pages_to_scan = [archive_url, legacy_archive_url]
    scanned: set[str] = set()
    meetings: list[CityMeetingPage] = []
    while pages_to_scan and len(scanned) < limit_pages:
        page_url = pages_to_scan.pop(0)
        if page_url in scanned:
            continue
        scanned.add(page_url)
        try:
            response = requests.get(page_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue
        soup = BeautifulSoup(response.text, "html.parser")
        for anchor in soup.find_all("a"):
            href = anchor.get("href")
            label = anchor.get_text(" ", strip=True)
            if not href or not label:
                continue
            url = urljoin(page_url, href)
            if "graz.at/cms/beitrag/" not in url:
                continue
            if annual_archive_label(label) and url not in scanned and url not in pages_to_scan:
                pages_to_scan.append(url)
            meeting_date = meeting_date_from_anchor(anchor, label)
            if meeting_date and meeting_page_label(label):
                meetings.append(
                    CityMeetingPage(
                        meeting_date=meeting_date,
                        title=label,
                        url=url,
                        source_url=page_url,
                    )
                )
    return unique_meeting_pages(meetings)


def write_city_meeting_index(output_path: Path) -> dict:
    pages, errors = fetch_city_meeting_pages_with_errors()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"source": ARCHIVE_URL, "legacy_source": LEGACY_ARCHIVE_URL, "pages": [page.__dict__ for page in pages], "errors": errors},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    years = sorted({page.meeting_date[:4] for page in pages})
    return {"city_meeting_pages": len(pages), "years": years, "output": str(output_path), "errors": errors}


def write_city_archive_asset_index(output_path: Path, input_index: Path | None = None, limit: int = 0) -> dict:
    pages, errors = read_city_meeting_index(input_index) if input_index else fetch_city_meeting_pages_with_errors()
    if limit > 0:
        pages = pages[:limit]
    assets = fetch_city_archive_assets(pages)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            {"source": ARCHIVE_URL, "legacy_source": LEGACY_ARCHIVE_URL, "assets": [asset.__dict__ for asset in assets], "errors": errors},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    kinds = Counter(asset.kind for asset in assets)
    years = sorted({asset.meeting_date[:4] for asset in assets if asset.meeting_date})
    return {
        "city_archive_assets": len(assets),
        "city_meeting_pages_scanned": len(pages),
        "kinds": dict(kinds),
        "document_types": dict(kinds),
        "years": years,
        "output": str(output_path),
        "errors": errors,
    }


def read_city_archive_asset_index(input_path: Path) -> tuple[list[CityArchiveAsset], list[dict[str, str]]]:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    assets = [
        CityArchiveAsset(
            meeting_date=str(asset.get("meeting_date", "")),
            title=str(asset.get("title", "")),
            url=str(asset.get("url", "")),
            source_url=str(asset.get("source_url", "")),
            kind=str(asset.get("kind", "")),
        )
        for asset in payload.get("assets", [])
    ]
    errors = payload.get("errors", [])
    return assets, errors if isinstance(errors, list) else []


def city_archive_assets_to_records(assets: list[CityArchiveAsset], *, extract_documents: bool = False) -> list[AgendaRecord]:
    records: list[AgendaRecord] = []
    for index, asset in enumerate(unique_assets(assets), start=1):
        if extract_documents and is_extractable_archive_question_hour_asset(asset):
            extracted = extract_archive_question_hour_asset_records(asset)
            if extracted:
                records.extend(extracted)
                continue
        if extract_documents and is_extractable_archive_agenda_asset(asset):
            extracted = extract_archive_agenda_asset_records(asset)
            if extracted:
                records.extend(extracted)
                continue
        if extract_documents and is_extractable_archive_communication_asset(asset):
            extracted = extract_archive_communication_asset_records(asset)
            if extracted:
                records.extend(extracted)
                continue
        if extract_documents and is_extractable_archive_motion_asset(asset):
            extracted = extract_archive_motion_asset_records(asset)
            if extracted:
                records.extend(extracted)
                continue
        if extract_documents and is_extractable_archive_question_asset(asset):
            extracted = extract_archive_question_asset_records(asset)
            if extracted:
                records.extend(extracted)
                continue
        kind_label = archive_asset_kind_label(asset.kind)
        title = archive_asset_record_title(asset)
        records.append(
            AgendaRecord(
                record_id=city_archive_asset_record_id(asset, index),
                record_type=archive_asset_record_type(asset),
                source_file="Stadt-Graz-Archiv",
                meeting_date=asset.meeting_date,
                section="Stadt-Graz-Archiv",
                agenda_item_no=index,
                business_numbers=[],
                title=title,
                status="source_available",
                status_text="Quelle verfügbar",
                result_text="Archivquelle: verfügbar",
                raw_result_text="",
                votes=[],
                amounts=[],
                locations=[],
                source_snippet=f"{kind_label} aus der Stadt-Graz-Archivseite.",
                parser_confidence=0.7 if asset.kind == "protocol_document" else 0.55,
                result_source="archiv",
                source_url=asset.url,
            )
        )
    return records


def is_extractable_archive_motion_asset(asset: CityArchiveAsset) -> bool:
    if not is_archive_pdf_asset(asset):
        return False
    normalized = f"{asset.title} {asset.url}".casefold()
    return "dringliche" in normalized or "antraege" in normalized or "anträge" in normalized


def is_extractable_archive_question_asset(asset: CityArchiveAsset) -> bool:
    if not is_archive_pdf_asset(asset):
        return False
    normalized = f"{asset.title} {asset.url}".casefold()
    return "anfragen" in normalized


def is_extractable_archive_question_hour_asset(asset: CityArchiveAsset) -> bool:
    if not is_archive_pdf_asset(asset):
        return False
    normalized = f"{asset.title} {asset.url}".casefold()
    return "fragestunde" in normalized


def is_extractable_archive_agenda_asset(asset: CityArchiveAsset) -> bool:
    if not is_archive_pdf_asset(asset):
        return False
    normalized = f"{asset.title} {asset.url}".casefold()
    return "tagesordnung" in normalized


def is_extractable_archive_communication_asset(asset: CityArchiveAsset) -> bool:
    if not is_archive_pdf_asset(asset):
        return False
    normalized = f"{asset.title} {asset.url}".casefold()
    return "mitteilungen" in normalized


def is_archive_pdf_asset(asset: CityArchiveAsset) -> bool:
    path = asset.url.split("?", 1)[0].split("#", 1)[0].casefold()
    return asset.kind in {"archive_document", "protocol_document"} and path.endswith(".pdf")


def extract_archive_motion_asset_records(asset: CityArchiveAsset) -> list[AgendaRecord]:
    from .archive_motion_pdf import parse_archive_motion_pdf_bytes

    try:
        response = requests.get(asset.url, timeout=30)
        response.raise_for_status()
        records = parse_archive_motion_pdf_bytes(response.content, Path(asset.url.split("?", 1)[0]).name, source_url=asset.url)
    except Exception:  # pylint: disable=broad-except
        return []
    return records


def extract_archive_question_asset_records(asset: CityArchiveAsset) -> list[AgendaRecord]:
    from .archive_question_pdf import parse_archive_question_pdf_bytes

    try:
        response = requests.get(asset.url, timeout=30)
        response.raise_for_status()
        records = parse_archive_question_pdf_bytes(response.content, Path(asset.url.split("?", 1)[0]).name, source_url=asset.url)
    except Exception:  # pylint: disable=broad-except
        return []
    return records


def extract_archive_question_hour_asset_records(asset: CityArchiveAsset) -> list[AgendaRecord]:
    from .question_pdf import parse_question_hour_pdf_bytes

    try:
        response = requests.get(asset.url, timeout=30)
        response.raise_for_status()
        source_file = Path(asset.url.split("?", 1)[0]).name
        records = parse_question_hour_pdf_bytes(response.content, source_file)
    except Exception:  # pylint: disable=broad-except
        return []
    return [replace(record, result_source="archiv", source_url=record.source_url or asset.url) for record in records]


def extract_archive_agenda_asset_records(asset: CityArchiveAsset) -> list[AgendaRecord]:
    from .archive_agenda_pdf import parse_archive_agenda_pdf

    try:
        response = requests.get(asset.url, timeout=30)
        response.raise_for_status()
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as handle:
            handle.write(response.content)
            temp_path = Path(handle.name)
        try:
            records = parse_archive_agenda_pdf(temp_path, source_url=asset.url)
        finally:
            temp_path.unlink(missing_ok=True)
    except Exception:  # pylint: disable=broad-except
        return []
    return records


def extract_archive_communication_asset_records(asset: CityArchiveAsset) -> list[AgendaRecord]:
    from .archive_communication_pdf import parse_archive_communication_pdf_bytes

    try:
        response = requests.get(asset.url, timeout=30)
        response.raise_for_status()
        records = parse_archive_communication_pdf_bytes(response.content, Path(asset.url.split("?", 1)[0]).name, source_url=asset.url)
    except Exception:  # pylint: disable=broad-except
        return []
    return records


def clean_archive_asset_title(title: str, kind_label: str) -> str:
    text = re.sub(r"\s+", " ", title).strip(" :-")
    prefix = re.escape(kind_label)
    text = re.sub(rf"^{prefix}\s*:\s*", "", text, flags=re.IGNORECASE).strip()
    return text or kind_label or "Archivquelle"


def archive_asset_record_type(asset: CityArchiveAsset) -> str:
    if is_attendance_asset(asset.title, asset.url):
        return "attendance_list"
    return "archive_source"


def archive_asset_record_title(asset: CityArchiveAsset) -> str:
    title = clean_archive_asset_title(asset.title, archive_asset_kind_label(asset.kind))
    improved = archive_asset_title_from_url(asset.url, title)
    return improved or title


def is_attendance_asset(title: str, url: str) -> bool:
    return "anwesenheits" in f"{title} {url}".casefold()


def archive_asset_title_from_url(url: str, fallback: str = "") -> str:
    filename = Path(url.split("?", 1)[0].split("#", 1)[0]).name
    decoded = unquote(filename)
    stem = Path(decoded).stem
    normalized = re.sub(r"[_%-]+", " ", stem).casefold()
    date = archive_asset_date_label(stem)
    part = archive_asset_part_label(stem)
    if "anwesenheits" in normalized:
        return f"Anwesenheitsliste{date}".strip()
    if "antwort" in normalized and ("fs" in normalized or "fragestunde" in normalized):
        suffix = archive_asset_person_suffix(stem)
        return f"Antwort zur Fragestunde{date}{suffix}".strip()
    if "dringliche" in normalized:
        result = " mit Abstimmungsergebnissen" if "abstimmung" in fallback.casefold() else ""
        return f"Dringlichkeitsanträge{date}{part}{result}".strip()
    if "fragestunde" in normalized or re.search(r"\bfs\d{6}", normalized):
        return f"Fragestunde{date}{part}".strip()
    if "antraege" in normalized or "anträge" in fallback.casefold():
        return f"Schriftliche Anträge{date}{part}".strip()
    if "tagesordnung" in normalized:
        return f"Tagesordnung{date}{part}".strip()
    return ""


def archive_asset_date_label(value: str) -> str:
    match = re.search(r"(?<!\d)(?P<date>\d{6})(?!\d)", value)
    if not match:
        return ""
    raw = match.group("date")
    year, month, day = raw[:2], raw[2:4], raw[4:]
    return f" vom {day}.{month}.20{year}"


def archive_asset_part_label(value: str) -> str:
    normalized = unquote(value).casefold()
    match = re.search(r"(\d+)\s*von\s*(\d+)", normalized)
    if match:
        return f" (Teil {match.group(1)} von {match.group(2)})"
    match = re.search(r"(?:antraege|anträge|dringliche|fragestunde)(\d+)\b", normalized)
    if match:
        return f" (Teil {match.group(1)})"
    return ""


def archive_asset_person_suffix(value: str) -> str:
    cleaned = re.sub(r"\.[^.]+$", "", value)
    parts = [part for part in re.split(r"[_\s-]+", cleaned) if part]
    if not parts:
        return ""
    person = parts[-1]
    if person.casefold() in {"antwort", "fs"} or re.search(r"\d", person):
        return ""
    return f" ({person})"


def archive_asset_kind_label(kind: str) -> str:
    return {
        "meeting_overview": "Sitzungsübersicht",
        "archive_document": "Archivdokument",
        "protocol_document": "Protokolldokument",
        "protocol_page": "Protokollseite",
    }.get(kind, kind or "Archivquelle")


def city_archive_asset_record_id(asset: CityArchiveAsset, index: int) -> str:
    digest = hashlib.sha1(asset.url.encode("utf-8")).hexdigest()[:12]
    date = asset.meeting_date or "unknown-date"
    return f"{date}-city-archive-{asset.kind or 'asset'}-{index}-{digest}"


def read_city_meeting_index(input_index: Path | None) -> tuple[list[CityMeetingPage], list[dict[str, str]]]:
    if input_index is None or not input_index.exists():
        return fetch_city_meeting_pages_with_errors()
    payload = json.loads(input_index.read_text(encoding="utf-8"))
    pages = [
        CityMeetingPage(
            meeting_date=str(page.get("meeting_date", "")),
            title=str(page.get("title", "")),
            url=str(page.get("url", "")),
            source_url=str(page.get("source_url", "")),
        )
        for page in payload.get("pages", [])
    ]
    errors = payload.get("errors", [])
    return pages, errors if isinstance(errors, list) else []


def fetch_city_archive_assets(pages: list[CityMeetingPage]) -> list[CityArchiveAsset]:
    assets: list[CityArchiveAsset] = []
    for page in pages:
        try:
            response = requests.get(page.url, timeout=20)
            response.raise_for_status()
        except requests.RequestException:
            continue
        assets.extend(parse_city_archive_assets(response.text, page))
    return unique_assets(assets)


def parse_city_archive_assets(html: str, page: CityMeetingPage) -> list[CityArchiveAsset]:
    soup = BeautifulSoup(html, "html.parser")
    assets: list[CityArchiveAsset] = []
    for anchor in soup.find_all("a"):
        href = anchor.get("href")
        label = anchor.get_text(" ", strip=True)
        if not href or not label:
            continue
        url = urljoin(page.url, href)
        kind = city_asset_kind(label, url)
        if not kind:
            continue
        meeting_date = asset_meeting_date(anchor, label, url, page.meeting_date)
        assets.append(
            CityArchiveAsset(
                meeting_date=meeting_date,
                title=clean_city_asset_label(label, url),
                url=url,
                source_url=page.url,
                kind=kind,
            )
        )
    return assets


def city_asset_kind(label: str, url: str) -> str:
    normalized = f"{label} {url}".casefold()
    path = url.split("?", 1)[0].split("#", 1)[0].casefold()
    if is_navigation_archive_label(label, url):
        return ""
    if path.endswith((".docx", ".doc")):
        return "protocol_document"
    if path.endswith(".pdf") and any(token in normalized for token in ("protokoll", "wortprotokoll", "fragestunde")):
        return "protocol_document"
    if path.endswith(".pdf"):
        return "archive_document"
    if any(token in normalized for token in ("wortprotokoll", "protokoll")):
        return "protocol_page"
    return ""


def is_navigation_archive_label(label: str, url: str) -> bool:
    normalized = re.sub(r"\s+", " ", label.casefold()).strip()
    if re.fullmatch(r"(?:alt\s*\+\s*)?\d+|20\d{2}", normalized):
        return True
    if normalized in {"kontakt", "feedback an autor", "archiv/nachlese übersicht", "archiv/nachlese uebersicht"}:
        return True
    path = url.split("?", 1)[0].casefold()
    if "cms_nearest" in url and not path.endswith((".pdf", ".doc", ".docx")):
        return True
    return False


def clean_city_asset_label(label: str, url: str) -> str:
    title = re.sub(r"\s+", " ", label).strip()
    if title:
        return title
    return Path(url.split("?", 1)[0]).name


def asset_meeting_date(anchor, label: str, url: str, fallback: str) -> str:
    path_name = Path(url.split("?", 1)[0]).name
    values = [label, path_name]
    parent = anchor.find_parent() if anchor is not None else None
    if parent:
        values.append(parent.get_text(" ", strip=True))
    for value in values:
        match = re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", value)
        if match:
            return normalize_date(match.group(0))
        compact_matches = re.finditer(r"(?<!\d)(?P<a>\d{2})(?P<b>\d{2})(?P<c>\d{2})(?!\d)", value)
        for compact in compact_matches:
            a, b, c = compact.group("a"), compact.group("b"), compact.group("c")
            yymmdd = compact_date(a, b, c)
            ddmmyy = compact_date(c, b, a)
            if compact.start() == 0 and yymmdd:
                return yymmdd
            if yymmdd and int(a) <= 26:
                return yymmdd
            if ddmmyy:
                return ddmmyy
    return fallback


def compact_date(year: str, month: str, day: str) -> str:
    year_int = 2000 + int(year)
    month_int = int(month)
    day_int = int(day)
    if not (2004 <= year_int <= 2026 and 1 <= month_int <= 12 and 1 <= day_int <= 31):
        return ""
    return f"{year_int:04d}-{month}-{day}"


def fetch_city_meeting_pages_with_errors(
    *,
    archive_url: str = ARCHIVE_URL,
    legacy_archive_url: str = LEGACY_ARCHIVE_URL,
    limit_pages: int = 40,
) -> tuple[list[CityMeetingPage], list[dict[str, str]]]:
    pages_to_scan = [archive_url, legacy_archive_url]
    scanned: set[str] = set()
    meetings: list[CityMeetingPage] = []
    errors: list[dict[str, str]] = []
    while pages_to_scan and len(scanned) < limit_pages:
        page_url = pages_to_scan.pop(0)
        if page_url in scanned:
            continue
        scanned.add(page_url)
        try:
            response = requests.get(page_url, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            errors.append({"url": page_url, "error": str(exc)})
            continue
        discovered_pages, discovered_links = parse_city_meeting_page_index(response.text, page_url)
        meetings.extend(discovered_pages)
        for url in discovered_links:
            if url not in scanned and url not in pages_to_scan:
                pages_to_scan.append(url)
    return unique_meeting_pages(meetings), errors


def parse_city_meeting_page_index(html: str, page_url: str) -> tuple[list[CityMeetingPage], list[str]]:
    soup = BeautifulSoup(html, "html.parser")
    meetings: list[CityMeetingPage] = []
    linked_indexes: list[str] = []
    for anchor in soup.find_all("a"):
        href = anchor.get("href")
        label = anchor.get_text(" ", strip=True)
        if not href or not label:
            continue
        url = urljoin(page_url, href)
        if "graz.at/cms/beitrag/" not in url:
            continue
        if annual_archive_label(label):
            linked_indexes.append(url)
        meeting_date = meeting_date_from_anchor(anchor, label)
        if meeting_date and (meeting_page_label(label) or useful_archive_label(label)):
            meetings.append(CityMeetingPage(meeting_date=meeting_date, title=label, url=url, source_url=page_url))
    return meetings, linked_indexes


def parse_archive_links(html: str, base_url: str) -> list[CityArchiveLink]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n")
    dates = set(normalize_date(match.group(0)) for match in re.finditer(r"\b\d{2}\.\d{2}\.\d{4}\b", text))
    links: list[CityArchiveLink] = []
    for anchor in soup.find_all("a"):
        href = anchor.get("href")
        label = anchor.get_text(" ", strip=True)
        if not href or not label:
            continue
        surrounding = anchor.find_parent()
        surrounding_text = surrounding.get_text(" ", strip=True) if surrounding else label
        date_match = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", surrounding_text)
        if not date_match:
            # Fallback: some archive anchors are just the date itself.
            date_match = re.search(r"\b\d{2}\.\d{2}\.\d{4}\b", label)
        if not date_match:
            continue
        meeting_date = normalize_date(date_match.group(0))
        if dates and meeting_date not in dates:
            continue
        if not useful_archive_label(label):
            continue
        links.append(CityArchiveLink(meeting_date=meeting_date, title=label, url=urljoin(base_url, href)))
    return unique_links(links)


def annual_archive_label(label: str) -> bool:
    normalized = label.casefold()
    return bool(re.fullmatch(r"(?:gr-sitzungen\s+)?20\d{2}(?:\s*\(.*\))?", normalized.strip()))


def meeting_page_label(label: str) -> bool:
    normalized = label.casefold()
    return bool(re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", label)) or "gemeinderatssitzung" in normalized


def meeting_date_from_anchor(anchor, label: str) -> str:
    values = [label]
    parent = anchor.find_parent()
    if parent:
        values.append(parent.get_text(" ", strip=True))
    for value in values:
        match = re.search(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b", value)
        if match:
            return normalize_date(match.group(0))
    return ""


def useful_archive_label(label: str) -> bool:
    normalized = label.casefold()
    return any(token in normalized for token in ("übersicht", "uebersicht", "gemeinderat", "berichterstattung", "livestream"))


def best_links_by_date(links: list[CityArchiveLink]) -> dict[str, CityArchiveLink]:
    best: dict[str, CityArchiveLink] = {}
    for link in links:
        current = best.get(link.meeting_date)
        if current is None or archive_rank(link.title) > archive_rank(current.title):
            best[link.meeting_date] = link
    return best


def archive_rank(title: str) -> int:
    normalized = title.casefold()
    if "übersicht" in normalized or "uebersicht" in normalized:
        return 3
    if "gemeinderat" in normalized:
        return 2
    return 1


def fetch_news_items(rss_url: str = RSS_URL) -> list[NewsItem]:
    try:
        response = requests.get(rss_url, timeout=20)
        response.raise_for_status()
        return parse_news_items(response.text)
    except (requests.RequestException, ET.ParseError):
        return []


def parse_news_items(xml_text: str) -> list[NewsItem]:
    root = ET.fromstring(xml_text)
    items: list[NewsItem] = []
    for item in root.findall(".//item"):
        title = text_of(item, "title")
        url = text_of(item, "link")
        description = text_of(item, "description")
        published = normalize_pub_date(text_of(item, "pubDate"))
        if title and url:
            items.append(NewsItem(title=title, url=url, description=description, published=published))
    return items


def enrich_topics_with_news(topics: list[dict], news_items: list[NewsItem], *, limit_per_topic: int = 4) -> list[dict]:
    enriched: list[dict] = []
    for topic in topics:
        query_tokens = topic_news_tokens(topic)
        matches: list[dict] = []
        for item in news_items:
            score = news_score(query_tokens, item)
            if score <= 0:
                continue
            matches.append(
                {
                    "title": item.title,
                    "url": item.url,
                    "published": item.published,
                    "description": item.description,
                    "score": round(score, 3),
                }
            )
        updated = dict(topic)
        updated["news"] = sorted(matches, key=lambda item: (-item["score"], item["published"]))[:limit_per_topic]
        enriched.append(updated)
    return enriched


def topic_news_tokens(topic: dict) -> set[str]:
    values = [str(topic.get("label", "")), str(topic.get("business_number", ""))]
    for record in topic.get("records", []):
        if isinstance(record, dict):
            values.append(str(record.get("title", "")))
    tokens: set[str] = set()
    for value in values:
        normalized = re.sub(r"[^\wÄÖÜäöüß-]+", " ", value.casefold())
        tokens.update(token for token in normalized.split() if len(token) >= 6)
    return tokens


def news_score(tokens: set[str], item: NewsItem) -> float:
    if not tokens:
        return 0.0
    haystack = f"{item.title} {item.description}".casefold()
    hits = sum(1 for token in tokens if token in haystack)
    return hits / max(len(tokens), 1)


def normalize_date(value: str) -> str:
    day, month, year = value.split(".")
    return f"{year}-{month}-{day}"


def normalize_pub_date(value: str) -> str:
    if not value:
        return ""
    try:
        return parsedate_to_datetime(value).date().isoformat()
    except (TypeError, ValueError):
        return value


def text_of(element: ET.Element, tag: str) -> str:
    value = element.findtext(tag)
    return value.strip() if value else ""


def unique_links(links: list[CityArchiveLink]) -> list[CityArchiveLink]:
    seen: set[tuple[str, str]] = set()
    result: list[CityArchiveLink] = []
    for link in links:
        key = (link.meeting_date, link.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(link)
    return result


def unique_meeting_pages(pages: list[CityMeetingPage]) -> list[CityMeetingPage]:
    seen: set[tuple[str, str]] = set()
    result: list[CityMeetingPage] = []
    for page in sorted(pages, key=lambda item: (item.meeting_date, item.title, item.url)):
        key = (page.meeting_date, page.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(page)
    return result


def unique_assets(assets: list[CityArchiveAsset]) -> list[CityArchiveAsset]:
    seen: set[tuple[str, str]] = set()
    result: list[CityArchiveAsset] = []
    for asset in sorted(assets, key=lambda item: (item.meeting_date, item.kind, item.title, item.url)):
        key = (asset.meeting_date, asset.url)
        if key in seen:
            continue
        seen.add(key)
        result.append(asset)
    return result
