from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json
import sys

from .audit import write_audit_report
from .city_sources import enrich_records_with_city_links
from .docx_text import read_docx_paragraph_blocks
from .digra_import import (
    DEFAULT_DIGRA_TOOL_PATH,
    digra_entries_to_records,
    enrich_records_with_digra,
    fetch_digra_entries,
    list_digra_meetings,
)
from .parser import AgendaRecord, parse_protocol
from .schema import SCHEMA_VERSION, validate_record
from .sqlite_export import write_sqlite
from .street_names import load_street_names
from .topics import write_topic_candidates


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
    if args.command == "topics":
        return run_topics(args)
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

    topics_cmd = subparsers.add_parser("topics", help="Topic-Kandidaten über mehrere Sitzungen erzeugen.")
    topics_cmd.add_argument("--records", type=Path, default=Path("out") / "agenda_items_digra.jsonl")
    topics_cmd.add_argument("--output", type=Path, default=Path("out") / "topic_candidates.json")
    topics_cmd.add_argument(
        "--ai-headings",
        action="store_true",
        help="Optionale KI-Unterstützung für bessere Themenüberschriften nutzen. Benötigt OPENAI_API_KEY.",
    )
    topics_cmd.add_argument("--ai-model", default="", help="Optionales OpenAI-Modell für --ai-headings.")
    topics_cmd.add_argument("--ai-limit", type=int, default=50, help="Maximale Anzahl KI-beschrifteter Topics.")
    topics_cmd.add_argument(
        "--city-news",
        action="store_true",
        help="Aktuelle Stadt-Graz-RSS-News als Hinweise zu Topic-Kandidaten ergänzen.",
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
    street_names = load_street_names(args.street_names) if args.street_names else None
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


def run_topics(args: argparse.Namespace) -> int:
    if not args.records.exists():
        print(f"Eintragsdatei nicht gefunden: {args.records}", file=sys.stderr)
        return 1
    try:
        write_topic_candidates(
            args.records,
            args.output,
            ai_headings=args.ai_headings,
            ai_model=args.ai_model,
            ai_limit=args.ai_limit,
            city_news=args.city_news,
        )
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Topic-Kandidaten nach {args.output} geschrieben.")
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
