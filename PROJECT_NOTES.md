# Projektstand

## Richtung

Das Projekt soll ein strukturiertes Entscheidungsregister für Grazer Gemeinderatsprotokolle werden:

- Volltextsuche mit Quellenbezug
- Extraktion von Tagesordnungspunkten
- Klassifikation von Entscheidungen und Status
- Extraktion von Geldbeträgen
- Extraktion von Orten und spätere Kartenansicht
- Themenverläufe über mehrere Sitzungen

## Nützliche bestehende Werkzeuge

`E:\01_StadtGrazProtokolle\Digra_Export_Tool` enthält bereits brauchbare Logik für DIGRA:

- Sitzungen finden
- DIGRA-Reiter auslesen
- tagesordnungsbezogene Dokumente exportieren
- DOCX-Protokollmaterial erzeugen

Dieses Projekt kann als Vorlage dienen. Rohe Exporte daraus dürfen aber nicht ins Git.

## Aktueller Arbeitsstand

Stand 2026-06-08 enthält `graz_protokolle_arbeitskopie/` 18 lokale DOCX-Protokollkopien für die erste Analyse. Der Ordner ist ignoriert und muss untracked bleiben.

## MVP-Parser

Der MVP-Parser liest ignorierte lokale DOCX-Dateien und schreibt ignorierte strukturierte Ausgabe.

Aktuelle Module:

- `graz_protocols/docx_text.py`: DOCX-Textextraktion mit Standardbibliothek
- `graz_protocols/parser.py`: Extraktion von Tagesordnungspunkten, Status, Beträgen, Geschäftszahlen und Ortshinweisen
- `graz_protocols/digra_import.py`: DIGRA-Abgleich über das vorhandene DIGRA-Export-Tool, Sitzungssuche, Dokumentlinks und Beschlussvermerk-Ergebnisse
- `graz_protocols/audit.py`: Markdown-Auditbericht für Ergebnisquellen, Fallbacks und niedrige DIGRA-Trefferwerte
- `graz_protocols/schema.py`: Validierung des JSONL-Datenmodells
- `graz_protocols/street_names.py`: XLSX-Import und Normalisierung der Grazer Straßennamenliste
- `graz_protocols/topics.py`: Themenkandidaten über Geschäftszahlen und Titel-Keywords
- `graz_protocols/ai_topics.py`: optionale KI-Überschriften für Themenverläufe, standardmäßig über lokales Ollama/Qwen, optional über OpenAI
- `graz_protocols/ai_summaries.py`: optionale KI-Zusammenfassungen pro Stück und Version in einfacher Sprache, standardmäßig über lokales Ollama/Qwen
- `graz_protocols/cli.py`: Stapelverarbeitung über die Kommandozeile
- `graz_protocols/sqlite_export.py`: lokale SQLite-Ausgabe mit Tabelle `eintraege`, normalisierten Tabellen und FTS5
- `graz_protocols/viewer.py`: erzeugte lokale Doppelklick-HTML-Ansicht
- `scripts/check_git_safety.py`: lokaler und CI-fähiger Sicherheitscheck gegen versehentlich committed Quellen-/Exportdaten
- `tests/test_parser.py`: bereinigte Parser-Tests
- `tests/test_digra_import.py`: Test, dass DIGRA-Ergebnisse nur aus dem `Beschlussvermerk` extrahiert werden
- `tests/test_goldset.py`: 20 sanitisierten Goldset-Fälle für Status, Geschäftszahl, Titel, Betrag und Abschnitt
- `tests/test_viewer.py`: Tests für deutsche Viewer-Anzeige und Rohtextschutz

Aktuelle Ergebnisbehandlung:

- Formale Ergebniszeilen werden für lokale Nachvollziehbarkeit in `raw_result_text` abgelegt.
- `result_text` wird für die Anzeige vereinheitlicht und nicht aus der Protokollformulierung kopiert.
- Strukturierte Abstimmungsdetails werden in `votes` ausgegeben.
- Die Statusklassifikation bevorzugt formale Ergebniszeilen gegenüber zufälligen Wörtern in Reden.
- Ältere Formulierungen wie `mehrstimmig angenommen` werden zu mehrheitlicher Annahme normalisiert.
- Parteiangaben wie `(Gegen KFG, NEOS, FPÖ)` werden zu `Dagegen: ...` normalisiert.
- Der lokale Viewer zeigt deutsche Typen, deutsche Statuswerte und nur vereinheitlichte `Ergebnisse`.
- Der lokale Viewer hat eine Detailansicht pro Eintrag mit Titel, Ergebnis, Ergebnisquelle, DIGRA-Einlagezahl, DIGRA-Trefferwert, DIGRA-Link, Geschäftszahlen, Beträgen, Orten und Quelldatei.
- Die Filterleiste ist global sichtbar und wirkt auf Suche, Zeitstrahlen, Karte und Export.
- Die Karte ist ein eigener großer Tab; alle gefilterten Orte werden geladen, Marker werden erst beim Öffnen der Karte geocodiert und bei unveränderter Ortsauswahl nicht erneut geladen.
- Beim Öffnen eines Eintrags werden die zugehörigen Ortsmarker grün hervorgehoben; Verbindungslinien werden nicht mehr gezeichnet.
- Zeitstrahl-Aktionen filtern direkt über Record-IDs statt über KI-Überschriftentext.
- Zeitstrahlen zeigen nur Themen mit mindestens zwei sichtbaren Einträgen, KI-Hinweise und den letzten bekannten Ergebnisstand.
- DIGRA-Links werden im Viewer auf stabile `document?ref=...`-URLs ohne flüchtige Session-Parameter normalisiert.
- `city-index` legt einen lokalen Index älterer Stadt-Graz-Archivseiten an; bei DNS-/Netzwerkfehlern werden Fehler im Index dokumentiert.
- Der lokale Viewer kann nach Ergebnisquelle filtern: `DIGRA`, `Protokoll`, `DIGRA fehlt`.
- Der lokale Viewer kann nach Betragsvorkommen und Quelldatei filtern und die aktuelle Trefferliste als CSV exportieren.
- Der lokale Viewer zeigt optional Themenverläufe aus `out\topic_candidates.json`.
- Der lokale Viewer enthält eine Graz-Karte mit Leaflet/OpenStreetMap; Orte sind anklickbar, Marker-Popups führen zu den Einträgen.
- Der Jahresfilter wirkt auf Trefferliste, Themenverläufe und Karte.
- DIGRA-Links werden im Viewer als anklickbare externe Links gerendert.
- Stadt-Graz-Archivlinks werden als Quellenfallback unter `source_url` gespeichert und im Viewer verlinkt.
- Rohformulierungen, Quellenausschnitte und interne englische Typ-/Statuscodes bleiben aus dem Viewer draußen.
- Beträge werden nur aus Titel/Überschrift oder aus formalen Antrag-/Anfrageabschnitten übernommen, nicht aus beliebigen Debattenstellen.
- Ortskandidaten werden optional gegen `Straßennamen_Graz.xlsx` geprüft; Titel-Orte haben Vorrang vor späteren Vergleichsstraßen im Antragstext.
- Straßengruppen und zusammengesetzte Straßennamen wie `Waltendorfer Hauptstraße – Schulgasse – Ruckerlberggasse` werden vollständig aus der Straßennamenliste erkannt.
- Der Viewer zeigt vorhandene KI-Zusammenfassungen pro Stück als ausklappbare Blöcke: fachliche Kurzfassung und einfache Sprache.

## DIGRA-Abgleich

Der aktuelle DIGRA-Abgleich nutzt `E:\01_StadtGrazProtokolle\Digra_Export_Tool\app` als bestehende technische Basis.
Er übernimmt aus DIGRA:

- Sitzung und Datum
- Reiter/Abschnitt
- Reihenfolge der Einträge
- DIGRA-Einlagezahl
- DIGRA-Dokumentlink
- offizielles Ergebnis aus `Beschlussvermerk`, wenn vorhanden

Wichtig: Ergebnisse werden nicht aus beliebigen Wörtern im DIGRA-Dokumenttext abgeleitet. Nur ein `Beschlussvermerk` zählt als DIGRA-Ergebnis.
Im Standardmodus `--digra` haben DIGRA-Beschlussvermerke Vorrang. Wo DIGRA wirklich kein Ergebnis liefert oder die Zuordnung nicht plausibel genug ist, wird das normalisierte Protokoll-Ergebnis als Fallback verwendet.
Mit `--digra-results-only` werden nicht belegte Ergebnisse ausdrücklich als `DIGRA-Ergebnis fehlt` markiert; dieser Modus ist nur für Audits gedacht.
DIGRA-Links werden konservativ zugeordnet: niedrige Titelähnlichkeiten werden verworfen, und Protokoll-Fallbacks behalten einen DIGRA-Link nur bei hoher Zuordnungssicherheit.

Letzter lokaler Lauf am 2026-06-08:

- Eingabe: `graz_protokolle_arbeitskopie/`
- geparste Dateien: 18
- geschriebene Einträge: 1135
- Einträge mit strukturierten Abstimmungs-/Ergebnisdaten: 1053
- interne Eintragstypen:
  - `agenda_item`: 459
  - `urgent_motion`: 108
  - `written_question`: 235
  - `written_motion`: 333
- interne Statusverteilung:
  - `accepted_majority`: 181
  - `accepted_unanimous`: 317
  - `assigned`: 571
  - `rejected_majority`: 43
  - `unknown`: 20
- Ausgabe: `out/agenda_items.jsonl`
- SQLite-Ausgabe: `out/eintraege.sqlite`

Letzter DIGRA-Lauf am 2026-06-08:

- Befehl: `python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items_digra.jsonl --summary out\summary_digra.json --sqlite out\eintraege_digra.sqlite --digra`
- Aktueller Befehl mit Straßennamenabgleich und Stadt-Graz-Archivlinks: `python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items_digra.jsonl --summary out\summary_digra.json --sqlite out\eintraege_digra.sqlite --digra --street-names .\Straßennamen_Graz.xlsx --city-archive-links`
- DIGRA-Einträge geladen: 1675
- lokalen Datensätzen zugeordnet: 938
- Ergebnisse aus DIGRA-Beschlussvermerken übernommen: 415
- Protokoll-Fallbacks, weil DIGRA kein plausibel zuordenbares Ergebnis liefert: 720
- Datensätze ohne DIGRA- oder Protokoll-Ergebnis: 5
- Stadt-Graz-Archivlinks geladen: 58
- Stadt-Graz-Archivlinks angewendet: 145
- Ausgabe: `out/agenda_items_digra.jsonl`
- SQLite-Ausgabe: `out\eintraege_digra.sqlite`
- Viewer-Ausgabe: `viewer.html`
- KI-Zusammenfassungs-Probe: `python -m graz_protocols.cli summaries --records out\agenda_items_digra.jsonl --output out\agenda_items_digra_ai.jsonl --ai-model qwen2.5:7b-instruct --limit 10`
- Vollständiger KI-Lauf: gleicher Befehl ohne `--limit`; der Lauf schreibt fortlaufend nach `out\agenda_items_digra_ai.jsonl` und kann erneut gestartet werden, um vorhandene Zusammenfassungen wiederzuverwenden.
- Audit-Ausgabe: `out\digra_audit.md`
- Themenkandidaten: `out\topic_candidates.json`
- Topic-News: optional über Stadt-Graz-RSS mit `--city-news`
- Viewer-Karte: Online-Geocoding nur im Browser bei Bedarf, keine Koordinaten-Exporte im Git.
- DIGRA-Audit nach strengerer Zuordnung: keine Links mit Trefferwert unter 0,5.

Erzeugte Ausgabe ist absichtlich ignoriert.

## Nächster Ausbauschritt

Die Extraktionsqualität über die Abschnittserkennung hinaus verbessern:

- DIGRA-Ergebnisse systematisch gegen Parser-Ergebnisse abgleichen
- komplexe Änderungs- und Zusatzanträge besser trennen
- Ortserkennung verbessern und geocoding-taugliche Ortsdatensätze erzeugen
- Zeitachsenabfragen auf der SQLite-Ausgabe aufbauen

## GitHub Issues

Am 2026-06-08 im privaten GitHub-Repository angelegt. Die MVP-Issues #3 bis #12 sind umgesetzt oder werden mit dem aktuellen Commit geschlossen:

- strukturierte Abstimmungsergebnisse
- JSONL-Schema und Validierung
- SQLite-Normalisierung und FTS
- DIGRA-Integration inklusive Export-Tool-Nutzung
- Ortserkennung mit Straßennamenabgleich
- lokale HTML-Ansicht mit CSV, Detailpanel und Themenverläufen
- sanitisiertes Goldset mit 20 Fällen
- Git-/Datensicherheitsprüfung
- Themenkandidaten über mehrere Sitzungen
- aktualisierte Produkt- und Entwicklerdokumentation
