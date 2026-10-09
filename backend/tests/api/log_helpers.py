"""Shared steps for the brewing-log tests: brew a batch from the Appendix A recipe, log
readings, add beers and tastings."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi.testclient import TestClient

from tests.conftest import CSRF
from tests.helpers import API, recipe_body

T0 = datetime(2026, 9, 1, 18, 0, tzinfo=UTC)  # well in the past: readings may not be post-dated


def at(hours: float) -> str:
    """T0 plus some hours, in the form the API echoes (UTC written as Z)."""
    return (T0 + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


def save_recipe(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(f"{API}/recipes", json=recipe_body(**overrides), headers=CSRF)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def brew(client: TestClient, recipe_id: str, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {"recipe_id": recipe_id, "brew_date": "2026-10-01", **overrides}
    response = client.post(f"{API}/batches", json=body, headers=CSRF)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def log(client: TestClient, batch_id: str, **reading: Any) -> dict[str, Any]:
    response = client.post(f"{API}/batches/{batch_id}/readings", json=reading, headers=CSRF)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def add_beer(client: TestClient, **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "name": "Pliny the Elder",
        "brewery_name": "Russian River",
        "style": "double-ipa",
        "abv": 8.0,
        **overrides,
    }
    response = client.post(f"{API}/beers", json=body, headers=CSRF)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def taste(client: TestClient, **body: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {"rating": 4.0, **body}
    response = client.post(f"{API}/tastings", json=payload, headers=CSRF)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result
