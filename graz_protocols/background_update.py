from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime
import locale
import os
from pathlib import Path
import subprocess
import sys
import time

from .digra_import import DEFAULT_DIGRA_TOOL_PATH
from .update_sources import update_records_with_latest_digra


@dataclass(frozen=True)
class DataTarget:
    records: Path
    summary: Path


PREFERRED_TARGETS = [
    DataTarget(
        Path("out") / "agenda_items_digra_sync_plus_city_protocols_and_archive_questions_clean.jsonl",
        Path("out") / "summary_digra_sync_plus_city_protocols_and_archive_questions_clean.json",
    ),
    DataTarget(
        Path("out") / "agenda_items_digra_sync_plus_city_protocols_and_archive_questions.jsonl",
        Path("out") / "summary_digra_sync_plus_city_protocols_and_archive_questions.json",
    ),
    DataTarget(
        Path("out") / "agenda_items_digra_sync_plus_city_protocols.jsonl",
        Path("out") / "summary_digra_sync_plus_city_protocols.json",
    ),
    DataTarget(Path("out") / "agenda_items_digra_sync.jsonl", Path("out") / "summary_digra_sync.json"),
    DataTarget(Path("out") / "agenda_items_digra_ai_plus_latest.jsonl", Path("out") / "summary_digra_plus_latest.json"),
    DataTarget(Path("out") / "agenda_items_digra_ai.jsonl", Path("out") / "summary_digra.json"),
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aktualisiert DIGRA im Hintergrund und baut lokale Viewer-Dateien neu.")
    parser.add_argument("--interval-minutes", type=float, default=30.0)
    parser.add_argument("--limit", type=int, default=30)
    parser.add_argument("--once", action="store_true", help="Nur einen Lauf ausführen.")
    parser.add_argument("--lock", type=Path, default=Path("out") / "digra_background.lock")
    parser.add_argument("--log", type=Path, default=Path("out") / "digra_background.log")
    parser.add_argument("--topics", type=Path, default=Path("out") / "topic_candidates.json")
    parser.add_argument("--viewer", type=Path, default=Path("viewer.html"))
    parser.add_argument("--digra-tool-path", type=Path, default=DEFAULT_DIGRA_TOOL_PATH)
    parser.add_argument("--summary-provider", choices=["ollama", "openai", "local", "none"], default="local")
    parser.add_argument("--summary-model", default="")
    parser.add_argument("--summary-base-url", default="")
    parser.add_argument(
        "--summary-limit",
        type=int,
        default=0,
        help="Maximale Anzahl fehlender Zusammenfassungen pro Lauf. 0 bedeutet alle fehlenden.",
    )
    args = parser.parse_args(argv)

    args.lock.parent.mkdir(parents=True, exist_ok=True)
    args.log.parent.mkdir(parents=True, exist_ok=True)
    if not acquire_lock(args.lock, args.log):
        log(args.log, "DIGRA-Hintergrunddienst läuft bereits.")
        return 0
    try:
        while True:
            run_once(args)
            if args.once:
                return 0
            time.sleep(max(60, int(args.interval_minutes * 60)))
    finally:
        release_lock(args.lock)


def run_once(args: argparse.Namespace) -> None:
    target = select_target()
    if target is None:
        log(args.log, "Keine lokale Datenbasis gefunden; DIGRA-Hintergrundlauf übersprungen.")
        return
    log(args.log, f"Prüfe DIGRA für {target.records}.")
    try:
        summary = update_records_with_latest_digra(
            target.records,
            target.summary,
            target.records,
            target.summary,
            tool_path=args.digra_tool_path,
            limit=args.limit,
        )
        log(args.log, f"DIGRA geprüft: {summary['added_records']} neue Einträge, {len(summary['new_dates'])} neue Sitzungen.")
        rebuild_summaries(target.records, args, args.log)
        rebuild_topics(target.records, args.topics, args.log)
        rebuild_viewer(target.records, target.summary, args.topics, args.viewer, args.log)
    except Exception as exc:  # pylint: disable=broad-except
        log(args.log, f"WARNUNG: Hintergrundlauf fehlgeschlagen: {exc}")


def select_target() -> DataTarget | None:
    for target in PREFERRED_TARGETS:
        if target.records.exists() and target.summary.exists():
            return target
    return None


def rebuild_topics(records: Path, topics: Path, log_path: Path) -> None:
    command = [sys.executable, "-m", "graz_protocols.cli", "topics", "--records", str(records), "--output", str(topics)]
    run_command(command, log_path)


def rebuild_summaries(records: Path, args: argparse.Namespace, log_path: Path) -> None:
    if args.summary_provider == "none":
        return
    command = [
        sys.executable,
        "-m",
        "graz_protocols.cli",
        "summaries",
        "--records",
        str(records),
        "--output",
        str(records),
        "--ai-provider",
        args.summary_provider,
        "--limit",
        str(args.summary_limit),
    ]
    if args.summary_model:
        command.extend(["--ai-model", args.summary_model])
    if args.summary_base_url:
        command.extend(["--ai-base-url", args.summary_base_url])
    try:
        run_command(command, log_path)
    except Exception as exc:  # pylint: disable=broad-except
        log(log_path, f"WARNUNG: Zusammenfassungen konnten nicht aktualisiert werden: {exc}")


def rebuild_viewer(records: Path, summary: Path, topics: Path, viewer: Path, log_path: Path) -> None:
    command = [
        sys.executable,
        "-m",
        "graz_protocols.viewer",
        "--records",
        str(records),
        "--summary",
        str(summary),
        "--topics",
        str(topics),
        "--output",
        str(viewer),
        "--parking-cache",
        str(Path("out") / "parkgaragen_graz.csv"),
        "--roadworks-cache",
        str(Path("out") / "baustellen_graz.html"),
    ]
    run_command(command, log_path)


def run_command(command: list[str], log_path: Path) -> None:
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding=locale.getpreferredencoding(False),
        errors="replace",
    )
    if (completed.stdout or "").strip():
        log(log_path, completed.stdout.strip())
    if (completed.stderr or "").strip():
        log(log_path, completed.stderr.strip())
    if completed.returncode:
        raise RuntimeError(f"Befehl fehlgeschlagen ({completed.returncode}): {' '.join(command)}")


def acquire_lock(lock_path: Path, log_path: Path) -> bool:
    if lock_path.exists():
        try:
            pid = int(lock_path.read_text(encoding="utf-8").strip() or "0")
        except ValueError:
            pid = 0
        if pid and process_exists(pid):
            return False
    lock_path.write_text(str(os.getpid()), encoding="utf-8")
    log(log_path, f"DIGRA-Hintergrunddienst gestartet, PID {os.getpid()}.")
    return True


def release_lock(lock_path: Path) -> None:
    try:
        if lock_path.read_text(encoding="utf-8").strip() == str(os.getpid()):
            lock_path.unlink()
    except OSError:
        return


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def log(path: Path, message: str) -> None:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(f"[{stamp}] {message}\n")


if __name__ == "__main__":
    raise SystemExit(main())
