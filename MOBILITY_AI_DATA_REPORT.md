# Mobilitäts-, Baustellen- und KI-Datenbericht

Stand: 2026-06-09

## Ziel

Die App soll nicht nur Gemeinderatsbeschlüsse anzeigen, sondern auch räumlich und zeitlich einschätzen helfen:

- Welche Beschlüsse betreffen welche Orte?
- Wo laufen oder liefen Baustellen?
- Welche Baustellen wären für neue Sperren kritisch?
- Welche Tiefgaragen/Parkhäuser gibt es in der Nähe?
- Welche zusätzlichen Verkehrs- und Stadtdaten kann eine lokale KI für bessere Einschätzungen verwenden?

Die wichtigste Regel bleibt: Rohprotokolle, heruntergeladene Daten-Caches und große erzeugte Exporte bleiben aus Git draußen.

## Direkt Umsetzbare UI-Ideen

### Start-Tab mit Fragefeld

Sinnvoller neuer erster Tab: `Start`.

Funktion:

- Mittig ein großes Fragefeld wie bei ChatGPT.
- Nutzerfrage, z. B. `Welche Beschlüsse und Baustellen betreffen 2026 die Kärntner Straße?`
- Antwort aus lokalem Datenbestand:
  - sichtbare Gemeinderatseinträge
  - Themenverläufe
  - Baustelleninfos
  - Tiefgaragen
  - optional zusätzliche Verkehrs-/Stadtdaten

Technisch ist der Start-Tab jetzt zuerst eine kostenlose lokale Quellenantwort:

- Kein OpenAI-Key nötig.
- Kein Ollama-Modell für die Standardantwort nötig.
- Die App durchsucht die lokalen Quellen, rankt die besten Treffer und gliedert die Antwort nach Beschluss, Antrag, Frage, Mitteilung und offenem Stand.
- Kontext bleibt stark begrenzt: erst normale Suche/Filter lokal ausführen, dann nur die besten Treffer anzeigen und zitieren.

Wichtig: Die KI darf nie ungeprüft als Quelle gelten. Antwort sollte Quellenblöcke nennen: Eintrag, Datum, DIGRA/Stadt-Graz-Link, Baustelle oder OGD-Datensatz.

### Baustellen-Legende nach Zeitstatus

Die Baustellenkarte sollte Statusfarben bekommen:

- `Aktuell`: Baustellen, deren Zeitraum heute einschließt.
- `Künftig`: Startdatum liegt in der Zukunft.
- `Abgeschlossen`: Enddatum liegt in der Vergangenheit.
- `Unklar`: Zeitraum konnte nicht sauber geparst werden.

Filter/Legende:

- Chips in der Baustellenkarte: `Alle`, `Aktuell`, `Künftig`, `Abgeschlossen`, `Unklar`.
- Klick auf Chip blendet nur diese Kategorie ein.
- Farben:
  - Aktuell: Orange/Rot
  - Künftig: Blau
  - Abgeschlossen: Grau
  - Unklar: Violett oder neutral

Offener technischer Punkt: Die Stadt-Graz-Baustellen-Seite schreibt Zeiträume teils als `01.06. - 19.06.2026` und teils mit Uhrzeiten. Der Parser muss fehlende Jahre im Startdatum vom Enddatum übernehmen.

### Ladebalken Für Alle Karten

Aktuell hat die normale Graz-Karte bereits einen Ladebalken. Ergänzen:

- Baustellenkarte: Fortschritt beim Geocoding der Baustellenorte.
- Tiefgaragenkarte: Fortschritt beim Einzeichnen/Geocoding der Garagen.
- Optional Statuszeile: `12/20 Baustellen eingezeichnet`.

Bei Tiefgaragen mit vorhandenen Koordinaten sollte der Balken nur sehr kurz sichtbar sein.

## Baustellenquellen

### Stadt Graz Baustellen-Seite

Quelle: https://www.graz.at/cms/beitrag/10028253/7755789/Baustellen_in_Graz.html

Aktueller lokaler Stand:

- Die App lädt die öffentliche HTML-Seite in `out\baustellen_graz.html`.
- Der Cache ist ignoriert und darf nicht ins Git.
- Der Parser findet aktuell 20 Baustelleninfos.
- Beispieltreffer:
  - `Kärntner Straße 163`
  - `Kärntner Straße gegenüber 209`

Verwendbare Felder:

- Ort/Straße aus Überschrift
- Maßnahme aus Text
- Zeitraum aus `Termin: ...`
- Projekt, z. B. Energie Graz
- Quellenlink zur Stadt-Graz-Seite

Bewertung:

- Für lokale Anzeige gut geeignet.
- Für Open-Source-Repository nicht als statischer Datensatz committen.
- Keine klare OGD-Lizenz für diese HTML-Liste gefunden.

### Stadt Graz Baustelleninformation / Geoportal

Quelle: https://www.graz.at/cms/beitrag/10295878/8115447/Baustelleninformation.html

Bewertung:

- Gut zum Verlinken und fachlich als offizielle Karte relevant.
- Nicht direkt als Datensatz übernehmen, solange keine offene Lizenz und kein klar dokumentierter Download/API-Endpunkt vorliegt.
- Geoportal-Geometrien nur verwenden, wenn Nutzungsbedingungen eindeutig erlauben.

## Tiefgaragen Und Parkhäuser

### OGD: Parkgaragen Graz

Quelle: https://www.data.gv.at/katalog/dataset/92183c55-442b-405d-9046-d19b07ffc83a

Download im Code:

```text
https://data.graz.gv.at/graz/wp-content/uploads/2024/06/Parkgaragen.csv
```

Lizenz:

- `CC BY 4.0`
- Attribution: `Stadt Graz - data.graz.gv.at`

Das ist die sauberste Quelle für Open Source.

Aktueller Befund:

- Der CSV-Download ist `ISO-8859-1`/`cp1252`, nicht UTF-8.
- Der aktuelle Loader versucht zuerst UTF-8 und bekommt dadurch lokal 0 Garagen.
- Das muss technisch korrigiert werden: Downloadbytes zuerst `utf-8-sig`, dann `cp1252`, dann `latin-1` probieren.

ODG-Datensatz enthält aktuell 14 Einträge:

- `PH LKH` - Stiftingtalstraße 30
- `PP Griesplatz` - Griesplatz 7
- `PH Orpheum` - St. Georgen Gasse 10
- `PH Griesgasse` - Griesgasse 10
- `PH Austeingasse` - Austeingasse 30
- `PH Körösistraße` - Körösistraße 67
- `PH Rösselmühlgasse` - Rösselmühlgasse 12
- `PH Am Rösselmühlpark` - Dreihackengasse 42
- `PH Thondorf` - Liebenauer Hauptstraße 316
- `PH GKB Center` - Köflacher Gasse 3
- `PH Schlossberg` - Sackstraße 29
- `PH Schönaugasse` - Schönaugasse 6
- `PH Kaiser-Josef-Platz` - Schlögelgasse 5
- `PP Plüddemanngasse (DM Markt)` - Plüddemanngasse 71

### Aktuelle Fallback-Garagen In Der App

Der Viewer enthält derzeit 8 manuelle Fallback-Standorte:

- `TG Operngarage`
- `TG Kastner&Öhler`
- `PH LKH`
- `TG Annenpassage`
- `TG Bahnhof`
- `TG Stadion Liebenau`
- `TG Brauquartier`
- `TG Gate17`

Bewertung:

- Diese Fallbacks helfen, wenn OGD/Geocoding nicht funktioniert.
- Sie sind aber kein sauberer Ersatz für einen vollständigen Datensatz.
- Einige Fallbacks stammen von der Stadt-Graz-Garagen-Webseite, nicht aus OGD.
- Diese Quelle hat keine klare Datensatzlizenz, daher besser nur als lokaler, nachvollziehbarer Fallback oder als Link verwenden.

### Stadt Graz Garagen-Webseite

Quelle: https://www.graz.at/cms/beitrag/10176957/7922687/Garagen_in_Graz.html

Die Seite nennt deutlich mehr Garagen/Parkplätze als der OGD-Datensatz. Kandidaten aus der Seite:

- `TG Burgring`
- `PH Schlossberg`
- `TG Kastner&Öhler`
- `TG Pfauengarten`
- `TG Operngarage`
- `TG Steirerhof`
- `PH Kaiser-Josef-Platz`
- `Parkhaus Körösistraße`
- `TG Styria Center`
- `PH Orpheum`
- `TG Kunsthaus`
- `TG Lendplatz`
- `PH Austeingasse`
- `TG Metahof`
- `TG Annenpassage`
- `TG Bahnhof`
- `TG Mariahilferplatz`
- `PH am Rösselmühlpark`
- `Parkplatz Bad zur Sonne`
- `PH Griesgasse`
- `TG Dominikaner-Kloster`
- `TG Roseggerhaus`
- `PP GriesPARKplatz`
- `Citygarage Weitzer`
- `TG ÖAMTC`
- `TG J. Pongratz Platz`
- `TG Augartenhotel Art & Design`
- `PH Schönaugasse`
- `TG Stadion Liebenau`
- `Parkplatz St. Peter Hauptstraße`
- `Waltendorf Garage`
- `TG Plüddemanngasse`
- `PH LKH`
- `TG Wohnpark Graz Gösting`
- `TG Brauquartier`
- `TG Gate17`

Bewertung:

- Fachlich wertvoll, weil vollständiger als OGD.
- Lizenzrechtlich schlechter als OGD, weil keine klare offene Datensatzlizenz gefunden wurde.
- Für die App: als verlinkte Webquelle und lokaler Cache möglich, aber nicht als committed statischer Datensatz.

### Fehlen Aktuell Garagen?

Ja.

Im aktuellen Viewer fehlen gegenüber dem OGD-Datensatz mindestens:

- `PP Griesplatz`
- `PH Orpheum`
- `PH Griesgasse`
- `PH Austeingasse`
- `PH Körösistraße`
- `PH Rösselmühlgasse`
- `PH Am Rösselmühlpark`
- `PH Thondorf`
- `PH GKB Center`
- `PH Schlossberg`
- `PH Schönaugasse`
- `PH Kaiser-Josef-Platz`
- `PP Plüddemanngasse (DM Markt)`

Grund: Der OGD-Loader liest den CSV-Download wegen Encoding aktuell nicht korrekt ein und fällt daher auf die 8 Fallbacks zurück.

Priorität:

1. OGD-Encoding-Fix einbauen.
2. Viewer bevorzugt die 14 OGD-Einträge anzeigen lassen.
3. Fallback-Liste nur ergänzend nutzen, wenn OGD leer ist.
4. Für zusätzliche Garagen aus der Stadt-Graz-Webseite gesondert kennzeichnen: `Quelle Webseite, Lizenz unklar, nicht exportieren`.

## Verfügbarkeit Von Stellplätzen

Aktuell belastbar:

- OGD liefert Standortdaten, aber keine Live-Verfügbarkeit.
- Die App zeigt deshalb korrekt `Verfügbarkeit: unbekannt`.
- Ergänzt: Für einzelne Garagen wird nur ein externer Prüflink zu `parken.at` angezeigt.
- Keine Verfügbarkeit, Preise oder Standortdaten von `parken.at` übernehmen oder cachen, weil die Nutzungsbedingungen eine Weiterverwendung ohne Zustimmung einschränken.
- Dieser Hinweis ist keine OGD-Live-API, wird als externe Quelle verlinkt und darf nicht als belastbarer städtischer Echtzeitdatensatz behandelt werden.

Noch zu prüfen:

- Ob Betreiberseiten Live-Anzeigen haben.
- Ob Holding Graz, BOE, Apcoa, Best in Parking oder private Betreiber eine API mit erlaubter Nutzung anbieten.
- Ob Scraping der Live-Anzeigen laut AGB erlaubt ist.

Empfehlung:

- Keine Live-Verfügbarkeit scrapen, solange AGB/API-Lizenz nicht eindeutig ist. `Parken.at` nur verlinken.
- Für MVP: `unbekannt` behalten.
- Später: Adapter pro Anbieter nur mit klar erlaubter API.

## Zusätzliche Verkehrs- Und Stadtdaten Für KI-Einschätzung

### Gute Kandidaten

Diese Daten wären für eine KI-Baustellenbewertung sinnvoll:

- Verkehrszählstellen / Verkehrsbelastung nach Straße
- Radzählstellen
- ÖV-Haltestellen, Linien und Fahrpläne
- Baustellen und Sperren
- Unfalldaten oder Unfallhäufungsstellen, falls offen verfügbar
- Straßennetz/GIP
- Schulen, Krankenhäuser, Pflegeheime, große Veranstaltungsorte
- Tiefgaragen und Parkhäuser
- Fußgängerzonen, Begegnungszonen, Tempozonen
- Wetterwarnungen nur als optionaler Tageskontext

### Mögliche Plattformen

#### data.gv.at / data.graz.gv.at

Verwendung:

- Erste Wahl, wenn Datensatz offen mit Lizenz angegeben ist.
- Meist gut für Open Source, wenn CC BY 4.0 oder vergleichbar.
- `https://data.graz.gv.at/graz/verkehr/` ist der lokale Katalogeinstieg für Grazer Verkehrsdaten.
- `Graz Linien - Fahrplandaten und Haltestellen` ist als Kandidat für ÖV-Haltestellen, Linien und Fahrpläne dokumentiert:
  `https://data.europa.eu/data/datasets/7317b9ca-1349-4660-a2db-54e67160d469?locale=de`

Prüfen pro Datensatz:

- Lizenz
- Aktualität
- Download/API-URL
- Attribution
- Personenbezug oder Sicherheitsrisiken

Umsetzung im Code:

- `mobility_source_summary()["traffic_data_audit"]` enthält jetzt die auditierte Quellenliste.
- Importiert werden weiterhin nur Quellen mit klarer lokaler Download-/Lizenzlage.
- ÖV-Daten bleiben ein späterer Import-Ticketkandidat, weil Download-URL und Lizenz vor einem Commit-fähigen Import nochmals am konkreten Datensatz geprüft werden müssen.

#### Mobilitydata Austria

Quelle: https://www.mobilitydata.gv.at/

Mögliche Daten:

- Verkehrsmeldungen / Ereignisse
- GIP-Straßennetz
- ÖV-Daten
- Radzählstellen oder Mobilitätsdaten je nach Datensatz

Bewertung:

- Sehr relevant für Baustellen-/Sperrenbewertung.
- Lizenz und technische API müssen pro Datensatz geprüft werden.
- Gute Kandidaten für eine spätere Import-Schicht.

Audit 2026-06-09:

- `Radzählstellenbericht`
  - Quelle: `https://mobilitaetsdaten.gv.at/en/daten/radz%C3%A4hlstellenbericht`
  - Inhalt: bundesweite Fahrradzähldaten, Stadt Graz als Dateneigentümer gelistet.
  - Lizenzmodell laut Mobilitydata: `No licence - No contract`.
  - Entscheidung: nur verlinken/manuell auswerten, nicht als offenen Rohdatensatz importieren.

- `Graphenintegrations-Plattform Österreich (GIP.at)`
  - Quelle: `https://mobilitaetsdaten.gv.at/en/daten/graphenintegrations-plattform-%C3%B6sterreich-gipat`
  - Inhalt: Netz-/Zugänglichkeitsdaten, laufend aktualisiert.
  - Lizenzmodell laut Mobilitydata: `No licence - No contract`; Data-Access-Link führt weiter zu data.gv.at und muss vor Import separat geprüft werden.
  - Entscheidung: sehr relevant für Routing/Referenzierung, aber kein Import ohne geklärte Nutzungsbedingungen.

- `Geplante Ereignismeldungen (EVIS.AT)`
  - Quelle: `https://mobilitaetsdaten.gv.at/daten/geplante-ereignismeldungen-evisat`
  - Inhalt: Baustellen, Veranstaltungen, Wintersperren, Sperren; DATEX II/XML; Aktualisierung 5 Minuten.
  - Lizenzmodell: `Nutzungsvertrag mit Nutzungsgebühr`.
  - Entscheidung: nicht ins Open-Source-MVP importieren; späterer lizenzierter Adapter möglich.

- `Ungeplante Ereignismeldungen (EVIS.AT)`
  - Quelle: `https://mobilitaetsdaten.gv.at/en/daten/ungeplante-ereignismeldungen-evisat`
  - Inhalt: Unfall, Panne, Stau, Störung; DATEX II/XML; Aktualisierung 5 Minuten.
  - Lizenzmodell: `Contract and Fee`.
  - Entscheidung: nicht ohne Vertrag importieren.

- `Verkehrslage (EVIS.AT)`
  - Quelle: `https://mobilitaetsdaten.gv.at/daten/verkehrslage-evisat`
  - Inhalt: Level of Service, Reisezeiten, Verkehrsaufkommen, Geschwindigkeiten; JSON; Aktualisierung 5 Minuten.
  - Lizenzmodell: `Nutzungsvertrag mit Nutzungsgebühr`.
  - Entscheidung: wertvoll für spätere Live-Bewertung, aber nicht Open-Source-Standarddatenquelle.

#### Stadt Graz Mobilitätsseiten

Quelle: https://www.graz.at/

Mögliche Informationen:

- Baustelleninfos
- Mobilitätsstrategie
- Parken/Garagen
- Radverkehrsinfrastruktur
- Verkehrskonzepte

Bewertung:

- Gut für Links und Kontext.
- Nicht automatisch als offener Datensatz behandeln.

## KI-Einschätzung Für Neue Baustellen

Ein sinnvoller KI-Workflow:

1. Nutzer gibt Ort, Zeitraum, Sperrtyp und Beschreibung ein.
2. App sammelt harte Fakten:
   - Baustellen im Umkreis
   - Gemeinderatsbeschlüsse am Ort
   - Kategorie/Projektverläufe
   - Garagen/Parkplätze in der Nähe
   - ÖV-/Rad-/Verkehrsdaten, sobald verfügbar
3. App berechnet einfache Regeln:
   - zeitliche Überschneidung
   - gleiche Straße oder Kreuzung
   - mehrere Sperren parallel
   - Nähe zu Krankenhaus, Schule, Bahnhof, Stadion, Innenstadt
4. Lokale KI formuliert Einschätzung:
   - Risiko: niedrig/mittel/hoch
   - Warum?
   - Bessere Zeitfenster?
   - Welche Stellen gemeinsam koordinieren?
   - Welche Quellen stützen die Einschätzung?

Wichtig: Die KI soll keine Geodaten erfinden. Sie darf nur aus den gefundenen Quellen argumentieren.

Umsetzung im Viewer:

- Die Baustellenprüfung berechnet jetzt zuerst eine Regelbewertung `niedrig`, `mittel` oder `hoch`.
- Regeln berücksichtigen räumliche Treffer, zeitliche Überschneidung, aktuelle/künftige Baustellen, Totalsperre und sensible Orte wie LKH, Schule, Bahnhof, Stadion oder Innenstadt.
- Danach werden Quellenblöcke aus Baustelleninfos, Gemeinderatseinträgen und Parkgaragen erzeugt.
- Die Standardantwort wird lokal aus Regelbewertung, Quellen und Zusammenfassungsfeldern aufgebaut.
- Wenn kein belastbarer Quellenkontext gefunden wird, erzeugt die App keine freie Antwort.

## Konkrete Nächste Tickets

Umsetzungsstand 2026-06-09:

- Erledigt: OGD-Parkgaragen-Encoding mit `utf-8-sig`, `cp1252`, `latin-1`.
- Erledigt: Parkgaragenkarte nutzt bevorzugt OGD-Daten und fällt nur bei leerem OGD-Datensatz auf lokale Fallbacks zurück.
- Erledigt: Baustellenzeiträume werden zu `start_date`, `end_date` und `time_status` normalisiert.
- Erledigt: Baustellenkarte hat Statuschips, Statusfarben und Filter.
- Erledigt: Baustellen- und Parkgaragenkarte haben Fortschrittsbalken.
- Erledigt: Neuer Start-Tab mit lokaler Quellenantwort, begrenztem Top-Treffer-Kontext und Quellenblöcken.
- Erledigt: Traffic-Data-Source-Audit für zusätzliche Verkehrs-/ÖV-/GIP-Daten.
- Erledigt: Eigene KI-Baustellenbewertung mit Regelbasis, lokaler KI-Erklärung und Quellenpflicht.

1. `Fix OGD parking CSV encoding`
   - `load_parking_garages` muss cp1252/latin-1 fallback können.
   - Test mit echter Header-Zeile und `Stiftingtalstraße`.

2. `Show all OGD parking garages`
   - Nach Encoding-Fix müssen die 14 OGD-Garagen in der Tiefgaragenkarte erscheinen.
   - Fallback nur verwenden, wenn OGD leer bleibt.

3. `Roadwork status parser`
   - `Termin: 01.06. - 19.06.2026` zu Start/Ende normalisieren.
   - Status `aktuell`, `künftig`, `abgeschlossen`, `unklar`.

4. `Roadwork legend and colors`
   - Statuschips in Baustellenkarte.
   - Markerfarben nach Status.
   - Filter per Legende.

5. `Progress bars for roadworks and parking maps`
   - Gleiche Fortschrittslogik wie bei der normalen Karte.

6. `Start tab with local AI question field`
   - Tab vor `Suche`.
   - Kostenlose lokale Quellenantwort.
   - Kontext aus Top-Treffern statt kompletter JSONL.
   - Trennung nach beschlossen/umgesetzt, beantragt, gefragt, mitgeteilt und offen.

7. `Traffic data source audit`
   - data.gv.at, data.graz.gv.at und mobilitydata.gv.at gezielt nach Verkehrszählung, Radzählstellen, GIP, ÖV, Verkehrsmeldungen durchsuchen.
   - Pro Quelle Lizenz, API, Felder, Aktualität dokumentieren.

8. `AI roadwork assessment`
   - Regelbasierte Vorbewertung plus lokale KI-Erklärung.
   - Quellenpflicht in jeder Antwort.

## Wichtigste Erkenntnis

Für Tiefgaragen ist der offene OGD-Datensatz rechtlich am saubersten, aber technisch aktuell wegen Encoding nicht richtig eingebunden. Für mehr Vollständigkeit ist die Stadt-Graz-Garagen-Webseite nützlich, aber nicht als frei weiterverwendbarer Datensatz gesichert.

Für Baustellen ist die öffentliche Stadt-Graz-Seite derzeit der beste lokale Startpunkt. Für echte Geometrien, alte/abgeschlossene Baustellen und präzisere Sperrflächen braucht es entweder eine klar lizenzierte API oder eine eigene gepflegte Planungsdatenbank.
