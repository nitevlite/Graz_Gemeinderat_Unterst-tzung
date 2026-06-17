import json
import hashlib
from types import SimpleNamespace

from graz_protocols.cli import main
from graz_protocols.question_pdf import parse_question_hour_pdf_bytes, parse_question_hour_text


def test_parse_question_hour_text_splits_question_answer_and_followup():
    text = """
    Gemeinderatssitzung am 16.12.2021
    Fragestellerin: GR Beispiel
    Frage: Welche Maßnahmen sind am Beispielplatz geplant?
    Antwort: Die zuständige Abteilung prüft die Situation und berichtet im Ausschuss.
    Zusatzfrage: Wird auch die Beispielgasse berücksichtigt?
    Zusatzantwort: Die Beispielgasse wird in die Prüfung aufgenommen.
    Frage: Wie ist der Zeitplan für die zweite Maßnahme?
    Antwort: Die Umsetzung ist nach der Abstimmung vorgesehen.
    """

    records = parse_question_hour_text(text, "fragestunde_2021.txt")

    assert len(records) == 2
    assert records[0].record_type == "question_hour"
    assert records[0].meeting_date == "2021-12-16"
    assert records[0].question_parts["question"] == "Welche Maßnahmen sind am Beispielplatz geplant?"
    assert records[0].question_parts["answer"].startswith("Die zuständige Abteilung")
    assert records[0].question_parts["followup_question"] == "Wird auch die Beispielgasse berücksichtigt?"
    assert records[0].question_parts["followup_answer"] == "Die Beispielgasse wird in die Prüfung aufgenommen."
    assert "Zusatzantwort" in records[0].source_snippet
    assert records[1].agenda_item_no == 2


def test_question_pdf_cli_accepts_sanitized_txt_fixture(tmp_path):
    source = tmp_path / "fragestunde_2021-12-16.txt"
    source.write_text(
        "\n".join(
            [
                "Gemeinderatssitzung am 16.12.2021",
                "Frage: Was ist am Beispielweg geplant?",
                "Antwort: Die Verwaltung prüft den Vorschlag.",
            ]
        ),
        encoding="utf-8",
    )
    output = tmp_path / "question_hours.jsonl"
    summary = tmp_path / "summary.json"

    exit_code = main(["question-pdf", str(source), "--output", str(output), "--summary", str(summary)])

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert rows[0]["record_type"] == "question_hour"
    assert rows[0]["question_parts"]["answer"] == "Die Verwaltung prüft den Vorschlag."
    assert payload["source_mode"] == "question_pdf"
    assert payload["records_total"] == 1


def test_question_pdf_cli_can_attach_original_city_archive_url(tmp_path):
    source_url = "https://www.graz.at/cms/dokumente/10157792_7768145/2ba59e85/101118_fragestunde2.pdf"
    digest = hashlib.sha1(source_url.encode("utf-8")).hexdigest()[:10]
    source = tmp_path / f"2010-11-18_Fragestunde-des-Gemeinderates_{digest}.txt"
    source.write_text(
        "\n".join(
            [
                "Gemeinderatssitzung am 18.11.2010",
                "Frage: Was ist geplant?",
                "Antwort: Die Verwaltung prüft es.",
            ]
        ),
        encoding="utf-8",
    )
    source_index = tmp_path / "city_assets.json"
    source_index.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "meeting_date": "2010-11-18",
                        "title": "Fragestunde des Gemeinderates",
                        "url": source_url,
                        "source_url": "https://www.graz.at/cms/beitrag/10134085/7768145/",
                        "kind": "protocol_document",
                    }
                ],
                "errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "question_hours.jsonl"
    summary = tmp_path / "summary.json"

    exit_code = main(
        [
            "question-pdf",
            str(source),
            "--source-index",
            str(source_index),
            "--output",
            str(output),
            "--summary",
            str(summary),
        ]
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert rows[0]["source_url"] == source_url
    assert payload["question_hour_source_urls_applied"] == 1


def test_parse_question_hour_text_splits_numbered_legacy_pdf_text():
    text = """
    Sitzung des Gemeinderates vom 18. November 2010 20
    F R A G E S T U N D E
    8) Parktarife in den Blauen Zonen
    GR. Eichberger stellt an Bgm.-Stvin. Rücker folgende Frage:
    GR. Eichberger: Wann kommt es zu dieser Erhöhung?
    Bgm.-Stvin. Rücker: Ein Vorschlag wird im Frühling diskutiert.
    GR. Eichberger: Gibt es 2011 diesbezügliche Anträge?
    Bgm.-Stvin. Rücker: Für 2011 wird ein Vorschlag entwickelt.
    9) Gemeindewohnungen ohne
    Heizmöglichkeit
    GRin. Pavlovec-Meixner stellt an StRin. Kahr folgende Frage:
    GRin. Pavlovec-Meixner: Wie viele Gemeindewohnungen verfügen über keine Heizmöglichkeit?
    StRin. Kahr: Es gibt keine Kategorie-B-Wohnung ohne Kaminanschluss.
    """

    records = parse_question_hour_text(text, "2010-11-18_fragestunde.pdf")

    assert len(records) == 2
    assert records[0].agenda_item_no == 8
    assert records[0].title == "Parktarife in den Blauen Zonen"
    assert records[0].question_parts["speaker"] == "GR. Eichberger"
    assert records[0].question_parts["respondent"] == "Bgm.-Stvin. Rücker"
    assert records[0].question_parts["question"] == "Wann kommt es zu dieser Erhöhung?"
    assert records[0].question_parts["answer"] == "Ein Vorschlag wird im Frühling diskutiert."
    assert records[0].question_parts["followup_question"] == "Gibt es 2011 diesbezügliche Anträge?"
    assert records[1].agenda_item_no == 9
    assert records[1].title == "Gemeindewohnungen ohne Heizmöglichkeit"


def test_parse_question_hour_title_drops_inline_speaker_intro():
    text = """
    Gemeinderatssitzung am 09.06.2011
    1) Aktionsprogramm gegen Armut GRin. Meißlitzer stellt an StRin. Maga Grabner folgende Frage:
    Was ist geplant?
    StRin. Maga Grabner: Die Maßnahmen werden geprüft.
    2) Unterstützung des ÖH-Kindergartens in der Hochsteingasse 16 GRin. Mag
    a Taberhofer stellt an Stadtrat Beispiel folgende Frage:
    Welche Unterstützung gibt es?
    Stadtrat Beispiel: Eine Prüfung läuft.
    """

    records = parse_question_hour_text(text, "2011-06-09_fragestunde.pdf")

    assert records[0].title == "Aktionsprogramm gegen Armut"
    assert records[1].title == "Unterstützung des ÖH-Kindergartens in der Hochsteingasse 16"
    assert records[1].question_parts["speaker"] == "GRin. Maga Taberhofer"


def test_parse_question_hour_text_reads_legacy_date_from_filename():
    records = parse_question_hour_text(
        """
        1) Trainingszentrum Weinzödl
        GRin. Jahn stellt an StR. Rüsch folgende Frage:
        Frage: Wie ist der Stand?
        Antwort: Dazu liegen Informationen vor.
        """,
        "091119_fragestunde2.pdf",
    )

    assert records[0].meeting_date == "2009-11-19"


def test_parse_question_hour_pdf_bytes_splits_numbered_archive_fragestunde(monkeypatch):
    class FakePage:
        def __init__(self, text):
            self.text = text

        def extract_text(self):
            return self.text

    class FakePdfReader:
        def __init__(self, _stream):
            self.pages = [
                FakePage(
                    """
                    Gemeinderatssitzung vom 7. Juli 2005 20
                    F R A G E S T U N D E
                    1) Weiterbestand der Beispielämter
                    GR. Beispiel stellt an Bgm. Beispiel folgende Frage:
                    GR. Beispiel: Bleiben die Beispielämter bestehen?
                    Bgm. Beispiel: Die Frage wird geprüft.
                    2) Finanzmittelbedarf der Beispielgesellschaft
                    GR. Muster stellt an StR. Beispiel folgende Frage:
                    GR. Muster: Wie hoch war der Finanzmittelbedarf?
                    StR. Beispiel: Der Betrag wird bekanntgegeben.
                    """
                )
            ]

    def fake_import_module(name):
        if name == "pypdf":
            return SimpleNamespace(PdfReader=FakePdfReader)
        raise ImportError(name)

    monkeypatch.setattr("graz_protocols.question_pdf.importlib.import_module", fake_import_module)

    records = parse_question_hour_pdf_bytes(b"%PDF-test", "050707_fragestunde2.pdf")

    assert len(records) == 2
    assert records[0].meeting_date == "2005-07-07"
    assert records[0].agenda_item_no == 1
    assert records[0].title == "Weiterbestand der Beispielämter"
    assert records[1].agenda_item_no == 2
    assert records[1].title == "Finanzmittelbedarf der Beispielgesellschaft"
