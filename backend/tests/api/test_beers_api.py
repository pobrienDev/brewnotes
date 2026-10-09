"""Commercial beers: private CRUD with style links, search and tasting statistics."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.security.oauth import build_oauth
from tests.api.log_helpers import add_beer, taste
from tests.conftest import CSRF, make_client, make_test_settings
from tests.fakes import FakeProviders
from tests.helpers import API, login_as


def test_beers_require_sign_in(seeded: None, client: TestClient) -> None:
    assert client.get(f"{API}/beers").status_code == 401
    response_ = client.post(f"{API}/beers", json={"name": "x"}, headers=CSRF)
    assert response_.status_code == 401


def test_create_list_search(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    pliny = add_beer(client)
    assert pliny["style"]["display_name"] == "22A Double IPA"
    assert pliny["brewery_name"] == "Russian River"
    assert pliny["abv"] == 8.0
    assert (pliny["tastings_count"], pliny["average_rating"]) == (0, None)
    add_beer(
        client, name="Augustiner Helles", brewery_name="Augustiner", style="munich-helles", abv=5.2
    )
    add_beer(client, name="Mystery", brewery_name=None, style=None, abv=None)

    listed = client.get(f"{API}/beers").json()
    assert [b["name"] for b in listed["items"]] == [
        "Augustiner Helles",
        "Mystery",
        "Pliny the Elder",
    ]
    assert listed["items"][1]["style"] is None and listed["items"][1]["brewery_name"] is None

    by_brewery = client.get(f"{API}/beers", params={"q": "russian"}).json()
    assert [b["name"] for b in by_brewery["items"]] == ["Pliny the Elder"]
    by_name = client.get(f"{API}/beers", params={"q": "helles"}).json()
    assert [b["name"] for b in by_name["items"]] == ["Augustiner Helles"]

    page = client.get(f"{API}/beers", params={"limit": 2}).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = client.get(f"{API}/beers", params={"limit": 2, "cursor": page["next_cursor"]}).json()
    assert [b["name"] for b in rest["items"]] == ["Pliny the Elder"]


def test_validation(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    unknown_style = client.post(
        f"{API}/beers", json={"name": "x", "style": "not-a-style"}, headers=CSRF
    )
    assert unknown_style.status_code == 422
    assert unknown_style.json()["errors"] == [
        {"loc": ["body", "style"], "msg": "unknown style", "type": "value_error"}
    ]
    for bad in [{"name": ""}, {"name": "x", "abv": 101}, {"name": "x", "brewery_name": ""}, {}]:
        response_ = client.post(f"{API}/beers", json=bad, headers=CSRF)
        assert response_.status_code == 422, bad
    response_ = client.post(f"{API}/beers", json={"name": "x"})
    assert response_.status_code == 403


def test_update_and_delete(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    beer = add_beer(client)
    url = f"{API}/beers/{beer['id']}"
    taste(client, beer_id=beer["id"], rating=4.0)
    taste(client, beer_id=beer["id"], rating=5.0)

    updated = client.patch(url, json={"abv": 8.2, "style": "american-ipa"}, headers=CSRF)
    assert updated.status_code == 200, updated.text
    assert updated.json()["abv"] == 8.2
    assert updated.json()["style"]["slug"] == "american-ipa"
    assert updated.json()["tastings_count"] == 2
    assert updated.json()["average_rating"] == pytest.approx(4.5)

    cleared = client.patch(
        url, json={"style": None, "brewery_name": None, "abv": None}, headers=CSRF
    )
    assert cleared.status_code == 200
    assert cleared.json()["style"] is None and cleared.json()["abv"] is None
    response_ = client.patch(url, json={"name": None}, headers=CSRF)
    assert response_.status_code == 422
    response_ = client.patch(url, json={"style": "nope"}, headers=CSRF)
    assert response_.status_code == 422

    response_ = client.delete(url, headers=CSRF)
    assert response_.status_code == 204
    assert client.get(url).status_code == 404
    assert client.get(f"{API}/tastings").json()["items"] == []  # cascaded
    assert client.get(f"{API}/beers/{uuid.uuid4()}").status_code == 404


def test_beer_quota(seeded: None, app: FastAPI, providers: FakeProviders) -> None:
    settings = make_test_settings(quota_beers=1)
    small = create_app(settings)
    small.dependency_overrides = app.dependency_overrides
    small.state.oauth = build_oauth(settings, transport=providers.transport)
    with make_client(small) as client:
        login_as(client, providers)
        add_beer(client)
        blocked = client.post(f"{API}/beers", json={"name": "two"}, headers=CSRF)
        assert blocked.status_code == 409
    small.state.engine.dispose()
