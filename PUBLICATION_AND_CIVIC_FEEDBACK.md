# Veröffentlichung und Bürgerfeedback

Stand: 2026-06-15

## Aktueller Online-Stand

Der technische Online-Build ist umgesetzt.

- Branch `master` enthält den Quellcode und den Workflow `.github/workflows/pages.yml`.
- Der Workflow `publish public viewer` baut täglich aus DIGRA eine statische Website.
- Der Workflow schreibt nur `index.html` und `.nojekyll` in den Branch `gh-pages`.
- JSONL-, Summary- und SQLite-Dateien entstehen nur temporär im GitHub-Runner.
- Der Viewer enthält `noindex,nofollow,noarchive`, damit Suchmaschinen die Seite nicht aktiv indexieren sollen.
- `noindex` ist kein Zugriffsschutz. Wer die URL kennt, kann die Seite öffnen, sobald GitHub Pages aktiv ist.

Der letzte geprüfte Lauf war erfolgreich:

- `checks`: erfolgreich
- `publish public viewer`: erfolgreich
- `gh-pages`: vorhanden

## Warum GitHub Pages noch nicht aktiv ist

Das Repository ist aktuell privat.
GitHub hat beim Aktivieren von Pages gemeldet:

```text
Your current plan does not support GitHub Pages for this repository.
```

Das bedeutet: Mit dem aktuellen GitHub-Plan kann GitHub Pages für dieses private Repository nicht aktiviert werden.

## Was später zu tun ist

Option A: Repository öffentlich machen

1. Repository auf GitHub öffnen.
2. `Settings -> General -> Danger Zone -> Change repository visibility`.
3. Repository auf `Public` stellen.
4. Danach `Settings -> Pages` öffnen.
5. Source auf `Deploy from a branch` stellen.
6. Branch `gh-pages` auswählen.
7. Folder `/ (root)` auswählen.
8. Speichern.
9. Danach sollte die Seite unter dieser Form erreichbar sein:

```text
https://nitevlite.github.io/graz-council-protocol-explorer/
```

Option B: GitHub-Plan ändern

1. GitHub-Plan wählen, der Pages für private Repositories unterstützt.
2. Danach in `Settings -> Pages` dieselbe Einstellung wie oben setzen:
   - Source: `Deploy from a branch`
   - Branch: `gh-pages`
   - Folder: `/ (root)`

Option C: Externes statisches Hosting

Cloudflare Pages, Netlify oder ein eigener Webserver können den Branch `gh-pages` ebenfalls als statische Website veröffentlichen.
Der Build erzeugt bereits eine fertige `index.html`.

## Sichtbarkeit

Sobald die Seite veröffentlicht ist, ist sie öffentlich abrufbar.
Es gibt keinen Login und keinen Zugriffsschutz.

`noindex,nofollow,noarchive` reduziert nur die Suchmaschinen-Auffindbarkeit.
Es verhindert nicht, dass Menschen mit Link die Seite öffnen oder die URL weitergeben.

Wenn echte Zugriffsbeschränkung nötig ist, braucht es ein anderes Hosting mit Authentifizierung.

## Juristische und fachliche Punkte vor öffentlicher Bewerbung

Vor einer breiten Veröffentlichung sollten diese Punkte geklärt werden:

- Die Seite ist keine amtliche Veröffentlichung der Stadt Graz.
- Die Originalquellen DIGRA/Stadt Graz müssen immer verlinkt bleiben.
- Ergebnis- und Zusammenfassungstexte können Fehler enthalten.
- Keine vollständigen Protokolle, PDFs, DOCX, Beilagen oder Rohtexte veröffentlichen.
- Keine personenbezogenen Bürgerdaten veröffentlichen.
- Bei Bürgerfeedback keine politischen Meinungen mit Name, E-Mail oder genauer Adresse öffentlich anzeigen.
- Für jede Datenerhebung braucht es eine kurze Datenschutzerklärung.
- Bei Kontaktaufnahme oder Stimmabgabe mit personenbezogenen Daten braucht es Löschfristen und Zweckbindung.

## Plan: Bürgerfeedback zu zukünftigen Stücken

Ziel: Wenn ein Stück bereits vor der Gemeinderatssitzung in DIGRA sichtbar ist, sollen Bürgerinnen und Bürger dazu Feedback geben können.

Wichtig: Das darf nicht als echte Gemeinderatsabstimmung bezeichnet werden.
Passende Begriffe:

- `Bürgerfeedback`
- `Meinungsbild`
- `Rückmeldung`
- `Stimmungsbild`
- `Kommentar zur Vorlage`

Nicht verwenden:

- `Abstimmung`
- `Volksabstimmung`
- `verbindliche Stimme`
- `Gemeinderatsentscheidung`

## Fachliches Zielbild

Für jedes zukünftige Stück zeigt die App:

- Titel
- DIGRA-Link
- Sitzungsdatum, falls bekannt
- Status `vor Sitzung`, `in Behandlung`, `beschlossen`, `erledigt`
- einfache Kurzfassung
- Pro/Contra-Feedback
- optionale Begründung
- öffentliche aggregierte Auswertung

Beispiel:

```text
Stück: Radweg Beispielstraße
Status: vor Sitzung
Meinungsbild:
- Zustimmung: 68
- Ablehnung: 21
- Unsicher: 9
Häufige Gründe:
- Sicherheit für Kinder
- Sorge um Parkplätze
- Kosten unklar
```

## Empfohlener MVP ohne Login

Für den ersten öffentlichen Test:

- Eine Rückmeldung pro Browser und Stück per `localStorage`.
- Keine Namen.
- Keine E-Mail.
- Keine Adresse.
- Optional nur Bezirk oder grobe Auswahl.
- Kommentar optional, begrenzt auf kurze Länge.
- Moderation vor Veröffentlichung von Kommentaren.
- Aggregierte Zahlen öffentlich anzeigen.

Vorteil:

- schnell umsetzbar
- wenig personenbezogene Daten
- keine Nutzerkonten
- geringer Betrieb

Nachteil:

- nicht manipulationssicher
- dieselbe Person kann mit anderem Browser erneut abstimmen
- nur als Stimmungsbild geeignet

## Produktiver MVP mit Backend

Wenn das ernsthaft öffentlich genutzt werden soll, braucht es ein kleines Backend.

Minimaler Backend-Stack:

- statischer Viewer bleibt auf GitHub Pages oder Cloudflare Pages
- API auf Cloudflare Workers, Supabase Edge Functions, Fly.io oder kleinem VPS
- Datenbank: Supabase Postgres, SQLite/Turso oder Postgres
- Rate-Limit pro IP/Browser-Fingerprint
- Moderationsstatus für Kommentare
- Admin-Ansicht für Export und Sperren

Minimaler Datensatz:

```text
feedback
- id
- record_id
- digra_url
- stance: support | oppose | unsure
- reason_code
- comment_text
- district_optional
- created_at
- moderation_status: pending | approved | rejected
- ip_hash
- user_agent_hash
```

Keine Roh-IP dauerhaft speichern.
Wenn Missbrauchsschutz nötig ist, IP nur gehasht und mit rotierendem Salt speichern.

## Missbrauchsschutz

Für eine echte öffentliche Funktion einplanen:

- Honeypot-Feld gegen Bots
- Rate-Limit pro IP-Hash
- Rate-Limit pro Stück
- Kommentar-Längenlimit
- blockierte Wörter/Links als erste Moderationshilfe
- Kommentare standardmäßig `pending`
- nur aggregierte Stimmen sofort anzeigen
- Admin-Export mit Zeitstempel und Quellenlink

## UI-Plan

Neuer Bereich im Viewer:

- Tab `Mitreden`
- Filter `vor Sitzung`
- Karte/Listenansicht wie bisher
- Detailpanel pro Stück
- Buttons:
  - `Dafür`
  - `Dagegen`
  - `Unsicher`
- Auswahlfeld `Warum?`
- optionales Textfeld `Kurzer Hinweis`
- Hinweistext:

```text
Dieses Meinungsbild ist nicht amtlich und nicht verbindlich.
Es zeigt nur Rückmeldungen von Nutzerinnen und Nutzern dieser Website.
Die Entscheidung trifft der Gemeinderat.
```

## Technischer Umsetzungsplan

Phase 1: Vorbereitung im bestehenden statischen Viewer

1. DIGRA-Stücke mit zukünftiger Sitzung oder fehlendem Beschlussergebnis als `vor Sitzung` markieren.
2. Im Viewer einen Filter `vor Sitzung` ergänzen.
3. Detailansicht um einen Abschnitt `Bürgerfeedback` erweitern.
4. Lokale Demo-Rückmeldungen in `localStorage` speichern.
5. Keine Daten an einen Server senden.
6. Tests für Status, UI und Datenschutztexte ergänzen.

Phase 2: Backend-Prototyp

1. Kleinen API-Endpunkt `POST /feedback` bauen.
2. API validiert `record_id`, `stance`, Kommentar-Länge und Rate-Limit.
3. API speichert Kommentare zuerst als `pending`.
4. API stellt aggregierte Zahlen per `GET /feedback/summary?record_id=...` bereit.
5. Viewer lädt nur Aggregatdaten öffentlich.
6. Kommentare werden erst nach Moderation angezeigt.

Phase 3: Betrieb

1. Datenschutzhinweis veröffentlichen.
2. Impressum/Betreiberhinweis klären.
3. Moderationsprozess festlegen.
4. Export für Gemeinderatsklubs/Stadt/Öffentlichkeit definieren.
5. Missbrauchs- und Löschregeln dokumentieren.

## Meine Empfehlung

Zuerst Phase 1 bauen.
Damit sieht man im Produkt, wie Bürgerfeedback funktionieren würde, ohne sofort personenbezogene Daten oder Moderationspflichten zu erzeugen.

Danach entscheiden:

- Nur informatives lokales Tool behalten.
- Oder echtes öffentliches Feedback mit Backend und Datenschutztext starten.

