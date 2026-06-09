from __future__ import annotations

from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
import json
import re
from urllib.parse import urljoin
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
