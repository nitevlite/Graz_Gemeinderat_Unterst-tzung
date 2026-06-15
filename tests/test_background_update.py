from pathlib import Path
import argparse

from graz_protocols import background_update


def test_select_target_prefers_final_combined_output(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    final_records = out / "agenda_items_digra_sync_plus_city_protocols_and_archive_questions.jsonl"
    final_summary = out / "summary_digra_sync_plus_city_protocols_and_archive_questions.json"
    fallback_records = out / "agenda_items_digra_ai.jsonl"
    fallback_summary = out / "summary_digra.json"
    for path in [final_records, final_summary, fallback_records, fallback_summary]:
        path.write_text("{}", encoding="utf-8")

    target = background_update.select_target()

    assert target is not None
    assert target.records == Path("out") / "agenda_items_digra_sync_plus_city_protocols_and_archive_questions.jsonl"


def test_lock_file_prevents_second_background_process(tmp_path, monkeypatch):
    lock = tmp_path / "digra.lock"
    log = tmp_path / "digra.log"
    monkeypatch.setattr(background_update.os, "getpid", lambda: 12345)

    assert background_update.acquire_lock(lock, log)
    assert lock.read_text(encoding="utf-8") == "12345"

    monkeypatch.setattr(background_update, "process_exists", lambda pid: pid == 12345)

    assert not background_update.acquire_lock(lock, log)


def test_background_rebuild_summaries_uses_configured_free_local_provider(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    records = tmp_path / "records.jsonl"
    log = tmp_path / "background.log"
    args = argparse.Namespace(summary_provider="local", summary_model="", summary_base_url="", summary_limit=0)

    monkeypatch.setattr(background_update, "run_command", lambda command, log_path: calls.append(command))

    background_update.rebuild_summaries(records, args, log)

    command = calls[0]
    assert "summaries" in command
    assert "--records" in command
    assert str(records) in command
    assert "--output" in command
    assert "--ai-provider" in command
    assert "local" in command
