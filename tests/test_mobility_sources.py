from graz_protocols.mobility_sources import parse_parking_csv, parse_roadworks_html


def test_parses_open_data_parking_garages_csv():
    csv_text = "\n".join(
        [
            "XCoord;YCoord;OBJECTID;NAME;ANSCHRIFT;ORT;KAT3;HERKUNFT;PHI;LAMBDA",
            "1721958,51930000;5955361,05020000;1;(PH) LKH;Stiftingtalstraße 30;Graz;Parkhaus;Stadt Graz - Stadtvermessung;47,081341;15,468616",
        ]
    )

    garages = parse_parking_csv(csv_text)

    assert len(garages) == 1
    assert garages[0].name == "PH LKH"
    assert garages[0].address == "Stiftingtalstraße 30"
    assert garages[0].availability == "unbekannt"
    assert garages[0].license == "CC BY 4.0"


def test_parses_official_graz_roadworks_html_blocks():
    html = """
    <div class="txtblock-wrapper vorlesen clearfix">
      <h2>Kärntner Straße 163</h2>
      <div class="txtblock-content wichtig">
        <p>Masttausch<br>Postenregelung während der Arbeitszeiten<br>
        Termin: 01.06. - 19.06.2026<br><em>(Projekt: Energie Graz - Beleuchtung)</em></p>
      </div>
    </div>
    """

    roadworks = parse_roadworks_html(html)

    assert len(roadworks) == 1
    assert roadworks[0].title == "Kärntner Straße 163"
    assert roadworks[0].period == "01.06. - 19.06.2026"
    assert roadworks[0].project == "Energie Graz - Beleuchtung"
    assert "Masttausch" in roadworks[0].description
