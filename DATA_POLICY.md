# Datenregeln

## Nicht verhandelbare Regel

Gemeinderatsprotokolle und roh heruntergeladene Dokumente dürfen niemals ins Git gepusht werden.

Die `.gitignore` schließt typische Protokollordner und Dokumentformate aus. Das allein reicht aber nicht. Vor jedem Staging oder Commit immer `git status --short` prüfen.

## Im Git erlaubt

- Quellcode
- Tests
- Dokumentation
- Extraktionsschemata
- kleine bereinigte Fixtures
- reine Metadatenbeispiele ohne vollständigen Protokolltext

## Im Git verboten

- DOCX-/PDF-/XLSX-Protokolldateien
- vollständig extrahierter Protokolltext
- rohe DIGRA-Exporte
- lokale Archiv-Manifeste mit sensiblen absoluten Pfaden, außer sie wurden ausdrücklich bereinigt
- erzeugte Datenbanken mit Quelleninhalt

## Lokale Arbeitsdaten

Für echtes Quellenmaterial ignorierte Ordner verwenden:

- `graz_protokolle_arbeitskopie/`
- `data/raw/`
- `data/source/`

Für erzeugte Extraktionsergebnisse ignorierte Ausgabeorte verwenden:

- `out/`
- `exports/`
- `*.sqlite`
- `*.jsonl`

## Bereinigte Fixtures

Wenn Tests Beispiele brauchen, kurze künstliche Ausschnitte erstellen, die die Struktur erhalten, aber keinen vollständigen Protokollinhalt kopieren.
