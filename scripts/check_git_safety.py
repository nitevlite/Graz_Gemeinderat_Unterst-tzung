from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys


FORBIDDEN_SUFFIXES = {
    ".db",
    ".doc",
    ".docx",
    ".jsonl",
    ".odt",
    ".pdf",
    ".sqlite",
    ".sqlite3",
    ".xls",
    ".xlsx",
}
FORBIDDEN_DIRS = {
    "archive",
    "data/raw",
    "data/source",
    "exports",
    "graz_protokolle_arbeitskopie",
    "out",
    "protokolle",
}
FORBIDDEN_FILENAMES = {
    "graz-baustellen-auditlog.json",
    "graz-baustellen-abos.json",
    "graz-baustellen-feedback.json",
    "graz-baustellen-feed.csv",
    "graz-baustellen-feed.json",
    "graz-baustellen-feed.rss",
    "graz-baustellen.ics",
}
DEFAULT_MAX_BYTES = 1_000_000


@dataclass(frozen=True)
class Finding:
    path: str
    reason: str


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Prüft Git-Index und verfolgte Dateien auf verbotene Protokoll-/Exportdaten.",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=DEFAULT_MAX_BYTES,
        help=f"Maximale erlaubte Dateigröße für verfolgte Dateien. Standard: {DEFAULT_MAX_BYTES}.",
    )
    args = parser.parse_args(argv)

    tracked_paths = git_lines(["ls-files"])
    staged_paths = git_lines(["diff", "--cached", "--name-only"])
    findings = check_paths(tracked_paths, staged_paths, max_bytes=args.max_bytes)
    if not findings:
        print("Git-Sicherheitscheck OK: keine verbotenen Dateien im Git-Index.")
        return 0

    print("Git-Sicherheitscheck FEHLGESCHLAGEN:", file=sys.stderr)
    for finding in findings:
        print(f"- {finding.path}: {finding.reason}", file=sys.stderr)
    return 1


def git_lines(args: list[str]) -> list[str]:
    result = subprocess.run(["git", *args], check=True, capture_output=True, text=True)
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def check_paths(tracked_paths: list[str], staged_paths: list[str], max_bytes: int) -> list[Finding]:
    findings: list[Finding] = []
    all_paths = sorted(set(tracked_paths) | set(staged_paths))
    staged = set(staged_paths)
    for path_text in all_paths:
        normalized = normalize_path(path_text)
        suffix = Path(normalized).suffix.casefold()
        if Path(normalized).name.casefold() in FORBIDDEN_FILENAMES:
            findings.append(Finding(path_text, "lokaler Baustellen-/Audit-Export"))
            continue
        if suffix in FORBIDDEN_SUFFIXES:
            findings.append(Finding(path_text, f"verbotener Dateityp {suffix}"))
            continue
        forbidden_dir = matching_forbidden_dir(normalized)
        if forbidden_dir:
            findings.append(Finding(path_text, f"verbotener Datenordner {forbidden_dir}/"))
            continue
        path = Path(path_text)
        if path.exists() and path.is_file() and path.stat().st_size > max_bytes:
            scope = "gestagte" if path_text in staged else "verfolgte"
            findings.append(Finding(path_text, f"{scope} Datei größer als {max_bytes} Bytes"))
    return findings


def normalize_path(path: str) -> str:
    return path.replace("\\", "/").strip("/")


def matching_forbidden_dir(path: str) -> str:
    lowered = normalize_path(path).casefold()
    for directory in sorted(FORBIDDEN_DIRS):
        if lowered == directory or lowered.startswith(f"{directory}/"):
            return directory
    return ""


if __name__ == "__main__":
    raise SystemExit(main())
