from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from pathlib import Path
import json

from .digra_import import DEFAULT_DIGRA_TOOL_PATH, digra_entries_to_records, fetch_digra_entries, list_digra_meetings
from .parser import normalize_written_submission_status
from .schema import validate_record


def update_records_with_latest_digra(
    base_records_path: Path,
    base_summary_path: Path,
    output_records_path: Path,
    output_summary_path: Path,
    *,
    tool_path: Path = DEFAULT_DIGRA_TOOL_PATH,
    limit: int = 30,
) -> dict:
    records = read_record_dicts(base_records_path)
    existing_dates = {str(record.get("meeting_date") or "") for record in records if record.get("meeting_date")}
    meetings = list_digra_meetings(tool_path, limit=limit)
    new_dates = sorted(
        {
            normalized
            for meeting in meetings
            if (normalized := normalize_digra_meeting_date(str(meeting.date))) and normalized not in existing_dates
        }
    )
    added_records: list[dict] = []
    validation_errors: list[dict[str, str]] = []
    if new_dates:
        entries = fetch_digra_entries(new_dates, tool_path=tool_path)
        added = digra_entries_to_records(entries)
        for record in added:
            errors = validate_record(record)
            validation_errors.extend({"record_id": record.record_id, "error": error} for error in errors)
        added_records = [asdict(record) for record in added]

    merged = merge_record_dicts(records, added_records)
    output_records_path.parent.mkdir(parents=True, exist_ok=True)
    output_records_path.write_text(
        "\n".join(json.dumps(record, ensure_ascii=False, sort_keys=True) for record in merged) + ("\n" if merged else ""),
        encoding="utf-8",
    )
    summary = read_summary(base_summary_path)
    summary.update(summary_for_records(merged))
    summary["digra_auto_update_checked"] = True
    summary["digra_auto_update_meetings_seen"] = len(meetings)
    summary["digra_auto_update_new_dates"] = new_dates
    summary["digra_auto_update_added_records"] = len(added_records)
    summary["digra_auto_update_validation_errors"] = validation_errors
    output_summary_path.parent.mkdir(parents=True, exist_ok=True)
    output_summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    return {
        "base_records": len(records),
        "added_records": len(added_records),
        "records_total": len(merged),
        "new_dates": new_dates,
        "validation_errors": validation_errors,
        "output_records": str(output_records_path),
        "output_summary": str(output_summary_path),
    }


def read_record_dicts(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def read_summary(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def merge_record_dicts(base: list[dict], added: list[dict]) -> list[dict]:
    normalized_base = [normalize_record_dict(record) for record in base]
    seen = {str(record.get("record_id") or "") for record in normalized_base}
    merged = list(normalized_base)
    for record in added:
        record = normalize_record_dict(record)
        record_id = str(record.get("record_id") or "")
        if record_id and record_id in seen:
            continue
        if record_id:
            seen.add(record_id)
        merged.append(record)
    return merged


def normalize_record_dict(record: dict) -> dict:
    status, status_text, raw_result_text = normalize_written_submission_status(
        str(record.get("record_type", "")),
        str(record.get("status", "")),
        str(record.get("status_text", "")),
        str(record.get("raw_result_text", "")),
    )
    if status == str(record.get("status", "")):
        return record
    normalized = dict(record)
    normalized["status"] = status
    normalized["status_text"] = status_text
    normalized["raw_result_text"] = raw_result_text
    if str(normalized.get("result_text", "")) in {"", "Unbekannt", "DIGRA-Ergebnis fehlt"}:
        normalized["result_text"] = "Verfahren: zugewiesen"
    if not normalized.get("votes"):
        normalized["votes"] = [
            {
                "subject": "procedure",
                "outcome": "assigned",
                "approval": [],
                "against": [],
                "abstention": [],
                "raw_text": raw_result_text,
            }
        ]
    return normalized


def normalize_digra_meeting_date(value: str) -> str:
    parts = value.strip().split(".")
    if len(parts) != 3:
        return ""
    day, month, year = [part.zfill(2) for part in parts]
    if len(year) != 4:
        return ""
    return f"{year}-{month}-{day}"


def summary_for_records(records: list[dict]) -> dict:
    status_counts = Counter(str(record.get("status") or "") for record in records)
    section_counts = Counter(str(record.get("section") or "unknown") for record in records)
    type_counts = Counter(str(record.get("record_type") or "") for record in records)
    file_counts = Counter(str(record.get("source_file") or "") for record in records)
    return {
        "records_total": len(records),
        "records_with_votes": sum(1 for record in records if record.get("votes")),
        "files_with_records": len(file_counts),
        "records_by_file": dict(file_counts),
        "records_by_section": dict(section_counts),
        "records_by_status": dict(status_counts),
        "records_by_type": dict(type_counts),
        "digra_results_used": sum(1 for record in records if record.get("result_source") == "digra"),
        "digra_records_matched": sum(1 for record in records if record.get("digra_url")),
        "digra_protocol_fallbacks": sum(1 for record in records if record.get("result_source") == "protokoll"),
    }
