from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
import importlib
import re

from .archive_agenda_pdf import source_url_with_page
from .parser import AgendaRecord, build_record_id, extract_amounts, extract_location_details, extract_meeting_date, make_snippet
from .question_pdf import extract_pdf_page_lines, normalize_question_line


COMMUNICATION_ITEM_RE = re.compile(r"^(?P<number>\d{1,3})\)\s*(?P<title>.+)$")


@dataclass(frozen=True)
class ArchiveCommunicationBlock:
    number: int
    title: str
    lines: list[str]
    page: int = 0


def parse_archive_communication_pdf(path: Path, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_communication_lines(extract_pdf_page_lines(path), path.name, source_url=source_url)


def parse_archive_communication_pdf_bytes(data: bytes, source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:
        raise RuntimeError("PDF-Extraktion benötigt optional das Paket pypdf.") from exc
    reader = pypdf.PdfReader(BytesIO(data))
    page_lines: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        for raw_line in (page.extract_text() or "").replace("\r", "\n").splitlines():
            line = normalize_question_line(raw_line)
            if line:
                page_lines.append((page_number, line))
    return parse_archive_communication_lines(page_lines, source_file, source_url=source_url)


def parse_archive_communication_text(text: str, source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_communication_lines([(0, line) for line in text.replace("\r", "\n").splitlines()], source_file, source_url=source_url)


def parse_archive_communication_lines(
    page_lines: list[tuple[int, str]], source_file: str, *, source_url: str = ""
) -> list[AgendaRecord]:
    cleaned = [(page, normalize_question_line(line)) for page, line in page_lines]
    cleaned = [(page, line) for page, line in cleaned if line]
    meeting_date = extract_meeting_date([line for _page, line in cleaned], source_file)
    blocks = split_archive_communication_blocks(cleaned)
    records: list[AgendaRecord] = []
    for index, block in enumerate(blocks, start=1):
        body = "\n".join(block.lines)
        location_details = extract_location_details(" ".join([block.title, body]))
        records.append(
            AgendaRecord(
                record_id=build_record_id(meeting_date, source_file, "communication", block.number, index),
                record_type="communication",
                source_file=source_file,
                meeting_date=meeting_date,
                section="Mitteilungen aus Archiv-PDF",
                agenda_item_no=block.number,
                business_numbers=[],
                title=clean_archive_communication_title(block.title, index),
                status="noted",
                status_text="zur Kenntnis genommen",
                result_text="Mitteilung ohne Beschluss.",
                raw_result_text="",
                votes=[],
                amounts=extract_amounts(block.title, block.lines),
                locations=[str(detail.get("value", "")) for detail in location_details if str(detail.get("value", ""))],
                location_details=location_details,
                source_snippet=make_snippet(body, limit=900),
                parser_confidence=0.85 if body else 0.7,
                result_source="archiv",
                source_url=source_url_with_page(source_url, block.page),
                source_page=block.page,
                submitter=archive_communication_submitter(block.lines),
            )
        )
    return records


def split_archive_communication_blocks(lines: list[tuple[int, str]]) -> list[ArchiveCommunicationBlock]:
    blocks: list[ArchiveCommunicationBlock] = []
    current_number = 0
    current_title = ""
    current_page = 0
    current_lines: list[str] = []
    for page, line in lines:
        match = COMMUNICATION_ITEM_RE.match(line)
        if match:
            if current_number and current_title:
                blocks.append(ArchiveCommunicationBlock(current_number, current_title, current_lines, current_page))
            current_number = int(match.group("number"))
            current_title = match.group("title").strip()
            current_page = page
            current_lines = []
            continue
        if current_number and not is_archive_communication_noise(line):
            current_lines.append(line)
    if current_number and current_title:
        blocks.append(ArchiveCommunicationBlock(current_number, current_title, current_lines, current_page))
    return blocks


def is_archive_communication_noise(line: str) -> bool:
    normalized = re.sub(r"\s+", " ", str(line or "")).strip().casefold()
    if not normalized:
        return True
    if normalized.startswith("gemeinderatssitzung vom "):
        return True
    if normalized == "mitteilungen des bürgermeisters":
        return True
    return False


def clean_archive_communication_title(value: str, index: int) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip(" .,:;-")
    return title or f"Mitteilung {index}"


def archive_communication_submitter(lines: list[str]) -> str:
    for line in lines[:6]:
        match = re.match(r"^(?P<speaker>Bgm(?:\.|in)?[^:]{0,90}|Bürgermeister(?:in)?[^:]{0,90})\s*:", line, re.IGNORECASE)
        if match:
            return re.sub(r"\s+", " ", match.group("speaker")).strip()
    return ""
