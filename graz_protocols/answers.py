from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from .search_index import SearchResult, search_sqlite


@dataclass(frozen=True)
class AnswerGroup:
    key: str
    title: str
    explanation: str
    results: list[tuple[int, SearchResult]]


GROUP_ORDER = [
    "council_decided",
    "committee",
    "treated",
    "open",
    "rejected",
]

GROUP_LABELS = {
    "council_decided": (
        "Gemeinderat beschlossen oder angenommen",
        "Diese Treffer wirken nach den lokalen Daten wie positive Gemeinderatsentscheidungen.",
    ),
    "committee": (
        "Vorberatung im Ausschuss",
        "Diese Treffer sind als Ausschussstand oder Vorberatung zu lesen, nicht automatisch als Gemeinderatsbeschluss.",
    ),
    "treated": (
        "Behandelt oder mitgeteilt",
        "Diese Treffer zeigen Behandlung, Mitteilung oder Quellenlage, aber keinen eigenständigen Beschluss.",
    ),
    "open": (
        "Antrag, Anfrage oder offenes Verfahren",
        "Diese Treffer sind relevant, aber in den lokalen Daten nicht als beschlossen oder umgesetzt belegt.",
    ),
    "rejected": (
        "Abgelehnt",
        "Diese Treffer sind in den lokalen Daten negativ entschieden.",
    ),
}


def answer_sqlite(path: Path, query: str, *, limit: int = 30, per_group: int = 5) -> str:
    results = search_sqlite(path, query, limit=limit)
    if not results:
        return "Keine belastbaren Treffer gefunden. Ohne Quellen wird keine inhaltliche Antwort erzeugt."

    indexed_results = list(enumerate(results, start=1))
    groups = grouped_results(indexed_results, per_group=per_group)
    lines: list[str] = ["Kurzantwort", short_answer(groups), ""]

    for group in groups:
        if not group.results:
            continue
        lines.extend([group.title, group.explanation])
        for index, result in group.results:
            lines.append(source_line(index, result))
        lines.append("")

    lines.extend(["Quellenhinweis", "Die Antwort verwendet nur den lokalen SQLite/FTS-Index. Sie ruft kein KI-Modell und keine externe API auf."])
    return "\n".join(lines).strip()


def grouped_results(indexed_results: list[tuple[int, SearchResult]], *, per_group: int) -> list[AnswerGroup]:
    buckets: dict[str, list[tuple[int, SearchResult]]] = {key: [] for key in GROUP_ORDER}
    for item in indexed_results:
        buckets[group_key(item[1])].append(item)
    return [
        AnswerGroup(key, GROUP_LABELS[key][0], GROUP_LABELS[key][1], buckets[key][:per_group])
        for key in GROUP_ORDER
    ]


def short_answer(groups: list[AnswerGroup]) -> str:
    decided = count_group(groups, "council_decided")
    committee = count_group(groups, "committee")
    open_count = count_group(groups, "open")
    rejected = count_group(groups, "rejected")
    treated = count_group(groups, "treated")

    parts: list[str] = []
    if decided:
        parts.append(f"Es gibt {decided} Treffer mit positivem Gemeinderatsstand.")
    else:
        parts.append("Ich finde keinen klar positiven Gemeinderatsbeschluss in den priorisierten Treffern.")
    if committee:
        parts.append(f"{committee} Treffer sind Ausschussstand oder Vorberatung und deshalb nicht als Gemeinderatsbeschluss zu lesen.")
    if open_count:
        parts.append(f"{open_count} Treffer sind Anträge, Anfragen oder offene Verfahren.")
    if treated:
        parts.append(f"{treated} Treffer sind behandelt oder mitgeteilt.")
    if rejected:
        parts.append(f"{rejected} Treffer sind abgelehnt.")
    return " ".join(parts)


def count_group(groups: list[AnswerGroup], key: str) -> int:
    return next((len(group.results) for group in groups if group.key == key), 0)


def group_key(result: SearchResult) -> str:
    text = normalized_result_text(result)
    if "ausschuss" in text:
        return "committee"
    if "abgelehnt" in text or "rejected" in text:
        return "rejected"
    if any(term in text for term in ("accepted", "angenommen", "beschlossen")):
        return "council_decided"
    if any(term in text for term in ("zugewiesen", "assigned", "offen", "unbekannt", "frage", "anfrage")):
        return "open"
    if any(term in text for term in ("mitteilung", "mitgeteilt", "kenntnis", "noted", "quelle verfuegbar", "quelle verfügbar")):
        return "treated"
    return "open"


def normalized_result_text(result: SearchResult) -> str:
    return (
        " ".join([result.status, result.result_text, result.record_type])
        .casefold()
        .replace("ß", "ss")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
    )


def source_line(index: int, result: SearchResult) -> str:
    source = result.digra_url or result.source_url or "-"
    result_text = compact(result.result_text or result.status or "-")
    title = compact(result.title, max_length=150)
    snippet = compact(result.snippets[0], max_length=180) if result.snippets else ""
    line = f"[{index}] {result.date or '-'} | {result.record_type or '-'} | {title} | Ergebnis: {result_text} | Quelle: {source}"
    if snippet:
        line += f" | Kontext: {snippet}"
    return line


def compact(value: str, *, max_length: int = 120) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_length:
        return text
    return text[:max_length].rsplit(" ", 1)[0].strip(" ,;:") + "."
