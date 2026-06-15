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
- `graz-baustellen-feed.json`
- `graz-baustellen-feed.csv`
- `graz-baustellen.ics`
- `graz-baustellen-feed.rss`
- `graz-baustellen-abos.json`
- `graz-baustellen-feedback.json`
- `graz-baustellen-auditlog.json`

## Technischer Git-Check

Der Check blockiert unter anderem:

- `*.docx`, `*.doc`, `*.pdf`, `*.xlsx`, `*.xls`, `*.odt`
- `*.jsonl`, `*.sqlite`, `*.sqlite3`, `*.db`
- `out/`, `exports/`, `data/raw/`, `data/source/`, `graz_protokolle_arbeitskopie/`
- verfolgte Dateien über 1 MB

Die GitHub Action `checks` führt denselben Check bei Push und Pull Request aus.

## Bereinigte Fixtures

Wenn Tests Beispiele brauchen, kurze künstliche Ausschnitte erstellen, die die Struktur erhalten, aber keinen vollständigen Protokollinhalt kopieren.
Such-Goldstandards dürfen nur bereinigte Fragen, erwartete lokale `record_id`s, kurze synthetische Hinweise und Tags enthalten. Keine vollständigen Protokollpassagen, keine heruntergeladenen Dokumenttexte und keine rohen Exporte in Goldstandard-Dateien übernehmen.

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
- Zulässig im Projekt: lokale Anzeige der öffentlichen Baustellen-Webseite von `graz.at` über einen ignorierten Cache unter `out/`, Verlinkung auf die offizielle Quelle und eigene Planungs-/Prüfdaten, die Nutzer:innen selbst eingeben.
- Nicht zulässig: den geladenen Baustellen-HTML-Cache, Geoportal-Geometrien oder daraus erzeugte statische Baustellen-Datensätze ins Repository committen.

Die statische Amtsansicht speichert Entwürfe, Freigaben und Auditlog nur im Browser-`localStorage`. Lokale Bürger-Abos und Feedbackhinweise werden ebenfalls nur im Browser gespeichert. Exporte daraus sind lokale Arbeitsdaten. Sie dürfen nur nach fachlicher Prüfung und ohne personenbezogene oder interne Inhalte veröffentlicht werden.

KI bleibt optional. Der Standardbetrieb darf keine kostenpflichtige Cloud-KI, externen API-Abos oder proprietären Datenquellen voraussetzen. Quellenanzeige, Suche, Karte, Feed-Export und regelbasierte Baustellenprüfung müssen ohne KI funktionieren.

## Öffentliche Website

Für GitHub Pages darf nur der statisch erzeugte Viewer veröffentlicht werden.
Build-Zwischendaten wie JSONL, Summary-JSON, SQLite-Datenbanken, DIGRA-Caches, lokale Archivassets oder heruntergeladene Quelldokumente dürfen nicht in `public/` oder den Branch `gh-pages` kopiert werden.
Der Pages-Workflow nutzt `public_work/` nur als temporären Runner-Arbeitsordner und veröffentlicht ausschließlich `index.html` und `.nojekyll` nach `gh-pages`.
