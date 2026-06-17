from argparse import Namespace

from graz_protocols.answers import answer_sqlite
from graz_protocols.cli import run_answer
from graz_protocols.parser import AgendaRecord
from graz_protocols.sqlite_export import write_sqlite


def test_answer_sqlite_separates_council_decisions_from_committee_status(tmp_path):
    db_path = tmp_path / "eintraege.sqlite"
    write_sqlite(db_path, answer_records(), {"records_total": 3})

    answer = answer_sqlite(db_path, "Anrainerparken St. Leonhard beschlossen", limit=10)

    assert "Gemeinderat beschlossen oder angenommen" in answer
    assert "Vorberatung im Ausschuss" in answer
    assert "nicht als Gemeinderatsbeschluss" in answer
    assert "Kostenlose lokale Antwort" not in answer
    assert "KI-Modell" in answer
    assert "[1]" in answer


def test_run_answer_prints_local_answer(tmp_path, capsys):
    db_path = tmp_path / "eintraege.sqlite"
    write_sqlite(db_path, answer_records(), {"records_total": 3})

    exit_code = run_answer(
        Namespace(sqlite=db_path, query="Anrainerparken St. Leonhard", limit=10, per_group=3)
    )
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "Kurzantwort" in output
    assert "Gemeinderat beschlossen oder angenommen" in output
    assert "Die Antwort verwendet nur den lokalen SQLite/FTS-Index" in output


def answer_records() -> list[AgendaRecord]:
    return [
        AgendaRecord(
            record_id="accepted-parking",
            record_type="agenda_item",
            source_file="DIGRA",
            meeting_date="2026-06-05",
            section="Tagesordnung",
            agenda_item_no=1,
            business_numbers=["959/1"],
            title="Anrainerparken St. Leonhard",
            status="accepted_majority",
            status_text="mehrheitlich angenommen",
            result_text="Antrag: mehrheitlich angenommen",
            raw_result_text="mehrheitlich angenommen",
            votes=[],
            amounts=[],
            locations=["St. Leonhard"],
            source_snippet="Der Gemeinderat behandelt Anrainerparken in St. Leonhard.",
            parser_confidence=1.0,
            digra_url="https://digra.graz.at/document?ref=accepted",
        ),
        AgendaRecord(
            record_id="committee-parking",
            record_type="agenda_item",
            source_file="DIGRA",
            meeting_date="2026-05-20",
            section="Tagesordnung",
            agenda_item_no=2,
            business_numbers=["958/1"],
            title="Bürgerbeteiligung Anrainerparken St. Leonhard",
            status="accepted_unanimous",
            status_text="einstimmig angenommen",
            result_text="Ausschuss am 20.05.2026: einstimmig angenommen",
            raw_result_text="Ausschuss am 20.05.2026: einstimmig angenommen",
            votes=[],
            amounts=[],
            locations=["St. Leonhard"],
            source_snippet="Im Ausschuss wurde die Bürgerbeteiligung zu Anrainerparken vorberaten.",
            parser_confidence=1.0,
            digra_url="https://digra.graz.at/document?ref=committee",
        ),
        AgendaRecord(
            record_id="open-parking",
            record_type="written_motion",
            source_file="DIGRA",
            meeting_date="2026-04-10",
            section="Anträge",
            agenda_item_no=3,
            business_numbers=["957/1"],
            title="Antrag auf Prüfung von Bewohnerparken",
            status="assigned",
            status_text="zugewiesen",
            result_text="Verfahren: zugewiesen",
            raw_result_text="zugewiesen",
            votes=[],
            amounts=[],
            locations=["St. Leonhard"],
            source_snippet="Der Antrag fordert eine Prüfung von Bewohnerparken und Parkzonen.",
            parser_confidence=0.9,
            digra_url="https://digra.graz.at/document?ref=open",
        ),
    ]
