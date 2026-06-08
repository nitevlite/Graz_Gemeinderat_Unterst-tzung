from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json
import re
from typing import Iterable, Protocol


class ParagraphLike(Protocol):
    text: str
    style: str
    index: int


AGENDA_RE = re.compile(
    r"^(?:(?P<section_no>\d+(?:\.\d+)*)\s+)?Stk\.?\s*(?P<item_no>\d+)\)\s*(?P<body>.+)$",
    re.IGNORECASE,
)
TO_RE = re.compile(r"^TO\s*(?P<item_no>\d+)\s*:\s*(?P<body>.+)$", re.IGNORECASE)
MEETING_DATE_IN_TEXT_RE = re.compile(
    r"(?:Sitzung|Gemeinderates?|Gemeinderatssitzung)[^\n]{0,80}?\bam\s+"
    r"(?P<date>\d{1,2}\s*\.\s*\d{1,2}\s*\.\s*\d{4})",
    re.IGNORECASE,
)
ISO_DATE_IN_FILENAME_RE = re.compile(r"\b(?P<date>\d{4}-\d{2}-\d{2})\b")
BUSINESS_NO_RE = re.compile(
    r"\b(?:"
    r"Präs\.?|Praes\.?|"
    r"AB|"
    r"A\s*\d+(?:\s*/\s*\d+)?|A\d+(?:/\d+)?"
    r")\s*(?:[-–]\s*)?\d{3,}(?:\s*/\s*\d{1,4}){0,3}(?:\s*[-–]\s*\d{1,4})?",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(
    r"€\s*\d[\d.\s]*(?:,\s*(?:\d{1,2}|-+))?",
    re.IGNORECASE,
)
LOCATION_RE = re.compile(
    r"\b[\wÄÖÜäöüß.-]+(?:straße|strasse|gasse|weg|platz|park|brücke|bruecke|allee|kai|ufer)\b"
    r"|\bKG\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+"
    r"|\bGdst\.?\s*Nr\.?\s*[\d/]+",
    re.IGNORECASE,
)
REPORTER_RE = re.compile(r"\((?:Berichterstatter(?:in)?|GR|KlObm|KlObf)[^)]+\)")
TRAILING_PAGE_RE = re.compile(r"\t\d{1,4}$")

SECTION_HEADINGS = {
    "mitteilungen": "Mitteilungen",
    "fragestunde": "Fragestunde",
    "tagesordnung": "Tagesordnung",
    "dringlichkeitsanträge": "Dringlichkeitsanträge",
    "dringlichkeitsantraege": "Dringlichkeitsanträge",
    "anfragen (schriftlich)": "Anfragen (schriftlich)",
    "anträge (schriftlich)": "Anträge (schriftlich)",
    "antraege (schriftlich)": "Anträge (schriftlich)",
}

STATUS_PATTERNS = [
    ("assigned", re.compile(r"geschäftsordnungsmäßigen Behandlung zugewiesen", re.IGNORECASE)),
    ("accepted_unanimous", re.compile(r"einstimmig angenommen", re.IGNORECASE)),
    ("accepted_majority", re.compile(r"mehrheitlich angenommen", re.IGNORECASE)),
    ("rejected_majority", re.compile(r"mehrheitlich abgelehnt", re.IGNORECASE)),
    ("accepted", re.compile(r"\bangenommen\b", re.IGNORECASE)),
    ("rejected", re.compile(r"\babgelehnt\b", re.IGNORECASE)),
    ("postponed", re.compile(r"\bvertagt\b", re.IGNORECASE)),
]


@dataclass(frozen=True)
class AgendaRecord:
    record_id: str
    record_type: str
    source_file: str
    meeting_date: str
    section: str
    agenda_item_no: int
    business_numbers: list[str]
    title: str
    status: str
    status_text: str
    amounts: list[str]
    locations: list[str]
    source_snippet: str
    parser_confidence: float

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def parse_protocol(paragraphs: Iterable[str | ParagraphLike], source_file: str) -> list[AgendaRecord]:
    blocks = normalize_blocks(paragraphs)
    meeting_date = extract_meeting_date((block.text for block in blocks), source_file)
    chunks = list(iter_record_chunks(blocks))
    seen: set[tuple[str, int, str, str]] = set()
    records: list[AgendaRecord] = []

    for chunk in chunks:
        if chunk.is_toc:
            continue
        item_no = chunk.item_no
        heading_body = chunk.heading_body
        title = extract_title(heading_body)
        key = (chunk.record_type, item_no, chunk.section, title.casefold())
        if key in seen:
            continue
        seen.add(key)

        chunk_text = "\n".join([chunk.heading, *chunk.body])
        status, status_text = classify_status(chunk_text)
        business_numbers = unique_preserve_order(
            normalize_business_number(match.group(0))
            for match in BUSINESS_NO_RE.finditer(heading_body)
        )
        amounts = unique_preserve_order(normalize_amount(match.group(0)) for match in AMOUNT_RE.finditer(chunk_text))
        locations = unique_preserve_order(match.group(0).strip() for match in LOCATION_RE.finditer(chunk_text))
        confidence = score_confidence(business_numbers, status, title)
        record_id = build_record_id(meeting_date, source_file, chunk.record_type, item_no, len(records) + 1)
        records.append(
            AgendaRecord(
                record_id=record_id,
                record_type=chunk.record_type,
                source_file=source_file,
                meeting_date=meeting_date,
                section=chunk.section,
                agenda_item_no=item_no,
                business_numbers=business_numbers,
                title=title,
                status=status,
                status_text=status_text,
                amounts=amounts,
                locations=locations,
                source_snippet=make_snippet(chunk_text),
                parser_confidence=confidence,
            )
        )
    return records


@dataclass(frozen=True)
class AgendaChunk:
    section: str
    heading: str
    heading_body: str
    item_no: int
    record_type: str
    is_toc: bool
    body: list[str]


@dataclass(frozen=True)
class ParserParagraph:
    text: str
    style: str = ""
    index: int = 0

    @property
    def is_heading(self) -> bool:
        return self.style.casefold().startswith("heading")

    @property
    def is_toc(self) -> bool:
        return self.style.casefold().startswith("toc")


def normalize_blocks(paragraphs: Iterable[str | ParagraphLike]) -> list[ParserParagraph]:
    blocks: list[ParserParagraph] = []
    for index, paragraph in enumerate(paragraphs):
        if isinstance(paragraph, str):
            blocks.append(ParserParagraph(text=paragraph, index=index))
        else:
            blocks.append(
                ParserParagraph(
                    text=paragraph.text,
                    style=getattr(paragraph, "style", ""),
                    index=getattr(paragraph, "index", index),
                )
            )
    return blocks


def iter_record_chunks(paragraphs: Iterable[ParserParagraph]) -> Iterable[AgendaChunk]:
    current_section = ""
    current_chunk: AgendaChunk | None = None
    current_body: list[str] = []
    generic_counts: dict[str, int] = {}

    for paragraph in paragraphs:
        heading = normalize_heading(paragraph.text)
        section = detect_section(heading)
        if section and paragraph.is_heading:
            if current_chunk is not None:
                yield with_body(current_chunk, current_body)
            current_chunk = None
            current_body = []
            current_section = section
            continue
        elif section:
            current_section = section

        parsed = parse_agenda_heading(heading)
        if parsed is not None:
            if current_chunk is not None:
                yield with_body(current_chunk, current_body)
            item_no, heading_body = parsed
            current_chunk = AgendaChunk(
                section=current_section,
                heading=heading,
                heading_body=heading_body,
                item_no=item_no,
                record_type="agenda_item",
                is_toc=paragraph.is_toc or looks_like_toc_entry(paragraph.text),
                body=[],
            )
            current_body = []
            continue

        generic_type = generic_record_type(current_section)
        if paragraph.is_heading and generic_type:
            if current_chunk is not None:
                yield with_body(current_chunk, current_body)
            generic_counts[current_section] = generic_counts.get(current_section, 0) + 1
            current_chunk = AgendaChunk(
                section=current_section,
                heading=heading,
                heading_body=heading,
                item_no=generic_counts[current_section],
                record_type=generic_type,
                is_toc=paragraph.is_toc,
                body=[],
            )
            current_body = []
            continue

        if current_chunk is not None:
            current_body.append(heading)

    if current_chunk is not None:
        yield with_body(current_chunk, current_body)


def with_body(chunk: AgendaChunk, body: list[str]) -> AgendaChunk:
    return AgendaChunk(
        section=chunk.section,
        heading=chunk.heading,
        heading_body=chunk.heading_body,
        item_no=chunk.item_no,
        record_type=chunk.record_type,
        is_toc=chunk.is_toc,
        body=list(body),
    )


def generic_record_type(section: str) -> str:
    return {
        "Dringlichkeitsanträge": "urgent_motion",
        "Anfragen (schriftlich)": "written_question",
        "Anträge (schriftlich)": "written_motion",
    }.get(section, "")


def parse_agenda_heading(value: str) -> tuple[int, str] | None:
    for pattern in (AGENDA_RE, TO_RE):
        match = pattern.match(value)
        if match:
            return int(match.group("item_no")), match.group("body").strip()
    return None


def detect_section(value: str) -> str:
    normalized = value.strip().casefold()
    normalized = re.sub(r"^\d+(?:\.\d+)*\s+", "", normalized)
    return SECTION_HEADINGS.get(normalized, "")


def looks_like_toc_entry(value: str) -> bool:
    return bool(TRAILING_PAGE_RE.search(value)) and "\t" in value


def normalize_heading(value: str) -> str:
    value = re.sub(r"[ \r\f\v]+", " ", value).strip()
    return value


def extract_meeting_date(paragraphs: Iterable[str], source_file: str) -> str:
    filename_match = ISO_DATE_IN_FILENAME_RE.search(source_file)
    if filename_match:
        return filename_match.group("date")
    for paragraph in paragraphs:
        match = MEETING_DATE_IN_TEXT_RE.search(paragraph)
        if match:
            return normalize_date(match.group("date"))
    return ""


def normalize_date(value: str) -> str:
    parts = [part.strip().zfill(2) for part in value.split(".")]
    if len(parts) == 3:
        return f"{parts[2]}-{parts[1]}-{parts[0]}"
    return value.strip()


def extract_title(heading_body: str) -> str:
    title = BUSINESS_NO_RE.sub(" ", heading_body)
    title = REPORTER_RE.sub(" ", title)
    title = re.sub(r"^\s*[,;]\s*", "", title)
    title = re.sub(r"\s+", " ", title).strip(" ,;")
    return title


def classify_status(text: str) -> tuple[str, str]:
    for status, pattern in STATUS_PATTERNS:
        match = pattern.search(text)
        if match:
            return status, match.group(0)
    return "unknown", ""


def normalize_business_number(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    value = re.sub(r"\s*/\s*", "/", value)
    value = re.sub(r"\s*[-–]\s*", "-", value)
    value = re.sub(r"^praes", "Präs", value, flags=re.IGNORECASE)
    value = re.sub(r"^präs\.?", "Präs.", value, flags=re.IGNORECASE)
    return value


def normalize_amount(value: str) -> str:
    value = re.sub(r"\s+", " ", value.strip())
    value = value.replace(" ,", ",")
    value = re.sub(r",\s*-+", ",-", value)
    return value


def unique_preserve_order(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        cleaned = value.strip()
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(cleaned)
    return result


def make_snippet(text: str, limit: int = 600) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def score_confidence(business_numbers: list[str], status: str, title: str) -> float:
    score = 0.45
    if business_numbers:
        score += 0.2
    if status != "unknown":
        score += 0.2
    if len(title) >= 8:
        score += 0.15
    return min(score, 1.0)


def build_record_id(meeting_date: str, source_file: str, record_type: str, item_no: int, ordinal: int) -> str:
    stem = Path(source_file).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    date_part = meeting_date or "unknown-date"
    type_part = re.sub(r"[^a-z0-9]+", "-", record_type.lower()).strip("-") or "record"
    return f"{date_part}-{type_part}-{item_no}-{ordinal}-{stem}"
