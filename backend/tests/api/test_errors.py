"""Every error is an RFC 9457 problem and never echoes submitted values."""

from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import Field

from app.errors import PROBLEM_MEDIA_TYPE
from app.schemas import Schema


class Payload(Schema):
    name: str = Field(max_length=5)
    amount: float = Field(gt=0)


def _add_test_routes(app: FastAPI) -> None:
    @app.post("/api/v1/_test/validate")
    def validate(body: Payload) -> Payload:
        return body

    @app.get("/api/v1/_test/boom")
    def boom() -> None:
        raise RuntimeError("secret internal detail")


def _is_problem(response: Any) -> bool:
    body = response.json()
    return (
        response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
        and body["status"] == response.status_code
        and isinstance(body["title"], str)
        and body["request_id"] == response.headers["x-request-id"]
    )


def test_unknown_api_path_is_json_404(client: TestClient) -> None:
    response = client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    assert _is_problem(response)
    assert response.json()["instance"] == "/api/v1/does-not-exist"


def test_method_not_allowed_is_problem(client: TestClient) -> None:
    response = client.post("/api/v1/health/live")
    assert response.status_code == 405
    assert _is_problem(response)


def test_validation_error_is_problem_without_submitted_values(
    app: FastAPI, client: TestClient
) -> None:
    _add_test_routes(app)
    submitted = "this-value-must-not-leak"
    response = client.post("/api/v1/_test/validate", json={"name": submitted, "amount": -1})
    assert response.status_code == 422
    assert _is_problem(response)
    body = response.json()
    assert body["title"] == "Validation failed"
    assert {tuple(e["loc"]) for e in body["errors"]} == {("body", "name"), ("body", "amount")}
    assert submitted not in response.text
    for error in body["errors"]:
        assert set(error) == {"loc", "msg", "type"}


def test_malformed_json_is_problem(app: FastAPI, client: TestClient) -> None:
    _add_test_routes(app)
    response = client.post(
        "/api/v1/_test/validate",
        content=b"{not json",
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 422
    assert _is_problem(response)


def test_nan_and_infinity_are_rejected(app: FastAPI, client: TestClient) -> None:
    _add_test_routes(app)
    for raw in (b'{"name": "ok", "amount": NaN}', b'{"name": "ok", "amount": Infinity}'):
        response = client.post(
            "/api/v1/_test/validate", content=raw, headers={"content-type": "application/json"}
        )
        assert response.status_code == 422, raw


def test_unhandled_exception_is_generic_500(app: FastAPI, client: TestClient) -> None:
    _add_test_routes(app)
    response = client.get("/api/v1/_test/boom")
    assert response.status_code == 500
    assert _is_problem(response)
    assert "secret internal detail" not in response.text
    assert "Traceback" not in response.text
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" in response.headers


def test_unknown_fields_are_rejected(app: FastAPI, client: TestClient) -> None:
    _add_test_routes(app)
    response = client.post(
        "/api/v1/_test/validate", json={"name": "ok", "amount": 1, "extra": "field"}
    )
    assert response.status_code == 422
    assert ("body", "extra") in {tuple(e["loc"]) for e in response.json()["errors"]}
