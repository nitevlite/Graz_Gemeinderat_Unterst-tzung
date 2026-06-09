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

Eine einzelne DIGRA-Sitzung ohne DOCX-Protokoll als strukturierte Ausgabe exportieren:

```powershell
python -m graz_protocols.cli digra-export --date 2026-04-23 --output out\digra_2026-04-23.jsonl --summary out\digra_2026-04-23_summary.json --sqlite out\digra_2026-04-23.sqlite
```

Interne Eintragstypen:

- `agenda_item`
- `urgent_motion`
- `written_question`
- `written_motion`

Die erzeugte Ausgabe unter `out/` ist ignoriert und darf nicht committed werden.

Lokale Doppelklick-HTML-Ansicht bauen:

```powershell
python -m graz_protocols.viewer --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --topics out\topic_candidates.json --output viewer.html
```

Danach `viewer.html` im Browser öffnen. Die Datei ist erzeugte lokale Ausgabe und wird von Git ignoriert.

Der Viewer zeigt deutsche Typen, deutsche Statuswerte und einheitliche `Ergebnisse`, zum Beispiel `Antrag: mehrheitlich angenommen` plus Parteilisten wie `Dagegen: KFG, NEOS, FPÖ`.
Ein Klick auf eine Tabellenzeile öffnet eine Detailansicht mit Titel, Ergebnis, Ergebnisquelle, DIGRA-Einlagezahl, DIGRA-Link, Geschäftszahlen, Einbringer, Beträgen, Orten und Quelldatei.
Die aktuelle Trefferliste kann im Viewer als CSV exportiert werden. Filter gibt es unter anderem für Datum, Typ, Status, Ergebnisquelle, Beträge, Quelldatei und Abschnitt.
Die Oberfläche ist als lokale App mit linker Navigation, KPI-Karten, Filterpanel, Detailansicht, Graz-Karte, Themenverläufen und Ergebnistabelle aufgebaut.
Erkannte Orte sind anklickbar: der Viewer springt auf die Karte, lädt den Ort online über OpenStreetMap/Nominatim und zeigt die zugehörigen Einträge samt Typ als Marker-Popup. Beim Öffnen eines Eintrags werden die dazugehörigen Orte grün hervorgehoben. Der Jahresfilter aktualisiert Tabelle, Themen und Karte gemeinsam. DIGRA-Links öffnen direkt die jeweilige DIGRA-Dokumentseite; Stadt-Graz-Links öffnen die Archivquelle.
Originalformulierungen aus dem Protokoll werden im Viewer nicht angezeigt und bleiben nur in der ignorierten lokalen JSONL-Ausgabe als Rohspur erhalten.

Der Viewer enthält zusätzliche Mobilitätsreiter:

- `Baustellen`: Planungsformular für eigene Baustellen mit Ort, Zeitraum, Sperrtyp und Konfliktprüfung gegen erkannte Gemeinderats-Orte. Offizielle Baustelleninformationen werden verlinkt, aber nicht als Geoportal-Datensatz eingebettet, weil dafür keine OGD-Freigabe gefunden wurde.
- `Tiefgaragen`: Karte für Parkgaragen aus dem OGD-Datensatz `Parkgaragen Graz` (`CC BY 4.0`, Quelle: `Stadt Graz - data.graz.gv.at`). Die Live-Verfügbarkeit bleibt `unbekannt`, solange keine offene Live-API mit klarer Weiterverwendungsfreigabe vorliegt.

DIGRA-Auditbericht bauen:

```powershell
python -m graz_protocols.cli audit --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --output out\digra_audit.md
```

Der Bericht zeigt DIGRA-Ergebnisse, Protokoll-Fallbacks, fehlende Ergebnisse und niedrige DIGRA-Trefferwerte. Er bleibt als erzeugte lokale Ausgabe unter `out/` ignoriert.

Stadt-Graz-Archivseiten für ältere Sitzungen indexieren:

```powershell
python -m graz_protocols.cli city-index --output out\city_archive_index.json
```

Der Index sammelt ältere Sitzungsseiten aus dem Stadt-Graz-Archiv ab 2004. Wenn `www.graz.at` lokal gerade nicht erreichbar ist, werden die Ladefehler im JSON unter `errors` dokumentiert.

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

Für einzelne Stücke können zusätzlich lokale KI-Zusammenfassungen und Texte in einfacher Sprache erzeugt werden:

```powershell
python -m graz_protocols.cli summaries --records out\agenda_items_digra.jsonl --output out\agenda_items_digra_ai.jsonl --ai-model qwen2.5:7b-instruct
python -m graz_protocols.viewer --records out\agenda_items_digra_ai.jsonl --summary out\summary_digra.json --topics out\topic_candidates.json --output viewer.html
```

Der Zusammenfassungslauf schreibt fortlaufend in die Ausgabedatei und kann neu gestartet werden. Für kurze Tests kann `--limit 10` verwendet werden.

## GitHub-Backlog

Repository:

```text
https://github.com/nitevlite/graz-council-protocol-explorer
```

Die bisherigen MVP-Arbeitspakete sind als GitHub Issues dokumentiert. Umgesetzt sind unter anderem Abschnittserkennung, schriftliche Anfragen/Anträge, strukturierte Abstimmungen, JSONL-Schema, DIGRA-Anbindung, Ortserkennung mit Straßennamenabgleich, lokale HTML-Ansicht, Goldset-Tests, Git-Sicherheitscheck, Themenkandidaten und Roadmap-Dokumentation.
