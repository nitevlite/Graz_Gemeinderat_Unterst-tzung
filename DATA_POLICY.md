# Datenregeln

## Nicht verhandelbare Regel

Gemeinderatsprotokolle und roh heruntergeladene Dokumente dürfen niemals ins Git gepusht werden.

Die `.gitignore` schließt typische Protokollordner und Dokumentformate aus. Das allein reicht aber nicht. Vor jedem Staging oder Commit immer `git status --short` prüfen.
Zusätzlich gibt es einen technischen Check:

```powershell
python scripts\check_git_safety.py
```

Der Check prüft den Git-Index und verfolgte Dateien auf verbotene Protokoll-/Exportformate, lokale Datenordner und große Dateien.

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

## Technischer Git-Check

Der Check blockiert unter anderem:

- `*.docx`, `*.doc`, `*.pdf`, `*.xlsx`, `*.xls`, `*.odt`
- `*.jsonl`, `*.sqlite`, `*.sqlite3`, `*.db`
- `out/`, `exports/`, `data/raw/`, `data/source/`, `graz_protokolle_arbeitskopie/`
- verfolgte Dateien über 1 MB

Die GitHub Action `checks` führt denselben Check bei Push und Pull Request aus.

## Bereinigte Fixtures

Wenn Tests Beispiele brauchen, kurze künstliche Ausschnitte erstellen, die die Struktur erhalten, aber keinen vollständigen Protokollinhalt kopieren.

## Externe Mobilitätsdaten

Direkt einbettbare externe Daten brauchen eine klare Weiterverwendungsgrundlage.

Aktuell zulässig:

- Parkgaragen Graz aus `data.gv.at` / `data.graz.gv.at`
- Lizenz: `CC BY 4.0`
- Namensnennung: `Stadt Graz - data.graz.gv.at`
- Nutzung im Open-Source-Projekt ist mit Attribution vorgesehen; Live-Verfügbarkeit wird nicht übernommen, solange keine offene Live-API mit klarer Lizenz vorliegt.

Aktuell nicht direkt einzubetten:

- Baustellen-Geometrien aus der Stadt-Graz-Onlinekarte bzw. Geoportal-Services
- Grund: keine OGD-Freigabe gefunden; die Geoportal-Nutzungsbedingungen sind restriktiv.
- Zulässig im Projekt: Verlinkung auf die offizielle Baustelleninformation und eigene Planungs-/Prüfdaten, die Nutzer:innen selbst eingeben.
