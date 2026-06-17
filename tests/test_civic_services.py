from graz_protocols.civic_services import (
    GRAZ_COUNCIL_MEMBERS_URL,
    GRAZ_OFFICES_URL,
    load_civic_council,
    load_civic_services,
    parse_city_senate_member_links,
    parse_council_member_links,
)


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


def test_civic_council_contains_current_seat_distribution_and_sources():
    council = load_civic_council()

    assert council["total_seats"] == 48
    assert council["majority_seats"] == 25
    assert council["sources"]["members_url"] == GRAZ_COUNCIL_MEMBERS_URL
    assert council["sources"]["city_government_url"].startswith("https://www.graz.at/")

    seats = {group["short_name"]: group["seats"] for group in council["groups"]}
    assert seats == {
        "KPÖ": 15,
        "ÖVP": 13,
        "Grüne": 9,
        "SPÖ": 4,
        "KFG": 3,
        "NEOS": 1,
        "FPÖ": 1,
        "ohne Klub": 2,
    }
    for group in council["groups"]:
        assert len(group["members"]) == group["seats"]
        assert all(member["url"].startswith("https://www.graz.at/") for member in group["members"])
    kpoe = next(group for group in council["groups"] if group["short_name"] == "KPÖ")
    oevp = next(group for group in council["groups"] if group["short_name"] == "ÖVP")
    assert "Elke Heinrichs" in {member["name"] for member in kpoe["members"]}
    assert "Anna Hopper" in {member["name"] for member in oevp["members"]}
    hopper = next(member for member in oevp["members"] if member["name"] == "Anna Hopper")
    assert hopper["url"] == "https://www.graz.at/cms/beitrag/10379867/7768635/Gemeinderaetin_Anna_Hopper_OeVP.html"

    senate = {group["short_name"]: group["seats"] for group in council["city_senate"]["groups"]}
    assert senate == {"KPÖ": 3, "ÖVP": 2, "Grüne": 1, "KFG": 1}
    for group in council["city_senate"]["groups"]:
        assert all(member["url"].startswith("https://www.graz.at/") for member in group["members"])


def test_parse_council_member_links_from_official_member_page_shape():
    groups = parse_council_member_links(
        """
        <a href="/cms/beitrag/10379867/7768635/Gemeinderaetin_Anna_Hopper_OeVP.html">
          Hopper, Anna ( CLUBOBFRAU ÖVP)
        </a>
        <a href="/cms/beitrag/1/7768635/Gemeinderat_Thomas_Alic_KPOE.html">Alic, Thomas Horst (KPÖ)</a>
        <a href="/cms/beitrag/2/7768635/Gemeinderat_Philipp_Pointner_NEOS.html">Pointner, Philipp Mag. (Neos)</a>
        """,
        "https://www.graz.at/cms/beitrag/10379731/7768104/Gemeinderat_Mitglieder.html",
    )

    seats = {group["short_name"]: group for group in groups}
    assert seats["ÖVP"]["members"][0] == {
        "name": "Anna Hopper",
        "url": "https://www.graz.at/cms/beitrag/10379867/7768635/Gemeinderaetin_Anna_Hopper_OeVP.html",
    }
    assert seats["KPÖ"]["members"][0]["name"] == "Thomas Horst Alic"
    assert seats["NEOS"]["members"][0]["url"].startswith("https://www.graz.at/cms/beitrag/2/")


def test_parse_city_senate_member_links_from_official_page_shape():
    groups = parse_city_senate_member_links(
        """
        <a href="/cms/beitrag/10311681/7765844/Buergermeisterin_Elke_Kahr_KPOE.html">
          Bürgermeisterin Elke Kahr (KPÖ)
        </a>
        <a href="/cms/beitrag/10312154/7765844/Vizebuergermeisterin_Judith_Schwentner_Gruene.html">
          Bürgermeisterin-Stellvertreterin Mag. Judith Schwentner (Grüne)
        </a>
        <a href="/cms/beitrag/10311687/7765844/Stadtraetin_Claudia_Schoenbacher.html">
          Stadträtin Claudia Schönbacher, (Korruptions-) Freier Gemeinderatsklub
        </a>
        """,
        "https://www.graz.at/cms/ziel/7765844/DE/",
    )

    seats = {group["short_name"]: group for group in groups}
    assert seats["KPÖ"]["members"][0] == {
        "name": "Elke Kahr",
        "url": "https://www.graz.at/cms/beitrag/10311681/7765844/Buergermeisterin_Elke_Kahr_KPOE.html",
    }
    assert seats["Grüne"]["members"][0]["name"] == "Judith Schwentner"
    assert seats["KFG"]["members"][0]["name"] == "Claudia Schönbacher"
