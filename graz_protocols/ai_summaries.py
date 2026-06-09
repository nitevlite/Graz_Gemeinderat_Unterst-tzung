from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Protocol

import requests

from .ai_topics import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL, parse_ollama_response_json, parse_response_json


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: object) -> requests.Response: ...


def write_record_summaries(
    records_path: Path,
    output_path: Path,
    *,
    provider: str = "ollama",
    model: str = "",
    base_url: str = "",
    api_key: str | None = None,
    limit: int = 0,
    overwrite: bool = False,
    http_client: HttpClient | None = None,
) -> dict:
    records = read_jsonl(records_path)
    existing_by_id = read_existing_summaries(output_path) if output_path.exists() and not overwrite else {}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as handle:
        enriched = annotate_record_summaries(
            records,
            provider=provider,
            model=model,
            base_url=base_url,
            api_key=api_key,
            limit=limit,
            overwrite=overwrite,
            http_client=http_client,
            existing_by_id=existing_by_id,
            output_handle=handle,
        )
    return {
        "records_total": len(records),
        "records_with_ai_summary": sum(1 for record in enriched if record.get("ai_summary")),
        "records_with_ai_easy_language": sum(1 for record in enriched if record.get("ai_easy_language")),
        "output": str(output_path),
    }


def annotate_record_summaries(
    records: list[dict],
    *,
    provider: str = "ollama",
    model: str = "",
    base_url: str = "",
    api_key: str | None = None,
    limit: int = 0,
    overwrite: bool = False,
    http_client: HttpClient | None = None,
    existing_by_id: dict[str, dict] | None = None,
    output_handle: object | None = None,
) -> list[dict]:
    provider = provider.lower().strip()
    if provider not in {"ollama", "openai"}:
        raise RuntimeError(f"Unbekannter KI-Provider: {provider}")
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if provider == "openai" and not key:
        raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt.")
    client = http_client or requests
    selected_model = model or (DEFAULT_OPENAI_MODEL if provider == "openai" else DEFAULT_OLLAMA_MODEL)
    processed = 0
    enriched: list[dict] = []
    for record in records:
        updated = dict(record)
        record_id = str(updated.get("record_id", ""))
        if existing_by_id and record_id in existing_by_id:
            existing = dict(existing_by_id[record_id])
            updated["ai_summary"] = existing.get("ai_summary", "")
            updated["ai_easy_language"] = existing.get("ai_easy_language", "")
            for key, value in existing.items():
                if key not in updated:
                    updated[key] = value
            write_incremental_record(output_handle, updated)
            enriched.append(updated)
            continue
        if not overwrite and updated.get("ai_summary") and updated.get("ai_easy_language"):
            write_incremental_record(output_handle, updated)
            enriched.append(updated)
            continue
        if limit > 0 and processed >= limit:
            write_incremental_record(output_handle, updated)
            enriched.append(updated)
            continue
        result = suggest_record_summary(
            updated,
            provider=provider,
            model=selected_model,
            base_url=base_url,
            api_key=key,
            http_client=client,
        )
        processed += 1
        if valid_summary(result):
            updated["ai_summary"] = str(result["summary"]).strip()
            updated["ai_easy_language"] = str(result["easy_language"]).strip()
        write_incremental_record(output_handle, updated)
        enriched.append(updated)
    return enriched


def write_incremental_record(output_handle: object | None, record: dict) -> None:
    if output_handle is None:
        return
    output_handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
    output_handle.write("\n")
    output_handle.flush()


def read_existing_summaries(path: Path) -> dict[str, dict]:
    rows = read_jsonl(path)
    return {
        str(record.get("record_id", "")): record
        for record in rows
        if record.get("record_id") and record.get("ai_summary") and record.get("ai_easy_language")
    }


def suggest_record_summary(
    record: dict,
    *,
    provider: str,
    model: str,
    base_url: str,
    api_key: str,
    http_client: HttpClient,
) -> dict:
    if provider == "openai":
        return suggest_record_summary_openai(record, model=model, api_key=api_key, http_client=http_client)
    return suggest_record_summary_ollama(record, model=model, base_url=base_url, http_client=http_client)


def system_prompt() -> str:
    return (
        "Du fasst einzelne Grazer Gemeinderatsstücke sachlich auf Deutsch zusammen. "
        "Nutze nur die gelieferten Daten. Erfinde keine Fakten. Antworte nur mit JSON. "
        'Schema: {"summary": "2 bis 4 kurze Sätze", "easy_language": "3 bis 5 sehr einfache Sätze"}'
    )


def record_prompt(record: dict) -> dict:
    return {
        "datum": record.get("meeting_date", ""),
        "typ": record.get("record_type", ""),
        "stueck": record.get("agenda_item_no", ""),
        "einbringer": record.get("submitter", ""),
        "geschaeftszahlen": record.get("business_numbers", []),
        "titel": record.get("title", ""),
        "ergebnis": record.get("result_text", ""),
        "ergebnisquelle": record.get("result_source", ""),
        "betraege": record.get("amounts", []),
        "orte": record.get("locations", []),
        "quellenausschnitt": record.get("source_snippet", ""),
        "auftrag": (
            "Erstelle eine kurze fachliche Zusammenfassung der wichtigsten Punkte. "
            "Erstelle zusätzlich eine Version in einfacher Sprache für Menschen mit kognitiven Einschränkungen. "
            "Bei schriftlichen Anträgen, Anfragen und Dringlichkeitsanträgen formuliere klar, dass der Einbringer "
            "etwas fordert, beantragt, fragt oder auf ein Problem hinweist. Schreibe nicht pauschal, die Gemeinde "
            "habe ein Problem, wenn nur ein Gemeinderatsmitglied oder Klub darauf hinweist. "
            "Keine Rohzitate und keine unsicheren Vermutungen."
        ),
    }


def suggest_record_summary_ollama(record: dict, *, model: str, base_url: str, http_client: HttpClient) -> dict:
    root_url = (base_url or os.getenv("OLLAMA_HOST") or DEFAULT_OLLAMA_URL).rstrip("/")
    payload = {
        "model": model,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.1,
            "num_ctx": 4096,
        },
        "messages": [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": json.dumps(record_prompt(record), ensure_ascii=False)},
        ],
    }
    response = http_client.post(f"{root_url}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    return parse_ollama_response_json(response.json())


def suggest_record_summary_openai(record: dict, *, model: str, api_key: str, http_client: HttpClient) -> dict:
    payload = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt()}]},
            {"role": "user", "content": [{"type": "input_text", "text": json.dumps(record_prompt(record), ensure_ascii=False)}]},
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "record_summary",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "summary": {"type": "string"},
                        "easy_language": {"type": "string"},
                    },
                    "required": ["summary", "easy_language"],
                },
                "strict": True,
            }
        },
    }
    response = http_client.post(
        OPENAI_RESPONSES_URL,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return parse_response_json(response.json())


def valid_summary(result: dict) -> bool:
    summary = str(result.get("summary", "")).strip()
    easy_language = str(result.get("easy_language", "")).strip()
    if len(summary) < 20 or len(easy_language) < 20:
        return False
    if len(summary) > 1000 or len(easy_language) > 1200:
        return False
    return True


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows
