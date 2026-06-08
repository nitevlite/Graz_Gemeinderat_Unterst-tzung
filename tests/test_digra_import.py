from bs4 import BeautifulSoup

from graz_protocols.digra_import import fetch_digra_result


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
