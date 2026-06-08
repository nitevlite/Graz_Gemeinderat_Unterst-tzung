from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import json
import re


STOPWORDS = {
    "der",
    "die",
    "das",
    "und",
    "von",
    "für",
    "fuer",
    "mit",
    "eine",
    "einer",
    "eines",
    "den",
    "dem",
    "des",
    "stadt",
    "graz",
    "beschluss",
    "projektgenehmigung",
}


def write_topic_candidates(records_path: Path, output_path: Path) -> None:
    records = read_jsonl(records_path)
    candidates = build_topic_candidates(records)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(candidates, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict]:
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def build_topic_candidates(records: list[dict]) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        for number in record.get("business_numbers", []):
            groups[f"business:{base_business_number(number)}"].append(record)
        for keyword in topic_keywords(record.get("title", "")):
            groups[f"keyword:{keyword}"].append(record)

    candidates: list[dict] = []
    for key, group_records in sorted(groups.items()):
        dates = sorted({record.get("meeting_date", "") for record in group_records if record.get("meeting_date")})
        if len(dates) < 2:
            continue
        reason_type, value = key.split(":", 1)
        confidence = 0.95 if reason_type == "business" else min(0.85, 0.45 + len(group_records) * 0.08)
        candidates.append(
            {
                "topic_id": stable_topic_id(key),
                "label": value,
                "reason": "gleiche Geschäftszahl-Basis" if reason_type == "business" else "wiederkehrender Titelbegriff",
                "confidence": round(confidence, 3),
                "dates": dates,
                "records": [
                    {
                        "record_id": record.get("record_id", ""),
                        "meeting_date": record.get("meeting_date", ""),
                        "record_type": record.get("record_type", ""),
                        "agenda_item_no": record.get("agenda_item_no", ""),
                        "title": record.get("title", ""),
                        "result_source": record.get("result_source", ""),
                    }
                    for record in sorted(group_records, key=lambda item: (item.get("meeting_date", ""), item.get("record_id", "")))
                ],
            }
        )
    return sorted(candidates, key=lambda item: (-item["confidence"], item["label"]))[:200]


def base_business_number(value: str) -> str:
    return re.sub(r"/\d+$", "", value.strip())


def topic_keywords(title: str) -> list[str]:
    normalized = re.sub(r"[^\wÄÖÜäöüß-]+", " ", title.casefold())
    tokens = [token for token in normalized.split() if len(token) >= 6 and token not in STOPWORDS]
    seen: set[str] = set()
    result: list[str] = []
    for token in tokens:
        if token in seen:
            continue
        seen.add(token)
        result.append(token)
    return result[:4]


def stable_topic_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", value.casefold()).strip("-")
    return slug[:80] or "topic"
