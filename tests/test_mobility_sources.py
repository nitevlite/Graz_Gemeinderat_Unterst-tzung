from graz_protocols.mobility_sources import parse_parking_csv


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
