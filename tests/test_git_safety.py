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
