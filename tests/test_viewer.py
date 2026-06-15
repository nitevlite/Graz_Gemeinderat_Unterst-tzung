from graz_protocols.viewer import (
    build_html,
    build_preloaded_location_cache,
    canonical_digra_url,
    clean_display_title,
    meaningful_ai_reason,
    viewer_record,
)


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
                "submitter": "Berichterstatterin: GR Beispiel, KPÖ",
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
    assert '<meta name="robots" content="noindex, nofollow, noarchive">' in html
    assert '<meta name="googlebot" content="noindex, nofollow, noarchive">' in html
    assert "mehrheitlich angenommen" in html
    assert "angenommen (mehrheitlich)" in html
    assert "Angenommen" in html
    assert '<span class="brand-title">Graz</span>' in html
    assert "Entscheidungsregister" not in html
    assert "Lokale HTML-Ansicht" not in html
    assert "Ergebnisse bevorzugt aus DIGRA" not in html
    assert "Parser-Fallback nur bei fehlenden DIGRA-Daten" not in html
    assert 'data-nav="search"' in html
    assert 'data-nav="start"' in html
    assert 'data-nav="overview"' not in html
    assert 'data-nav="map"' in html
    assert 'data-nav="roadworks"' in html
    assert 'id="staffLoginButton"' not in html
    assert 'data-nav="parking"' in html
    assert 'data-nav="pharmacies"' in html
    assert 'data-nav="doctors"' in html
    assert 'data-nav="services"' in html
    assert 'data-nav="export"' not in html
    assert 'id="searchSection" aria-label="Filter" hidden' in html
    assert "searchSection.hidden = !['search', 'map'].includes(target)" in html
    assert ".toolbar[hidden]" in html
    assert "display: none !important" in html
    assert "Themenverläufe" not in html
    assert '<span class="side-dot">' not in html
    assert 'id="searchPanel"' in html
    assert 'id="startPanel"' in html
    assert 'id="overviewPanel"' not in html
    assert 'id="mapPanel"' in html
    assert 'id="roadworksPanel"' in html
    assert 'id="staffPanel"' not in html
    assert 'id="parkingPanel"' in html
    assert 'id="pharmaciesPanel"' in html
    assert 'id="doctorsPanel"' in html
    assert 'id="servicesPanel"' in html
    assert 'id="exportPanel"' not in html
    assert 'id="dateSummaryWrap" hidden' in html
    assert 'data-search-subtab="table"' in html
    assert 'data-search-subtab="details"' in html
    assert 'data-search-subtab="summary"' in html
    assert "Eintragsdetails" in html
    assert "Gesamtzusammenfassung" in html
    assert 'role="tab" aria-selected="true"' in html
    assert "item.setAttribute('aria-selected', String(active))" in html
    assert "border-bottom: 3px solid transparent" in html
    assert "border-bottom-color: var(--accent)" in html
    assert 'id="searchTablePanel"' in html
    assert 'id="searchDetailPanel" hidden' in html
    assert 'id="searchSummaryPanel" hidden' in html
    assert 'class="detail date-summary-detail" id="dateSummaryWrap" hidden' in html
    assert ".date-summary-detail .summary-text" in html
    assert "max-height: none" in html
    assert "activateSearchSubtab" in html
    assert "searchSubtabScroll = { table: 0, details: 0, summary: 0 }" in html
    assert "Gesamtzusammenfassung für" in html
    assert "Gesamtzusammenfassung für die aktuelle Auswahl" in html
    assert "sessionSummaryHtml" in html
    assert "sessionExampleItems" in html
    assert "summaryListHtml" in html
    assert "summary-filter-link" in html
    assert "data-summary-filter" in html
    assert "applySummaryFilter" in html
    assert "sessionSummaryFilterItems" in html
    assert "summary-list" in html
    assert "Ergebnislage" in html
    assert "Beispiele für positive Ergebnisse" in html
    assert "data-date-summary" in html
    assert "dateSummaryItems" not in html
    assert "renderDateSummary()" in html
    assert "ensureSelectedTableRowVisible" in html
    assert "activateSearchSubtab('details', false)" in html
    assert "scrollToRecordDetail()" in html
    assert "detailWrap.scrollIntoView" in html
    assert "dateSummaryWrap.addEventListener('click'" in html
    assert "behavior: 'auto'" in html
    assert "table-card" in html
    assert "selected-record" in html
    assert "highlightSelectedTableRow" in html
    assert "overflow-wrap: anywhere" in html
    assert 'td[data-label="Titel"]' in html
    assert "grid-template-columns: 92px minmax(0, 1fr)" in html
    assert "tbody tr.selected-record" in html
    assert "mobile-card-only" in html
    assert 'data-label="Einbringer"' in html
    assert 'data-label="Zusammenfassung"' in html
    assert 'data-label="Ergebnis"' in html
    assert 'data-label="Quelle"' in html
    assert "tableMobileSummaryHtml" in html
    assert "tableMobileSourceHtml" in html
    assert "--accent: #2563eb" in html
    assert "#ff5900" not in html
    assert "white-space: pre-line" in html
    assert "Lokale Doppelklick-Ansicht. Protokolldateien bleiben außerhalb von Git." not in html
    assert "Eintrag auswählen, um Details zu sehen." not in html
    assert "Alle Quellen" in html
    assert "Alle Themen" in html
    assert "fillTypeSelect" in html
    assert '<option value="Mitteilung">Mitteilung</option>' in html
    assert '<option value="Fragestunde">Fragestunde</option>' in html
    assert '<option value="Archivquelle">Archivquelle</option>' in html
    assert '<option value="Anwesenheitsliste">Anwesenheitsliste</option>' in html
    assert "const existing = new Set([...select.options]" in html
    assert "categoryFilter" in html
    assert "mapLegend" in html
    assert "data-map-category" in html
    assert "Alle Jahre" in html
    assert "Alle Beträge" in html
    assert "Alle Dateien" not in html
    assert "Alle Abschnitte" not in html
    assert "fileFilter" not in html
    assert "sectionFilter" not in html
    assert "CSV Export" not in html
    assert "graz-gemeinderat-treffer.csv" in html
    assert "graz-baustellen-feed.json" in html
    assert "graz-baustellen-feed.csv" in html
    assert "graz-baustellen.ics" in html
    assert "graz-baustellen-feed.rss" in html
    assert "graz-baustellen-abos.json" in html
    assert "graz-baustellen-feedback.json" in html
    assert "publicRoadworkFeed" in html
    assert "exportRssFeed" in html
    assert "roadworkSubscriptions" in html
    assert "matchingSubscribedRoadworks" in html
    assert "subscriptionMatchesRoadwork" in html
    assert "saveRoadworkFeedback" in html
    assert "String.fromCharCode(92)" in html
    assert "replace(/\\\\/g" not in html
    assert "Graz Gemeinderat//Baustellen" not in html
    assert "graz-gemeinderat.local" not in html
    assert "JSON Feed" not in html
    assert "Baustellen CSV" not in html
    assert "ICS Export" not in html
    assert "RSS Feed" not in html
    assert "Benachrichtigungen und Beteiligung" not in html
    assert "Abo speichern" not in html
    assert "Hinweis speichern" not in html
    assert "keine personenbezogene Veröffentlichung" in html
    assert "license_note" in html
    assert "topicsWrap" not in html
    assert "topicSearch" not in html
    assert "topicYearFilter" not in html
    assert "topicTypeFilter" not in html
    assert "topicLimitFilter" not in html
    assert "Graz-Karte" in html
    assert '<h1 id="viewTitle">Start</h1>' in html
    assert "roadworks: 'Baustellen'" in html
    assert "parking: 'Tiefgaragen'" in html
    assert "pharmacies: 'Apotheken'" in html
    assert "doctors: 'Ärzte'" in html
    assert "services: 'Services & Ämter'" in html
    assert "export: 'Export'" not in html
    assert "Baustellen/Veranstaltungen" not in html
    assert "Baustelle/Veranstaltung" not in html
    assert "Services & Ämter" in html
    assert html.index('data-nav="services"') < html.index('data-nav="roadworks"')
    assert "Baustelle planen" not in html
    assert "Baustelle prüfen" not in html
    assert "Amtsansicht" not in html
    assert "Gespeicherte Entwürfe" not in html
    assert "roadworkDraftList" not in html
    assert "Browser-lokale Entwürfe" not in html
    assert "Geplant: public, staff, admin" not in html
    assert "Entwürfe und Freigaben" not in html
    assert "Auditlog" not in html
    assert "roadworkDraftsKey" not in html
    assert "roadworkAuditKey" not in html
    assert "saveRoadworkDraft" not in html
    assert "approvedRoadworkDrafts" not in html
    assert "renderStaffWorkspace" not in html
    assert "Entwurf speichern" not in html
    assert "Freigeben" not in html
    assert "Zurückziehen" not in html
    assert "map-actions" in html
    assert "roadworkDialog" not in html
    assert "roadworkPasswordKey" not in html
    assert "unlockRoadworkDialog" not in html
    assert "openProtectedRoadworkDialog" not in html
    assert "activateTab('roadworks');" not in html
    assert "crypto.subtle" not in html
    assert "localStorage.setItem(roadworkPasswordKey" not in html
    assert '<textarea id="roadworkDescription"' not in html
    assert "roadworkImpact" not in html
    assert "roadworkLane" not in html
    assert "roadworkDetour" not in html
    assert "roadworkCaseNumber" not in html
    assert "roadworkDepartment" not in html
    assert "roadworkMode" not in html
    assert "roadworkClosure" not in html
    assert "roadworkAccess" not in html
    assert "inferRoadworkImpactAndDetour" not in html
    assert "roadworkFallbackCoords" in html
    assert "roadworkCoords" in html
    assert "roadworkGeocodeTarget" in html
    assert "cleanRoadworkLocationForGeocoding" in html
    assert "roadworkHasSpecificGeocodeQuery" in html
    assert "fallbackCoords" in html
    assert "const query = cleanRoadworkLocationForGeocoding(title, description)" in html
    assert "Positioniert nach:" in html
    assert "Triester Straße 25 bis 30, ÖBB-Unterführung" in html
    assert "Hilmteichstraße zwischen Mariatroster Straße und Hilmgasse" in html
    assert "spreadRoadworkCoords" in html
    assert "Tiefgaragen" in html
    assert "Apotheken" in html
    assert "Ärzte" in html
    assert "pharmacyMap" in html
    assert "doctorsMap" in html
    assert "#pharmacyMap" in html
    assert "#doctorsMap" in html
    assert "pharmacyFallbackPlaces" in html
    assert "Adler Apotheke Graz" in html
    assert "loadHealthPlacesFromOverpass('pharmacy', pharmacyStatus, true)" in html
    assert "doctorsProfessionFilter" in html
    assert "doctorsLegend" not in html
    assert "data-doctor-group" not in html
    assert "Alle Fachrichtungen" in html
    assert '<option value="Allgemeinmedizin">Allgemeinmedizin</option>' in html
    assert "Tierarzt" in html
    assert "Zahnarzt" in html
    assert "Augenheilkunde" in html
    assert "specialtyDisplayLabel" in html
    assert "Sonstige Fachrichtung" not in html
    assert "Allgemeinmedizin/Ordination" not in html
    assert "Ordinationen.st zeigt aktuelle" not in html
    assert "Aktuelle Ordinationszeiten und Bereitschaftsdienste bitte offiziell prüfen." not in html
    assert "groupHealthPlacesByCoords" in html
    assert "healthPopupHtml" in html
    assert "health-popup-item" in html
    assert "formatOpeningHoursHtml" in html
    assert "healthMeta" in html
    assert "healthWebsite" in html
    assert "Website:" in html
    assert "doctorColorForGroup" in html
    assert "palette[hash % palette.length]" in html
    assert "Nachtdienst öffnen" in html
    assert "Ordinationen.st öffnen" in html
    assert 'class="primary-link" href="https://www.apothekerkammer.at/apothekensuche"' in html
    assert 'class="primary-link" href="https://ordinationen.st/"' in html
    assert "loadHealthPlacesFromOverpass" in html
    assert "parseOverpassHealthPlaces" in html
    assert "OpenStreetMap / ODbL" in html
    assert "Nachtdienste und Bereitschaftsdienste werden nicht lokal berechnet" in html
    assert "Bereitschaftsdienste und aktuelle Ordinationszeiten bitte offiziell prüfen." not in html
    assert "parkingAvailabilityHints" in html
    assert "parkingDetailLinks" in html
    assert "parkingDetailLink" in html
    assert "parkingListCardHtml" in html
    assert "https://www.parken.at/garage/1057/" in html
    assert "https://www.parken.at/garage/1105/" in html
    assert "https://www.parken.at/garage/1053/" in html
    assert "https://www.kastner-oehler.at/service/parken/" in html
    assert "https://www.contipark.at/de/parken/graz/tiefgarage-andreas-hofer-platz/" in html
    assert "https://www.granit-immobilien.at/stadiongarage/" in html
    assert "parking-card" in html
    assert "parking-card-actions" in html
    assert "data-parking-link=\"detail\"" in html
    assert "Betreiberseite öffnen" in html
    assert "Detailquelle öffnen" in html
    assert "supplementalParkingGarages" in html
    assert "TG Lendplatz" in html
    assert "TG Josef-Pongratz-Platz" in html
    assert "Betreiberseite, nur Prüflink; Weiterverwendung vor Import klären" in html
    assert "Live-Verfügbarkeit extern bei Parken.at prüfen" in html
    assert "Parken.at wird nur verlinkt" in html
    assert "Zusätzliche Betreiberstandorte werden nur als Prüflinks ergänzt" in html
    assert "teilweise integriert" in html
    assert "GTFS-Adapter vorbereiten" in html
    assert "lizenzierter DATEX-II-Adapter" in html
    assert "Wobei kann ich behilflich sein?" in html
    assert "KI-generierte Antworten können Fehler enthalten" in html
    assert "background: rgba(255, 255, 255, 0.96)" in html
    assert "background: #f8fafc" in html
    assert "function defaultYearValue()" in html
    assert "return years[0] || ''" in html
    assert "function fillYearSelect" in html
    assert "function fillDateSelect" in html
    assert "String(right).localeCompare(String(left)" in html
    assert "fillYearSelect(yearFilter" in html
    assert "fillDateSelect(dateFilter" in html
    assert "fillYearSelect(topicYearFilter" not in html
    assert "yearFilter.value = defaultYearValue()" in html
    assert "dateFilter.value = ''" in html
    assert "if (target === 'map' && grazMap)" in html
    assert "function sortRecordsForTable(items)" in html
    assert "const tableRenderLimit = 350" in html
    assert "Nutze Suche oder Filter, um die Liste weiter einzugrenzen." in html
    assert "String(right.datum || '').localeCompare(String(left.datum || ''))" in html
    assert "function typeSortRank(record)" in html
    assert "typeSortRank(left) - typeSortRank(right)" in html
    assert "'Mitteilung'," in html
    assert "'Fragestunde'," in html
    assert "'Tagesordnungspunkt'," in html
    assert "'Dringlichkeitsantrag'," in html
    assert "dateFilter.value = ''" in html
    assert "yearFilter.value = ''" in html
    assert "place-items: center" in html
    assert "min-height: clamp(420px, 68vh, 760px)" in html
    assert "width: min(920px, 100%)" in html
    assert ".question-row input" in html
    assert "font-size: clamp(18px, 2vw, 24px)" in html
    assert ".staff-actions button" not in html
    assert "background: var(--accent)" in html
    assert "min-height: 58px" in html
    assert '<div class="question-row">' in html
    assert '<div class="question-result" id="aiAnswer" hidden></div>' in html
    assert '<div class="question-sources" id="aiSources" hidden></div>' in html
    assert "aiAnswer.hidden = false" in html
    assert "qwen2.5:7b-instruct" not in html
    assert "http://localhost:11434/api/chat" not in html
    assert "topLocalSources" in html
    assert "buildQuestionCandidateSet(question)" in html
    assert "buildLocalQuestionAnswer(question, candidateSet)" in html
    assert "answer-shell" in html
    assert "answer-section" in html
    assert "answer-item" in html
    assert "Kurzantwort" in html
    assert "Die Antwort fasst die wichtigsten Treffer zusammen" not in html
    assert "Wichtig sind vor allem:" not in html
    assert "answerThemeText" in html
    assert "answerExampleSummaryText" in html
    assert "Beispiele mit Kurzbeschreibung:" in html
    assert "summaryText:" in html
    assert "border-top: 3px solid #cbd5e1" in html
    assert "Beschlossen oder angenommen" in html
    assert "Offene Anträge und Fragen" in html
    assert "aiAnswer.innerHTML = buildLocalQuestionAnswer(question, candidateSet)" in html
    assert "Ohne Quellen wird keine Antwort erzeugt" in html
    assert "questionFocus(query)" in html
    assert "questionDataFocuses" in html
    assert "questionFocusTermsForValue" in html
    assert "focusLabel: focus.label" in html
    assert "Fokus:" in html
    assert "St. Leonhard" in html
    assert "Geidorf" in html
    assert "Puntigam" in html
    assert "Mariatrost" in html
    assert "Straßgang" in html
    assert "Stadionbau/Stadion Liebenau" in html
    assert "'stadion liebenau', 'merkur arena', 'stadion graz', 'stadion'" in html
    assert "Parken/Parkplätze" in html
    assert "Baustellen" in html
    assert "Apotheken" in html
    assert "Ärzte/Ordinationen" in html
    assert "strasse|straße|gasse|platz|weg|kai|ring|allee|guertel|gürtel" in html
    assert "'bezirk', 'bezirke'" in html
    assert "allLocalQuestionSources()" in html
    assert "candidateSet.scannedCount" in html
    assert "candidateSet.candidateCount" in html
    assert "candidateSet.answerSources = answerSources" in html
    assert "Beschlusslage:" in html
    assert "Beschlossen/angenommen" not in html
    assert "beschlossen/angenommen" in html
    assert "Verlauf/Folgebeschlüsse" in html
    assert "balancedQuestionContextSources" in html
    assert "questionCandidateOverview" in html
    assert "KI-generierte Antworten können Fehler enthalten. Bitte immer die Quellen prüfen." in html
    assert "Quellen nach der KI-Antwort gereiht" not in html
    assert "rankSourcesFromAiAnswer" in html
    assert "citedSourceIndexes" in html
    assert "renderAiSources(answerSources)" in html
    assert "question-sources-more" in html
    assert "Alle ${escapeHtml(sources.length)} Quellen anzeigen" in html
    assert "answer-more" in html
    assert "Alle ${escapeHtml(sources.length)} Treffer in diesem Abschnitt anzeigen" in html
    assert "function answerSourceSort" in html
    assert "candidateSet.contextSources.slice(0, 30)" in html
    assert "function personContributionAnswer" in html
    assert "passende Personentreffer" in html
    assert "Person: ${escapeHtml(person)}" in html
    assert "candidateSet.rankedSources || sources" in html
    assert "max-width: 78ch" not in html
    assert "max-width: 85ch" not in html
    assert "source-rank" in html
    assert "source-kind" in html
    assert "source-facts" in html
    assert "sourceDescription(source)" in html
    assert "source-matches" in html
    assert "Relevanz:" not in html
    assert "recordSourceRoleForAi" in html
    assert "stellte dazu einen selbständigen Antrag" in html
    assert "stellte dazu eine schriftliche Frage" in html
    assert "stellte dazu in der Fragestunde eine Frage" in html
    assert "In dieser Datenbasis ist keine Antwort erfasst" in html
    assert "Es darf daraus nicht geschlossen werden, dass es keine Antwort gab" in html
    assert "keine Antwort erfasst" in html
    assert "Die Stadt bzw. die zuständige Stelle teilte dazu etwas mit" in html
    assert "Quellenart:" in html
    assert "Das ist ein Dringlichkeitsantrag und noch keine Umsetzung" not in html
    assert "Dringlichkeitsantrag." in html
    assert "Schriftlicher Antrag." in html
    assert "border-left: 4px solid #bfdbfe" in html
    assert "line-height: 1.68" in html
    assert "anwohnerparkzone" in html
    assert "anrainerparken" in html
    assert "Stadionbau" in html
    assert "merkur arena" in html
    assert "Apotheke" in html
    assert "Ordination/Ärztin/Arzt" in html
    assert ".slice(0, 40)" in html
    assert ".slice(0, 48)" in html
    assert "grazMap" in html
    assert "roadworksMap" in html
    assert "parkingMap" in html
    assert "pharmacies" in html
    assert "doctors" in html
    assert "Services & Ämter" in html
    assert 'id="mobileNavToggle"' in html
    assert 'aria-controls="sideNav"' in html
    assert 'aria-expanded="false"' in html
    assert 'aria-label="Navigation öffnen"' in html
    assert ".sidebar.nav-open .side-nav" in html
    assert "setMobileNavOpen(false)" in html
    assert "servicesMap" in html
    assert "servicesCategoryFilter" in html
    assert "civicServices" in html
    assert "civicServiceQuestionSource" in html
    assert "Ämterverzeichnis öffnen" in html
    assert "Termine prüfen" in html
    assert "öffentliche Webseite, keine OGD-Lizenz gefunden" in html
    assert "height: min(62vh, 680px)" in html
    assert "overflow-x: auto" in html
    assert "min-width: 1080px" in html
    assert "@media (max-width: 1280px)" in html
    assert "nominatim.openstreetmap.org" in html
    assert "openstreetmap.org" in html
    assert "currentLocationIndex = buildLocationIndex(sichtbareEintraege)" in html
    assert ".slice(0, 120)" not in html
    assert ".slice(0, 80)" not in html
    assert "mapProgressBar" in html
    assert "roadworksProgressBar" in html
    assert "parkingProgressBar" in html
    assert "${loaded}/${places.length} Orte geprüft" in html
    assert "${markersByLocation.size}/${places.length} Orte auf der Karte" in html
    assert "cachedCoordsForLocation" in html
    assert "preloadedLocationCache" in html
    assert "Orte aus Cache" in html
    assert "locationCacheKey(location)" in html
    assert "refreshMapMarkersIfNeeded()" in html
    assert "activeTopicRecordIds" in html
    assert "data-topic-id" not in html
    assert "topic.confidence" not in html
    assert "categoryColors" in html
    assert "categoryFilter.value === category ? '' : category" in html
    assert "focusRecordLocations(record" in html
    assert "selectRecord(ausgewaehlterEintrag, true)" not in html
    assert "selectRecord(findRecordById(step.dataset.recordId), true)" not in html
    assert "focusLocation(locationButton.dataset.location" in html
    assert "L.polyline(points" not in html
    assert "record-route" not in html
    assert "record.typ" in html
    assert "Einbringer" in html
    assert "highlightedLocations" in html
    assert "related-place" in html
    assert "updateMarkerHighlights()" in html
    assert "timelineTopics.map" not in html
    assert "derivedTopicsFromRecords(sichtbareEintraege)" not in html
    assert "filter(topicRecordMatchesFilters)" not in html
    assert "if (yearFilter.value && !meetingDate.startsWith(yearFilter.value + '-')) return false;" not in html
    assert "renderTopics();" not in html
    assert "DIGRA-Trefferwert" in html
    assert "digraLink(record.digra_url" in html
    assert "status-dot" in html
    assert "Kein Ergebnis in den lokalen DIGRA-Daten erfasst" in html
    assert "Lokale PDF-Seite" not in html
    assert "parkingGarages" in html
    assert "Verfügbarkeit: unbekannt" in html
    assert "checkRoadworkPlan" not in html
    assert "roadworkStatusLabels" in html
    assert "data-roadwork-status" in html
    assert "activeRoadworkStatus" in html
    assert "roadworkRuleAssessment" not in html
    assert "buildRoadworkAssessmentSources" not in html
    assert "plannedRoadworkDraft" not in html
    assert "renderRoadworkDraft" not in html
    assert "buildRoadworkDetourHints" not in html
    assert "suggestDetourStreets" not in html
    assert "findDetourConflicts" not in html
    assert "Umleitungskonflikt" not in html
    assert "Konflikte auf möglichen Umleitungsstraßen" not in html
    assert "Prüfe vorgeschlagene Umleitungsstraßen gegen die Quellen" not in html
    assert "Andreas-Hofer-Platz/Innenstadt" not in html
    assert "Grieskai" not in html
    assert "Neutorgasse" not in html
    assert "Mögliche Umleitungs- und Koordinationshinweise" not in html
    assert "acceptRoadworkDraft" not in html
    assert "data-roadwork-action=\"accept\"" not in html
    assert "Auf Karte übernehmen" not in html
    assert "Angaben ändern" not in html
    assert "Verwerfen" not in html
    assert "ai-assessment" not in html
    assert "Noch nicht integrierte Verkehrsdatenquellen" not in html
    assert "werden aber noch nicht automatisch in die KI-Einschätzung eingerechnet" not in html
    assert "trafficSourceList" in html
    assert "Lokale KI-Einschätzung" not in html
    assert "roadworkAssessmentSources" not in html
    assert "https://digra.graz.at/document?ref=b7b33fe0-443a-49c8-9e95-22a77851b9f9" in html
    assert 'target="_blank"' in html
    assert 'rel="noopener noreferrer"' in html
    assert "Quelldatei" in html
    assert "Geschäftszahlen" in html
    assert "Berichterstatterin: GR Beispiel, KPÖ" in html
    assert "agenda_item" not in html
    assert "agenda_item_no" not in html
    assert "accepted_majority" not in html
    assert "record_type" not in html
    assert "status_text" not in html
    assert "Der Antrag wurde" not in html
    assert "raw_result_text" not in html
    assert "abstimmungen" in html
    assert "gegenstimmen" in html
    assert "enthaltungen" in html
    assert "KI-generierte Inhalte können Fehler enthalten" in html
    assert "source_snippet" not in html
    assert "raw_text" not in html


def test_viewer_assigns_unclear_written_submissions():
    record = viewer_record(
        {
            "record_id": "written-test",
            "record_type": "written_question",
            "meeting_date": "2026-04-23",
            "section": "Anfragen (schriftlich)",
            "agenda_item_no": 1,
            "business_numbers": [],
            "title": "Schriftliche Anfrage ohne Ergebnis",
            "status": "unknown",
            "result_text": "Unbekannt",
            "source_file": "test.docx",
        }
    )

    assert record["status"] == "zugewiesen"
    assert record["status_filter"] == "Zugewiesen"
    assert record["ergebnis"] == "Verfahren: zugewiesen"


def test_viewer_labels_city_protocol_result_sources():
    assert viewer_record({"record_type": "archive_source", "result_source": "archiv"})["ergebnisquelle"] == "Stadt-Graz-Protokoll"
    assert viewer_record({"record_type": "agenda_item", "result_source": "protokoll"})["ergebnisquelle"] == "Stadt-Graz-Protokoll"


def test_viewer_infers_locations_for_records_without_location_field():
    record = viewer_record(
        {
            "meeting_date": "2026-01-22",
            "record_type": "written_question",
            "status": "unknown",
            "title": "Sanierung der Triester Straße im Bezirk Straßgang",
            "locations": [],
        }
    )

    assert "Triester Straße" in record["orte"]
    assert "Straßgang" in record["orte"]


def test_viewer_filters_land_register_values_from_existing_locations():
    record = viewer_record(
        {
            "meeting_date": "2026-01-22",
            "record_type": "agenda_item",
            "status": "accepted",
            "title": "Sanierung der Triester Straße, KG St. Peter, EZ 1353",
            "locations": ["KG St", "EZ 1353", "Gdst. Nr. 123/4", "Triester Straße"],
        }
    )

    assert "Triester Straße" in record["orte"]
    assert "KG St" not in record["orte"]
    assert "EZ 1353" not in record["orte"]
    assert "Gdst. Nr. 123/4" not in record["orte"]


def test_viewer_filters_budget_deckungsring_and_keeps_weinzoedl_location():
    record = viewer_record(
        {
            "meeting_date": "2026-06-18",
            "record_type": "agenda_item",
            "status": "accepted",
            "title": "Fördervereinbarung GAK Akademiecampus in Weinzödl",
            "source_snippet": "Die Förderung wird aus dem Deckungsring D.120004 abgedeckt. Der Akademiecampus liegt in Weinzödl.",
            "locations": [],
        }
    )

    assert "Weinzödl" in record["orte"]
    assert "Deckungsring" not in record["orte"]


def test_viewer_renders_ai_record_summaries_as_expandable_details():
    html = build_html(
        [
            {
                "agenda_item_no": 1,
                "ai_easy_language": "Die Stadt entscheidet über eine Maßnahme. Das wird einfach erklärt.",
                "ai_key_points": [
                    {
                        "kind": "Beschluss",
                        "text": "Die Maßnahme wird umgesetzt",
                        "simple": "Die Stadt macht die Maßnahme.",
                        "status": "beschlossen",
                    }
                ],
                "ai_open_points": ["Der genaue Zeitplan ist nicht erfasst."],
                "ai_summary": "Das Stück behandelt die wichtigsten Punkte einer Maßnahme.",
                "ai_why_interesting": "Das ist interessant, weil Bürgerinnen und Bürger betroffen sind.",
                "business_numbers": [],
                "locations": [],
                "meeting_date": "2026-04-23",
                "record_id": "test-record",
                "record_type": "agenda_item",
                "result_text": "Antrag: angenommen",
                "section": "Tagesordnung",
                "source_file": "test.docx",
                "status": "accepted",
                "title": "Teststück",
            }
        ],
        {},
    )

    assert "KI-Zusammenfassung" in html
    assert "Einfache Sprache" in html
    assert "summary-block" in html
    assert "summary-toggle-sub" in html
    assert "Inhalt, Einordnung und Ergebnisstand kompakt zusammengefasst." in html
    assert "Gleicher Inhalt einfacher formuliert." in html
    assert "data-summary-kind" in html
    assert "summaryDisplayText" in html
    assert "clippedSummaryDisplayText" in html
    assert "Warum ist das interessant?" not in html
    assert "Kernpunkte und offene Punkte" not in html
    assert "summaryPointsText" in html
    assert "max-height: 520px" in html
    assert "Einordnung:" not in html


def test_viewer_normalizes_contradictory_unanimous_ai_summary_with_against_votes():
    record = viewer_record(
        {
            "meeting_date": "2026-01-16",
            "record_type": "agenda_item",
            "status": "accepted_majority",
            "title": "Teststück",
            "ai_summary": "Der Antrag wurde einstimmig angenommen. Dagegen: KFG.",
            "ai_easy_language": "Der Antrag wurde einstimmig angenommen. Gegen: KFG.",
        }
    )

    assert "mehrheitlich angenommen" in record["ki_zusammenfassung"]
    assert "mehrheitlich angenommen" in record["ki_einfache_sprache"]
    assert "einstimmig angenommen" not in record["ki_zusammenfassung"]
    assert "einstimmig angenommen" not in record["ki_einfache_sprache"]


def test_viewer_replaces_bad_question_summary_display_text():
    record = viewer_record(
        {
            "meeting_date": "2026-01-16",
            "title": "ÖV-Anbindung des Grieskais",
            "record_type": "question_hour",
            "submitter": "GR. Eichberger",
            "result_text": "Unbekannt",
            "ai_summary": (
                "Die Fragestunde behandelt „ÖV‐Anbindung des Grieskais“. Frage: Werter Herr Bürgermeister, "
                "Frau Vizebürgermeisterin, liebe Kolleginnen, liebe Kollegen! In meiner Frage geht es um die "
                "ÖV-Anbindung des Grieskais, ist leider momentan nicht da, aber ich hoffe, er ist mir nicht böse. "
                "Das dokumentierte Ergebnis lautet: Unbekannt."
            ),
            "question_parts": {
                "question": "Werter Herr Bürgermeister, in meiner Frage geht es um die ÖV-Anbindung des Grieskais.",
                "answer": "Werter Herr Gemeinderat! Meine Frage richtet sich an den Herrn Bürgermeister.",
                "respondent": "Bgm.-Stvin. Rücker",
            },
        }
    )

    assert record["ki_zusammenfassung"].startswith("GR. Eichberger fragt zum Thema „ÖV-Anbindung des Grieskais“.")
    assert "Gefragt hat GR. Eichberger" not in record["ki_zusammenfassung"]
    assert "Adressiert ist die Frage an Bgm.-Stvin. Rücker" in record["ki_zusammenfassung"]
    assert "Eine Antwort ist in der lokalen Datenbasis nicht erfasst." in record["ki_zusammenfassung"]
    assert "Frage:" not in record["ki_zusammenfassung"]
    assert "Werter Herr Bürgermeister" not in record["ki_zusammenfassung"]
    assert "Werter Herr Gemeinderat" not in record["ki_zusammenfassung"]
    assert "Meine Frage richtet sich" not in record["ki_zusammenfassung"]
    assert "Das dokumentierte Ergebnis lautet: Unbekannt" not in record["ki_zusammenfassung"]


def test_viewer_question_fallback_summary_uses_procedural_status_without_meta_text():
    record = viewer_record(
        {
            "meeting_date": "2026-01-16",
            "title": "Stadion",
            "record_type": "written_question",
            "submitter": "GR Markus Huber (ÖVP)",
            "result_text": "Verfahren: zugewiesen",
            "business_numbers": ["2713/1"],
            "status": "assigned",
        }
    )

    assert record["ki_zusammenfassung"] == (
        "GR Markus Huber (ÖVP) fragt zum Thema „Stadion“. "
        "In den lokalen Daten ist nur der Verfahrensstand „zugewiesen“ erfasst; "
        "eine inhaltliche Antwort ist dort nicht hinterlegt. Geschäftszahl: 2713/1."
    )
    assert "Einordnung:" not in record["ki_zusammenfassung"]
    assert "beschreibt daher Antrag" not in record["ki_zusammenfassung"]


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


def test_viewer_classifies_record_category():
    record = viewer_record(
        {
            "meeting_date": "2026-02-12",
            "record_id": "r1",
            "record_type": "agenda_item",
            "source_file": "test.docx",
            "status": "accepted_unanimous",
            "title": "Erhöhung und Verlängerung der Projektgenehmigung Prüfung Stadion Graz Liebenau",
        }
    )

    assert record["kategorie"] == "Kultur, Sport & Veranstaltungen"


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
                        "business_numbers": ["A 14-001665/2025"],
                        "result_text": "Antrag: angenommen",
                        "status": "accepted",
                        "title": "Auflage des Entwurfs",
                    },
                    {
                        "meeting_date": "2025-03-20",
                        "record_id": "record-b",
                        "business_numbers": ["A 14-001665/2025"],
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

    assert "Themenverläufe" not in html
    assert "timeline-step" not in html
    assert "timeline-business-group" not in html
    assert "timeline-business-label" not in html
    assert "timeline-business" not in html
    assert "timelineBusinessGroups" not in html
    assert "userFacingTopicResult" not in html
    assert "Zeitstrahl:" not in html
    assert "Einträge dazu filtern" not in html
    assert "Flächenwidmungsplan Landeshauptstadt" in html
    assert "Geschäftszahl:" not in html
    assert "A 14-001665/2025" in html
    assert "recordBusinessLabel" not in html
    assert "recordBusinessNumbers" not in html
    assert "gleiche Geschäftszahl-Basis" not in html
    assert "KI-Hinweis:" not in html
    assert "Gemeinsames Projekt über mehrere Sitzungen" in html
    assert "Letzter Stand:" not in html
    assert "Antrag: mehrheitlich angenommen" in html
    assert "data-topic-id" not in html
    assert "record-b" in html
    assert "Auflage des Entwurfs" in html
    assert "Aktuelle Hinweise" not in html
    assert "Gemeinderat beschließt Flächenwidmungsplan" in html


def test_viewer_strips_record_type_prefixes_from_titles():
    assert clean_display_title("Fragestunde: Verlängerung der Linie 5") == "Verlängerung der Linie 5"
    assert clean_display_title("Schriftliche Anfrage: Leerstand in Graz") == "Leerstand in Graz"
    assert (
        clean_display_title(
            "Berichterstatter:in: GR Tristan Ammerer (Grüne) Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie"
        )
        == "Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie"
    )
    assert (
        clean_display_title(
            "Berichterstatterin: Klubobfrau Dipl.-Ing. (FH) Daniela Schlüsselberger (SPÖ) Grundsatzbeschluss Modernisierung Stadion Graz Liebenau 1. Ausgangslage"
        )
        == "Grundsatzbeschluss Modernisierung Stadion Graz Liebenau 1. Ausgangslage"
    )
    assert (
        clean_display_title("Neutorgasse Behindertenparkplatz Sehr geehrte Frau Vizebürgermeisterin")
        == "Neutorgasse Behindertenparkplatz"
    )
    assert clean_display_title("Sehr geehrter Herr Bürgermeisterstellvertreter, sind von deiner Seite Schritte geplant?") == ""

    record = viewer_record(
        {
            "meeting_date": "2026-01-01",
            "record_type": "written_question",
            "status": "unknown",
            "title": "Schriftliche Anfrage: Leerstand in Graz",
        }
    )
    assert record["titel"] == "Leerstand in Graz"

    html = build_html(
        [],
        {},
        [
            {
                "dates": ["2026-01-01", "2026-02-01"],
                "label": "Leerstand in Graz",
                "records": [
                    {
                        "meeting_date": "2026-01-01",
                        "record_id": "record-a",
                        "record_type": "question_hour",
                        "result_text": "Unbekannt",
                        "status": "unknown",
                        "title": "Fragestunde: Verlängerung der Linie 5",
                    },
                    {
                        "meeting_date": "2026-02-01",
                        "record_id": "record-b",
                        "record_type": "written_question",
                        "result_text": "Unbekannt",
                        "status": "unknown",
                        "title": "Schriftliche Anfrage: Leerstand in Graz",
                    },
                ],
                "topic_id": "topic-prefix-test",
            }
        ],
    )
    assert "Fragestunde: Verlängerung" not in html
    assert "Schriftliche Anfrage: Leerstand" not in html
    assert "Verlängerung der Linie 5" in html
    assert "Leerstand in Graz" in html


def test_viewer_uses_source_snippet_title_when_record_title_is_only_reporter():
    record = viewer_record(
        {
            "record_type": "agenda_item",
            "status": "accepted_unanimous",
            "title": "Berichterstatter:in: GR Tristan Ammerer (Grüne)",
            "source_snippet": (
                "Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie: Änderung von Geschäftsordnungen "
                "I. Allgemeiner Teil Der Gemeinderat hat dazu bereits einen Antrag beschlossen."
            ),
        }
    )

    assert record["titel"] == "Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie: Änderung von Geschäftsordnungen"


def test_viewer_prefers_structured_topic_and_betreff_titles_for_archive_sources():
    assert (
        viewer_record(
            {
                "record_type": "archive_source",
                "status": "source_available",
                "title": "Anträge",
                "source_snippet": "Betr.: Sicherheit in der Panoramagasse\nWeitere Details",
            }
        )["titel"]
        == "Sicherheit in der Panoramagasse"
    )
    assert (
        viewer_record(
            {
                "record_type": "archive_source",
                "status": "source_available",
                "title": "Tagesordnung",
                "source_snippet": "Thema: Sanierung Leonhardstraße",
            }
        )["titel"]
        == "Sanierung Leonhardstraße"
    )


def test_viewer_improves_generic_archive_titles_from_pdf_urls():
    record = viewer_record(
        {
            "record_type": "archive_source",
            "status": "source_available",
            "title": "Dringlichkeitsanträge",
            "source_url": "https://www.graz.at/cms/dokumente/10418012_7768145/c7ea592c/231116_dringliche2.pdf",
        }
    )
    assert record["titel"] == "Dringlichkeitsanträge vom 16.11.2023 (Teil 2)"

    attendance = viewer_record(
        {
            "record_type": "archive_source",
            "status": "source_available",
            "title": "Anwesenheitsliste",
            "source_url": "https://www.graz.at/cms/dokumente/10418012_7768145/11111111/231116_anwesenheitsliste.pdf",
        }
    )
    assert attendance["typ"] == "Anwesenheitsliste"
    assert attendance["titel"] == "Anwesenheitsliste"


def test_viewer_labels_amendment_and_additional_motion_types():
    assert viewer_record({"record_type": "amendment_motion", "status": "unknown"})["typ"] == "Abänderungsantrag"
    assert viewer_record({"record_type": "additional_motion", "status": "unknown"})["typ"] == "Zusatzantrag"
    assert viewer_record({"record_type": "additional_motion", "status": "unknown"})["ergebnis"] == "Verfahren: zugewiesen"


def test_viewer_hides_topics_with_only_one_visible_record_after_filters():
    html = build_html(
        [],
        {},
        [
            {
                "confidence": 0.95,
                "business_number": "A14-081274/2023",
                "dates": ["2024-11-14", "2025-05-15"],
                "label": "Flächenwidmungsplan Änderung",
                "records": [
                    {
                        "business_numbers": ["A14-081274/2023/0382"],
                        "meeting_date": "2024-11-14",
                        "record_id": "record-a",
                        "result_text": "Antrag: angenommen",
                        "status": "accepted",
                        "title": "4.08 A Flächenwidmungsplan - 8. Änderung Teil A",
                    },
                    {
                        "business_numbers": ["A14-081274/2023/0411"],
                        "meeting_date": "2025-05-15",
                        "record_id": "record-b",
                        "result_text": "Antrag: angenommen",
                        "status": "accepted",
                        "title": "Ergänzungsbeschluss 4.08 A",
                    },
                ],
                "topic_id": "business-a14-081274-2023",
            }
        ],
    )

    assert "visibleRecords.length >= 2" not in html
    assert "record.business_number" not in html
    assert "...(record.business_numbers || [])" not in html


def test_viewer_can_build_timeline_from_visible_records_without_topics():
    html = build_html(
        [
            {
                "business_numbers": ["A10-123/2025"],
                "category": "Mobilität",
                "date": "2025-01-16",
                "record_id": "record-a",
                "record_type": "written_motion",
                "result_text": "Antrag angenommen",
                "source": {"file": "fixture.docx"},
                "status": "accepted",
                "title": "Erster Beschluss",
            },
            {
                "business_numbers": ["A10-123/2025"],
                "category": "Mobilität",
                "date": "2025-03-20",
                "record_id": "record-b",
                "record_type": "written_motion",
                "result_text": "Folgebeschluss",
                "source": {"file": "fixture.docx"},
                "status": "accepted",
                "title": "Zweiter Beschluss",
            },
        ],
        {},
        [],
    )

    assert "derivedTopicsFromRecords(sichtbareEintraege)" not in html
    assert "Geschäftszahl ${number}" not in html
    assert "topicFilterRecords = topics.length" not in html


def test_preloaded_location_cache_uses_known_and_embedded_coords():
    cache = build_preloaded_location_cache(
        [{"locations": ["Hauptplatz", "Unbekannter Ort"]}],
        [{"name": "PH Test", "address": "Testgasse 1, Graz", "lat": 47.1, "lon": 15.4}],
        [],
        [{"name": "Apotheke Test", "address": "Pharmagasse 2, Graz", "lat": 47.2, "lon": 15.5}],
        [],
    )

    assert cache["Hauptplatz"] == {"lat": 47.0707, "lon": 15.4386}
    assert cache["Testgasse 1, Graz"] == {"lat": 47.1, "lon": 15.4}
    assert cache["PH Test"] == {"lat": 47.1, "lon": 15.4}
    assert cache["Pharmagasse 2, Graz"] == {"lat": 47.2, "lon": 15.5}
    assert "Unbekannter Ort" not in cache
