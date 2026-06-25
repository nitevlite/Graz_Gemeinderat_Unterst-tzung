import json
from pathlib import Path


def test_manifest_starts_at_published_page_root():
    manifest = json.loads(Path("site.webmanifest").read_text(encoding="utf-8"))

    assert manifest["start_url"] == "./"


def test_pages_workflow_publishes_referenced_static_assets():
    workflow = Path(".github/workflows/pages.yml").read_text(encoding="utf-8")

    assert "cp site.webmanifest public/site.webmanifest" in workflow
    assert "cp -a bi public/bi" in workflow
    assert "cp -a vendor public/vendor" in workflow
    assert "git add index.html .nojekyll site.webmanifest bi/ vendor/" in workflow


def test_leaflet_vendor_assets_are_available_locally():
    assert Path("vendor/leaflet/leaflet.css").is_file()
    assert Path("vendor/leaflet/leaflet.js").is_file()
    assert Path("vendor/leaflet/images/marker-icon.png").is_file()
    assert Path("vendor/leaflet/images/marker-icon-2x.png").is_file()
    assert Path("vendor/leaflet/images/marker-shadow.png").is_file()
