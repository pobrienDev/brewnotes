"""Single-origin serving: hashed assets immutable, index.html for deep links, JSON 404 for API."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import make_test_settings


def _build_static(tmp_path: Path) -> Path:
    static = tmp_path / "dist"
    (static / "assets").mkdir(parents=True)
    (static / "index.html").write_text("<!doctype html><title>BrewNotes</title>")
    (static / "assets" / "app-abc123.js").write_text("console.log('hi')")
    (static / "favicon.svg").write_text("<svg/>")
    return static


def test_frontend_serving(tmp_path: Path) -> None:
    settings = make_test_settings(static_dir=_build_static(tmp_path))
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        root = client.get("/")
        assert root.status_code == 200
        assert "BrewNotes" in root.text
        assert root.headers["cache-control"] == "no-cache"

        deep = client.get("/recipes/0192f3a0-1234-7abc-8def-0123456789ab")
        assert deep.status_code == 200
        assert deep.text == root.text
        assert deep.headers["cache-control"] == "no-cache"

        asset = client.get("/assets/app-abc123.js")
        assert asset.status_code == 200
        assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"

        favicon = client.get("/favicon.svg")
        assert favicon.status_code == 200
        assert favicon.text == "<svg/>"

        missing_asset = client.get("/assets/nope.js")
        assert missing_asset.status_code == 404

        api_404 = client.get("/api/v1/nothing-here")
        assert api_404.status_code == 404
        assert api_404.headers["content-type"].startswith("application/problem+json")

        post_to_page = client.post("/recipes")
        assert post_to_page.status_code == 405

        head = client.head("/recipes/anything")
        assert head.status_code == 200
        assert head.headers["content-type"].startswith("text/html")
        assert head.headers["cache-control"] == "no-cache"

        traversal = client.get("/../pyproject.toml")
        assert traversal.status_code == 200
        assert traversal.text == root.text


def test_without_static_dir_root_is_json_404(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")
