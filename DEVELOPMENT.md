# Entwicklung

## Git-Regeln

Vor dem Staging:

```powershell
git status --short
```

Nur Quellcode und Dokumentation stagen. Niemals Protokolldateien oder erzeugte rohe Extraktionsausgaben stagen.

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
Mit `--sqlite` erzeugt er zusätzlich eine lokale SQLite-Datenbank mit deutscher Tabelle `eintraege`.

DIGRA-Abgleich ausführen:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items_digra.jsonl --summary out\summary_digra.json --sqlite out\eintraege_digra.sqlite --digra
```

Dieser Lauf nutzt `E:\01_StadtGrazProtokolle\Digra_Export_Tool\app`.
Die DIGRA-Daten werden in `out\digra_cache.json` gecacht und bleiben ignoriertes lokales Arbeitsmaterial.
DIGRA-Beschlussvermerke haben Vorrang; wo DIGRA wirklich kein Ergebnis liefert, wird das normalisierte Protokoll-Ergebnis als Fallback verwendet.
`--digra-results-only` ist nur für Audits gedacht und markiert fehlende DIGRA-Beschlussvermerke als `DIGRA-Ergebnis fehlt`.

Lokale HTML-Ansicht bauen:

```powershell
python -m graz_protocols.viewer --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --output viewer.html
```

Der erzeugte Viewer entfernt Rohformulierungen, Quellenausschnitte und interne englische Typ-/Statuscodes aus den eingebetteten Einträgen.
Ein Klick auf eine Tabellenzeile zeigt eine deutsche Detailansicht für den Eintrag, inklusive Ergebnisquelle und DIGRA-Link.

DIGRA-Auditbericht bauen:

```powershell
python -m graz_protocols.cli audit --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --output out\digra_audit.md
```

Der Bericht ist lokale erzeugte Ausgabe. Er listet Fallbacks, fehlende Ergebnisse und niedrige DIGRA-Trefferwerte, damit die Zuordnung gezielt verbessert werden kann.

## Dokumentation aktuell halten

Wenn sich das Projekt ändert, die passende Markdown-Datei im selben Arbeitsdurchlauf aktualisieren:

- `AGENTS.md` für Agentenregeln und Arbeitsbeschränkungen
- `DATA_POLICY.md` für Datenregeln
- `PROJECT_NOTES.md` für Architektur, Richtung und Projektstand
- `README.md` für Zweck und Bedienung
- `DEVELOPMENT.md` für Befehle und lokalen Ablauf
