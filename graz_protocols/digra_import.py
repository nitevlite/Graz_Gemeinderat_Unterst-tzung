from __future__ import annotations

from dataclasses import asdict, dataclass, replace
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

BUSINESS_NUMBER_RE = re.compile(r"\b\d{1,6}/\d{1,4}\b")
DATE_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b")
OUTCOME_LINE_RE = re.compile(
    r"^(?P<modifier>einstimmig|mehrheitlich|mehrstimmig)?\s*"
    r"(?P<decision>angenommen|abgelehnt|zugewiesen|vertagt)\.?$",
    re.IGNORECASE,
)
PARTY_NOTE_RE = re.compile(
    r"\b(?P<label>Zustimmung|Dagegen|Gegen|Enthaltung|Gegenstimmen?)\s*:?\s*(?P<parties>[^.;\n]+)",
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
    index = build_match_index(entries)
    type_counts: dict[tuple[str, str], int] = {}
    enriched: list[AgendaRecord] = []
    matched = 0
    matched_with_result = 0

    for record in records:
        key = (record.meeting_date, record.record_type)
        order = type_counts.get(key, 0) + 1
        type_counts[key] = order
        entry = index.get((record.meeting_date, record.record_type, order))
        if entry is not None:
            matched += 1
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
                )
            )
            continue
        enriched.append(
            replace(
                record,
                result_source=PROTOCOL_SOURCE,
                digra_url=entry.url if entry else "",
                digra_business_number=entry.business_number if entry else "",
                protocol_result_text=record.result_text,
            )
        )

    summary = {
        "digra_entries_total": len(entries),
        "digra_records_matched": matched,
        "digra_results_used": matched_with_result,
        "digra_results_only": results_only,
    }
    return enriched, summary


def load_or_fetch_entries(dates: list[str], tool_path: Path, cache_path: Path | None) -> list[DigraEntry]:
    if cache_path is not None and cache_path.exists():
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
        cached_dates = set(payload.get("dates", []))
        if set(dates).issubset(cached_dates):
            return [DigraEntry(**entry) for entry in payload.get("entries", [])]

    entries = fetch_digra_entries(dates, tool_path)
    if cache_path is not None:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(
            json.dumps(
                {"dates": dates, "entries": [asdict(entry) for entry in entries]},
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


def build_match_index(entries: Iterable[DigraEntry]) -> dict[tuple[str, str, int], DigraEntry]:
    return {(entry.meeting_date, entry.record_type, entry.order_in_type): entry for entry in entries}


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
