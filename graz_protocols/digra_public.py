from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import re
import time
from typing import Callable
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, NavigableString


BASE_URL = "https://digra.graz.at/"
REQUEST_TIMEOUT = 45
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = 2.0
DEFAULT_FALLBACK_YEARS = 4
LABEL_PREFIXES = (
    "dienststelle",
    "regierungsmitglied",
    "antragsteller",
    "antragsteller:in",
    "antragsteller:in(nen)",
)
DATE_RE = re.compile(r"\b(\d{1,2}\.\d{1,2}\.\d{4})\b")
MEETING_DATE_RE = re.compile(r"gemeinderatssitzung\s+am\s+(\d{1,2}\.\d{1,2}\.\d{4})", re.IGNORECASE)


@dataclass(frozen=True)
class Entry:
    href: str
    desc_blocks: list[list[str]]


@dataclass(frozen=True)
class MeetingOption:
    number: str
    date: str
    title: str
    url: str


@dataclass(frozen=True)
class Block:
    tag: BeautifulSoup
    lines: list[str]
    is_entry: bool
    text_norm: str


def list_recent_meetings(
    log_cb: Callable[[str], None] | None = None,
    timetable_range: tuple[str, str] | None = None,
    fallback_years: int = DEFAULT_FALLBACK_YEARS,
    limit: int = 12,
) -> list[MeetingOption]:
    log = log_cb or (lambda _: None)
    session = requests.Session()
    session.headers.update({"User-Agent": "GrazCouncilProtocolExplorer/1.0 (+https://digra.graz.at)"})
    urls: list[str] = []
    if timetable_range:
        urls.append(build_timetable_url(*timetable_range))
    else:
        urls.append(urljoin(BASE_URL, "timetable"))
        start_year = current_cycle_start_year(date.today())
        for offset in range(0, max(0, int(fallback_years)) + 1):
            urls.append(build_timetable_url(*build_cycle_range(start_year - offset)))

    meetings: list[MeetingOption] = []
    seen_urls: set[str] = set()
    for url in urls:
        if len(meetings) >= limit:
            break
        log(f"Lade Sitzungen von {url} ...")
        soup = fetch_soup(session, url, log_cb=log_cb)
        for link in soup.find_all("a", href=True):
            option = parse_meeting_link(link)
            if option is None or option.url in seen_urls:
                continue
            seen_urls.add(option.url)
            meetings.append(option)
            if len(meetings) >= limit:
                break
    return meetings


def parse_meeting_link(link: BeautifulSoup) -> MeetingOption | None:
    text = normalize_label(link.get_text(" ", strip=True))
    title_attr = normalize_label(link.get("title", ""))
    context_text = ""
    parent = link.find_parent(["tr", "li", "p", "div"])
    if parent:
        context_text = normalize_label(parent.get_text(" ", strip=True))
    combined = normalize_label(f"{text} {title_attr} {context_text}")
    match = re.search(r"\b(\d+)\.\s*Gemeinderatssitzung\b", combined, re.IGNORECASE)
    if not match:
        return None
    date_match = DATE_RE.search(combined)
    return MeetingOption(
        number=match.group(1),
        date=date_match.group(1) if date_match else "",
        title=title_attr or text or f"{match.group(1)}. Gemeinderatssitzung",
        url=urljoin(BASE_URL, link["href"]),
    )


def fetch_soup(session: requests.Session, url: str, log_cb: Callable[[str], None] | None = None) -> BeautifulSoup:
    response = request_with_retries(session, url, log_cb=log_cb)
    return BeautifulSoup(response.text, "html.parser")


def get_panel_for_tab(soup: BeautifulSoup, tab_title: str) -> BeautifulSoup | None:
    for link in soup.select("ul.ui-tabs-nav a"):
        text = normalize_label(link.get_text(" ", strip=True))
        if text.lower() != tab_title.lower():
            continue
        panel_id = link.get("aria-controls")
        if not panel_id:
            href = link.get("href", "")
            panel_id = href.lstrip("#") if href.startswith("#") else href
        if panel_id:
            panel = soup.find(id=panel_id)
            if panel:
                return panel
    return None


def extract_entries_in_order(panel: BeautifulSoup) -> list[Entry]:
    preview = panel.select_one("div.preview")
    if preview:
        return extract_entries_from_preview(preview)
    if panel.select("p.default"):
        return [parse_p_entry(tag) for tag in panel.select("p.default") if is_p_default_entry(tag)]
    return []


def extract_entries_from_preview(preview: BeautifulSoup) -> list[Entry]:
    inner = BeautifulSoup(preview.decode_contents(), "html.parser")
    body = inner.body or inner
    raw_blocks = [tag for tag in body.find_all(["div", "p"], recursive=True) if is_leaf_block(tag)]
    blocks: list[Block] = []
    for tag in raw_blocks:
        lines = normalize_lines(tag.get_text("\n", strip=True))
        if not lines:
            continue
        blocks.append(
            Block(
                tag=tag,
                lines=lines,
                is_entry=is_entry_block(tag),
                text_norm=normalize_label(" ".join(lines)),
            )
        )

    entries: list[Entry] = []
    current: Entry | None = None
    skip_mode = False
    related_type: str | None = None
    for block in blocks:
        if block.is_entry:
            if skip_mode and not is_primary_entry_block(block.tag):
                continue
            if skip_mode and is_primary_entry_block(block.tag):
                skip_mode = False
            if related_type and is_primary_entry_block(block.tag):
                related_type = None
            link = block.tag.find("a", href=True)
            desc_blocks: list[list[str]] = []
            inline_lines = extract_inline_lines_from_entry_block(block.tag)
            if related_type and not is_primary_entry_block(block.tag):
                desc_blocks.append([related_type])
                if inline_lines:
                    desc_blocks.append([f"Betreff: {normalize_label(' '.join(inline_lines))}"])
            elif inline_lines:
                desc_blocks.append(inline_lines)
            current = Entry(href=urljoin(BASE_URL, link["href"]), desc_blocks=desc_blocks)
            entries.append(current)
            continue

        if block.text_norm.lower().startswith("bezug zu stück"):
            skip_mode = True
            related_type = None
            continue
        possible_related_type = related_entry_type_from_header(block.text_norm)
        if possible_related_type:
            related_type = possible_related_type
            continue
        if skip_mode or current is None:
            continue
        current.desc_blocks.append(block.lines)
    return entries


def related_entry_type_from_header(text: str) -> str | None:
    lowered = text.lower()
    if lowered.startswith("zusatzanträge"):
        return "Zusatzantrag"
    if lowered.startswith("abänderungsanträge"):
        return "Abänderungsantrag"
    return None


def is_leaf_block(tag: BeautifulSoup) -> bool:
    return tag.name in {"div", "p"} and not tag.find(["div", "p"], recursive=False)


def is_entry_block(tag: BeautifulSoup) -> bool:
    if not is_leaf_block(tag) or "Einlagezahl" not in tag.get_text():
        return False
    link = tag.find("a", href=True)
    return bool(link and "document" in link["href"])


def has_code_bold(tag: BeautifulSoup) -> bool:
    for bold in tag.find_all("b"):
        if bold.find("a") is not None or bold.find_parent("a") is not None:
            continue
        code = bold.get_text(strip=True)
        if code and code.lower() != "einlagezahl":
            return True
    return False


def is_primary_entry_block(tag: BeautifulSoup) -> bool:
    return is_entry_block(tag) and has_code_bold(tag)


def extract_inline_lines_from_entry_block(tag: BeautifulSoup) -> list[str]:
    link = tag.find("a", href=True)
    if not link:
        return []
    container = link.parent if link.parent and link.parent.name == "b" else link
    lines: list[str] = []
    for node in container.next_siblings:
        text = str(node) if isinstance(node, NavigableString) else node.get_text("\n", strip=True)
        if text:
            lines.extend(normalize_lines(text))
    return lines


def is_p_default_entry(tag: BeautifulSoup) -> bool:
    if tag.name != "p" or "default" not in tag.get("class", []):
        return False
    if "Einlagezahl" not in tag.get_text():
        return False
    link = tag.find("a", href=True)
    return bool(link and "document" in link["href"])


def parse_p_entry(tag: BeautifulSoup) -> Entry:
    link = tag.find("a", href=True)
    lines = normalize_lines(tag.get_text("\n"))
    start_index = 0
    for index, line in enumerate(lines):
        if "Einlagezahl" in line:
            start_index = index + 1
            break
    desc_blocks: list[list[str]] = []
    index = start_index
    while index < len(lines):
        line = lines[index]
        if line.lower().startswith("betreff:"):
            block = [line]
            next_index = index + 1
            while next_index < len(lines) and not is_label_line(lines[next_index]):
                block.append(lines[next_index])
                next_index += 1
            desc_blocks.append(block)
            index = next_index
            continue
        desc_blocks.append([line])
        index += 1
    return Entry(href=urljoin(BASE_URL, link["href"]), desc_blocks=desc_blocks)


def extract_meeting_date(soup: BeautifulSoup) -> str | None:
    if soup.title:
        title_text = soup.title.get_text(" ", strip=True)
        match = MEETING_DATE_RE.search(title_text) or DATE_RE.search(title_text)
        if match:
            return match.group(1)
    text = soup.get_text(" ", strip=True)
    match = MEETING_DATE_RE.search(text) or DATE_RE.search(text)
    return match.group(1) if match else None


def current_cycle_start_year(today: date) -> int:
    return today.year if (today.month, today.day) >= (2, 1) else today.year - 1


def build_cycle_range(start_year: int) -> tuple[str, str]:
    return (f"{start_year}-02-01", f"{start_year + 1}-01-31")


def build_timetable_url(from_date: str, to_date: str) -> str:
    return urljoin(BASE_URL, f"timetable?from={from_date}&to={to_date}")


def is_label_line(line: str) -> bool:
    lowered = line.lower().strip()
    return any(lowered.startswith(prefix) for prefix in LABEL_PREFIXES)


def normalize_lines(text: str) -> list[str]:
    lines: list[str] = []
    for raw in text.splitlines():
        cleaned = raw.replace("\xa0", " ").strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def normalize_label(text: str) -> str:
    return " ".join(str(text or "").replace("\xa0", " ").split())


def request_with_retries(
    session: requests.Session,
    url: str,
    log_cb: Callable[[str], None] | None = None,
) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = session.get(url, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            if log_cb:
                log_cb(f"Netzwerkfehler (Versuch {attempt}/{MAX_RETRIES}) bei {url}: {exc}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_BACKOFF_SECONDS * attempt)
    raise last_exc if last_exc else RuntimeError(f"Request fehlgeschlagen: {url}")
