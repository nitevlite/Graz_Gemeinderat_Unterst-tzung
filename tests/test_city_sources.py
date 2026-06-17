import requests

from graz_protocols.city_sources import (
    enrich_topics_with_news,
    fetch_news_items,
    parse_archive_links,
    parse_news_items,
    annual_archive_label,
    meeting_date_from_anchor,
    meeting_page_label,
    parse_city_meeting_page_index,
    parse_city_archive_assets,
    city_archive_assets_to_records,
    write_city_archive_asset_index,
    CityArchiveAsset,
    CityMeetingPage,
)
from bs4 import BeautifulSoup


def test_parse_archive_links_extracts_overview_by_date():
    html = """
    <html><body>
      <p>14.11.2024 <a href="/cms/beitrag/test">Übersicht</a></p>
      <p>14.11.2024 <a href="/cms/beitrag/video">Livestream (1 Woche) und Berichterstattung</a></p>
    </body></html>
    """

    links = parse_archive_links(html, "https://www.graz.at/cms/beitrag/10142612/7768104")

    assert links[0].meeting_date == "2024-11-14"
    assert links[0].url == "https://www.graz.at/cms/beitrag/test"


def test_enrich_topics_with_news_matches_rss_items():
    rss = """
    <rss><channel>
      <item>
        <title>Gemeinderat beschließt neuen Klimaschutzplan</title>
        <link>https://www.graz.at/news/klima</link>
        <description>Fortschrittsbericht zum Klimaschutzplan Graz.</description>
        <pubDate>Fri, 22 May 2026 18:19:16 +0200</pubDate>
      </item>
    </channel></rss>
    """
    topics = [{"label": "Klimaschutzplan Fortschrittsbericht", "records": []}]

    enriched = enrich_topics_with_news(topics, parse_news_items(rss))

    assert enriched[0]["news"][0]["title"] == "Gemeinderat beschließt neuen Klimaschutzplan"
    assert enriched[0]["news"][0]["published"] == "2026-05-22"


def test_fetch_news_items_tolerates_network_errors(monkeypatch):
    def fail_get(*args, **kwargs):
        raise requests.ConnectionError("offline")

    monkeypatch.setattr("graz_protocols.city_sources.requests.get", fail_get)

    assert fetch_news_items() == []


def test_city_archive_labels_identify_old_meeting_pages():
    assert annual_archive_label("GR-Sitzungen 2021")
    assert annual_archive_label("2024")
    assert meeting_page_label("Gemeinderatssitzung vom 16. Dezember 2021")
    assert meeting_page_label("16.12.2021")

    soup = BeautifulSoup('<p>16.12.2021 <a href="/cms/beitrag/x">Übersicht</a></p>', "html.parser")
    anchor = soup.find("a")
    assert meeting_date_from_anchor(anchor, anchor.get_text(" ", strip=True)) == "2021-12-16"


def test_parse_city_meeting_page_index_discovers_year_and_meeting_links():
    html = """
    <html><body>
      <a href="/cms/beitrag/10390232/7768145/ArchivNachlese.html">GR-Sitzungen 2021</a>
      <p>16.12.2021 <a href="/cms/beitrag/10382049/7768145/Gemeinderatssitzung_vom_Dezember.html">Übersicht</a></p>
    </body></html>
    """

    meetings, links = parse_city_meeting_page_index(html, "https://www.graz.at/cms/beitrag/10134085/7768145/")

    assert links == ["https://www.graz.at/cms/beitrag/10390232/7768145/ArchivNachlese.html"]
    assert meetings[0].meeting_date == "2021-12-16"
    assert meetings[0].url == "https://www.graz.at/cms/beitrag/10382049/7768145/Gemeinderatssitzung_vom_Dezember.html"


def test_parse_city_archive_assets_discovers_protocol_documents():
    page = CityMeetingPage(
        meeting_date="2021-12-16",
        title="Gemeinderatssitzung",
        url="https://www.graz.at/cms/beitrag/page",
        source_url="https://www.graz.at/cms/beitrag/index",
    )
    html = """
    <html><body>
      <a href="/fileadmin/protokoll.docx">Protokoll Gemeinderat</a>
      <a href="/cms/dokumente/10036908_7768145/4297f20e/040422_antraege.pdf">Anträge</a>
      <a href="/cms/beitrag/overview?cms_nearest=10036908">Kontakt</a>
    </body></html>
    """

    assets = parse_city_archive_assets(html, page)

    assert {asset.kind for asset in assets} == {"protocol_document", "archive_document"}
    assert assets[0].meeting_date == "2021-12-16"
    assert assets[1].meeting_date == "2004-04-22"


def test_city_archive_asset_summary_reports_years_and_document_types(monkeypatch, tmp_path):
    pages = [
        CityMeetingPage(
            meeting_date="2021-12-16",
            title="Gemeinderatssitzung",
            url="https://www.graz.at/cms/beitrag/page",
            source_url="https://www.graz.at/cms/beitrag/index",
        )
    ]
    monkeypatch.setattr("graz_protocols.city_sources.read_city_meeting_index", lambda input_index: (pages, []))
    monkeypatch.setattr(
        "graz_protocols.city_sources.fetch_city_archive_assets",
        lambda loaded_pages: parse_city_archive_assets(
            '<a href="/fileadmin/protokoll.docx">Protokoll Gemeinderat</a><a href="/cms/dokumente/10036908_7768145/4297f20e/040422_antraege.pdf">Anträge</a>',
            loaded_pages[0],
        ),
    )

    summary = write_city_archive_asset_index(tmp_path / "assets.json", input_index=tmp_path / "index.json")

    assert summary["years"] == ["2004", "2021"]
    assert summary["document_types"]["protocol_document"] == 1
    assert summary["document_types"]["archive_document"] == 1


def test_city_archive_assets_become_source_records():
    page = CityMeetingPage(
        meeting_date="2021-12-16",
        title="Gemeinderatssitzung",
        url="https://www.graz.at/cms/beitrag/page",
        source_url="https://www.graz.at/cms/beitrag/index",
    )
    assets = parse_city_archive_assets('<a href="/fileadmin/protokoll.docx">Protokoll Gemeinderat</a>', page)

    records = city_archive_assets_to_records(assets)

    assert len(records) == 1
    assert records[0].record_type == "archive_source"
    assert records[0].title == "Protokoll Gemeinderat"
    assert records[0].status == "source_available"
    assert records[0].result_source == "archiv"
    assert records[0].source_url == "https://www.graz.at/fileadmin/protokoll.docx"


def test_city_archive_assets_use_specific_titles_and_attendance_type():
    assets = [
        CityArchiveAsset(
            meeting_date="2023-12-14",
            title="Anträge",
            url="https://www.graz.at/cms/dokumente/10419397_7768145/4c6e45d9/231214_antraege2.pdf",
            source_url="https://www.graz.at/cms/beitrag/page",
            kind="archive_document",
        ),
        CityArchiveAsset(
            meeting_date="2023-12-14",
            title="Tagesordnung",
            url="https://www.graz.at/cms/dokumente/10419397_7768145/04fa2430/231214_tagesordnung%202von2.pdf",
            source_url="https://www.graz.at/cms/beitrag/page",
            kind="archive_document",
        ),
        CityArchiveAsset(
            meeting_date="2023-11-16",
            title="->schriftliche ANTWORT",
            url="https://www.graz.at/cms/dokumente/10418174_8106610/668ab7c2/Antwort_FS231116_10_Pascuttini.pdf",
            source_url="https://www.graz.at/cms/beitrag/page",
            kind="archive_document",
        ),
        CityArchiveAsset(
            meeting_date="2023-11-16",
            title="Anwesenheitsliste",
            url="https://www.graz.at/cms/dokumente/10418012_7768145/11111111/231116_anwesenheitsliste.pdf",
            source_url="https://www.graz.at/cms/beitrag/page",
            kind="archive_document",
        ),
    ]

    records = {record.source_url: record for record in city_archive_assets_to_records(assets)}

    assert records[assets[0].url].title == "Schriftliche Anträge vom 14.12.2023 (Teil 2)"
    assert records[assets[1].url].title == "Tagesordnung vom 14.12.2023 (Teil 2 von 2)"
    assert records[assets[2].url].title == "Antwort zur Fragestunde vom 16.11.2023 (Pascuttini)"
    assert records[assets[3].url].record_type == "attendance_list"
    assert records[assets[3].url].title == "Anwesenheitsliste vom 16.11.2023"


def test_city_archive_assets_can_expand_motion_pdfs(monkeypatch):
    asset = CityArchiveAsset(
        meeting_date="2007-06-28",
        title="Dringliche",
        url="https://www.graz.at/cms/dokumente/10073283_7768145/9a4bbac4/070628_dringliche.pdf",
        source_url="https://www.graz.at/cms/beitrag/page",
        kind="archive_document",
    )

    def fake_extract(asset_to_parse):
        from graz_protocols.archive_motion_pdf import parse_archive_motion_text

        assert asset_to_parse == asset
        return parse_archive_motion_text(
            """
            Dringlicher Antrag an den Gemeinderat
            von GRin Lisa Rücker
            Betrifft: FußgängerInnenverkehr
            Der Gemeinderat möge beschließen.
            """,
            "070628_dringliche.pdf",
            source_url=asset.url,
        )

    monkeypatch.setattr("graz_protocols.city_sources.extract_archive_motion_asset_records", fake_extract)

    records = city_archive_assets_to_records([asset], extract_documents=True)

    assert len(records) == 1
    assert records[0].record_type == "urgent_motion"
    assert records[0].title == "FußgängerInnenverkehr"
    assert records[0].source_url == asset.url


def test_city_archive_assets_can_expand_question_pdfs(monkeypatch):
    asset = CityArchiveAsset(
        meeting_date="2006-11-16",
        title="Anfragen",
        url="https://www.graz.at/cms/dokumente/10064481_7768145/47f825b2/061116_anfragen.pdf",
        source_url="https://www.graz.at/cms/beitrag/page",
        kind="archive_document",
    )

    def fake_extract(asset_to_parse):
        from graz_protocols.archive_question_pdf import parse_archive_question_text

        assert asset_to_parse == asset
        return parse_archive_question_text(
            """
            Betr.: Maßnahmenpaket Sturzgasse
            MÜNDLICHE ANFRAGE
            von Herrn Gemeinderat Wilhelm Kolar
            Sehr geehrter Herr Bürgermeister!
            die Anfrage,
            ob du ein Maßnahmenpaket veranlasst?
            Betr.: Verkehrssituation Mariatrost
            MÜNDLICHE ANFRAGE
            von Frau Gemeinderätin Edeltraud Meißlitzer
            die Anfrage,
            ob Sie ein Verkehrskonzept in Angriff nehmen?
            """,
            "061116_anfragen.pdf",
            source_url=asset.url,
        )

    monkeypatch.setattr("graz_protocols.city_sources.extract_archive_question_asset_records", fake_extract)

    records = city_archive_assets_to_records([asset], extract_documents=True)

    assert len(records) == 2
    assert [record.record_type for record in records] == ["written_question", "written_question"]
    assert [record.title for record in records] == ["Maßnahmenpaket Sturzgasse", "Verkehrssituation Mariatrost"]
    assert records[0].source_url == asset.url


def test_city_archive_assets_can_expand_question_hour_pdfs_classified_as_protocol_documents(monkeypatch):
    asset = CityArchiveAsset(
        meeting_date="2007-01-18",
        title="Fragestunde des Gemeinderates",
        url="https://www.graz.at/cms/dokumente/10066994_7768145/62d3801c/070118_fragestunde2.pdf",
        source_url="https://www.graz.at/cms/beitrag/page",
        kind="protocol_document",
    )

    def fake_extract(asset_to_parse):
        from graz_protocols.parser import AgendaRecord

        assert asset_to_parse == asset
        return [
            AgendaRecord(
                record_id="2007-01-18-question-hour-1",
                record_type="question_hour",
                source_file="070118_fragestunde2.pdf",
                meeting_date="2007-01-18",
                section="Fragestunde",
                agenda_item_no=1,
                business_numbers=[],
                title="Verkehrssicherheit am Lendplatz",
                status="source_available",
                status_text="Quelle verfügbar",
                result_text="",
                raw_result_text="",
                votes=[],
                amounts=[],
                locations=[],
                source_snippet="Frage zur Verkehrssicherheit",
                parser_confidence=0.8,
            )
        ]

    monkeypatch.setattr("graz_protocols.city_sources.extract_archive_question_hour_asset_records", fake_extract)

    records = city_archive_assets_to_records([asset], extract_documents=True)

    assert len(records) == 1
    assert records[0].record_type == "question_hour"
    assert records[0].title == "Verkehrssicherheit am Lendplatz"
