from graz_protocols.viewer import build_html, viewer_record


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
    assert "angenommen (mehrheitlich)" in html
    assert "Angenommen" in html
    assert "Entscheidungsregister" in html
    assert "Ergebnisse bevorzugt aus DIGRA" in html
    assert 'data-nav="overview"' in html
    assert 'data-nav="export"' in html
    assert "table-card" in html
    assert "--accent: #2563eb" in html
    assert "#ff5900" not in html
    assert "Lokale Doppelklick-Ansicht. Protokolldateien bleiben außerhalb von Git." not in html
    assert "Eintrag auswählen, um Details zu sehen." in html
    assert "Alle Quellen" in html
    assert "Alle Beträge" in html
    assert "Alle Dateien" in html
    assert "CSV Export" in html
    assert "graz-gemeinderat-treffer.csv" in html
    assert "topicsWrap" in html
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


def test_viewer_normalizes_file_labels_and_status_filter():
    record = viewer_record(
        {
            "meeting_date": "2024-11-14",
            "record_id": "r1",
            "record_type": "agenda_item",
            "source_file": "2024-11-14_Protokoll_O-Teil.docx",
            "status": "accepted_unanimous",
        }
    )

    assert record["quell_datei"] == "Protokoll 2024-11-14.docx"
    assert record["status"] == "angenommen (einstimmig)"
    assert record["status_filter"] == "Angenommen"


def test_viewer_can_embed_topic_candidates():
    html = build_html(
        [],
        {},
        [
            {
                "confidence": 0.95,
                "business_number": "A 14-001665/2025",
                "dates": ["2025-01-16", "2025-03-20"],
                "label": "Flächenwidmungsplan Landeshauptstadt",
                "reason": "gleiche Geschäftszahl-Basis",
                "records": [
                    {"meeting_date": "2025-01-16", "title": "Auflage des Entwurfs"},
                    {"meeting_date": "2025-03-20", "title": "Beschluss"},
                ],
                "topic_id": "business-a-14-001665-2025",
            }
        ],
    )

    assert "Themenverläufe" in html
    assert "timeline-step" in html
    assert "Zeitstrahl:" in html
    assert "Einträge dazu filtern" in html
    assert "Flächenwidmungsplan Landeshauptstadt" in html
    assert "Geschäftszahl:" in html
    assert "A 14-001665/2025" in html
    assert "gleiche Geschäftszahl-Basis" in html
    assert "Auflage des Entwurfs" in html
