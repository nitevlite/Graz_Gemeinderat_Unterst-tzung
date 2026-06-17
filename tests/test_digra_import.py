from bs4 import BeautifulSoup

from graz_protocols.digra_import import (
    DigraEntry,
    best_digra_title,
    canonical_digra_url,
    dedupe_digra_entries,
    digra_entries_to_records,
    enrich_records_with_digra,
    fetch_digra_result,
    find_best_digra_entry,
    import_exporter,
    extract_digra_record_type,
    parse_digra_list_metadata,
)
from graz_protocols.parser import AgendaRecord
from graz_protocols.viewer import viewer_record


class FakeExporter:
    def __init__(self, html: str):
        self.html = html

    def fetch_soup(self, session, url):  # noqa: ANN001
        return BeautifulSoup(self.html, "html.parser")


def test_digra_written_motion_without_result_is_assigned():
    entry = DigraEntry(
        meeting_date="2026-05-21",
        meeting_number="58",
        record_type="written_motion",
        section="Selbständige Anträge",
        order_in_type=1,
        agenda_item_no=1,
        business_number="123/2026",
        title="Umleitung bei Baustellen koordinieren",
        url="https://digra.graz.at/document?ref=test",
        status="unknown",
        result_text="",
        raw_result_text="",
        votes=[],
    )

    records = digra_entries_to_records([entry])

    assert records[0].status == "assigned"
    assert records[0].result_text == "Verfahren: zugewiesen"
    assert records[0].raw_result_text == "Der geschäftsordnungsmäßigen Behandlung zugewiesen."


def test_digra_entries_extract_amounts_from_title_and_snippet():
    entry = DigraEntry(
        meeting_date="2026-05-21",
        meeting_number="58",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=1,
        agenda_item_no=1,
        business_number="123/2026",
        title="Projektgenehmigung über € 125.000,-",
        url="https://digra.graz.at/document?ref=test",
        status="accepted_unanimous",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="einstimmig angenommen",
        votes=[],
        source_snippet="Im Motivenbericht ist ein Finanzmittelbedarf von € 75.000,- angeführt.",
    )

    records = digra_entries_to_records([entry])

    assert records[0].amounts == ["€ 125.000,-", "€ 75.000,-"]


def test_digra_entries_keep_attachment_titles():
    entry = DigraEntry(
        meeting_date="2026-05-21",
        meeting_number="58",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=1,
        agenda_item_no=1,
        business_number="123/2026",
        title="Stadtentwicklung",
        url="https://digra.graz.at/document?ref=test",
        status="accepted_unanimous",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="einstimmig angenommen",
        votes=[],
        attachment_titles=["2 - Mitterstraße - Entwicklungsplan"],
    )

    records = digra_entries_to_records([entry])

    assert records[0].attachment_titles == ["2 - Mitterstraße - Entwicklungsplan"]


def test_digra_list_metadata_uses_betreff_instead_of_document_type():
    lines = [
        "2299/1",
        "Anfrage an Bürgermeister:in (§ 16 GO-GR)",
        "Betreff: Kosten- und Nutzenbewertung neuer Ampelanlagen in Graz",
        "Antragsteller:in(nen): Clubobfrau Anna Hopper (ÖVP)",
        "Regierungsmitglied(er): Bürgermeisterin Elke Kahr (KPÖ)",
    ]

    metadata = parse_digra_list_metadata(lines)
    result = fetch_digra_result(
        FakeExporter(
            """
            <html><body><div class="preview">
              <p>Anfrage an Bürgermeister:in (§ 16 GO-GR)</p>
              <p>Datum:</p>
              <p>11.12.2025</p>
              <p>Kosten- und Nutzenbewertung neuer Ampelanlagen in Graz</p>
            </div></body></html>
            """
        ),
        session=None,
        url="https://digra.graz.at/document?ref=test",
    )

    assert metadata.title == "Kosten- und Nutzenbewertung neuer Ampelanlagen in Graz"
    assert metadata.submitter == "Clubobfrau Anna Hopper (ÖVP)"
    assert metadata.addressee == "Bürgermeisterin Elke Kahr (KPÖ)"
    assert best_digra_title(lines, result, metadata) == "Kosten- und Nutzenbewertung neuer Ampelanlagen in Graz"


def test_digra_record_type_uses_detail_document_heading_like_export_tool():
    assert extract_digra_record_type(["Frage für die Fragestunde (§ 16a GO-GR)"]) == "question_hour"
    assert extract_digra_record_type(["Mitteilung von Bürgermeister:in"]) == "communication"
    assert extract_digra_record_type(["Anfrage an Bürgermeister:in (§ 16 GO-GR)"]) == "written_question"
    assert extract_digra_record_type(["Selbständiger Antrag (§ 17 GO-GR)"]) == "written_motion"
    assert extract_digra_record_type(["Dringlicher Antrag (§ 18 GO-GR)"]) == "urgent_motion"
    assert extract_digra_record_type(["Abänderungsantrag"]) == "amendment_motion"
    assert extract_digra_record_type(["Zusatzantrag"]) == "additional_motion"
    assert extract_digra_record_type(["Bericht an den Gemeinderat"]) == "agenda_item"


def test_digra_entries_preserve_addressee_for_viewer():
    entry = DigraEntry(
        meeting_date="2025-12-11",
        meeting_number="55",
        record_type="written_question",
        section="Anfragen an Bürgermeister:in",
        order_in_type=1,
        agenda_item_no=1,
        business_number="2299/1",
        title="Kosten- und Nutzenbewertung neuer Ampelanlagen in Graz",
        url="https://digra.graz.at/document?ref=test",
        status="unknown",
        result_text="",
        raw_result_text="",
        votes=[],
        submitter="Clubobfrau Anna Hopper (ÖVP)",
        addressee="Bürgermeisterin Elke Kahr (KPÖ)",
    )

    record = digra_entries_to_records([entry])[0]
    display = viewer_record(record.__dict__)

    assert record.addressee == "Bürgermeisterin Elke Kahr (KPÖ)"
    assert display["titel"] == "Kosten- und Nutzenbewertung neuer Ampelanlagen in Graz"
    assert display["einbringer"] == "Clubobfrau Anna Hopper (ÖVP)"
    assert display["adressat"] == "Bürgermeisterin Elke Kahr (KPÖ)"


def test_digra_list_metadata_handles_multiline_betreff_and_reporter():
    metadata = parse_digra_list_metadata(
        [
            "Bericht an den Gemeinderat",
            "Betreff:",
            "Holding Graz- Kommunale Dienstleistungen GmbH;",
            "Jahresabschluss 2025",
            "Regierungsmitglied(er): Stadtrat Manfred Eber (KPÖ)",
            "Berichterstatter:in: Klubobfrau Dipl.-Ing. (FH) Daniela Schlüsselberger (SPÖ)",
        ]
    )

    assert metadata.title == "Holding Graz- Kommunale Dienstleistungen GmbH; Jahresabschluss 2025"
    assert metadata.reporter == "Berichterstatterin: Klubobfrau Dipl.-Ing. (FH) Daniela Schlüsselberger (SPÖ)"
    assert metadata.addressee == "Stadtrat Manfred Eber (KPÖ)"


def test_extracts_result_only_from_digra_decision_note():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 2257/1</title></head>
      <body>
        <div class="preview">
          <p>ANTRAG</p>
          <p>Der Gemeinderat wolle beschließen: Beispieltext.</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 11.12.2025</p>
          <p>mehrheitlich angenommen</p>
          <p>Anmerkungen zur Abstimmung:</p>
          <p>Die Dringlichkeit wurde mehrheitlich angenommen; Zustimmung: KPÖ, Grüne, KFG, NEOS</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.status == "accepted_majority"
    assert result.result_text == "Gemeinderat am 11.12.2025: mehrheitlich angenommen\nZustimmung: KPÖ, Grüne, KFG, NEOS"
    assert result.votes[0]["approval"] == ["KPÖ", "Grüne", "KFG", "NEOS"]
    assert "Der Gemeinderat wolle beschließen" not in result.raw_result_text


def test_extracts_committee_and_council_decision_notes_separately():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 781/1</title></head>
      <body>
        <div class="preview">
          <p>Tagesordnungspunkt</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Finanzstück Beispiel</p>
          <p>Beschlussvermerk</p>
          <p>Ausschuss für Finanzen, Beteiligungen und Immobilien</p>
          <p>am 12.05.2026</p>
          <p>einstimmig angenommen</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>mehrheitlich angenommen</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.status == "accepted_majority"
    assert "Ausschuss für Finanzen, Beteiligungen und Immobilien am 12.05.2026: einstimmig angenommen" in result.result_text
    assert "Gemeinderat am 21.05.2026: mehrheitlich angenommen" in result.result_text
    assert result.votes[0]["organ"] == "Ausschuss für Finanzen, Beteiligungen und Immobilien"
    assert result.votes[1]["organ"] == "Gemeinderat"


def test_detects_question_hour_with_oral_answer_from_digra():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 999/1</title></head>
      <body>
        <div class="preview">
          <p>Fragestunde</p>
          <p>Fragesteller:in:</p>
          <p>GR Beispiel (NEOS)</p>
          <p>Frage 2: Radweg Beispiel (GR Beispiel, NEOS, an StRin. Muster, Grüne)</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>mündlich beantwortet</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.record_type_override == "question_hour"
    assert result.status == "source_available"
    assert result.result_text == "Gemeinderat am 21.05.2026: mündlich beantwortet"
    assert result.votes[0]["outcome_text"] == "mündlich beantwortet"


def test_detects_question_hour_with_oral_answer_from_real_digra_document_layout():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3402/1</title></head>
      <body>
        <div class="preview">
          <h1>Frage für die Fragestunde (§ 16a GO-GR)</h1>
          <div><b>Antragsteller:in(nen): </b>Clubobfrau Anna Hopper (ÖVP)</div>
          <div><b>Regierungsmitglied(er): </b>Stadtrat Manfred Eber (KPÖ)</div>
          <div>EZ/OZ: 3402/1</div>
          <div><b>Fraktion:</b></div>
          <div>ÖVP</div>
          <div><b>Datum:</b></div>
          <div>21.05.2026</div>
          <div><b>Park and Ride Murpark</b></div>
          <p>Es wird folgende<br /><strong>ANFRAGE</strong><br />gestellt:</p>
          <p>Wann wird der angekündigte Planungsbeschluss für den Ausbau der Park-&amp;-Ride-Anlage Murpark dem Gemeinderat vorgelegt?</p>
          <p><b>Beschlussvermerk</b></p>
          <div>
            <p>Gemeinderat am 21.05.2026</p>
            <p>mündlich beantwortet</p>
            <p>Schriftführer:in: Lidija Fink</p>
          </div>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")
    record = digra_entries_to_records(
        [
            DigraEntry(
                meeting_date="2026-05-21",
                meeting_number="58",
                record_type=result.record_type_override or "agenda_item",
                section="Fragestunde",
                order_in_type=15,
                agenda_item_no=15,
                business_number="3402/1",
                title=best_digra_title([], result),
                url="https://digra.graz.at/document?ref=test",
                status=result.status,
                result_text=result.result_text,
                raw_result_text=result.raw_result_text,
                votes=result.votes,
                submitter=result.submitter,
                source_snippet=result.source_snippet,
            )
        ]
    )[0]

    assert result.record_type_override == "question_hour"
    assert result.subject_title == "Park and Ride Murpark"
    assert result.status == "source_available"
    assert result.result_text == "Gemeinderat am 21.05.2026: mündlich beantwortet"
    assert result.votes[0]["outcome_text"] == "mündlich beantwortet"
    assert record.record_type == "question_hour"
    assert viewer_record(record.__dict__)["titel"] == "Park and Ride Murpark"
    assert viewer_record(record.__dict__)["status"] == "mündlich beantwortet"


def test_detects_parkleitsystem_question_hour_with_oral_answer_from_real_digra_document_layout():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3401/1</title></head>
      <body>
        <div class="preview">
          <h1>Frage für die Fragestunde (§ 16a GO-GR)</h1>
          <div><b>Antragsteller:in(nen): </b>GR Tristan Ammerer (Grüne)</div>
          <div><b>Regierungsmitglied(er): </b>Stadtrat Kurt Hohensinner, MBA (ÖVP)</div>
          <div>EZ/OZ: 3401/1</div>
          <div><b>Fraktion:</b></div>
          <div>Grüne</div>
          <div><b>Datum:</b></div>
          <div>21.05.2026</div>
          <div><b style="white-space: pre-line;">Parkleitsystem</b></div>
          <p>Deshalb stelle ich dir folgende Frage:</p>
          <p>Wie und wann willst du einen Entwurf zur Diskussion vorlegen?</p>
          <p><b>Beschlussvermerk</b></p>
          <div>
            <p>Gemeinderat am 21.05.2026</p>
            <p>mündlich beantwortet</p>
            <p>Schriftführer:in: Lidija Fink</p>
          </div>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")
    record = digra_entries_to_records(
        [
            DigraEntry(
                meeting_date="2026-05-21",
                meeting_number="58",
                record_type=result.record_type_override or "agenda_item",
                section="Fragestunde",
                order_in_type=10,
                agenda_item_no=10,
                business_number="3401/1",
                title=best_digra_title([], result),
                url="https://digra.graz.at/document?ref=test",
                status=result.status,
                result_text=result.result_text,
                raw_result_text=result.raw_result_text,
                votes=result.votes,
                submitter=result.submitter,
                source_snippet=result.source_snippet,
            )
        ]
    )[0]

    assert result.record_type_override == "question_hour"
    assert result.subject_title == "Parkleitsystem"
    assert result.status == "source_available"
    assert result.result_text == "Gemeinderat am 21.05.2026: mündlich beantwortet"
    assert record.record_type == "question_hour"
    assert viewer_record(record.__dict__)["status"] == "mündlich beantwortet"


def test_detects_question_hour_addressee_and_oral_answer_from_april_2026_layout():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3128/1</title></head>
      <body>
        <div class="preview">
          <h1>Frage für die Fragestunde (§ 16a GO-GR)</h1>
          <div><b>Antragsteller:in(nen): </b>Klubobmann Karl Dreisiebner (Grüne)</div>
          <div><b>Regierungsmitglied(er): </b>Stadtrat Manfred Eber (KPÖ)</div>
          <div>EZ/OZ: 3128/1</div>
          <div><b>Datum:</b></div>
          <div>23.04.2026</div>
          <div><b>Auszahlung. Zweckwidmung. Verzicht. Was wurde aus den Worten über die Nachzahlung der seit 2013 nicht ausbezahlten Geldmittel aus dem Titel „Parteienförderung“?</b></div>
          <p>Es wird folgende Anfrage gestellt.</p>
          <p><b>Beschlussvermerk</b></p>
          <div>
            <p>Gemeinderat am 23.04.2026</p>
            <p>mündlich beantwortet</p>
            <p>Schriftführer:in: Lidija Fink</p>
          </div>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(
        FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=6edccaa0-f82c-4d14-99cb-c9757023cdb1"
    )
    record = digra_entries_to_records(
        [
            DigraEntry(
                meeting_date="2026-04-23",
                meeting_number="57",
                record_type=result.record_type_override or "agenda_item",
                section="Fragestunde",
                order_in_type=1,
                agenda_item_no=1,
                business_number="3128/1",
                title=best_digra_title([], result),
                url="https://digra.graz.at/document?ref=6edccaa0-f82c-4d14-99cb-c9757023cdb1",
                status=result.status,
                result_text=result.result_text,
                raw_result_text=result.raw_result_text,
                votes=result.votes,
                submitter=result.submitter,
                addressee=result.addressee,
                source_snippet=result.source_snippet,
            )
        ]
    )[0]
    display = viewer_record(record.__dict__)

    assert result.record_type_override == "question_hour"
    assert result.subject_title.startswith("Auszahlung. Zweckwidmung. Verzicht.")
    assert result.status == "source_available"
    assert result.result_text == "Gemeinderat am 23.04.2026: mündlich beantwortet"
    assert result.submitter == "Klubobmann Karl Dreisiebner (Grüne)"
    assert result.addressee == "Stadtrat Manfred Eber (KPÖ)"
    assert display["status"] == "mündlich beantwortet"
    assert display["einbringer"] == "Klubobmann Karl Dreisiebner (Grüne)"
    assert display["adressat"] == "Stadtrat Manfred Eber (KPÖ)"


def test_extracts_long_title_from_real_digra_report_layout():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 1887/1</title></head>
      <body>
        <div class="preview">
          <h1>Bericht an den Gemeinderat</h1>
          <div><b>Geschäftszahl(en): </b>A 8 - 021515/2006-0361, A 8 - 020081/2006-390</div>
          <div><b>Vorberatendes Organ: </b>Ausschuss für Finanzen, Beteiligungen und Immobilien</div>
          <div><b>Regierungsmitglied(er): </b>Stadtrat Manfred Eber (KPÖ)</div>
          <div>EZ/OZ: 1887/1</div>
          <div><b>Datum:</b></div>
          <div>13.11.2025</div>
          <div><b>Berichterstatter:in:</b></div>
          <div>Dipl.-Ing. Nenad Savic, BSc (KPÖ)</div>
          <div><b style="white-space: pre-line;">GBG Gebäude- u. Baumanagement Graz GmbH (kurz: GBG)
          Festlegung des Prozederes des Auswahlverfahrens zur Bestellung der Geschäftsführung;
          Stimmrechtsermächtigung für den Vertreter der Stadt Graz gem § 87 Abs 4 des Statutes der Landstadt Graz 1967; Umlaufbeschluss</b></div>
          <p>Die Gesellschafterstruktur der GBG stellt sich wie folgt dar:</p>
          <p><b>Beschlussvermerk</b></p>
          <div>
            <p>Ausschuss für Finanzen, Beteiligungen und Immobilien am 05.11.2025</p>
            <p>einstimmig angenommen</p>
          </div>
          <div>
            <p>Gemeinderat am 13.11.2025</p>
            <p>mehrheitlich angenommen</p>
          </div>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.subject_title == (
        "GBG Gebäude- u. Baumanagement Graz GmbH (kurz: GBG) "
        "Festlegung des Prozederes des Auswahlverfahrens zur Bestellung der Geschäftsführung; "
        "Stimmrechtsermächtigung für den Vertreter der Stadt Graz gem § 87 Abs 4 des Statutes der Landstadt Graz 1967; Umlaufbeschluss"
    )
    assert best_digra_title([], result) == result.subject_title
    assert "Gemeinderat am 13.11.2025: mehrheitlich angenommen" in result.result_text
    assert "Ausschuss für Finanzen, Beteiligungen und Immobilien am 05.11.2025: einstimmig angenommen" in result.result_text


def test_digra_subject_title_skips_leading_pres_reference_lines():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3365/1</title></head>
      <body>
        <div class="preview">
          <h1>Mitteilung von Bürgermeister:in</h1>
          <div>EZ/OZ: 3365/1</div>
          <div><b>Datum:</b></div>
          <div>21.05.2026</div>
          <div><b style="white-space: pre-line;">Präs-038781/2026
          Präs-007862/2026
          Präs-007863/2026
          Genehmigung der Protokolle:
          Protokolle der öffentlichen und nichtöffentlichen Sitzung vom 12. Februar 2026</b></div>
          <p>Die Protokolle der öffentlichen und nichtöffentlichen Sitzung vom 12. Februar 2026 wurden überprüft.</p>
          <p><b>Beschlussvermerk</b></p>
          <div>
            <p>Gemeinderat am 21.05.2026</p>
            <p>einstimmig angenommen</p>
          </div>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.subject_title == (
        "Genehmigung der Protokolle: "
        "Protokolle der öffentlichen und nichtöffentlichen Sitzung vom 12. Februar 2026"
    )
    assert best_digra_title([], result) == result.subject_title
    assert not result.subject_title.startswith("Präs-")
    assert result.source_snippet.startswith("Die Protokolle der öffentlichen")
    assert "Gemeinderat am 21.05.2026: einstimmig angenommen" in result.result_text


def test_digra_protocol_approval_from_may_2026_is_communication_with_clean_title():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3364/1</title></head>
      <body>
        <div class="preview">
          <h1>Mitteilung von Bürgermeister:in</h1>
          <div>EZ/OZ: 3364/1</div>
          <div><b>Datum:</b></div>
          <div>21.05.2026</div>
          <div><b style="white-space: pre-line;">Präs-038781/2026
          Präs-002482/2026
          Präs-002484/2026
          Genehmigung der Protokolle:
          Protokolle der öffentlichen und nichtöffentlichen Sitzung vom 22. Jänner 2026</b></div>
          <p>Die Protokolle der öffentlichen und nichtöffentlichen Sitzung vom 22. Jänner 2026 wurden überprüft.</p>
          <p><b>Beschlussvermerk</b></p>
          <div>
            <p>Gemeinderat am 21.05.2026</p>
            <p>einstimmig angenommen</p>
          </div>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.record_type_override == "communication"
    assert result.subject_title == (
        "Genehmigung der Protokolle: "
        "Protokolle der öffentlichen und nichtöffentlichen Sitzung vom 22. Jänner 2026"
    )
    assert not result.subject_title.startswith("Präs-")
    assert "Gemeinderat am 21.05.2026: einstimmig angenommen" in result.result_text


def test_extracts_digra_submitter_from_document_preview():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3397/1</title></head>
      <body>
        <div class="preview">
          <p>Dringlicher Antrag (§ 18 GO-GR)</p>
          <p>Antragsteller:in(nen):</p>
          <p>GR Tristan Ammerer (Grüne)</p>
          <p>EZ/OZ: 3397/1</p>
          <p>Lärmblitzer-Piloten auch in der Steiermark</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>mehrheitlich angenommen</p>
          <p>Anmerkungen zur Abstimmung:</p>
          <p>Dringlichkeit wurde mehrheitlich angenommen. Zustimmung: KPÖ, ÖVP, Grüne; dagegen: KFG</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.submitter == "GR Tristan Ammerer (Grüne)"
    assert result.status == "accepted_majority"
    assert "Dagegen: KFG" in result.result_text


def test_extracts_digra_reporter_from_agenda_document_preview():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3420/1</title></head>
      <body>
        <div class="preview">
          <p>Tagesordnungspunkt</p>
          <p>Bearbeiter:in:</p>
          <p>Dipl.-Ing.in Heike Schütz-Krammer, MA</p>
          <p>Berichterstatter:in:</p>
          <p>GR Anna Slama (Grüne)</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Beispiel Tagesordnungspunkt</p>
          <p>Freigaben / Unterschriften:</p>
          <p>Mag. Beispiel Person</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>einstimmig angenommen</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.submitter == "Berichterstatterin: GR Anna Slama (Grüne)"
    assert result.status == "accepted_unanimous"


def test_best_digra_title_uses_document_snippet_when_tab_title_is_only_reporter():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3067/1</title></head>
      <body>
        <div class="preview">
          <p>Tagesordnungspunkt</p>
          <p>Berichterstatter:in:</p>
          <p>GR Tristan Ammerer (Grüne)</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie (Konvent Bezirksdemokratie): Änderung von Geschäftsordnungen / Petition an den Landesgesetzgeber</p>
          <p>I. Allgemeiner Teil</p>
          <p>Der Gemeinderat hat in seiner Sitzung einen Dringlichkeitsantrag beschlossen.</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>einstimmig angenommen</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")
    title = best_digra_title(["Berichterstatter:in: GR Tristan Ammerer (Grüne)"], result)

    assert title == (
        "Umsetzung der Vorschläge zur Stärkung der Grazer Bezirksdemokratie (Konvent Bezirksdemokratie): "
        "Änderung von Geschäftsordnungen / Petition an den Landesgesetzgeber"
    )


def test_detects_digra_communication_with_editor_and_noted_result():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3399/1</title></head>
      <body>
        <div class="preview">
          <p>Mitteilung an den Gemeinderat (§ 15 GO-GR)</p>
          <p>Bearbeiter:in:</p>
          <p>Dipl.-Ing. Teresa Riedenbauer</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Leistungsbericht Haus Graz 2025</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>zur Kenntnis gebracht</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.record_type_override == "communication"
    assert result.submitter == "Bearbeiterin: Dipl.-Ing. Teresa Riedenbauer"
    assert result.status == "noted"
    assert result.result_text == "Gemeinderat am 21.05.2026: zur Kenntnis gebracht"


def test_extracts_multiline_digra_subject_and_document_snippet():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3366/1</title></head>
      <body>
        <div class="preview">
          <p>Mitteilung an den Gemeinderat (§ 15 GO-GR)</p>
          <p>Bearbeiter:in:</p>
          <p>Mag. Dr. Verena Binder</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Antrag auf Aufnahme eines Stückes auf die Tagesordnung:</p>
          <p>Städtische Tagesbetreuung Graz GmbH</p>
          <p>Einrichtung eines Aufsichtsrats und Bestellung von Vertretern der Stadt Graz</p>
          <p>Antrag auf Aufnahme eines Stückes auf die Tagesordnung der Gemeinderatssitzung vom 21.05.2026</p>
          <p>Frau GRin Daniela Gamsjäger-Katzensteiner, BA (KPÖ) stellt den Antrag gemäß § 19 Abs. 3 der Geschäftsordnung des Gemeinderates, das Stück laut Anlage mit obigem Betreff auf die Tagesordnung zu nehmen.</p>
          <p>Ein Antrag gemäß § 19 Abs. 3 GO-GR war deshalb erforderlich, weil die Frage, welche Personen für die Wahl in den Aufsichtsrat vorgeschlagen werden sollen, erst kurzfristig geklärt werden konnte.</p>
          <p>Anlagen:</p>
          <p>3371_1-Bericht.pdf</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>einstimmig angenommen</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.subject_title == (
        "Städtische Tagesbetreuung Graz GmbH "
        "Einrichtung eines Aufsichtsrats und Bestellung von Vertretern der Stadt Graz"
    )
    assert "Gamsjäger-Katzensteiner" in result.source_snippet
    assert "erst kurzfristig geklärt" in result.source_snippet


def test_digra_subject_title_stops_before_body_intro():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 100/1</title></head>
      <body>
        <div class="preview">
          <p>Anfrage an Bürgermeister:in (§ 16 GO-GR)</p>
          <p>Antragsteller:in(nen):</p>
          <p>Sabine Reininghaus (NEOS)</p>
          <p>EZ/OZ: 100/1</p>
          <p>Fraktion:</p>
          <p>NEOS</p>
          <p>Datum:</p>
          <p>13.02.2025</p>
          <p>Areal der Rösselmühle in seiner Einzigartigkeit bewahren</p>
          <p>Seit mehreren Jahren</p>
          <p>beobachten viele Anrainer:innen und Grazer:innen mit großem Interesse, was mit dem Areal der Rösselmühle geschehen soll.</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.subject_title == "Areal der Rösselmühle in seiner Einzigartigkeit bewahren"
    assert result.source_snippet.startswith("Seit mehreren Jahren beobachten")


def test_digra_subject_title_does_not_use_body_text_when_heading_is_missing():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 100/1</title></head>
      <body>
        <div class="preview">
          <p>Bericht an den Gemeinderat</p>
          <p>Datum:</p>
          <p>13.02.2025</p>
          <p>Die Abteilung für Verkehrsplanung bringt einen Antrag im Gemeinderat ein.</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat am 13.02.2025</p>
          <p>mehrheitlich angenommen</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.subject_title == ""
    assert result.source_snippet.startswith("Die Abteilung für Verkehrsplanung bringt")


def test_digra_subject_title_skips_reporter_lines_after_date():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3301/1</title></head>
      <body>
        <div class="preview">
          <p>Bericht an den Gemeinderat</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Berichterstatter:in:</p>
          <p>GR Tristan Ammerer (Grüne)</p>
          <p>Zuzahlung zum Grundstücksankauf Land Steiermark zum Zwecke der Errichtung der P+R Anlage Steinberg</p>
          <p>Budgetvorsorge iHv. € 150.000,- für 2026 im ICF der Abteilung für Verkehrsplanung</p>
          <p>Die Abteilung für Verkehrsplanung bringt mit EZ/OZ: 3232/1 bzw. GZ: A10/8-24390/2026/0001 am 21.05.2026 einen Antrag im Gemeinderat ein.</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.subject_title == (
        "Zuzahlung zum Grundstücksankauf Land Steiermark zum Zwecke der Errichtung der P+R Anlage Steinberg "
        "Budgetvorsorge iHv. € 150.000,- für 2026 im ICF der Abteilung für Verkehrsplanung"
    )
    assert result.source_snippet.startswith("Die Abteilung für Verkehrsplanung bringt")


def test_digra_subject_title_stops_at_background_heading():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3232/1</title></head>
      <body>
        <div class="preview">
          <p>Bericht an den Gemeinderat</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Berichterstatter:in:</p>
          <p>GR Christian Sikora (KPÖ)</p>
          <p>Zuzahlung zum Grundstücksankauf Land Steiermark zum Zwecke der Errichtung der P+R Anlage Steinberg</p>
          <p>Ausgangslage:</p>
          <p>Mit Gemeinderatsitzung am 21.05.2026 bringt die Finanz- und Vermögensdirektion das Stück</p>
          <p>mit identischem Betreff mit GZ: A8- 067137/2025-70 ein.</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.subject_title == "Zuzahlung zum Grundstücksankauf Land Steiermark zum Zwecke der Errichtung der P+R Anlage Steinberg"
    assert result.source_snippet.startswith("Ausgangslage: Mit Gemeinderatsitzung")


def test_fetch_digra_result_extracts_attachment_titles():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 1678/1</title></head>
      <body>
        <div class="preview">
          <p>Bericht an den Gemeinderat</p>
          <p>Datum:</p>
          <p>16.10.2025</p>
          <p>4.08 B Stadtentwicklungskonzept</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 16.10.2025</p>
          <p>einstimmig angenommen</p>
        </div>
        <a href="document/attachment?ref=test&amp;att=1" title="2 - Mitterstraße - Entwicklungsplan">Download</a>
        <a href="document/attachment?ref=test&amp;att=2">3 - Bergstraße - Deckplan 5</a>
        <a href="/documents?init=true" title="Materialien">Materialien</a>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.attachment_titles == ["2 - Mitterstraße - Entwicklungsplan", "3 - Bergstraße - Deckplan 5"]


def test_extracts_split_digra_vote_results():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3413/1</title></head>
      <body>
        <div class="preview">
          <p>Dringlicher Antrag (§ 18 GO-GR)</p>
          <p>Antragsteller:in(nen):</p>
          <p>GR Miriam Rebecca Herlicska (KPÖ)</p>
          <p>Fußball-Weltmeisterschaft 2026: Sportwetten endlich als Glücksspiel behandeln</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>getrennt abgestimmt</p>
          <p>Anmerkungen zur Abstimmung:</p>
          <p>Dringlichkeit wurde mehrheitlich angenommen; Zustimmung: KPÖ, ÖVP, Grüne, SPÖ, NEOS, Reininghaus; dagegen: KFG.</p>
          <p>Punkt  1: mehrheitlich angenommen; Zustimmung: KPÖ, ÖVP, Grüne, SPÖ, NEOS, Reininghaus; dagegen: KFG</p>
          <p>Punkt  2: mehrheitlich angenommen; Zustimmung: KPÖ, Grüne, SPÖ, NEOS; dagegen: ÖVP, KFG, Reininghaus</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.submitter == "GR Miriam Rebecca Herlicska (KPÖ)"
    assert result.status == "accepted_majority"
    assert "Punkt 1: mehrheitlich angenommen" in result.result_text
    assert "Punkt 2: mehrheitlich angenommen" in result.result_text
    assert result.votes[1]["against"] == ["KFG"]


def test_extracts_split_digra_vote_results_with_punkt_dot_and_additional_motion():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 2867/1</title></head>
      <body>
        <div class="preview">
          <p>Dringlicher Antrag (§ 18 GO-GR)</p>
          <p>Antragsteller:in(nen):</p>
          <p>GR Beispiel (KPÖ)</p>
          <p>Verbesserung der mobilen Versorgung von Patient:innen mit ME/CFS</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 12.03.2026</p>
          <p>getrennt abgestimmt</p>
          <p>Anmerkungen zur Abstimmung:</p>
          <p>Die Dringlichkeit wurde einstimmig angenommen (Eustacchio nicht anwesend).</p>
          <p>Punkt 1.: mehrheitlich angenommen; Zustimmung: KPÖ, Grüne, SPÖ, KFG, NEOS, FPÖ, Eustacchio; Dagegen: ÖVP</p>
          <p>Punkt 2.: mehrheitlich angenommen; Zustimmung: KPÖ, Grüne, SPÖ, KFG, NEOS, FPÖ, Eustacchio; Dagegen: ÖVP</p>
          <p>Punkt 3.: mehrheitlich angenommen; Zustimmung: KPÖ, Grüne, SPÖ, KFG, FPÖ, Eustacchio; Dagegen: ÖVP, NEOS</p>
          <p>Punkt 4.: mehrheitlich angenommen; Zustimmung: KPÖ, Grüne, SPÖ, KFG, Eustacchio; Dagegen: ÖVP, NEOS, FPÖ</p>
          <p>Zusatzantrag Einlagezahl 2867/3, keine Mehrheit</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.status == "accepted_majority"
    assert "Dringlichkeit: einstimmig angenommen" in result.result_text
    assert "Punkt 1: mehrheitlich angenommen" in result.result_text
    assert "Punkt 4: mehrheitlich angenommen" in result.result_text
    assert "Zusatzantrag 2867/3: mehrheitlich abgelehnt" in result.result_text
    assert result.votes[0]["subject"] == "urgency"
    assert result.votes[1]["against"] == ["ÖVP"]
    assert result.votes[-1]["subject"] == "additional_motion_2867/3"
    assert result.votes[-1]["outcome"] == "rejected_majority"


def test_extracts_urgent_motion_no_majority_as_rejected_urgency():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 3425/1</title></head>
      <body>
        <div class="preview">
          <p>Dringlicher Antrag (§ 18 GO-GR)</p>
          <p>Antragsteller:in(nen):</p>
          <p>Clubobfrau Anna Hopper (ÖVP)</p>
          <p>Datum:</p>
          <p>21.05.2026</p>
          <p>Keine Kürzungen für Sport- und Kultursponsoring</p>
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 21.05.2026</p>
          <p>keine Mehrheit</p>
          <p>Anmerkungen zur Abstimmung:</p>
          <p>Dringlichkeit bekam keine Mehrheit.</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.submitter == "Clubobfrau Anna Hopper (ÖVP)"
    assert result.status == "rejected_majority"
    assert result.result_text == "Dringlichkeit: mehrheitlich abgelehnt"
    assert result.votes[0]["subject"] == "urgency"


def test_detects_digra_amendment_and_additional_motion_types():
    amendment_html = """
    <html><body><div class="preview">
      <p>Abänderungsantrag</p>
      <p>Antragsteller:in(nen):</p>
      <p>GR Beispiel (KPÖ)</p>
      <p>Datum:</p>
      <p>21.05.2026</p>
      <p>Budgetpunkt ändern</p>
      <p>Beschlussvermerk</p>
      <p>mehrheitlich angenommen</p>
    </div></body></html>
    """
    additional_html = amendment_html.replace("Abänderungsantrag", "Zusatzantrag").replace("Budgetpunkt ändern", "Ergänzung Budget")

    amendment = fetch_digra_result(FakeExporter(amendment_html), session=None, url="https://digra.graz.at/document?ref=a")
    additional = fetch_digra_result(FakeExporter(additional_html), session=None, url="https://digra.graz.at/document?ref=b")

    assert amendment.record_type_override == "amendment_motion"
    assert amendment.subject_title == "Budgetpunkt ändern"
    assert additional.record_type_override == "additional_motion"
    assert additional.subject_title == "Ergänzung Budget"


def test_detects_digra_motion_subtypes_when_heading_is_not_first_line():
    amendment_html = """
    <html><body><div class="preview">
      <p>EZ/OZ: 402/2</p>
      <p>Datum:</p>
      <p>21.05.2026</p>
      <p>Abänderungsantrag</p>
      <p>Budgetpunkt ändern</p>
      <p>Beschlussvermerk</p>
      <p>Gemeinderat am 21.05.2026</p>
      <p>mehrheitlich angenommen</p>
    </div></body></html>
    """
    additional_html = amendment_html.replace("Abänderungsantrag", "Zusatzantrag").replace("Budgetpunkt ändern", "Ergänzung Budget")

    amendment = fetch_digra_result(FakeExporter(amendment_html), session=None, url="https://digra.graz.at/document?ref=a")
    additional = fetch_digra_result(FakeExporter(additional_html), session=None, url="https://digra.graz.at/document?ref=b")

    assert amendment.record_type_override == "amendment_motion"
    assert additional.record_type_override == "additional_motion"


def test_detects_question_hour_that_will_be_answered_in_writing():
    html = """
    <html><body><div class="preview">
      <p>Frage für die Fragestunde (§ 16a GO-GR)</p>
      <p>Datum:</p>
      <p>21.05.2026</p>
      <p>Parkraumüberwachung</p>
      <p>Beschlussvermerk</p>
      <p>Gemeinderat am 21.05.2026</p>
      <p>wird schriftlich beantwortet</p>
    </div></body></html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")
    record = digra_entries_to_records(
        [
            DigraEntry(
                meeting_date="2026-05-21",
                meeting_number="58",
                record_type=result.record_type_override or "agenda_item",
                section="Fragestunde",
                order_in_type=1,
                agenda_item_no=1,
                business_number="2757/1",
                title=best_digra_title([], result),
                url="https://digra.graz.at/document?ref=test",
                status=result.status,
                result_text=result.result_text,
                raw_result_text=result.raw_result_text,
                votes=result.votes,
            )
        ]
    )[0]

    assert result.record_type_override == "question_hour"
    assert result.status == "source_available"
    assert "wird schriftlich beantwortet" in result.result_text
    assert viewer_record(record.__dict__)["status"] == "wird schriftlich beantwortet"


def test_does_not_parse_gegenstaendlich_as_against_vote():
    html = """
    <html>
      <head><title>Digitales Grazer Rathaus - 402/1</title></head>
      <body>
        <div class="preview">
          <p>Beschlussvermerk</p>
          <p>Gemeinderat</p>
          <p>am 20.03.2025</p>
          <p>mehrheitlich angenommen</p>
          <p>Anmerkungen zur Abstimmung:</p>
          <p>Abänderungsantrag Einlagezahl 402/2, mehrheitlich angenommen</p>
          <p>Die gegenständliche Petition wird um folgenden Punkt ergänzt:</p>
          <p>Schriftführer:in: Beispiel</p>
        </div>
      </body>
    </html>
    """

    result = fetch_digra_result(FakeExporter(html), session=None, url="https://digra.graz.at/document?ref=test")

    assert result.status == "accepted_majority"
    assert result.votes[0]["against"] == []
    assert "Dagegen:" not in result.result_text


def test_rejects_low_similarity_agenda_match():
    record = AgendaRecord(
        record_id="record",
        record_type="agenda_item",
        source_file="test.docx",
        meeting_date="2025-02-13",
        section="Tagesordnung",
        agenda_item_no=4,
        business_numbers=[],
        title="Aufnahme eines Wohnhauses in das Wohnkostenmodell",
        status="accepted_unanimous",
        status_text="",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.8,
    )
    entry = DigraEntry(
        meeting_date="2025-02-13",
        meeting_number="1",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=4,
        agenda_item_no=4,
        business_number="86/1",
        title="Satzung für Ehrungen durch die Stadt Graz",
        url="https://digra.graz.at/document?ref=test",
        status="accepted_unanimous",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="einstimmig angenommen",
        votes=[],
    )

    match, score = find_best_digra_entry(record, [entry], set(), order_in_type=4)

    assert match is None
    assert score == 0.0


def test_protocol_fallback_does_not_keep_uncertain_digra_link(monkeypatch):
    record = AgendaRecord(
        record_id="record",
        record_type="agenda_item",
        source_file="test.docx",
        meeting_date="2025-02-13",
        section="Tagesordnung",
        agenda_item_no=4,
        business_numbers=[],
        title="Aufnahme eines Wohnhauses in das Wohnkostenmodell",
        status="accepted_unanimous",
        status_text="",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.8,
    )
    entry = DigraEntry(
        meeting_date="2025-02-13",
        meeting_number="1",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=4,
        agenda_item_no=4,
        business_number="86/1",
        title="Satzung für Ehrungen durch die Stadt Graz",
        url="https://digra.graz.at/document?ref=wrong",
        status="unknown",
        result_text="",
        raw_result_text="",
        votes=[],
    )

    monkeypatch.setattr("graz_protocols.digra_import.load_or_fetch_entries", lambda dates, tool_path, cache_path: [entry])

    enriched, summary = enrich_records_with_digra([record])

    assert summary["digra_records_matched"] == 0
    assert enriched[0].result_source == "protokoll"
    assert enriched[0].digra_url == ""
    assert enriched[0].digra_business_number == ""


def test_agenda_item_can_match_digra_by_distinctive_title_tokens_when_numbers_differ():
    record = AgendaRecord(
        record_id="stadion",
        record_type="agenda_item",
        source_file="test.docx",
        meeting_date="2026-02-12",
        section="Tagesordnung",
        agenda_item_no=10,
        business_numbers=["A8-067136/2025-2"],
        title="Erhöhung und Verlängerung der Projektgenehmigung: Prüfung Stadion Graz Liebenau",
        status="unknown",
        status_text="",
        result_text="Unbekannt",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.8,
    )
    entry = DigraEntry(
        meeting_date="2026-02-12",
        meeting_number="57",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=33,
        agenda_item_no=33,
        business_number="2552/1",
        title="Aufwandsgenehmigung Präzisierung Machbarkeitsstudie Erweiterung Stadtion Graz Liebenau",
        url="https://digra.graz.at/document?ref=stadion",
        status="accepted_unanimous",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="einstimmig angenommen",
        votes=[],
    )

    match, score = find_best_digra_entry(record, [entry], set(), order_in_type=10)

    assert match == entry
    assert score >= 0.5


def test_agenda_item_does_not_match_by_generic_admin_tokens_when_numbers_differ():
    record = AgendaRecord(
        record_id="stadtmuseum",
        record_type="agenda_item",
        source_file="test.docx",
        meeting_date="2025-04-24",
        section="Tagesordnung",
        agenda_item_no=21,
        business_numbers=[],
        title="Stadtmuseum Graz GmbH; Stimmrechtsermächtigung für den Vertreter der Stadt Graz gem. § 87 (4) des Statuts der Landeshauptstadt Graz 1967; Umlaufbeschluss",
        status="unknown",
        status_text="",
        result_text="Unbekannt",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.8,
    )
    entry = DigraEntry(
        meeting_date="2025-04-24",
        meeting_number="1",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=40,
        agenda_item_no=40,
        business_number="575/1",
        title="Holding Graz Kommunale Dienstleistungen GmbH Energiewerk Graz Anpassung des Entsorgungsvertrages Generalversammlung gemäß § 87 (4) des Statutes der Landeshauptstadt Graz 1967; Umlaufbeschluss",
        url="https://digra.graz.at/document?ref=wrong",
        status="accepted_unanimous",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="einstimmig angenommen",
        votes=[],
    )

    match, score = find_best_digra_entry(record, [entry], set(), order_in_type=21)

    assert match is None
    assert score == 0.0


def test_agenda_item_can_match_short_digra_title_with_high_similarity_when_numbers_differ():
    record = AgendaRecord(
        record_id="ggz",
        record_type="agenda_item",
        source_file="test.docx",
        meeting_date="2025-12-11",
        section="Tagesordnung",
        agenda_item_no=48,
        business_numbers=[],
        title="GGZ - 070224/2004/0115 - Wirtschaftsplan 2026",
        status="unknown",
        status_text="",
        result_text="Unbekannt",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.8,
    )
    entry = DigraEntry(
        meeting_date="2025-12-11",
        meeting_number="1",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=62,
        agenda_item_no=62,
        business_number="1955/1",
        title="Wirtschaftsplan 2026",
        url="https://digra.graz.at/document?ref=ggz",
        status="accepted_unanimous",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="einstimmig angenommen",
        votes=[],
    )

    match, score = find_best_digra_entry(record, [entry], set(), order_in_type=48)

    assert match == entry
    assert score >= 0.8


def test_agenda_item_does_not_steal_similar_company_admin_digra_entry():
    record = AgendaRecord(
        record_id="fh",
        record_type="agenda_item",
        source_file="test.docx",
        meeting_date="2025-04-24",
        section="Tagesordnung",
        agenda_item_no=16,
        business_numbers=[],
        title="FH Standort Graz GmbH – Jahresabschluss zum 31.12.2024: Ermächtigung des Vertreters der Stadt Graz gem. § 87 (4) des Statuts der Landeshauptstadt Graz; Umlaufbeschluss",
        status="unknown",
        status_text="",
        result_text="Unbekannt",
        raw_result_text="",
        votes=[],
        amounts=[],
        locations=[],
        source_snippet="",
        parser_confidence=0.8,
    )
    entry = DigraEntry(
        meeting_date="2025-04-24",
        meeting_number="1",
        record_type="agenda_item",
        section="Tagesordnung",
        order_in_type=38,
        agenda_item_no=38,
        business_number="554/1",
        title="Stadtmuseum Graz GmbH; Stimmrechtsermächtigung für den Vertreter der Stadt Graz gem. § 87 (4) des Statuts der Landeshauptstadt Graz 1967; Umlaufbeschluss",
        url="https://digra.graz.at/document?ref=stadtmuseum",
        status="accepted_unanimous",
        result_text="Antrag: einstimmig angenommen",
        raw_result_text="einstimmig angenommen",
        votes=[],
    )

    match, score = find_best_digra_entry(record, [entry], set(), order_in_type=16)

    assert match is None
    assert score == 0.0


def test_canonicalizes_digra_session_urls():
    assert (
        canonical_digra_url("https://digra.graz.at/document?ref=62ffdb64-e7eb-41a9-917d-349c5ef37a9c&jfwid=abc")
        == "https://digra.graz.at/document?ref=62ffdb64-e7eb-41a9-917d-349c5ef37a9c"
    )
    assert canonical_digra_url("https://example.com/document?ref=x") == ""


def test_import_exporter_falls_back_to_public_http_importer(tmp_path):
    exporter = import_exporter(tmp_path / "missing-digra-tool")

    assert exporter.__name__ == "graz_protocols.digra_public"
    assert hasattr(exporter, "list_recent_meetings")
    assert hasattr(exporter, "fetch_soup")
    assert hasattr(exporter, "get_panel_for_tab")
    assert hasattr(exporter, "extract_entries_in_order")


def test_dedupes_digra_entries_by_url_preferring_specific_type():
    common = {
        "meeting_date": "2026-05-21",
        "meeting_number": "61",
        "agenda_item_no": 1,
        "business_number": "3413/1",
        "url": "https://digra.graz.at/document?ref=7df45b14-e3da-4abd-8e06-9fa5e4602cc7",
        "status": "accepted_majority",
        "result_text": "Antrag: mehrheitlich angenommen",
        "raw_result_text": "mehrheitlich angenommen",
        "votes": [],
        "submitter": "GR Beispiel",
    }
    entries = [
        DigraEntry(
            **common,
            record_type="agenda_item",
            section="Tagesordnung",
            order_in_type=68,
            title="",
        ),
        DigraEntry(
            **common,
            record_type="urgent_motion",
            section="Dringlichkeitsanträge",
            order_in_type=1,
            title="Sportwetten als Glücksspiel behandeln",
        ),
    ]

    deduped = dedupe_digra_entries(entries)

    assert len(deduped) == 1
    assert deduped[0].record_type == "urgent_motion"
    assert deduped[0].title == "Sportwetten als Glücksspiel behandeln"
