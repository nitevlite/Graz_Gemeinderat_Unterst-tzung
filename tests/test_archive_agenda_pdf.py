from graz_protocols.archive_agenda_pdf import parse_archive_agenda_lines, parse_archive_agenda_text


def test_parse_archive_agenda_text_extracts_numbered_items_from_tagesordnung_pdf_text():
    text = """
    Gemeinderatssitzung (Budget) vom 12. Dezember 2005 12
    T a g e s o r d n u n g
    Ö f f e n t l i c h
    Berichterstatterin: StR. Mag. Dr. Riedler
    2) A 8 - K 70/2005-1 Haushaltsanalyse 2006
    3) A 8 - K 70/2005-1 Voranschlag 2006Gemeinderatssitzung (Budget) vom 12. Dezember 2005 13
    StR. Mag. Dr. Riedler: Meine sehr verehrten Damen und Herren.
    """

    records = parse_archive_agenda_text(
        text,
        "051212_tagesordnung.pdf",
        source_url="https://www.graz.at/cms/dokumente/10043514_7768145/d8014535/051212_tagesordnung.pdf",
    )

    assert [record.agenda_item_no for record in records] == [2, 3]
    assert records[0].record_type == "archive_agenda_item"
    assert records[0].meeting_date == "2005-12-12"
    assert records[0].business_numbers == ["A 8 - K 70/2005-1"]
    assert records[0].title == "Haushaltsanalyse 2006"
    assert records[0].submitter == "StR. Mag. Dr. Riedler"
    assert records[0].status == "source_available"
    assert "Beschlussergebnis" in records[0].result_text
    assert records[1].title == "Voranschlag 2006"


def test_parse_archive_agenda_lines_adds_source_page_fragment():
    lines = [
        (1, "Gemeinderatssitzung vom 19. Oktober 2023"),
        (2, "10) A 10/BD-12345/2023 Stadion Graz-Liebenau Projektgenehmigung"),
    ]

    records = parse_archive_agenda_lines(lines, "231019_tagesordnung.pdf", source_url="https://example.test/tagesordnung.pdf")

    assert records[0].meeting_date == "2023-10-19"
    assert records[0].source_url == "https://example.test/tagesordnung.pdf#page=2"
    assert records[0].title == "Stadion Graz-Liebenau Projektgenehmigung"
