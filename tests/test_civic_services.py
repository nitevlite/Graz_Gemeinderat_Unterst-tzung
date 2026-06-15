from graz_protocols.civic_services import GRAZ_OFFICES_URL, load_civic_services


def test_civic_services_are_source_tagged_and_reusable_as_links():
    services, summary = load_civic_services()

    assert services
    assert summary["directory_url"] == GRAZ_OFFICES_URL
    assert summary["license"] == "öffentliche Webseite, keine OGD-Lizenz gefunden"
    assert "kurze, faktische Servicehinweise" in summary["reuse"]

    for service in services:
        assert service["name"]
        assert service["category"]
        assert service["address"]
        assert isinstance(service["lat"], float)
        assert isinstance(service["lon"], float)
        assert service["source"]
        assert service["source_url"].startswith("https://")
        assert service["license"]
        assert service["reuse"]


def test_civic_services_include_citizen_relevant_entry_points():
    services, _summary = load_civic_services()
    names = {service["name"] for service in services}

    assert "Bürger:innenamt" in names
    assert "Passservice / Reisedokumente" in names
    assert "Amt der Bürgermeisterin" in names
    assert "Magistratsdirektion" in names
    assert "Finanzdirektion" in names
    assert "Kulturamt" in names
    assert "Sportamt" in names
    assert "Stadtbaudirektion" in names
    assert "Stadtvermessungsamt" in names
    assert "Sozialamt" in names
    assert "Straßenamt" in names
    assert "Holding Graz Service" in names

    pass_service = next(service for service in services if service["name"] == "Passservice / Reisedokumente")
    assert "Reisepass" in pass_service["services"]
    assert "Passamt" in pass_service["services"]
    assert "Personalausweis" in pass_service["services"]
