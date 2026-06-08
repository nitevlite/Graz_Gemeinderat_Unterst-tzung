from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from difflib import SequenceMatcher
from pathlib import Path
import importlib
import json
import re
import sys
from typing import Iterable

from .parser import (
    AgendaRecord,
    apply_vote_parties,
    format_result_text,
    normalize_date,
    normalize_vote_outcome,
)


DEFAULT_DIGRA_TOOL_PATH = Path(r"E:\01_StadtGrazProtokolle\Digra_Export_Tool\app")
DIGRA_SOURCE = "digra"
DIGRA_MISSING_SOURCE = "digra_fehlt"
PROTOCOL_SOURCE = "protokoll"
CACHE_VERSION = 2
MIN_AGENDA_TITLE_SCORE = 0.35
MIN_GENERIC_TITLE_SCORE = 0.44

BUSINESS_NUMBER_RE = re.compile(r"\b\d{1,6}/\d{1,4}\b")
DATE_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b")
OUTCOME_LINE_RE = re.compile(
    r"^(?P<modifier>einstimmig|mehrheitlich|mehrstimmig)?\s*"
    r"(?P<decision>angenommen|abgelehnt|zugewiesen|vertagt)\.?$",
    re.IGNORECASE,
)
PARTY_NOTE_RE = re.compile(
    r"\b(?P<label>Zustimmung|Dagegen|Gegen|Enthaltung|Gegenstimmen?)\s*:\s*(?P<parties>[^.;\n]+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DigraEntry:
    meeting_date: str
    meeting_number: str
    record_type: str
    section: str
    order_in_type: int
    agenda_item_no: int
    business_number: str
    title: str
    url: str
    status: str
    result_text: str
    raw_result_text: str
    votes: list[dict[str, object]]


def enrich_records_with_digra(
    records: list[AgendaRecord],
    tool_path: Path = DEFAULT_DIGRA_TOOL_PATH,
    cache_path: Path | None = None,
    results_only: bool = False,
) -> tuple[list[AgendaRecord], dict]:
    dates = sorted({record.meeting_date for record in records if record.meeting_date})
    entries = load_or_fetch_entries(dates, tool_path, cache_path)
    entries_by_type = group_entries_by_type(entries)
    type_counts: dict[tuple[str, str], int] = {}
    used_urls: set[str] = set()
    enriched: list[AgendaRecord] = []
    matched = 0
    matched_with_result = 0
    protocol_fallbacks = 0

    for record in records:
        key = (record.meeting_date, record.record_type)
        order = type_counts.get(key, 0) + 1
        type_counts[key] = order
        entry, match_score = find_best_digra_entry(
            record,
            entries_by_type.get((record.meeting_date, record.record_type), []),
            used_urls,
            order,
        )
        if entry is not None:
            matched += 1
            used_urls.add(entry.url)
        if entry is not None and entry.result_text:
            matched_with_result += 1
            enriched.append(
                replace(
                    record,
                    status=entry.status,
                    status_text=entry.status,
                    result_text=entry.result_text,
                    raw_result_text=entry.raw_result_text,
                    votes=entry.votes,
                    result_source=DIGRA_SOURCE,
                    digra_url=entry.url,
                    digra_business_number=entry.business_number,
                    protocol_result_text=record.result_text,
                    digra_match_score=match_score,
                )
            )
            continue
        if results_only:
            enriched.append(
                replace(
                    record,
                    status="unknown",
                    status_text="",
                    result_text="DIGRA-Ergebnis fehlt",
                    raw_result_text="",
                    votes=[],
                    result_source=DIGRA_MISSING_SOURCE,
                    digra_url=entry.url if entry else "",
                    digra_business_number=entry.business_number if entry else "",
                    protocol_result_text=record.result_text,
                    digra_match_score=match_score,
                )
            )
            continue
        protocol_fallbacks += 1
        enriched.append(
            replace(
                record,
                result_source=PROTOCOL_SOURCE if record.result_text and record.result_text != "Unbekannt" else DIGRA_MISSING_SOURCE,
                digra_url=entry.url if entry else "",
                digra_business_number=entry.business_number if entry else "",
                protocol_result_text=record.result_text,
                digra_match_score=match_score,
            )
        )

    summary = {
        "digra_entries_total": len(entries),
        "digra_records_matched": matched,
        "digra_results_used": matched_with_result,
        "digra_protocol_fallbacks": protocol_fallbacks,
        "digra_results_only": results_only,
        "digra_match_strategy": "agenda_item_no_or_title_similarity",
    }
    return enriched, summary


def load_or_fetch_entries(dates: list[str], tool_path: Path, cache_path: Path | None) -> list[DigraEntry]:
    if cache_path is not None and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_dates = set(payload.get("dates", []))
        if payload.get("cache_version") == CACHE_VERSION and set(dates).issubset(cached_dates):
            return [DigraEntry(**entry) for entry in payload.get("entries", [])]

    entries = fetch_digra_entries(dates, tool_path)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {"cache_version": CACHE_VERSION, "dates": dates, "entries": [asdict(entry) for entry in entries]},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            ),
            encoding="utf-8",
        )
    return entries


def fetch_digra_entries(dates: list[str], tool_path: Path = DEFAULT_DIGRA_TOOL_PATH) -> list[DigraEntry]:
    exporter = import_exporter(tool_path)
    session = exporter.requests.Session()
    session.headers.update({"User-Agent": "GrazCouncilProtocolExplorer/0.1 (+https://digra.graz.at)"})
    meetings = exporter.list_recent_meetings(fallback_years=3, limit=120)
    meetings_by_date = {normalize_date(meeting.date): meeting for meeting in meetings if meeting.date}
    entries: list[DigraEntry] = []
    for meeting_date in dates:
        meeting = meetings_by_date.get(meeting_date)
        if meeting is None:
            continue
        soup = exporter.fetch_soup(session, meeting.url)
        for tab_title, record_type, section in digra_tabs():
            panel = exporter.get_panel_for_tab(soup, tab_title)
            if panel is None:
                continue
            digra_entries = exporter.extract_entries_in_order(panel)
            for order, digra_entry in enumerate(digra_entries, start=1):
                desc_lines = flatten_blocks(digra_entry.desc_blocks)
                result = fetch_digra_result(exporter, session, digra_entry.href)
                business_number = extract_business_number(desc_lines, result.document_title)
                entries.append(
                    DigraEntry(
                        meeting_date=meeting_date,
                        meeting_number=meeting.number,
                        record_type=record_type,
                        section=section,
                        order_in_type=order,
                        agenda_item_no=extract_agenda_item_no(desc_lines, order),
                        business_number=business_number,
                        title=extract_title_from_digra(desc_lines),
                        url=digra_entry.href,
                        status=result.status,
                        result_text=result.result_text,
                        raw_result_text=result.raw_result_text,
                        votes=result.votes,
                    )
                )
    return entries


def import_exporter(tool_path: Path):
    if not tool_path.exists():
        raise RuntimeError(f"DIGRA-Export-Tool nicht gefunden: {tool_path}")
    tool_path_text = str(tool_path)
    if tool_path_text not in sys.path:
        sys.path.insert(0, tool_path_text)
    return importlib.import_module("exporter")


def digra_tabs() -> list[tuple[str, str, str]]:
    return [
        ("Tagesordnung", "agenda_item", "Tagesordnung"),
        ("Dringliche Anträge", "urgent_motion", "Dringlichkeitsanträge"),
        ("Anfragen an Bürgermeister:in", "written_question", "Anfragen an Bürgermeister:in"),
        ("Selbständige Anträge", "written_motion", "Selbständige Anträge"),
    ]


@dataclass(frozen=True)
class DigraResult:
    status: str
    result_text: str
    raw_result_text: str
    votes: list[dict[str, object]]
    document_title: str


def fetch_digra_result(exporter, session, url: str) -> DigraResult:
    soup = exporter.fetch_soup(session, url)
    document_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    preview = soup.select_one("div.preview") or soup.body or soup
    lines = [line.strip() for line in preview.get_text("\n").splitlines() if line.strip()]
    marker_index = next((index for index, line in enumerate(lines) if line.casefold() == "beschlussvermerk"), -1)
    if marker_index < 0:
        return DigraResult("unknown", "", "", [], document_title)

    outcome_line = ""
    note_lines: list[str] = []
    for line in lines[marker_index + 1 : marker_index + 18]:
        if line.casefold().startswith("schriftführer"):
            break
        if line.casefold() in {"gemeinderat"} or DATE_RE.fullmatch(line):
            continue
        if not outcome_line and OUTCOME_LINE_RE.match(line):
            outcome_line = line.rstrip(".")
            continue
        if outcome_line:
            if line.casefold().startswith("anmerkungen zur abstimmung"):
                continue
            note_lines.append(line)

    if not outcome_line:
        return DigraResult("unknown", "", "", [], document_title)

    outcome_match = OUTCOME_LINE_RE.match(outcome_line)
    if outcome_match is None:
        return DigraResult("unknown", "", "", [], document_title)
    status = normalize_vote_outcome(outcome_match.group("modifier") or "", outcome_match.group("decision"))
    raw_result_text = "\n".join([outcome_line, *note_lines])
    vote = {
        "subject": "motion",
        "outcome": status,
        "approval": [],
        "against": [],
        "abstention": [],
        "raw_text": raw_result_text,
    }
    for line in note_lines:
        for match in PARTY_NOTE_RE.finditer(line):
            apply_vote_parties(vote, match.group("label"), match.group("parties"))
    votes = [vote]
    return DigraResult(status, format_result_text(votes, status, outcome_line), raw_result_text, votes, document_title)


def group_entries_by_type(entries: Iterable[DigraEntry]) -> dict[tuple[str, str], list[DigraEntry]]:
    grouped: dict[tuple[str, str], list[DigraEntry]] = {}
    for entry in entries:
        grouped.setdefault((entry.meeting_date, entry.record_type), []).append(entry)
    return grouped


def find_best_digra_entry(
    record: AgendaRecord,
    candidates: list[DigraEntry],
    used_urls: set[str],
    order_in_type: int,
) -> tuple[DigraEntry | None, float]:
    available = [entry for entry in candidates if entry.url not in used_urls]
    if not available:
        return None, 0.0

    if record.record_type == "agenda_item":
        numbered = [entry for entry in available if entry.agenda_item_no == record.agenda_item_no]
        if numbered:
            best_numbered, numbered_score = best_by_title(
                record,
                numbered,
                order_in_type,
                minimum=MIN_AGENDA_TITLE_SCORE,
                use_order_bonus=False,
            )
            if best_numbered is not None:
                return best_numbered, numbered_score

    best, score = best_by_title(record, available, order_in_type, minimum=0.0)
    if best is None:
        return None, 0.0
    if score >= MIN_GENERIC_TITLE_SCORE:
        return best, score
    if best.order_in_type == order_in_type and record.record_type != "agenda_item" and score >= 0.28:
        return best, score
    return None, 0.0


def best_by_title(
    record: AgendaRecord,
    candidates: list[DigraEntry],
    order_in_type: int,
    minimum: float,
    use_order_bonus: bool = True,
) -> tuple[DigraEntry | None, float]:
    best: DigraEntry | None = None
    best_score = 0.0
    for entry in candidates:
        title_score = title_similarity(record.title, entry.title)
        order_bonus = 0.08 if use_order_bonus and entry.order_in_type == order_in_type else 0.0
        score = min(title_score + order_bonus, 1.0)
        if score > best_score:
            best = entry
            best_score = score
    if best is None or best_score < minimum:
        return None, 0.0
    return best, round(best_score, 3)


def title_similarity(left: str, right: str) -> float:
    left_norm = normalize_match_text(left)
    right_norm = normalize_match_text(right)
    if not left_norm or not right_norm:
        return 0.0
    sequence_score = SequenceMatcher(None, left_norm, right_norm).ratio()
    left_tokens = set(left_norm.split())
    right_tokens = set(right_norm.split())
    overlap = len(left_tokens & right_tokens) / max(len(left_tokens), 1)
    return max(sequence_score, overlap)


def normalize_match_text(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"\b[a-zäöüß]{0,5}\d+[a-z]?[-_/]?\d+(?:[-_/]\d+)*\b", " ", value)
    value = re.sub(r"\b\d{1,6}/\d{1,4}\b", " ", value)
    value = re.sub(r"€|\beuro\b|\d+[.,]?\d*", " ", value)
    value = re.sub(r"[^\wäöüß]+", " ", value)
    stopwords = {"der", "die", "das", "und", "von", "für", "fuer", "im", "in", "am", "an", "zu", "zur", "zum"}
    tokens = [token for token in value.split() if len(token) > 2 and token not in stopwords]
    return " ".join(tokens)


def flatten_blocks(blocks: list[list[str]]) -> list[str]:
    return [line.strip() for block in blocks for line in block if line.strip()]


def extract_business_number(desc_lines: list[str], document_title: str) -> str:
    for value in [document_title, *desc_lines]:
        match = BUSINESS_NUMBER_RE.search(value)
        if match:
            return match.group(0)
    return ""


def extract_agenda_item_no(desc_lines: list[str], fallback: int) -> int:
    for line in desc_lines[:2]:
        if line.isdigit():
            return int(line)
    return fallback


def extract_title_from_digra(desc_lines: list[str]) -> str:
    for index, line in enumerate(desc_lines):
        if line.casefold().startswith("betreff:"):
            value = line.split(":", 1)[1].strip()
            if value:
                return value
            following: list[str] = []
            for next_line in desc_lines[index + 1 :]:
                if ":" in next_line and not BUSINESS_NUMBER_RE.search(next_line):
                    break
                following.append(next_line)
            return " ".join(following).strip()
    return ""
