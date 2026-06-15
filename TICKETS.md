# Tickets

## Umsetzungsstand statisches MVP

Vorerst bleibt die Anwendung eine statisch erzeugte HTML-Datei. Dadurch gelten folgende Grenzen:

- Bürgeransicht und Amtsansicht sind in der Oberfläche getrennt, aber nicht produktiv serverseitig abgesichert.
- Baustellen-/Veranstaltungsentwürfe, Freigaben und Auditlog liegen browser-lokal in `localStorage`.
- Öffentliche Datenabgaben werden aus offiziellen Quellen und lokal freigegebenen Entwürfen als JSON/CSV/ICS exportiert.
- Übergabepaket, produktives Backend, echte Rollen, serverseitige Freigaben und Betriebskonzept bleiben Schlussphase.

Direkt im statischen MVP adressiert sind T-006, T-007, T-008, T-009, T-011, T-012, T-014, T-015, T-016, T-017, T-018, T-019 und T-020 jeweils soweit ohne Backend möglich.
T-013 ist als Produktivanforderung konzipiert und in der statischen Ansicht ausdrücklich nicht als erfüllt markiert; das Rollenmodell `public`, `staff`, `admin` ist backendfähig dokumentiert.
T-001 bis T-004 sind als DIGRA-/Archivimportstrecke umgesetzt. T-010 ist als Übergabedokumentation im README, DATA_POLICY, DEVELOPMENT, PROJECT_NOTES und diesem Ticketstand abgedeckt.
Neu hinzugekommen ist `digra-sync` als Standardimport ohne lokale DOCX-Protokollkopien. Der Stadt-Graz-Archiv-Assetbericht weist Jahre und Dokumenttypen aus; mit `--city-archive-assets` werden vorhandene Archivassetlinks als `Archivquelle`-Records in JSONL, SQLite und Viewer übernommen.
Mitteilungen werden als eigener Typ `communication` mit Status `noted` geführt und nicht mehr als unklare Tagesordnungspunkte gezählt. Mit `--city-protocols-dir` kann `digra-sync` aus der lokalen, ignorierten Stadt-Graz-Protokollkopie ergänzend `communication` und `question_hour` einbauen, damit die Viewerfilter `Mitteilung` und `Fragestunde` Treffer liefern.
T-005 hat eine Importstrecke `question-pdf` für PDF/TXT mit strukturierter Erkennung von Frage, Antwort, Zusatzfrage und Zusatzantwort. Die Qualitätsprüfung gegen echte lokale Alt-PDFs bleibt lokale Arbeit ohne Commit der Quellen.

## Projektvorgabe: Keine laufenden KI- oder Lizenzkosten

Für die Entwicklung ist zu beachten: Der Stadt Graz sollen neben eigenem Serverbetrieb, Hosting, Wartung und interner Administration keine laufenden externen Kosten entstehen.

Konsequenzen:
- Standardbetrieb muss ohne kostenpflichtige Cloud-KI funktionieren.
- Keine Pflicht zu externen API-Abos, SaaS-Lizenzen oder proprietären Datenquellen.
- Bevorzugt werden Open-Source-Komponenten, offene Standards und lokal/serverseitig betreibbare Modelle.
- Kostenpflichtige Dienste dürfen höchstens als optionale, austauschbare Zusatzvariante dokumentiert werden.
- Die Anwendung muss ohne KI lauffähig bleiben: Quellenanzeige, Suche, Karte und regelbasierte Prüfungen funktionieren weiterhin.

## T-001: Datenquellen auf Open-Source-Betrieb umstellen

Ziel: Die Anwendung darf ohne lokale Protokollkopien funktionieren und keine rohen Gemeinderatsdokumente voraussetzen.

Akzeptanzkriterien:
- Standardimport nutzt DIGRA als Hauptquelle.
- Stadt-Graz-Archiv wird nur über öffentliche Links/Importer ergänzt.
- Lokale Rohdateien bleiben in ignorierten Ordnern und werden nie committet.
- Viewer zeigt pro Eintrag die konkrete Quelle und den Quellenlink.

## T-002: Lokale Protokoll-Arbeitskopie aus dem Standardpfad entfernen

Ziel: Der Open-Source-Start darf nicht von `graz_protokolle_arbeitskopie/` abhängen.

Akzeptanzkriterien:
- Start-/Build-Befehle verwenden DIGRA/Archiv-Ausgaben.
- Lokale DOCX-Parsebefehle bleiben optional für interne Migration.
- README erklärt klar, dass Rohprotokolle nicht Teil des Projekts sind.

## T-003: DIGRA-Importer vervollständigen

Ziel: DIGRA soll Tagesordnung, Fragestunde, Dringliche Anträge, schriftliche Anfragen und selbständige Anträge möglichst vollständig liefern.

Akzeptanzkriterien:
- Alle relevanten DIGRA-Tabs werden importiert.
- Einträge haben Datum, Typ, Titel, Geschäftszahl, URL, Ergebnis und Abstimmungsstatus, soweit DIGRA diese ausweist.
- Fehlende Ergebnisse werden sichtbar als fehlend markiert, nicht still geschätzt.
- Automatisches Update erkennt neue Sitzungen.

## T-004: Stadt-Graz-Archivimport für alte Quellen

Ziel: Alte öffentliche Archivseiten ab 2004 werden als ergänzende Quelle nutzbar.

Akzeptanzkriterien:
- `city-assets` indexiert Archivseiten wiederaufnehmbar.
- PDF/DOC/DOCX-Links werden getrennt von reinen HTML-Archivseiten klassifiziert.
- Downloads landen nur in ignorierten Cache-Ordnern.
- Importbericht zeigt, welche Jahre und Dokumenttypen verarbeitet wurden.

## T-005: PDF-Parser für alte Fragestunden

Ziel: Alte Fragestunden-PDFs werden in strukturierte Frage-/Antwort-Einträge zerlegt.

Akzeptanzkriterien:
- PDF-Text wird reproduzierbar extrahiert.
- Frage, Antwort, Zusatzfrage und Zusatzantwort werden getrennt erkannt.
- KI-Zusammenfassungen wiederholen Frage und Antwort kurz.
- Leichte Sprache enthält ebenfalls Antwort und Zusatzantwort.
- Parser hat bereinigte Testfixtures ohne vollständige Protokolltexte.

## T-006: Admin- und Bürgeransicht trennen

Ziel: Bürger:innen sehen nur öffentliche Informationen; interne Prüf- und Planungsfunktionen sind nicht sichtbar.

Akzeptanzkriterien:
- Bürgeransicht: Karte, Baustellen/Veranstaltungen, Beschluss-/Quelleninfos, einfache Sprache.
- Amtsansicht: Baustellen prüfen, Entwürfe, Freigabe, Export, Konfliktanalyse.
- Rollenmodell ist nicht nur clientseitig versteckt, sondern backendfähig geplant.

## T-007: Mehrere zukünftige Baustellen/Veranstaltungen planen

Ziel: Beamte können mehrere geplante Maßnahmen erfassen und gemeinsam prüfen.

Akzeptanzkriterien:
- Mehrere Entwürfe mit Ort, Zeitraum, Sperrtyp, Umleitung, Priorität und Beschreibung.
- Maßnahmen können gespeichert, bearbeitet, verworfen und freigegeben werden.
- Gemeinsame Ansicht zeigt Überschneidungen nach Zeit, Ort und Verkehrsachsen.

## T-008: Konflikt- und Synergieanalyse für Baustellen

Ziel: Das System unterstützt operative Koordination statt nur Einzelfallprüfung.

Akzeptanzkriterien:
- Erkennt Konflikte mit bestehenden Baustellen, Veranstaltungen und vorgeschlagenen Umleitungen.
- Erkennt mögliche Synergien wie gemeinsame Sperrfenster, gebündelte Kommunikation oder abgestimmte Umleitungen.
- Gibt konkrete Alternativrouten und Warnhinweise mit Quellen aus.
- KI-Ergebnisse sind immer als unsicher gekennzeichnet.

## T-009: Datenmodell für amtliche Befüllung

Ziel: Die Stadt Graz kann Daten strukturiert pflegen, statt HTML/JSON manuell zu ändern.

Akzeptanzkriterien:
- Entwurf für Tabellen/API: Baustellen, Veranstaltungen, Umleitungen, Quellen, Freigaben, Auditlog.
- Import/Export in CSV/JSON.
- Änderungsverlauf für veröffentlichte Datensätze.
- Pflichtfelder und Validierungsregeln sind definiert.

## T-010: Veröffentlichungspaket für Stadt Graz

Ziel: Das Projekt kann der Stadt als nachvollziehbares Open-Source-MVP übergeben werden.

Akzeptanzkriterien:
- README mit Datenquellen, Start, Betrieb, Einschränkungen.
- DATA_POLICY mit Rohdaten-/Lizenzhinweisen.
- Demo-Datensatz ohne rohe Protokolle.
- Bekannte Grenzen und KI-Hinweise dokumentiert.

## T-011: Nice-to-have: Barrierefreie Bürgerkarte

Ziel: Die öffentliche Karte ist auch ohne Karteninteraktion nutzbar.

Akzeptanzkriterien:
- Listenansicht parallel zur Karte.
- Tastaturbedienung und Screenreader-Labels.
- Filter nach Zeitraum, Bezirk, Straße, Status und Auswirkung.
- Druck-/Teilen-Link für einzelne Baustellen.

## T-012: Nice-to-have: Benachrichtigungen und Beteiligung

Ziel: Bürger:innen können relevante Änderungen leichter verfolgen.

Akzeptanzkriterien:
- Abonnement für Straße/Bezirk/Zeitraum.
- RSS/ICS/JSON-Feed für Baustellen und Veranstaltungen.
- Änderungsdatum und Quelle pro Eintrag.
- Optionales Feedbackformular ohne personenbezogene Veröffentlichung.

## T-013: Rollen, Rechte und Zugriffsschutz

Ziel: Interne Funktionen sind technisch getrennt von der öffentlichen Bürgeransicht.

Akzeptanzkriterien:
- Rollen mindestens: `public`, `staff`, `admin`.
- Bürger:innen sehen keine Baustellenprüfung, keine Entwürfe und keine internen KI-Einschätzungen.
- Amtsfunktionen sind nicht nur im Frontend versteckt, sondern serverseitig geschützt.
- Sitzungen, Passwörter und Freigaben sind für einen produktiven Betrieb konzipiert.

## T-014: Quellenstand, Haftung und KI-Kennzeichnung

Ziel: Jede KI-Ausgabe und jede Datenanzeige macht Unsicherheit und Quellenstand klar.

Akzeptanzkriterien:
- Globaler Hinweis auf KI-generierte Inhalte bleibt sichtbar.
- Jede Zusammenfassung zeigt Quellen, Datenstand und Erzeugungszeitpunkt.
- KI-Antworten werden nicht als amtliche Entscheidung formuliert.
- Öffentliche Ansicht unterscheidet amtlich freigegebene Daten von automatisch importierten Informationen.

## T-015: Auditlog und Freigabeprozess

Ziel: Änderungen an Baustellen, Veranstaltungen und Veröffentlichungen sind nachvollziehbar.

Akzeptanzkriterien:
- Jede Änderung speichert Zeitpunkt, Benutzer, Änderungstyp und vorher/nachher.
- Entwürfe werden erst nach Freigabe öffentlich.
- Veröffentlichte Einträge können zurückgezogen oder korrigiert werden.
- Export des Auditlogs ist für interne Prüfung möglich.

## T-016: Betriebsmodell für lokale oder serverseitige KI

Ziel: Die Stadt kann entscheiden, ob KI lokal, auf einem eigenen Server oder extern betrieben wird.

Akzeptanzkriterien:
- Variantenvergleich für Ollama lokal, Ollama Server, vLLM/llama.cpp, Cloud-API und Hybridbetrieb.
- Datenschutz-, Kosten-, Wartungs- und Qualitätsauswirkungen sind dokumentiert.
- Die Anwendung nutzt eine austauschbare KI-Schnittstelle statt fest verdrahteter Ollama-Aufrufe.
- Fallback ohne KI ist möglich: Quellenanzeige und regelbasierte Konfliktprüfung bleiben nutzbar.
- Empfohlener Standard ist kostenfrei im Betrieb abseits eigener Server-/Administrationskosten.
- Cloud-KI ist nur optionale Zusatzkonfiguration, nicht Voraussetzung.

## T-017: Barrierefreiheit und öffentlicher Betrieb

Ziel: Die Bürgeransicht erfüllt grundlegende Anforderungen für Verwaltungskommunikation.

Akzeptanzkriterien:
- Karte hat gleichwertige Listenansicht.
- Bedienung per Tastatur ist möglich.
- Kontraste, Schriftgrößen und responsive Layouts sind geprüft.
- Wichtige Inhalte sind ohne Hover, Farbe oder Karte verständlich.

## T-018: Öffentliche Schnittstellen und Datenabgabe

Ziel: Freigegebene Daten können von Bürger:innen, Medien und anderen Systemen weiterverwendet werden.

Akzeptanzkriterien:
- JSON-Feed für freigegebene Baustellen/Veranstaltungen.
- CSV-Export für Tabellenarbeit.
- Optional RSS/ICS für neue oder geänderte Einträge.
- Jeder Feed enthält Lizenz-/Quellenhinweis und Aktualisierungszeitpunkt.

## T-019: Datenschutz- und Betriebsentscheidung für KI

Ziel: Vor einem Stadtbetrieb ist klar, welche Daten an welche KI-Komponente gehen dürfen.

Akzeptanzkriterien:
- Entscheidungsmatrix für personenbezogene Daten, interne Entwürfe und öffentliche Daten.
- Vorgabe, ob externe KI-Dienste erlaubt sind.
- Protokollierung von KI-Anfragen ohne unnötige personenbezogene Inhalte.
- Lösch- und Aufbewahrungsregeln für KI-Logs.
- Standardannahme: keine externen KI-Dienste und keine laufenden API-Kosten.

## T-020: Open-Source-Kosten- und Lizenzprüfung

Ziel: Vor Übergabe an die Stadt ist klar, dass der Standardbetrieb keine laufenden externen Lizenz- oder API-Kosten erzeugt.

Akzeptanzkriterien:
- Abhängigkeiten sind mit Lizenz und Einsatzzweck dokumentiert.
- Karten-, Geocoding-, KI- und Datenquellen sind auf Nutzungsbedingungen geprüft.
- Für kostenkritische Dienste gibt es lokale oder Open-Source-Alternativen.
- README enthält eine klare Aussage: Betriebskosten entstehen nur durch eigene Infrastruktur und Administration.
- CI/Testlauf prüft nicht gegen kostenpflichtige externe Dienste.

## T-021: Zusammenfassungen pro Eintrag neu definieren

Ziel: Die bisherigen sehr kurzen Ollama-Zusammenfassungen werden durch aussagekräftige Einzeldokument-Zusammenfassungen ersetzt.

Akzeptanzkriterien:
- Der Leitfaden `AI_SUMMARY_GUIDE.md` ist die fachliche Vorgabe für Prompts, Ausgabeformat und Qualitätskontrolle.
- Jeder KI-Aufruf verarbeitet genau einen Eintrag, nicht mehrere Einträge gemeinsam.
- Die fachliche Zusammenfassung erklärt Inhalt, Problem, Einbringer, Forderung oder Frage, Relevanz und Ergebnisstand.
- Die Version in einfacher Sprache erklärt denselben Inhalt mit kurzen Sätzen und ohne Verwaltungssprache.
- Anträge, Anfragen und Fragestunden werden nicht als amtliche Stadtposition formuliert.
- Fehlende Antworten oder fehlende Umsetzungsbelege werden ausdrücklich als "in der lokalen Datenbasis nicht erfasst" beschrieben.

## T-022: Strukturiertes Summary-Schema erweitern

Ziel: Zusammenfassungen sollen nicht nur zwei Textfelder sein, sondern auch maschinenlesbare Kernpunkte für Suche und Antwortassistent liefern.

Akzeptanzkriterien:
- Ausgabe enthält mindestens `ai_summary`, `ai_easy_language`, `ai_why_interesting`, `ai_key_points`, `ai_open_points` und `ai_source_limits`.
- `ai_key_points` trennt Forderungen, Fragen, Mitteilungen, Beschlüsse und offene Punkte.
- Jeder Kernpunkt hat einen Status wie `beschlossen`, `beantragt`, `gefragt`, `mitgeteilt`, `offen` oder `nicht_erfasst`.
- Viewer bleibt abwärtskompatibel mit bestehenden `ai_summary`- und `ai_easy_language`-Feldern.
- SQLite kann die neuen Felder speichern oder als JSON-Spalte verfügbar machen.

## T-023: Kostenlose Summary-Erzeugung als Standard

Ziel: Für die Erzeugung der Einzeldokument-Zusammenfassungen fallen im Standard keine externen KI- oder API-Kosten an.

Akzeptanzkriterien:
- `summaries` unterstützt weiterhin `local`, `ollama` und `openai`.
- Der Standardlauf nutzt `--ai-provider local` und erzeugt Zusammenfassungen ohne HTTP-KI-Aufruf.
- Ollama bleibt optional für lokal betriebene Modelle.
- OpenAI-Nutzung ist höchstens eine explizite Zusatzoption und nicht Empfehlung für den kostenlosen Betrieb.
- Ohne API-Key bleibt der lokale Betrieb möglich.
- Dokumentation erklärt Kosten-, Datenschutz- und Qualitätsunterschiede.
- Erzeugte Zusammenfassungen werden lokal in ignorierte Ausgabedateien geschrieben und nicht automatisch committet.

## T-024: KI-Modus ohne Startdialog konfigurierbar halten

Ziel: Beim lokalen Start gibt es keine störende Modusabfrage; KI-Verhalten wird über CLI/Startskript-Vorgaben konfiguriert.

Akzeptanzkriterien:
- CLI und Hintergrunddienst erlauben Auswahl: `none`, `local`, `ollama`, `openai`.
- Standard für Zusammenfassungen ist `local`.
- Bei `ollama` wird das Modell geprüft und eine verständliche Fehlermeldung angezeigt, falls es fehlt.
- Bei `openai` wird geprüft, ob `OPENAI_API_KEY` gesetzt ist.
- Die App zeigt im Viewer den verwendeten KI-Modus und Datenstand.
- Der Standard bleibt ohne externe laufende Kosten lauffähig.

## T-025: Zusammenfassungs-Evaluation mit Goldfragen

Ziel: Die Qualität der neuen Zusammenfassungen wird messbar gegen typische Nutzerfragen geprüft.

Akzeptanzkriterien:
- Es gibt bereinigte Testfälle ohne rohe Protokolltexte.
- Testfragen umfassen mindestens Parkplätze, Baustellen, Verkehr, Wohnen, Kosten, Transparenz und konkrete Bezirke.
- Erwartet wird nicht Wortgleichheit, sondern korrekte Trennung von Beschluss, Antrag, Frage, Mitteilung und offenem Stand.
- Beispielproblem "Was ist bezüglich Parkplätze beschlossen und umgesetzt worden?" ist als Evaluationsfall enthalten.
- Falsche Behauptungen über Umsetzung oder fehlende Antworten führen zu einem Testfehler oder Audit-Hinweis.

## T-026: Antwortassistent auf RAG statt einfachem Ollama-Chat umbauen

Ziel: Die Frage-KI soll Antworten aus gut gerankten Quellen, Einzelsummaries und Kernpunkten bauen statt aus zu grobem Trefferkontext.

Akzeptanzkriterien:
- Nutzerfrage wird zuerst lokal analysiert: Thema, Zeitraum, Bezirk, Strasse, Dokumenttyp und gewünschter Ergebnisstand.
- Retrieval nutzt Titel, Orte, Geschäftszahlen, Ergebnis, Summary, einfache Sprache und `ai_key_points`.
- Quellen werden nach direkter Relevanz priorisiert, nicht nur nach ähnlichen Wörtern.
- Antwort trennt "beschlossen/umgesetzt", "beantragt", "gefragt", "mitgeteilt" und "nicht belegt".
- Jede Aussage verweist auf konkrete Quellen.
- Wenn die Quellen keine Umsetzung belegen, sagt die Antwort das klar, statt aus offenen Anträgen eine Umsetzung abzuleiten.

## T-027: Verlaufserkennung über verwandte Einträge

Ziel: Die App erkennt, wenn mehrere Einträge zu demselben politischen Thema gehören.

Akzeptanzkriterien:
- Verknüpfung über Geschäftszahl, Titelähnlichkeit, Orte, Einbringer, betroffene Stellen und Thema.
- Ein Folgeverlauf kann z. B. Antrag -> Ausschusszuweisung -> Beschluss -> spätere Mitteilung darstellen.
- Die Verlaufserkennung bleibt überprüfbar und nennt die Verknüpfungsgründe.
- Der Antwortassistent nutzt diese Verläufe, um eigene Anträge und spätere Beschlüsse besser auseinanderzuhalten.

## T-028: Eigenes Modell nur als spätere Option prüfen

Ziel: Ein eigenes Modell wird nicht vorschnell trainiert, sondern als spätere Option gegen RAG und bessere Summaries abgewogen.

Akzeptanzkriterien:
- Dokumentierter Variantenvergleich: besseres lokales Modell, OpenAI-Provider, RAG mit Embeddings, Feintuning/LoRA, vollständiges eigenes Modell.
- Empfehlung: zuerst RAG und hochwertige Einzelsummaries, danach erst Feintuning prüfen.
- Datenschutz, Hardwarebedarf, Wartung, Kosten und Qualitätsrisiko sind beschrieben.
- Kein Training auf rohen Protokollen im Git; Trainingsdaten bleiben bereinigte, freigegebene Ableitungen.
- Eigenes Modell wird nur verfolgt, wenn Evaluation zeigt, dass RAG plus gute Modelle nicht reicht.

## T-029: Lokaler Embedding-Index für semantische Suche

Ziel: Die App findet relevante Einträge auch dann, wenn Nutzer andere Wörter verwenden als die Dokumente.

Akzeptanzkriterien:
- Embeddings werden aus Titel, strukturierten Feldern, Summary, einfacher Sprache und Kernpunkten erzeugt.
- Standard kann lokal/serverseitig mit Open-Source-Embeddingmodell laufen.
- Index wird aus ignorierten Ausgabedaten erzeugt und nicht mit rohen Quellen committet.
- Keyword-Suche und semantische Suche werden kombiniert.
- Quellenranking ist nachvollziehbar und kann im Audit angezeigt werden.

## T-030: Viewer-Anzeige für bessere KI-Zusammenfassungen

Ziel: Die neuen Zusammenfassungen werden im Viewer so angezeigt, dass Bürgerinnen und Bürger den Stand schnell verstehen.

Akzeptanzkriterien:
- Detailansicht zeigt fachliche Zusammenfassung, einfache Sprache, "Warum ist das interessant?", Kernpunkte und offene Punkte.
- Ergebnisstand und Quellenlink bleiben direkt sichtbar.
- KI-Hinweis bleibt sichtbar und verständlich.
- Lange Summary-Blöcke sind aufklappbar, aber nicht so versteckt, dass der Nutzen verloren geht.
- Alte Einträge ohne neue Felder bleiben lesbar.
