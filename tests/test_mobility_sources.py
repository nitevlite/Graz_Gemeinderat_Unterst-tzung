from datetime import date

from graz_protocols.mobility_sources import (
    decode_parking_csv_bytes,
    mobility_source_summary,
    normalize_roadwork_period,
    parse_parking_csv,
    parse_osm_health_places,
    parse_roadworks_html,
    roadwork_time_status,
)


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


def test_decodes_open_data_parking_csv_with_cp1252_fallback():
    csv_text = "NAME;ANSCHRIFT;PHI;LAMBDA\n(PH) LKH;Stiftingtalstraße 30;47,081341;15,468616"
    decoded = decode_parking_csv_bytes(csv_text.encode("cp1252"))

    garages = parse_parking_csv(decoded)

    assert len(garages) == 1
    assert garages[0].address == "Stiftingtalstraße 30"


def test_parses_osm_health_places_with_opening_hours():
    osm_json = """
    {
      "elements": [
        {
          "type": "node",
          "id": 1,
          "lat": 47.0701,
          "lon": 15.4391,
          "tags": {
            "amenity": "pharmacy",
            "name": "Test Apotheke",
            "addr:street": "Herrengasse",
            "addr:housenumber": "1",
            "addr:postcode": "8010",
            "addr:city": "Graz",
            "opening_hours": "Mo-Fr 08:00-18:00",
            "phone": "+43 316 123456",
            "contact:website": "test-apotheke.example"
          }
        },
        {
          "type": "node",
          "id": 2,
          "lat": 47.0702,
          "lon": 15.4392,
          "tags": {
            "amenity": "pharmacy",
            "name": "Salvator-Apotheke"
          }
        },
        {
          "type": "node",
          "id": 3,
          "lat": 47.0711,
          "lon": 15.4381,
          "tags": {
            "amenity": "veterinary",
            "name": "Tierarzt Test",
            "addr:street": "Tiergasse",
            "addr:housenumber": "2"
          }
        },
        {
          "type": "node",
          "id": 4,
          "lat": 47.0721,
          "lon": 15.4371,
          "tags": {
            "amenity": "doctors",
            "name": "Augen Test",
            "healthcare:speciality": "ophthalmology"
          }
        },
        {
          "type": "node",
          "id": 5,
          "lat": 47.0731,
          "lon": 15.4361,
          "tags": {
            "amenity": "doctors",
            "name": "Hausarzt Test"
          }
        },
        {
          "type": "node",
          "id": 6,
          "lat": 47.0741,
          "lon": 15.4351,
          "tags": {
            "amenity": "doctors",
            "name": "Deutsche Fachrichtung Test",
            "healthcare:speciality": "Innere Medizin;HNO;unknown_specialty"
          }
        }
      ]
    }
    """

    places = parse_osm_health_places(osm_json, "pharmacy")

    assert len(places) == 2
    test_apotheke = next(place for place in places if place.name == "Test Apotheke")
    salvator = next(place for place in places if place.name == "Salvator-Apotheke")
    assert test_apotheke.kind == "Apotheke"
    assert test_apotheke.profession == ""
    assert test_apotheke.address == "Herrengasse 1, 8010 Graz"
    assert test_apotheke.opening_hours == "Mo-Fr 08:00-18:00"
    assert test_apotheke.license == "ODbL"
    assert test_apotheke.website == "https://test-apotheke.example"
    assert salvator.website == ""

    doctors = parse_osm_health_places(osm_json, "doctor")
    vet = next(place for place in doctors if place.name == "Tierarzt Test")
    assert vet.kind == "Tierarzt"
    assert vet.profession == "Tierarzt"
    eye = next(place for place in doctors if place.name == "Augen Test")
    assert eye.profession == "Augenheilkunde"
    gp = next(place for place in doctors if place.name == "Hausarzt Test")
    assert gp.profession == "Allgemeinmedizin"
    german = next(place for place in doctors if place.name == "Deutsche Fachrichtung Test")
    assert german.profession == "Innere Medizin, Hals-Nasen-Ohren-Heilkunde, Unknown Specialty"


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
    assert roadworks[0].start_date == "2026-06-01"
    assert roadworks[0].end_date == "2026-06-19"
    assert roadworks[0].time_status == "aktuell"
    assert roadworks[0].project == "Energie Graz - Beleuchtung"
    assert "Masttausch" in roadworks[0].description


def test_parses_current_until_roadwork_period_from_description():
    html = """
    <div class="txtblock-wrapper vorlesen clearfix">
      <h2>Peter-Tunner-Gasse</h2>
      <div class="txtblock-content wichtig">
        <p>im Bereich Lastenstraße bis Waagner-Biro-Straße<br>
        ÖBB-Brückensanierung<br>Totalsperre!<br>
        Umfahrung über Eggenberger Straße bzw. Ibererstraße<br>
        derzeit - 20.06.2026</p>
      </div>
    </div>
    """

    roadworks = parse_roadworks_html(html)

    assert len(roadworks) == 1
    assert roadworks[0].period == "derzeit - 20.06.2026"
    assert roadworks[0].end_date == "2026-06-20"
    assert roadworks[0].time_status == "aktuell"


def test_normalizes_roadwork_period_and_status():
    assert normalize_roadwork_period("01.06. - 19.06.2026") == ("2026-06-01", "2026-06-19")
    assert normalize_roadwork_period("01.06 - 30.06.2026 (08.00 - 16.00 Uhr)") == ("2026-06-01", "2026-06-30")
    assert normalize_roadwork_period("08.06. - 31.07.2026 (08.30 - 14.00 Uhr)") == ("2026-06-08", "2026-07-31")
    assert roadwork_time_status("01.06. - 19.06.2026", today=date(2026, 6, 9)) == "aktuell"
    assert roadwork_time_status("01.06 - 30.06.2026 (08.00 - 16.00 Uhr)", today=date(2026, 6, 9)) == "aktuell"
    assert roadwork_time_status("08.06. - 31.07.2026 (08.30 - 14.00 Uhr)", today=date(2026, 6, 9)) == "aktuell"
    assert roadwork_time_status("derzeit - 20.06.2026", today=date(2026, 6, 9)) == "aktuell"
    assert roadwork_time_status("derzeit - 20.06.2026", today=date(2026, 6, 21)) == "abgeschlossen"
    assert roadwork_time_status("20.06.2026 - 21.06.2026", today=date(2026, 6, 9)) == "kuenftig"
    assert roadwork_time_status("01.05.2026 - 02.05.2026", today=date(2026, 6, 9)) == "abgeschlossen"
    assert roadwork_time_status("nach Bedarf", today=date(2026, 6, 9)) == "unklar"


def test_mobility_source_summary_includes_traffic_data_audit():
    audit = mobility_source_summary()["traffic_data_audit"]

    names = {source["name"] for source in audit}
    assert "Data Graz Verkehr" in names
    assert "Kulturserver Graz Veranstaltungskalender" in names
    assert "Graz Linien - Fahrplandaten und Haltestellen" in names
    assert "Geplante Ereignismeldungen (EVIS.AT)" in names
    assert "Verkehrslage (EVIS.AT)" in names
    assert any(source["license"] == "Nutzungsvertrag mit Nutzungsgebühr" for source in audit)
    assert any(source.get("integration_status") == "teilweise integriert" for source in audit)
    assert any(source.get("integration_status") == "GTFS-Adapter vorbereiten" for source in audit)
    assert any(source.get("integration_status") == "lizenzierter DATEX-II-Adapter" for source in audit)
    assert any(source.get("integration_status") == "Veranstaltungsquelle prüfen" for source in audit)
    assert summary_has_source(mobility_source_summary(), "pharmacies", "https://www.apothekerkammer.at/apothekensuche")
    assert summary_has_source(mobility_source_summary(), "doctors", "https://ordinationen.st/")


def summary_has_source(summary, key, url):
    return summary[key]["official_search_url"] == url
