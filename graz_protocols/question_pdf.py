from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import importlib
import re

from .parser import AgendaRecord, extract_meeting_date, make_snippet


LABEL_RE = re.compile(r"^(?P<label>Frage|Antwort|Zusatzfrage|Zusatzantwort|Nachfrage)\b\s*:\s*(?P<text>.*)$", re.IGNORECASE)
SPEAKER_RE = re.compile(
    r"^(?P<label>Fragesteller(?:in)?|Antwort(?:ende|ender)?|Bürgermeister(?:in)?|Stadtrat|Stadträtin)\s*:?\s*(?P<text>.*)$",
    re.IGNORECASE,
)
NUMBERED_TOPIC_RE = re.compile(r"^(?P<number>\d{1,2})\)\s*(?P<title>.+)$")
ASKS_QUESTION_RE = re.compile(
    r"^(?P<speaker>.+?)\s+stellt\s+an\s+(?P<respondent>.+?)\s+folgende\s+Frage\s*:?\s*$",
    re.IGNORECASE,
)
SPEAKER_TURN_RE = re.compile(
    r"^(?P<speaker>(?:GR(?:in)?\.?|Bgm(?:\.|in)?|Bgm\.?[-‐–]\s*Stvin\.?|Bürgermeister(?:in)?|StR(?:in)?\.?|Stadtrat|Stadträtin)[^:]{0,90})\s*:\s*(?P<text>.*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class QuestionHourBlock:
    number: int = 0
    topic: str = ""
    question: str = ""
    answer: str = ""
    followup_question: str = ""
    followup_answer: str = ""
    speaker: str = ""
    respondent: str = ""


def read_question_hour_source(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".pdf":
        return extract_pdf_text(path)
    return path.read_text(encoding="utf-8")


def extract_pdf_text(path: Path) -> str:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:
        raise RuntimeError("PDF-Extraktion benötigt optional das Paket pypdf.") from exc
    reader = pypdf.PdfReader(str(path))
    page_texts = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(page_texts)


def extract_pdf_page_lines(path: Path) -> list[tuple[int, str]]:
    try:
        pypdf = importlib.import_module("pypdf")
    except ImportError as exc:
        raise RuntimeError("PDF-Extraktion benötigt optional das Paket pypdf.") from exc
    reader = pypdf.PdfReader(str(path))
    lines: list[tuple[int, str]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        for raw_line in (page.extract_text() or "").replace("\r", "\n").splitlines():
            line = normalize_question_line(raw_line)
            if line:
                lines.append((page_number, line))
    return lines


def parse_question_hour_text(text: str, source_file: str) -> list[AgendaRecord]:
    lines = normalize_question_lines(text)
    meeting_date = extract_meeting_date(lines, source_file)
    blocks = split_question_blocks(lines)
    records: list[AgendaRecord] = []
    for index, block in enumerate(blocks, start=1):
        item_no = block.number or index
        title = title_from_question(block.topic or block.question, item_no)
        snippet = make_question_snippet(block)
        records.append(
            AgendaRecord(
                record_id=build_question_record_id(meeting_date, source_file, item_no, index),
                record_type="question_hour",
                source_file=source_file,
                meeting_date=meeting_date,
                section="Fragestunde",
                agenda_item_no=item_no,
                business_numbers=[],
                title=title,
                status="unknown",
                status_text="",
                result_text="Unbekannt",
                raw_result_text="",
                votes=[],
                amounts=[],
                locations=[],
                source_snippet=make_snippet(snippet, limit=900),
                parser_confidence=question_confidence(block),
                submitter=block.speaker,
                question_parts={
                    "question": block.question,
                    "answer": block.answer,
                    "followup_question": block.followup_question,
                    "followup_answer": block.followup_answer,
                    "speaker": block.speaker,
                    "respondent": block.respondent,
                },
            )
        )
    return records


def normalize_question_lines(text: str) -> list[str]:
    lines = []
    for raw_line in text.replace("\r", "\n").splitlines():
        line = normalize_question_line(raw_line)
        if line:
            lines.append(line)
    return lines


def normalize_question_line(raw_line: str) -> str:
    line = re.sub(r"\s+", " ", raw_line).strip()
    if not line:
        return ""
    if is_question_pdf_noise(line):
        return ""
    if re.fullmatch(r"\d{1,4}", line):
        return ""
    return line


def is_question_pdf_noise(line: str) -> bool:
    normalized = line.casefold()
    if re.fullmatch(r"f\s*r\s*a\s*g\s*e\s*s\s*t\s*u\s*n\s*d\s*e", normalized):
        return True
    if re.fullmatch(r"beginn:\s*.+|ende:\s*.+", normalized):
        return True
    if re.fullmatch(r"sitzung des gemeinderates vom .+ \d{1,4}", normalized):
        return True
    return False


def split_question_blocks(lines: list[str]) -> list[QuestionHourBlock]:
    blocks: list[QuestionHourBlock] = []
    current = MutableQuestionBlock()
    active = ""
    for line in lines:
        topic_match = NUMBERED_TOPIC_RE.match(line)
        if topic_match:
            if current.has_content():
                blocks.append(current.freeze())
            current = MutableQuestionBlock(
                topic=topic_match.group("title").strip(),
                number=int(topic_match.group("number")),
            )
            active = ""
            continue

        asks_match = ASKS_QUESTION_RE.match(line)
        if asks_match:
            current.speaker = clean_question_person(asks_match.group("speaker"))
            current.respondent = clean_question_person(asks_match.group("respondent"))
            active = "question"
            continue

        label_match = LABEL_RE.match(line)
        if label_match:
            label = normalize_label(label_match.group("label"))
            value = label_match.group("text").strip()
            if label == "question" and current.has_content():
                blocks.append(current.freeze())
                current = MutableQuestionBlock()
            active = label
            current.add(active, value)
            continue

        speaker_match = SPEAKER_RE.match(line)
        if speaker_match:
            label = speaker_match.group("label").casefold()
            value = clean_question_person(speaker_match.group("text"))
            if "frage" in label:
                current.speaker = value
            else:
                current.respondent = value
            continue

        turn_match = SPEAKER_TURN_RE.match(line)
        if turn_match and (current.topic or current.has_content()):
            target = next_turn_label(current)
            speaker = clean_question_person(turn_match.group("speaker"))
            value = turn_match.group("text").strip()
            if target == "question" and not current.speaker:
                current.speaker = speaker
            if target in {"answer", "followup_answer"} and not current.respondent:
                current.respondent = speaker
            active = target
            current.add(active, value)
            continue

        if current.topic and not active:
            current.append_topic(line)
            continue

        if active:
            current.add(active, line)
    if current.has_content():
        blocks.append(current.freeze())
    return [block for block in blocks if block.question or block.answer]


class MutableQuestionBlock:
    def __init__(self, topic: str = "", number: int = 0) -> None:
        self.number = number
        self.topic = topic
        self.question: list[str] = []
        self.answer: list[str] = []
        self.followup_question: list[str] = []
        self.followup_answer: list[str] = []
        self.speaker = ""
        self.respondent = ""

    def add(self, label: str, value: str) -> None:
        if not value:
            return
        getattr(self, label).append(value)

    def append_topic(self, value: str) -> None:
        if not value:
            return
        self.topic = f"{self.topic} {value}".strip()

    def has_content(self) -> bool:
        return bool(self.question or self.answer or self.followup_question or self.followup_answer)

    def freeze(self) -> QuestionHourBlock:
        return QuestionHourBlock(
            number=self.number,
            topic=self.topic,
            question=" ".join(self.question).strip(),
            answer=" ".join(self.answer).strip(),
            followup_question=" ".join(self.followup_question).strip(),
            followup_answer=" ".join(self.followup_answer).strip(),
            speaker=clean_question_person(self.speaker),
            respondent=clean_question_person(self.respondent),
        )


def clean_question_person(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" :")
    text = re.sub(r"\bMag\s+a\b", "Maga", text)
    text = re.sub(r"\bDr\s+in\b", "Drin", text)
    text = re.sub(r"\bBgm\.\s*-\s*Stvin\.", "Bgm.-Stvin.", text)
    text = re.sub(r"\bStR\s+in\b", "StRin", text)
    text = re.sub(r"\bGR\s+in\b", "GRin", text)
    if re.match(r"^a\s+[A-ZÄÖÜ]", text):
        return f"GRin. Maga {text[2:].strip()}"
    return text


def normalize_label(label: str) -> str:
    normalized = label.casefold()
    if normalized == "antwort":
        return "answer"
    if normalized in {"zusatzfrage", "nachfrage"}:
        return "followup_question"
    if normalized == "zusatzantwort":
        return "followup_answer"
    return "question"


def next_turn_label(block: MutableQuestionBlock) -> str:
    if not block.question:
        return "question"
    if not block.answer:
        return "answer"
    if not block.followup_question:
        return "followup_question"
    return "followup_answer"


def title_from_question(question: str, index: int) -> str:
    text = clean_question_topic(question)
    if not text:
        return f"Fragestunde Frage {index}"
    if len(text) <= 96:
        return text
    return text[:95].rstrip(" ,.;") + "…"


def clean_question_topic(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip(" .")
    text = re.sub(
        r"\s+(?:GR(?:in)?\.?|Bgm(?:\.|in)?|Bürgermeister(?:in)?|StR(?:in)?\.?|Stadtrat|Stadträtin)\b.{0,160}?\bstellt\s+an\b.*$",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip(" .")
    text = re.sub(r"\s+GR(?:in)?\.?\s+(?:Mag\.?|Maga?|Dr\.?|Drin\.?)?$", "", text, flags=re.IGNORECASE).strip(" .")
    return text


def make_question_snippet(block: QuestionHourBlock) -> str:
    parts = [
        ("Frage", block.question),
        ("Antwort", block.answer),
        ("Zusatzfrage", block.followup_question),
        ("Zusatzantwort", block.followup_answer),
    ]
    return "\n".join(f"{label}: {value}" for label, value in parts if value)


def question_confidence(block: QuestionHourBlock) -> float:
    score = 0.45
    if block.question:
        score += 0.25
    if block.answer:
        score += 0.2
    if block.followup_question or block.followup_answer:
        score += 0.1
    return min(score, 1.0)


def build_question_record_id(meeting_date: str, source_file: str, item_no: int, index: int = 0) -> str:
    stem = Path(source_file).stem.lower()
    stem = re.sub(r"[^a-z0-9]+", "-", stem).strip("-")
    suffix = f"-{index}" if index and index != item_no else ""
    return f"{meeting_date or 'unknown-date'}-question-hour-{item_no}{suffix}-{stem}"
