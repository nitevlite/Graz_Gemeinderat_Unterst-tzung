from graz_protocols.archive_question_pdf import parse_archive_question_lines, parse_archive_question_text


def test_parse_archive_question_text_uses_numbered_subject_as_title():
    text = """
    Gemeinderatssitzung vom 22. April 2004 46
    Anfragen an den Bürgermeister
    1) Eintrittspreise für Grazer Freibäder
    GR. Hohensinner stellt folgende Anfrage:
    GR. Hohensinner: Warum sind die Eintrittspreise höher als in Wien?
    Bgm. Mag. Nagl: Ich werde mit den Stadtwerken Gespräche führen.
    2) Ohne das No Problem Musiktherapiezentrum hat Graz ein Problem
    GRin. Mag a Beispiel stellt folgende Anfrage:
    GRin. Maga Beispiel: Wie wird die Zukunft gesichert?
    Bgm. Mag. Nagl: Wir prüfen eine Lösung.
    """

    records = parse_archive_question_text(text, "2004-04-22_anfragen.pdf", source_url="https://example.test/anfragen.pdf")

    assert len(records) == 2
    assert records[0].record_type == "written_question"
    assert records[0].agenda_item_no == 1
    assert records[0].title == "Eintrittspreise für Grazer Freibäder"
    assert records[0].submitter == "GR. Hohensinner"
    assert records[0].source_url == "https://example.test/anfragen.pdf"
    assert records[1].title == "Ohne das No Problem Musiktherapiezentrum hat Graz ein Problem"
    assert records[1].submitter == "GRin. Maga Beispiel"


def test_parse_archive_question_lines_adds_pdf_page_fragment_to_source_url():
    lines = [
        (2, "Gemeinderatssitzung vom 22. April 2004 46"),
        (2, "1) Eintrittspreise für Grazer Freibäder"),
        (2, "GR. Hohensinner stellt folgende Anfrage:"),
        (2, "GR. Hohensinner: Warum sind die Eintrittspreise höher?"),
        (3, "Bgm. Mag. Nagl: Ich werde Gespräche führen."),
        (4, "2) Erhaltung des Pammerbades"),
        (4, "GR. Beispiel stellt folgende Anfrage:"),
        (4, "GR. Beispiel: Was ist geplant?"),
    ]

    records = parse_archive_question_lines(lines, "2004-04-22_anfragen.pdf", source_url="https://example.test/anfragen.pdf")

    assert records[0].source_url == "https://example.test/anfragen.pdf#page=2"
    assert records[1].source_url == "https://example.test/anfragen.pdf#page=4"
