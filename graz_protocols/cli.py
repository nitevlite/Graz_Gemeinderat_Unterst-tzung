from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import json
import sys

from .docx_text import read_docx_paragraphs
from .parser import AgendaRecord, parse_protocol


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "parse":
        return run_parse(args)
    parser.print_help()
    return 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="graz-protocols",
        description="Extract structured, source-linked records from local Graz council DOCX protocols.",
    )
    subparsers = parser.add_subparsers(dest="command")

    parse_cmd = subparsers.add_parser("parse", help="Parse DOCX protocols from a local directory.")
    parse_cmd.add_argument("input_dir", type=Path, help="Directory containing local DOCX protocols.")
    parse_cmd.add_argument(
        "--output",
        type=Path,
        default=Path("out") / "agenda_items.jsonl",
        help="JSONL output path. Defaults to out/agenda_items.jsonl.",
    )
    parse_cmd.add_argument(
        "--summary",
        type=Path,
        default=Path("out") / "summary.json",
        help="Summary JSON output path. Defaults to out/summary.json.",
    )
    parse_cmd.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of DOCX files to parse, useful during development.",
    )
    return parser


def run_parse(args: argparse.Namespace) -> int:
    input_dir: Path = args.input_dir
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    docx_files = sorted(input_dir.glob("*.docx"))
    if args.limit and args.limit > 0:
        docx_files = docx_files[: args.limit]
    if not docx_files:
        print(f"No DOCX files found in {input_dir}", file=sys.stderr)
        return 1

    records: list[AgendaRecord] = []
    errors: list[dict[str, str]] = []
    for path in docx_files:
        try:
            paragraphs = read_docx_paragraphs(path)
            records.extend(parse_protocol(paragraphs, path.name))
        except Exception as exc:  # pylint: disable=broad-except
            errors.append({"file": path.name, "error": str(exc)})

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(record.to_json())
            handle.write("\n")

    summary = build_summary(docx_files, records, errors)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")

    print(
        f"Parsed {summary['files_total']} DOCX files, wrote {summary['records_total']} records "
        f"to {args.output}."
    )
    if errors:
        print(f"Files with errors: {len(errors)}", file=sys.stderr)
        return 1
    return 0


def build_summary(docx_files: list[Path], records: list[AgendaRecord], errors: list[dict[str, str]]) -> dict:
    status_counts = Counter(record.status for record in records)
    section_counts = Counter(record.section or "unknown" for record in records)
    file_counts = Counter(record.source_file for record in records)
    return {
        "files_total": len(docx_files),
        "files_with_records": len(file_counts),
        "records_total": len(records),
        "records_by_file": dict(sorted(file_counts.items())),
        "records_by_section": dict(sorted(section_counts.items())),
        "records_by_status": dict(sorted(status_counts.items())),
        "errors": errors,
    }


if __name__ == "__main__":
    raise SystemExit(main())
