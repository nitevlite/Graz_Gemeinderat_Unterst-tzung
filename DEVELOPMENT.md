# Entwicklung

## Git-Regeln

Vor dem Staging:

```powershell
git status --short
python scripts\check_git_safety.py
```

Nur Quellcode und Dokumentation stagen. Niemals Protokolldateien oder erzeugte rohe Extraktionsausgaben stagen.
Der Sicherheitscheck läuft zusätzlich in GitHub Actions bei Push und Pull Request.

GitHub-Remote:

```text
origin https://github.com/nitevlite/graz-council-protocol-explorer.git
```

Empfohlenes Staging-Muster:

```powershell
git add .gitignore AGENTS.md README.md DATA_POLICY.md PROJECT_NOTES.md DEVELOPMENT.md
```

## Lokale Daten

Quelldokumente bleiben in ignorierten Ordnern. Der aktuelle lokale Arbeitsordner ist:

```text
graz_protokolle_arbeitskopie/
```

## Parser-Ausgabe

Erzeugte Daten in ignorierte Pfade schreiben, zum Beispiel:

```text
out/
exports/
```

Erzeugte Datenbanken oder JSONL-Dateien nicht committen, außer es sind winzige bereinigte Testfixtures.

## Befehle

Tests ausführen:

```powershell
python -m pytest -q
```

Pytest läuft ohne Cache-Provider, damit keine lokalen Cache-Dateien entstehen.

Parser-MVP ausführen:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items.jsonl --summary out\summary.json --sqlite out\eintraege.sqlite
```

Die Parser-Ausgabe ist lokales Arbeitsmaterial und wird von Git ignoriert.
Der aktuelle Parser liest DOCX-Absatzformatvorlagen und erzeugt mehrere Eintragstypen, darunter schriftliche Anfragen und Anträge.
Er erzeugt `result_text` als normalisierte Anzeige, `votes` für strukturierte Entscheidungsdetails und `raw_result_text` nur als lokale Rohspur in der ignorierten JSONL-Ausgabe.
Mit `--sqlite` erzeugt er zusätzlich eine lokale SQLite-Datenbank mit deutscher Tabelle `eintraege`, normalisierten Tabellen, der bisherigen FTS5-Volltextsuche und dem produktionsnäheren Suchindex `search_documents`/`search_chunks`/`search_fts`.

DIGRA-Abgleich ausführen:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items_digra.jsonl --summary out\summary_digra.json --sqlite out\eintraege_digra.sqlite --digra --street-names .\Straßennamen_Graz.xlsx --city-archive-links
```

Dieser Lauf nutzt `E:\01_StadtGrazProtokolle\Digra_Export_Tool\app`.
Die DIGRA-Daten werden in `out\digra_cache.json` gecacht und bleiben ignoriertes lokales Arbeitsmaterial.
DIGRA-Beschlussvermerke haben Vorrang; wo DIGRA wirklich kein Ergebnis liefert, wird das normalisierte Protokoll-Ergebnis als Fallback verwendet.
`--digra-results-only` ist nur für Audits gedacht und markiert fehlende DIGRA-Beschlussvermerke als `DIGRA-Ergebnis fehlt`.
`--street-names` filtert Ortskandidaten gegen die lokale Grazer Straßennamenliste.
`--city-archive-links` ergänzt Stadt-Graz-Archivlinks als Quellenfallback.

DIGRA-Sitzungen und einzelne DIGRA-Exporte:

```powershell
python -m graz_protocols.cli digra-list --limit 20
python -m graz_protocols.cli digra-sync --limit 30 --output out\agenda_items_digra_sync.jsonl --summary out\summary_digra_sync.json --sqlite out\eintraege_digra_sync.sqlite --city-archive-links --city-archive-assets --city-archive-assets-index out\city_archive_assets.json
python -m graz_protocols.cli digra-export --date 2026-04-23 --output out\digra_2026-04-23.jsonl --summary out\digra_2026-04-23_summary.json --sqlite out\digra_2026-04-23.sqlite
python -m graz_protocols.cli digra-update --base-records out\agenda_items_digra_ai.jsonl --base-summary out\summary_digra.json --output out\agenda_items_digra_ai_plus_latest.jsonl --summary out\summary_digra_plus_latest.json
```

`digra-sync` ist der Open-Source-Standardpfad ohne lokale DOCX-Protokollkopien. Er exportiert die letzten DIGRA-Sitzungen in ignorierte JSONL-/Summary-/SQLite-Ausgaben und kann Stadt-Graz-Archivlinks sowie vorhandene Stadt-Graz-Archivassets als `Archivquelle`-Records ergänzen.
Wenn das lokale externe Export-Tool fehlt, fällt der Import automatisch auf `graz_protocols.digra_public` zurück. Dieser Fallback nutzt nur die öffentliche DIGRA-Webseite und ist der Pfad für GitHub Actions und andere Linux-/CI-Umgebungen.
`digra-update` ergänzt fehlende neue DIGRA-Sitzungen ohne DOCX-Protokoll als lokale ignorierte JSONL-Ausgabe. Der Doppelklick-Starter führt diesen Schritt nicht blockierend vor dem Viewer-Bau aus, sondern startet bei Bedarf `python -m graz_protocols.background_update` als minimierten Hintergrunddienst. Der Dienst prüft periodisch, baut Topics und `viewer.html` neu und schreibt nach `out\digra_background.log`.

Lokale HTML-Ansicht bauen:

```powershell
python -m graz_protocols.viewer --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --topics out\topic_candidates.json --output viewer.html
```

Lokale HTML-Ansicht per Doppelklick starten:

```text
Start Viewer mit Ollama.cmd
```

Die CMD-Datei startet einen lokalen Viewer-Server auf `http://127.0.0.1:8765/`, startet den DIGRA-Hintergrunddienst und öffnet `viewer.html`.
Der lokale HTTP-Start ist wichtig, damit Karten-, Quellen- und Browserfunktionen zuverlässiger funktionieren als bei direktem `file://`-Öffnen.

Der erzeugte Viewer entfernt Rohformulierungen, Quellenausschnitte und interne englische Typ-/Statuscodes aus den eingebetteten Einträgen.
Ein Klick auf eine Tabellenzeile zeigt eine deutsche Detailansicht für den Eintrag, inklusive Ergebnisquelle und DIGRA-Link.
Optional eingebettete Themenkandidaten erscheinen als einfache Themenverläufe oberhalb der Tabelle.
Fragestunde wird als eigener Record-Typ `question_hour` erkannt. Zusammenfassungen sollen Frage, Antwort und Zusatzfrage/Nachfrage gesondert herausarbeiten. Der Start-Tab beantwortet Fragen kostenlos aus lokalen Quellen und trennt Beschlüsse, Anträge, Fragen, Mitteilungen und offene Punkte.

Lokalen SQLite-Suchindex prüfen:

```powershell
python -m graz_protocols.cli search "barrierefreie Haltestelle Waltendorf" --sqlite out\eintraege_digra_sync.sqlite --limit 10
```

Der Befehl nutzt nur die lokale SQLite-Datei, fragt den Chunk-Index ab und zeigt Trefferfelder, Score, Kontext und Quellenlink. Er ist als testbarer Unterbau für die spätere Antwortlogik gedacht; der Viewer-Start-Tab bleibt vorerst kompatibel.

Suchqualität gegen den bereinigten Goldstandard messen:

```powershell
python -m graz_protocols.cli eval-search --sqlite out\eintraege_digra_sync.sqlite --goldset tests\fixtures\search_goldstandard.json --limit 10 --output out\search_eval.json
```

Der Goldstandard in `tests\fixtures\search_goldstandard.json` enthält synthetische Fälle. Für reale Qualitätsläufe lokale `record_id`s aus der eigenen SQLite-/JSONL-Ausgabe übernehmen, aber keine Rohprotokolle oder vollständigen Quellentexte in die Fixture kopieren.
Orte werden als klickbare Kartenelemente gerendert. Der Viewer nutzt Leaflet/OpenStreetMap und geocodiert Ortsnamen bei Bedarf online über Nominatim; Geocoding-Ergebnisse werden im Browser-LocalStorage gecacht.

Der Reiter `Service & Ämter` nutzt `graz_protocols/civic_services.py` als kleine kuratierte Orientierungsliste für bürgerrelevante Ämter und Servicepunkte. Die Einträge enthalten nur kurze faktische Hinweise, Koordinaten, Kategorien und offizielle Quellenlinks. Stadt-Graz-Webseiten ohne klare OGD-Lizenz werden nicht als Rohdaten ins Repository übernommen; Öffnungszeiten, Termine, Formulare und Detailzuständigkeiten bleiben über `graz.at/termine`, Telefonbuch und Amtsseiten zu prüfen.
Der Jahresfilter wirkt auf Tabelle, Themen und Karte gemeinsam.
DIGRA-URLs werden als externe Links mit `target="_blank"` gerendert.

## Online-Veröffentlichung

`.github/workflows/pages.yml` baut die öffentliche statische Seite automatisch:

- manuell per `workflow_dispatch`
- täglich um 03:17 UTC
- bei Änderungen an Workflow, `graz_protocols/**` oder `requirements.txt` auf `master`

Der Build schreibt Arbeitsdaten nur in `public_work/` im GitHub-Runner und veröffentlicht danach ausschließlich `public/` als GitHub-Pages-Artefakt.
Die erzeugte Seite ist eine statische HTML-Datei; es gibt keinen produktiven Python-Server und keine laufenden Kosten.
Vor dem ersten produktiven Lauf muss im Repository unter `Settings -> Pages` die Quelle `GitHub Actions` gesetzt sein.
Der Viewer setzt `noindex,nofollow,noarchive`. Das reduziert Suchmaschinen-Auffindbarkeit, ist aber kein Zugriffsschutz.

## Statisches Amts-MVP

Vorerst bleibt das Projekt eine statisch erzeugte HTML-Anwendung. Die Trennung zwischen Bürgeransicht und Amtsansicht ist deshalb eine UI- und Datenfluss-Trennung, kein produktiver Zugriffsschutz.

Bürgeransicht:

- Suche, Quellen, DIGRA-/Archivlinks, Karte, Zeitstrahlen und Export der sichtbaren Gemeinderatseinträge
- öffentliche Baustellen-/Veranstaltungskarte aus offiziellen Stadt-Graz-Quellen
- lokal freigegebene Baustellen-/Veranstaltungsentwürfe
- JSON-, CSV-, RSS- und ICS-Feed ohne rohe Protokolltexte
- browser-lokale Abos nach Straße, Bezirk oder Zeitraum und lokaler Feedbackexport ohne personenbezogene Veröffentlichung

Amtsansicht:

- lokaler Passwortdialog nur als Bedienhürde für denselben Browser
- mehrere Baustellen-/Veranstaltungsentwürfe in `localStorage`
- Felder: Ort, Art, Start, Ende, Auswirkung, betroffene Richtung/Spur, Umleitung/Rettungswege, Beschreibung, Koordinaten, Konfliktbewertung, Quellen
- Statuswerte: `draft`, `approved`
- Aktionen: speichern, bearbeiten, freigeben, zurückziehen, löschen
- Auditlog in `localStorage` mit Zeitpunkt, Aktion, Entwurfs-ID, Titel und Status
- Bürger-Abos und Feedback sind im statischen MVP ebenfalls nur `localStorage`-Daten und müssen vor produktiver Veröffentlichung serverseitig geprüft werden.

Späteres Backend-Datenmodell:

- `roadworks`: Ort, Zeitraum, Sperrtyp, Auswirkung, Beschreibung, Koordinaten, Status, Quelle
- `events`: Ort, Zeitraum, erwartete Auswirkung, Veranstalter-/Quellenangaben
- `detours`: Maßnahme, Straßenliste, Rettungswege, ÖV-/Rad-/Fußverkehrshinweise
- `sources`: Name, URL, Lizenz, Datenstand, Importzeitpunkt
- `approvals`: Entwurf, Freigabestatus, freigebende Rolle, Zeitpunkt
- `audit_log`: Benutzer, Rolle, Aktion, vorher/nachher, Zeitpunkt

Produktiv müssen Rollen `public`, `staff` und `admin`, Sitzungen, Passwortspeicherung, Freigaben und Auditlog serverseitig umgesetzt werden. Die statische HTML-Datei darf diese Sicherheitsanforderung nicht als erfüllt ausgeben.

## Alte Fragestunden

Fragestunden-PDFs bleiben lokale Quelldokumente und dürfen nicht committed werden. Für den Import gibt es eine getrennte Strecke:

```powershell
python -m graz_protocols.cli question-pdf data\source\fragestunden --output out\question_hours.jsonl --summary out\question_hours_summary.json --sqlite out\question_hours.sqlite
```

Der Befehl verarbeitet `.pdf` und `.txt`. PDF-Text wird mit `pypdf` extrahiert. Bereinigte TXT-Fixtures dürfen nur kurze künstliche Beispiele enthalten. Der Parser erkennt die Blöcke `Frage`, `Antwort`, `Zusatzfrage` und `Zusatzantwort` und speichert sie zusätzlich zu einem kurzen `source_snippet` im Feld `question_parts`.

DIGRA-Auditbericht bauen:

```powershell
python -m graz_protocols.cli audit --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --output out\digra_audit.md
```

Der Bericht ist lokale erzeugte Ausgabe. Er listet Fallbacks, fehlende Ergebnisse und niedrige DIGRA-Trefferwerte, damit die Zuordnung gezielt verbessert werden kann.

Themenkandidaten bauen:

```powershell
python -m graz_protocols.cli topics --records out\agenda_items_digra.jsonl --output out\topic_candidates.json --city-news
```

Optionale KI-Überschriften für Topics:

```powershell
python -m graz_protocols.cli topics --records out\agenda_items_digra.jsonl --output out\topic_candidates.json --city-news --ai-headings --ai-model qwen2.5:7b-instruct --ai-limit 50
```

Standard ist lokales Ollama auf `http://localhost:11434`. Wenn das Modell lokal anders heißt, den Namen aus `ollama list` als `--ai-model` verwenden. Ohne `--ai-headings` bleibt die rein lokale regelbasierte Überschriftenerzeugung aktiv. OpenAI ist nur explizit über `--ai-provider openai` und `OPENAI_API_KEY` aktivierbar.

Einzeldokument-Zusammenfassungen erzeugen:

```powershell
python -m graz_protocols.cli summaries --records out\agenda_items_digra.jsonl --output out\agenda_items_digra_ai.jsonl
```

Der Standardprovider ist `local`. Er erzeugt fachliche Zusammenfassungen, einfache Sprache, Kernpunkte, offene Punkte und Quellenlimits ohne externen KI-Dienst und ohne API-Kosten. Ollama bleibt optional über `--ai-provider ollama`; OpenAI ist technisch möglich, aber nicht Teil des kostenlosen Standardbetriebs.

## Dokumentation aktuell halten

Wenn sich das Projekt ändert, die passende Markdown-Datei im selben Arbeitsdurchlauf aktualisieren:

- `AGENTS.md` für Agentenregeln und Arbeitsbeschränkungen
- `DATA_POLICY.md` für Datenregeln
- `PROJECT_NOTES.md` für Architektur, Richtung und Projektstand
- `README.md` für Zweck und Bedienung
- `DEVELOPMENT.md` für Befehle und lokalen Ablauf
