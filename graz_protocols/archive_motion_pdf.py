from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import importlib
import re

from .archive_agenda_pdf import source_url_with_page
from .date_utils import parse_compact_public_date
from .parser import (
    AgendaRecord,
    build_record_id,
    extract_amounts,
    extract_location_details,
    make_snippet,
    normalize_written_submission_status,
)
from .question_pdf import extract_pdf_page_lines


MOTION_TITLE_RE = re.compile(r"^(?:Betrifft|Betreff|Betr\.)\s*:?\s*(?P<title>.+)$", re.IGNORECASE)
MEETING_DATE_RE = re.compile(r"\b(?P<day>\d{1,2})\s*\.\s*(?P<month>\d{1,2})\s*\.\s*(?P<year>\d{4})\b")
SUBMITTER_PATTERNS = [
    re.compile(r"^eingebracht\s+von\s+(?P<name>.+)$", re.IGNORECASE),
    re.compile(r"^von\s+(?P<name>(?:GR(?:in)?\.?|Klubobfrau|Klubobmann|Gemeinderat|Gemeinderätin).+)$", re.IGNORECASE),
    re.compile(r"^Gemeinderat\s*:\s*(?P<name>.+)$", re.IGNORECASE),
    re.compile(r"^(?P<name>(?:GR(?:in)?\.?|Klubobfrau|Klubobmann|Gemeinderat|Gemeinderätin)[^:]{2,120}?)\s+stellt\b", re.IGNORECASE),
    re.compile(r"^(?P<name>GR(?:in)?\.?\s+.+?)\s+\d{1,2}\.\s*\d{1,2}\.\s*\d{4}$", re.IGNORECASE),
]
START_MARKER_RE = re.compile(
    r"(?:"
    r"Abänderungsantrag\b|Abaenderungsantrag\b|"
    r"Dringlich(?:er|keits)\s+Antrag\b|"
    r"G\s+E\s+M\s+E\s+I\s+N\s+S\s+A\s+M\s+E\s+R\s+A\s+N\s+T\s+R\s+A\s+G"
    r")",
    re.IGNORECASE,
)
BODY_STOP_RE = re.compile(
    r"^(?:Sehr geehrte|Liebe Kolleginnen|Der Gemeinderat möge|Der Gemeinderat wolle|Namens|Ich stelle|In diesem Sinne)",
    re.IGNORECASE,
)
NUMBERED_MOTION_RE = re.compile(r"^(?P<number>\d{1,3})\)\s*(?P<title>.+)$")


@dataclass(frozen=True)
class ArchiveMotionBlock:
    lines: list[str]
    page: int = 0


def parse_archive_motion_pdf(path: Path, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_motion_lines(extract_pdf_page_lines(path), path.name, source_url=source_url)


def parse_archive_motion_pdf_bytes(data: bytes, source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:
        raise RuntimeError("PDF-Extraktion benötigt optional das Paket pypdf.") from exc
    reader = pypdf.PdfReader(BytesIO(data))
    page_lines: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        for raw_line in (page.extract_text() or "").replace("\r", "\n").splitlines():
            line = clean_motion_line(raw_line)
            if line:
                page_lines.append((page_number, line))
    return parse_archive_motion_lines(page_lines, source_file, source_url=source_url)


def parse_archive_motion_text(text: str, source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_motion_lines([(0, line) for line in text.replace("\r", "\n").splitlines()], source_file, source_url=source_url)


def parse_archive_motion_lines(page_lines: list[tuple[int, str]], source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    normalized = normalize_motion_page_lines(page_lines)
    meeting_date = archive_motion_meeting_date(normalized, source_file)
    blocks = split_archive_motion_blocks(normalized)
    records: list[AgendaRecord] = []
    for index, block in enumerate(blocks, start=1):
        title = archive_motion_title(block.lines, index)
        body = "\n".join(block.lines)
        record_type = archive_motion_record_type(block.lines, source_file)
        status, status_text, raw_result_text = normalize_written_submission_status(record_type, "unknown", "", "")
        if status == "unknown":
            status = "source_available"
            status_text = "Quelle verfügbar"
            raw_result_text = ""
        result_text = "Antragstext aus Archivquelle; ein Beschlussergebnis ist in dieser Quelle nicht belegt."
        location_details = extract_location_details(body)
        records.append(
            AgendaRecord(
                record_id=build_record_id(meeting_date, source_file, record_type, index, index),
                record_type=record_type,
                source_file=source_file,
                meeting_date=meeting_date,
                section=archive_motion_section(record_type),
                agenda_item_no=index,
                business_numbers=[],
                title=title,
                status=status,
                status_text=status_text,
                result_text=result_text if status == "source_available" else "Verfahren: zugewiesen",
                raw_result_text=raw_result_text,
                votes=[],
                amounts=extract_amounts(title, block.lines),
                locations=[str(detail.get("value", "")) for detail in location_details if str(detail.get("value", ""))],
                location_details=location_details,
                source_snippet=make_snippet(body, limit=900),
                parser_confidence=archive_motion_confidence(block.lines, title),
                result_source="archiv",
                source_url=source_url_with_page(source_url, block.page),
                source_page=block.page,
                submitter=archive_motion_submitter(block.lines),
            )
        )
    return records


def normalize_motion_page_lines(page_lines: list[tuple[int, str]]) -> list[tuple[int, str]]:
    result: list[tuple[int, str]] = []
    for page, raw_line in page_lines:
        line = clean_motion_line(raw_line)
        if not line:
            continue
        result.extend(split_embedded_motion_starts(page, line))
    return result


def split_embedded_motion_starts(page: int, line: str) -> list[tuple[int, str]]:
    matches = [match for match in START_MARKER_RE.finditer(line) if valid_embedded_start(line, match)]
    if not matches:
        return [(page, line)]
    pieces: list[tuple[int, str]] = []
    position = 0
    for match in matches:
        if match.start() > position:
            before = line[position : match.start()].strip(" .")
            if before:
                pieces.append((page, before))
        position = match.start()
    tail = line[position:].strip()
    if tail:
        pieces.append((page, tail))
    return pieces


def valid_embedded_start(line: str, match: re.Match[str]) -> bool:
    if match.start() == 0:
        return True
    prefix = line[: match.start()].rstrip()
    marker = match.group(0).casefold()
    if not prefix.endswith((".", "!", "?")):
        return False
    return marker.startswith(("dringlicher", "dringlichkeits", "d r i n g"))


def clean_motion_line(value: str) -> str:
    text = re.sub(r"\s+", " ", str(value or "").replace("\u0002", "")).strip()
    if not text or re.fullmatch(r"\d{1,4}", text):
        return ""
    return text


def split_archive_motion_blocks(lines: list[tuple[int, str]]) -> list[ArchiveMotionBlock]:
    blocks: list[ArchiveMotionBlock] = []
    current: list[str] = []
    current_page = 0
    seen_motion_language = False
    for page, line in lines:
        is_start = is_motion_start_line(line)
        is_title_start = bool(MOTION_TITLE_RE.match(line))
        is_numbered_start = bool(NUMBERED_MOTION_RE.match(line))
        if (is_start or is_title_start or is_numbered_start) and current and has_motion_title(current):
            if seen_motion_language:
                blocks.append(ArchiveMotionBlock(current, current_page))
                current = []
                seen_motion_language = False
        if (is_start or is_title_start or is_numbered_start) and not current:
            current_page = page
        if is_numbered_start and not current:
            seen_motion_language = True
        if is_start:
            seen_motion_language = True
        if not current and not is_start and not is_numbered_start and not looks_like_motion_preface(line):
            continue
        current.append(line)
        if not seen_motion_language and is_motion_context_line(line):
            seen_motion_language = True
    if current and seen_motion_language and has_motion_title(current):
        blocks.append(ArchiveMotionBlock(current, current_page))
    return blocks


def is_motion_start_line(line: str) -> bool:
    return bool(START_MARKER_RE.match(line))


def looks_like_motion_preface(line: str) -> bool:
    return bool(MOTION_TITLE_RE.match(line) or re.search(r"\b(?:Gemeinderat|Antrag|DRINGLICHEN BEHANDLUNG)\b", line, re.IGNORECASE))


def is_motion_context_line(line: str) -> bool:
    normalized = line.casefold()
    return "dringlich" in normalized or "antrag" in normalized or "gemeinderat" in normalized


def has_motion_title(lines: list[str]) -> bool:
    return any(MOTION_TITLE_RE.match(line) or NUMBERED_MOTION_RE.match(line) for line in lines)


def archive_motion_title(lines: list[str], index: int) -> str:
    numbered = NUMBERED_MOTION_RE.match(lines[0]) if lines else None
    if numbered:
        title = clean_motion_title_part(numbered.group("title"))
        if title:
            return title
    for line_index, line in enumerate(lines):
        match = MOTION_TITLE_RE.match(line)
        if not match:
            continue
        parts = [clean_motion_title_part(match.group("title"))]
        for follow in lines[line_index + 1 : line_index + 4]:
            if not follow or MOTION_TITLE_RE.match(follow) or is_motion_start_line(follow) or BODY_STOP_RE.match(follow):
                break
            if MEETING_DATE_RE.search(follow) or archive_motion_submitter([follow]):
                break
            if re.search(
                r"\b(?:eingebracht|Sitzung|Gemeinderat|Sehr geehrte)\b|^(?:Der Bürgermeister|Die zuständigen|Der Gemeinderat)\b",
                follow,
                re.IGNORECASE,
            ):
                break
            if len(follow) <= 90 and continues_motion_title(parts[-1], follow):
                parts.append(clean_motion_title_part(follow))
                continue
            break
        title = clean_motion_title_part(" ".join(parts))
        if title:
            return title
    return f"Archiv-Antrag {index}"


def clean_motion_title_part(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip(" .,:;-!?")


def continues_motion_title(previous: str, follow: str) -> bool:
    previous_clean = previous.rstrip()
    follow_clean = follow.strip()
    if previous_clean.endswith(("/", "-", "–", "—")):
        return True
    if re.match(r"^(?:und|oder|am|im|in|zur|zum|von|bei)\b", follow_clean, re.IGNORECASE):
        return True
    return bool(follow_clean and follow_clean[0].islower())


def archive_motion_record_type(lines: list[str], source_file: str) -> str:
    text = f"{source_file} {' '.join(lines[:8])}".casefold()
    if "abänderungsantrag" in text or "abaenderungsantrag" in text:
        return "amendment_motion"
    if "dringlich" in text:
        return "urgent_motion"
    return "written_motion"


def archive_motion_section(record_type: str) -> str:
    return {
        "amendment_motion": "Abänderungsanträge aus Archiv-PDF",
        "urgent_motion": "Dringlichkeitsanträge aus Archiv-PDF",
        "written_motion": "Anträge aus Archiv-PDF",
    }.get(record_type, "Anträge aus Archiv-PDF")


def archive_motion_submitter(lines: list[str]) -> str:
    for line in lines[:12]:
        for pattern in SUBMITTER_PATTERNS:
            match = pattern.match(line)
            if match:
                return clean_submitter(match.group("name"))
    return ""


def clean_submitter(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" .,:;-")
    text = re.sub(r"^(?:Herrn?|Frau)\s+", "", text, flags=re.IGNORECASE)
    return text


def archive_motion_meeting_date(lines: list[tuple[int, str]], source_file: str) -> str:
    filename_match = re.search(r"(?<!\d)(?P<yy>\d{2})(?P<month>\d{2})(?P<day>\d{2})(?!\d)", source_file)
    if filename_match:
        parsed_date = parse_compact_public_date(
            filename_match.group("yy"),
            filename_match.group("month"),
            filename_match.group("day"),
        )
        if parsed_date:
            return parsed_date
    for _page, line in lines[:30]:
        match = MEETING_DATE_RE.search(line)
        if match:
            return f"{match.group('year')}-{int(match.group('month')):02d}-{int(match.group('day')):02d}"
    return ""


def archive_motion_confidence(lines: list[str], title: str) -> float:
    score = 0.45
    if title and not title.startswith("Archiv-Antrag"):
        score += 0.2
    if archive_motion_submitter(lines):
        score += 0.15
    if any("gemeinderat" in line.casefold() for line in lines[:12]):
        score += 0.1
    if any("dringlich" in line.casefold() for line in lines[:12]):
        score += 0.1
    return min(score, 1.0)
