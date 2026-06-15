import pytest

from graz_protocols.parser import ParserParagraph, parse_protocol


def paragraph(text: str, style: str = "Normal", index: int = 0) -> ParserParagraph:
    return ParserParagraph(text, style, index)


GOLDSET_CASES = [
    {
        "name": "agenda_unanimous_amount_title",
        "section": "Tagesordnung",
        "heading": "Stk. 1) A8-123456/2024-1 Sanierung Beispielgasse über € 10.000,-",
        "body": ["Der Antrag wurde einstimmig angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Sanierung Beispielgasse über € 10.000,-",
            "business_numbers": ["A8-123456/2024-1"],
            "amounts": ["€ 10.000,-"],
            "status": "accepted_unanimous",
        },
    },
    {
        "name": "agenda_majority_against_parties",
        "section": "Tagesordnung",
        "heading": "Stk. 2) A10-234567/2025-2 Verkehrsmaßnahme Musterstraße",
        "body": ["Der Antrag wurde mehrstimmig angenommen (Gegen NEOS, FPÖ)."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Verkehrsmaßnahme Musterstraße",
            "business_numbers": ["A10-234567/2025-2"],
            "amounts": [],
            "status": "accepted_majority",
        },
    },
    {
        "name": "agenda_rejected_majority",
        "section": "Tagesordnung",
        "heading": "Stk. 3) AB-345678/2025/1 Bericht Beispielprojekt",
        "body": ["Der Antrag wurde mehrheitlich abgelehnt.", "Zustimmung: KFG"],
        "expected": {
            "section": "Tagesordnung",
            "title": "Bericht Beispielprojekt",
            "business_numbers": ["AB-345678/2025/1"],
            "amounts": [],
            "status": "rejected_majority",
        },
    },
    {
        "name": "agenda_business_number_with_spaces",
        "section": "Tagesordnung",
        "heading": "Stk. 4) A 14-456789/2025 Flächenwidmung Mustergebiet",
        "body": ["Der Antrag wurde einstimmig angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Flächenwidmung Mustergebiet",
            "business_numbers": ["A 14-456789/2025"],
            "amounts": [],
            "status": "accepted_unanimous",
        },
    },
    {
        "name": "agenda_to_heading",
        "section": "Tagesordnung",
        "heading": "TO 5: A5-567890/2024/3 Förderbericht Musterschule",
        "body": ["Der Antrag wurde mehrheitlich angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Förderbericht Musterschule",
            "business_numbers": ["A5-567890/2024/3"],
            "amounts": [],
            "status": "accepted_majority",
        },
    },
    {
        "name": "agenda_formal_motion_amount",
        "section": "Tagesordnung",
        "heading": "Stk. 6) A8-678901/2025 Budgetanpassung Musteramt",
        "body": [
            "In der Debatte werden € 999.999,- erwähnt.",
            "Es wird folgender Antrag gestellt:",
            "Für die Umsetzung werden € 22.000,- genehmigt.",
            "Der Antrag wurde einstimmig angenommen.",
        ],
        "expected": {
            "section": "Tagesordnung",
            "title": "Budgetanpassung Musteramt",
            "business_numbers": ["A8-678901/2025"],
            "amounts": ["€ 22.000,-"],
            "status": "accepted_unanimous",
        },
    },
    {
        "name": "agenda_general_accepted",
        "section": "Tagesordnung",
        "heading": "Stk. 7) Präs. 789012/2025 Geschäftsordnung Beispiel",
        "body": ["Der Antrag wurde angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Geschäftsordnung Beispiel",
            "business_numbers": ["Präs. 789012/2025"],
            "amounts": [],
            "status": "accepted",
        },
    },
    {
        "name": "agenda_noted",
        "section": "Tagesordnung",
        "heading": "Stk. 8) A7-890123/2025 Informationsbericht Beispiel",
        "body": ["Bericht wurde zur Kenntnis genommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Informationsbericht Beispiel",
            "business_numbers": ["A7-890123/2025"],
            "amounts": [],
            "status": "noted",
        },
    },
    {
        "name": "urgent_motion_assigned",
        "section": "Dringlichkeitsanträge",
        "heading": "A2-901234/2025 Sicherer Musterplatz",
        "body": ["Der geschäftsordnungsmäßigen Behandlung zugewiesen."],
        "expected": {
            "section": "Dringlichkeitsanträge",
            "title": "Sicherer Musterplatz",
            "business_numbers": ["A2-901234/2025"],
            "amounts": [],
            "status": "assigned",
        },
    },
    {
        "name": "urgent_motion_accepted",
        "section": "Dringlichkeitsanträge",
        "heading": "A3-912345/2025 Sofortmaßnahme Musterbrücke",
        "body": ["Der Antrag wurde mehrheitlich angenommen.", "Dagegen: ÖVP"],
        "expected": {
            "section": "Dringlichkeitsanträge",
            "title": "Sofortmaßnahme Musterbrücke",
            "business_numbers": ["A3-912345/2025"],
            "amounts": [],
            "status": "accepted_majority",
        },
    },
    {
        "name": "urgent_motion_rejected",
        "section": "Dringlichkeitsanträge",
        "heading": "A4-923456/2025 Testantrag Energie",
        "body": ["Der Antrag wurde mehrstimmig abgelehnt."],
        "expected": {
            "section": "Dringlichkeitsanträge",
            "title": "Testantrag Energie",
            "business_numbers": ["A4-923456/2025"],
            "amounts": [],
            "status": "rejected_majority",
        },
    },
    {
        "name": "written_question_assigned",
        "section": "Anfragen (schriftlich)",
        "heading": "A1-934567/2025 Anfrage Musterstraße",
        "body": ["Originaltext der Anfrage:", "Der geschäftsordnungsmäßigen Behandlung zugewiesen."],
        "expected": {
            "section": "Anfragen (schriftlich)",
            "title": "Anfrage Musterstraße",
            "business_numbers": ["A1-934567/2025"],
            "amounts": [],
            "status": "assigned",
        },
    },
    {
        "name": "written_question_without_business_number",
        "section": "Anfragen (schriftlich)",
        "heading": "Auskunft zu Musterpark",
        "body": ["Der geschäftsordnungsmäßigen Behandlung zugewiesen."],
        "expected": {
            "section": "Anfragen (schriftlich)",
            "title": "Auskunft zu Musterpark",
            "business_numbers": [],
            "amounts": [],
            "status": "assigned",
        },
    },
    {
        "name": "written_motion_assigned",
        "section": "Anträge (schriftlich)",
        "heading": "A6-945678/2025 Antrag sichere Querung",
        "body": ["Der geschäftsordnungsmäßigen Behandlung zugewiesen."],
        "expected": {
            "section": "Anträge (schriftlich)",
            "title": "Antrag sichere Querung",
            "business_numbers": ["A6-945678/2025"],
            "amounts": [],
            "status": "assigned",
        },
    },
    {
        "name": "written_motion_amount_in_title",
        "section": "Anträge (schriftlich)",
        "heading": "A6-956789/2025 Förderung Beispielverein € 5.000,-",
        "body": ["Der geschäftsordnungsmäßigen Behandlung zugewiesen."],
        "expected": {
            "section": "Anträge (schriftlich)",
            "title": "Förderung Beispielverein € 5.000,-",
            "business_numbers": ["A6-956789/2025"],
            "amounts": ["€ 5.000,-"],
            "status": "assigned",
        },
    },
    {
        "name": "agenda_additional_motion_vote",
        "section": "Tagesordnung",
        "heading": "Stk. 16) A9-967890/2025 Beschluss Musterbezirk",
        "body": ["Der Zusatzantrag wurde mehrheitlich abgelehnt.", "Der Antrag wurde einstimmig angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Beschluss Musterbezirk",
            "business_numbers": ["A9-967890/2025"],
            "amounts": [],
            "status": "accepted_unanimous",
        },
    },
    {
        "name": "agenda_parcel_location_not_required",
        "section": "Tagesordnung",
        "heading": "Stk. 17) A10-978901/2025 Grundstück Gdst. Nr. 123/4",
        "body": ["Der Antrag wurde einstimmig angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Grundstück Gdst. Nr. 123/4",
            "business_numbers": ["A10-978901/2025"],
            "amounts": [],
            "status": "accepted_unanimous",
        },
    },
    {
        "name": "agenda_amount_ignores_debate",
        "section": "Tagesordnung",
        "heading": "Stk. 18) A8-989012/2025 Sachprogramm ohne Budget",
        "body": ["In der Rede fällt € 77.000,-.", "Der Antrag wurde einstimmig angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Sachprogramm ohne Budget",
            "business_numbers": ["A8-989012/2025"],
            "amounts": [],
            "status": "accepted_unanimous",
        },
    },
    {
        "name": "agenda_multiple_amounts_title",
        "section": "Tagesordnung",
        "heading": "Stk. 19) A8-990123/2025 Doppelbudget € 1.000,- und € 2.000,-",
        "body": ["Der Antrag wurde mehrheitlich angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Doppelbudget € 1.000,- und € 2.000,-",
            "business_numbers": ["A8-990123/2025"],
            "amounts": ["€ 1.000,-", "€ 2.000,-"],
            "status": "accepted_majority",
        },
    },
    {
        "name": "agenda_toc_entry_ignored",
        "section": "Tagesordnung",
        "heading": "Stk. 20) A8-991234/2025 Nur echter Eintrag zählt",
        "prefix": [paragraph("6.1\tStk. 20) A8-991234/2025 Nur echter Eintrag zählt\t44", "TOC2", 1)],
        "body": ["Der Antrag wurde einstimmig angenommen."],
        "expected": {
            "section": "Tagesordnung",
            "title": "Nur echter Eintrag zählt",
            "business_numbers": ["A8-991234/2025"],
            "amounts": [],
            "status": "accepted_unanimous",
        },
    },
]


@pytest.mark.parametrize("case", GOLDSET_CASES, ids=[case["name"] for case in GOLDSET_CASES])
def test_parser_matches_sanitized_goldset(case: dict) -> None:
    paragraphs = [
        paragraph("Protokoll über die öffentliche Sitzung des Gemeinderates am 23.04.2026", "Normal", 0),
        *case.get("prefix", []),
        paragraph(case["section"], "Heading1", 2),
        paragraph(case["heading"], "Heading2", 3),
        *[paragraph(line, "Normal", index + 4) for index, line in enumerate(case["body"])],
    ]

    records = parse_protocol(paragraphs, "2026-04-23_Protokoll.docx")

    assert len(records) == 1
    expected = case["expected"]
    record = records[0]
    assert record.section == expected["section"]
    assert record.title == expected["title"]
    assert record.business_numbers == expected["business_numbers"]
    assert record.amounts == expected["amounts"]
    assert record.status == expected["status"]
