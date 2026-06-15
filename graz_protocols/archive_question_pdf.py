from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .parser import AgendaRecord, extract_amounts, extract_location_details, extract_meeting_date, make_snippet
from .question_pdf import NUMBERED_TOPIC_RE, clean_question_person, clean_question_topic, extract_pdf_page_lines, normalize_question_lines


INQUIRY_INTRO_RE = re.compile(r"^(?P<speaker>.+?)\s+stellt\s+folgende\s+Anfrage\s*:?\s*$", re.IGNORECASE)
MAYOR_ANSWER_RE = re.compile(r"^(?P<speaker>Bgm(?:\.|in)?[^:]{0,90}|Bürgermeister(?:in)?[^:]{0,90})\s*:\s*(?P<text>.*)$", re.IGNORECASE)
SPEAKER_TURN_RE = re.compile(
    r"^(?P<speaker>(?:GR(?:in)?\.?|Bgm(?:\.|in)?|Bürgermeister(?:in)?|StR(?:in)?\.?|Stadtrat|Stadträtin)[^:]{0,90})\s*:\s*(?P<text>.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ArchiveQuestionBlock:
    number: int
    topic: str
    page: int = 0
    speaker: str = ""
    question: str = ""
    answer: str = ""


def parse_archive_question_pdf(path: Path, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_question_lines(extract_pdf_page_lines(path), path.name, source_url=source_url)


def parse_archive_question_text(text: str, source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    return parse_archive_question_lines([(0, line) for line in normalize_question_lines(text)], source_file, source_url=source_url)


def parse_archive_question_lines(page_lines: list[tuple[int, str]], source_file: str, *, source_url: str = "") -> list[AgendaRecord]:
    lines = [line for _page, line in page_lines]
    meeting_date = extract_meeting_date(lines, source_file)
    blocks = split_archive_question_blocks(page_lines)
    records: list[AgendaRecord] = []
    for index, block in enumerate(blocks, start=1):
        item_no = block.number or index
        title = title_from_archive_question(block.topic, item_no)
        body = [block.question, block.answer]
        locations = sorted({detail["text"] for detail in extract_location_details(" ".join([title, *body])) if detail.get("text")})
        records.append(
            AgendaRecord(
                record_id=build_archive_question_record_id(meeting_date, source_file, item_no, index),
                record_type="written_question",
                source_file=source_file,
                meeting_date=meeting_date,
                section="Anfragen an den Bürgermeister",
                agenda_item_no=item_no,
                business_numbers=[],
                title=title,
                status="unknown",
                status_text="",
                result_text="Unbekannt",
                raw_result_text="",
                votes=[],
                amounts=extract_amounts(title, body),
                locations=locations,
                location_details=extract_location_details(" ".join([title, *body])),
                source_snippet=make_snippet("\n".join(part for part in body if part), limit=900),
                parser_confidence=archive_question_confidence(block),
                result_source="protokoll",
                source_url=source_url_with_page(source_url, block.page),
                source_page=block.page,
                submitter=block.speaker,
                question_parts={
                    "question": block.question,
                    "answer": block.answer,
                    "speaker": block.speaker,
                    "source_page": str(block.page or ""),
                },
            )
        )
    return records


def split_archive_question_blocks(lines: list[tuple[int, str]]) -> list[ArchiveQuestionBlock]:
    blocks: list[ArchiveQuestionBlock] = []
    current = MutableArchiveQuestionBlock()
    active = ""
    for page, line in lines:
        topic_match = NUMBERED_TOPIC_RE.match(line)
        if topic_match:
            if current.has_content():
                blocks.append(current.freeze())
            current = MutableArchiveQuestionBlock(
                number=int(topic_match.group("number")),
                topic=topic_match.group("title").strip(),
                page=page,
            )
            active = ""
            continue

        intro_match = INQUIRY_INTRO_RE.match(line)
        if intro_match:
            current.speaker = clean_question_person(intro_match.group("speaker"))
            active = "question"
            continue

        mayor_match = MAYOR_ANSWER_RE.match(line)
        if mayor_match and current.has_content():
            active = "answer"
            current.add(active, mayor_match.group("text").strip())
            continue

        turn_match = SPEAKER_TURN_RE.match(line)
        if turn_match and current.has_content():
            speaker = clean_question_person(turn_match.group("speaker"))
            if not current.speaker and speaker.casefold().startswith("gr"):
                current.speaker = speaker
            active = "answer" if speaker.casefold().startswith(("bgm", "bürgermeister")) else "question"
            current.add(active, turn_match.group("text").strip())
            continue

        if current.topic and not active:
            current.append_topic(line)
            continue
        if active:
            current.add(active, line)

    if current.has_content():
        blocks.append(current.freeze())
    return [block for block in blocks if block.topic and (block.question or block.answer)]


class MutableArchiveQuestionBlock:
    def __init__(self, *, number: int = 0, topic: str = "", page: int = 0) -> None:
        self.number = number
        self.topic = topic
        self.page = page
        self.speaker = ""
        self.question: list[str] = []
        self.answer: list[str] = []

    def append_topic(self, value: str) -> None:
        self.topic = f"{self.topic} {value}".strip()

    def add(self, label: str, value: str) -> None:
        if value:
            getattr(self, label).append(value)

    def has_content(self) -> bool:
        return bool(self.question or self.answer)

    def freeze(self) -> ArchiveQuestionBlock:
        return ArchiveQuestionBlock(
            number=self.number,
            topic=self.topic,
            page=self.page,
            speaker=clean_question_person(self.speaker),
            question=" ".join(self.question).strip(),
            answer=" ".join(self.answer).strip(),
        )


def title_from_archive_question(topic: str, index: int) -> str:
    title = clean_question_topic(topic)
    if not title:
        return f"Schriftliche Anfrage {index}"
    if len(title) <= 112:
        return title
    return title[:111].rstrip(" ,.;") + "…"


def source_url_with_page(source_url: str, page: int) -> str:
    if not source_url or page <= 0:
        return source_url
    return f"{source_url.split('#', 1)[0]}#page={page}"


def archive_question_confidence(block: ArchiveQuestionBlock) -> float:
    score = 0.5
    if block.topic:
        score += 0.15
    if block.speaker:
        score += 0.15
    if block.question:
        score += 0.15
    if block.answer:
        score += 0.05
    return min(score, 1.0)


def build_archive_question_record_id(meeting_date: str, source_file: str, item_no: int, index: int = 0) -> str:
    stem = Path(source_file).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    suffix = f"-{index}" if index and index != item_no else ""
    return f"{meeting_date or 'unknown-date'}-archive-question-{item_no}{suffix}-{stem}"
