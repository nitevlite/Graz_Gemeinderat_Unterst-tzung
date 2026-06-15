from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from difflib import SequenceMatcher
from pathlib import Path
import importlib
import json
import re
import sys
from typing import Iterable
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from .parser import (
    AgendaRecord,
    apply_vote_parties,
    format_result_text,
    normalize_date,
    normalize_written_submission_status,
    normalize_vote_outcome,
)


DEFAULT_DIGRA_TOOL_PATH = Path(r"E:\01_StadtGrazProtokolle\Digra_Export_Tool\app")
DIGRA_SOURCE = "digra"
DIGRA_MISSING_SOURCE = "digra_fehlt"
PROTOCOL_SOURCE = "protokoll"
CACHE_VERSION = 11
MIN_AGENDA_TITLE_SCORE = 0.5
MIN_GENERIC_TITLE_SCORE = 0.55
MIN_ORDER_TITLE_SCORE = 0.5
MIN_FALLBACK_LINK_SCORE = 0.7
GENERIC_MATCH_TOKENS = {
    "abteilung",
    "abschluss",
    "budgetvorsorge",
    "dienststelle",
    "ermächtigung",
    "ermaechtigung",
    "euro",
    "feststellung",
    "förderung",
    "foerderung",
    "generalversammlung",
    "gemäß",
    "gemaess",
    "gmbh",
    "graz",
    "grazer",
    "höhe",
    "hoehe",
    "ihv",
    "jahr",
    "jahre",
    "jahresabschluss",
    "landeshauptstadt",
    "projektgenehmigung",
    "richtlinien",
    "stadt",
    "statut",
    "statuts",
    "statutes",
    "stimmrechtsermächtigung",
    "stimmrechtsermaechtigung",
    "umlaufbeschluss",
    "vertreter",
    "vertreters",
}

BUSINESS_NUMBER_RE = re.compile(r"\b\d{1,6}/\d{1,4}\b")
DATE_RE = re.compile(r"\b\d{1,2}\.\d{1,2}\.\d{4}\b")
OUTCOME_LINE_RE = re.compile(
    r"^(?P<modifier>einstimmig|mehrheitlich|mehrstimmig)?\s*"
    r"(?P<decision>angenommen|abgelehnt|zugewiesen|vertagt)\.?$",
    re.IGNORECASE,
)
NO_MAJORITY_RE = re.compile(r"^(?:keine\s+mehrheit|dringlichkeit\s+bekam\s+keine\s+mehrheit)\.?$", re.IGNORECASE)
NOTED_RE = re.compile(r"^zur\s+kenntnis\s+gebracht\.?$", re.IGNORECASE)
ANSWERED_RE = re.compile(r"^(?:mündlich|muendlich|schriftlich)?\s*beantwortet\.?$", re.IGNORECASE)
DECISION_ORGAN_RE = re.compile(r"^(?:Gemeinderat|Ausschuss\b.+)$", re.IGNORECASE)
DIGRA_BODY_START_RE = re.compile(
    r"^(?:der|die|das|frau|herr|ich|wir|es|gemäß|gemaess|sehr\s+geehrte|am\s+vergangenen|kurz\s+vor)\b|.*[.!?]$",
    re.IGNORECASE,
)
PARTY_NOTE_RE = re.compile(
    r"\b(?P<label>Zustimmung|Dagegen|Gegen|Enthaltung|Gegenstimmen?)\s*:\s*(?P<parties>[^.;\n]+)",
    re.IGNORECASE,
)
SPLIT_VOTE_LINE_RE = re.compile(
    r"^(?P<label>Dringlichkeit|Punkt\s*\d+|Antrag|Abänderungsantrag|Abaenderungsantrag|Zusatzantrag)"
    r"(?:\s+wurde)?\s*[:;,]?\s*"
    r"(?P<modifier>einstimmig|mehrheitlich|mehrstimmig)?\s*"
    r"(?P<decision>angenommen|abgelehnt|zugewiesen|vertagt)\b",
    re.IGNORECASE,
)
ROLE_TITLE_RE = re.compile(
    r"^(?:Berichterstatter(?:in|:in)?|Bearbeiter(?:in|:in)?|Einbringer(?:in|:in)?)\s*:?\s*",
    re.IGNORECASE,
)
ROLE_TITLE_PREFIX_RE = re.compile(
    r"^(?:Berichterstatter(?:in|:in)?|Bearbeiter(?:in|:in)?|Einbringer(?:in|:in)?)\s*:?\s*"
    r"[^:;]{0,220}?(?:\([^)]{1,80}\)|,?\s(?:KPÖ|KPOE|Grüne|Gruene|SPÖ|SPOE|ÖVP|OEVP|FPÖ|FPOE|NEOS|KFG|GRÜNE))\s+",
    re.IGNORECASE,
)
METADATA_LABELS = {
    "anlagen",
    "beschlussvermerk",
    "datum",
    "dienststelle",
    "dienststelle(n)",
    "einlagezahl",
    "freigaben / unterschriften",
    "gemeinderat",
    "materialien",
    "regierungsmitglied",
    "regierungsmitglied(er)",
    "vorberatendes organ",
}


def canonical_digra_url(value: str) -> str:
    if not value:
        return ""
    parsed = urlparse(value.strip())
    if parsed.netloc != "digra.graz.at" or parsed.path != "/document":
        return ""
    ref = parse_qs(parsed.query).get("ref", [""])[0]
    if not ref:
        return ""
    return urlunparse(("https", "digra.graz.at", "/document", "", urlencode({"ref": ref}), ""))


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
    submitter: str = ""
    source_snippet: str = ""
    attachment_titles: list[str] = field(default_factory=list)


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
                    submitter=record.submitter or entry.submitter,
                    result_source=DIGRA_SOURCE,
                    digra_url=canonical_digra_url(entry.url),
                    digra_business_number=entry.business_number,
                    protocol_result_text=record.result_text,
                    digra_match_score=match_score,
                    attachment_titles=entry.attachment_titles,
                )
            )
            continue
        if results_only:
            status, status_text, raw_result_text = normalize_written_submission_status(
                record.record_type, "unknown", "", ""
            )
            result_text = format_result_text([], status, status_text) if status == "assigned" else "DIGRA-Ergebnis fehlt"
            enriched.append(
                replace(
                    record,
                    status=status,
                    status_text=status_text,
                    result_text=result_text,
                    raw_result_text=raw_result_text,
                    votes=[],
                    submitter=record.submitter or (entry.submitter if entry else ""),
                    result_source=DIGRA_MISSING_SOURCE,
                    digra_url=canonical_digra_url(entry.url) if entry and match_score >= MIN_FALLBACK_LINK_SCORE else "",
                    digra_business_number=entry.business_number if entry and match_score >= MIN_FALLBACK_LINK_SCORE else "",
                    protocol_result_text=record.result_text,
                    digra_match_score=match_score,
                    attachment_titles=entry.attachment_titles if entry and match_score >= MIN_FALLBACK_LINK_SCORE else [],
                )
            )
            continue
        protocol_fallbacks += 1
        enriched.append(
            replace(
                record,
                result_source=PROTOCOL_SOURCE if record.result_text and record.result_text != "Unbekannt" else DIGRA_MISSING_SOURCE,
                submitter=record.submitter or (entry.submitter if entry and match_score >= MIN_FALLBACK_LINK_SCORE else ""),
                digra_url=canonical_digra_url(entry.url) if entry and match_score >= MIN_FALLBACK_LINK_SCORE else "",
                digra_business_number=entry.business_number if entry and match_score >= MIN_FALLBACK_LINK_SCORE else "",
                protocol_result_text=record.result_text,
                digra_match_score=match_score,
                attachment_titles=entry.attachment_titles if entry and match_score >= MIN_FALLBACK_LINK_SCORE else [],
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
            return dedupe_digra_entries(
                [DigraEntry(**{**entry, "url": canonical_digra_url(str(entry.get("url", "")))}) for entry in payload.get("entries", [])]
            )

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
    return dedupe_digra_entries(entries)


def dedupe_digra_entries(entries: list[DigraEntry]) -> list[DigraEntry]:
    by_url: dict[str, DigraEntry] = {}
    ordered_urls: list[str] = []
    for entry in entries:
        key = canonical_digra_url(entry.url) or f"{entry.meeting_date}:{entry.record_type}:{entry.order_in_type}:{entry.title}"
        if key not in by_url:
            by_url[key] = entry
            ordered_urls.append(key)
            continue
        if digra_entry_priority(entry) > digra_entry_priority(by_url[key]):
            by_url[key] = entry
    return [by_url[key] for key in ordered_urls]


def digra_entry_priority(entry: DigraEntry) -> tuple[int, int, int]:
    type_priority = {
        "amendment_motion": 6,
        "additional_motion": 6,
        "urgent_motion": 5,
        "written_motion": 5,
        "written_question": 5,
        "communication": 4,
        "agenda_item": 2,
    }.get(entry.record_type, 1)
    result_priority = 1 if entry.result_text else 0
    return (type_priority, result_priority, len(entry.title or ""))


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
                        record_type=result.record_type_override or record_type,
                        section=digra_section_for_type(result.record_type_override or record_type, section),
                        order_in_type=order,
                        agenda_item_no=extract_agenda_item_no(desc_lines, order),
                        business_number=business_number,
                        title=best_digra_title(desc_lines, result),
                        url=canonical_digra_url(digra_entry.href),
                        status=result.status,
                        result_text=result.result_text,
                        raw_result_text=result.raw_result_text,
                        votes=result.votes,
                        submitter=result.submitter,
                        source_snippet=result.source_snippet,
                        attachment_titles=result.attachment_titles,
                    )
                )
    return entries


def digra_section_for_type(record_type: str, fallback: str) -> str:
    return {
        "communication": "Mitteilungen",
        "amendment_motion": "Abänderungsanträge",
        "additional_motion": "Zusatzanträge",
    }.get(record_type, fallback)


def digra_entries_to_records(entries: list[DigraEntry]) -> list[AgendaRecord]:
    records: list[AgendaRecord] = []
    for index, entry in enumerate(entries, start=1):
        status = entry.status if entry.result_text else "unknown"
        status, status_text, raw_result_text = normalize_written_submission_status(
            entry.record_type, status, status, entry.raw_result_text
        )
        result_text = entry.result_text or format_result_text([], status, status_text)
        if result_text == "Unbekannt":
            result_text = "DIGRA-Ergebnis fehlt"
        records.append(
            AgendaRecord(
                record_id=f"{entry.meeting_date}-digra-{entry.record_type}-{entry.order_in_type}-{index}",
                record_type=entry.record_type,
                source_file="DIGRA",
                meeting_date=entry.meeting_date,
                section=entry.section,
                agenda_item_no=entry.agenda_item_no,
                business_numbers=[entry.business_number] if entry.business_number else [],
                title=entry.title,
                status=status,
                status_text=status_text,
                result_text=result_text,
                raw_result_text=raw_result_text,
                votes=entry.votes,
                submitter=entry.submitter,
                amounts=[],
                locations=[],
                source_snippet=entry.source_snippet,
                attachment_titles=entry.attachment_titles,
                parser_confidence=0.8 if entry.title else 0.5,
                result_source=DIGRA_SOURCE if entry.result_text else DIGRA_MISSING_SOURCE,
                digra_url=canonical_digra_url(entry.url),
                digra_business_number=entry.business_number,
                protocol_result_text="",
                digra_match_score=1.0,
            )
        )
    return records


def list_digra_meetings(tool_path: Path = DEFAULT_DIGRA_TOOL_PATH, limit: int = 20):
    exporter = import_exporter(tool_path)
    return exporter.list_recent_meetings(fallback_years=3, limit=limit)


def import_exporter(tool_path: Path):
    if not tool_path.exists():
        return importlib.import_module("graz_protocols.digra_public")
    tool_path_text = str(tool_path)
    if tool_path_text not in sys.path:
        sys.path.insert(0, tool_path_text)
    return importlib.import_module("exporter")


def digra_tabs() -> list[tuple[str, str, str]]:
    return [
        ("Mitteilungen", "communication", "Mitteilungen"),
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
    submitter: str = ""
    subject_title: str = ""
    record_type_override: str = ""
    source_snippet: str = ""
    attachment_titles: list[str] = field(default_factory=list)


def fetch_digra_result(exporter, session, url: str) -> DigraResult:
    soup = exporter.fetch_soup(session, url)
    attachment_titles = extract_digra_attachment_titles(soup)
    document_title = soup.title.get_text(" ", strip=True) if soup.title else ""
    preview = soup.select_one("div.preview") or soup.body or soup
    lines = [line.strip() for line in preview.get_text("\n").splitlines() if line.strip()]
    submitter = extract_digra_submitter(lines)
    subject_title = extract_digra_subject_title(lines)
    source_snippet = extract_digra_source_snippet(lines, subject_title)
    record_type_override = extract_digra_record_type(lines)
    marker_index = next((index for index, line in enumerate(lines) if line.casefold() == "beschlussvermerk"), -1)
    if marker_index < 0:
        return DigraResult(
            "unknown", "", "", [], document_title, submitter, subject_title, record_type_override, source_snippet, attachment_titles
        )

    decision_votes = extract_decision_votes(lines[marker_index + 1 : marker_index + 24])
    if decision_votes:
        raw_result_text = "\n".join(str(vote.get("raw_text", "")) for vote in decision_votes if vote.get("raw_text"))
        status = aggregate_split_vote_status(decision_votes)
        result_text = format_split_result_text(decision_votes)
        return DigraResult(
            status,
            result_text,
            raw_result_text,
            decision_votes,
            document_title,
            submitter,
            subject_title,
            record_type_override,
            source_snippet,
            attachment_titles,
        )

    outcome_line = ""
    note_lines: list[str] = []
    for line in lines[marker_index + 1 : marker_index + 18]:
        if line.casefold().startswith("schriftführer"):
            break
        if line.casefold() in {"gemeinderat"} or DATE_RE.fullmatch(line):
            continue
        if not outcome_line and (
            OUTCOME_LINE_RE.match(line)
            or line.casefold() == "getrennt abgestimmt"
            or NO_MAJORITY_RE.match(line)
            or NOTED_RE.match(line)
            or ANSWERED_RE.match(line)
        ):
            outcome_line = line.rstrip(".")
            continue
        if outcome_line:
            if line.casefold().startswith("anmerkungen zur abstimmung"):
                continue
            note_lines.append(line)

    if not outcome_line:
        return DigraResult(
            "unknown", "", "", [], document_title, submitter, subject_title, record_type_override, source_snippet, attachment_titles
        )

    if outcome_line.casefold() == "getrennt abgestimmt":
        raw_result_text = "\n".join([outcome_line, *note_lines])
        votes = extract_split_votes(note_lines, raw_result_text)
        status = aggregate_split_vote_status(votes)
        result_text = format_split_result_text(votes) if votes else ""
        return DigraResult(
            status, result_text, raw_result_text, votes, document_title, submitter, subject_title, record_type_override, source_snippet, attachment_titles
        )

    if NO_MAJORITY_RE.match(outcome_line):
        raw_result_text = "\n".join([outcome_line, *note_lines])
        vote = {
            "subject": "urgency",
            "outcome": "rejected_majority",
            "approval": [],
            "against": [],
            "abstention": [],
            "raw_text": raw_result_text,
        }
        votes = [vote]
        return DigraResult(
            "rejected_majority",
            format_split_result_text(votes),
            raw_result_text,
            votes,
            document_title,
            submitter,
            subject_title,
            record_type_override,
            source_snippet,
            attachment_titles,
        )

    if NOTED_RE.match(outcome_line):
        raw_result_text = "\n".join([outcome_line, *note_lines])
        return DigraResult(
            "noted",
            "zur Kenntnis gebracht",
            raw_result_text,
            [],
            document_title,
            submitter,
            subject_title,
            record_type_override,
            source_snippet,
            attachment_titles,
        )

    if ANSWERED_RE.match(outcome_line):
        raw_result_text = "\n".join([outcome_line, *note_lines])
        return DigraResult(
            "source_available",
            outcome_line,
            raw_result_text,
            [],
            document_title,
            submitter,
            subject_title,
            record_type_override or "question_hour",
            source_snippet,
            attachment_titles,
        )

    outcome_match = OUTCOME_LINE_RE.match(outcome_line)
    if outcome_match is None:
        return DigraResult(
            "unknown", "", "", [], document_title, submitter, subject_title, record_type_override, source_snippet, attachment_titles
        )
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
    return DigraResult(
        status,
        format_result_text(votes, status, outcome_line),
        raw_result_text,
        votes,
        document_title,
        submitter,
        subject_title,
        record_type_override,
        source_snippet,
        attachment_titles,
    )


def extract_digra_submitter(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        normalized = line.casefold().strip(" :")
        if normalized in {"antragsteller:in(nen)", "antragsteller:innen", "antragsteller", "fragesteller:in", "fragesteller"}:
            return clean_digra_person(lines[index + 1] if index + 1 < len(lines) else "")
    for index, line in enumerate(lines):
        normalized = line.casefold().strip(" :")
        if normalized in {
            "berichterstatter:in",
            "berichterstatterin",
            "berichterstatter",
            "berichterstatter:innen",
        }:
            person = clean_digra_person(lines[index + 1] if index + 1 < len(lines) else "")
            return f"Berichterstatterin: {person}" if person else ""
    for index, line in enumerate(lines):
        normalized = line.casefold().strip(" :")
        if normalized in {"bearbeiter:in", "bearbeiterin", "bearbeiter"}:
            person = clean_digra_person(lines[index + 1] if index + 1 < len(lines) else "")
            return f"Bearbeiterin: {person}" if person else ""
    for index, line in enumerate(lines):
        if line.casefold().strip(" :") == "freigaben / unterschriften":
            return clean_digra_person(lines[index + 1] if index + 1 < len(lines) else "")
    return ""


def clean_digra_person(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" ,;")
    return cleaned if cleaned and ":" not in cleaned else ""


def extract_digra_record_type(lines: list[str]) -> str:
    head = " ".join(lines[:14]).casefold()
    if "fragestunde" in head or "fragesteller" in head or re.search(r"\bstellt\s+an\s+.+folgende\s+frage\b", head):
        return "question_hour"
    if "mitteilung an den gemeinderat" in head:
        return "communication"
    if "abänderungsantrag" in head or "abaenderungsantrag" in head:
        return "amendment_motion"
    if "zusatzantrag" in head:
        return "additional_motion"
    return ""


def extract_decision_votes(lines: list[str]) -> list[dict[str, object]]:
    votes: list[dict[str, object]] = []
    current_organ = ""
    current_date = ""
    for index, line in enumerate(lines):
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if cleaned.casefold().startswith("schriftführer"):
            break
        if DECISION_ORGAN_RE.match(cleaned):
            current_organ = cleaned
            current_date = ""
            continue
        date_match = re.match(r"^am\s+(\d{1,2}\.\d{1,2}\.\d{4})$", cleaned, flags=re.IGNORECASE)
        if date_match:
            current_date = date_match.group(1)
            continue
        outcome_match = OUTCOME_LINE_RE.match(cleaned)
        answered_match = ANSWERED_RE.match(cleaned)
        noted_match = NOTED_RE.match(cleaned)
        if outcome_match is None and answered_match is None and noted_match is None:
            continue
        note_lines = collect_decision_note_lines(lines[index + 1 :])
        raw_parts = [part for part in [current_organ, f"am {current_date}" if current_date else "", cleaned, *note_lines] if part]
        if outcome_match is not None:
            status = normalize_vote_outcome(outcome_match.group("modifier") or "", outcome_match.group("decision"))
        elif noted_match is not None:
            status = "noted"
        else:
            status = "source_available"
        vote = {
            "subject": "motion",
            "outcome": status,
            "outcome_text": cleaned,
            "approval": [],
            "against": [],
            "abstention": [],
            "raw_text": "\n".join(raw_parts),
            "organ": current_organ,
            "date": current_date,
        }
        for note in note_lines:
            for party_match in PARTY_NOTE_RE.finditer(note):
                apply_vote_parties(vote, party_match.group("label"), party_match.group("parties"))
        votes.append(vote)
    return votes


def collect_decision_note_lines(lines: list[str]) -> list[str]:
    notes: list[str] = []
    for line in lines:
        cleaned = re.sub(r"\s+", " ", line).strip()
        if not cleaned:
            continue
        if cleaned.casefold().startswith("schriftführer"):
            break
        if DECISION_ORGAN_RE.match(cleaned):
            break
        if OUTCOME_LINE_RE.match(cleaned) or ANSWERED_RE.match(cleaned) or NOTED_RE.match(cleaned):
            break
        if re.match(r"^am\s+\d{1,2}\.\d{1,2}\.\d{4}$", cleaned, flags=re.IGNORECASE):
            continue
        if cleaned.casefold().startswith("anmerkungen zur abstimmung"):
            continue
        notes.append(cleaned)
    return notes

def extract_digra_attachment_titles(soup) -> list[str]:  # noqa: ANN001
    titles: list[str] = []
    seen: set[str] = set()
    for link in soup.select('a[href*="document/attachment"]'):
        title = re.sub(r"\s+", " ", str(link.get("title") or link.get_text(" ", strip=True) or "")).strip()
        if not title:
            continue
        key = title.casefold()
        if key in seen:
            continue
        seen.add(key)
        titles.append(title)
    return titles



def extract_digra_subject_title(lines: list[str]) -> str:
    for index, line in enumerate(lines):
        if line.casefold().strip(" :") == "datum" and index + 2 < len(lines):
            candidate = clean_digra_title_lines(lines[index + 2 : index + 8])
            if candidate:
                return candidate
    return ""


def best_digra_title(desc_lines: list[str], result: DigraResult) -> str:
    for candidate in (
        extract_title_from_digra(desc_lines),
        result.subject_title,
        extract_title_from_source_snippet(result.source_snippet),
    ):
        title = clean_digra_display_title(candidate)
        if title and not is_role_only_title(title):
            return title
    return ""


def extract_digra_source_snippet(lines: list[str], subject_title: str = "") -> str:
    start = next((index + 2 for index, line in enumerate(lines) if line.casefold().strip(" :") == "datum"), -1)
    if start < 0:
        return ""
    snippet_lines: list[str] = []
    title_seen = False
    for line in lines[start:]:
        normalized = line.casefold().strip(" :")
        if normalized in {
            "anlagen",
            "freigaben / unterschriften",
            "beschlussvermerk",
            "materialien",
            "gemeinderats- und stadtsenatsdokumente",
        }:
            break
        cleaned = clean_digra_title_line(line)
        if not cleaned:
            continue
        if is_generic_digra_title(cleaned):
            title_seen = True
            continue
        if subject_title and cleaned.casefold() in subject_title.casefold():
            title_seen = True
            continue
        if subject_title and not title_seen:
            continue
        snippet_lines.append(cleaned)
        if len(" ".join(snippet_lines)) >= 900:
            break
    return compact_snippet(" ".join(snippet_lines))


def clean_digra_title_lines(lines: list[str]) -> str:
    parts: list[str] = []
    for line in lines:
        cleaned = clean_digra_title_line(line)
        normalized = cleaned.casefold().strip(" :")
        if not cleaned:
            break
        if normalized in {
            "anlagen",
            "freigaben / unterschriften",
            "beschlussvermerk",
            "gemeinderat",
            "materialien",
        }:
            break
        if is_digra_metadata_label(cleaned):
            continue
        if is_role_only_title(cleaned):
            continue
        if parts and is_generic_digra_title(cleaned):
            break
        if parts and len(cleaned) > 160:
            break
        if DIGRA_BODY_START_RE.match(cleaned) and parts:
            break
        parts.append(cleaned)
    while len(parts) > 1 and is_generic_digra_title(parts[0]):
        parts.pop(0)
    return " ".join(parts).strip()


def split_title_parts(value: str) -> list[str]:
    parts = [part.strip() for part in re.split(r"\s{2,}|[.;]\s+", value) if part.strip()]
    return parts or [value]


def is_generic_digra_title(value: str) -> bool:
    normalized = value.casefold().strip(" :")
    return normalized.startswith("antrag auf aufnahme eines stückes auf die tagesordnung")


def compact_snippet(value: str, limit: int = 1100) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip()
    if len(cleaned) <= limit:
        return cleaned
    return cleaned[:limit].rsplit(" ", 1)[0].strip() + " ..."


def clean_digra_title_line(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" ,;")
    cleaned = cleaned.replace("\u200b", "").strip(" ,;")
    if not cleaned or ":" not in cleaned and len(cleaned.split()) <= 1:
        return ""
    blocked = {
        "beschlussvermerk",
        "freigaben / unterschriften",
        "antrag",
        "gestellt",
    }
    return "" if cleaned.casefold() in blocked else cleaned


def extract_split_votes(note_lines: list[str], raw_result_text: str) -> list[dict[str, object]]:
    votes: list[dict[str, object]] = []
    for line in note_lines:
        match = SPLIT_VOTE_LINE_RE.match(line)
        if match is None:
            continue
        vote = {
            "subject": split_vote_subject(match.group("label")),
            "outcome": normalize_vote_outcome(match.group("modifier") or "", match.group("decision")),
            "approval": [],
            "against": [],
            "abstention": [],
            "raw_text": line,
        }
        for party_match in PARTY_NOTE_RE.finditer(line):
            apply_vote_parties(vote, party_match.group("label"), party_match.group("parties"))
        votes.append(vote)
    if votes:
        return votes
    return [
        {
            "subject": "motion",
            "outcome": "unknown",
            "approval": [],
            "against": [],
            "abstention": [],
            "raw_text": raw_result_text,
        }
    ]


def split_vote_subject(value: str) -> str:
    normalized = re.sub(r"\s+", " ", value).strip().casefold()
    if normalized == "dringlichkeit":
        return "urgency"
    if normalized.startswith("punkt"):
        return normalized.replace(" ", "_")
    if normalized in {"abänderungsantrag", "abaenderungsantrag"}:
        return "amendment"
    if normalized == "zusatzantrag":
        return "additional_motion"
    return "motion"


def aggregate_split_vote_status(votes: list[dict[str, object]]) -> str:
    outcomes = [str(vote.get("outcome", "")) for vote in votes if str(vote.get("subject", "")) != "urgency"]
    if not outcomes:
        outcomes = [str(vote.get("outcome", "")) for vote in votes]
    if any(outcome.startswith("accepted") for outcome in outcomes):
        if "accepted_majority" in outcomes:
            return "accepted_majority"
        if outcomes and all(outcome == "accepted_unanimous" for outcome in outcomes):
            return "accepted_unanimous"
        return "accepted"
    if any(outcome.startswith("rejected") for outcome in outcomes):
        return "rejected_majority" if "rejected_majority" in outcomes else "rejected"
    return outcomes[0] if outcomes else "unknown"


def format_split_result_text(votes: list[dict[str, object]]) -> str:
    blocks: list[str] = []
    for vote in votes:
        subject = split_vote_label(str(vote.get("subject", "")))
        organ = str(vote.get("organ", "") or "").strip()
        date = str(vote.get("date", "") or "").strip()
        if organ:
            subject = f"{organ} am {date}" if date else organ
        outcome = str(vote.get("outcome_text", "") or "").strip() or str(vote.get("outcome", ""))
        lines = [f"{subject}: {normalize_split_outcome_label(outcome)}"]
        approval = vote.get("approval")
        against = vote.get("against")
        abstention = vote.get("abstention")
        if isinstance(approval, list) and approval:
            lines.append(f"Zustimmung: {', '.join(str(item) for item in approval)}")
        if isinstance(against, list) and against:
            lines.append(f"Dagegen: {', '.join(str(item) for item in against)}")
        if isinstance(abstention, list) and abstention:
            lines.append(f"Enthaltung: {', '.join(str(item) for item in abstention)}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)


def split_vote_label(value: str) -> str:
    if value == "urgency":
        return "Dringlichkeit"
    point_match = re.match(r"punkt_(\d+)", value)
    if point_match:
        return f"Punkt {point_match.group(1)}"
    if value == "amendment":
        return "Abänderungsantrag"
    if value == "additional_motion":
        return "Zusatzantrag"
    return "Antrag"


def normalize_split_outcome_label(status: str) -> str:
    return {
        "accepted_unanimous": "einstimmig angenommen",
        "accepted_majority": "mehrheitlich angenommen",
        "accepted": "angenommen",
        "noted": "zur Kenntnis genommen",
        "source_available": "Quelle verfügbar",
        "rejected_majority": "mehrheitlich abgelehnt",
        "rejected": "abgelehnt",
        "assigned": "zugewiesen",
        "postponed": "vertagt",
    }.get(status, status or "unbekannt")


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
    distinctive_overlap = distinctive_token_overlap(record.title, best.title)
    if score >= MIN_GENERIC_TITLE_SCORE and (
        record.record_type != "agenda_item"
        or best.agenda_item_no == record.agenda_item_no
        or distinctive_overlap >= 2
        or (score >= 0.8 and distinctive_overlap >= 1)
    ):
        return best, score
    if record.record_type == "agenda_item" and score >= MIN_AGENDA_TITLE_SCORE and distinctive_overlap >= 2:
        return best, score
    if best.order_in_type == order_in_type and record.record_type != "agenda_item" and score >= MIN_ORDER_TITLE_SCORE:
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


def distinctive_token_overlap(left: str, right: str) -> int:
    left_tokens = distinctive_tokens(normalize_match_text(left))
    right_tokens = distinctive_tokens(normalize_match_text(right))
    exact = left_tokens & right_tokens
    fuzzy = {
        left_token
        for left_token in left_tokens - exact
        for right_token in right_tokens - exact
        if len(left_token) >= 6
        and len(right_token) >= 6
        and SequenceMatcher(None, left_token, right_token).ratio() >= 0.86
    }
    return len(exact) + len(fuzzy)


def distinctive_tokens(value: str) -> set[str]:
    return {token for token in value.split() if len(token) >= 4 and token not in GENERIC_MATCH_TOKENS}


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
                return clean_digra_display_title(value)
            following: list[str] = []
            for next_line in desc_lines[index + 1 :]:
                if ":" in next_line and not BUSINESS_NUMBER_RE.search(next_line):
                    break
                following.append(next_line)
            return clean_digra_display_title(" ".join(following).strip())
        cleaned = clean_digra_display_title(line)
        if (
            cleaned
            and not re.fullmatch(r"\d{1,3}", cleaned)
            and not BUSINESS_NUMBER_RE.fullmatch(cleaned)
            and not is_digra_metadata_label(cleaned)
            and not is_role_only_title(cleaned)
        ):
            return cleaned
    return ""


def is_digra_metadata_label(value: str) -> bool:
    normalized = re.sub(r"\s+", " ", value).casefold().strip(" :")
    if normalized in METADATA_LABELS:
        return True
    return bool(ROLE_TITLE_RE.match(normalized))


def is_role_only_title(value: str) -> bool:
    title = re.sub(r"\s+", " ", value).strip(" ,;:-")
    if not title:
        return True
    if ROLE_TITLE_RE.match(title):
        return True
    return False


def clean_digra_display_title(value: str) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip(" ,;:-")
    title = re.sub(r"^(?:Frage|Antwort)\s*:\s*", "", title, flags=re.IGNORECASE).strip(" ,;:-")
    title = re.sub(r"\bvon deiner Seite\b", "von zuständiger Seite", title, flags=re.IGNORECASE)
    title = re.sub(r"\bdeinerseits\b", "von zuständiger Seite", title, flags=re.IGNORECASE)
    if re.match(r"^(?:Sehr geehrte|Sehr geehrter|Sehr geehrtes|Werter|Werte|Liebe)\b", title, flags=re.IGNORECASE):
        return ""
    previous = ""
    while title and title != previous:
        previous = title
        title = ROLE_TITLE_PREFIX_RE.sub("", title).strip(" ,;:-")
    title = re.sub(r"^(?:Betreff|Betr\.?)\s*:?\s*", "", title, flags=re.IGNORECASE).strip(" ,;:-")
    title = re.split(
        r"\s+(?:Sehr geehrte Frau|Sehr geehrter Herr|Sehr geehrte Damen und Herren)\b",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:-")
    title = re.split(
        r"\s+(?:I\.\s+Allgemeiner\s+Teil|II\.\s+Besonderer\s+Teil|Der\s+Gemeinderat\s+hat|Frau\s+GR|Herr\s+GR|Es\s+wird)\b",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:-")
    if len(title) > 220:
        title = title[:220].rsplit(" ", 1)[0].strip(" ,;:-")
    return title


def extract_title_from_source_snippet(value: str) -> str:
    snippet = clean_digra_display_title(value)
    if not snippet:
        return ""
    if len(snippet.split()) < 2:
        return ""
    return snippet
