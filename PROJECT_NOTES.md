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
- `graz_protocols/cli.py`: Stapelverarbeitung über die Kommandozeile
- `graz_protocols/sqlite_export.py`: lokale SQLite-Ausgabe mit Tabelle `eintraege`
- `graz_protocols/viewer.py`: erzeugte lokale Doppelklick-HTML-Ansicht
- `tests/test_parser.py`: bereinigte Parser-Tests
- `tests/test_digra_import.py`: Test, dass DIGRA-Ergebnisse nur aus dem `Beschlussvermerk` extrahiert werden
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
- Der lokale Viewer kann nach Ergebnisquelle filtern: `DIGRA`, `Protokoll`, `DIGRA fehlt`.
- Rohformulierungen, Quellenausschnitte und interne englische Typ-/Statuscodes bleiben aus dem Viewer draußen.

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
- DIGRA-Einträge geladen: 1675
- lokalen Datensätzen zugeordnet: 951
- Ergebnisse aus DIGRA-Beschlussvermerken übernommen: 412
- Protokoll-Fallbacks, weil DIGRA kein plausibel zuordenbares Ergebnis liefert: 718
- Datensätze ohne DIGRA- oder Protokoll-Ergebnis: 5
- Ausgabe: `out/agenda_items_digra.jsonl`
- SQLite-Ausgabe: `out\eintraege_digra.sqlite`
- Viewer-Ausgabe: `viewer.html`
- Audit-Ausgabe: `out\digra_audit.md`

Erzeugte Ausgabe ist absichtlich ignoriert.

## Nächster Ausbauschritt

Die Extraktionsqualität über die Abschnittserkennung hinaus verbessern:

- DIGRA-Ergebnisse systematisch gegen Parser-Ergebnisse abgleichen
- komplexe Änderungs- und Zusatzanträge besser trennen
- Ortserkennung verbessern und geocoding-taugliche Ortsdatensätze erzeugen
- Zeitachsenabfragen auf der SQLite-Ausgabe aufbauen

## GitHub Issues

Am 2026-06-08 im privaten GitHub-Repository angelegt:

- https://github.com/nitevlite/graz-council-protocol-explorer/issues/1
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/2
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/3
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/4
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/5
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/6
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/7
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/8
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/9
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/10
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/11
- https://github.com/nitevlite/graz-council-protocol-explorer/issues/12
