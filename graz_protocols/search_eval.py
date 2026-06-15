from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import json

from .search_index import search_sqlite


@dataclass(frozen=True)
class GoldCaseResult:
    case_id: str
    question: str
    expected_record_ids: list[str]
    found_record_ids: list[str]
    hit: bool
    first_hit_rank: int
    reciprocal_rank: float
    precision_at_k: float
    recall_at_k: float
    tags: list[str]


def evaluate_search_goldstandard(sqlite_path: Path, goldset_path: Path, *, limit: int = 10) -> dict:
    cases = read_goldstandard(goldset_path)
    results = [evaluate_case(sqlite_path, case, limit=limit) for case in cases]
    total = len(results)
    hits = sum(1 for result in results if result.hit)
    return {
        "goldset": str(goldset_path),
        "sqlite": str(sqlite_path),
        "limit": limit,
        "cases_total": total,
        "hits_at_k": hits,
        "recall_at_k": round(hits / total, 4) if total else 0.0,
        "mean_reciprocal_rank": round(sum(result.reciprocal_rank for result in results) / total, 4) if total else 0.0,
        "mean_precision_at_k": round(sum(result.precision_at_k for result in results) / total, 4) if total else 0.0,
        "case_results": [asdict(result) for result in results],
    }


def read_goldstandard(path: Path) -> list[dict]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = payload.get("cases", [])
    if not isinstance(cases, list):
        raise RuntimeError("Goldstandard enthält keine cases-Liste.")
    normalized = [normalize_case(case) for case in cases]
    duplicate_ids = duplicate_values(case["id"] for case in normalized)
    if duplicate_ids:
        raise RuntimeError(f"Doppelte Goldstandard-IDs: {', '.join(duplicate_ids)}")
    return normalized


def normalize_case(case: object) -> dict:
    if not isinstance(case, dict):
        raise RuntimeError("Goldstandard-Fall muss ein Objekt sein.")
    case_id = str(case.get("id", "")).strip()
    question = str(case.get("question", "")).strip()
    expected = case.get("expected_record_ids", [])
    tags = case.get("tags", [])
    if not case_id:
        raise RuntimeError("Goldstandard-Fall ohne id.")
    if not question:
        raise RuntimeError(f"Goldstandard-Fall {case_id} ohne question.")
    if not isinstance(expected, list) or not expected:
        raise RuntimeError(f"Goldstandard-Fall {case_id} ohne expected_record_ids.")
    if not all(str(value).strip() for value in expected):
        raise RuntimeError(f"Goldstandard-Fall {case_id} enthält leere expected_record_ids.")
    return {
        "id": case_id,
        "question": question,
        "expected_record_ids": [str(value).strip() for value in expected],
        "tags": [str(value).strip() for value in tags if str(value).strip()] if isinstance(tags, list) else [],
    }


def duplicate_values(values: object) -> list[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return sorted(duplicates)


def evaluate_case(sqlite_path: Path, case: dict, *, limit: int) -> GoldCaseResult:
    expected = set(case["expected_record_ids"])
    results = search_sqlite(sqlite_path, case["question"], limit=limit)
    found = [result.record_id for result in results]
    first_hit_rank = first_matching_rank(found, expected)
    hits_found = sum(1 for record_id in found if record_id in expected)
    return GoldCaseResult(
        case_id=case["id"],
        question=case["question"],
        expected_record_ids=case["expected_record_ids"],
        found_record_ids=found,
        hit=first_hit_rank > 0,
        first_hit_rank=first_hit_rank,
        reciprocal_rank=round(1 / first_hit_rank, 4) if first_hit_rank else 0.0,
        precision_at_k=round(hits_found / limit, 4) if limit else 0.0,
        recall_at_k=round(hits_found / len(expected), 4) if expected else 0.0,
        tags=case["tags"],
    )


def first_matching_rank(found: list[str], expected: set[str]) -> int:
    for index, record_id in enumerate(found, start=1):
        if record_id in expected:
            return index
    return 0
