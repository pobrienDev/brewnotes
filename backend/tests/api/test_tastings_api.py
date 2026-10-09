"""Tastings: one subject (batch or beer), half-step ratings, structured notes, filters."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import create_app
from app.security.oauth import build_oauth
from tests.api.log_helpers import add_beer, at, brew, save_recipe, taste
from tests.conftest import CSRF, make_client, make_test_settings
from tests.fakes import FakeProviders
from tests.helpers import API, login_as


def test_tastings_require_sign_in(seeded: None, client: TestClient) -> None:
    assert client.get(f"{API}/tastings").status_code == 401


def test_rate_a_batch_and_a_beer(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"], status="packaged")
    beer = add_beer(client)

    homebrew = taste(
        client,
        batch_id=batch["id"],
        rating=3.5,
        aroma="Citrus, a little grainy",
        appearance="Gold, slight haze",
        flavor="Balanced, finish a bit short",
        mouthfeel="Medium-light",
        notes="Would mash a degree warmer next time.",
        tasted_at=at(24 * 20),
    )
    assert homebrew["batch"] == {"id": batch["id"], "name": batch["name"], "status": "packaged"}
    assert homebrew["beer"] is None
    assert homebrew["rating"] == 3.5
    assert homebrew["aroma"] == "Citrus, a little grainy"
    assert homebrew["tasted_at"] == at(24 * 20)

    commercial = taste(client, beer_id=beer["id"], rating=5.0, tasted_at=at(24 * 21))
    assert commercial["batch"] is None
    assert commercial["beer"] == {
        "id": beer["id"],
        "name": "Pliny the Elder",
        "brewery_name": "Russian River",
    }
    assert commercial["notes"] == ""

    listed = client.get(f"{API}/tastings").json()
    assert [t["id"] for t in listed["items"]] == [commercial["id"], homebrew["id"]]
    only_batch = client.get(f"{API}/tastings", params={"batch_id": batch["id"]}).json()
    assert [t["id"] for t in only_batch["items"]] == [homebrew["id"]]
    only_beer = client.get(f"{API}/tastings", params={"beer_id": beer["id"]}).json()
    assert [t["id"] for t in only_beer["items"]] == [commercial["id"]]
    assert (
        client.get(f"{API}/tastings", params={"beer_id": str(uuid.uuid4())}).json()["items"] == []
    )

    read = client.get(f"{API}/tastings/{homebrew['id']}")
    assert read.status_code == 200 and read.json() == homebrew
    assert client.get(f"{API}/beers/{beer['id']}").json()["average_rating"] == 5.0


def test_validation(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    beer = add_beer(client)
    cases = [
        {"rating": 4.0},  # no subject
        {"rating": 4.0, "batch_id": batch["id"], "beer_id": beer["id"]},  # two subjects
        {"rating": 3.3, "batch_id": batch["id"]},  # not a half step
        {"rating": 0, "batch_id": batch["id"]},
        {"rating": 5.5, "batch_id": batch["id"]},
        {"rating": 4.0, "batch_id": batch["id"], "aroma": "x" * 2001},
        {"rating": 4.0, "batch_id": batch["id"], "tasted_at": "2026-10-01T18:00:00"},
        {"rating": 4.0, "batch_id": batch["id"], "brewery_id": str(uuid.uuid4())},
    ]
    for body in cases:
        assert client.post(f"{API}/tastings", json=body, headers=CSRF).status_code == 422, body
    unknown_batch = client.post(
        f"{API}/tastings", json={"rating": 4.0, "batch_id": str(uuid.uuid4())}, headers=CSRF
    )
    assert unknown_batch.status_code == 422
    assert unknown_batch.json()["errors"][0]["loc"] == ["body", "batch_id"]
    unknown_beer = client.post(
        f"{API}/tastings", json={"rating": 4.0, "beer_id": str(uuid.uuid4())}, headers=CSRF
    )
    assert unknown_beer.json()["errors"][0] == {
        "loc": ["body", "beer_id"],
        "msg": "unknown beer",
        "type": "value_error",
    }
    assert (
        client.post(f"{API}/tastings", json={"rating": 4.0, "beer_id": beer["id"]}).status_code
        == 403
    )


def test_update_and_delete(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    beer = add_beer(client)
    tasting = taste(client, beer_id=beer["id"], rating=4.0)
    url = f"{API}/tastings/{tasting['id']}"

    updated = client.patch(url, json={"rating": 4.5, "mouthfeel": "Creamy"}, headers=CSRF)
    assert updated.status_code == 200, updated.text
    assert updated.json()["rating"] == 4.5
    assert updated.json()["mouthfeel"] == "Creamy"
    assert updated.json()["beer"]["id"] == beer["id"]
    for bad in [
        {"rating": 4.2},
        {"rating": None},
        {"beer_id": str(uuid.uuid4())},
        {"batch_id": None},
    ]:
        assert client.patch(url, json=bad, headers=CSRF).status_code == 422, bad

    assert client.delete(url, headers=CSRF).status_code == 204
    assert client.get(url).status_code == 404
    assert client.get(f"{API}/beers/{beer['id']}").json()["tastings_count"] == 0


def test_tasting_quota(seeded: None, app: FastAPI, providers: FakeProviders) -> None:
    settings = make_test_settings(quota_tastings=1)
    small = create_app(settings)
    small.dependency_overrides = app.dependency_overrides
    small.state.oauth = build_oauth(settings, transport=providers.transport)
    with make_client(small) as client:
        login_as(client, providers)
        beer = add_beer(client)
        taste(client, beer_id=beer["id"])
        blocked = client.post(
            f"{API}/tastings", json={"rating": 4.0, "beer_id": beer["id"]}, headers=CSRF
        )
        assert blocked.status_code == 409
    small.state.engine.dispose()
