from graz_protocols.parser import parse_protocol
from graz_protocols.street_names import normalize_street_name


def test_normalizes_street_names():
    assert normalize_street_name(" Algersdorfer Strasse ") == "algersdorfer straße"


def test_street_name_filter_removes_false_weg_suffix():
    records = parse_protocol(
        [
            "Protokoll über die ordentliche öffentliche Sitzung des Gemeinderates am 14.11.2024",
            "Tagesordnung",
            "Stk. 1) A10-123/1 Sanierung Beispielgasse",
            "Das ist vorweg zu prüfen. Die Beispielgasse ist betroffen.",
            "Der Antrag wurde einstimmig angenommen.",
        ],
        "2024-11-14_Protokoll.docx",
        street_names={"beispielgasse"},
    )

    assert records[0].locations == ["Beispielgasse"]
    assert "vorweg" not in [location.casefold() for location in records[0].locations]


def test_street_name_filter_keeps_only_allowlisted_weg_locations():
    records = parse_protocol(
        [
            "Protokoll über die ordentliche öffentliche Sitzung des Gemeinderates am 14.11.2024",
            "Tagesordnung",
            "Stk. 1) Ausbau Murradweg und Radweg",
            "Der Antrag wurde einstimmig angenommen.",
        ],
        "2024-11-14_Protokoll.docx",
        street_names={"murradweg"},
    )

    assert records[0].locations == ["Murradweg"]
