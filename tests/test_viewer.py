from graz_protocols.viewer import build_html


def test_viewer_uses_german_labels_and_hides_raw_text():
    html = build_html(
        [
            {
                "agenda_item_no": 1,
                "amounts": [],
                "business_numbers": [],
                "locations": [],
                "meeting_date": "2026-04-23",
                "parser_confidence": 1.0,
                "record_id": "test-record",
                "record_type": "agenda_item",
                "result_text": "Antrag: mehrheitlich angenommen",
                "raw_result_text": "Der Antrag wurde mehrstimmig angenommen.",
                "section": "Tagesordnung",
                "source_file": "test.docx",
                "source_snippet": "Der Antrag wurde mehrstimmig angenommen.",
                "status": "accepted_majority",
                "status_text": "mehrstimmig angenommen",
                "title": "Teststück",
                "votes": [
                    {
                        "abstention": [],
                        "against": [],
                        "approval": [],
                        "outcome": "accepted_majority",
                        "raw_text": "Der Antrag wurde mehrstimmig angenommen.",
                        "subject": "motion",
                    }
                ],
            }
        ],
        {"records_by_status": {"unknown": 0}},
    )

    assert "Tagesordnungspunkt" in html
    assert "mehrheitlich angenommen" in html
    assert "Eintrag auswählen, um Details zu sehen." in html
    assert "Alle Quellen" in html
    assert "DIGRA-Trefferwert" in html
    assert "Quelldatei" in html
    assert "Geschäftszahlen" in html
    assert "agenda_item" not in html
    assert "agenda_item_no" not in html
    assert "accepted_majority" not in html
    assert "record_type" not in html
    assert "status_text" not in html
    assert "Der Antrag wurde" not in html
    assert "raw_result_text" not in html
    assert "source_snippet" not in html
    assert "raw_text" not in html
