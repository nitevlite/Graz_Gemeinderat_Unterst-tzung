# Grazer Gemeinderatsprotokoll-Explorer

Arbeitsprojekt, um Gemeinderatsprotokolle der Stadt Graz in ein durchsuchbares, strukturiertes und quellnahes Entscheidungsregister zu überführen.

## Ziel

Das System soll später Fragen beantworten wie:

- Was wurde genehmigt?
- Wo betrifft die Entscheidung ein Grundstück, eine Straße, einen Platz oder einen Betrag?
- Welche Tagesordnungspunkte, Geschäftszahlen, Personen, Parteien, Beträge und Daten hängen daran?
- Wo steht die ursprüngliche Quelle?
- Wie entwickelt sich ein Thema über mehrere Sitzungen?

## Datenregeln

Protokolldateien sind lokales Arbeitsmaterial und dürfen nicht committed oder gepusht werden.

Ins Repository dürfen:

- Parser-Code
- Extraktionsregeln
- Tests
- Dokumentation
- bereinigte Mini-Testdaten

Nicht ins Repository dürfen:

- vollständige DOCX-/PDF-Protokolle
- heruntergeladene Gemeinderatsdokumente
- rohe DIGRA-Exporte
- lokale Archivkopien
- unbereinigter extrahierter Volltext

## Aktuelle Quellen

- Lokale Archivdateien unter `E:\01_StadtGrazProtokolle\Archiv\...`
- DIGRA Public: `https://digra.graz.at/timetable`
- Archivseiten der Stadt Graz: `https://www.graz.at/cms/beitrag/10142612/7768104`
- Bestehendes Hilfsprojekt: `E:\01_StadtGrazProtokolle\Digra_Export_Tool`
- Lokale Straßennamenliste: `E:\.T_apps\Open-Source\Straßennamen_Graz.xlsx`

## Erstes MVP

Das MVP extrahiert strukturierte Einträge aus lokalen DOCX-Dateien:

- Sitzungsdatum
- Abschnitt
- Stücknummer
- Geschäftszahl
- Titel
- Status
- einheitlich formuliertes Ergebnis
- strukturierte Abstimmungsdetails
- Geldbeträge
- Orts- und Grundstückshinweise
- kurzer Quellenausschnitt für lokale Nachvollziehbarkeit

Die Ausgabe bleibt lokal in ignorierten Dateien, nicht im Git.

## Bedienung

Abhängigkeiten installieren:

```powershell
python -m pip install -r requirements.txt
```

Lokalen Parser gegen die ignorierten DOCX-Arbeitskopien ausführen:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items.jsonl --summary out\summary.json --sqlite out\eintraege.sqlite
```

Der Parser schreibt JSONL-Einträge mit Sitzungsdatum, Stücknummer, Geschäftszahlen, Titel, Status, einheitlichem Ergebnistext, strukturierten Abstimmungsdetails, Beträgen, Ortshinweisen und kurzem Quellenausschnitt.
Er nutzt DOCX-Absatzformatvorlagen, um echte Überschriften von Inhaltsverzeichnis-Einträgen zu unterscheiden.
Optional erzeugt er zusätzlich eine lokale SQLite-Datenbank mit der Tabelle `eintraege`, normalisierten Tabellen für Suche/Verlauf und einer FTS5-Volltexttabelle. Die SQLite-Datei bleibt wie JSONL und HTML ignoriert.
Die SQLite-Ausgabe enthält zusätzlich einen produktionsnäheren lokalen Suchindex mit stabilen Dokument- und Chunk-IDs (`search_documents`, `search_chunks`, `search_fts`). Dadurch können Titel, Ergebnisse, Geschäftszahlen, Orte, Beträge, Einbringer, Abstimmungen, Fragestundenteile und kurze lokale Quellenausschnitte testbar durchsucht werden.

Parser mit DIGRA-Abgleich ausführen:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items_digra.jsonl --summary out\summary_digra.json --sqlite out\eintraege_digra.sqlite --digra --street-names .\Straßennamen_Graz.xlsx --city-archive-links
```

Dieser Modus nutzt das vorhandene Tool unter `E:\01_StadtGrazProtokolle\Digra_Export_Tool\app`, lädt DIGRA-Sitzungen und DIGRA-Dokumentseiten, extrahiert offizielle Ergebnisse nur aus dem Block `Beschlussvermerk` und cached die geladenen DIGRA-Daten lokal in `out\digra_cache.json`.
DIGRA-Ergebnisse haben Vorrang. Wenn DIGRA keinen Beschlussvermerk liefert oder kein Ergebnis zugeordnet werden kann, bleibt das normalisierte Protokoll-Ergebnis als Fallback erhalten und die Ergebnisquelle steht auf `Protokoll`.
Links zu DIGRA werden konservativ übernommen: unsichere Treffer werden nicht verlinkt, damit ein fehlender Link eher vorkommt als ein falscher Link.
Mit `--street-names` wird die Ortserkennung gegen die Grazer Straßennamenliste gefiltert. Dadurch werden Füllwörter aus Reden nicht als Orte übernommen.
Mit `--city-archive-links` werden passende Stadt-Graz-Archivlinks als Quellenfallback ergänzt, besonders für Datensätze ohne sicheren DIGRA-Link.
Mit `--digra-results-only` kann man zusätzlich auditieren, wo DIGRA wirklich kein Ergebnis liefert.

DIGRA-Sitzungen direkt aus dem Export-Tool abfragen:

```powershell
python -m graz_protocols.cli digra-list --limit 20
```

Standardimport ohne lokale Protokollkopien aus den letzten DIGRA-Sitzungen erzeugen:

```powershell
python -m graz_protocols.cli digra-sync --limit 30 --output out\agenda_items_digra_sync.jsonl --summary out\summary_digra_sync.json --sqlite out\eintraege_digra_sync.sqlite --city-archive-links
```

Dieser Pfad ist der bevorzugte Open-Source-Betrieb, weil er keine lokalen DOCX-/PDF-Protokollkopien voraussetzt. Er nutzt DIGRA als Hauptquelle, ergänzt optional Stadt-Graz-Archivlinks und schreibt ausschließlich ignorierte lokale Ausgaben unter `out\`.
Wenn das externe lokale DIGRA-Export-Tool nicht vorhanden ist, nutzt der Importer automatisch den repo-eigenen öffentlichen HTTP-Importer für `https://digra.graz.at/`. Dadurch kann derselbe Pfad auch in GitHub Actions laufen.
Wenn alte Stadt-Graz-Archivquellen im Viewer ebenfalls sichtbar sein sollen, vorher `city-index` und `city-assets` ausführen und den Sync so starten:

```powershell
python -m graz_protocols.cli digra-sync --limit 30 --output out\agenda_items_digra_sync.jsonl --summary out\summary_digra_sync.json --sqlite out\eintraege_digra_sync.sqlite --city-archive-links --city-archive-assets --city-archive-assets-index out\city_archive_assets.json
```

Diese Archivasset-Records verlinken Protokolldokumente, Protokollseiten und Sitzungsübersichten als `Archivquelle`; die Rohdokumente werden nicht heruntergeladen oder ins Repository übernommen.
Wenn lokal ignorierte Stadt-Graz-DOCX-Protokolle vorhanden sind, können daraus ergänzend die Abschnitte `Mitteilungen` und `Fragestunde` eingebaut werden:

```powershell
python -m graz_protocols.cli digra-sync --limit 30 --output out\agenda_items_digra_sync_plus_city_protocols.jsonl --summary out\summary_digra_sync_plus_city_protocols.json --sqlite out\eintraege_digra_sync_plus_city_protocols.sqlite --city-archive-links --city-archive-assets --city-archive-assets-index out\city_archive_assets.json --city-protocols-dir graz_protokolle_arbeitskopie --street-names .\Straßennamen_Graz.xlsx
```

Der Standard für `--city-protocol-types` ist `communication,question_hour`; damit werden keine vollständigen Rohprotokolle übernommen, sondern nur die strukturierten ergänzenden Viewer-Einträge in ignorierte lokale Ausgaben geschrieben. Mit `--street-names` werden Orte aus den lokalen Stadt-Graz-Protokollen erkannt und in passende DIGRA-Einträge übernommen. Alte Jahre, für die nur Archivlinks und keine geparsten Dokumenttexte vorliegen, haben weiterhin keine extrahierten Orte.

Alte Fragestunden-PDFs aus dem Stadt-Graz-Archiv können lokal in `out\city_archive_protocol_docs\` als Arbeitskopie liegen und mit der vorhandenen PDF-Strecke strukturiert werden:

```powershell
python -m graz_protocols.cli question-pdf out\city_archive_protocol_docs --output out\question_hours_city_archive.jsonl --summary out\question_hours_city_archive_summary.json --sqlite out\question_hours_city_archive.sqlite
```

Die daraus gebaute lokale Viewer-Basis `out\agenda_items_digra_sync_plus_city_protocols_and_archive_questions.jsonl` enthält zusätzlich geparste alte Fragestunden; der Doppelklick-Starter bevorzugt diese Datei, wenn sie vorhanden ist.

Eine einzelne DIGRA-Sitzung ohne DOCX-Protokoll als strukturierte Ausgabe exportieren:

```powershell
python -m graz_protocols.cli digra-export --date 2026-04-23 --output out\digra_2026-04-23.jsonl --summary out\digra_2026-04-23_summary.json --sqlite out\digra_2026-04-23.sqlite
```

Neue DIGRA-Sitzungen automatisch in die lokale Viewer-Datenbasis übernehmen:

```powershell
python -m graz_protocols.cli digra-update --base-records out\agenda_items_digra_ai.jsonl --base-summary out\summary_digra.json --output out\agenda_items_digra_ai_plus_latest.jsonl --summary out\summary_digra_plus_latest.json
```

Der Doppelklick-Starter `Start Viewer mit Ollama.cmd` führt diesen Update-Schritt nicht mehr blockierend beim Öffnen aus. Er baut den Viewer aus der vorhandenen lokalen Datenbasis und startet zusätzlich einen minimierten DIGRA-Hintergrunddienst. Dieser prüft periodisch neue Sitzungen, baut `out\topic_candidates.json` und `viewer.html` neu und schreibt Statusmeldungen nach `out\digra_background.log`.

Interne Eintragstypen:

- `agenda_item`
- `archive_source`
- `communication`
- `urgent_motion`
- `written_question`
- `written_motion`
- `question_hour`

Die erzeugte Ausgabe unter `out/` ist ignoriert und darf nicht committed werden.

Lokale Doppelklick-HTML-Ansicht bauen:

```powershell
python -m graz_protocols.viewer --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --topics out\topic_candidates.json --output viewer.html
```

Danach `viewer.html` im Browser öffnen. Die Datei ist erzeugte lokale Ausgabe und wird von Git ignoriert.

Den Viewer kann man lokal per Doppelklick starten:

```text
Start Viewer mit Ollama.cmd
```

Diese Datei kann im Explorer per Doppelklick gestartet werden.
Sie startet einen lokalen Viewer-Server auf `http://127.0.0.1:8765/` und öffnet danach `viewer.html`.
Zusätzlich startet sie bei Bedarf den DIGRA-Hintergrunddienst; die laufende Abfrage blockiert den Viewer-Start nicht.
Der Start-Tab beantwortet Fragen kostenlos aus den lokalen Quellen. Er trennt Beschlüsse, Anträge, Fragen, Mitteilungen und offene Punkte und braucht dafür kein Ollama-Modell.

Der Viewer zeigt deutsche Typen, deutsche Statuswerte und einheitliche `Ergebnisse`, zum Beispiel `Antrag: mehrheitlich angenommen` plus Parteilisten wie `Dagegen: KFG, NEOS, FPÖ`.
Ein Klick auf eine Tabellenzeile öffnet eine Detailansicht mit Titel, Ergebnis, Ergebnisquelle, DIGRA-Einlagezahl, DIGRA-Link, Geschäftszahlen, Einbringer, Beträgen, Orten und Quelldatei.
Die aktuelle Trefferliste kann im Viewer als CSV exportiert werden. Filter gibt es unter anderem für Jahr, Datum, Typ, Status, Thema, Ergebnisquelle und Beträge. Der frühere Datei-/Abschnittsfilter ist entfernt, weil der Standardbetrieb auf DIGRA- und Stadt-Graz-Quellen statt lokale Arbeitsdateien ausgerichtet ist.
Die Oberfläche ist als lokale App mit linker Navigation, KPI-Karten, Filterpanel, Detailansicht, Graz-Karte, Themenverläufen und Ergebnistabelle aufgebaut.
Erkannte Orte sind anklickbar: der Viewer springt auf die Karte, lädt den Ort online über OpenStreetMap/Nominatim und zeigt die zugehörigen Einträge samt Typ als Marker-Popup. Beim Öffnen eines Eintrags werden die dazugehörigen Orte grün hervorgehoben. Der Jahresfilter aktualisiert Tabelle, Themen und Karte gemeinsam. DIGRA-Links öffnen direkt die jeweilige DIGRA-Dokumentseite; Stadt-Graz-Links öffnen die Archivquelle.
Originalformulierungen aus dem Protokoll werden im Viewer nicht angezeigt und bleiben nur in der ignorierten lokalen JSONL-Ausgabe als Rohspur erhalten.

Der Viewer enthält zusätzliche Mobilitätsreiter:

- `Baustellen`: öffentliche Karte und Liste mit offiziellen Baustelleninfos aus der Stadt-Graz-Seite und lokal freigegebenen Entwürfen. Die Seite wird nur lokal nach `out\baustellen_graz.html` gecacht; dieser Cache bleibt ignoriert und wird nicht committed.
- `Amtsansicht`: browser-lokale Planung für Baustellen und Veranstaltungen. Mehrere Entwürfe können gespeichert, wieder geladen, freigegeben, zurückgezogen oder gelöscht werden. Änderungen werden lokal als Auditlog in `localStorage` protokolliert. Das ist bewusst nur eine statische MVP-Variante; produktive Rollen `public`, `staff`, `admin`, Passwörter, Sitzungen und serverseitige Freigaben brauchen später ein Backend.
- `Tiefgaragen`: Karte für Parkgaragen aus dem OGD-Datensatz `Parkgaragen Graz` (`CC BY 4.0`, Quelle: `Stadt Graz - data.graz.gv.at`). Für die lokale Ansicht gibt es Koordinaten-Fallbacks, damit Marker auch ohne Browser-Geocoding erscheinen. Die Live-Verfügbarkeit bleibt `unbekannt`, solange keine offene Live-API mit klarer Weiterverwendungsfreigabe vorliegt. `Parken.at` wird nur als externer Prüflink angezeigt; Verfügbarkeiten, Preise und Standortdaten werden nicht übernommen.
- `Service & Ämter`: kuratierte Karte mit bürgerrelevanten Stadt-Graz-Ämtern und Servicepunkten. Der Datensatz in `graz_protocols/civic_services.py` enthält nur kurze faktische Orientierungshinweise, Koordinaten, Kategorien und Quellenlinks. Die offiziellen Stadt-Graz-Seiten werden nicht als Rohdaten ins Repository kopiert; aktuelle Öffnungszeiten, Termine, Formulare und Detailzuständigkeiten sind über `graz.at/termine`, das Stadt-Graz-Telefonbuch und die verlinkten Amtsseiten zu prüfen.

Die Baustellenprüfung läuft ohne externe KI: regelbasierte Konflikte, Umleitungshinweise und Quellenlisten funktionieren direkt im Browser. Antworten im Start-Tab werden ebenfalls lokal aus den geladenen Quellen aufgebaut und bleiben quellenpflichtig.

Der Export-Reiter erzeugt zusätzlich zur Treffer-CSV statische öffentliche Datenabgaben:

- `graz-baustellen-feed.json`: JSON-Feed für offizielle Baustelleninfos und freigegebene lokale Entwürfe mit Quellen-/Lizenzhinweis und Aktualisierungszeitpunkt.
- `graz-baustellen-feed.csv`: CSV-Ausgabe derselben freigegebenen Baustellen-/Veranstaltungsdaten.
- `graz-baustellen.ics`: einfacher Kalenderexport für Einträge mit Startdatum.
- `graz-baustellen-feed.rss`: RSS-Feed für neue oder geänderte freigegebene Baustellen-/Veranstaltungsdaten.
- `graz-baustellen-abos.json`: browser-lokal gepflegte Abos für Straße, Bezirk oder Zeitraum samt passenden öffentlichen Einträgen.
- `graz-baustellen-feedback.json`: browser-lokaler Feedbackexport ohne personenbezogene Veröffentlichung.
- `graz-baustellen-auditlog.json`: lokaler Auditlog der Amtsansicht, nur für interne Prüfung.

DIGRA-Auditbericht bauen:

```powershell
python -m graz_protocols.cli audit --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --output out\digra_audit.md
```

Der Bericht zeigt DIGRA-Ergebnisse, Protokoll-Fallbacks, fehlende Ergebnisse und niedrige DIGRA-Trefferwerte. Er bleibt als erzeugte lokale Ausgabe unter `out/` ignoriert.

Lokalen SQLite-Suchindex abfragen:

```powershell
python -m graz_protocols.cli search "barrierefreie Haltestelle Waltendorf" --sqlite out\eintraege_digra_sync.sqlite --limit 10
```

Die Suche ist read-only und gibt Treffer mit Record-ID, Ergebnis, Trefferfeldern, Score, Kontext und Quellenlink aus. Sie nutzt den lokalen Chunk-Index und braucht keine externe KI.

Suchqualität gegen den bereinigten Goldstandard messen:

```powershell
python -m graz_protocols.cli eval-search --sqlite out\eintraege_digra_sync.sqlite --goldset tests\fixtures\search_goldstandard.json --limit 10 --output out\search_eval.json
```

Der Goldstandard enthält synthetische, bereinigte Fragen mit erwarteten `record_id`s und keine Rohprotokolle. Für echte lokale Daten müssen die erwarteten IDs auf vorhandene lokale Records angepasst oder zusätzliche bereinigte Fälle ergänzt werden.

## Online-Betrieb

Der wartungsarme Online-Standard ist GitHub Pages mit täglichem Neuaufbau über `.github/workflows/pages.yml`.
Der Workflow lädt die letzten DIGRA-Sitzungen aus der öffentlichen Webseite, erzeugt lokale Zusammenfassungen, baut Themen und veröffentlicht nur die statische `index.html` in den Branch `gh-pages`.
Temporäre JSONL-, Summary- und SQLite-Dateien bleiben im GitHub-Runner und werden nicht in den Website-Branch kopiert.

Einmalig nötig:

1. In GitHub unter `Settings -> Pages` als Quelle `Deploy from a branch` auswählen.
2. Branch `gh-pages` und Ordner `/ (root)` auswählen.
3. Änderungen nach `master` pushen.
4. Den Workflow `publish public viewer` einmal manuell starten oder den täglichen Lauf abwarten.
5. Die veröffentlichte URL in den GitHub-Pages-Einstellungen prüfen.

Der Betrieb braucht keine Cloud-KI, keine API-Schlüssel und keinen dauerhaft laufenden Server.
Manuell eingegriffen werden muss nur, wenn `digra.graz.at` nicht erreichbar ist oder die DIGRA-HTML-Struktur so geändert wird, dass der öffentliche Importer angepasst werden muss.
Der erzeugte Viewer enthält `noindex,nofollow,noarchive`, damit Suchmaschinen die Seite nicht aktiv indexieren sollen. Das ersetzt keinen Zugriffsschutz: Wer die GitHub-Pages-URL kennt, kann die Seite öffnen.

Stadt-Graz-Archivseiten für ältere Sitzungen indexieren:

```powershell
python -m graz_protocols.cli city-index --output out\city_archive_index.json
```

Der Index sammelt ältere Sitzungsseiten aus dem Stadt-Graz-Archiv ab 2004. Wenn `www.graz.at` lokal gerade nicht erreichbar ist, werden die Ladefehler im JSON unter `errors` dokumentiert.
Der aktuelle lokale Index aus `https://www.graz.at/cms/beitrag/10142612/7768104` enthält 261 Sitzungsseiten für 2004 bis 2025 und bleibt als `out\city_archive_index.json` ignoriertes Arbeitsmaterial.
Für alte Protokolle gibt es zusätzlich einen Asset-Index (`city-assets`), der Dokument- und Übersichtslinks aus den Sitzungsseiten sammelt:

```powershell
python -m graz_protocols.cli city-assets --input-index out\city_archive_index.json --output out\city_archive_assets.json
```

Der vollständige Download/Import bleibt lokales Arbeitsmaterial und darf nicht committed werden.
Der Asset-Bericht enthält Jahre und Dokumenttypen, damit sichtbar ist, welche Archivbereiche und welche Linkarten verarbeitet wurden.

Alte Fragestunden-PDFs oder bereinigte Textauszüge strukturieren:

```powershell
python -m graz_protocols.cli question-pdf data\source\fragestunden --output out\question_hours.jsonl --summary out\question_hours_summary.json --sqlite out\question_hours.sqlite
```

Der Import akzeptiert `.pdf` und `.txt`. PDF-Text wird mit `pypdf` extrahiert, TXT-Dateien sind für bereinigte Test-/Arbeitsauszüge gedacht. Er erkennt `Frage`, `Antwort`, `Zusatzfrage` und `Zusatzantwort` getrennt und speichert diese Struktur in `question_parts`. Echte PDFs und daraus erzeugte Roh-/Zwischendaten bleiben lokale Arbeitsdaten in ignorierten Ordnern.

Themenkandidaten über mehrere Sitzungen erzeugen:

```powershell
python -m graz_protocols.cli topics --records out\agenda_items_digra.jsonl --output out\topic_candidates.json --city-news
```

Die Kandidaten enthalten Confidence, Begründung, verknüpfte Einträge und optional aktuelle Stadt-Graz-RSS-Hinweise. Sie können im Viewer angezeigt und später manuell bestätigt werden.
Optional kann die lokale Ollama-KI bessere Themenüberschriften vorschlagen. Standard ist `qwen2.5:7b-instruct` auf `http://localhost:11434`:

```powershell
python -m graz_protocols.cli topics --records out\agenda_items_digra.jsonl --output out\topic_candidates.json --city-news --ai-headings --ai-model qwen2.5:7b-instruct --ai-limit 50
```

Falls das Modell in Ollama anders heißt, den Namen aus `ollama list` bei `--ai-model` einsetzen. OpenAI bleibt explizit möglich über `--ai-provider openai` und `OPENAI_API_KEY`.
Die KI-Überschrift wird nachvollziehbar mit `rule_label`, `ai_label`, `ai_reason`, `ai_confidence` und `label_source` gespeichert.

Für einzelne Stücke können zusätzlich kostenlose lokale Zusammenfassungen, einfache Sprache, Kernpunkte und offene Punkte erzeugt werden. Der Standard nutzt keinen externen KI-Dienst und verursacht keine API-Kosten:

```powershell
python -m graz_protocols.cli summaries --records out\agenda_items_digra.jsonl --output out\agenda_items_digra_ai.jsonl
python -m graz_protocols.viewer --records out\agenda_items_digra_ai.jsonl --summary out\summary_digra.json --topics out\topic_candidates.json --output viewer.html
```

Der Zusammenfassungslauf schreibt fortlaufend in die Ausgabedatei und kann neu gestartet werden. Für kurze Tests kann `--limit 10` verwendet werden. Optional kann bewusst `--ai-provider ollama` für ein lokal betriebenes Modell genutzt werden; OpenAI ist technisch explizit möglich, aber nicht Teil des kostenlosen Standardbetriebs.
Der Viewer lädt beim Erzeugen zusätzlich Parkgaragen-OGD und die öffentliche Baustellenseite in ignorierte Caches unter `out\`. Wenn die Netzverbindung ausfällt, werden vorhandene Caches weiterverwendet.

## GitHub-Backlog

Repository:

```text
https://github.com/nitevlite/graz-council-protocol-explorer
```

Die bisherigen MVP-Arbeitspakete sind als GitHub Issues dokumentiert. Umgesetzt sind unter anderem Abschnittserkennung, schriftliche Anfragen/Anträge, strukturierte Abstimmungen, JSONL-Schema, DIGRA-Anbindung, Ortserkennung mit Straßennamenabgleich, lokale HTML-Ansicht, Goldset-Tests, Git-Sicherheitscheck, Themenkandidaten und Roadmap-Dokumentation.
