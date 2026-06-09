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
Mit `--sqlite` erzeugt er zusätzlich eine lokale SQLite-Datenbank mit deutscher Tabelle `eintraege`, normalisierten Tabellen und FTS5-Volltextsuche.

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
python -m graz_protocols.cli digra-export --date 2026-04-23 --output out\digra_2026-04-23.jsonl --summary out\digra_2026-04-23_summary.json --sqlite out\digra_2026-04-23.sqlite
```

Lokale HTML-Ansicht bauen:

```powershell
python -m graz_protocols.viewer --records out\agenda_items_digra.jsonl --summary out\summary_digra.json --topics out\topic_candidates.json --output viewer.html
```

Der erzeugte Viewer entfernt Rohformulierungen, Quellenausschnitte und interne englische Typ-/Statuscodes aus den eingebetteten Einträgen.
Ein Klick auf eine Tabellenzeile zeigt eine deutsche Detailansicht für den Eintrag, inklusive Ergebnisquelle und DIGRA-Link.
Optional eingebettete Themenkandidaten erscheinen als einfache Themenverläufe oberhalb der Tabelle.
Orte werden als klickbare Kartenelemente gerendert. Der Viewer nutzt Leaflet/OpenStreetMap und geocodiert Ortsnamen bei Bedarf online über Nominatim; Geocoding-Ergebnisse werden im Browser-LocalStorage gecacht.
Der Jahresfilter wirkt auf Tabelle, Themen und Karte gemeinsam.
DIGRA-URLs werden als externe Links mit `target="_blank"` gerendert.

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

## Dokumentation aktuell halten

Wenn sich das Projekt ändert, die passende Markdown-Datei im selben Arbeitsdurchlauf aktualisieren:

- `AGENTS.md` für Agentenregeln und Arbeitsbeschränkungen
- `DATA_POLICY.md` für Datenregeln
- `PROJECT_NOTES.md` für Architektur, Richtung und Projektstand
- `README.md` für Zweck und Bedienung
- `DEVELOPMENT.md` für Befehle und lokalen Ablauf
