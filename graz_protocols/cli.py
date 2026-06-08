from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json
import sys

from .audit import write_audit_report
from .docx_text import read_docx_paragraph_blocks
from .digra_import import DEFAULT_DIGRA_TOOL_PATH, enrich_records_with_digra
from .parser import AgendaRecord, parse_protocol
from .sqlite_export import write_sqlite


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "parse":
        return run_parse(args)
    if args.command == "audit":
        return run_audit(args)
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
    for path in docx_files:
        try:
            paragraphs = read_docx_paragraph_blocks(path)
            records.extend(parse_protocol(paragraphs, path.name))
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

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")

    summary = build_summary(docx_files, records, errors)
    summary.update(digra_summary)
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
        "errors": errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())
