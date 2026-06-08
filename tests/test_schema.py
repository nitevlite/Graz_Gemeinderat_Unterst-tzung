from graz_protocols.parser import AgendaRecord
from graz_protocols.schema import SCHEMA_VERSION, validate_record


def test_validates_record_schema():
    record = AgendaRecord(
        record_id="id",
        record_type="agenda_item",
        source_file="test.docx",
        meeting_date="2026-01-22",
        section="Tagesordnung",
        agenda_item_no=1,
        business_numbers=[],
        title="Test",
        status="unknown",
        status_text="",
        result_text="Unbekannt",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.5,
    )

    assert SCHEMA_VERSION == "1.0"
    assert validate_record(record) == []


def test_rejects_invalid_record_type():
    record = AgendaRecord(
        record_id="id",
        record_type="bad",
        source_file="test.docx",
        meeting_date="2026-01-22",
        section="Tagesordnung",
        agenda_item_no=1,
        business_numbers=[],
        title="Test",
        status="unknown",
        status_text="",
        result_text="Unbekannt",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.5,
    )

    assert "record_type ungültig: bad" in validate_record(record)
