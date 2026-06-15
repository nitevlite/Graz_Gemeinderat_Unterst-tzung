from scripts.check_git_safety import check_paths


def reasons(findings):
    return {finding.path: finding.reason for finding in findings}


def test_blocks_protocol_and_generated_file_types():
    findings = check_paths(
        ["README.md", "data/raw/protocol.docx", "out/agenda_items.jsonl", "out/eintraege.sqlite"],
        [],
        max_bytes=1_000_000,
    )

    by_path = reasons(findings)
    assert "data/raw/protocol.docx" in by_path
    assert "out/agenda_items.jsonl" in by_path
    assert "out/eintraege.sqlite" in by_path
    assert "README.md" not in by_path


def test_blocks_forbidden_data_directories():
    findings = check_paths(["graz_protokolle_arbeitskopie/example.txt", "src/app.py"], [], max_bytes=1_000_000)

    by_path = reasons(findings)
    assert by_path["graz_protokolle_arbeitskopie/example.txt"] == "verbotener Datenordner graz_protokolle_arbeitskopie/"
    assert "src/app.py" not in by_path


def test_blocks_local_roadwork_feed_exports():
    findings = check_paths(
        [
            "graz-baustellen-feed.json",
            "graz-baustellen-feed.csv",
            "graz-baustellen.ics",
            "graz-baustellen-feed.rss",
            "graz-baustellen-abos.json",
            "graz-baustellen-feedback.json",
            "graz-baustellen-auditlog.json",
        ],
        [],
        max_bytes=1_000_000,
    )

    by_path = reasons(findings)
    assert by_path["graz-baustellen-feed.json"] == "lokaler Baustellen-/Audit-Export"
    assert by_path["graz-baustellen-feed.csv"] == "lokaler Baustellen-/Audit-Export"
    assert by_path["graz-baustellen.ics"] == "lokaler Baustellen-/Audit-Export"
    assert by_path["graz-baustellen-feed.rss"] == "lokaler Baustellen-/Audit-Export"
    assert by_path["graz-baustellen-abos.json"] == "lokaler Baustellen-/Audit-Export"
    assert by_path["graz-baustellen-feedback.json"] == "lokaler Baustellen-/Audit-Export"
    assert by_path["graz-baustellen-auditlog.json"] == "lokaler Baustellen-/Audit-Export"
