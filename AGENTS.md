# AGENTS.md

## Projektregel: Keine Protokolle committen

Gemeinderatsprotokolle, heruntergeladene Gemeinderatsdokumente, lokale Archivkopien und daraus abgeleitete rohe Dokumentexporte niemals committen, stagen oder pushen.

Das betrifft insbesondere:

- `graz_protokolle_arbeitskopie/`
- `protokolle/`
- `archive/`
- `data/raw/`
- `data/source/`
- `*.docx`, `*.doc`, `*.pdf`, `*.xlsx`, `*.xls`, `*.odt`

Nur Quellcode, Dokumentation, Parserdefinitionen, Tests und bereinigte Beispiel-Fixtures committen.

## Arbeitsnotizen

- Diese Datei und die anderen Projekt-Markdown-Dateien aktuell halten, wenn sich Richtung, Datenregeln, Befehle oder Architektur ändern.
- Vor jedem Commit `git status --short` ausführen und prüfen, dass keine Protokolldateien gestaged sind.
- Wenn Beispieldaten nötig sind, kleine bereinigte Textfixtures erstellen, die keinen vollständigen Protokollinhalt enthalten.
- Quelldokumente als lokales Arbeitsmaterial behandeln, nicht als Repository-Inhalt.

## Aktuelle lokale Daten

Der aktuelle Workspace enthält eine lokale, ignorierte Protokoll-Arbeitskopie:

- `graz_protokolle_arbeitskopie/`

Der Ordner enthält DOCX-Dateien aus `E:\01_StadtGrazProtokolle\Archiv\...` plus eine lokale `manifest.json`. Dieser Ordner ist absichtlich von Git ignoriert.

## Aktuelles MVP

Das Parser-MVP liegt in `graz_protocols/` und wird mit bereinigten Fixtures in `tests/` geprüft.
Es liest DOCX-Absatzformatvorlagen und erzeugt aktuell die internen Typen `agenda_item`, `archive_source`, `communication`, `urgent_motion`, `written_question`, `written_motion` und `question_hour`.
`result_text` bleibt für die Anzeige standardisiert und wird nicht aus dem Protokollwortlaut kopiert.
Originalformulierungen bleiben nur in ignorierten lokalen Ausgabefeldern wie `raw_result_text`.
`votes` enthält strukturierte Entscheidungsdetails wie Ergebnis, Zustimmung, Gegenstimmen und Enthaltungen.
Der Viewer zeigt deutsche Typen und deutsche Statuswerte.

Parser ausführen:

```powershell
python -m graz_protocols.cli parse graz_protokolle_arbeitskopie --output out\agenda_items.jsonl --summary out\summary.json --sqlite out\eintraege.sqlite
```

Open-Source-Standardimport ohne lokale Protokollkopien:

```powershell
python -m graz_protocols.cli digra-sync --limit 30 --output out\agenda_items_digra_sync.jsonl --summary out\summary_digra_sync.json --sqlite out\eintraege_digra_sync.sqlite --city-archive-links
```

Mit vorhandenen Stadt-Graz-Archivassets:

```powershell
python -m graz_protocols.cli digra-sync --limit 30 --output out\agenda_items_digra_sync.jsonl --summary out\summary_digra_sync.json --sqlite out\eintraege_digra_sync.sqlite --city-archive-links --city-archive-assets --city-archive-assets-index out\city_archive_assets.json
```

Der Ausgabeordner `out/` ist ignoriert und muss untracked bleiben.
Lokale Viewer-Exporte wie `graz-baustellen-feed.json`, `graz-baustellen-feed.csv`, `graz-baustellen-feed.rss`, `graz-baustellen.ics`, `graz-baustellen-abos.json`, `graz-baustellen-feedback.json` und `graz-baustellen-auditlog.json` sind ebenfalls Arbeitsdaten und dürfen nicht gestaged werden.
