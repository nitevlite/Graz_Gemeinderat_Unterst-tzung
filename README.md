# Graz Gemeinderatsprotokoll-Explorer

Der Graz Gemeinderatsprotokoll-Explorer ist eine Webansicht fuer oeffentliche Gemeinderatsdaten der Stadt Graz. Die Anwendung bereitet Tagesordnungspunkte, Antraege, Anfragen, Mitteilungen, Fragestunden und Archivquellen so auf, dass sie durchsucht, gefiltert und thematisch eingeordnet werden koennen.

Die App ist keine amtliche Quelle und ersetzt nicht die offiziellen Systeme der Stadt Graz. Sie ist ein Recherche- und Transparenzwerkzeug, das oeffentliche Informationen leichter zugaenglich macht.

## Fuer Besucherinnen und Besucher

Die oeffentliche Ansicht bietet:

- Volltextsuche ueber Gemeinderatsstuecke und verwandte Quellen
- Filter nach Datum, Jahr, Typ, Status, Ergebnis, Thema und Betrag
- Detailansichten mit Titel, Status, Ergebnis, Geschaeftszahlen, Quellenlinks und erkannten Ortsbezuegen
- Themenverlaeufe ueber mehrere Sitzungen
- Kartenansichten fuer erkannte Orte und zusaetzliche Graz-Kontexte
- lokale Antwortfunktion, die Suchtreffer gruppiert und mit Quellenbezug zusammenfasst
- einfache Zusammenfassungen, Kernpunkte und offene Punkte zu einzelnen Eintraegen
- Exportfunktionen fuer gefilterte Treffer

Der Viewer arbeitet als statische Website. Fuer die Nutzung braucht man keinen Account, keinen lokalen Server und kein Modell.

## Inhaltlicher Fokus

Die App versucht sichtbar zu machen:

- was im Gemeinderat behandelt wurde
- ob ein Stueck angenommen, abgelehnt, zugewiesen, berichtet oder nur zur Kenntnis genommen wurde
- welche Geschaeftszahlen, Einbringer, Adressaten und Abstimmungsdetails erkennbar sind
- welche Orte, Strassen, Plaetze, Grundstuecke oder Geldbetraege in einem Stueck vorkommen
- wie sich ein Thema ueber mehrere Sitzungen entwickelt
- wo die jeweilige Originalquelle erreichbar ist

## Datenbasis

Die Anwendung nutzt oeffentliche Quellen wie DIGRA Graz und Archivseiten der Stadt Graz. Zusaetzliche offene Datenquellen werden fuer Karten- und Serviceansichten eingebunden, etwa fuer Baustellen, Parkgaragen, Apotheken, Ordinationen oder Servicepunkte.

Die veroeffentlichte Website enthaelt eine statisch erzeugte Ansicht. Arbeitsdaten, Rohdokumente und lokale Zwischenergebnisse werden nicht als Repository-Inhalt veroeffentlicht.

## Technischer Ueberblick

Das Repository enthaelt die Python-Werkzeuge, Tests, Viewer-Logik, statische Assets und GitHub-Actions-Workflows, mit denen die Website gebaut wird.

Der technische Ablauf ist:

1. oeffentliche Sitzungs- und Dokumentdaten werden importiert,
2. Eintraege werden normalisiert und strukturiert,
3. Suchdaten, Themen und Zusammenfassungen werden erzeugt,
4. eine statische HTML-Seite wird gebaut,
5. GitHub Actions veroeffentlicht die Seite ueber GitHub Pages.

## Entwicklung

Abhaengigkeiten installieren:

```powershell
python -m pip install -r requirements.txt
```

Tests ausfuehren:

```powershell
python -m pytest
```

Datensicherheitscheck ausfuehren:

```powershell
python scripts\check_git_safety.py
```

Aktuelle oeffentliche Daten importieren:

```powershell
python -m graz_protocols.cli digra-sync --limit 30 --city-archive-links
```

Viewer bauen:

```powershell
python -m graz_protocols.viewer
```

Lokale Suche ausfuehren:

```powershell
python -m graz_protocols.cli search "Anrainerparken"
```

Lokale Antwort aus dem Suchindex erzeugen:

```powershell
python -m graz_protocols.cli answer "Was ist zu Anrainerparken beschlossen?"
```

## GitHub Pages

Der Workflow `publish public viewer` baut die oeffentliche Website automatisch. Bei einem passenden Push oder beim geplanten Lauf werden die aktuellen oeffentlichen Daten verarbeitet, der Viewer gebaut und der Inhalt in den Pages-Branch veroeffentlicht.

Wenn GitHub Pages fuer das Repository aktiviert ist, ist die Website unter der Pages-URL des Repositories erreichbar.

## Status

Das Projekt ist ein laufendes Open-Source-Arbeitsprojekt. Parser, Importer, Suche und Viewer sind testabgedeckt, koennen sich aber mit neuen Datenstrukturen der Quellen weiterentwickeln.
