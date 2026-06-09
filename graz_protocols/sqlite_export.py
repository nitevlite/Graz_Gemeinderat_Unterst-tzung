from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import shutil
import sqlite3
import tempfile
import uuid

from .parser import AgendaRecord


SCHEMA_VERSION = 6


def write_sqlite(path: Path, records: list[AgendaRecord], summary: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_dir = Path(tempfile.gettempdir()) / "graz_protocols_sqlite_work"
    temporary_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = temporary_dir / f"{uuid.uuid4().hex}-{path.name}"
    connection = sqlite3.connect(temporary_path)
    try:
        connection.execute("PRAGMA journal_mode = DELETE")
        connection.execute("PRAGMA foreign_keys = ON")
        create_schema(connection)
        clear_existing_data(connection)
        insert_summary(connection, summary)
        insert_records(connection, records)
        connection.commit()
    finally:
        connection.close()
    shutil.copyfile(temporary_path, path)
    unlink_if_possible(temporary_path)
    unlink_if_possible(temporary_path.with_name(f"{temporary_path.name}-journal"))
    unlink_if_possible(path.with_name(f"{path.name}-journal"))
    unlink_if_possible(path.with_name(f"{path.name}.tmp"))
    unlink_if_possible(path.with_name(f"{path.name}.tmp-journal"))


def unlink_if_possible(path: Path) -> None:
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass


def create_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
          schluessel TEXT PRIMARY KEY,
          wert TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS eintraege (
          eintrag_id TEXT PRIMARY KEY,
          datum TEXT NOT NULL,
          typ TEXT NOT NULL,
          quelldatei TEXT NOT NULL,
          abschnitt TEXT NOT NULL,
          stueck_nr INTEGER NOT NULL,
          geschaeftszahlen_json TEXT NOT NULL,
          titel TEXT NOT NULL,
          status TEXT NOT NULL,
          status_text TEXT NOT NULL,
          ergebnis TEXT NOT NULL,
          roh_ergebnis TEXT NOT NULL,
          abstimmungen_json TEXT NOT NULL,
          betraege_json TEXT NOT NULL,
          orte_json TEXT NOT NULL,
          quellenausschnitt TEXT NOT NULL,
          parser_sicherheit REAL NOT NULL,
          ergebnisquelle TEXT NOT NULL,
          digra_url TEXT NOT NULL,
          digra_einlagezahl TEXT NOT NULL,
          protokoll_ergebnis TEXT NOT NULL,
          digra_trefferwert REAL NOT NULL,
          source_url TEXT NOT NULL,
          einbringer TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS meetings (
          datum TEXT PRIMARY KEY,
          eintraege INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS records (
          eintrag_id TEXT PRIMARY KEY,
          datum TEXT NOT NULL,
          typ TEXT NOT NULL,
          titel TEXT NOT NULL,
          status TEXT NOT NULL,
          ergebnisquelle TEXT NOT NULL,
          FOREIGN KEY (eintrag_id) REFERENCES eintraege(eintrag_id)
        );

        CREATE TABLE IF NOT EXISTS business_numbers (
          eintrag_id TEXT NOT NULL,
          wert TEXT NOT NULL,
          FOREIGN KEY (eintrag_id) REFERENCES eintraege(eintrag_id)
        );

        CREATE TABLE IF NOT EXISTS amounts (
          eintrag_id TEXT NOT NULL,
          wert TEXT NOT NULL,
          FOREIGN KEY (eintrag_id) REFERENCES eintraege(eintrag_id)
        );

        CREATE TABLE IF NOT EXISTS locations (
          eintrag_id TEXT NOT NULL,
          typ TEXT NOT NULL,
          wert TEXT NOT NULL,
          kontext TEXT NOT NULL,
          confidence REAL NOT NULL,
          FOREIGN KEY (eintrag_id) REFERENCES eintraege(eintrag_id)
        );

        CREATE TABLE IF NOT EXISTS votes (
          eintrag_id TEXT NOT NULL,
          subject TEXT NOT NULL,
          outcome TEXT NOT NULL,
          approval_json TEXT NOT NULL,
          against_json TEXT NOT NULL,
          abstention_json TEXT NOT NULL,
          FOREIGN KEY (eintrag_id) REFERENCES eintraege(eintrag_id)
        );

        CREATE TABLE IF NOT EXISTS source_spans (
          eintrag_id TEXT PRIMARY KEY,
          quellenausschnitt TEXT NOT NULL,
          roh_ergebnis TEXT NOT NULL,
          FOREIGN KEY (eintrag_id) REFERENCES eintraege(eintrag_id)
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS eintraege_fts USING fts5(
          titel,
          ergebnis,
          geschaeftszahlen,
          orte,
          content=''
        );

        CREATE INDEX IF NOT EXISTS idx_eintraege_datum ON eintraege(datum);
        CREATE INDEX IF NOT EXISTS idx_eintraege_typ ON eintraege(typ);
        CREATE INDEX IF NOT EXISTS idx_eintraege_status ON eintraege(status);
        CREATE INDEX IF NOT EXISTS idx_eintraege_abschnitt ON eintraege(abschnitt);
        CREATE INDEX IF NOT EXISTS idx_eintraege_stueck ON eintraege(datum, stueck_nr);
        CREATE INDEX IF NOT EXISTS idx_business_numbers_wert ON business_numbers(wert);
        CREATE INDEX IF NOT EXISTS idx_locations_wert ON locations(wert);
        CREATE INDEX IF NOT EXISTS idx_votes_outcome ON votes(outcome);

        CREATE TABLE IF NOT EXISTS zusammenfassung (
          schluessel TEXT PRIMARY KEY,
          wert_json TEXT NOT NULL
        );
        """
    )


def clear_existing_data(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM eintraege")
    connection.execute("DELETE FROM meetings")
    connection.execute("DELETE FROM records")
    connection.execute("DELETE FROM business_numbers")
    connection.execute("DELETE FROM amounts")
    connection.execute("DELETE FROM locations")
    connection.execute("DELETE FROM votes")
    connection.execute("DELETE FROM source_spans")
    connection.execute("DELETE FROM eintraege_fts")
    connection.execute("DELETE FROM zusammenfassung")
    connection.execute("DELETE FROM meta")
    connection.execute(
        "INSERT INTO meta (schluessel, wert) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )


def insert_summary(connection: sqlite3.Connection, summary: dict) -> None:
    rows = [(key, json.dumps(value, ensure_ascii=False, sort_keys=True)) for key, value in sorted(summary.items())]
    connection.executemany("INSERT INTO zusammenfassung (schluessel, wert_json) VALUES (?, ?)", rows)


def insert_records(connection: sqlite3.Connection, records: list[AgendaRecord]) -> None:
    rows = [record_row(record) for record in records]
    connection.executemany(
        """
        INSERT INTO eintraege (
          eintrag_id,
          datum,
          typ,
          quelldatei,
          abschnitt,
          stueck_nr,
          geschaeftszahlen_json,
          titel,
          status,
          status_text,
          ergebnis,
          roh_ergebnis,
          abstimmungen_json,
          betraege_json,
          orte_json,
          quellenausschnitt,
          parser_sicherheit,
          ergebnisquelle,
          digra_url,
          digra_einlagezahl,
          protokoll_ergebnis,
          digra_trefferwert,
          source_url,
          einbringer
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    insert_normalized_tables(connection, records)


def record_row(record: AgendaRecord) -> tuple:
    data = asdict(record)
    return (
        data["record_id"],
        data["meeting_date"],
        data["record_type"],
        data["source_file"],
        data["section"],
        data["agenda_item_no"],
        json.dumps(data["business_numbers"], ensure_ascii=False),
        data["title"],
        data["status"],
        data["status_text"],
        data["result_text"],
        data["raw_result_text"],
        json.dumps(data["votes"], ensure_ascii=False),
        json.dumps(data["amounts"], ensure_ascii=False),
        json.dumps(data["locations"], ensure_ascii=False),
        data["source_snippet"],
        data["parser_confidence"],
        data["result_source"],
        data["digra_url"],
        data["digra_business_number"],
        data["protocol_result_text"],
        data["digra_match_score"],
        data["source_url"],
        data["submitter"],
    )


def insert_normalized_tables(connection: sqlite3.Connection, records: list[AgendaRecord]) -> None:
    data = [asdict(record) for record in records]
    meeting_counts: dict[str, int] = {}
    for record in data:
        meeting_counts[record["meeting_date"]] = meeting_counts.get(record["meeting_date"], 0) + 1
    connection.executemany(
        "INSERT INTO meetings (datum, eintraege) VALUES (?, ?)",
        sorted(meeting_counts.items()),
    )
    connection.executemany(
        "INSERT INTO records (eintrag_id, datum, typ, titel, status, ergebnisquelle) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                record["record_id"],
                record["meeting_date"],
                record["record_type"],
                record["title"],
                record["status"],
                record["result_source"],
            )
            for record in data
        ],
    )
    connection.executemany(
        "INSERT INTO business_numbers (eintrag_id, wert) VALUES (?, ?)",
        [(record["record_id"], value) for record in data for value in record["business_numbers"]],
    )
    connection.executemany(
        "INSERT INTO amounts (eintrag_id, wert) VALUES (?, ?)",
        [(record["record_id"], value) for record in data for value in record["amounts"]],
    )
    connection.executemany(
        "INSERT INTO locations (eintrag_id, typ, wert, kontext, confidence) VALUES (?, ?, ?, ?, ?)",
        [
            (
                record["record_id"],
                str(location.get("type", "")),
                str(location.get("value", "")),
                str(location.get("context", "")),
                float(location.get("confidence", 0)),
            )
            for record in data
            for location in record.get("location_details", [])
        ],
    )
    connection.executemany(
        "INSERT INTO votes (eintrag_id, subject, outcome, approval_json, against_json, abstention_json) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (
                record["record_id"],
                str(vote.get("subject", "")),
                str(vote.get("outcome", "")),
                json.dumps(vote.get("approval", []), ensure_ascii=False),
                json.dumps(vote.get("against", []), ensure_ascii=False),
                json.dumps(vote.get("abstention", []), ensure_ascii=False),
            )
            for record in data
            for vote in record["votes"]
        ],
    )
    connection.executemany(
        "INSERT INTO source_spans (eintrag_id, quellenausschnitt, roh_ergebnis) VALUES (?, ?, ?)",
        [(record["record_id"], record["source_snippet"], record["raw_result_text"]) for record in data],
    )
    connection.executemany(
        "INSERT INTO eintraege_fts (rowid, titel, ergebnis, geschaeftszahlen, orte) VALUES (?, ?, ?, ?, ?)",
        [
            (
                index,
                record["title"],
                record["result_text"],
                " ".join(record["business_numbers"]),
                " ".join(record["locations"]),
            )
            for index, record in enumerate(data, start=1)
        ],
    )
