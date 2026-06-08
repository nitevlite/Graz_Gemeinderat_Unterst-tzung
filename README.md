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
Optional erzeugt er zusätzlich eine lokale SQLite-Datenbank mit der Tabelle `eintraege`. Die SQLite-Datei bleibt wie JSONL und HTML ignoriert.

Parser mit DIGRA-Abgleich ausführen:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items_digra.jsonl --summary out\summary_digra.json --sqlite out\eintraege_digra.sqlite --digra
```

Dieser Modus nutzt das vorhandene Tool unter `E:\01_StadtGrazProtokolle\Digra_Export_Tool\app`, lädt DIGRA-Sitzungen und DIGRA-Dokumentseiten, extrahiert offizielle Ergebnisse nur aus dem Block `Beschlussvermerk` und cached die geladenen DIGRA-Daten lokal in `out\digra_cache.json`.
DIGRA-Ergebnisse haben Vorrang. Wenn DIGRA keinen Beschlussvermerk liefert oder kein Ergebnis zugeordnet werden kann, bleibt das normalisierte Protokoll-Ergebnis als Fallback erhalten und die Ergebnisquelle steht auf `Protokoll`.
Mit `--digra-results-only` kann man zusätzlich auditieren, wo DIGRA wirklich kein Ergebnis liefert.

Interne Eintragstypen:

- `agenda_item`
- `urgent_motion`
- `written_question`
- `written_motion`

Die erzeugte Ausgabe unter `out/` ist ignoriert und darf nicht committed werden.

Lokale Doppelklick-HTML-Ansicht bauen:

```powershell
python -m graz_protocols.viewer --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --output viewer.html
```

Danach `viewer.html` im Browser öffnen. Die Datei ist erzeugte lokale Ausgabe und wird von Git ignoriert.

Der Viewer zeigt deutsche Typen, deutsche Statuswerte und einheitliche `Ergebnisse`, zum Beispiel `Antrag: mehrheitlich angenommen` plus Parteilisten wie `Dagegen: KFG, NEOS, FPÖ`.
Ein Klick auf eine Tabellenzeile öffnet eine Detailansicht mit Titel, Ergebnis, Ergebnisquelle, DIGRA-Einlagezahl, DIGRA-Link, Geschäftszahlen, Beträgen, Orten und Quelldatei.
Originalformulierungen aus dem Protokoll werden im Viewer nicht angezeigt und bleiben nur in der ignorierten lokalen JSONL-Ausgabe als Rohspur erhalten.

## GitHub-Backlog

Repository:

```text
https://github.com/nitevlite/graz-council-protocol-explorer
```

Die nächsten Arbeitspakete liegen in GitHub Issues:

- Abschnittserkennung und Trennung vom Inhaltsverzeichnis
- Schriftliche Anfragen und Anträge ohne `Stk.`-Nummer
- Strukturierte Abstimmungsergebnisse und Parteistimmen
- Stabiles JSONL-Schema und Validierung
- DIGRA-Anbindung
- Ortserkennung und Vorbereitung für Karten
- Bessere lokale HTML-Ansicht
- Qualitätsprüfung mit Goldset
- Git- und Datensicherheitsprüfungen
- Themenverläufe über Sitzungen
- Roadmap- und Produktdokumentation
