from graz_protocols.archive_communication_pdf import parse_archive_communication_text


def test_parse_archive_communication_text_extracts_numbered_mayor_messages():
    text = """
    Gemeinderatssitzung vom 19. November 2009
    Mitteilungen des Bürgermeisters
    1) Verwaltungspreis
    Bgm. Mag. Nagl: Die Stadt Graz wurde ausgezeichnet.
    2) Protokollgenehmigung
    Bgm. Mag. Nagl: Das Protokoll wurde überprüft.
    """

    records = parse_archive_communication_text(text, "091119_mitteilungen.pdf", source_url="https://example.test/mitteilungen.pdf")

    assert [record.record_type for record in records] == ["communication", "communication"]
    assert [record.title for record in records] == ["Verwaltungspreis", "Protokollgenehmigung"]
    assert records[0].meeting_date == "2009-11-19"
    assert records[0].status == "noted"
    assert records[0].submitter == "Bgm. Mag. Nagl"
    assert records[0].source_url == "https://example.test/mitteilungen.pdf"
