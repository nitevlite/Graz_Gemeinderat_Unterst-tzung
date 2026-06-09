from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
import json
import re
from typing import Iterable, Protocol

from .street_names import normalize_street_name


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
STREET_SUFFIX_RE = (
    r"(?:straße|strasse|gasse|weg|platz|park|brücke|bruecke|allee|kai|ufer|ring|"
    r"gürtel|guertel|graben|lände|laende|steig|steg|zeile)"
)
LOCATION_RE = re.compile(
    rf"\b[\wÄÖÜäöüß.-]+{STREET_SUFFIX_RE}\b"
    r"|\bKG\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+"
    r"|\bEZ\s+\d+"
    r"|\bGdst\.?\s*Nr\.?\s*[\d/]+",
    re.IGNORECASE,
)
LOCATION_TYPED_PATTERNS = [
    ("street", re.compile(rf"\b[\wÄÖÜäöüß.-]+{STREET_SUFFIX_RE}\b", re.IGNORECASE)),
    ("place", re.compile(r"\b[\wÄÖÜäöüß.-]+platz\b", re.IGNORECASE)),
    ("park", re.compile(r"\b[\wÄÖÜäöüß.-]+park\b", re.IGNORECASE)),
    ("bridge", re.compile(r"\b[\wÄÖÜäöüß.-]+(?:brücke|bruecke)\b", re.IGNORECASE)),
    ("cadastral_municipality", re.compile(r"\bKG\s+[A-ZÄÖÜ][\wÄÖÜäöüß.-]+", re.IGNORECASE)),
    ("land_register", re.compile(r"\bEZ\s+\d+", re.IGNORECASE)),
    ("parcel", re.compile(r"\bGdst\.?\s*Nr\.?\s*[\d/]+", re.IGNORECASE)),
]
REPORTER_RE = re.compile(r"\((?:Berichterstatter(?:in)?|GR|KlObm|KlObf)[^)]+\)")
REPORTER_DETAIL_RE = re.compile(r"\((?P<role>Berichterstatter(?:in)?|GR|KlObm|KlObf)\s*:?\s*(?P<name>[^)]+)\)")
MOTION_AUTHOR_RE = re.compile(
    r"\b(?P<name>(?:GR(?:in)?\.?|Gemeinderätin|Gemeinderat|KlObm|KlObf)[^:\n]{2,120}?)\s+stellt\s+"
    r"(?:folgenden|folgende|den)\s+(?:dringlichen\s+)?(?:Antrag|Anfrage)",
    re.IGNORECASE,
)
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
    ("accepted_majority", re.compile(r"mehr(?:heitlich|stimmig) angenommen", re.IGNORECASE)),
    ("rejected_majority", re.compile(r"mehr(?:heitlich|stimmig) abgelehnt", re.IGNORECASE)),
    ("accepted", re.compile(r"\bangenommen\b", re.IGNORECASE)),
    ("rejected", re.compile(r"\babgelehnt\b", re.IGNORECASE)),
    ("postponed", re.compile(r"\bvertagt\b", re.IGNORECASE)),
]
FORMAL_RESULT_RE = re.compile(
    r"(?:"
    r"Der\s+(?:Antrag|Abänderungsantrag|Abaenderungsantrag|Zusatzantrag|Tagesordnungspunkt)"
    r"[^.\n]{0,240}?\b(?:angenommen|abgelehnt|zugewiesen|vertagt)"
    r"(?:\s*\((?:Gegen|Dagegen|Zustimmung|Enthaltung)\s*:?\s*[^)]{1,220}\))?\.?"
    r"|Der\s+geschäftsordnungsmäßigen\s+Behandlung\s+zugewiesen\.?"
    r")",
    re.IGNORECASE,
)
RESULT_DETAIL_RE = re.compile(
    r"^(?:Zustimmung|Dagegen|Gegen|Enthaltung|Gegenstimmen?|Gegenprobe)\s*:?",
    re.IGNORECASE,
)
AMOUNT_SCOPE_START_RE = re.compile(
    r"(?:folgender\s+(?:Antrag|Anfrage)\s+gestellt|Der\s+Gemeinderat\s+wolle\s+beschließen)",
    re.IGNORECASE,
)
RESULT_SUBJECT_RE = re.compile(
    r"Der\s+(?P<subject>Antrag|Abänderungsantrag|Abaenderungsantrag|Zusatzantrag|Tagesordnungspunkt)",
    re.IGNORECASE,
)
RESULT_OUTCOME_RE = re.compile(
    r"\b(?P<modifier>einstimmig|mehrheitlich|mehrstimmig)?\s*(?P<decision>angenommen|abgelehnt|zugewiesen|vertagt)\b",
    re.IGNORECASE,
)
PARTY_DETAIL_RE = re.compile(
    r"^(?P<label>Zustimmung|Dagegen|Gegen|Enthaltung|Gegenstimmen?)\s*:?\s*(?P<parties>.+)$",
    re.IGNORECASE,
)
PAREN_PARTY_DETAIL_RE = re.compile(
    r"\((?P<label>Zustimmung|Dagegen|Gegen|Enthaltung|Gegenstimmen?)\s*:?\s*(?P<parties>[^)]+)\)",
    re.IGNORECASE,
)
SUBJECT_LABELS = {
    "motion": "Antrag",
    "amendment": "Abänderungsantrag",
    "additional_motion": "Zusatzantrag",
    "agenda_item": "Tagesordnungspunkt",
    "procedure": "Verfahren",
}
OUTCOME_LABELS = {
    "accepted_unanimous": "einstimmig angenommen",
    "accepted_majority": "mehrheitlich angenommen",
    "accepted": "angenommen",
    "rejected_majority": "mehrheitlich abgelehnt",
    "rejected": "abgelehnt",
    "assigned": "zugewiesen",
    "postponed": "vertagt",
    "unknown": "unbekannt",
}


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
    result_text: str
    raw_result_text: str
    votes: list[dict[str, object]]
    amounts: list[str]
    locations: list[str]
    source_snippet: str
    parser_confidence: float
    location_details: list[dict[str, object]] = field(default_factory=list)
    result_source: str = "protokoll"
    digra_url: str = ""
    digra_business_number: str = ""
    protocol_result_text: str = ""
    digra_match_score: float = 0.0
    source_url: str = ""
    submitter: str = ""

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, sort_keys=True)


def parse_protocol(
    paragraphs: Iterable[str | ParagraphLike], source_file: str, street_names: set[str] | None = None
) -> list[AgendaRecord]:
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
        submitter = extract_submitter(chunk_text)
        raw_result_text = extract_result_text(chunk_text)
        status, status_text = classify_status(raw_result_text or chunk_text)
        votes = extract_votes(raw_result_text, status)
        result_text = format_result_text(votes, status, status_text)
        business_numbers = unique_preserve_order(
            normalize_business_number(match.group(0))
            for match in BUSINESS_NO_RE.finditer(heading_body)
        )
        amounts = extract_amounts(heading_body, chunk.body)
        title_location_details = extract_location_details(heading_body, street_names=street_names)
        location_details = title_location_details or extract_location_details(
            location_context_text(heading_body, chunk.body),
            street_names=street_names,
        )
        locations = unique_preserve_order(str(location["value"]) for location in location_details)
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
                result_text=result_text,
                raw_result_text=raw_result_text,
                votes=votes,
                amounts=amounts,
                locations=locations,
                location_details=location_details,
                source_snippet=make_snippet(chunk_text),
                parser_confidence=confidence,
                submitter=submitter,
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


def extract_submitter(text: str) -> str:
    reporter_match = REPORTER_DETAIL_RE.search(text)
    if reporter_match:
        role = reporter_match.group("role").strip()
        name = normalize_submitter_name(reporter_match.group("name"))
        if name:
            return f"{role}: {name}"

    author_match = MOTION_AUTHOR_RE.search(text)
    if author_match:
        return normalize_submitter_name(author_match.group("name"))
    return ""


def normalize_submitter_name(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip(" .,:;")
    value = re.sub(r"^(?:Frau|Herr)\s+", "", value, flags=re.IGNORECASE)
    return value


def classify_status(text: str) -> tuple[str, str]:
    for status, pattern in STATUS_PATTERNS:
        match = pattern.search(text)
        if match:
            return status, match.group(0)
    return "unknown", ""


def extract_result_text(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    result_lines: list[str] = []
    for index, line in enumerate(lines):
        matches = [match.group(0).strip() for match in FORMAL_RESULT_RE.finditer(line)]
        if not matches:
            continue
        result_lines.extend(matches)
        for follow in lines[index + 1 : index + 4]:
            if RESULT_DETAIL_RE.match(follow):
                result_lines.append(follow)
                continue
            break
    if not result_lines:
        return ""
    return "\n".join(unique_preserve_order(result_lines))


def extract_votes(result_text: str, status: str = "unknown") -> list[dict[str, object]]:
    if not result_text:
        return []
    lines = [line.strip() for line in result_text.splitlines() if line.strip()]
    votes: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    for line in lines:
        subject_match = RESULT_SUBJECT_RE.search(line)
        outcome_match = RESULT_OUTCOME_RE.search(line)
        if subject_match and outcome_match:
            if current is not None:
                votes.append(current)
            current = {
                "subject": normalize_subject(subject_match.group("subject")),
                "outcome": normalize_vote_outcome(outcome_match.group("modifier") or "", outcome_match.group("decision")),
                "approval": [],
                "against": [],
                "abstention": [],
                "raw_text": line,
            }
            for label, parties in extract_party_details_from_line(line):
                apply_vote_parties(current, label, parties)
            continue
        detail_match = PARTY_DETAIL_RE.match(line)
        if detail_match and current is not None:
            apply_vote_parties(current, detail_match.group("label"), detail_match.group("parties"))
            current["raw_text"] = f"{current['raw_text']}\n{line}"
    if current is not None:
        votes.append(current)
    if not votes and status == "assigned":
        return [
            {
                "subject": "procedure",
                "outcome": "assigned",
                "approval": [],
                "against": [],
                "abstention": [],
                "raw_text": result_text,
            }
        ]
    return votes


def format_result_text(votes: list[dict[str, object]], status: str, status_text: str) -> str:
    if votes:
        return "\n\n".join(format_vote(vote) for vote in votes)
    if status == "assigned":
        return "Zugewiesen"
    if status == "unknown":
        return "Unbekannt"
    return normalize_status_label(status, status_text)


def format_vote(vote: dict[str, object]) -> str:
    subject = SUBJECT_LABELS.get(str(vote.get("subject", "")), "Antrag")
    outcome = OUTCOME_LABELS.get(str(vote.get("outcome", "")), str(vote.get("outcome", "")) or "unbekannt")
    lines = [f"{subject}: {outcome}"]
    approval = vote.get("approval")
    against = vote.get("against")
    abstention = vote.get("abstention")
    if isinstance(approval, list) and approval:
        lines.append(f"Zustimmung: {', '.join(str(item) for item in approval)}")
    if isinstance(against, list) and against:
        lines.append(f"Dagegen: {', '.join(str(item) for item in against)}")
    if isinstance(abstention, list) and abstention:
        lines.append(f"Enthaltung: {', '.join(str(item) for item in abstention)}")
    return "\n".join(lines)


def normalize_status_label(status: str, status_text: str = "") -> str:
    return OUTCOME_LABELS.get(status, status_text or status)


def extract_party_details_from_line(line: str) -> list[tuple[str, str]]:
    return [(match.group("label"), match.group("parties")) for match in PAREN_PARTY_DETAIL_RE.finditer(line)]


def apply_vote_parties(vote: dict[str, object], label: str, parties: str) -> None:
    normalized_label = label.casefold()
    target = "approval"
    if normalized_label in {"dagegen", "gegen", "gegenstimmen"}:
        target = "against"
    elif normalized_label == "enthaltung":
        target = "abstention"
    existing = vote.get(target)
    if not isinstance(existing, list):
        existing = []
    merged = unique_preserve_order([*existing, *split_party_names(parties)])
    vote[target] = merged


def split_party_names(value: str) -> list[str]:
    cleaned = value.strip().strip(".;")
    if not cleaned:
        return []
    pieces = re.split(r"\s*,\s*|\s+und\s+", cleaned)
    return [piece.strip().strip(".;") for piece in pieces if piece.strip().strip(".;")]


def normalize_subject(value: str) -> str:
    normalized = value.casefold()
    if normalized in {"abänderungsantrag", "abaenderungsantrag"}:
        return "amendment"
    if normalized == "zusatzantrag":
        return "additional_motion"
    if normalized == "tagesordnungspunkt":
        return "agenda_item"
    return "motion"


def normalize_vote_outcome(modifier: str, decision: str) -> str:
    mod = modifier.casefold()
    dec = decision.casefold()
    if dec == "zugewiesen":
        return "assigned"
    if dec == "vertagt":
        return "postponed"
    if dec == "angenommen":
        if mod == "einstimmig":
            return "accepted_unanimous"
        if mod in {"mehrheitlich", "mehrstimmig"}:
            return "accepted_majority"
        return "accepted"
    if dec == "abgelehnt":
        if mod in {"mehrheitlich", "mehrstimmig"}:
            return "rejected_majority"
        return "rejected"
    return dec


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


def extract_amounts(heading_body: str, body: list[str]) -> list[str]:
    scoped_texts = [heading_body]
    marker_seen = False
    for line in body:
        if FORMAL_RESULT_RE.search(line):
            break
        if AMOUNT_SCOPE_START_RE.search(line):
            marker_seen = True
            scoped_texts.append(line)
            continue
        if marker_seen:
            scoped_texts.append(line)
    return unique_preserve_order(
        normalize_amount(match.group(0)) for text in scoped_texts for match in AMOUNT_RE.finditer(text)
    )


def extract_location_details(text: str, street_names: set[str] | None = None) -> list[dict[str, object]]:
    details: list[dict[str, object]] = []
    seen: set[tuple[str, str]] = set()
    for location_type, pattern in LOCATION_TYPED_PATTERNS:
        for match in pattern.finditer(text):
            value = match.group(0).strip()
            if street_names is not None and location_type not in {"street", "place", "park", "bridge"}:
                continue
            if street_names is not None:
                if normalize_street_name(value) not in street_names:
                    continue
            key = (location_type, value.casefold())
            if key in seen:
                continue
            seen.add(key)
            details.append(
                {
                    "type": location_type,
                    "value": value,
                    "context": make_context(text, match.start(), match.end()),
                    "confidence": 0.9 if location_type in {"parcel", "land_register", "cadastral_municipality"} else 0.75,
                }
            )
    if street_names is not None:
        for value, start, end in find_street_names_in_text(text, street_names):
            key = ("street", value.casefold())
            if key in seen:
                continue
            seen.add(key)
            details.append(
                {
                    "type": "street",
                    "value": value,
                    "context": make_context(text, start, end),
                    "confidence": 0.8,
                }
            )
    return details


def location_context_text(heading_body: str, body: list[str], limit: int = 1600) -> str:
    texts = [heading_body]
    total = len(heading_body)
    for line in body:
        if FORMAL_RESULT_RE.search(line):
            break
        if any(pattern.search(line) for _, pattern in STATUS_PATTERNS):
            break
        texts.append(line)
        total += len(line)
        if total >= limit:
            break
    return "\n".join(texts)


def find_street_names_in_text(text: str, street_names: set[str]) -> list[tuple[str, int, int]]:
    street_names = {normalize_street_name(name) for name in street_names}
    normalized_to_display: dict[str, str] = {}
    for value in re.findall(rf"\b[\wÄÖÜäöüß.-]+{STREET_SUFFIX_RE}\b", text, re.IGNORECASE):
        normalized = normalize_street_name(value)
        if normalized in street_names:
            normalized_to_display[normalized] = value.strip()
    for match in re.finditer(
        r"\b[A-ZÄÖÜ][\wÄÖÜäöüß.-]+(?:\s+[A-ZÄÖÜa-zäöüß][\wÄÖÜäöüß.-]+){1,4}"
        rf"{STREET_SUFFIX_RE}?\b",
        text,
    ):
        words = match.group(0).strip().split()
        for start_index in range(len(words)):
            value = " ".join(words[start_index:])
            normalized = normalize_street_name(value)
            if normalized in street_names:
                normalized_to_display[normalized] = value
                break

    # Hyphenated planning titles often omit the repeated prefix, e.g.
    # "Waltendorfer Hauptstraße-Schulgasse-Ruckerlberggasse".
    for match in re.finditer(
        rf"\b(?P<prefix>[A-ZÄÖÜ][\wÄÖÜäöüß.-]+)\s+(?P<suffixes>[\wÄÖÜäöüß.-]+{STREET_SUFFIX_RE}(?:\s*[-–]\s*[\wÄÖÜäöüß.-]+{STREET_SUFFIX_RE}){{1,}})\b",
        text,
    ):
        prefix = match.group("prefix")
        suffixes = re.split(r"\s*[-–]\s*", match.group("suffixes"))
        for suffix in suffixes:
            candidates = [suffix, f"{prefix} {suffix}"]
            for candidate in candidates:
                normalized = normalize_street_name(candidate)
                if normalized in street_names:
                    normalized_to_display.setdefault(normalized, candidate)

    result: list[tuple[str, int, int]] = []
    for normalized, display in normalized_to_display.items():
        direct_match = re.search(re.escape(display), text, re.IGNORECASE)
        if direct_match:
            result.append((display, direct_match.start(), direct_match.end()))
        else:
            result.append((display, 0, min(len(text), len(display))))
    return sorted(result, key=lambda item: (item[1], item[2], item[0].casefold()))


def make_context(text: str, start: int, end: int, limit: int = 160) -> str:
    prefix_start = max(0, start - limit // 2)
    suffix_end = min(len(text), end + limit // 2)
    context = text[prefix_start:suffix_end]
    return re.sub(r"\s+", " ", context).strip()


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
