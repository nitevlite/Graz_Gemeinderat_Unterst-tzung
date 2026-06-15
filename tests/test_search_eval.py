import json
from pathlib import Path
from argparse import Namespace

from graz_protocols.cli import run_eval_search
from graz_protocols.parser import AgendaRecord
from graz_protocols.search_eval import evaluate_search_goldstandard, read_goldstandard
from graz_protocols.sqlite_export import write_sqlite


def test_search_goldstandard_fixture_is_valid():
    cases = read_goldstandard(Path("tests/fixtures/search_goldstandard.json"))

    assert len(cases) == 10
    assert all(case["id"] for case in cases)
    assert all(case["question"] for case in cases)
    assert all(case["expected_record_ids"] for case in cases)


def test_evaluate_search_goldstandard_against_synthetic_index(tmp_path):
    db_path = tmp_path / "eintraege.sqlite"
    output_path = tmp_path / "goldstandard.json"
    goldset = json.loads(Path("tests/fixtures/search_goldstandard.json").read_text(encoding="utf-8"))
    output_path.write_text(json.dumps(goldset, ensure_ascii=False), encoding="utf-8")
    write_sqlite(db_path, synthetic_gold_records(), {"records_total": 8})

    summary = evaluate_search_goldstandard(db_path, output_path, limit=10)

    assert summary["cases_total"] == 10
    assert summary["hits_at_k"] == 10
    assert summary["recall_at_k"] == 1.0
    assert summary["mean_reciprocal_rank"] > 0
    assert all(case["hit"] for case in summary["case_results"])


def test_run_eval_search_writes_optional_report(tmp_path, capsys):
    db_path = tmp_path / "eintraege.sqlite"
    goldset_path = tmp_path / "goldstandard.json"
    report_path = tmp_path / "report.json"
    goldset = json.loads(Path("tests/fixtures/search_goldstandard.json").read_text(encoding="utf-8"))
    goldset_path.write_text(json.dumps(goldset, ensure_ascii=False), encoding="utf-8")
    write_sqlite(db_path, synthetic_gold_records(), {"records_total": 8})

    exit_code = run_eval_search(Namespace(sqlite=db_path, goldset=goldset_path, limit=10, output=report_path))
    output = capsys.readouterr().out
    report = json.loads(report_path.read_text(encoding="utf-8"))

    assert exit_code == 0
    assert "Such-Eval: 10/10 Treffer @ 10" in output
    assert report["hits_at_k"] == 10


def synthetic_gold_records() -> list[AgendaRecord]:
    return [
        AgendaRecord(
            record_id="gold-haltestelle-waltendorf",
            record_type="written_motion",
            source_file="synthetic",
            meeting_date="2026-05-21",
            section="Anträge",
            agenda_item_no=1,
            business_numbers=["A10/BD-123/2026"],
            title="Verkehrsantrag: Barrierefreie Haltestelle in Waltendorf",
            status="assigned",
            status_text="zugewiesen",
            result_text="Verfahren: zugewiesen",
            raw_result_text="zugewiesen",
            votes=[],
            amounts=[],
            locations=["Waltendorf"],
            source_snippet="Die KPÖ bringt einen Verkehrsantrag zur barrierefreien Haltestelle in Waltendorf ein.",
            parser_confidence=0.9,
            submitter="GR Beispiel, KPÖ",
        ),
        AgendaRecord(
            record_id="gold-parken-gruene-zone",
            record_type="written_motion",
            source_file="synthetic",
            meeting_date="2026-04-23",
            section="Anträge",
            agenda_item_no=2,
            business_numbers=["A10/456/2026"],
            title="Offener Antrag zum Parken in der Grünen Zone",
            status="assigned",
            status_text="zugewiesen",
            result_text="Verfahren: zugewiesen",
            raw_result_text="zugewiesen",
            votes=[],
            amounts=[],
            locations=["Waltendorf"],
            source_snippet="Es geht um Anrainerparken, Parkplätze und die Grüne Zone.",
            parser_confidence=0.9,
        ),
        AgendaRecord(
            record_id="gold-fragestunde-sozialamt",
            record_type="question_hour",
            source_file="synthetic",
            meeting_date="2026-03-19",
            section="Fragestunde",
            agenda_item_no=3,
            business_numbers=["2713/1"],
            title="Fragestunde zum Sozialamt",
            status="unknown",
            status_text="unbekannt",
            result_text="Unbekannt",
            raw_result_text="",
            votes=[],
            amounts=[],
            locations=[],
            source_snippet="In der Fragestunde wird zum Sozialamt gefragt. Keine Antwort ist in den lokalen Daten erfasst.",
            parser_confidence=0.8,
            question_parts={"question": "Frage zum Sozialamt", "answer": ""},
        ),
        AgendaRecord(
            record_id="gold-budget-kultur",
            record_type="agenda_item",
            source_file="synthetic",
            meeting_date="2026-02-12",
            section="Tagesordnung",
            agenda_item_no=4,
            business_numbers=["A16-789/2026"],
            title="Budgetbeschluss für Kulturarbeit",
            status="accepted_unanimous",
            status_text="einstimmig angenommen",
            result_text="Antrag: einstimmig angenommen",
            raw_result_text="angenommen",
            votes=[],
            amounts=["€ 5.000,-"],
            locations=[],
            source_snippet="Der Beschluss enthält einen Betrag für Kulturarbeit.",
            parser_confidence=1.0,
        ),
        AgendaRecord(
            record_id="gold-stadion-abgelehnt",
            record_type="urgent_motion",
            source_file="synthetic",
            meeting_date="2026-01-22",
            section="Dringlichkeitsanträge",
            agenda_item_no=5,
            business_numbers=["A8-321/2026"],
            title="Stadion Liebenau Antrag",
            status="rejected_majority",
            status_text="mehrheitlich abgelehnt",
            result_text="Antrag: mehrheitlich abgelehnt",
            raw_result_text="abgelehnt",
            votes=[],
            amounts=[],
            locations=["Liebenau"],
            source_snippet="Der Stadion-Antrag wurde abgelehnt.",
            parser_confidence=1.0,
        ),
        AgendaRecord(
            record_id="gold-leistungsbericht",
            record_type="communication",
            source_file="synthetic",
            meeting_date="2026-05-21",
            section="Mitteilungen",
            agenda_item_no=6,
            business_numbers=["3399/1"],
            title="Leistungsbericht Haus Graz",
            status="noted",
            status_text="zur Kenntnis genommen",
            result_text="zur Kenntnis genommen",
            raw_result_text="zur Kenntnis genommen",
            votes=[],
            amounts=[],
            locations=[],
            source_snippet="Mitteilung zum Leistungsbericht Haus Graz.",
            parser_confidence=0.9,
        ),
        AgendaRecord(
            record_id="gold-hauptplatz-service",
            record_type="agenda_item",
            source_file="synthetic",
            meeting_date="2026-06-18",
            section="Tagesordnung",
            agenda_item_no=7,
            business_numbers=["A10-654/2026"],
            title="Servicepunkt am Hauptplatz",
            status="accepted_majority",
            status_text="mehrheitlich angenommen",
            result_text="Antrag: mehrheitlich angenommen",
            raw_result_text="angenommen",
            votes=[],
            amounts=[],
            locations=["Hauptplatz"],
            source_snippet="Der Eintrag betrifft den Hauptplatz.",
            parser_confidence=0.9,
        ),
        AgendaRecord(
            record_id="gold-noise",
            record_type="agenda_item",
            source_file="synthetic",
            meeting_date="2026-06-18",
            section="Tagesordnung",
            agenda_item_no=8,
            business_numbers=["A1-000/2026"],
            title="Allgemeiner Vergleichseintrag",
            status="accepted_majority",
            status_text="mehrheitlich angenommen",
            result_text="Antrag: mehrheitlich angenommen",
            raw_result_text="angenommen",
            votes=[],
            amounts=[],
            locations=[],
            source_snippet="Dieser Eintrag dient nur als irrelevanter Vergleich.",
            parser_confidence=0.9,
        ),
    ]
