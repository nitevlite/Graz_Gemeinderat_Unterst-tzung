from argparse import Namespace
import json
from pathlib import Path

from graz_protocols.cli import run_digra_sync
from graz_protocols.digra_import import DigraEntry


class FakeMeeting:
    def __init__(self, date: str):
        self.date = date


def test_digra_sync_writes_records_without_docx_input(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "graz_protocols.cli.list_digra_meetings",
        lambda tool_path, limit: [FakeMeeting("21.05.2026")],
    )
    monkeypatch.setattr(
        "graz_protocols.cli.fetch_digra_entries",
        lambda dates, tool_path: [
            DigraEntry(
                meeting_date="2026-05-21",
                meeting_number="61",
                record_type="agenda_item",
                section="Tagesordnung",
                order_in_type=1,
                agenda_item_no=1,
                business_number="123/1",
                title="DIGRA Standardimport",
                url="https://digra.graz.at/document?ref=test",
                status="accepted_unanimous",
                result_text="Antrag: einstimmig angenommen",
                raw_result_text="einstimmig angenommen",
                votes=[],
            )
        ],
    )
    output = tmp_path / "records.jsonl"
    summary = tmp_path / "summary.json"

    exit_code = run_digra_sync(
        Namespace(
            city_archive_cache=tmp_path / "city.json",
            city_archive_assets=False,
            city_archive_assets_index=tmp_path / "city_assets.json",
            city_archive_links=False,
            city_protocols_dir=None,
            city_protocol_types="communication,question_hour",
            digra_tool_path=Path("unused"),
            limit=30,
            output=output,
            sqlite=None,
            street_names=None,
            summary=summary,
        )
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert rows[0]["source_file"] == "DIGRA"
    assert rows[0]["meeting_date"] == "2026-05-21"
    assert payload["source_mode"] == "digra_sync"
    assert payload["digra_sync_dates"] == ["2026-05-21"]


def test_digra_sync_can_include_city_archive_asset_records(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "graz_protocols.cli.list_digra_meetings",
        lambda tool_path, limit: [FakeMeeting("21.05.2026")],
    )
    monkeypatch.setattr("graz_protocols.cli.fetch_digra_entries", lambda dates, tool_path: [])
    asset_index = tmp_path / "city_assets.json"
    asset_index.write_text(
        json.dumps(
            {
                "assets": [
                    {
                        "meeting_date": "2021-12-16",
                        "title": "Protokoll Gemeinderat",
                        "url": "https://www.graz.at/fileadmin/protokoll.docx",
                        "source_url": "https://www.graz.at/cms/beitrag/page",
                        "kind": "protocol_document",
                    }
                ],
                "errors": [],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    output = tmp_path / "records.jsonl"
    summary = tmp_path / "summary.json"

    exit_code = run_digra_sync(
        Namespace(
            city_archive_cache=tmp_path / "city.json",
            city_archive_assets=True,
            city_archive_assets_index=asset_index,
            city_archive_links=False,
            city_protocols_dir=None,
            city_protocol_types="communication,question_hour",
            digra_tool_path=Path("unused"),
            limit=30,
            output=output,
            sqlite=None,
            street_names=None,
            summary=summary,
        )
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert rows[0]["record_type"] == "archive_source"
    assert rows[0]["source_url"] == "https://www.graz.at/fileadmin/protokoll.docx"
    assert payload["city_archive_asset_records"] == 1
    assert payload["city_archive_asset_years"] == ["2021"]


def test_digra_sync_can_include_city_protocol_supplements(monkeypatch, tmp_path):
    monkeypatch.setattr(
        "graz_protocols.cli.list_digra_meetings",
        lambda tool_path, limit: [FakeMeeting("21.05.2026")],
    )
    monkeypatch.setattr(
        "graz_protocols.cli.fetch_digra_entries",
        lambda dates, tool_path: [
            DigraEntry(
                meeting_date="2026-05-21",
                meeting_number="61",
                record_type="agenda_item",
                section="Tagesordnung",
                order_in_type=1,
                agenda_item_no=1,
                business_number="2985/1",
                title="Bericht des Bürgermeisters",
                url="https://digra.graz.at/document?ref=matching",
                status="accepted_unanimous",
                result_text="Antrag: einstimmig angenommen",
                raw_result_text="einstimmig angenommen",
                votes=[],
            )
        ],
    )

    protocol_dir = tmp_path / "protocols"
    protocol_dir.mkdir()
    (protocol_dir / "2026-05-21_Protokoll.docx").write_bytes(b"placeholder")

    def fake_read_docx(path):
        return [f"blocks from {path.name}"]

    def fake_parse_protocol(paragraphs, source_file, street_names=None):
        from graz_protocols.parser import AgendaRecord

        return [
            AgendaRecord(
                record_id="2026-05-21-communication-1",
                record_type="communication",
                source_file=source_file,
                meeting_date="2026-05-21",
                section="Mitteilungen",
                agenda_item_no=1,
                business_numbers=[],
                title="Bericht des Bürgermeisters",
                status="noted",
                status_text="zur Kenntnis genommen",
                result_text="zur Kenntnis genommen",
                raw_result_text="Mitteilung ohne Beschluss.",
                votes=[],
                amounts=[],
                locations=[],
                source_snippet="Bericht des Bürgermeisters",
                parser_confidence=0.7,
            )
            ,
            AgendaRecord(
                record_id="2026-05-21-agenda-item-1-local",
                record_type="agenda_item",
                source_file=source_file,
                meeting_date="2026-05-21",
                section="Tagesordnung",
                agenda_item_no=1,
                business_numbers=[],
                title="Bericht des Bürgermeisters",
                status="accepted_unanimous",
                status_text="einstimmig angenommen",
                result_text="Antrag: einstimmig angenommen",
                raw_result_text="Der Antrag wurde einstimmig angenommen.",
                votes=[],
                amounts=[],
                locations=["Hauptplatz"],
                location_details=[{"type": "street", "value": "Hauptplatz", "context": "am Hauptplatz", "confidence": 0.9}],
                source_snippet="Bericht am Hauptplatz",
                parser_confidence=0.8,
            ),
        ]

    monkeypatch.setattr("graz_protocols.cli.read_docx_paragraph_blocks", fake_read_docx)
    monkeypatch.setattr("graz_protocols.cli.parse_protocol", fake_parse_protocol)
    output = tmp_path / "records.jsonl"
    summary = tmp_path / "summary.json"

    exit_code = run_digra_sync(
        Namespace(
            city_archive_cache=tmp_path / "city.json",
            city_archive_assets=False,
            city_archive_assets_index=tmp_path / "city_assets.json",
            city_archive_links=False,
            city_protocols_dir=protocol_dir,
            city_protocol_types="communication,question_hour",
            digra_tool_path=Path("unused"),
            limit=30,
            output=output,
            sqlite=None,
            street_names=None,
            summary=summary,
        )
    )

    rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert exit_code == 0
    communication = next(row for row in rows if row["record_type"] == "communication")
    agenda_item = next(row for row in rows if row["record_type"] == "agenda_item")
    assert agenda_item["locations"] == ["Hauptplatz"]
    assert communication["digra_url"] == "https://digra.graz.at/document?ref=matching"
    assert communication["digra_business_number"] == "2985/1"
    assert payload["city_protocol_files"] == 1
    assert payload["city_protocol_records"] == 1
    assert payload["city_protocol_types"] == ["communication", "question_hour"]
