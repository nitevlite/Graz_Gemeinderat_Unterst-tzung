# Leitfaden fuer Einzeldokument-Zusammenfassungen

## Ziel

Aus jedem einzelnen DIGRA- oder Stadt-Graz-Archiv-Eintrag soll automatisch eine verstaendliche, neutrale und inhaltlich nuetzliche Zusammenfassung entstehen.

Die Zusammenfassung soll Leserinnen und Lesern helfen, den politischen Inhalt eines Punktes zu verstehen, ohne das ganze Dokument selbst lesen zu muessen. Sie darf deshalb nicht nur ein sehr kurzer Teaser sein. Sie soll erklaeren, worum es geht, wer etwas fordert oder fragt, welche Entscheidung dokumentiert ist und welche offenen Punkte bleiben.

Wichtig: Jeder Eintrag wird einzeln zusammengefasst. Es werden nicht mehrere Gemeinderatsstuecke gemeinsam in einem Prompt zusammengezogen, weil dabei Themen vermischt werden und Antworten zu allgemein werden.

## Grundprinzipien

- Pro KI-Aufruf wird genau ein Eintrag bearbeitet.
- Die KI nutzt nur die gelieferten Felder und den verlinkten oder extrahierten Hauptinhalt.
- Wenn eine Information fehlt, wird das klar gesagt.
- Forderungen, Fragen und Antraege einzelner Personen oder Fraktionen werden nicht als amtliche Haltung der Stadt formuliert.
- Beschlossene, nur beantragte, nur gefragte und noch offene Punkte werden klar getrennt.
- Keine Rohprotokolle, kompletten Dokumenttexte oder heruntergeladenen Quelldokumente ins Repository uebernehmen.

## 1. Dokument abrufen

Wenn ein DIGRA- oder Archivlink vorhanden ist:

- den sichtbaren Hauptinhalt des Dokuments erfassen
- Navigation, Footer, Impressum, Datenschutz, allgemeine Seitenlinks und Session-Parameter ignorieren
- Metadaten auslesen, soweit vorhanden
- Anlagen nur nennen, wenn sie vorhanden sind
- keine externen Webseiten als gelesen behaupten, wenn nur ein Link vorhanden ist

Wenn nur ein strukturierter Eintrag ohne Dokumentinhalt vorhanden ist:

- Titel, Typ, Datum, Einbringer, Geschaeftszahl, Ergebnis, Orte, Betraege, Frage-/Antwortteile und Quellenlink verwenden
- ausdruecklich kenntlich machen, wenn der Detailinhalt nicht in den lokalen Daten erfasst ist

## 2. Relevante Felder erkennen

Folgende Felder sollen erkannt oder aus vorhandenen Record-Feldern uebernommen werden:

| Feld | Bedeutung |
| --- | --- |
| Dokumenttyp | Anfrage, Antrag, Dringlichkeitsantrag, Mitteilung, Tagesordnungspunkt, Fragestunde |
| Einbringer | Person, Personen, Klub oder Fraktion, die etwas einbringen |
| Adressat | angesprochene Person oder Stelle bei Fragen |
| Datum | Sitzungs- oder Dokumentdatum |
| EZ/OZ/GZ | Geschaeftszahl oder Einlagezahl |
| Titel | Hauptthema des Eintrags |
| Hauptproblem | Was wird kritisiert, gefragt, berichtet oder gefordert? |
| Betroffene Stellen | Stadt Graz, Holding Graz, Abteilungen, Bezirke, Unternehmen, Einrichtungen |
| Forderungen oder Fragen | Was soll beantwortet, beschlossen, geaendert oder geprueft werden? |
| Ergebnisstand | Beschlossen, angenommen, abgelehnt, zugewiesen, mitgeteilt, unbekannt oder nicht erfasst |
| Umsetzungshinweise | Nur nennen, wenn sie aus den Daten belegt sind |
| Anlagen | Ob zusaetzliche Dokumente vorhanden sind |

## 3. Inhaltlich zusammenfassen

Die fachliche Zusammenfassung soll laenger und hilfreicher sein als bisher:

- 1 kurzer Einstiegssatz zum Thema
- 1 bis 3 Saetze zum politischen oder praktischen Problem
- 1 bis 3 Saetze zu Forderungen, Fragen, Argumenten oder betroffenen Stellen
- 1 Satz zum dokumentierten Ergebnis oder zum fehlenden Ergebnisstand

Richtwert: etwa 120 bis 220 Woerter, sofern genug Inhalt vorhanden ist. Bei sehr kurzen Quellen darf die Zusammenfassung kuerzer sein, soll aber trotzdem nicht leer oder generisch werden.

Die Zusammenfassung soll beantworten:

- Worum geht es?
- Wer bringt das Thema ein?
- Was ist das Problem oder Anliegen?
- Welche konkrete Frage, Forderung oder Entscheidung gibt es?
- Warum ist das politisch oder oeffentlich relevant?
- Was ist laut lokaler Datenbasis beschlossen, nur beantragt, nur gefragt oder offen?

## 4. Einfache Sprache

Die Version in einfacher Sprache ist keine zweite Kurzfassung, sondern eine leichter lesbare Erklaerung desselben Inhalts.

Sie soll:

- kurze Saetze verwenden
- schwierige Begriffe erklaeren
- keine Ironie, keine Verwaltungssprache und keine langen Nebensaetze enthalten
- klar sagen, ob etwas beschlossen wurde oder nur ein Antrag beziehungsweise eine Frage war
- wichtige Unsicherheiten einfach formulieren

Richtwert: etwa 80 bis 160 Woerter.

## 5. Leserfreundliche Tabelle

Zusaetzlich zur Zusammenfassung sollen die wichtigsten Eckdaten strukturiert vorliegen. Empfohlene Felder:

| Punkt | Inhalt |
| --- | --- |
| Dokumenttyp | ... |
| Einbringer | ... |
| Adressat | ... |
| Datum | ... |
| Geschaeftszahl | ... |
| Thema | ... |
| Problem | ... |
| Ziel | ... |
| Betroffene Stellen | ... |
| Ergebnisstand | ... |
| Quelle | ... |

Diese Tabelle kann als eigenes JSON-Feld gespeichert oder im Viewer aus strukturierten Feldern erzeugt werden.

## 6. Warum ist das interessant?

Jede Zusammenfassung soll einen Abschnitt oder ein Feld `warum_interessant` ermoeglichen.

Dieser Abschnitt erklaert:

- welche oeffentliche Bedeutung das Thema hat
- welche politischen Fragen dahinterstehen
- welche Buergerinnen und Buerger betroffen sein koennten
- ob es um Transparenz, Kontrolle, Kosten, Infrastruktur, Verkehr, Wohnen, Bildung, Klima, Gesundheit oder Verwaltung geht
- ob der Punkt Teil eines laengeren politischen Verlaufs sein koennte

Der Abschnitt darf den Eintrag einordnen, aber keine Meinung der KI als Fakt darstellen.

## 7. Fragen, Forderungen und Beschluesse extrahieren

Wenn konkrete Fragen, Antraege, Forderungen oder Beschluesse vorhanden sind, sollen sie gesondert extrahiert werden.

Format:

| Nr. | Kernpunkt | Einfach erklaert | Stand |
| --- | --- | --- | --- |
| 1 | ... | ... | beschlossen / beantragt / gefragt / offen / nicht erfasst |
| 2 | ... | ... | beschlossen / beantragt / gefragt / offen / nicht erfasst |

Dabei nicht jedes Wort kopieren, sondern den Sinn klar wiedergeben. Wichtige Einzelpunkte duerfen nicht zu einer allgemeinen Aussage zusammengezogen werden.

## 8. Verlauf und Verknuepfungen

Die Einzeldokument-Zusammenfassung darf Hinweise auf verwandte Eintraege enthalten, aber nur als getrennte Metadaten:

- moegliche Folgeeintraege
- gleiche Geschaeftszahl
- gleiche Strasse, gleicher Bezirk oder gleiche Einrichtung
- gleicher Antragsteller oder gleiche betroffene Stelle

Die eigentliche Zusammenfassung bleibt beim einzelnen Eintrag. Ein spaeterer Antwortassistent darf diese Einzelsummaries dann fuer verlaufsbezogene Fragen nutzen.

## 9. Ausgabeformat fuer die KI

Die KI soll JSON ausgeben, damit die App die Felder getrennt anzeigen und fuer Suche/RAG nutzen kann.

Empfohlenes Schema:

```json
{
  "summary": "Fachliche Zusammenfassung in 120 bis 220 Woertern.",
  "easy_language": "Erklaerung in einfacher Sprache in 80 bis 160 Woertern.",
  "why_interesting": "Warum das Thema oeffentlich oder politisch relevant ist.",
  "key_points": [
    {
      "kind": "Forderung",
      "text": "Kernpunkt ohne Rohzitat.",
      "simple": "Einfach erklaert.",
      "status": "beantragt"
    }
  ],
  "open_points": [
    "Welche Information fehlt oder in den lokalen Daten nicht belegt ist."
  ],
  "source_limits": [
    "Welche Einschraenkung die Quelle hat."
  ]
}
```

## 10. Qualitaetskontrolle

Vor dem Speichern pruefen:

- Sind Datum, Person, Fraktion, Geschaeftszahl und Dokumenttyp korrekt?
- Wird klar, ob etwas beschlossen, nur beantragt, nur gefragt oder nicht erfasst ist?
- Sind Meinung und Fakt getrennt?
- Ist die Zusammenfassung kuerzer und verstaendlicher als das Original, aber nicht inhaltsleer?
- Sind wichtige Forderungen, Fragen oder Antworten vollstaendig enthalten?
- Wurde nichts erfunden, was nicht im Dokument oder lokalen Record steht?
- Werden fehlende Antworten nicht als "keine Antwort gegeben" missverstanden?
- Sind Quellenlink, Quellenart und Datenstand nachvollziehbar?

## 11. Beispiel-Prompt fuer Codex/OpenAI

```text
Analysiere genau diesen einen Gemeinderats-Eintrag. Nutze nur die gelieferten Daten und den gelieferten Dokumentinhalt.

Extrahiere Dokumenttyp, Einbringer, Adressat, Datum, Geschaeftszahl, Titel, Hauptproblem, betroffene Stellen, konkrete Fragen oder Forderungen, Ergebnisstand und offene Punkte.

Schreibe zuerst eine fachliche Zusammenfassung fuer Leserinnen und Leser. Sie soll den Inhalt wirklich erklaeren und nicht nur in 2 Saetzen anteasern. Schreibe danach eine Version in einfacher Sprache. Erstelle ausserdem einen Abschnitt "Warum ist das interessant?" und eine Liste der konkreten Fragen, Forderungen oder Beschluesse.

Bleibe neutral. Formuliere Antraege, Anfragen und Dringlichkeitsantraege als Position oder Forderung des Einbringers, nicht als amtliche Aussage der Stadt. Unterscheide klar zwischen beschlossen, beantragt, gefragt, mitgeteilt, offen und in der lokalen Datenbasis nicht erfasst. Erfinde keine Informationen.

Antworte ausschliesslich als JSON im vorgegebenen Schema.
```

