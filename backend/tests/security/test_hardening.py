"""Security headers, trusted host, body size limit and request IDs."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.errors import PROBLEM_MEDIA_TYPE
from app.main import create_app
from tests.conftest import make_test_settings


def test_security_headers_on_api_responses(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert response.headers["permissions-policy"] == "geolocation=(self)"
    csp = response.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "https://avatars.githubusercontent.com" in csp
    assert "https://lh3.googleusercontent.com" in csp
    assert "unsafe-inline" not in csp
    # Not production, so no HSTS.
    assert "strict-transport-security" not in response.headers


def test_security_headers_on_error_responses(client: TestClient) -> None:
    response = client.get("/api/v1/nope")
    assert response.status_code == 404
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers


def test_hsts_in_production() -> None:
    settings = make_test_settings(
        app_env="production",
        public_base_url="https://brewnotes.example",
        allowed_hosts=["brewnotes.example"],
        github_client_id="id",
        github_client_secret="secret",
        google_client_id="id",
        google_client_secret="secret",
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        response = client.get("/api/v1/health/live", headers={"host": "brewnotes.example"})
    assert response.status_code == 200
    assert response.headers["strict-transport-security"].startswith("max-age=")


def test_docs_disabled_outside_development(client: TestClient) -> None:
    assert client.get("/api/v1/docs").status_code == 404


def test_unknown_host_is_rejected_with_problem(client: TestClient) -> None:
    response = client.get("/api/v1/openapi.json", headers={"host": "evil.example"})
    assert response.status_code == 400
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.json()["detail"] == "Invalid host header."
    assert response.json()["request_id"] == response.headers["x-request-id"]
    assert "content-security-policy" in response.headers


@pytest.mark.parametrize("host", ["testserver", "TestServer", "testserver:8000"])
def test_allowed_host_variants(client: TestClient, host: str) -> None:
    assert client.get("/api/v1/openapi.json", headers={"host": host}).status_code == 200


def test_wildcard_and_ipv6_hosts() -> None:
    from app.middleware import _host_matches

    assert _host_matches("api.brewnotes.example:443", ["*.brewnotes.example"])
    assert not _host_matches("brewnotes.example", ["*.brewnotes.example"])
    assert _host_matches("[::1]:8000", ["[::1]"])
    assert not _host_matches("evil.example", ["brewnotes.example"])


def test_health_accepts_any_host_for_platform_probes(client: TestClient) -> None:
    response = client.get("/api/v1/health/live", headers={"host": "10.0.0.7:8000"})
    assert response.status_code == 200


def test_request_id_is_generated(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")
    uuid.UUID(response.headers["x-request-id"])


def test_valid_request_id_is_echoed(client: TestClient) -> None:
    response = client.get("/api/v1/health/live", headers={"x-request-id": "abc-123.XYZ"})
    assert response.headers["x-request-id"] == "abc-123.XYZ"


@pytest.mark.parametrize("bad", ["x" * 65, "has space", "semi;colon", "slash/here"])
def test_malformed_request_id_is_replaced(client: TestClient, bad: str) -> None:
    response = client.get("/api/v1/health/live", headers={"x-request-id": bad})
    assert response.headers["x-request-id"] != bad
    uuid.UUID(response.headers["x-request-id"])


def _add_upload_route(app: FastAPI) -> None:
    # Test-only route that reads the raw body, so the streaming limit is exercised.
    @app.post("/api/v1/_test/upload")
    async def upload(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}


def test_body_over_limit_with_content_length_is_413(app: FastAPI, client: TestClient) -> None:
    _add_upload_route(app)
    limit = app.state.settings.max_body_bytes
    response = client.post(
        "/api/v1/_test/upload",
        content=b"x" * (limit + 1),
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 413
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)


def test_chunked_body_over_limit_is_413(app: FastAPI, client: TestClient) -> None:
    _add_upload_route(app)
    limit = app.state.settings.max_body_bytes

    def chunks() -> Iterator[bytes]:
        sent = 0
        while sent <= limit:
            yield b"y" * 65536
            sent += 65536

    response = client.post(
        "/api/v1/_test/upload",
        content=chunks(),
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 413


def test_body_under_limit_passes_through(app: FastAPI, client: TestClient) -> None:
    _add_upload_route(app)
    response = client.post(
        "/api/v1/_test/upload",
        content=b"z" * 1024,
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 200
    assert response.json() == {"size": 1024}
