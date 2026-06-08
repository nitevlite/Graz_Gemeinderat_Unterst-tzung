from bs4 import BeautifulSoup

from graz_protocols.digra_import import DigraEntry, enrich_records_with_digra, fetch_digra_result, find_best_digra_entry
from graz_protocols.parser import AgendaRecord


class FakeExporter:
    def __init__(self, html: str):
        self.html = html

    def fetch_soup(self, session, url):  # noqa: ANN001
        return BeautifulSoup(self.html, "html.parser")


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
    assert result.result_text == "Antrag: mehrheitlich angenommen\nZustimmung: KPÖ, Grüne, KFG, NEOS"
    assert result.votes[0]["approval"] == ["KPÖ", "Grüne", "KFG", "NEOS"]
    assert "Der Gemeinderat wolle beschließen" not in result.raw_result_text


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
