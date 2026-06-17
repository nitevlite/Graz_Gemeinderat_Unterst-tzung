import json
import sqlite3

from graz_protocols.parser import AgendaRecord
from graz_protocols.search_index import search_sqlite
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
        source_snippet="Kurzer lokaler Ausschnitt zur barrierefreien Haltestelle.",
        parser_confidence=1.0,
        submitter="GR Beispiel, KPÖ",
    )

    write_sqlite(db_path, [record], {"records_total": 1})

    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT datum, typ, stueck_nr, titel, ergebnis, geschaeftszahlen_json, abstimmungen_json,
                   ergebnisquelle, digra_url, digra_einlagezahl, protokoll_ergebnis, digra_trefferwert, source_url,
                   einbringer
            FROM eintraege
            """
        ).fetchone()
        version = connection.execute("SELECT wert FROM meta WHERE schluessel = 'schema_version'").fetchone()[0]
        summary = connection.execute(
            "SELECT wert_json FROM zusammenfassung WHERE schluessel = 'records_total'"
        ).fetchone()[0]
        normalized_count = connection.execute("SELECT count(*) FROM records").fetchone()[0]
        vote_count = connection.execute("SELECT count(*) FROM votes").fetchone()[0]
        fts_count = connection.execute("SELECT count(*) FROM eintraege_fts").fetchone()[0]
        search_document_count = connection.execute("SELECT count(*) FROM search_documents").fetchone()[0]
        search_chunk_rows = connection.execute(
            "SELECT chunk_id, feld, gewicht, text FROM search_chunks ORDER BY chunk_id"
        ).fetchall()
        search_fts_count = connection.execute("SELECT count(*) FROM search_fts").fetchone()[0]

    assert row[0] == "2026-04-23"
    assert row[1] == "agenda_item"
    assert row[2] == 7
    assert row[3] == "Teststück"
    assert row[4] == "Antrag: mehrheitlich angenommen\nDagegen: KFG"
    assert json.loads(row[5]) == ["A8-1"]
    assert json.loads(row[6])[0]["against"] == ["KFG"]
    assert row[7] == "protokoll"
    assert row[8] == ""
    assert row[9] == ""
    assert row[10] == ""
    assert row[11] == 0.0
    assert row[12] == ""
    assert row[13] == "GR Beispiel, KPÖ"
    assert version == "7"
    assert json.loads(summary) == 1
    assert normalized_count == 1
    assert vote_count == 1
    assert fts_count == 1
    assert search_document_count == 1
    assert search_fts_count == len(search_chunk_rows)
    assert ("2026-test:titel", "titel", 5.0, "Teststück") in search_chunk_rows
    assert any(row[0] == "2026-test:quellenausschnitt" and "barrierefreien Haltestelle" in row[3] for row in search_chunk_rows)
    assert any(row[0] == "2026-test:einbringer" and row[3] == "GR Beispiel, KPÖ" for row in search_chunk_rows)


def test_search_sqlite_finds_source_snippets_and_structured_fields(tmp_path):
    db_path = tmp_path / "eintraege.sqlite"
    records = [
        AgendaRecord(
            record_id="2026-haltestelle",
            record_type="written_motion",
            source_file="DIGRA",
            meeting_date="2026-05-21",
            section="Anträge",
            agenda_item_no=3,
            business_numbers=["A10/BD-123/2026"],
            title="Barrierefreie Haltestelle in Waltendorf",
            status="assigned",
            status_text="zugewiesen",
            result_text="Verfahren: zugewiesen",
            raw_result_text="Der geschäftsordnungsmäßigen Behandlung zugewiesen.",
            votes=[],
            amounts=[],
            locations=["Waltendorf"],
            source_snippet="Die zuständigen Stellen sollen einen barrierefreien Umbau der Haltestelle prüfen.",
            parser_confidence=0.9,
            submitter="GR Beispiel, KPÖ",
            addressee="Stadtrat Manfred Eber (KPÖ)",
            source_url="https://www.graz.at/beispiel",
        ),
        AgendaRecord(
            record_id="2026-budget",
            record_type="agenda_item",
            source_file="DIGRA",
            meeting_date="2026-05-21",
            section="Tagesordnung",
            agenda_item_no=4,
            business_numbers=["A8-999/2026"],
            title="Budgetumschichtung Kultur",
            status="accepted_unanimous",
            status_text="einstimmig angenommen",
            result_text="Antrag: einstimmig angenommen",
            raw_result_text="Der Antrag wurde einstimmig angenommen.",
            votes=[],
            amounts=["€ 5.000,-"],
            locations=[],
            source_snippet="Mittel werden für Kulturarbeit umgeschichtet.",
            parser_confidence=0.9,
        ),
    ]
    write_sqlite(db_path, records, {"records_total": 2})

    snippet_results = search_sqlite(db_path, "barrierefreier Umbau Haltestelle", limit=5)
    submitter_results = search_sqlite(db_path, "GR Beispiel KPÖ Waltendorf", limit=5)
    addressee_results = search_sqlite(db_path, "Manfred Eber Stadtrat", limit=5)
    business_results = search_sqlite(db_path, "A10 BD 123", limit=5)

    assert snippet_results[0].record_id == "2026-haltestelle"
    assert "quellenausschnitt" in snippet_results[0].matched_fields
    assert submitter_results[0].record_id == "2026-haltestelle"
    assert {"einbringer", "orte"} & set(submitter_results[0].matched_fields)
    assert addressee_results[0].record_id == "2026-haltestelle"
    assert "adressat" in addressee_results[0].matched_fields
    assert business_results[0].record_id == "2026-haltestelle"
    assert "geschaeftszahlen" in business_results[0].matched_fields
