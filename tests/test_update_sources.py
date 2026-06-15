from dataclasses import dataclass
import json

from graz_protocols.digra_import import DigraEntry
from graz_protocols.update_sources import normalize_record_dict, update_records_with_latest_digra


@dataclass(frozen=True)
class FakeMeeting:
    date: str
    number: str
    title: str
    url: str


def test_update_records_with_latest_digra_merges_missing_meeting(monkeypatch, tmp_path):
    base_records = tmp_path / "base.jsonl"
    base_summary = tmp_path / "summary.json"
    output = tmp_path / "out.jsonl"
    output_summary = tmp_path / "out_summary.json"
    base_records.write_text(
        json.dumps(
            {
                "record_id": "2026-04-23-a",
                "record_type": "agenda_item",
                "meeting_date": "2026-04-23",
                "source_file": "DIGRA",
                "section": "Tagesordnung",
                "agenda_item_no": 1,
                "business_numbers": [],
                "title": "Alt",
                "status": "unknown",
                "status_text": "",
                "result_text": "Unbekannt",
                "raw_result_text": "",
                "votes": [],
                "amounts": [],
                "locations": [],
                "location_details": [],
                "source_snippet": "",
                "parser_confidence": 0.5,
                "source_url": "",
                "submitter": "",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    base_summary.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "graz_protocols.update_sources.list_digra_meetings",
        lambda tool_path, limit: [FakeMeeting("21.05.2026", "61", "Sitzung", "https://digra.graz.at/meeting?ref=x")],
    )
    monkeypatch.setattr(
        "graz_protocols.update_sources.fetch_digra_entries",
        lambda dates, tool_path: [
            DigraEntry(
                meeting_date="2026-05-21",
                meeting_number="61",
                record_type="agenda_item",
                section="Tagesordnung",
                order_in_type=1,
                agenda_item_no=1,
                business_number="",
                title="Neu",
                url="https://digra.graz.at/document?ref=y",
                status="accepted_unanimous",
                result_text="Antrag: einstimmig angenommen",
                raw_result_text="einstimmig angenommen",
                votes=[],
            )
        ],
    )

    summary = update_records_with_latest_digra(base_records, base_summary, output, output_summary)

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    assert summary["added_records"] == 1
    assert len(rows) == 2
    assert rows[-1]["meeting_date"] == "2026-05-21"


def test_update_records_with_latest_digra_is_idempotent_when_output_is_reused(monkeypatch, tmp_path):
    base_records = tmp_path / "base.jsonl"
    base_summary = tmp_path / "summary.json"
    first_output = tmp_path / "plus.jsonl"
    first_summary = tmp_path / "plus_summary.json"
    base_records.write_text(
        json.dumps(
            {
                "record_id": "2026-04-23-a",
                "record_type": "agenda_item",
                "meeting_date": "2026-04-23",
                "source_file": "DIGRA",
                "section": "Tagesordnung",
                "agenda_item_no": 1,
                "business_numbers": [],
                "title": "Alt",
                "status": "accepted_unanimous",
                "status_text": "einstimmig angenommen",
                "result_text": "Antrag: einstimmig angenommen",
                "raw_result_text": "einstimmig angenommen",
                "votes": [],
                "amounts": [],
                "locations": [],
                "location_details": [],
                "source_snippet": "",
                "parser_confidence": 0.5,
                "source_url": "",
                "submitter": "",
                "question_parts": {},
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    base_summary.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        "graz_protocols.update_sources.list_digra_meetings",
        lambda tool_path, limit: [FakeMeeting("21.05.2026", "61", "Sitzung", "https://digra.graz.at/meeting?ref=x")],
    )
    monkeypatch.setattr(
        "graz_protocols.update_sources.fetch_digra_entries",
        lambda dates, tool_path: [
            DigraEntry(
                meeting_date="2026-05-21",
                meeting_number="61",
                record_type="agenda_item",
                section="Tagesordnung",
                order_in_type=1,
                agenda_item_no=1,
                business_number="",
                title="Neu",
                url="https://digra.graz.at/document?ref=y",
                status="accepted_unanimous",
                result_text="Antrag: einstimmig angenommen",
                raw_result_text="einstimmig angenommen",
                votes=[],
            )
        ],
    )

    first = update_records_with_latest_digra(base_records, base_summary, first_output, first_summary)
    second = update_records_with_latest_digra(first_output, first_summary, first_output, first_summary)

    rows = [json.loads(line) for line in first_output.read_text(encoding="utf-8").splitlines()]
    assert first["added_records"] == 1
    assert second["added_records"] == 0
    assert second["new_dates"] == []
    assert len(rows) == 2


def test_normalize_record_dict_assigns_unclear_written_submission():
    record = {
        "record_id": "written-unknown",
        "record_type": "written_question",
        "status": "unknown",
        "status_text": "",
        "result_text": "Unbekannt",
        "raw_result_text": "",
        "votes": [],
    }

    normalized = normalize_record_dict(record)

    assert normalized["status"] == "assigned"
    assert normalized["result_text"] == "Verfahren: zugewiesen"
    assert normalized["votes"][0]["outcome"] == "assigned"
