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
