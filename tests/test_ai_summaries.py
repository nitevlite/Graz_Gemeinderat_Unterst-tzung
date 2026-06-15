from graz_protocols.ai_summaries import annotate_record_summaries


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class FakeHttpClient:
    def __init__(self):
        self.calls: list[dict] = []

    def post(self, url: str, **kwargs: object) -> FakeResponse:
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(
            {
                "message": {
                    "content": (
                        '{"summary":"Das Stück behandelt eine Verkehrsmaßnahme und das Ergebnis der Abstimmung.",'
                        '"easy_language":"Es geht um eine Straße. Die Stadt entscheidet darüber. Das Ergebnis steht dabei."}'
                    )
                }
            }
        )


def test_annotate_record_summaries_uses_local_ollama():
    client = FakeHttpClient()
    records = [
        {
            "meeting_date": "2025-01-16",
            "title": "Unfallhäufungsstelle Marburger Straße",
            "record_type": "written_motion",
            "submitter": "Berichterstatterin: GR Beispiel, KPÖ",
            "result_text": "Verfahren: zugewiesen",
            "locations": ["Marburger Straße"],
        }
    ]

    enriched = annotate_record_summaries(
        records,
        provider="ollama",
        model="qwen2.5:7b-instruct",
        base_url="http://localhost:11434",
        http_client=client,
    )

    assert enriched[0]["ai_summary"].startswith("Das Stück behandelt")
    assert enriched[0]["ai_easy_language"].startswith("Es geht um")
    assert enriched[0]["ai_why_interesting"] == ""
    assert enriched[0]["ai_key_points"] == []
    assert enriched[0]["ai_open_points"] == []
    assert isinstance(enriched[0]["ai_source_limits"], list)
    assert client.calls[0]["url"] == "http://localhost:11434/api/chat"
    assert client.calls[0]["json"]["model"] == "qwen2.5:7b-instruct"
    assert client.calls[0]["json"]["format"] == "json"
    user_prompt = client.calls[0]["json"]["messages"][1]["content"]
    assert "Berichterstatterin: GR Beispiel, KPÖ" in user_prompt
    assert "Schreibe nicht pauschal, die Gemeinde" in user_prompt
    assert "nicht nur ein Teaser" in user_prompt


def test_annotate_record_summaries_defaults_to_free_local_provider():
    client = FakeHttpClient()
    records = [
        {
            "meeting_date": "2025-01-16",
            "title": "Parkplätze in Waltendorf",
            "record_type": "written_motion",
            "result_text": "Unbekannt",
            "source_snippet": "Der Antrag betrifft Parkplätze und die Nutzung des öffentlichen Raums.",
        }
    ]

    enriched = annotate_record_summaries(records, http_client=client)

    assert enriched[0]["ai_summary"].startswith("Der schriftliche Antrag behandelt")
    assert enriched[0]["ai_key_points"] == []
    assert not client.calls


def test_question_hour_summary_prompt_requests_answer_and_followup():
    client = FakeHttpClient()
    records = [
        {
            "meeting_date": "2025-01-16",
            "title": "Verkehrssituation Andreas-Hofer-Platz",
            "record_type": "question_hour",
            "source_snippet": "Frage: Was ist geplant? Antwort: Prüfung läuft. Zusatzfrage: Was ist mit Neutorgasse?",
            "question_parts": {
                "question": "Was ist geplant?",
                "answer": "Prüfung läuft.",
                "followup_question": "Was ist mit Neutorgasse?",
                "followup_answer": "Wird mitgeprüft.",
            },
        }
    ]

    annotate_record_summaries(records, provider="ollama", model="qwen2.5:7b-instruct", http_client=client)

    user_prompt = client.calls[0]["json"]["messages"][1]["content"]
    assert "Fragestunde" in user_prompt
    assert "Zusatzfrage" in user_prompt
    assert '"followup_answer": "Wird mitgeprüft."' in user_prompt
    assert "fasse nur deren Inhalt kurz zusammen" in user_prompt
    assert "kopiere keine" in user_prompt


def test_local_question_summary_avoids_raw_question_text():
    records = [
        {
            "meeting_date": "2026-01-16",
            "title": "ÖV-Anbindung des Grieskais",
            "record_type": "question_hour",
            "submitter": "GR. Eichberger",
            "result_text": "Unbekannt",
            "source_snippet": (
                "Frage: Werter Herr Bürgermeister, Frau Vizebürgermeisterin, liebe Kolleginnen, "
                "liebe Kollegen! In meiner Frage geht es um die ÖV-Anbindung des Grieskais."
            ),
            "question_parts": {
                "question": "Werter Herr Bürgermeister, in meiner Frage geht es um die ÖV-Anbindung des Grieskais.",
                "answer": "Werter Herr Gemeinderat! Meine Frage richtet sich an den Herrn Bürgermeister.",
                "respondent": "Bgm.-Stvin. Rücker",
            },
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert enriched[0]["ai_summary"].startswith("Die Fragestunde betrifft das Thema ÖV-Anbindung des Grieskais.")
    assert "Gefragt hat GR. Eichberger" in enriched[0]["ai_summary"]
    assert "Eine Antwort ist in der lokalen Datenbasis nicht erfasst." in enriched[0]["ai_summary"]
    assert "Frage:" not in enriched[0]["ai_summary"]
    assert "Werter Herr Bürgermeister" not in enriched[0]["ai_summary"]
    assert "Werter Herr Gemeinderat" not in enriched[0]["ai_summary"]
    assert "Meine Frage richtet sich" not in enriched[0]["ai_summary"]
    assert "Das dokumentierte Ergebnis lautet: Unbekannt" not in enriched[0]["ai_summary"]
    assert enriched[0]["ai_key_points"] == []
    assert enriched[0]["ai_open_points"] == []


def test_local_question_summary_neutralizes_deictic_answer_text():
    records = [
        {
            "meeting_date": "2011-05-12",
            "title": "Armutsbericht – weitere Schritte",
            "record_type": "question_hour",
            "submitter": "GRin. Maga Ennemoser",
            "question_parts": {
                "answer": "Es gibt einen großen Handlungsbereich im Sozialbereich von deiner Seite her.",
            },
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "von deiner Seite" not in enriched[0]["ai_summary"]
    assert "von zuständiger Seite" in enriched[0]["ai_summary"]


def test_local_question_summary_uses_concise_answered_status():
    records = [
        {
            "meeting_date": "2026-05-21",
            "title": "Frage für die Fragestunde (§ 16a GO-GR)",
            "record_type": "question_hour",
            "submitter": "GR Beispiel (ÖVP)",
            "result_text": "Gemeinderat am 21.05.2026: mündlich beantwortet",
            "votes": [
                {
                    "organ": "Gemeinderat",
                    "date": "21.05.2026",
                    "outcome": "source_available",
                    "outcome_text": "mündlich beantwortet",
                }
            ],
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "Der dokumentierte Stand lautet: mündlich beantwortet." in enriched[0]["ai_summary"]
    assert "Stand: mündlich beantwortet." in enriched[0]["ai_easy_language"]
    assert "Gemeinderat am 21.05.2026: mündlich beantwortet" not in enriched[0]["ai_summary"]
    assert "Gemeinderat am 21.05.2026: mündlich beantwortet" not in enriched[0]["ai_easy_language"]


def test_local_summary_provider_fills_missing_without_http_client():
    client = FakeHttpClient()
    records = [
        {
            "meeting_date": "2026-05-21",
            "title": "Leistungsbericht Haus Graz 2025",
            "record_type": "communication",
            "submitter": "Bearbeiterin: Dipl.-Ing. Teresa Riedenbauer",
            "result_text": "zur Kenntnis gebracht",
            "result_source": "digra",
            "business_numbers": ["3399/1"],
            "source_snippet": "Der Leistungsbericht des Haus Graz 2025 ist online verfügbar. Er bietet eine Übersicht über Finanzen, Personalressourcen und Leistungen der Abteilungen.",
        }
    ]

    enriched = annotate_record_summaries(records, provider="local", http_client=client)

    assert enriched[0]["ai_summary"].startswith("Die Mitteilung behandelt")
    assert "Leistungsbericht Haus Graz 2025" in enriched[0]["ai_summary"]
    assert "Übersicht über Finanzen" in enriched[0]["ai_summary"]
    assert enriched[0]["ai_easy_language"].startswith("Es geht um Leistungsbericht Haus Graz 2025.")
    assert not client.calls


def test_local_summary_avoids_direct_quote_blocks():
    records = [
        {
            "meeting_date": "2025-02-13",
            "title": "Nachruf Beispielperson",
            "record_type": "communication",
            "submitter": "Bearbeiterin: Beispiel",
            "result_text": "zur Kenntnis gebracht",
            "source_snippet": (
                "„Diese Person hat seit Jahrzehnten das Publikum mit einer enormen künstlerischen Spannweite verzückt.“ "
                "So würdigte der damalige Bürgermeister die Verdienste. Die Mitteilung erinnert an das Thema „Leben und Wirken“ der Person in Graz."
            ),
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "„" not in enriched[0]["ai_summary"]
    assert "“" not in enriched[0]["ai_summary"]
    assert "künstlerischen Spannweite" not in enriched[0]["ai_summary"]
    assert "erinnert an das Thema Leben und Wirken" in enriched[0]["ai_summary"]


def test_local_summary_removes_speaker_salutations_from_source_text():
    records = [
        {
            "meeting_date": "2025-07-03",
            "title": "Budgetsanierungsmaßnahmengesetz 2025",
            "record_type": "communication",
            "submitter": "GR Kurt Luttenberger",
            "result_text": "Antrag: einstimmig angenommen",
            "source_snippet": (
                "Budgetsanierungsmaßnahmengesetz 2025 GR Luttenberger: Sehr geehrte Damen und Herren, "
                "werte Gäste, ich habe das Glück, dass ich ein akkordiertes Stück berichten kann. "
                "Es geht um das zweite Budgetsanierungsmaßnahmengesetz 2025."
            ),
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "Sehr geehrte" not in enriched[0]["ai_summary"]
    assert "Sehr geehrte" not in enriched[0]["ai_easy_language"]
    assert "werte Gäste" not in enriched[0]["ai_summary"]
    assert "zweite Budgetsanierungsmaßnahmengesetz" in enriched[0]["ai_summary"]


def test_local_summary_repairs_motion_formula_and_abbreviation_cutoff():
    records = [
        {
            "meeting_date": "2026-05-21",
            "title": "Barrierefreie Haltestelle",
            "record_type": "written_motion",
            "submitter": "GR Beispiel, KPÖ",
            "result_text": "Verfahren: zugewiesen",
            "source_snippet": (
                "Originaltext des Antrages: Es wird folgender gestellt: Der Gemeinderat wolle "
                "gemäß § 45 Abs. 2 Z 16 des Statutes der Landeshauptstadt Graz beschließen: "
                "Die zuständigen Stellen sollen prüfen, ob die Haltestelle barrierefrei umgebaut werden kann."
            ),
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "Es wird folgender gestellt" not in enriched[0]["ai_summary"]
    assert "Der Gemeinderat soll beschließen" in enriched[0]["ai_summary"]
    assert "Abs." not in enriched[0]["ai_summary"]
    assert "barrierefrei umgebaut" in enriched[0]["ai_summary"]


def test_local_summary_drops_unfinished_source_tail():
    records = [
        {
            "meeting_date": "2026-06-18",
            "title": "Ferialermächtigung 2026",
            "record_type": "agenda_item",
            "submitter": "Berichterstatterin: Beispiel",
            "result_text": "Antrag: einstimmig angenommen",
            "business_numbers": ["3470/1"],
            "source_snippet": (
                "Im Sommer finden keine ordentlichen Sitzungen statt. Der Stadtsenat soll dringende Angelegenheiten behandeln. "
                "Es wird folgender gestellt: Der Gemeinderat wolle gemäß § 45 Abs. 5 des Statutes beschließen: "
                "Der Stadtsenat wird gemäß § 45 Abs. 2 Z 1, 4 bis 10, 15 und 16"
            ),
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "Der Stadtsenat soll dringende Angelegenheiten behandeln." in enriched[0]["ai_summary"]
    assert "Z 1, 4 bis 10" not in enriched[0]["ai_summary"]


def test_local_summary_uses_snippet_title_when_title_is_only_reporter():
    records = [
        {
            "meeting_date": "2026-05-21",
            "title": "Berichterstatter:in: GR Tristan Ammerer (Grüne)",
            "record_type": "agenda_item",
            "submitter": "Berichterstatterin: GR Tristan Ammerer (Grüne)",
            "result_text": "Antrag: einstimmig angenommen",
            "source_snippet": (
                "Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie: Änderung von Geschäftsordnungen "
                "I. Allgemeiner Teil Der Gemeinderat hat dazu bereits einen Antrag beschlossen."
            ),
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "Berichterstatter:in" not in enriched[0]["ai_summary"]
    assert "Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie" in enriched[0]["ai_summary"]


def test_local_summary_neutralizes_first_person_source_text_and_social_relevance():
    records = [
        {
            "meeting_date": "2026-05-21",
            "title": "Sozialamt",
            "record_type": "agenda_item",
            "submitter": "Mag. Gerhard Spath (ÖVP)",
            "result_text": "Unbekannt",
            "business_numbers": ["3403/1"],
            "source_snippet": (
                "Im Zuge meiner schriftlichen Fragebeantwortung aus dem letzten Gemeinderat wurde von deiner Seite "
                "festgehalten, dass die Leitung des Sozialamtes nicht neu ausgeschrieben werde."
            ),
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "meiner schriftlichen Fragebeantwortung" not in enriched[0]["ai_summary"]
    assert "von deiner Seite" not in enriched[0]["ai_summary"]
    assert "einer schriftlichen Fragebeantwortung" in enriched[0]["ai_summary"]
    assert "Mobilität, Verkehr" not in enriched[0]["ai_summary"]


def test_local_summary_provider_creates_extended_free_summary_schema():
    records = [
        {
            "meeting_date": "2025-10-16",
            "title": "Anwohnerparkplätze für Unternehmer in der Grünen Zone",
            "record_type": "written_motion",
            "submitter": "GR Beispiel, ÖVP",
            "result_text": "Unbekannt",
            "locations": ["Waltendorf"],
            "source_snippet": (
                "Der Antrag weist darauf hin, dass Unternehmerinnen und Unternehmer in bestimmten Bezirken "
                "Probleme mit Parkmöglichkeiten haben. Es soll geprüft werden, ob Anwohnerparkplätze auch "
                "für betroffene Betriebe geöffnet werden können. Die Regelung betrifft die Nutzung des "
                "öffentlichen Straßenraums und die Abgrenzung zwischen Bewohnerinteressen und Betrieben."
            ),
        }
    ]

    enriched = annotate_record_summaries(records, provider="local")

    assert "Unternehmerinnen und Unternehmer" in enriched[0]["ai_summary"]
    assert "Nutzung des öffentlichen Raums" in enriched[0]["ai_summary"]
    assert "Öffentlich relevant ist das" not in enriched[0]["ai_summary"]
    assert enriched[0]["ai_why_interesting"] == ""
    assert enriched[0]["ai_key_points"] == []
    assert enriched[0]["ai_open_points"] == []
