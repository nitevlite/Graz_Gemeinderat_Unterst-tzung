from graz_protocols.archive_motion_pdf import parse_archive_motion_text


def test_parse_archive_motion_text_extracts_multiple_urgent_motions():
    text = """
    G E M E I N S A M E R A N T R A G
    von ÖVP und FPÖ
    zur
    DRINGLICHEN BEHANDLUNG
    Betr.: Alkohol bei Jugendlichen - koordinierte
    und rasche Hilfe ist nötiger denn je!
    GR. Univ. Prof. Dr. Heinz Hammer 28.6.2007
    Ich stelle daher den dringlichen Antrag,
    der Gemeinderat möge beschließen: Bericht zu erarbeiten.

    Betrifft: Alkohol bei Jugendlichen
    Abänderungsantrag
    zum Dringlichen Antrag
    eingebracht von Herrn Gemeinderat Alexander Perissutti
    in der Sitzung des Gemeinderates vom 28. Juni 2007
    den Abänderungsantrag zum vorliegenden dringlichen Antrag.

    Dringlicher Antrag von SPÖ, ÖVP, KPÖ, Grüne und FPÖ
    an den Gemeinderat
    eingebracht von Frau Gemeinderätin Dagmar Krampl
    in der Sitzung des Gemeinderates vom 28. Juni 2007
    Betreff: Factory-Outlet-Center
    Der Bürgermeister wird aufgefordert, den Planungsbeirat einzuberufen.
    """

    records = parse_archive_motion_text(
        text,
        "070628_dringliche.pdf",
        source_url="https://www.graz.at/cms/dokumente/10073283_7768145/9a4bbac4/070628_dringliche.pdf",
    )

    assert [record.record_type for record in records] == ["urgent_motion", "amendment_motion", "urgent_motion"]
    assert [record.meeting_date for record in records] == ["2007-06-28", "2007-06-28", "2007-06-28"]
    assert records[0].title == "Alkohol bei Jugendlichen - koordinierte und rasche Hilfe ist nötiger denn je"
    assert records[0].submitter == "GR. Univ. Prof. Dr. Heinz Hammer"
    assert records[1].title == "Alkohol bei Jugendlichen"
    assert records[1].submitter == "Gemeinderat Alexander Perissutti"
    assert records[2].title == "Factory-Outlet-Center"
    assert records[2].submitter == "Gemeinderätin Dagmar Krampl"
    assert all(record.result_source == "archiv" for record in records)


def test_parse_archive_motion_text_splits_embedded_page_joined_start():
    text = """
    Dringlicher Antrag an den Gemeinderat
    von GRin Lisa Rücker
    Betrifft: Kontrollausschuss der Stadt Graz
    Der Gemeinderat möge beschließen. Dringlicher Antrag an den Gemeinderat
    eingebracht in der Gemeinderatssitzung vom 28.6.2007
    von GRin Lisa Rücker
    Betrifft: FußgängerInnenverkehr
    Der Gemeinderat möge beschließen.
    """

    records = parse_archive_motion_text(text, "070628_dringliche.pdf")

    assert [record.title for record in records] == ["Kontrollausschuss der Stadt Graz", "FußgängerInnenverkehr"]


def test_parse_archive_motion_text_extracts_numbered_written_motions():
    text = """
    Gemeinderatssitzung vom 19. November 2009
    A N T R Ä G E
    1) Zweitwohnsitzabgabe, Petition an die Steiermärkische Landesregierung
    GR. Hohensinner stellt namens von ÖVP und Grünen folgenden Antrag:
    Der Gemeinderat wolle beschließen.
    2) Nachmittagsbetreuung in Schulen
    GRin. Musterfrau stellt folgenden Antrag:
    Der Gemeinderat wolle beschließen.
    """

    records = parse_archive_motion_text(text, "091119_antraege2.pdf")

    assert [record.record_type for record in records] == ["written_motion", "written_motion"]
    assert [record.meeting_date for record in records] == ["2009-11-19", "2009-11-19"]
    assert records[0].title == "Zweitwohnsitzabgabe, Petition an die Steiermärkische Landesregierung"
    assert records[0].submitter == "GR. Hohensinner"
