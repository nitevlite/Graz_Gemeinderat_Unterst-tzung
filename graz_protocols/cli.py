from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import replace
from difflib import SequenceMatcher
import hashlib
from pathlib import Path
import json
import re
import sys

from .audit import write_audit_report
from .archive_agenda_pdf import parse_archive_agenda_text, read_archive_agenda_source
from .city_sources import (
    city_archive_assets_to_records,
    enrich_records_with_city_links,
    read_city_archive_asset_index,
    write_city_archive_asset_index,
    write_city_meeting_index,
)
from .docx_text import read_docx_paragraph_blocks
from .digra_import import (
    DEFAULT_DIGRA_TOOL_PATH,
    digra_entries_to_records,
    enrich_records_with_digra,
    fetch_digra_entries,
    list_digra_meetings,
)
from .parser import AgendaRecord, parse_protocol
from .question_pdf import parse_question_hour_text, read_question_hour_source
from .schema import SCHEMA_VERSION, validate_record
from .sqlite_export import write_sqlite
from .street_names import load_default_street_names, load_street_names
from .topics import write_topic_candidates
from .update_sources import normalize_digra_meeting_date, update_records_with_latest_digra


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "parse":
        return run_parse(args)
    if args.command == "audit":
        return run_audit(args)
    if args.command == "digra-list":
        return run_digra_list(args)
    if args.command == "digra-export":
        return run_digra_export(args)
    if args.command == "digra-sync":
        return run_digra_sync(args)
    if args.command == "digra-update":
        return run_digra_update(args)
    if args.command == "question-pdf":
        return run_question_pdf(args)
    if args.command == "agenda-pdf":
        return run_archive_agenda_pdf(args)
    if args.command == "topics":
        return run_topics(args)
    if args.command == "summaries":
        return run_summaries(args)
    if args.command == "search":
        return run_search(args)
    if args.command == "answer":
        return run_answer(args)
    if args.command == "eval-search":
        return run_eval_search(args)
    if args.command == "city-index":
        return run_city_index(args)
    if args.command == "city-assets":
        return run_city_assets(args)
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graz-protocols",
        description="Extrahiert strukturierte Einträge aus lokalen Grazer Gemeinderatsprotokollen im DOCX-Format.",
    )
    subparsers = parser.add_subparsers(dest="command")

    parse_cmd = subparsers.add_parser("parse", help="DOCX-Protokolle aus einem lokalen Ordner parsen.")
    parse_cmd.add_argument("input_dir", type=Path, help="Ordner mit lokalen DOCX-Protokollen.")
    parse_cmd.add_argument(
        "--output",
        type=Path,
        default=Path("out") / "agenda_items.jsonl",
        help="JSONL-Ausgabepfad. Standard: out/agenda_items.jsonl.",
    )
    parse_cmd.add_argument(
        "--summary",
        type=Path,
        default=Path("out") / "summary.json",
        help="JSON-Ausgabepfad für die Zusammenfassung. Standard: out/summary.json.",
    )
    parse_cmd.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optionale Höchstzahl zu parsenden DOCX-Dateien, praktisch während der Entwicklung.",
    )
    parse_cmd.add_argument(
        "--sqlite",
        type=Path,
        default=None,
        help="Optionaler SQLite-Ausgabepfad, z. B. out/eintraege.sqlite.",
    )
    parse_cmd.add_argument(
        "--street-names",
        type=Path,
        default=None,
        help="Optionale XLSX-Datei mit gültigen Grazer Straßennamen zur Ortserkennung.",
    )
    parse_cmd.add_argument(
        "--digra",
        action="store_true",
        help="DIGRA-Dokumentseiten über das vorhandene DIGRA-Export-Tool einbeziehen.",
    )
    parse_cmd.add_argument(
        "--digra-tool-path",
        type=Path,
        default=DEFAULT_DIGRA_TOOL_PATH,
        help=f"Pfad zum app-Ordner des DIGRA-Export-Tools. Standard: {DEFAULT_DIGRA_TOOL_PATH}.",
    )
    parse_cmd.add_argument(
        "--digra-cache",
        type=Path,
        default=Path("out") / "digra_cache.json",
        help="Lokaler Cache für DIGRA-Einträge. Standard: out/digra_cache.json.",
    )
    parse_cmd.add_argument(
        "--digra-results-only",
        action="store_true",
        help="Ergebnisse nur aus DIGRA anzeigen; fehlende DIGRA-Ergebnisse ausdrücklich markieren.",
    )
    parse_cmd.add_argument(
        "--city-archive-links",
        action="store_true",
        help="Stadt-Graz-Archivlinks als Quellen-Fallback ergänzen.",
    )
    parse_cmd.add_argument(
        "--city-archive-cache",
        type=Path,
        default=Path("out") / "city_archive_links.json",
        help="Lokaler Cache für Stadt-Graz-Archivlinks. Standard: out/city_archive_links.json.",
    )
    audit_cmd = subparsers.add_parser("audit", help="Markdown-Auditbericht für eine JSONL-Ausgabe erzeugen.")
    audit_cmd.add_argument(
        "--records",
        type=Path,
        default=Path("out") / "agenda_items_digra.jsonl",
        help="JSONL-Datei mit Einträgen. Standard: out/agenda_items_digra.jsonl.",
    )
    audit_cmd.add_argument(
        "--summary",
        type=Path,
        default=Path("out") / "summary_digra.json",
        help="JSON-Zusammenfassung. Standard: out/summary_digra.json.",
    )
    audit_cmd.add_argument(
        "--output",
        type=Path,
        default=Path("out") / "digra_audit.md",
        help="Markdown-Ausgabepfad. Standard: out/digra_audit.md.",
    )
    digra_list_cmd = subparsers.add_parser("digra-list", help="Verfügbare DIGRA-Sitzungen listen.")
    digra_list_cmd.add_argument("--limit", type=int, default=20, help="Maximale Anzahl Sitzungen.")
    digra_list_cmd.add_argument("--digra-tool-path", type=Path, default=DEFAULT_DIGRA_TOOL_PATH)

    digra_export_cmd = subparsers.add_parser(
        "digra-export", help="Strukturierte DIGRA-Einträge für Datumswerte ohne DOCX-Protokoll erzeugen."
    )
    digra_export_cmd.add_argument("--date", action="append", required=True, help="Sitzungsdatum im Format YYYY-MM-DD.")
    digra_export_cmd.add_argument("--output", type=Path, default=Path("out") / "digra_entries.jsonl")
    digra_export_cmd.add_argument("--summary", type=Path, default=Path("out") / "digra_summary.json")
    digra_export_cmd.add_argument("--sqlite", type=Path, default=None)
    digra_export_cmd.add_argument("--digra-tool-path", type=Path, default=DEFAULT_DIGRA_TOOL_PATH)

    digra_sync_cmd = subparsers.add_parser(
        "digra-sync", help="Aktuelle DIGRA-Sitzungen ohne lokale DOCX-Protokolle als Standarddatenbasis exportieren."
    )
    digra_sync_cmd.add_argument("--limit", type=int, default=30, help="Anzahl zu prüfender DIGRA-Sitzungen.")
    digra_sync_cmd.add_argument("--output", type=Path, default=Path("out") / "agenda_items_digra_sync.jsonl")
    digra_sync_cmd.add_argument("--summary", type=Path, default=Path("out") / "summary_digra_sync.json")
    digra_sync_cmd.add_argument("--sqlite", type=Path, default=None)
    digra_sync_cmd.add_argument("--digra-tool-path", type=Path, default=DEFAULT_DIGRA_TOOL_PATH)
    digra_sync_cmd.add_argument(
        "--city-archive-links",
        action="store_true",
        help="Stadt-Graz-Archivlinks als Quellen-Fallback ergänzen.",
    )
    digra_sync_cmd.add_argument(
        "--city-archive-cache",
        type=Path,
        default=Path("out") / "city_archive_links.json",
        help="Lokaler Cache für Stadt-Graz-Archivlinks. Standard: out/city_archive_links.json.",
    )
    digra_sync_cmd.add_argument(
        "--city-archive-assets",
        action="store_true",
        help="Vorhandenen Stadt-Graz-Archivassetindex als zusätzliche Archivquellen einbeziehen.",
    )
    digra_sync_cmd.add_argument(
        "--city-archive-assets-index",
        type=Path,
        default=Path("out") / "city_archive_assets.json",
        help="Assetindex aus city-assets. Standard: out/city_archive_assets.json.",
    )
    digra_sync_cmd.add_argument(
        "--city-archive-extract-documents",
        action="store_true",
        help="Geeignete Stadt-Graz-Archiv-PDFs herunterladen und in einzelne Antrags-Einträge zerlegen.",
    )
    digra_sync_cmd.add_argument(
        "--city-protocols-dir",
        type=Path,
        default=None,
        help="Lokale, ignorierte Stadt-Graz-DOCX-Protokolle als Ergänzung einbeziehen.",
    )
    digra_sync_cmd.add_argument(
        "--city-protocol-types",
        default="communication,question_hour",
        help="Kommagetrennte interne Typen aus --city-protocols-dir. Standard: communication,question_hour.",
    )
    digra_sync_cmd.add_argument(
        "--street-names",
        type=Path,
        default=None,
        help="Optionale XLSX-Datei mit gültigen Grazer Straßennamen zur Ortserkennung in lokalen Protokollen.",
    )

    digra_update_cmd = subparsers.add_parser(
        "digra-update", help="Vorhandene JSONL-Ausgabe automatisch um neue DIGRA-Sitzungen erweitern."
    )
    digra_update_cmd.add_argument("--base-records", type=Path, default=Path("out") / "agenda_items_digra_ai.jsonl")
    digra_update_cmd.add_argument("--base-summary", type=Path, default=Path("out") / "summary_digra.json")
    digra_update_cmd.add_argument("--output", type=Path, default=Path("out") / "agenda_items_digra_ai_plus_latest.jsonl")
    digra_update_cmd.add_argument("--summary", type=Path, default=Path("out") / "summary_digra_plus_latest.json")
    digra_update_cmd.add_argument("--limit", type=int, default=30, help="Anzahl zu prüfender DIGRA-Sitzungen.")
    digra_update_cmd.add_argument("--digra-tool-path", type=Path, default=DEFAULT_DIGRA_TOOL_PATH)

    question_pdf_cmd = subparsers.add_parser(
        "question-pdf",
        help="Alte Fragestunden-PDFs oder bereinigte TXT-Exporte in strukturierte Fragestunden-Einträge zerlegen.",
    )
    question_pdf_cmd.add_argument("input", type=Path, help="PDF-/TXT-Datei oder Ordner mit PDF-/TXT-Dateien.")
    question_pdf_cmd.add_argument("--output", type=Path, default=Path("out") / "question_hours.jsonl")
    question_pdf_cmd.add_argument("--summary", type=Path, default=Path("out") / "question_hours_summary.json")
    question_pdf_cmd.add_argument("--sqlite", type=Path, default=None)
    question_pdf_cmd.add_argument(
        "--source-index",
        type=Path,
        default=None,
        help="Optionaler Stadt-Graz-Archivassetindex; ordnet lokal geparsten PDFs ihre Original-URL zu.",
    )

    agenda_pdf_cmd = subparsers.add_parser(
        "agenda-pdf",
        help="Tagesordnungs-PDFs oder bereinigte TXT-Exporte in einzelne Archiv-Tagesordnungspunkte zerlegen.",
    )
    agenda_pdf_cmd.add_argument("input", type=Path, help="PDF-/TXT-Datei oder Ordner mit PDF-/TXT-Dateien.")
    agenda_pdf_cmd.add_argument("--output", type=Path, default=Path("out") / "archive_agenda_items.jsonl")
    agenda_pdf_cmd.add_argument("--summary", type=Path, default=Path("out") / "archive_agenda_summary.json")
    agenda_pdf_cmd.add_argument("--sqlite", type=Path, default=None)
    agenda_pdf_cmd.add_argument(
        "--source-url",
        default="",
        help="Optionale Original-URL für eine einzelne Quelle; PDF-Seiten werden als #page= ergänzt.",
    )

    topics_cmd = subparsers.add_parser("topics", help="Topic-Kandidaten über mehrere Sitzungen erzeugen.")
    topics_cmd.add_argument("--records", type=Path, default=Path("out") / "agenda_items_digra.jsonl")
    topics_cmd.add_argument("--output", type=Path, default=Path("out") / "topic_candidates.json")
    topics_cmd.add_argument(
        "--ai-headings",
        action="store_true",
        help="Optionale KI-Unterstützung für bessere Themenüberschriften nutzen. Standard: lokales Ollama.",
    )
    topics_cmd.add_argument(
        "--ai-provider",
        choices=["ollama", "openai"],
        default="ollama",
        help="KI-Provider für --ai-headings. Standard: ollama.",
    )
    topics_cmd.add_argument("--ai-model", default="", help="Optionales KI-Modell für --ai-headings.")
    topics_cmd.add_argument(
        "--ai-base-url",
        default="",
        help="Basis-URL für Ollama, z. B. http://localhost:11434. Standard: OLLAMA_HOST oder localhost.",
    )
    topics_cmd.add_argument("--ai-limit", type=int, default=50, help="Maximale Anzahl KI-beschrifteter Topics.")
    topics_cmd.add_argument(
        "--city-news",
        action="store_true",
        help="Aktuelle Stadt-Graz-RSS-News als Hinweise zu Topic-Kandidaten ergänzen.",
    )
    summaries_cmd = subparsers.add_parser(
        "summaries", help="KI-Zusammenfassungen und einfache Sprache zu Einträgen ergänzen."
    )
    summaries_cmd.add_argument("--records", type=Path, default=Path("out") / "agenda_items_digra.jsonl")
    summaries_cmd.add_argument("--output", type=Path, default=Path("out") / "agenda_items_digra_ai.jsonl")
    summaries_cmd.add_argument(
        "--ai-provider",
        choices=["ollama", "openai", "local"],
        default="local",
        help="Provider. Standard: local erzeugt kostenlose Zusammenfassungen ohne externen Dienst. Ollama/OpenAI sind optional.",
    )
    summaries_cmd.add_argument("--ai-model", default="", help="Optionales KI-Modell.")
    summaries_cmd.add_argument(
        "--ai-base-url",
        default="",
        help="Basis-URL für Ollama, z. B. http://localhost:11434. Standard: OLLAMA_HOST oder localhost.",
    )
    summaries_cmd.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximale Anzahl neu zu erzeugender Zusammenfassungen. 0 bedeutet alle fehlenden.",
    )
    summaries_cmd.add_argument("--overwrite", action="store_true", help="Vorhandene KI-Zusammenfassungen neu erzeugen.")
    search_cmd = subparsers.add_parser("search", help="Lokalen SQLite-Suchindex abfragen.")
    search_cmd.add_argument("query", help="Suchfrage oder Suchbegriff.")
    search_cmd.add_argument(
        "--sqlite",
        type=Path,
        default=Path("out") / "eintraege.sqlite",
        help="SQLite-Datenbank mit Suchindex. Standard: out/eintraege.sqlite.",
    )
    search_cmd.add_argument("--limit", type=int, default=10, help="Maximale Trefferzahl. Standard: 10.")
    answer_cmd = subparsers.add_parser("answer", help="Kostenfreie lokale Antwort aus dem SQLite-Suchindex erzeugen.")
    answer_cmd.add_argument("query", help="Frage, die aus lokalen Quellen beantwortet werden soll.")
    answer_cmd.add_argument(
        "--sqlite",
        type=Path,
        default=Path("out") / "eintraege.sqlite",
        help="SQLite-Datenbank mit Suchindex. Standard: out/eintraege.sqlite.",
    )
    answer_cmd.add_argument("--limit", type=int, default=30, help="Maximale Suchtreffer für die Antwort. Standard: 30.")
    answer_cmd.add_argument("--per-group", type=int, default=5, help="Maximale Quellen pro Antwortgruppe. Standard: 5.")
    eval_search_cmd = subparsers.add_parser("eval-search", help="Lokale Suche gegen einen bereinigten Goldstandard messen.")
    eval_search_cmd.add_argument(
        "--sqlite",
        type=Path,
        default=Path("out") / "eintraege.sqlite",
        help="SQLite-Datenbank mit Suchindex. Standard: out/eintraege.sqlite.",
    )
    eval_search_cmd.add_argument(
        "--goldset",
        type=Path,
        default=Path("tests") / "fixtures" / "search_goldstandard.json",
        help="Bereinigter Goldstandard. Standard: tests/fixtures/search_goldstandard.json.",
    )
    eval_search_cmd.add_argument("--limit", type=int, default=10, help="Trefferfenster für @K-Metriken. Standard: 10.")
    eval_search_cmd.add_argument("--output", type=Path, default=None, help="Optionaler JSON-Ausgabepfad.")
    city_index_cmd = subparsers.add_parser(
        "city-index", help="Stadt-Graz-Archivseiten für ältere Gemeinderatssitzungen indexieren."
    )
    city_index_cmd.add_argument("--output", type=Path, default=Path("out") / "city_archive_index.json")
    city_assets_cmd = subparsers.add_parser(
        "city-assets", help="Dokument-/Übersichtslinks aus Stadt-Graz-Sitzungsseiten indexieren."
    )
    city_assets_cmd.add_argument("--output", type=Path, default=Path("out") / "city_archive_assets.json")
    city_assets_cmd.add_argument(
        "--input-index",
        type=Path,
        default=Path("out") / "city_archive_index.json",
        help="Vorhandenen Stadt-Graz-Sitzungsindex verwenden, statt die Archivliste neu zu laden.",
    )
    city_assets_cmd.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximale Anzahl Sitzungsseiten scannen. 0 bedeutet alle.",
    )
    return parser


def run_parse(args: argparse.Namespace) -> int:
    input_dir: Path = args.input_dir
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Eingabeordner nicht gefunden: {input_dir}", file=sys.stderr)
        return 1

    docx_files = sorted(input_dir.glob("*.docx"))
    if args.limit and args.limit > 0:
        docx_files = docx_files[: args.limit]
    if not docx_files:
        print(f"Keine DOCX-Dateien in {input_dir} gefunden.", file=sys.stderr)
        return 1

    records: list[AgendaRecord] = []
    errors: list[dict[str, str]] = []
    street_names = load_street_names(args.street_names) if args.street_names else load_default_street_names()
    for path in docx_files:
        try:
            paragraphs = read_docx_paragraph_blocks(path)
            records.extend(parse_protocol(paragraphs, path.name, street_names=street_names))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": path.name, "fehler": str(exc)})

    digra_summary: dict = {}
    if args.digra or args.digra_results_only:
        try:
            records, digra_summary = enrich_records_with_digra(
                records,
                tool_path=args.digra_tool_path,
                cache_path=args.digra_cache,
                results_only=args.digra_results_only,
            )
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": "DIGRA", "fehler": str(exc)})

    city_summary: dict = {}
    if args.city_archive_links:
        try:
            records, city_summary = enrich_records_with_city_links(records, cache_path=args.city_archive_cache)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": "Stadt-Graz-Archiv", "fehler": str(exc)})

    records, validation_errors = validate_records(records)
    errors.extend(validation_errors)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")

    summary = build_summary(docx_files, records, errors)
    summary.update(digra_summary)
    summary.update(city_summary)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.sqlite is not None:
        write_sqlite(args.sqlite, records, summary)

    print(
        f"{summary['files_total']} DOCX-Dateien geparst, {summary['records_total']} Einträge "
        f"nach {args.output} geschrieben."
    )
    if args.sqlite is not None:
        print(f"SQLite-Datenbank nach {args.sqlite} geschrieben.")
    if errors:
        print(f"Dateien mit Fehlern: {len(errors)}", file=sys.stderr)
        return 1
    return 0


def run_audit(args: argparse.Namespace) -> int:
    if not args.records.exists():
        print(f"Eintragsdatei nicht gefunden: {args.records}", file=sys.stderr)
        return 1
    write_audit_report(args.records, args.summary, args.output)
    print(f"Auditbericht nach {args.output} geschrieben.")
    return 0


def run_digra_list(args: argparse.Namespace) -> int:
    meetings = list_digra_meetings(args.digra_tool_path, limit=args.limit)
    for meeting in meetings:
        print(f"{meeting.date}\t{meeting.number}\t{meeting.title}\t{meeting.url}")
    return 0


def run_digra_export(args: argparse.Namespace) -> int:
    entries = fetch_digra_entries(args.date, tool_path=args.digra_tool_path)
    records = digra_entries_to_records(entries)
    records, validation_errors = validate_records(records)
    summary = build_summary([], records, validation_errors)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.sqlite is not None:
        write_sqlite(args.sqlite, records, summary)
    print(f"{len(records)} DIGRA-Einträge nach {args.output} geschrieben.")
    return 1 if validation_errors else 0


def run_digra_sync(args: argparse.Namespace) -> int:
    meetings = list_digra_meetings(args.digra_tool_path, limit=args.limit)
    dates = sorted(
        {
            normalized
            for meeting in meetings
            if (normalized := normalize_digra_meeting_date(str(meeting.date)))
        }
    )
    entries = fetch_digra_entries(dates, tool_path=args.digra_tool_path)
    records = digra_entries_to_records(entries)
    city_summary: dict = {}
    errors: list[dict[str, str]] = []
    city_protocol_files = 0
    city_protocol_records = 0
    city_protocol_types: list[str] = []
    archive_asset_records = 0
    archive_asset_years: list[str] = []
    archive_asset_errors: list[dict[str, str]] = []
    if args.city_protocols_dir:
        protocol_types = parse_type_list(args.city_protocol_types)
        city_protocol_types = sorted(protocol_types)
        street_names = load_street_names(args.street_names) if args.street_names else load_default_street_names()
        all_protocol_records, city_protocol_files, protocol_errors = parse_city_protocol_records(
            args.city_protocols_dir,
            street_names=street_names,
        )
        records = inherit_locations_from_matching_records(records, all_protocol_records)
        records = inherit_amounts_from_matching_records(records, all_protocol_records)
        protocol_records = [record for record in all_protocol_records if record.record_type in protocol_types]
        protocol_records = inherit_links_from_matching_records(records, protocol_records)
        protocol_records = inherit_question_links_from_similar_records(records, protocol_records)
        city_protocol_records = len(protocol_records)
        records = merge_missing_records(records, protocol_records)
        errors.extend(protocol_errors)
    if args.city_archive_assets:
        try:
            assets, archive_asset_errors = read_city_archive_asset_index(args.city_archive_assets_index)
            archive_records = city_archive_assets_to_records(
                assets,
                extract_documents=getattr(args, "city_archive_extract_documents", False),
            )
            archive_asset_records = len(archive_records)
            archive_asset_years = sorted({record.meeting_date[:4] for record in archive_records if record.meeting_date})
            records.extend(archive_records)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": "Stadt-Graz-Archivassets", "fehler": str(exc)})
    if args.city_archive_links:
        try:
            records, city_summary = enrich_records_with_city_links(records, cache_path=args.city_archive_cache)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": "Stadt-Graz-Archiv", "fehler": str(exc)})
    records = inherit_links_within_records(records)
    records, validation_errors = validate_records(records)
    errors.extend(validation_errors)
    summary = build_summary([], records, errors)
    summary.update(
        {
            "source_mode": "digra_sync",
            "digra_sync_meetings_seen": len(meetings),
            "digra_sync_dates": dates,
            "digra_entries_total": len(entries),
            "digra_results_used": sum(1 for record in records if record.result_source == "digra"),
            "digra_records_matched": sum(1 for record in records if record.digra_url),
            "digra_protocol_fallbacks": 0,
            "city_protocol_files": city_protocol_files,
            "city_protocol_records": city_protocol_records,
            "city_protocol_types": city_protocol_types,
            "city_archive_asset_records": archive_asset_records,
            "city_archive_asset_years": archive_asset_years,
            "city_archive_asset_index_errors": archive_asset_errors,
        }
    )
    summary.update(city_summary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.sqlite is not None:
        write_sqlite(args.sqlite, records, summary)
    print(f"{len(records)} DIGRA-Einträge aus {len(dates)} Sitzungen nach {args.output} geschrieben.")
    if args.sqlite is not None:
        print(f"SQLite-Datenbank nach {args.sqlite} geschrieben.")
    if errors:
        print(f"Hinweis: {len(errors)} Fehler beim DIGRA-Sync.", file=sys.stderr)
        return 1
    return 0


def parse_type_list(value: str) -> set[str]:
    return {item.strip() for item in value.split(",") if item.strip()}


def parse_city_protocol_supplements(
    input_dir: Path,
    record_types: set[str],
    street_names: set[str] | None = None,
) -> tuple[list[AgendaRecord], int, list[dict[str, str]]]:
    records, file_count, errors = parse_city_protocol_records(input_dir, street_names=street_names)
    return [record for record in records if record.record_type in record_types], file_count, errors


def parse_city_protocol_records(
    input_dir: Path,
    street_names: set[str] | None = None,
) -> tuple[list[AgendaRecord], int, list[dict[str, str]]]:
    if not input_dir.exists() or not input_dir.is_dir():
        return [], 0, [{"datei": str(input_dir), "fehler": "Stadt-Graz-Protokollordner nicht gefunden"}]
    records: list[AgendaRecord] = []
    errors: list[dict[str, str]] = []
    docx_files = sorted(input_dir.glob("*.docx"))
    for path in docx_files:
        try:
            parsed = parse_protocol(read_docx_paragraph_blocks(path), path.name, street_names=street_names)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": path.name, "fehler": str(exc)})
            continue
        records.extend(parsed)
    return records, len(docx_files), errors


def merge_missing_records(base_records: list[AgendaRecord], supplemental_records: list[AgendaRecord]) -> list[AgendaRecord]:
    seen = {record_identity(record) for record in base_records}
    seen_titles_by_type = {
        (record.record_type, title_date_identity(record))
        for record in base_records
        if title_date_identity(record) != ("", "")
    }
    merged = list(base_records)
    for record in supplemental_records:
        identity = record_identity(record)
        title_identity = title_date_identity(record)
        if identity in seen or supplemental_title_exists(record, title_identity, seen_titles_by_type):
            continue
        merged.append(record)
        seen.add(identity)
        if title_identity != ("", ""):
            seen_titles_by_type.add((record.record_type, title_identity))
    return merged


def supplemental_title_exists(
    record: AgendaRecord,
    title_identity: tuple[str, str],
    seen_titles_by_type: set[tuple[str, tuple[str, str]]],
) -> bool:
    if title_identity == ("", ""):
        return False
    if (record.record_type, title_identity) in seen_titles_by_type:
        return True
    if record.record_type == "question_hour":
        return ("agenda_item", title_identity) in seen_titles_by_type
    if record.record_type == "agenda_item":
        return ("question_hour", title_identity) in seen_titles_by_type
    return False


def inherit_links_from_matching_records(
    base_records: list[AgendaRecord],
    supplemental_records: list[AgendaRecord],
) -> list[AgendaRecord]:
    links_by_identity: dict[tuple[str, str], AgendaRecord] = {}
    for record in base_records:
        identity = title_date_identity(record)
        if not identity:
            continue
        if record.digra_url or record.source_url:
            links_by_identity.setdefault(identity, record)

    enriched: list[AgendaRecord] = []
    for record in supplemental_records:
        match = links_by_identity.get(title_date_identity(record))
        if not match:
            enriched.append(record)
            continue
        enriched.append(
            replace(
                record,
                digra_url=record.digra_url or match.digra_url,
                digra_business_number=record.digra_business_number or match.digra_business_number,
                digra_match_score=record.digra_match_score or match.digra_match_score,
                source_url=record.source_url or match.source_url,
            )
        )
    return enriched


def inherit_question_links_from_similar_records(
    base_records: list[AgendaRecord],
    supplemental_records: list[AgendaRecord],
) -> list[AgendaRecord]:
    linked_records_by_date: dict[str, list[AgendaRecord]] = {}
    for record in base_records:
        if not record.meeting_date or not record.digra_url:
            continue
        linked_records_by_date.setdefault(record.meeting_date, []).append(record)

    enriched: list[AgendaRecord] = []
    for record in supplemental_records:
        if record.digra_url or record.record_type not in {"question_hour", "written_question"}:
            enriched.append(record)
            continue
        match = best_similar_question_record(record, linked_records_by_date.get(record.meeting_date, []))
        if not match:
            enriched.append(record)
            continue
        enriched.append(
            replace(
                record,
                digra_url=match.digra_url,
                digra_business_number=record.digra_business_number or match.digra_business_number,
                digra_match_score=max(record.digra_match_score, 0.78),
            )
        )
    return enriched


def best_similar_question_record(record: AgendaRecord, candidates: list[AgendaRecord]) -> AgendaRecord | None:
    source_title = comparable_question_title(record.title)
    if not source_title:
        return None
    best_record: AgendaRecord | None = None
    best_score = 0.0
    for candidate in candidates:
        candidate_title = comparable_question_title(candidate.title)
        if not candidate_title:
            continue
        score = question_title_similarity(source_title, candidate_title)
        if score > best_score:
            best_score = score
            best_record = candidate
    return best_record if best_score >= 0.78 else None


def question_title_similarity(left: str, right: str) -> float:
    if left == right:
        return 1.0
    if len(left) >= 16 and left in right or len(right) >= 16 and right in left:
        return 0.9
    return SequenceMatcher(None, left, right).ratio()


def comparable_question_title(value: str) -> str:
    title = normalized_identity_title(value)
    title = re.sub(r"\([^)]{0,180}\)", " ", title)
    title = re.split(r"\bsehr geehrte\b", title, maxsplit=1)[0]
    title = re.sub(r"\s+", " ", title).strip(" ,;:-")
    return title


def inherit_links_within_records(records: list[AgendaRecord]) -> list[AgendaRecord]:
    return inherit_links_from_matching_records(records, records)


def inherit_locations_from_matching_records(
    base_records: list[AgendaRecord],
    location_source_records: list[AgendaRecord],
) -> list[AgendaRecord]:
    locations_by_identity: dict[tuple[str, str], AgendaRecord] = {}
    for record in location_source_records:
        identity = title_date_identity(record)
        if identity and record.locations:
            locations_by_identity.setdefault(identity, record)

    enriched: list[AgendaRecord] = []
    for record in base_records:
        if record.locations:
            enriched.append(record)
            continue
        match = locations_by_identity.get(title_date_identity(record))
        if not match:
            enriched.append(record)
            continue
        enriched.append(replace(record, locations=match.locations, location_details=match.location_details))
    return enriched


def inherit_amounts_from_matching_records(
    base_records: list[AgendaRecord],
    amount_source_records: list[AgendaRecord],
) -> list[AgendaRecord]:
    amounts_by_identity: dict[tuple[str, str], AgendaRecord] = {}
    for record in amount_source_records:
        identity = title_date_identity(record)
        if identity and record.amounts:
            amounts_by_identity.setdefault(identity, record)

    enriched: list[AgendaRecord] = []
    for record in base_records:
        if record.amounts:
            enriched.append(record)
            continue
        match = amounts_by_identity.get(title_date_identity(record))
        if not match:
            enriched.append(record)
            continue
        enriched.append(replace(record, amounts=match.amounts))
    return enriched


def title_date_identity(record: AgendaRecord) -> tuple[str, str]:
    if not record.meeting_date or not record.title:
        return ("", "")
    return (record.meeting_date, normalized_identity_title(record.title))


def record_identity(record: AgendaRecord) -> tuple[str, str, str, str]:
    return (
        record.meeting_date,
        record.record_type,
        " ".join(record.business_numbers),
        normalized_identity_title(record.title),
    )


def normalized_identity_title(value: str) -> str:
    title = re.sub(r"\s+", " ", str(value or "")).strip().casefold()
    title = re.sub(r"^(?:frage|stk\.?|to)?\s*\d{1,3}\)\s*", "", title)
    title = re.sub(r"^(?:frage|stk\.?|to)\s+\d{1,3}\s*[:.)-]\s*", "", title)
    return title.strip(" ,;:-")


def run_digra_update(args: argparse.Namespace) -> int:
    summary = update_records_with_latest_digra(
        args.base_records,
        args.base_summary,
        args.output,
        args.summary,
        tool_path=args.digra_tool_path,
        limit=args.limit,
    )
    if summary["new_dates"]:
        print(f"Neue DIGRA-Termine: {', '.join(summary['new_dates'])}")
    else:
        print("Keine neuen DIGRA-Termine gefunden.")
    print(f"{summary['added_records']} neue DIGRA-Einträge ergänzt; gesamt {summary['records_total']}.")
    print(f"Ausgabe: {summary['output_records']}")
    if summary["validation_errors"]:
        print(f"Hinweis: {len(summary['validation_errors'])} Validierungsfehler.", file=sys.stderr)
        return 1
    return 0


def run_question_pdf(args: argparse.Namespace) -> int:
    input_path: Path = args.input
    if not input_path.exists():
        print(f"Eingabe nicht gefunden: {input_path}", file=sys.stderr)
        return 1
    paths = question_hour_input_paths(input_path)
    if not paths:
        print(f"Keine PDF-/TXT-Dateien gefunden: {input_path}", file=sys.stderr)
        return 1

    source_urls = source_urls_by_local_question_file(args.source_index) if args.source_index else {}
    records: list[AgendaRecord] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            parsed = parse_question_hour_text(read_question_hour_source(path), path.name)
            source_url = source_urls.get(path.name)
            if source_url:
                parsed = [replace(record, source_url=source_url) for record in parsed]
            records.extend(parsed)
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": path.name, "fehler": str(exc)})
    records, validation_errors = validate_records(records)
    errors.extend(validation_errors)
    summary = build_summary(paths, records, errors)
    summary["source_mode"] = "question_pdf"
    summary["question_hour_sources"] = [path.name for path in paths]
    summary["question_hour_source_urls_applied"] = sum(1 for record in records if record.source_url)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.sqlite is not None:
        write_sqlite(args.sqlite, records, summary)
    print(f"{len(records)} Fragestunden-Einträge aus {len(paths)} Quellen nach {args.output} geschrieben.")
    if errors:
        print(f"Hinweis: {len(errors)} Fehler beim Fragestunden-Import.", file=sys.stderr)
        return 1
    return 0


def run_archive_agenda_pdf(args: argparse.Namespace) -> int:
    input_path: Path = args.input
    if not input_path.exists():
        print(f"Eingabe nicht gefunden: {input_path}", file=sys.stderr)
        return 1
    paths = question_hour_input_paths(input_path)
    if not paths:
        print(f"Keine PDF-/TXT-Dateien gefunden: {input_path}", file=sys.stderr)
        return 1

    records: list[AgendaRecord] = []
    errors: list[dict[str, str]] = []
    for path in paths:
        try:
            source_url = args.source_url if len(paths) == 1 else ""
            records.extend(parse_archive_agenda_text(read_archive_agenda_source(path), path.name, source_url=source_url))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"datei": path.name, "fehler": str(exc)})
    records, validation_errors = validate_records(records)
    errors.extend(validation_errors)
    summary = build_summary(paths, records, errors)
    summary["source_mode"] = "archive_agenda_pdf"
    summary["archive_agenda_sources"] = [path.name for path in paths]
    summary["archive_agenda_source_url_applied"] = bool(args.source_url and len(paths) == 1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    if args.sqlite is not None:
        write_sqlite(args.sqlite, records, summary)
    print(f"{len(records)} Archiv-Tagesordnungspunkte aus {len(paths)} Quellen nach {args.output} geschrieben.")
    if errors:
        print(f"Hinweis: {len(errors)} Fehler beim Tagesordnungs-PDF-Import.", file=sys.stderr)
        return 1
    return 0


def source_urls_by_local_question_file(source_index: Path) -> dict[str, str]:
    if not source_index.exists():
        return {}
    try:
        assets, _errors = read_city_archive_asset_index(source_index)
    except Exception:  # pylint: disable=broad-except
        return {}
    mapping: dict[str, str] = {}
    for asset in assets:
        if asset.kind != "protocol_document":
            continue
        if "fragestunde" not in f"{asset.title} {asset.url}".casefold():
            continue
        digest = hashlib.sha1(asset.url.encode("utf-8")).hexdigest()[:10]
        date = asset.meeting_date or "unknown-date"
        stem = safe_filename_part(asset.title or "Fragestunde des Gemeinderates")
        mapping[f"{date}_{stem}_{digest}.pdf"] = asset.url
        mapping[f"{date}_{stem}_{digest}.txt"] = asset.url
    return mapping


def safe_filename_part(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9ÄÖÜäöüß]+", "-", value).strip("-")
    return cleaned[:80] or "quelle"


def question_hour_input_paths(input_path: Path) -> list[Path]:
    if input_path.is_file() and input_path.suffix.casefold() in {".pdf", ".txt"}:
        return [input_path]
    if input_path.is_dir():
        return sorted(
            path
            for path in input_path.iterdir()
            if path.is_file() and path.suffix.casefold() in {".pdf", ".txt"}
        )
    return []


def run_topics(args: argparse.Namespace) -> int:
    if not args.records.exists():
        print(f"Eintragsdatei nicht gefunden: {args.records}", file=sys.stderr)
        return 1
    try:
        write_topic_candidates(
            args.records,
            args.output,
            ai_headings=args.ai_headings,
            ai_provider=args.ai_provider,
            ai_model=args.ai_model,
            ai_base_url=args.ai_base_url,
            ai_limit=args.ai_limit,
            city_news=args.city_news,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Topic-Kandidaten nach {args.output} geschrieben.")
    return 0


def run_summaries(args: argparse.Namespace) -> int:
    if not args.records.exists():
        print(f"Eintragsdatei nicht gefunden: {args.records}", file=sys.stderr)
        return 1
    try:
        from .ai_summaries import write_record_summaries

        summary = write_record_summaries(
            args.records,
            args.output,
            provider=args.ai_provider,
            model=args.ai_model,
            base_url=args.ai_base_url,
            limit=args.limit,
            overwrite=args.overwrite,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"{summary['records_with_ai_summary']} Einträge mit KI-Zusammenfassung "
        f"nach {args.output} geschrieben."
    )
    return 0


def run_search(args: argparse.Namespace) -> int:
    if not args.sqlite.exists():
        print(f"SQLite-Datenbank nicht gefunden: {args.sqlite}", file=sys.stderr)
        return 1
    from .search_index import search_sqlite

    results = search_sqlite(args.sqlite, args.query, limit=args.limit)
    if not results:
        print("Keine Treffer gefunden.")
        return 0
    for index, result in enumerate(results, start=1):
        source = result.digra_url or result.source_url or "-"
        fields = ", ".join(result.matched_fields) or "-"
        print(f"{index}. {result.date} | {result.record_type} | {result.title}")
        print(f"   ID: {result.record_id}")
        print(f"   Ergebnis: {result.result_text or '-'}")
        print(f"   Trefferfelder: {fields} | Score: {result.score}")
        print(f"   Quelle: {source}")
        if result.snippets:
            print(f"   Kontext: {result.snippets[0]}")
    return 0


def run_answer(args: argparse.Namespace) -> int:
    if not args.sqlite.exists():
        print(f"SQLite-Datenbank nicht gefunden: {args.sqlite}", file=sys.stderr)
        return 1
    from .answers import answer_sqlite

    print(answer_sqlite(args.sqlite, args.query, limit=args.limit, per_group=args.per_group))
    return 0


def run_eval_search(args: argparse.Namespace) -> int:
    if not args.sqlite.exists():
        print(f"SQLite-Datenbank nicht gefunden: {args.sqlite}", file=sys.stderr)
        return 1
    if not args.goldset.exists():
        print(f"Goldstandard nicht gefunden: {args.goldset}", file=sys.stderr)
        return 1
    from .search_eval import evaluate_search_goldstandard

    try:
        summary = evaluate_search_goldstandard(args.sqlite, args.goldset, limit=args.limit)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(
        f"Such-Eval: {summary['hits_at_k']}/{summary['cases_total']} Treffer @ {summary['limit']} | "
        f"Recall@K {summary['recall_at_k']:.4f} | MRR {summary['mean_reciprocal_rank']:.4f} | "
        f"Precision@K {summary['mean_precision_at_k']:.4f}"
    )
    missed = [case for case in summary["case_results"] if not case["hit"]]
    if missed:
        print("Nicht getroffen:")
        for case in missed:
            expected = ", ".join(case["expected_record_ids"])
            print(f"- {case['case_id']}: erwartet {expected}")
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        print(f"Eval-Bericht: {args.output}")
    return 0


def run_city_index(args: argparse.Namespace) -> int:
    summary = write_city_meeting_index(args.output)
    years = ", ".join(summary["years"])
    print(f"{summary['city_meeting_pages']} Stadt-Graz-Sitzungsseiten nach {summary['output']} geschrieben.")
    if years:
        print(f"Jahre: {years}")
    if summary.get("errors"):
        print(f"Hinweis: {len(summary['errors'])} Stadt-Graz-Seiten konnten nicht geladen werden.", file=sys.stderr)
    return 0


def run_city_assets(args: argparse.Namespace) -> int:
    summary = write_city_archive_asset_index(args.output, input_index=args.input_index, limit=args.limit)
    print(
        f"{summary['city_archive_assets']} Stadt-Graz-Archivassets aus "
        f"{summary['city_meeting_pages_scanned']} Sitzungsseiten nach {summary['output']} geschrieben."
    )
    if summary.get("kinds"):
        print("Typen: " + ", ".join(f"{key}={value}" for key, value in sorted(summary["kinds"].items())))
    if summary.get("errors"):
        print(f"Hinweis: {len(summary['errors'])} Stadt-Graz-Seiten konnten nicht geladen werden.", file=sys.stderr)
    return 0


def build_summary(docx_files: list[Path], records: list[AgendaRecord], errors: list[dict[str, str]]) -> dict:
    status_counts = Counter(record.status for record in records)
    section_counts = Counter(record.section or "unknown" for record in records)
    type_counts = Counter(record.record_type for record in records)
    file_counts = Counter(record.source_file for record in records)
    records_with_votes = sum(1 for record in records if record.votes)
    return {
        "files_total": len(docx_files),
        "files_with_records": len(file_counts),
        "records_with_votes": records_with_votes,
        "records_total": len(records),
        "records_by_file": dict(sorted(file_counts.items())),
        "records_by_section": dict(sorted(section_counts.items())),
        "records_by_status": dict(sorted(status_counts.items())),
        "records_by_type": dict(sorted(type_counts.items())),
        "schema_version": SCHEMA_VERSION,
        "errors": errors,
    }


def validate_records(records: list[AgendaRecord]) -> tuple[list[AgendaRecord], list[dict[str, str]]]:
    valid: list[AgendaRecord] = []
    errors: list[dict[str, str]] = []
    for record in records:
        record_errors = validate_record(record)
        if record_errors:
            errors.append({"datei": record.source_file, "fehler": f"{record.record_id}: {'; '.join(record_errors)}"})
            continue
        valid.append(record)
    return valid, errors


if __name__ == "__main__":
    raise SystemExit(main())
