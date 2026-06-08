from graz_protocols.audit import build_audit_report


def test_audit_report_summarizes_sources_and_missing_records():
    report = build_audit_report(
        [
            {
                "agenda_item_no": 1,
                "digra_business_number": "100/1",
                "digra_match_score": 1.0,
                "digra_url": "https://digra.graz.at/document?ref=1",
                "meeting_date": "2026-01-22",
                "record_type": "agenda_item",
                "result_source": "digra",
                "status": "accepted_unanimous",
                "title": "DIGRA-Beispiel",
            },
            {
                "agenda_item_no": 2,
                "digra_business_number": "",
                "digra_match_score": 0,
                "digra_url": "",
                "meeting_date": "2026-01-22",
                "record_type": "agenda_item",
                "result_source": "digra_fehlt",
                "status": "unknown",
                "title": "Fehlendes Beispiel",
            },
        ],
        {"digra_match_strategy": "test"},
    )

    assert "DIGRA-Ergebnisse: 1" in report
    assert "Ohne Ergebnis: 1" in report
    assert "Fehlendes Beispiel" in report
    assert "digra_fehlt" not in report
