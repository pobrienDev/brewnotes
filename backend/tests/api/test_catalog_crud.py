"""Custom ingredients: create, edit, delete, uniqueness, quota and visibility."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.errors import PROBLEM_MEDIA_TYPE
from app.main import create_app
from app.security.oauth import build_oauth
from tests.conftest import CSRF, make_client, make_test_settings
from tests.fakes import FakeProviders
from tests.helpers import API, login_as

FERMENTABLE = {
    "name": "Garage Pale",
    "type": "grain",
    "ppg": 36.5,
    "color_lovibond": 2.2,
    "default_addition": "mash",
}
HOP = {
    "name": "Garage Hop",
    "alpha_typical_pct": 8.8,
    "origin": "Backyard",
}
YEAST = {
    "name": "Garage Ale",
    "lab": "Me",
    "product_code": "G1",
    "attenuation_min_pct": 72,
    "attenuation_max_pct": 78,
}


def test_custom_ingredient_lifecycle(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    created = client.post(f"{API}/catalog/hops", json=HOP, headers=CSRF)
    assert created.status_code == 201, created.text
    hop = created.json()
    assert hop["custom"] is True
    assert hop["alpha_typical_pct"] == 8.8

    listed = client.get(f"{API}/catalog/hops", params={"q": "garage"}).json()["items"]
    assert [h["id"] for h in listed] == [hop["id"]]

    edited = client.patch(
        f"{API}/catalog/hops/{hop['id']}", json={"alpha_typical_pct": 9.1}, headers=CSRF
    )
    assert edited.status_code == 200
    assert edited.json()["alpha_typical_pct"] == 9.1
    assert edited.json()["origin"] == "Backyard"

    cleared = client.patch(f"{API}/catalog/hops/{hop['id']}", json={"origin": None}, headers=CSRF)
    assert cleared.status_code == 200
    assert cleared.json()["origin"] is None

    deleted = client.delete(f"{API}/catalog/hops/{hop['id']}", headers=CSRF)
    assert deleted.status_code == 204
    payload = client.get(f"{API}/catalog/hops", params={"q": "garage"}).json()
    assert payload["items"] == []
    response_ = client.delete(f"{API}/catalog/hops/{hop['id']}", headers=CSRF)
    assert response_.status_code == 404


def test_fermentables_and_yeasts(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    fermentable = client.post(f"{API}/catalog/fermentables", json=FERMENTABLE, headers=CSRF)
    assert fermentable.status_code == 201, fermentable.text
    assert fermentable.json()["default_addition"] == "mash"
    yeast = client.post(f"{API}/catalog/yeasts", json=YEAST, headers=CSRF)
    assert yeast.status_code == 201, yeast.text
    assert yeast.json()["attenuation_midpoint_pct"] == 75

    bad = client.patch(
        f"{API}/catalog/yeasts/{yeast.json()['id']}", json={"attenuation_min_pct": 90}, headers=CSRF
    )
    assert bad.status_code == 422
    assert bad.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)


def test_writes_need_sign_in_and_origin(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    response_ = client.post(f"{API}/catalog/hops", json=HOP, headers=CSRF)
    assert response_.status_code == 401
    login_as(client, providers)
    response_ = client.post(f"{API}/catalog/hops", json=HOP)
    assert response_.status_code == 403


def test_builtins_cannot_be_edited_or_deleted(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    cascade = client.get(f"{API}/catalog/hops", params={"q": "cascade"}).json()["items"][0]
    edit = client.patch(
        f"{API}/catalog/hops/{cascade['id']}", json={"alpha_typical_pct": 1}, headers=CSRF
    )
    assert edit.status_code == 404
    delete = client.delete(f"{API}/catalog/hops/{cascade['id']}", headers=CSRF)
    assert delete.status_code == 404
    assert (
        client.get(f"{API}/catalog/hops", params={"q": "cascade"}).json()["items"][0][
            "alpha_typical_pct"
        ]
        == 5.5
    )


def test_duplicate_names_per_user_are_conflicts(
    seeded: None, app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers, subject="1001")
    first = client.post(f"{API}/catalog/hops", json=HOP, headers=CSRF)
    assert first.status_code == 201
    duplicate = client.post(f"{API}/catalog/hops", json=HOP, headers=CSRF)
    assert duplicate.status_code == 409
    assert duplicate.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    # A built-in name is fine for a custom entry: built-ins have no owner.
    shadow = client.post(
        f"{API}/catalog/hops", json={"name": "Cascade", "alpha_typical_pct": 6}, headers=CSRF
    )
    assert shadow.status_code == 201
    # Renaming onto an existing name is also a conflict.
    rename = client.patch(
        f"{API}/catalog/hops/{shadow.json()['id']}", json={"name": "Garage Hop"}, headers=CSRF
    )
    assert rename.status_code == 409
    # Another user may use the same name.
    with make_client(app) as other:
        login_as(other, providers, subject="1002")
        response_ = other.post(f"{API}/catalog/hops", json=HOP, headers=CSRF)
        assert response_.status_code == 201


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("hops", {**HOP, "alpha_typical_pct": 26}),
        ("hops", {**HOP, "name": ""}),
        ("hops", {**HOP, "unknown": 1}),
        ("fermentables", {**FERMENTABLE, "ppg": 51}),
        ("fermentables", {**FERMENTABLE, "type": "rock"}),
        ("yeasts", {**YEAST, "attenuation_min_pct": 39}),
        ("yeasts", {**YEAST, "attenuation_min_pct": 80, "attenuation_max_pct": 70}),
    ],
)
def test_custom_ingredient_bounds(
    seeded: None, client: TestClient, providers: FakeProviders, kind: str, body: dict[str, Any]
) -> None:
    login_as(client, providers)
    response = client.post(f"{API}/catalog/{kind}", json=body, headers=CSRF)
    assert response.status_code == 422, response.text


def test_explicit_null_on_required_field_is_rejected(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    hop = client.post(f"{API}/catalog/hops", json=HOP, headers=CSRF).json()
    response = client.patch(
        f"{API}/catalog/hops/{hop['id']}", json={"alpha_typical_pct": None}, headers=CSRF
    )
    assert response.status_code == 422


def test_custom_ingredient_quota_counts_all_types(
    seeded: None, app: FastAPI, providers: FakeProviders
) -> None:
    settings = make_test_settings(quota_custom_ingredients=2)
    small = create_app(settings)
    small.dependency_overrides = app.dependency_overrides
    small.state.oauth = build_oauth(settings, transport=providers.transport)
    with make_client(small) as client:
        login_as(client, providers)
        response_ = client.post(f"{API}/catalog/hops", json=HOP, headers=CSRF)
        assert response_.status_code == 201
        response_ = client.post(f"{API}/catalog/yeasts", json=YEAST, headers=CSRF)
        assert response_.status_code == 201
        blocked = client.post(f"{API}/catalog/fermentables", json=FERMENTABLE, headers=CSRF)
        assert blocked.status_code == 409
        assert "limit" in blocked.json()["detail"].lower()
    small.state.engine.dispose()
