from graz_protocols.parser import ParserParagraph, extract_meeting_date, parse_protocol


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
    assert record.result_text == "Antrag: einstimmig angenommen"
    assert record.raw_result_text == "Der Antrag wurde einstimmig angenommen."
    assert record.votes[0]["outcome"] == "accepted_unanimous"
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


def test_extracts_written_question_heading_without_stk_number():
    paragraphs = [
        ParserParagraph("Protokoll über die öffentliche Sitzung des Gemeinderates am 14.11.2024", "Normal", 1),
        ParserParagraph("Anfragen (schriftlich)", "Heading1", 2),
        ParserParagraph("Aufträge an Beispiel Sicherheitsdienst GmbH", "Heading2", 3),
        ParserParagraph("(Berichterstatter: KlObm Beispiel, KFG)", "Normal", 4),
        ParserParagraph("Originaltext der Anfrage:", "Normal", 5),
        ParserParagraph("Welche Aufträge wurden vergeben?", "Normal", 6),
        ParserParagraph("Der geschäftsordnungsmäßigen Behandlung zugewiesen.", "Normal", 7),
    ]

    records = parse_protocol(paragraphs, "2024-11-14_Protokoll.docx")

    assert len(records) == 1
    assert records[0].record_type == "written_question"
    assert records[0].section == "Anfragen (schriftlich)"
    assert records[0].title == "Aufträge an Beispiel Sicherheitsdienst GmbH"
    assert records[0].status == "assigned"
    assert records[0].result_text == "Verfahren: zugewiesen"
    assert records[0].raw_result_text == "Der geschäftsordnungsmäßigen Behandlung zugewiesen."


def test_uses_docx_heading_style_to_skip_toc_entries():
    paragraphs = [
        ParserParagraph("6.1\tStk. 5) A5-076766/2024/0005 Beispielpunkt\t64", "TOC2", 1),
        ParserParagraph("Tagesordnung", "Heading1", 2),
        ParserParagraph("Stk. 5) A5-076766/2024/0005 Beispielpunkt", "Heading2", 3),
        ParserParagraph("Der Antrag wurde einstimmig angenommen.", "Normal", 4),
    ]

    records = parse_protocol(paragraphs, "2025-01-16_Protokoll.docx")

    assert len(records) == 1
    assert records[0].record_type == "agenda_item"
    assert records[0].status == "accepted_unanimous"


def test_prefers_formal_result_over_words_in_speech():
    paragraphs = [
        ParserParagraph("Dringlichkeitsanträge", "Heading1", 1),
        ParserParagraph("SOS Öffentlicher Verkehr", "Heading2", 2),
        ParserParagraph("In meiner Rede sage ich, dass etwas angenommen werden könnte.", "Normal", 3),
        ParserParagraph("Der Antrag wurde mehrheitlich abgelehnt.", "Normal", 4),
        ParserParagraph("Zustimmung: KFG", "Normal", 5),
        ParserParagraph("Dagegen: KPÖ, SPÖ, Grüne", "Normal", 6),
    ]

    records = parse_protocol(paragraphs, "2026-04-23_Protokoll.docx")

    assert len(records) == 1
    assert records[0].status == "rejected_majority"
    assert "Antrag: mehrheitlich abgelehnt" in records[0].result_text
    assert "Zustimmung: KFG" in records[0].result_text
    assert "Dagegen: KPÖ, SPÖ, Grüne" in records[0].result_text
    assert "Der Antrag wurde mehrheitlich abgelehnt." in records[0].raw_result_text


def test_classifies_legacy_mehrstimmig_as_majority():
    paragraphs = [
        ParserParagraph("Tagesordnung", "Heading1", 1),
        ParserParagraph("Stk. 16) A8-018561/2006-134 Kunsthaus Graz GmbH", "Heading2", 2),
        ParserParagraph("Der Antrag wurde mehrstimmig angenommen", "Normal", 3),
    ]

    records = parse_protocol(paragraphs, "2025-03-20_Protokoll.docx")

    assert records[0].status == "accepted_majority"
    assert records[0].result_text == "Antrag: mehrheitlich angenommen"


def test_extracts_parenthetical_against_parties():
    paragraphs = [
        ParserParagraph("Tagesordnung", "Heading1", 1),
        ParserParagraph("Stk. 5) 2804/1 Jahresabschluss 2025", "Heading2", 2),
        ParserParagraph("Der Antrag wurde mehrstimmig angenommen (Gegen: KFG, NEOS, FPÖ).", "Normal", 3),
    ]

    records = parse_protocol(paragraphs, "2026-04-23_Protokoll.docx")

    assert records[0].result_text == "Antrag: mehrheitlich angenommen\nDagegen: KFG, NEOS, FPÖ"
    assert records[0].votes[0]["against"] == ["KFG", "NEOS", "FPÖ"]
    assert records[0].raw_result_text == "Der Antrag wurde mehrstimmig angenommen (Gegen: KFG, NEOS, FPÖ)."


def test_extracts_parenthetical_against_parties_without_colon():
    paragraphs = [
        ParserParagraph("Tagesordnung", "Heading1", 1),
        ParserParagraph("Stk. 6) 2805/1 Voranschlag 2026", "Heading2", 2),
        ParserParagraph("Der Antrag wurde mehrstimmig angenommen (Gegen ÖVP, NEOS, FPÖ, Eustacchio).", "Normal", 3),
    ]

    records = parse_protocol(paragraphs, "2026-04-23_Protokoll.docx")

    assert records[0].result_text == "Antrag: mehrheitlich angenommen\nDagegen: ÖVP, NEOS, FPÖ, Eustacchio"
    assert records[0].votes[0]["against"] == ["ÖVP", "NEOS", "FPÖ", "Eustacchio"]


def test_extracts_following_against_line_without_colon():
    paragraphs = [
        ParserParagraph("Tagesordnung", "Heading1", 1),
        ParserParagraph("Stk. 7) 2806/1 Gebühren 2026", "Heading2", 2),
        ParserParagraph("Der Antrag wurde mehrstimmig angenommen.", "Normal", 3),
        ParserParagraph("Gegen ÖVP, NEOS, FPÖ", "Normal", 4),
    ]

    records = parse_protocol(paragraphs, "2026-04-23_Protokoll.docx")

    assert records[0].result_text == "Antrag: mehrheitlich angenommen\nDagegen: ÖVP, NEOS, FPÖ"
    assert records[0].votes[0]["against"] == ["ÖVP", "NEOS", "FPÖ"]
