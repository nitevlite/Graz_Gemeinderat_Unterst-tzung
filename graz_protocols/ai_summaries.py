from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Protocol

import requests

from .ai_topics import DEFAULT_OLLAMA_MODEL, DEFAULT_OLLAMA_URL, parse_ollama_response_json, parse_response_json


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
DEFAULT_OPENAI_MODEL = "gpt-4o-mini"
SUMMARY_EXTRA_FIELDS = ("why_interesting", "key_points", "open_points", "source_limits")
AI_SUMMARY_FIELDS = (
    "ai_summary",
    "ai_easy_language",
    "ai_why_interesting",
    "ai_key_points",
    "ai_open_points",
    "ai_source_limits",
)


class HttpClient(Protocol):
    def post(self, url: str, **kwargs: object) -> requests.Response: ...


def write_record_summaries(
    records_path: Path,
    output_path: Path,
    *,
    provider: str = "local",
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
        "records_with_ai_key_points": sum(1 for record in enriched if record.get("ai_key_points")),
        "output": str(output_path),
    }


def annotate_record_summaries(
    records: list[dict],
    *,
    provider: str = "local",
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
    if provider not in {"ollama", "openai", "local"}:
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
            for field in AI_SUMMARY_FIELDS:
                if field in existing:
                    updated[field] = existing[field]
            for key, value in existing.items():
                if key not in updated:
                    updated[key] = value
            write_incremental_record(output_handle, updated)
            enriched.append(updated)
            continue
        if not overwrite and record_has_complete_summary(updated):
            write_incremental_record(output_handle, updated)
            enriched.append(updated)
            continue
        if limit > 0 and processed >= limit:
            write_incremental_record(output_handle, updated)
            enriched.append(updated)
            continue
        if provider == "local":
            result = suggest_record_summary_local(updated)
        else:
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
            apply_summary_result(updated, result)
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
        if record.get("record_id") and record_has_complete_summary(record)
    }


def record_has_complete_summary(record: dict) -> bool:
    return bool(
        record.get("ai_summary")
        and record.get("ai_easy_language")
    )


def apply_summary_result(record: dict, result: dict) -> None:
    defaults = default_summary_extras(record)
    record["ai_summary"] = final_summary_text(str(result.get("summary", "")))
    record["ai_easy_language"] = final_summary_text(str(result.get("easy_language", "")))
    record["ai_why_interesting"] = ""
    record["ai_key_points"] = []
    record["ai_open_points"] = []
    record["ai_source_limits"] = normalize_text_list(result.get("source_limits"), defaults["source_limits"])


def final_summary_text(value: str) -> str:
    text = clean_text(value)
    text = text.translate(str.maketrans({"„": "", "“": "", "”": "", "«": "", "»": ""}))
    text = re.sub(r'"([^"]{1,120})"', r"\1", text)
    return clean_text(text)


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


def suggest_record_summary_local(record: dict) -> dict:
    title = summary_title_for_record(record)
    date = clean_text(str(record.get("meeting_date", "")))
    submitter = clean_text(str(record.get("submitter", "")))
    result = clean_text(str(record.get("result_text", "")))
    snippet = clean_text(str(record.get("source_snippet", "")))
    business_numbers = clean_list(record.get("business_numbers", []))
    locations = clean_list(record.get("locations", []))
    amounts = clean_list(record.get("amounts", []))

    if str(record.get("record_type", "")) in {"question_hour", "written_question"}:
        return suggest_question_summary_local(
            record,
            title=title,
            date=date,
            submitter=submitter,
            result=result,
            business_numbers=business_numbers,
            locations=locations,
        )

    facts: list[str] = []
    content = summarize_snippet(snippet, max_sentences=7, max_chars=1500)
    if content:
        facts.append(f"{local_record_intro(record)} das Thema {title}. {content}")
    else:
        facts.append(f"{local_record_intro(record)} das Thema {title}.")
    if submitter:
        facts.append(f"Eingebracht oder bearbeitet wurde der Punkt von {submitter}.")
    if locations:
        facts.append(f"Räumlich genannt werden {', '.join(locations[:4])}.")
    if amounts:
        facts.append(f"Im Eintrag kommen Beträge wie {', '.join(amounts[:3])} vor.")
    interest = public_interest_sentence(record, title)
    if interest:
        facts.append(interest)
    if has_meaningful_result(result):
        facts.append(f"Das dokumentierte Ergebnis lautet: {result}.")
    else:
        facts.append("Ein belastbares Ergebnis ist in den lokalen Daten noch nicht erfasst.")
    if business_numbers:
        facts.append(f"Geschäftszahl: {', '.join(business_numbers[:2])}.")

    easy: list[str] = []
    easy.append(f"Es geht um {title}.")
    if content:
        easy.extend(easy_language_sentences(content))
    if submitter:
        easy.append(f"Eingebracht oder bearbeitet wurde der Punkt von {submitter}.")
    if locations:
        easy.append(f"Genannte Orte: {', '.join(locations[:3])}.")
    if has_meaningful_result(result):
        easy.append(f"Ergebnis: {result}.")
    else:
        easy.append("Ein klares Ergebnis steht noch nicht in den lokalen Daten.")
    if date:
        easy.append(f"Sitzung: {date}.")
    extras = default_summary_extras(record)

    return {
        "summary": " ".join(facts),
        "easy_language": " ".join(easy),
        **extras,
    }


def suggest_question_summary_local(
    record: dict,
    *,
    title: str,
    date: str,
    submitter: str,
    result: str,
    business_numbers: list[str],
    locations: list[str],
) -> dict:
    record_type = str(record.get("record_type", ""))
    parts = record.get("question_parts", {})
    parts = parts if isinstance(parts, dict) else {}
    answer = clean_text(str(parts.get("answer", "")))
    followup_answer = clean_text(str(parts.get("followup_answer", "")))
    recipient = clean_text(str(record.get("recipient", "") or record.get("addressee", "")))
    type_label = "Fragestunde" if record_type == "question_hour" else "schriftliche Anfrage"
    question_title = clean_question_summary_title(title, submitter)

    facts = [f"Die {type_label} betrifft das Thema {question_title}."]
    if submitter:
        facts.append(f"Gefragt hat {submitter}.")
    if recipient:
        facts.append(f"Adressiert ist die Frage an {recipient}.")
    answer_summary = summarize_answer_text(answer)
    followup_answer_summary = summarize_answer_text(followup_answer)
    if answer_summary:
        facts.append(f"Erfasste Antwort: {answer_summary}")
    elif followup_answer_summary:
        facts.append(f"Erfasste Antwort zur Nachfrage: {followup_answer_summary}")
    elif has_meaningful_result(result):
        facts.append(f"Der dokumentierte Stand lautet: {result}.")
    else:
        facts.append("Eine Antwort ist in der lokalen Datenbasis nicht erfasst.")
    if locations:
        facts.append(f"Räumlich genannt werden {', '.join(locations[:4])}.")
    if business_numbers:
        facts.append(f"Geschäftszahl: {', '.join(business_numbers[:2])}.")

    easy = [f"Es geht um {question_title}."]
    if submitter:
        easy.append(f"Gefragt hat {submitter}.")
    if answer_summary:
        easy.append(f"Die erfasste Antwort sagt kurz: {answer_summary}")
    elif followup_answer_summary:
        easy.append(f"Zur Nachfrage ist kurz erfasst: {followup_answer_summary}")
    elif has_meaningful_result(result):
        easy.append(f"Stand: {result}.")
    else:
        easy.append("In den lokalen Daten steht keine Antwort.")
    if locations:
        easy.append(f"Genannte Orte: {', '.join(locations[:3])}.")
    if date:
        easy.append(f"Sitzung: {date}.")
    extras = default_summary_extras(record)

    return {
        "summary": " ".join(facts),
        "easy_language": " ".join(easy),
        **extras,
    }


def local_record_intro(record: dict) -> str:
    return {
        "agenda_item": "Der Tagesordnungspunkt behandelt",
        "communication": "Die Mitteilung behandelt",
        "question_hour": "Die Fragestunde behandelt",
        "urgent_motion": "Der Dringlichkeitsantrag behandelt",
        "written_question": "Die schriftliche Anfrage behandelt",
        "written_motion": "Der schriftliche Antrag behandelt",
        "amendment_motion": "Der Abänderungsantrag behandelt",
        "additional_motion": "Der Zusatzantrag behandelt",
        "archive_agenda_item": "Der Archiv-Tagesordnungspunkt behandelt",
        "archive_source": "Die Archivquelle behandelt",
        "attendance_list": "Die Anwesenheitsliste behandelt",
    }.get(str(record.get("record_type", "")), "Der Eintrag behandelt")


def summarize_snippet(value: str, max_sentences: int = 2, max_chars: int = 650) -> str:
    if not value:
        return ""
    value = clean_summary_source_text(value)
    sentences = re_split_sentences(value)
    selected = sentences[:max_sentences] if sentences else [value]
    if selected and not sentence_complete(selected[-1]) and len(selected) > 1:
        selected = selected[:-1]
    text = clean_text(" ".join(selected))
    if len(text) <= max_chars:
        return text.strip()
    return trim_to_sentence_boundary(text, max_chars)


def summarize_answer_text(value: str, limit: int = 260) -> str:
    text = clean_summary_source_text(value)
    text = re.sub(r"^(?:Antwort|Zusatzantwort)\s*:?\s*", "", text, flags=re.IGNORECASE).strip()
    text = remove_leading_salutation(text)
    if looks_like_question_text(text):
        return ""
    if not text:
        return ""
    if len(text) <= limit:
        return text if text.endswith(".") else f"{text}."
    return text[:limit].rsplit(" ", 1)[0].strip(" ,;:") + "."


def clean_question_summary_title(title: str, submitter: str = "") -> str:
    text = clean_text(title)
    if not text:
        return "diese Frage"
    if re.match(r"^[„\"']?(?:sehr geehrt\w*|werter|werte|liebe kolleg)\b", text, flags=re.IGNORECASE):
        return "eine Frage in der Gemeinderatssitzung"
    if re.search(r"originaltext der frage", text, flags=re.IGNORECASE):
        return "eine Frage in der Gemeinderatssitzung"
    salutation = re.search(r"\s+(?:sehr geehrt\w*|werter|werte|liebe kolleg).*$", text, flags=re.IGNORECASE)
    if salutation and salutation.start() >= 8:
        text = text[: salutation.start()].strip(" ,.;:")
    if re.search(
        r"\b(Herr Bürgermeister|sehr geehrt\w*|liebe Kolleg|meine Frage|in meiner Frage|folgende Frage)\b",
        text,
        flags=re.IGNORECASE,
    ) or re.match(r"^[„\"']?(?:wie|was|warum|wieso|welche|mit welchen|in welcher|dürfen|duerfen|sind sie|haben sie|liegen|konnte)\b", text, flags=re.IGNORECASE):
        prefix = text.split(":", 1)[0].strip() if ":" in text else ""
        if prefix and len(prefix) <= 80 and re.search(r"\bGR\b|Gemeinder", prefix, flags=re.IGNORECASE):
            return f"eine Frage von {prefix}"
        if submitter:
            return f"eine Frage von {submitter}"
        return "eine Frage in der Gemeinderatssitzung"
    return text


def remove_leading_salutation(value: str) -> str:
    text = clean_text(value)
    if not re.match(
        r"(?i)^(?:sehr geehrt|werter|werte|liebe|geschätzte|geschaetzte|frau |herr |danke für die frage|danke für deine frage)",
        text,
    ):
        return text
    stripped = re.sub(
        r"(?is)^(?:sehr geehrte?r?|werter|werte|liebe|geschätzte|geschaetzte|frau|herr|danke für die frage|danke für deine frage)"
        r"[^.!?]{0,220}[.!?]\s*",
        "",
        text,
        count=1,
    ).strip()
    return stripped or text


def looks_like_question_text(value: str) -> bool:
    text = clean_text(value).casefold()
    return bool(
        re.search(r"\b(meine frage|in meiner frage|folgende frage|frage richtet sich|ich richte.*frage)\b", text)
        or text.endswith("?")
    )


def simplify_sentence(value: str) -> str:
    text = clean_text(value)
    if len(text) <= 260:
        return text
    return trim_to_sentence_boundary(text, 260)


def easy_language_sentences(value: str) -> list[str]:
    sentences = re_split_sentences(value)
    if not sentences:
        return [simplify_sentence(value)]
    simple: list[str] = []
    for sentence in sentences[:4]:
        text = simplify_sentence(sentence)
        text = text.replace("Beschlussvermerk", "offizielle Notiz zum Beschluss")
        text = text.replace("Geschäftszahl", "Aktenzahl")
        simple.append(text)
    return simple


def re_split_sentences(value: str) -> list[str]:
    protected = str(value or "")
    abbreviations = {
        "Abs.": "Abs§",
        "Art.": "Art§",
        "Nr.": "Nr§",
        "Z.": "Z§",
        "lit.": "lit§",
        "z.B.": "z§B§",
        "bzw.": "bzw§",
        "u.a.": "u§a§",
        "d.h.": "d§h§",
    }
    for old, new in abbreviations.items():
        protected = protected.replace(old, new)
    parts = re.split(r"(?<=[.!?])\s+(?=[A-ZÄÖÜ„\"'])", protected)
    sentences = []
    for part in parts:
        text = part
        for old, new in abbreviations.items():
            text = text.replace(new, old)
        text = text.strip()
        if len(text) > 15:
            sentences.append(text)
    return sentences


def sentence_complete(value: str) -> bool:
    text = clean_text(value)
    return bool(text and re.search(r"[.!?]$|[.“”\"']$", text) and not re.search(r"\b(?:Abs|Art|Nr|Z|lit)\.$", text))


def local_record_type_label(record: dict) -> str:
    return {
        "agenda_item": "einen Tagesordnungspunkt",
        "communication": "eine Mitteilung",
        "question_hour": "einen Beitrag aus der Fragestunde",
        "urgent_motion": "einen Dringlichkeitsantrag",
        "written_question": "eine schriftliche Anfrage",
        "written_motion": "einen schriftlichen Antrag",
        "amendment_motion": "einen Abänderungsantrag",
        "additional_motion": "einen Zusatzantrag",
        "archive_agenda_item": "einen Tagesordnungspunkt aus einem Archiv-PDF",
        "archive_source": "eine Archivquelle",
        "attendance_list": "eine Anwesenheitsliste",
    }.get(str(record.get("record_type", "")), "einen Gemeinderatseintrag")


def clean_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [clean_text(str(item)) for item in value if clean_text(str(item))]


def clean_text(value: str) -> str:
    text = " ".join(value.split())
    text = re.sub(r"\bEs wird folgender gestellt\b", "Es wird folgender Antrag gestellt", text)
    text = re.sub(r"\bEs wird folgende gestellt\b", "Es wird folgende Anfrage gestellt", text)
    return text


def clean_summary_source_text(value: str) -> str:
    text = clean_text(value)
    text = remove_direct_quote_blocks(text)
    text = re.sub(r"\bOriginaltext\s+des\s+(?:Antrages|Antrags|der Anfrage)\s*:?", "", text, flags=re.IGNORECASE).strip()
    text = re.sub(r"\bEs wird folgender Antrag gestellt\s*:\s*", "Es wird beantragt: ", text, flags=re.IGNORECASE)
    text = re.sub(r"\bDer Gemeinderat wolle\s+gemäß\s+§\s*45\s+Abs\.\s*[^:]{0,260}\bbeschließen\s*:?", "Der Gemeinderat soll beschließen:", text, flags=re.IGNORECASE)
    text = re.sub(r"\bDer Gemeinderat wolle\s+beschließen\s*:?", "Der Gemeinderat soll beschließen:", text, flags=re.IGNORECASE)
    text = re.sub(r"\bim Zuge meiner schriftlichen Fragebeantwortung\b", "im Zuge einer schriftlichen Fragebeantwortung", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmeiner schriftlichen Fragebeantwortung\b", "einer schriftlichen Fragebeantwortung", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmeine schriftliche Anfrage\b", "die schriftliche Anfrage", text, flags=re.IGNORECASE)
    text = re.sub(r"\bmeiner schriftlichen Anfrage\b", "der schriftlichen Anfrage", text, flags=re.IGNORECASE)
    text = re.sub(r"\bvon deiner Seite\b", "von zuständiger Seite", text, flags=re.IGNORECASE)
    text = re.sub(r"\bdeinerseits\b", "von zuständiger Seite", text, flags=re.IGNORECASE)
    text = re.sub(r"(^|[.!?]\s+)im Zuge\b", lambda match: f"{match.group(1)}Im Zuge", text)
    return clean_text(text)


def remove_direct_quote_blocks(value: str) -> str:
    text = value
    text = re.sub(r"\([^)]*Applaus[^)]*\)", "", text, flags=re.IGNORECASE)
    text = re.sub(r"„[^“]{25,900}“", "", text)
    text = re.sub(r"\"[^\"]{25,900}\"", "", text)
    text = re.sub(r"“[^”]{25,900}”", "", text)
    text = re.sub(r"\b(?:so\s+)?(?:zitierte|zitiert|wuerdigte|würdigte)\b[^.?!]{0,240}[.?!]", "", text, flags=re.IGNORECASE)
    return clean_text(text)


def clean_summary_title(value: str) -> str:
    title = clean_text(value).strip(" ,;:-")
    title = re.sub(r"^(?:Frage|Antwort)\s*:\s*", "", title, flags=re.IGNORECASE).strip(" ,;:-")
    title = re.sub(r"\bvon deiner Seite\b", "von zuständiger Seite", title, flags=re.IGNORECASE)
    title = re.sub(r"\bdeinerseits\b", "von zuständiger Seite", title, flags=re.IGNORECASE)
    if re.match(r"^(?:Sehr geehrte|Sehr geehrter|Sehr geehrtes|Werter|Werte|Liebe)\b", title, flags=re.IGNORECASE):
        return ""
    role_pattern = (
        r"^(?:Berichterstatter(?:in|:in)?|Bearbeiter(?:in|:in)?|Einbringer(?:in|:in)?)\s*:?\s*"
        r"[^:;]{0,220}?(?:\([^)]{1,80}\)|,?\s(?:KPÖ|KPOE|Grüne|Gruene|SPÖ|SPOE|ÖVP|OEVP|FPÖ|FPOE|NEOS|KFG|GRÜNE))\s+"
    )
    previous = ""
    while title and title != previous:
        previous = title
        title = re.sub(role_pattern, "", title, flags=re.IGNORECASE).strip(" ,;:-")
    title = re.sub(r"\s+(?:Sehr geehrte Frau|Sehr geehrter Herr|Sehr geehrte Damen und Herren)\b.*$", "", title, flags=re.IGNORECASE)
    return title or clean_text(value)


def summary_title_for_record(record: dict) -> str:
    raw_title = clean_summary_title(str(record.get("title", "")))
    if raw_title and not role_only_summary_title(raw_title):
        return raw_title
    snippet_title = clean_summary_snippet_title(str(record.get("source_snippet", "")))
    return snippet_title or raw_title or "Ohne Titel"


def role_only_summary_title(value: str) -> bool:
    return bool(
        re.match(
            r"^(?:Berichterstatter(?:in|:in)?|Bearbeiter(?:in|:in)?|Einbringer(?:in|:in)?)\s*:?\s*",
            clean_text(value),
            re.IGNORECASE,
        )
    )


def clean_summary_snippet_title(value: str) -> str:
    title = clean_summary_title(value)
    title = re.split(
        r"\s+(?:I\.\s+Allgemeiner\s+Teil|II\.\s+Besonderer\s+Teil|Der\s+Gemeinderat\s+hat|Frau\s+GR|Herr\s+GR|Es\s+wird|Sehr geehrte Frau|Sehr geehrter Herr)\b",
        title,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip(" ,;:-")
    if len(title) > 220:
        title = title[:220].rsplit(" ", 1)[0].strip(" ,;:-")
    if len(title.split()) < 2:
        return ""
    return title


def trim_to_sentence_boundary(value: str, max_chars: int) -> str:
    text = clean_text(value)
    if len(text) <= max_chars:
        return text
    clipped = text[:max_chars].rsplit(" ", 1)[0].strip(" ,;:")
    boundary = max(clipped.rfind("."), clipped.rfind("!"), clipped.rfind("?"))
    if boundary >= int(max_chars * 0.55):
        return clipped[: boundary + 1].strip()
    if re.search(r"\b(?:Abs|Art|Nr|Z|lit)\.$", clipped):
        clipped = re.sub(r"\b(?:Abs|Art|Nr|Z|lit)\.$", "", clipped).strip(" ,;:")
    return clipped + "."


def has_meaningful_result(result: str) -> bool:
    normalized = clean_text(result).casefold()
    return bool(normalized) and normalized not in {
        "unbekannt",
        "digra-ergebnis fehlt",
        "kein ergebnis",
        "keine angabe",
    }


def default_summary_extras(record: dict) -> dict:
    result = clean_text(str(record.get("result_text", "")))
    title = summary_title_for_record(record)
    record_type = str(record.get("record_type", ""))
    locations = clean_list(record.get("locations", []))
    amounts = clean_list(record.get("amounts", []))
    business_numbers = clean_list(record.get("business_numbers", []))
    key_points = default_key_points(record, title, result)
    open_points = default_open_points(record, result)
    source_limits = default_source_limits(record)
    why_parts = [public_interest_sentence(record, title)]
    if locations:
        why_parts.append(f"Betroffen sein können Menschen, die mit {', '.join(locations[:3])} zu tun haben.")
    if amounts:
        why_parts.append(f"Auch Geld spielt eine Rolle, weil Beträge wie {', '.join(amounts[:3])} genannt werden.")
    if business_numbers:
        why_parts.append(f"Über die Geschäftszahl {', '.join(business_numbers[:2])} kann der Vorgang später wiedergefunden werden.")
    if record_type in {"written_motion", "urgent_motion", "written_question", "question_hour"}:
        why_parts.append("Wichtig ist die Trennung zwischen politischem Anliegen und belegter Entscheidung.")
    return {
        "why_interesting": " ".join(why_parts),
        "key_points": key_points,
        "open_points": open_points,
        "source_limits": source_limits,
    }


def public_interest_sentence(record: dict, title: str) -> str:
    haystack = f"{title} {record.get('source_snippet', '')}".casefold()
    if re.search(r"\b(sozial|sozialamt|pflege|gesundheit|behinder|inklusion|senior|armut)\b", haystack):
        return "Für Leserinnen und Leser ist wichtig, welche sozialen Leistungen betroffen sind und ob Zuständigkeiten, Personal oder Unterstützung verlässlich geklärt werden."
    if re.search(r"(parkplatz|parkplätze|parkplaetze|parkmöglich|parkmoeglich|\bparken\b|\bparkgarage\b|\bverkehr\b|\bstraße\b|\bstrasse\b|\bbaustelle\b|\bgarage\b|\bradweg\b|\bradfahrer\b|\bfahrrad\b|\bbus\b|\bbahn\b)", haystack):
        return "Für die Öffentlichkeit zählt hier vor allem, wie sich die Regelung auf Wege, Parkraum, Verkehrssicherheit oder die Nutzung des öffentlichen Raums auswirkt."
    if re.search(r"schule|bildung|kindergarten|kinderkrippe|kinderbetreuung|betreuungsplatz|jugend", haystack):
        return "Bedeutsam ist der Punkt, weil Schulen, Kinderbetreuung oder Angebote für junge Menschen viele Familien und Beschäftigte im Alltag betreffen."
    if re.search(r"kosten|euro|budget|förder|foerder|finanz", haystack):
        return "Für Leserinnen und Leser ist entscheidend, welche Ausgaben, Förderungen oder Beteiligungen beschlossen werden und wie diese Entscheidung begründet ist."
    if re.search(r"wohnen|miete|siedlung|bau|bebauung|stadtentwicklung", haystack):
        return "Relevant ist das, weil solche Entscheidungen das Wohnumfeld, Bauvorhaben oder die Entwicklung einzelner Stadtteile direkt beeinflussen können."
    if re.search(r"\b(personal|leitung|ausschreibung|führung|fuehrung)\b", haystack):
        return "Wichtig ist hier, wie Führungsfunktionen besetzt werden und ob die dafür genannten Gründe nachvollziehbar dokumentiert sind."
    if re.search(r"\b(transparenz|kontrolle|bericht|anfrage|auskunft)\b", haystack):
        return "Der Vorgang zeigt, welche Informationen die Politik von der Verwaltung verlangt und wo Entscheidungen genauer erklärt werden sollen."
    return ""


def default_key_points(record: dict, title: str, result: str) -> list[dict[str, str]]:
    record_type = str(record.get("record_type", ""))
    status = key_point_status(record, result)
    kind = {
        "communication": "Mitteilung",
        "question_hour": "Frage",
        "written_question": "Frage",
        "written_motion": "Forderung",
        "urgent_motion": "Forderung",
        "amendment_motion": "Forderung",
        "additional_motion": "Forderung",
        "agenda_item": "Beschlussgegenstand",
        "archive_agenda_item": "Tagesordnungspunkt",
        "archive_source": "Quelle",
    }.get(record_type, "Kernpunkt")
    simple = {
        "beschlossen": "In den lokalen Daten ist eine Annahme oder ein Beschluss erfasst.",
        "abgelehnt": "In den lokalen Daten ist erfasst, dass der Punkt nicht angenommen wurde.",
        "zugewiesen": "Der Punkt wurde weiterbehandelt oder an eine Stelle weitergegeben.",
        "gefragt": "Es wurde eine Frage gestellt. Das ist noch kein Beschluss.",
        "beantragt": "Es wurde etwas beantragt. Das ist noch keine Umsetzung.",
        "mitgeteilt": "Es wurde etwas mitgeteilt. Das ist nicht automatisch ein Beschluss.",
        "offen": "Der genaue Stand ist in den lokalen Daten nicht belegt.",
        "nicht_erfasst": "Die lokale Datenbasis enthält dazu keine gesicherte Information.",
    }.get(status, "Der Stand muss anhand der Quelle geprüft werden.")
    return [
        {
            "kind": kind,
            "text": title,
            "simple": simple,
            "status": status,
        }
    ]


def key_point_status(record: dict, result: str) -> str:
    record_type = str(record.get("record_type", ""))
    combined = clean_text(f"{record.get('status', '')} {result}").casefold()
    if "angenommen" in combined or "beschlossen" in combined:
        return "beschlossen"
    if "abgelehnt" in combined:
        return "abgelehnt"
    if "zugewiesen" in combined or "vertagt" in combined:
        return "zugewiesen"
    if record_type in {"written_question", "question_hour"}:
        return "gefragt"
    if record_type in {"written_motion", "urgent_motion", "amendment_motion", "additional_motion"}:
        return "beantragt"
    if record_type == "communication":
        return "mitgeteilt"
    if has_meaningful_result(result):
        return "offen"
    return "nicht_erfasst"


def default_open_points(record: dict, result: str) -> list[str]:
    points: list[str] = []
    record_type = str(record.get("record_type", ""))
    parts = record.get("question_parts", {})
    parts = parts if isinstance(parts, dict) else {}
    if not has_meaningful_result(result):
        points.append("Ein gesicherter Ergebnisstand ist in der lokalen Datenbasis nicht erfasst.")
    answer_summary = summarize_answer_text(str(parts.get("answer", "")))
    followup_answer_summary = summarize_answer_text(str(parts.get("followup_answer", "")))
    if record_type in {"written_question", "question_hour"} and not (answer_summary or followup_answer_summary):
        points.append("Eine Antwort ist in der lokalen Datenbasis nicht erfasst.")
    if record_type in {"written_motion", "urgent_motion"} and key_point_status(record, result) == "beantragt":
        points.append("Ob der Antrag später beschlossen oder umgesetzt wurde, muss über Folgeeinträge geprüft werden.")
    return points


def default_source_limits(record: dict) -> list[str]:
    limits: list[str] = []
    if not clean_text(str(record.get("source_snippet", ""))):
        limits.append("Für diesen Eintrag liegt nur strukturierter Metadatenkontext vor.")
    if not record.get("digra_url") and not record.get("source_url"):
        limits.append("Ein direkter Quellenlink ist in den lokalen Daten nicht erfasst.")
    result_source = clean_text(str(record.get("result_source", ""))).casefold()
    if result_source and result_source != "digra":
        limits.append("Der Ergebnisstand stammt nicht aus einem DIGRA-Beschlussvermerk und sollte bei Bedarf geprüft werden.")
    return limits


def normalize_key_points(value: object, fallback: list[dict[str, str]]) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return fallback
    normalized = []
    for item in value[:12]:
        if not isinstance(item, dict):
            continue
        text = clean_text(str(item.get("text", "")))
        if not text:
            continue
        normalized.append(
            {
                "kind": clean_text(str(item.get("kind", "Kernpunkt"))) or "Kernpunkt",
                "text": text,
                "simple": clean_text(str(item.get("simple", ""))),
                "status": normalize_point_status(str(item.get("status", ""))),
            }
        )
    return normalized or fallback


def normalize_point_status(value: str) -> str:
    normalized = clean_text(value).casefold().replace("-", "_")
    allowed = {"beschlossen", "abgelehnt", "zugewiesen", "beantragt", "gefragt", "mitgeteilt", "offen", "nicht_erfasst"}
    return normalized if normalized in allowed else "offen"


def normalize_text_list(value: object, fallback: list[str]) -> list[str]:
    if not isinstance(value, list):
        return fallback
    normalized = [clean_text(str(item)) for item in value if clean_text(str(item))]
    return normalized[:12] if normalized else fallback


def system_prompt() -> str:
    return (
        "Du fasst einzelne Grazer Gemeinderatsstücke sachlich auf Deutsch zusammen. "
        "Nutze nur die gelieferten Daten. Erfinde keine Fakten. Antworte nur mit JSON. "
        "Fasse immer genau einen Eintrag zusammen. Schreibe nicht zu kurz: Die fachliche Zusammenfassung soll "
        "Inhalt, Problem, Einbringer, Forderung oder Frage, Relevanz und Ergebnisstand erklären. "
        "Die einfache Sprache ist für Menschen mit kognitiven Einschränkungen: kurze Sätze, einfache Wörter, klare Trennung "
        "zwischen beschlossen, beantragt, gefragt, mitgeteilt und offen. "
        'Schema: {"summary": "120 bis 220 Wörter, wenn genug Inhalt vorhanden ist", '
        '"easy_language": "80 bis 160 Wörter in einfacher Sprache", '
        '"why_interesting": "öffentliche Bedeutung", '
        '"key_points": [{"kind": "Forderung|Frage|Beschluss|Mitteilung|Kernpunkt", "text": "Kernpunkt", "simple": "einfach erklärt", "status": "beschlossen|abgelehnt|zugewiesen|beantragt|gefragt|mitgeteilt|offen|nicht_erfasst"}], '
        '"open_points": ["fehlende oder offene Information"], "source_limits": ["Quelleneinschränkung"]}'
    )


def record_prompt(record: dict) -> dict:
    record_type = str(record.get("record_type", ""))
    if record_type == "question_hour":
        task = (
            "Dieser Eintrag stammt aus der Fragestunde. Fasse nicht den Wortlaut der Frage zusammen und kopiere keine "
            "Anrede, keine langen Fragesätze und keine abgeschnittenen Textauszüge. Nenne knapp das Thema, wer gefragt "
            "hat, an wen die Frage ging und ob eine Antwort in den gelieferten Daten erfasst ist. Wenn eine Antwort oder "
            "Zusatzantwort im strukturierten Feld steht, fasse nur deren Inhalt kurz zusammen. Wenn keine Antwort erfasst "
            "ist, schreibe genau das. Keine Rohzitate und keine Vermutungen."
        )
    elif record_type == "written_question":
        task = (
            "Dieser Eintrag ist eine schriftliche Anfrage. Fasse nicht den Wortlaut der Frage zusammen und kopiere keine "
            "Anrede, keine langen Fragesätze und keine abgeschnittenen Textauszüge. Nenne knapp Thema, Fragesteller, "
            "Adressat und Antwort-/Verfahrensstand aus den gelieferten Daten. Wenn keine Antwort erfasst ist, schreibe "
            "nur, dass in der lokalen Datenbasis keine Antwort erfasst ist. Keine Rohzitate und keine Vermutungen."
        )
    else:
        task = (
            "Erstelle eine fachliche Zusammenfassung der wichtigsten Punkte. Sie soll nicht nur ein Teaser sein, "
            "sondern den Inhalt des Stücks so erklären, dass Leserinnen und Leser das Original nicht vollständig lesen müssen. "
            "Erstelle zusätzlich eine Version in einfacher Sprache für Menschen mit kognitiven Einschränkungen. "
            "Bei schriftlichen Anträgen, Anfragen und Dringlichkeitsanträgen formuliere klar, dass der Einbringer "
            "etwas fordert, beantragt, fragt oder auf ein Problem hinweist. Schreibe nicht pauschal, die Gemeinde "
            "habe ein Problem, wenn nur ein Gemeinderatsmitglied oder Klub darauf hinweist. "
            "Extrahiere Kernpunkte mit Status. Keine Rohzitate und keine unsicheren Vermutungen."
        )
    return {
        "datum": record.get("meeting_date", ""),
        "typ": record_type,
        "stueck": record.get("agenda_item_no", ""),
        "einbringer": record.get("submitter", ""),
        "geschaeftszahlen": record.get("business_numbers", []),
        "titel": record.get("title", ""),
        "ergebnis": record.get("result_text", ""),
        "ergebnisquelle": record.get("result_source", ""),
        "betraege": record.get("amounts", []),
        "orte": record.get("locations", []),
        "fragestunde": record.get("question_parts", {}),
        "quellenausschnitt": record.get("source_snippet", ""),
        "auftrag": task,
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
                        "why_interesting": {"type": "string"},
                        "key_points": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "additionalProperties": False,
                                "properties": {
                                    "kind": {"type": "string"},
                                    "text": {"type": "string"},
                                    "simple": {"type": "string"},
                                    "status": {"type": "string"},
                                },
                                "required": ["kind", "text", "simple", "status"],
                            },
                        },
                        "open_points": {"type": "array", "items": {"type": "string"}},
                        "source_limits": {"type": "array", "items": {"type": "string"}},
                    },
                    "required": ["summary", "easy_language", "why_interesting", "key_points", "open_points", "source_limits"],
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
    if len(summary) > 2400 or len(easy_language) > 1800:
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
