from graz_protocols.parser import extract_meeting_date, parse_protocol


def test_extracts_stk_record_with_status_amount_and_location():
    paragraphs = [
        "Protokoll über die ordentliche öffentliche Sitzung des Gemeinderates am 14.11.2024",
        "Tagesordnung",
        "Stk. 8) A8-055598/2023-8 Sanierung Beispielgasse Annahme Förderungsvertrag über € 52.500,-",
        "(Berichterstatterin: GR Beispiel)",
        "Originaltext des Antrages:",
        "Der Gemeinderat wolle beschließen: Dem Bericht wird zugestimmt.",
        "Der Antrag wurde einstimmig angenommen.",
    ]

    records = parse_protocol(paragraphs, "2024-11-14_Protokoll.docx")

    assert len(records) == 1
    record = records[0]
    assert record.meeting_date == "2024-11-14"
    assert record.agenda_item_no == 8
    assert record.business_numbers == ["A8-055598/2023-8"]
    assert "Sanierung Beispielgasse" in record.title
    assert record.status == "accepted_unanimous"
    assert record.amounts == ["€ 52.500,-"]
    assert record.locations == ["Beispielgasse"]
    assert len(record.source_snippet) < 601


def test_skips_table_of_contents_stk_entries():
    paragraphs = [
        "6.1\tStk. 5) A5-076766/2024/0005 Beispielpunkt\t64",
        "Tagesordnung",
        "Stk. 5) A5-076766/2024/0005 Beispielpunkt",
        "Der Antrag wurde mehrheitlich angenommen.",
    ]

    records = parse_protocol(paragraphs, "2025-01-16_Protokoll.docx")

    assert len(records) == 1
    assert records[0].agenda_item_no == 5
    assert records[0].status == "accepted_majority"


def test_extract_meeting_date_from_text_when_filename_has_no_iso_date():
    date = extract_meeting_date(
        ["Protokoll über die öffentliche Sitzung des Gemeinderates am 12 . 03 . 2026"],
        "Protokoll_12.03.2026.docx",
    )

    assert date == "2026-03-12"
