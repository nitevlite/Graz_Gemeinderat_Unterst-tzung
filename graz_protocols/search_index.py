from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import sqlite3


TOKEN_RE = re.compile(r"[\wÄÖÜäöüß-]+", re.UNICODE)
STOPWORDS = {
    "also",
    "alles",
    "antrag",
    "anträge",
    "antraege",
    "bitte",
    "beschluss",
    "beschlüsse",
    "beschluesse",
    "betrifft",
    "bis",
    "dass",
    "dazu",
    "das",
    "den",
    "der",
    "die",
    "eine",
    "einen",
    "einer",
    "finde",
    "frage",
    "fragen",
    "gibt",
    "haben",
    "nach",
    "oder",
    "über",
    "ueber",
    "und",
    "was",
    "welche",
    "welcher",
    "welchen",
    "wer",
    "wie",
    "wurde",
    "wurden",
    "zum",
    "zur",
}


@dataclass(frozen=True)
class SearchResult:
    record_id: str
    title: str
    date: str
    record_type: str
    status: str
    result_text: str
    result_source: str
    source_url: str
    digra_url: str
    score: float
    matched_fields: list[str]
    snippets: list[str]


def search_sqlite(path: Path, query: str, *, limit: int = 20) -> list[SearchResult]:
    fts_query = build_fts_query(query)
    if not fts_query:
        return []
    candidate_limit = max(limit * 25, 100)
    with sqlite3.connect(path) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            WITH matches AS (
              SELECT
                fts.eintrag_id,
                fts.feld,
                chunks.text,
                chunks.gewicht
              FROM search_fts AS fts
              JOIN search_chunks AS chunks ON chunks.chunk_id = fts.chunk_id
              WHERE search_fts MATCH ?
            ),
            ranked AS (
              SELECT
                eintrag_id,
                SUM(gewicht) AS score,
                GROUP_CONCAT(DISTINCT feld) AS matched_fields,
                GROUP_CONCAT(text, char(31)) AS snippets
              FROM matches
              GROUP BY eintrag_id
            )
            SELECT
              docs.eintrag_id,
              docs.titel,
              docs.datum,
              docs.typ,
              docs.status,
              docs.ergebnis,
              docs.ergebnisquelle,
              docs.source_url,
              docs.digra_url,
              ranked.score,
              ranked.matched_fields,
              ranked.snippets
            FROM ranked
            JOIN search_documents AS docs ON docs.eintrag_id = ranked.eintrag_id
            ORDER BY ranked.score DESC, docs.datum DESC, docs.titel COLLATE NOCASE ASC
            LIMIT ?
            """,
            (fts_query, candidate_limit),
        ).fetchall()
    results = [row_to_result(row) for row in rows]
    return rerank_results(results, query)[:limit]


def build_fts_query(query: str) -> str:
    tokens = query_tokens(query)
    if not tokens:
        return ""
    if len(tokens) == 1:
        return fts_token_clause(tokens[0])
    return " OR ".join(fts_token_clause(token) for token in tokens[:8])


def fts_token_clause(token: str) -> str:
    alternatives = token_alternatives(token)
    if len(alternatives) == 1:
        return f"{quote_fts_token(alternatives[0])}*"
    return "(" + " OR ".join(f"{quote_fts_token(alternative)}*" for alternative in alternatives) + ")"


def token_alternatives(token: str) -> list[str]:
    alternatives = [token]
    for suffix in ("innen", "enden", "eren", "erer", "er", "en", "em", "es", "e"):
        if token.endswith(suffix) and len(token) - len(suffix) >= 5:
            alternatives.append(token[: -len(suffix)])
            break
    return list(dict.fromkeys(alternatives))


def quote_fts_token(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def query_tokens(query: str) -> list[str]:
    normalized = normalize_query_text(query)
    seen: set[str] = set()
    tokens: list[str] = []
    for match in TOKEN_RE.finditer(normalized):
        raw_token = match.group(0).strip("-_")
        for token in expanded_query_token(raw_token):
            if len(token) < 3 or token in STOPWORDS or token in seen:
                continue
            seen.add(token)
            tokens.append(token)
    return tokens


def expanded_query_token(token: str) -> list[str]:
    if "-" not in token:
        return [token]
    parts = [part for part in token.split("-") if part]
    return [token, *parts]


def normalize_query_text(value: str) -> str:
    return (
        str(value or "")
        .casefold()
        .replace("ß", "ss")
        .replace("ä", "ae")
        .replace("ö", "oe")
        .replace("ü", "ue")
    )


def row_to_result(row: sqlite3.Row) -> SearchResult:
    return SearchResult(
        record_id=str(row["eintrag_id"]),
        title=str(row["titel"]),
        date=str(row["datum"]),
        record_type=str(row["typ"]),
        status=str(row["status"]),
        result_text=str(row["ergebnis"]),
        result_source=str(row["ergebnisquelle"]),
        source_url=str(row["source_url"]),
        digra_url=str(row["digra_url"]),
        score=round(float(row["score"]), 3),
        matched_fields=split_distinct(str(row["matched_fields"] or ""), ","),
        snippets=best_snippets(str(row["snippets"] or "")),
    )


def rerank_results(results: list[SearchResult], query: str) -> list[SearchResult]:
    tokens = query_tokens(query)
    if not tokens:
        return results
    return sorted(
        (rescore_result(result, tokens, query) for result in results),
        key=lambda result: (
            -result.score,
            result.first_hit_rank if hasattr(result, "first_hit_rank") else 0,
            result.date,
            result.title.casefold(),
        ),
        reverse=False,
    )


def rescore_result(result: SearchResult, tokens: list[str], query: str) -> SearchResult:
    title_text = normalize_query_text(result.title)
    haystack = normalize_query_text(" ".join([result.title, result.result_text, *result.snippets]))
    matched_tokens = [token for token in tokens if token_matches_text(token, haystack)]
    title_matches = [token for token in tokens if token_matches_text(token, title_text)]
    coverage = len(matched_tokens) / len(tokens) if tokens else 0
    all_tokens_bonus = 40 if len(matched_tokens) == len(tokens) else 0
    title_bonus = len(title_matches) * 8
    field_bonus = field_match_bonus(result.matched_fields)
    phrase_bonus = 20 if normalize_query_text(query) in haystack else 0
    score = result.score + coverage * 50 + all_tokens_bonus + title_bonus + field_bonus + phrase_bonus
    return SearchResult(
        record_id=result.record_id,
        title=result.title,
        date=result.date,
        record_type=result.record_type,
        status=result.status,
        result_text=result.result_text,
        result_source=result.result_source,
        source_url=result.source_url,
        digra_url=result.digra_url,
        score=round(score, 3),
        matched_fields=result.matched_fields,
        snippets=result.snippets,
    )


def token_matches_text(token: str, text: str) -> bool:
    return any(alternative in text for alternative in token_alternatives(token))


def field_match_bonus(fields: list[str]) -> float:
    weights = {
        "titel": 15,
        "geschaeftszahlen": 15,
        "orte": 10,
        "einbringer": 8,
        "fragestunde": 8,
        "ergebnis": 6,
        "quellenausschnitt": 4,
    }
    return sum(weights.get(field, 0) for field in fields)


def split_distinct(value: str, separator: str) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for part in value.split(separator):
        item = part.strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def best_snippets(value: str, *, limit: int = 3) -> list[str]:
    snippets: list[str] = []
    seen: set[str] = set()
    for part in value.split(chr(31)):
        snippet = " ".join(part.split())
        if not snippet or snippet in seen:
            continue
        seen.add(snippet)
        snippets.append(trim_snippet(snippet))
        if len(snippets) >= limit:
            break
    return snippets


def trim_snippet(value: str, max_length: int = 260) -> str:
    if len(value) <= max_length:
        return value
    return value[:max_length].rsplit(" ", 1)[0].strip(" ,;:") + "."
