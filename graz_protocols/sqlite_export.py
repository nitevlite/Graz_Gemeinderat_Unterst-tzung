from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json
import shutil
import sqlite3
import tempfile
import uuid

from .parser import AgendaRecord


SCHEMA_VERSION = 2


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
          protokoll_ergebnis TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_eintraege_datum ON eintraege(datum);
        CREATE INDEX IF NOT EXISTS idx_eintraege_typ ON eintraege(typ);
        CREATE INDEX IF NOT EXISTS idx_eintraege_status ON eintraege(status);
        CREATE INDEX IF NOT EXISTS idx_eintraege_abschnitt ON eintraege(abschnitt);
        CREATE INDEX IF NOT EXISTS idx_eintraege_stueck ON eintraege(datum, stueck_nr);

        CREATE TABLE IF NOT EXISTS zusammenfassung (
          schluessel TEXT PRIMARY KEY,
          wert_json TEXT NOT NULL
        );
        """
    )


def clear_existing_data(connection: sqlite3.Connection) -> None:
    connection.execute("DELETE FROM eintraege")
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
          protokoll_ergebnis
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )


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
    )
