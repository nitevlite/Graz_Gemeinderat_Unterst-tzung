from graz_protocols.viewer import build_html, canonical_digra_url, meaningful_ai_reason, viewer_record


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
                "digra_url": "https://digra.graz.at/document?ref=b7b33fe0-443a-49c8-9e95-22a77851b9f9",
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
    assert "Lokale HTML-Ansicht" not in html
    assert "Ergebnisse bevorzugt aus DIGRA" not in html
    assert "Parser-Fallback nur bei fehlenden DIGRA-Daten" not in html
    assert 'data-nav="search"' in html
    assert 'data-nav="overview"' in html
    assert 'data-nav="map"' in html
    assert 'data-nav="export"' in html
    assert "Zeitstrahlen" in html
    assert '<span class="side-dot">' not in html
    assert 'id="searchPanel"' in html
    assert 'id="overviewPanel"' in html
    assert 'id="mapPanel"' in html
    assert 'id="exportPanel"' in html
    assert "table-card" in html
    assert "overflow-wrap: anywhere" in html
    assert "--accent: #2563eb" in html
    assert "#ff5900" not in html
    assert "Lokale Doppelklick-Ansicht. Protokolldateien bleiben außerhalb von Git." not in html
    assert "Eintrag auswählen, um Details zu sehen." in html
    assert "Alle Quellen" in html
    assert "Alle Jahre" in html
    assert "Alle Beträge" in html
    assert "Alle Dateien" in html
    assert "CSV Export" in html
    assert "graz-gemeinderat-treffer.csv" in html
    assert "topicsWrap" in html
    assert "Graz-Karte" in html
    assert "grazMap" in html
    assert "min-height: 720px" in html
    assert "nominatim.openstreetmap.org" in html
    assert "openstreetmap.org" in html
    assert "currentLocationIndex = buildLocationIndex(sichtbareEintraege)" in html
    assert "refreshMapMarkersIfNeeded()" in html
    assert "activeTopicRecordIds" in html
    assert "data-topic-id" in html
    assert "focusRecordLocations(record" in html
    assert "L.polyline(points" in html
    assert "record-route" in html
    assert "visibleTopics = topics.map" in html
    assert "filter(topicRecordMatchesFilters)" in html
    assert "renderTopics();" in html
    assert "DIGRA-Trefferwert" in html
    assert "digraLink(record.digra_url" in html
    assert "https://digra.graz.at/document?ref=b7b33fe0-443a-49c8-9e95-22a77851b9f9" in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
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


def test_viewer_canonicalizes_digra_urls():
    assert (
        canonical_digra_url(
            "https://digra.graz.at/document?ref=d811022e-2e21-408c-8e23-9622acfc1432&jfwid=abc"
        )
        == "https://digra.graz.at/document?ref=d811022e-2e21-408c-8e23-9622acfc1432"
    )
    assert canonical_digra_url("https://example.com/document?ref=x") == ""


def test_viewer_hides_generic_ai_reasons():
    assert meaningful_ai_reason("Kurze Bezeichnung des Themas") == ""
    assert meaningful_ai_reason("kompakt und beinhaltet den wesentlichen Inhalt.") == ""
    assert meaningful_ai_reason("Mehrere Beschlüsse betreffen denselben Bebauungsplan.") != ""


def test_viewer_renders_locations_as_map_buttons():
    html = build_html(
        [
            {
                "agenda_item_no": 1,
                "amounts": [],
                "business_numbers": [],
                "locations": ["Schönaugasse"],
                "meeting_date": "2026-04-23",
                "record_id": "test-record",
                "record_type": "agenda_item",
                "result_text": "Antrag: angenommen",
                "section": "Tagesordnung",
                "source_url": "https://www.graz.at/cms/beitrag/test",
                "source_file": "test.docx",
                "status": "accepted",
                "title": "Test",
            }
        ],
        {},
    )

    assert 'data-location="${escapeHtml(location)}"' in html
    assert "focusLocation(locationButton.dataset.location" in html
    assert "Quelle öffnen" in html
    assert "Schönaugasse" in html


def test_viewer_can_embed_topic_candidates():
    html = build_html(
        [],
        {},
        [
            {
                "confidence": 0.95,
                "ai_reason": "Gemeinsames Projekt über mehrere Sitzungen",
                "business_number": "A 14-001665/2025",
                "dates": ["2025-01-16", "2025-03-20"],
                "label": "Flächenwidmungsplan Landeshauptstadt",
                "reason": "gleiche Geschäftszahl-Basis",
                "records": [
                    {
                        "meeting_date": "2025-01-16",
                        "record_id": "record-a",
                        "result_text": "Antrag: angenommen",
                        "status": "accepted",
                        "title": "Auflage des Entwurfs",
                    },
                    {
                        "meeting_date": "2025-03-20",
                        "record_id": "record-b",
                        "result_text": "Antrag: mehrheitlich angenommen",
                        "status": "accepted_majority",
                        "title": "Beschluss",
                    },
                ],
                "news": [{"title": "Gemeinderat beschließt Flächenwidmungsplan", "url": "https://www.graz.at/news"}],
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
    assert "gleiche Geschäftszahl-Basis" not in html
    assert "KI-Hinweis:" in html
    assert "Gemeinsames Projekt über mehrere Sitzungen" in html
    assert "Letzter Stand:" in html
    assert "Antrag: mehrheitlich angenommen" in html
    assert "data-topic-id" in html
    assert "record-b" in html
    assert "Auflage des Entwurfs" in html
    assert "Aktuelle Hinweise" in html
    assert "Gemeinderat beschließt Flächenwidmungsplan" in html
