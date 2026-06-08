import json
import sqlite3

from graz_protocols.parser import AgendaRecord
from graz_protocols.sqlite_export import write_sqlite


def test_writes_records_to_sqlite(tmp_path):
    db_path = tmp_path / "eintraege.sqlite"
    record = AgendaRecord(
        record_id="2026-test",
        record_type="agenda_item",
        source_file="2026-04-23_Protokoll.docx",
        meeting_date="2026-04-23",
        section="Tagesordnung",
        agenda_item_no=7,
        business_numbers=["A8-1"],
        title="Teststück",
        status="accepted_majority",
        status_text="mehrheitlich angenommen",
        result_text="Antrag: mehrheitlich angenommen\nDagegen: KFG",
        raw_result_text="Der Antrag wurde mehrstimmig angenommen (Gegen KFG).",
        votes=[
            {
                "subject": "motion",
                "outcome": "accepted_majority",
                "approval": [],
                "against": ["KFG"],
                "abstention": [],
                "raw_text": "Der Antrag wurde mehrstimmig angenommen (Gegen KFG).",
            }
        ],
        amounts=["€ 1.000,-"],
        locations=["Beispielgasse"],
        source_snippet="Kurzer lokaler Ausschnitt",
        parser_confidence=1.0,
    )

    write_sqlite(db_path, [record], {"records_total": 1})

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT datum, typ, stueck_nr, titel, ergebnis, geschaeftszahlen_json, abstimmungen_json
            FROM eintraege
            """
        ).fetchone()
        version = connection.execute("SELECT wert FROM meta WHERE schluessel = 'schema_version'").fetchone()[0]
        summary = connection.execute(
            "SELECT wert_json FROM zusammenfassung WHERE schluessel = 'records_total'"
        ).fetchone()[0]

    assert row[0] == "2026-04-23"
    assert row[1] == "agenda_item"
    assert row[2] == 7
    assert row[3] == "Teststück"
    assert row[4] == "Antrag: mehrheitlich angenommen\nDagegen: KFG"
    assert json.loads(row[5]) == ["A8-1"]
    assert json.loads(row[6])[0]["against"] == ["KFG"]
    assert version == "1"
    assert json.loads(summary) == 1
