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
    "änderung",
    "aenderung",
    "entwurf",
    "auflage",
    "beschluss",
    "jahre",
    "jahr",
    "nicht",
    "hoehe",
    "höhe",
    "betr",
    "betrag",
    "lcf",
    "anpassung",
    "anpassungen",
    "adaptierung",
    "bestehenden",
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
        label = topic_label(group_records, fallback=value)
        candidates.append(
            {
                "topic_id": stable_topic_id(key),
                "label": label,
                "business_number": value if reason_type == "business" else "",
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


def topic_label(records: list[dict], fallback: str) -> str:
    titles = [str(record.get("title", "")) for record in records if record.get("title")]
    if not titles:
        return fallback
    shared = shared_title_tokens(titles)
    if shared:
        return " ".join(shared)
    compact = compact_title(titles[0])
    return compact or fallback


def shared_title_tokens(titles: list[str]) -> list[str]:
    tokenized = [title_tokens(title) for title in titles]
    if len(tokenized) < 2:
        return []
    threshold = max(2, len(tokenized) - 1)
    counts: dict[str, int] = defaultdict(int)
    display: dict[str, str] = {}
    for tokens in tokenized:
        seen: set[str] = set()
        for raw, normalized in tokens:
            if normalized in seen:
                continue
            seen.add(normalized)
            counts[normalized] += 1
            display.setdefault(normalized, raw)
    common = {token for token, count in counts.items() if count >= threshold}
    first_title_common = [display[normalized] for _, normalized in tokenized[0] if normalized in common]
    return unique_preserve_order(first_title_common)[:8]


def compact_title(title: str) -> str:
    tokens = [raw for raw, _ in title_tokens(title)]
    return " ".join(unique_preserve_order(tokens)[:6])


def title_tokens(title: str) -> list[tuple[str, str]]:
    cleaned = re.sub(
        r"\b(?:Präs\.?|Praes\.?|AB|A\s*\d+(?:/\s*[A-Z]{1,3})?(?:/\d+)?|A\d+(?:/\s*[A-Z]{1,3})?(?:/\d+)?)"
        r"\s*[-–]?\s*\d[\d/\-–\s]*",
        " ",
        title,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"€\s*\d[\d.\s]*(?:,\s*(?:\d{1,2}|-+))?", " ", cleaned)
    words = re.findall(r"[A-ZÄÖÜa-zäöüß][\wÄÖÜäöüß-]{2,}", cleaned)
    tokens: list[tuple[str, str]] = []
    for word in words:
        normalized = normalize_token(word)
        if len(normalized) < 4 or normalized in STOPWORDS or any(char.isdigit() for char in normalized):
            continue
        tokens.append((pretty_word(word), normalized))
    return tokens


def normalize_token(value: str) -> str:
    normalized = value.casefold().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue").replace("ß", "ss")
    normalized = re.sub(r"[^a-z0-9-]+", "", normalized)
    return normalized


def pretty_word(value: str) -> str:
    if value.isupper():
        return value
    return value[:1].upper() + value[1:]


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(value)
    return result


def stable_topic_id(value: str) -> str:
    slug = re.sub(r"[^a-z0-9äöüß]+", "-", value.casefold()).strip("-")
    return slug[:80] or "topic"
