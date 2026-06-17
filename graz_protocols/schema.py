from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .parser import AgendaRecord


SCHEMA_VERSION = "1.4"
VALID_RECORD_TYPES = {
    "agenda_item",
    "archive_agenda_item",
    "archive_source",
    "attendance_list",
    "communication",
    "amendment_motion",
    "additional_motion",
    "urgent_motion",
    "written_question",
    "written_motion",
    "question_hour",
}
VALID_STATUSES = {
    "accepted",
    "accepted_majority",
    "accepted_unanimous",
    "assigned",
    "noted",
    "postponed",
    "pending",
    "rejected",
    "rejected_majority",
    "source_available",
    "unknown",
}
REQUIRED_FIELDS = {
    "record_id": str,
    "record_type": str,
    "source_file": str,
    "meeting_date": str,
    "section": str,
    "agenda_item_no": int,
    "business_numbers": list,
    "title": str,
    "status": str,
    "status_text": str,
    "result_text": str,
    "raw_result_text": str,
    "votes": list,
    "amounts": list,
    "locations": list,
    "location_details": list,
    "source_snippet": str,
    "parser_confidence": float,
    "source_url": str,
    "source_page": int,
    "local_source_url": str,
    "submitter": str,
    "addressee": str,
    "question_parts": dict,
    "attachment_titles": list,
}


def validate_record(record: AgendaRecord) -> list[str]:
    data = asdict(record)
    errors: list[str] = []
    for field_name, expected_type in REQUIRED_FIELDS.items():
        if field_name not in data:
            errors.append(f"Pflichtfeld fehlt: {field_name}")
            continue
        value = data[field_name]
        if expected_type is float and isinstance(value, int):
            continue
        if not isinstance(value, expected_type):
            errors.append(f"{field_name}: erwartet {expected_type.__name__}, erhalten {type(value).__name__}")
    if data.get("record_type") not in VALID_RECORD_TYPES:
        errors.append(f"record_type ungültig: {data.get('record_type')}")
    if data.get("status") not in VALID_STATUSES:
        errors.append(f"status ungültig: {data.get('status')}")
    confidence = data.get("parser_confidence")
    if isinstance(confidence, int | float) and not 0 <= confidence <= 1:
        errors.append("parser_confidence muss zwischen 0 und 1 liegen")
    errors.extend(validate_votes(data.get("votes", [])))
    errors.extend(validate_location_details(data.get("location_details", [])))
    return errors


def validate_votes(votes: Any) -> list[str]:
    if not isinstance(votes, list):
        return ["votes muss eine Liste sein"]
    errors: list[str] = []
    for index, vote in enumerate(votes):
        if not isinstance(vote, dict):
            errors.append(f"votes[{index}] muss ein Objekt sein")
            continue
        for field_name in ("subject", "outcome", "approval", "against", "abstention", "raw_text"):
            if field_name not in vote:
                errors.append(f"votes[{index}].{field_name} fehlt")
        for field_name in ("approval", "against", "abstention"):
            if field_name in vote and not isinstance(vote[field_name], list):
                errors.append(f"votes[{index}].{field_name} muss eine Liste sein")
    return errors


def validate_location_details(locations: Any) -> list[str]:
    if not isinstance(locations, list):
        return ["location_details muss eine Liste sein"]
    errors: list[str] = []
    for index, location in enumerate(locations):
        if not isinstance(location, dict):
            errors.append(f"location_details[{index}] muss ein Objekt sein")
            continue
        for field_name in ("type", "value", "context", "confidence"):
            if field_name not in location:
                errors.append(f"location_details[{index}].{field_name} fehlt")
    return errors
