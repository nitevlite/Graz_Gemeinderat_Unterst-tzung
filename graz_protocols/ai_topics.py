from __future__ import annotations

import json
import os
from typing import Protocol

import requests


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
DEFAULT_OLLAMA_MODEL = "qwen2.5:7b-instruct"
DEFAULT_OLLAMA_URL = "http://localhost:11434"
DEFAULT_AI_MODEL = DEFAULT_OLLAMA_MODEL
DEFAULT_AI_PROVIDER = "ollama"


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: object) -> requests.Response: ...


def annotate_topic_headings(
    candidates: list[dict],
    *,
    model: str = DEFAULT_AI_MODEL,
    provider: str = DEFAULT_AI_PROVIDER,
    base_url: str = "",
    api_key: str | None = None,
    limit: int = 50,
    http_client: HttpClient | None = None,
) -> list[dict]:
    provider = provider.lower().strip()
    if provider not in {"ollama", "openai"}:
        raise RuntimeError(f"Unbekannter KI-Provider: {provider}")
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if provider == "openai" and not key:
        raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt.")
    client = http_client or requests
    selected_model = model or (DEFAULT_OPENAI_MODEL if provider == "openai" else DEFAULT_OLLAMA_MODEL)
    annotated: list[dict] = []
    for index, candidate in enumerate(candidates):
        if index >= limit:
            annotated.append(candidate)
            continue
        ai_result = suggest_heading(
            candidate,
            model=selected_model,
            provider=provider,
            base_url=base_url,
            api_key=key,
            http_client=client,
        )
        if not ai_result:
            annotated.append(candidate)
            continue
        original_label = candidate.get("label", "")
        updated = dict(candidate)
        updated["rule_label"] = original_label
        updated["label"] = ai_result["label"]
        updated["ai_label"] = ai_result["label"]
        updated["ai_reason"] = ai_result["reason"]
        updated["ai_confidence"] = ai_result["confidence"]
        updated["label_source"] = "ki"
        annotated.append(updated)
    return annotated


def suggest_heading(
    candidate: dict,
    *,
    model: str,
    provider: str,
    base_url: str,
    api_key: str,
    http_client: HttpClient,
) -> dict | None:
    if provider == "openai":
        result = suggest_heading_openai(candidate, model=model, api_key=api_key, http_client=http_client)
    else:
        result = suggest_heading_ollama(candidate, model=model, base_url=base_url, http_client=http_client)
    if not valid_ai_heading(result):
        return None
    return {
        "label": str(result["label"]).strip(),
        "reason": str(result["reason"]).strip(),
        "confidence": round(float(result["confidence"]), 3),
    }


def system_prompt() -> str:
    return (
        "Du erzeugst kurze, sachliche deutsche Überschriften für Themenverläufe "
        "aus Grazer Gemeinderatsbeschlüssen. Antworte nur mit JSON. "
        "Keine Aktenzeichen als Haupttitel, keine Jahreszahlen als Titel, keine Füllwörter. "
        'Schema: {"label": "2 bis 7 Wörter", "reason": "kurze Begründung", "confidence": 0.0 bis 1.0}.'
    )


def suggest_heading_openai(candidate: dict, *, model: str, api_key: str, http_client: HttpClient) -> dict:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": system_prompt()}],
            },
            {
                "role": "user",
                "content": [{"type": "input_text", "text": json.dumps(topic_prompt(candidate), ensure_ascii=False)}],
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "topic_heading",
                "schema": {
                    "type": "object",
                    "additionalProperties": False,
                    "properties": {
                        "label": {"type": "string"},
                        "reason": {"type": "string"},
                        "confidence": {"type": "number"},
                    },
                    "required": ["label", "reason", "confidence"],
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


def suggest_heading_ollama(candidate: dict, *, model: str, base_url: str, http_client: HttpClient) -> dict:
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
            {"role": "user", "content": json.dumps(topic_prompt(candidate), ensure_ascii=False)},
        ],
    }
    response = http_client.post(f"{root_url}/api/chat", json=payload, timeout=120)
    response.raise_for_status()
    return parse_ollama_response_json(response.json())


def topic_prompt(candidate: dict) -> dict:
    return {
        "regel_titel": candidate.get("label", ""),
        "geschaeftszahl": candidate.get("business_number", ""),
        "grund": candidate.get("reason", ""),
        "zeitraum": candidate.get("dates", []),
        "ueberschriften": [
            {
                "datum": record.get("meeting_date", ""),
                "titel": record.get("title", ""),
            }
            for record in candidate.get("records", [])
            if isinstance(record, dict)
        ],
        "auftrag": (
            "Finde eine prägnante gemeinsame Überschrift mit 2 bis 7 Wörtern. "
            "Sie soll den gemeinsamen Inhalt der Überschriften treffen. "
            "Die Geschäftszahl gehört nicht in den Titel."
        ),
    }


def parse_response_json(payload: dict) -> dict:
    text = payload.get("output_text")
    if isinstance(text, str) and text.strip():
        return json.loads(text)
    for item in payload.get("output", []):
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return json.loads(text)
    return {}


def parse_ollama_response_json(payload: dict) -> dict:
    message = payload.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return parse_json_text(content)
    response_text = payload.get("response")
    if isinstance(response_text, str) and response_text.strip():
        return parse_json_text(response_text)
    return {}


def parse_json_text(text: str) -> dict:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`").strip()
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:].strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end >= start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)


def valid_ai_heading(result: dict) -> bool:
    label = str(result.get("label", "")).strip()
    if not label or len(label) > 90:
        return False
    if len(label.split()) > 9:
        return False
    try:
        confidence = float(result.get("confidence", 0))
    except (TypeError, ValueError):
        return False
    return 0 <= confidence <= 1
