from __future__ import annotations

import json
import os
from typing import Protocol

import requests


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_AI_MODEL = "gpt-4o-mini"


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: object) -> requests.Response: ...


def annotate_topic_headings(
    candidates: list[dict],
    *,
    model: str = DEFAULT_AI_MODEL,
    api_key: str | None = None,
    limit: int = 50,
    http_client: HttpClient | None = None,
) -> list[dict]:
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY ist nicht gesetzt.")
    client = http_client or requests
    annotated: list[dict] = []
    for index, candidate in enumerate(candidates):
        if index >= limit:
            annotated.append(candidate)
            continue
        ai_result = suggest_heading(candidate, model=model, api_key=key, http_client=client)
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


def suggest_heading(candidate: dict, *, model: str, api_key: str, http_client: HttpClient) -> dict | None:
    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "Du erzeugst kurze, sachliche deutsche Überschriften für Themenverläufe "
                            "aus Grazer Gemeinderatsbeschlüssen. Antworte nur mit JSON. "
                            "Keine Aktenzeichen als Haupttitel, keine Jahreszahlen als Titel, keine Füllwörter."
                        ),
                    }
                ],
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
    result = parse_response_json(response.json())
    if not valid_ai_heading(result):
        return None
    return {
        "label": str(result["label"]).strip(),
        "reason": str(result["reason"]).strip(),
        "confidence": round(float(result["confidence"]), 3),
    }


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
