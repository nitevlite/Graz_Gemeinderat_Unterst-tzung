from __future__ import annotations

from collections import Counter
from pathlib import Path
import json


def write_audit_report(records_path: Path, summary_path: Path | None, output_path: Path) -> None:
    records = read_jsonl(records_path)
    summary = read_json(summary_path) if summary_path and summary_path.exists() else {}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_audit_report(records, summary), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build_audit_report(records: list[dict], summary: dict) -> str:
    source_counts = Counter(record.get("result_source", "") or "unbekannt" for record in records)
    status_counts = Counter(record.get("status", "") or "unknown" for record in records)
    fallback_by_date = Counter(record.get("meeting_date", "") for record in records if record.get("result_source") == "protokoll")
    missing = [record for record in records if record.get("result_source") == "digra_fehlt"]
    low_score = [
        record
        for record in records
        if record.get("result_source") == "digra" and float(record.get("digra_match_score") or 0) < 0.44
    ]

    lines = [
        "# DIGRA-Audit",
        "",
        "## Überblick",
        "",
        f"- Einträge gesamt: {len(records)}",
        f"- DIGRA-Ergebnisse: {source_counts.get('digra', 0)}",
        f"- Protokoll-Fallbacks: {source_counts.get('protokoll', 0)}",
        f"- Ohne Ergebnis: {source_counts.get('digra_fehlt', 0)}",
        f"- DIGRA-Zuordnung: {summary.get('digra_match_strategy', '-')}",
        "",
        "## Status",
        "",
        *format_counter(status_counts),
        "",
        "## Protokoll-Fallbacks nach Datum",
        "",
        *format_counter(fallback_by_date),
        "",
        "## Ohne Ergebnis",
        "",
        *format_records(missing),
        "",
        "## DIGRA-Treffer unter 0.44",
        "",
        *format_records(low_score),
        "",
    ]
    return "\n".join(lines)


def format_counter(counter: Counter) -> list[str]:
    if not counter:
        return ["- Keine"]
    return [f"- {key}: {value}" for key, value in sorted(counter.items())]


def format_records(records: list[dict]) -> list[str]:
    if not records:
        return ["- Keine"]
    rows = []
    for record in records:
        rows.append(
            "- "
            f"{record.get('meeting_date', '-')}, "
            f"{record.get('record_type', '-')}, "
            f"Stk. {record.get('agenda_item_no', '-')}: "
            f"{compact(record.get('title', '-'))}"
            f" | DIGRA: {record.get('digra_business_number') or '-'}"
            f" | Treffer: {format_score(record.get('digra_match_score'))}"
            f" | Link: {record.get('digra_url') or '-'}"
        )
    return rows


def compact(value: str, limit: int = 130) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def format_score(value: object) -> str:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return "-"
    if score <= 0:
        return "-"
    return f"{score:.3f}"
