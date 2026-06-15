from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .parser import AgendaRecord, build_record_id, extract_amounts, extract_location_details, make_snippet
from .question_pdf import extract_pdf_page_lines, read_question_hour_source


AGENDA_ITEM_RE = re.compile(r"^(?P<number>\d{1,3})\)\s+(?P<body>.+)$")
AGENDA_BUSINESS_RE = re.compile(
    r"^(?P<business>"
    r"[A-ZÄÖÜ]{1,5}\s*\d+"
    r"(?:\s*/\s*[A-ZÄÖÜ]{1,8}\s*[-–—]?\s*\d+/\d{4}(?:\s*[-–—]\s*\d+)?)?"
    r"(?:\s*[-–—]\s*[A-ZÄÖÜ]{1,5}\s*\d+/\d{4}(?:\s*[-–—]\s*\d+)?)?"
    r")\s+(?P<title>.+)$"
)
GERMAN_MONTHS = {
    "jänner": "01",
    "jaenner": "01",
    "januar": "01",
    "februar": "02",
    "märz": "03",
    "maerz": "03",
    "april": "04",
    "mai": "05",
    "juni": "06",
    "juli": "07",
    "august": "08",
    "september": "09",
    "oktober": "10",
    "november": "11",
    "dezember": "12",
}


@dataclass(frozen=True)
class ArchiveAgendaBlock:
    number: int
    body: str
    page: int = 0
    reporter: str = ""


def parse_archive_agenda_pdf(path: Path, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_agenda_lines(extract_pdf_page_lines(path), path.name, source_url=source_url)


def parse_archive_agenda_text(text: str, source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_agenda_lines([(0, line) for line in text.replace("\r", "\n").splitlines()], source_file, source_url=source_url)


def parse_archive_agenda_lines(page_lines: list[tuple[int, str]], source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    cleaned_lines = [(page, clean_archive_agenda_line(line)) for page, line in page_lines]
    cleaned_lines = [(page, line) for page, line in cleaned_lines if line]
    meeting_date = archive_agenda_meeting_date(cleaned_lines, source_file)
    blocks = split_archive_agenda_blocks(cleaned_lines)
    records: list[AgendaRecord] = []
    for index, block in enumerate(blocks, start=1):
        business_numbers, title = split_archive_agenda_business_title(block.body)
        location_details = extract_location_details(title)
        records.append(
            AgendaRecord(
                record_id=build_record_id(meeting_date, source_file, "archive_agenda_item", block.number, index),
                record_type="archive_agenda_item",
                source_file=source_file,
                meeting_date=meeting_date,
                section="Tagesordnung aus Archiv-PDF",
                agenda_item_no=block.number,
                business_numbers=business_numbers,
                title=title,
                status="source_available",
                status_text="nur in Tagesordnung belegt",
                result_text="Tagesordnungspunkt aus Archivquelle; ein Beschlussergebnis ist in dieser Quelle nicht belegt.",
                raw_result_text="",
                votes=[],
                amounts=extract_amounts(title, []),
                locations=[str(detail.get("value", "")) for detail in location_details if str(detail.get("value", ""))],
                location_details=location_details,
                source_snippet=make_snippet(block.body, limit=700),
                parser_confidence=archive_agenda_confidence(block, business_numbers, title),
                result_source="archiv",
                source_url=source_url_with_page(source_url, block.page),
                source_page=block.page,
                submitter=block.reporter,
            )
        )
    return records


def split_archive_agenda_blocks(lines: list[tuple[int, str]]) -> list[ArchiveAgendaBlock]:
    blocks: list[ArchiveAgendaBlock] = []
    current_number = 0
    current_page = 0
    current_parts: list[str] = []
    current_reporter = ""
    reporter = ""
    for page, line in lines:
        reporter_match = re.match(r"^Berichterstatter(?:in)?:\s*(?P<name>.+)$", line, flags=re.IGNORECASE)
        if reporter_match:
            reporter = reporter_match.group("name").strip()
            continue
        item_match = AGENDA_ITEM_RE.match(line)
        if item_match:
            if current_number and current_parts:
                blocks.append(
                    ArchiveAgendaBlock(
                        number=current_number,
                        body=" ".join(current_parts).strip(),
                        page=current_page,
                        reporter=current_reporter,
                    )
                )
            current_number = int(item_match.group("number"))
            current_page = page
            current_parts = [item_match.group("body").strip()]
            current_reporter = reporter
            continue
        if current_number and looks_like_archive_agenda_continuation(line):
            current_parts.append(line)
    if current_number and current_parts:
        blocks.append(
            ArchiveAgendaBlock(
                number=current_number,
                body=" ".join(current_parts).strip(),
                page=current_page,
                reporter=current_reporter,
            )
        )
    return [block for block in blocks if clean_archive_agenda_title(block.body)]


def looks_like_archive_agenda_continuation(line: str) -> bool:
    if len(line) > 180:
        return False
    if re.match(r"^(?:Bgm|StR|GR|GRin|Mag|Dr)\.?.{0,90}:\s", line):
        return False
    if re.search(r"\b(?:Meine sehr|Sehr geehrte|Zwischenruf|Applaus)\b", line):
        return False
    return bool(re.search(r"[A-Za-zÄÖÜäöüß]", line))


def split_archive_agenda_business_title(body: str) -> tuple[list[str], str]:
    text = clean_archive_agenda_title(body)
    match = AGENDA_BUSINESS_RE.match(text)
    if not match:
        return [], text
    business = normalize_archive_agenda_business_number(match.group("business"))
    title = clean_archive_agenda_title(match.group("title"))
    return ([business] if business else []), title or text


def clean_archive_agenda_line(line: str) -> str:
    text = re.sub(r"\s+", " ", str(line or "")).strip()
    text = re.sub(r"Gemeinderatssitzung\b.*$", "", text).strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{1,4}", text):
        return ""
    if re.fullmatch(r"T\s*a\s*g\s*e\s*s\s*o\s*r\s*d\s*n\s*u\s*n\s*g", text, re.IGNORECASE):
        return ""
    if re.fullmatch(r"Ö\s*f\s*f\s*e\s*n\s*t\s*l\s*i\s*c\s*h|Nicht\s*öffentlich", text, re.IGNORECASE):
        return ""
    return text


def clean_archive_agenda_title(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" ,;:-")
    text = re.sub(r"Gemeinderatssitzung\b.*$", "", text).strip(" ,;:-")
    return text or "Tagesordnungspunkt aus Archiv-PDF"


def normalize_archive_agenda_business_number(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" ,;:-")
    text = re.sub(r"\s*([–—-])\s*", r" \1 ", text)
    text = re.sub(r"(?<=/\d{4})\s+[–—-]\s+(?=\d)", "-", text)
    text = re.sub(r"\s*/\s*", "/", text)
    return re.sub(r"\s+", " ", text).strip()


def archive_agenda_meeting_date(lines: list[tuple[int, str]], source_file: str) -> str:
    filename_match = re.search(r"(?<!\d)(?P<yy>\d{2})(?P<month>\d{2})(?P<day>\d{2})(?!\d)", source_file)
    if filename_match:
        year = 2000 + int(filename_match.group("yy"))
        month = int(filename_match.group("month"))
        day = int(filename_match.group("day"))
        if 2000 <= year <= 2026 and 1 <= month <= 12 and 1 <= day <= 31:
            return f"{year:04d}-{month:02d}-{day:02d}"
    for _page, line in lines[:12]:
        match = re.search(
            r"(?P<day>\d{1,2})\.\s*(?P<month>[A-Za-zÄÖÜäöüß]+)\s+(?P<year>\d{4})",
            line,
            flags=re.IGNORECASE,
        )
        if not match:
            continue
        month = GERMAN_MONTHS.get(match.group("month").casefold().replace("ä", "ae"))
        if month:
            return f"{match.group('year')}-{month}-{int(match.group('day')):02d}"
    return ""


def source_url_with_page(source_url: str, page: int) -> str:
    if not source_url or page <= 0:
        return source_url
    return f"{source_url.split('#', 1)[0]}#page={page}"


def archive_agenda_confidence(block: ArchiveAgendaBlock, business_numbers: list[str], title: str) -> float:
    score = 0.55
    if block.number:
        score += 0.1
    if business_numbers:
        score += 0.15
    if title and title != "Tagesordnungspunkt aus Archiv-PDF":
        score += 0.15
    if block.reporter:
        score += 0.05
    return min(score, 1.0)


def read_archive_agenda_source(path: Path) -> str:
    return read_question_hour_source(path)
