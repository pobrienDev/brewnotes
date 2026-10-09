"""Recipes: CRUD with ownership, quotas, reference checks, export and cascade."""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select

from app.domain.units import lb_to_kg
from app.errors import PROBLEM_MEDIA_TYPE
from app.main import create_app
from app.models import Recipe, RecipeFermentable, RecipeHop, RecipeYeast
from app.security.oauth import build_oauth
from tests.conftest import CSRF, make_client, make_test_settings
from tests.fakes import FakeProviders
from tests.fixtures import APPENDIX_A_EXPECTED
from tests.helpers import API, login_as, recipe_body


def create(client: TestClient, **overrides: Any) -> dict[str, Any]:
    response = client.post(f"{API}/recipes", json=recipe_body(**overrides), headers=CSRF)
    assert response.status_code == 201, response.text
    result: dict[str, Any] = response.json()
    return result


def test_recipes_require_sign_in(seeded: None, client: TestClient) -> None:
    response_ = client.get(f"{API}/recipes")
    assert response_.status_code == 401
    anonymous_post = client.post(f"{API}/recipes", json=recipe_body(), headers=CSRF)
    assert anonymous_post.status_code == 401


def test_create_read_list(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    created = create(client)
    uuid.UUID(created["id"])
    assert created["name"] == "Appendix A Pale Ale"
    assert created["target_style"]["display_name"] == "18B American Pale Ale"
    assert created["stats"]["og"] == pytest.approx(APPENDIX_A_EXPECTED.og, abs=0.001)
    assert created["style_matches"][0]["slug"] == "american-pale-ale"
    assert [f["name"] for f in created["fermentables"]] == [
        "2-row pale malt",
        "Munich malt",
        "Crystal 40",
    ]
    assert all("id" in f for f in created["fermentables"])
    assert created["hops"][0]["time_min"] == 60
    assert created["calc_notes"]

    fetched = client.get(f"{API}/recipes/{created['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == created

    listed = client.get(f"{API}/recipes").json()
    assert [r["name"] for r in listed["items"]] == ["Appendix A Pale Ale"]
    summary = listed["items"][0]
    assert summary["target_style"]["code"] == "18B"
    assert summary["abv"] == pytest.approx(APPENDIX_A_EXPECTED.abv, abs=0.1)
    assert summary["srm"] == pytest.approx(APPENDIX_A_EXPECTED.srm, abs=0.5)
    assert "stats" not in summary


def test_list_is_newest_first_and_paginated(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    ids = [create(client, name=f"Recipe {i}")["id"] for i in range(7)]
    page = client.get(f"{API}/recipes", params={"limit": 3}).json()
    assert [r["id"] for r in page["items"]] == ids[::-1][:3]
    assert page["next_cursor"]
    rest = client.get(f"{API}/recipes", params={"limit": 3, "cursor": page["next_cursor"]}).json()
    assert [r["id"] for r in rest["items"]] == ids[::-1][3:6]
    last = client.get(f"{API}/recipes", params={"limit": 3, "cursor": rest["next_cursor"]}).json()
    assert [r["id"] for r in last["items"]] == ids[::-1][6:]
    assert last["next_cursor"] is None


def test_replace_and_delete(
    seeded: None, client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    login_as(client, providers)
    created = create(client)
    recipe_id = created["id"]

    body = recipe_body(
        name="Bigger",
        target_style="american-ipa",
        hops=[
            {
                "name": "Citra",
                "amount_g": 56,
                "alpha_pct": 12,
                "use": "boil",
                "time_min": 15,
            },
            {
                "name": "Citra",
                "amount_g": 56,
                "alpha_pct": 12,
                "use": "dry_hop",
                "dry_hop_days": 4,
            },
        ],
    )
    body["fermentables"][0]["amount_kg"] = lb_to_kg(12)
    replaced = client.put(f"{API}/recipes/{recipe_id}", json=body, headers=CSRF)
    assert replaced.status_code == 200, replaced.text
    out = replaced.json()
    assert out["id"] == recipe_id
    assert out["name"] == "Bigger"
    assert out["target_style"]["slug"] == "american-ipa"
    assert [h["use"] for h in out["hops"]] == ["boil", "dry_hop"]
    assert out["stats"]["og"] > created["stats"]["og"]
    assert out["updated_at"] >= created["updated_at"]
    # Old child rows are gone, not orphaned.
    assert db_connection.execute(select(func.count()).select_from(RecipeHop)).scalar_one() == 2

    deleted = client.delete(f"{API}/recipes/{recipe_id}", headers=CSRF)
    assert deleted.status_code == 204
    response_ = client.get(f"{API}/recipes/{recipe_id}")
    assert response_.status_code == 404
    for model in (RecipeFermentable, RecipeHop, RecipeYeast):
        assert db_connection.execute(select(func.count()).select_from(model)).scalar_one() == 0
    again = client.delete(f"{API}/recipes/{recipe_id}", headers=CSRF)
    assert again.status_code == 404


def test_writes_require_origin(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    created = create(client)
    response_ = client.post(f"{API}/recipes", json=recipe_body())
    assert response_.status_code == 403
    response_ = client.put(f"{API}/recipes/{created['id']}", json=recipe_body())
    assert response_.status_code == 403
    response_ = client.delete(f"{API}/recipes/{created['id']}")
    assert response_.status_code == 403


@pytest.mark.parametrize(
    ("overrides", "loc"),
    [
        ({"name": ""}, ("body", "name")),
        ({"name": "x" * 201}, ("body", "name")),
        ({"notes": "x" * 10_001}, ("body", "notes")),
        ({"target_style": "not-a-style"}, ("body", "target_style")),
        ({"batch_volume_l": 0.4}, ("body", "batch_volume_l")),
        ({"extra": 1}, ("body", "extra")),
    ],
)
def test_recipe_validation(
    seeded: None,
    client: TestClient,
    providers: FakeProviders,
    overrides: dict[str, Any],
    loc: tuple[str, ...],
) -> None:
    login_as(client, providers)
    response = client.post(f"{API}/recipes", json=recipe_body(**overrides), headers=CSRF)
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert loc in {tuple(e["loc"]) for e in response.json()["errors"]}
    payload = client.get(f"{API}/recipes").json()
    assert payload["items"] == []


def test_fermentable_type_is_required_for_saved_recipes(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    body = recipe_body()
    del body["fermentables"][0]["type"]
    response = client.post(f"{API}/recipes", json=body, headers=CSRF)
    assert response.status_code == 422
    assert ("body", "fermentables", 0, "type") in {
        tuple(e["loc"]) for e in response.json()["errors"]
    }


def test_impossible_recipe_is_rejected_before_saving(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    body = recipe_body(batch_volume_l=0.5)
    body["fermentables"][0]["amount_kg"] = 1000
    response = client.post(f"{API}/recipes", json=body, headers=CSRF)
    assert response.status_code == 422
    assert ("body", "fermentables") in {tuple(e["loc"]) for e in response.json()["errors"]}
    payload = client.get(f"{API}/recipes").json()
    assert payload["items"] == []


def test_catalog_references_must_be_builtin_or_mine(
    seeded: None, app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers, subject="1001")
    cascade = client.get(f"{API}/catalog/hops", params={"q": "cascade"}).json()["items"][0]
    mine_response = client.post(
        f"{API}/catalog/hops", json={"name": "My Hop", "alpha_typical_pct": 9}, headers=CSRF
    )
    assert mine_response.status_code == 201, mine_response.text
    mine = mine_response.json()

    body = recipe_body()
    body["hops"][0]["hop_id"] = cascade["id"]
    body["hops"][1]["hop_id"] = mine["id"]
    created = client.post(f"{API}/recipes", json=body, headers=CSRF)
    assert created.status_code == 201, created.text
    assert created.json()["hops"][0]["hop_id"] == cascade["id"]

    with make_client(app) as other:
        login_as(other, providers, subject="1002")
        body = recipe_body()
        body["hops"][0]["hop_id"] = mine["id"]  # another user's custom hop
        body["fermentables"][1]["fermentable_id"] = str(uuid.uuid4())  # nonexistent
        response = other.post(f"{API}/recipes", json=body, headers=CSRF)
        assert response.status_code == 422
        locs = {tuple(e["loc"]) for e in response.json()["errors"]}
        assert ("body", "hops", 0, "hop_id") in locs
        assert ("body", "fermentables", 1, "fermentable_id") in locs
        payload = other.get(f"{API}/recipes").json()
        assert payload["items"] == []


def test_deleting_a_custom_ingredient_keeps_the_recipe_snapshot(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    mine = client.post(
        f"{API}/catalog/hops", json={"name": "My Hop", "alpha_typical_pct": 9}, headers=CSRF
    ).json()
    body = recipe_body()
    body["hops"][0]["hop_id"] = mine["id"]
    created = create(client, **body)
    response_ = client.delete(f"{API}/catalog/hops/{mine['id']}", headers=CSRF)
    assert response_.status_code == 204
    after = client.get(f"{API}/recipes/{created['id']}").json()
    assert after["hops"][0]["hop_id"] is None
    assert after["hops"][0]["name"] == "Cascade"
    assert after["stats"]["ibu"] == pytest.approx(created["stats"]["ibu"])


def test_cross_user_matrix(
    seeded: None, app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    """Every owned endpoint and method answers 404 for another user's IDs."""
    login_as(client, providers, subject="1001")
    recipe = create(client)
    fermentable = client.post(
        f"{API}/catalog/fermentables",
        json={
            "name": "Mine",
            "type": "grain",
            "ppg": 36,
            "color_lovibond": 4,
            "default_addition": "mash",
        },
        headers=CSRF,
    ).json()
    hop = client.post(
        f"{API}/catalog/hops", json={"name": "Mine", "alpha_typical_pct": 5}, headers=CSRF
    ).json()
    yeast = client.post(
        f"{API}/catalog/yeasts",
        json={"name": "Mine", "lab": "Me", "attenuation_min_pct": 70, "attenuation_max_pct": 80},
        headers=CSRF,
    ).json()

    attempts = [
        ("GET", f"{API}/recipes/{recipe['id']}", None),
        ("PUT", f"{API}/recipes/{recipe['id']}", recipe_body(name="hijack")),
        ("DELETE", f"{API}/recipes/{recipe['id']}", None),
        ("PATCH", f"{API}/catalog/fermentables/{fermentable['id']}", {"ppg": 1}),
        ("DELETE", f"{API}/catalog/fermentables/{fermentable['id']}", None),
        ("PATCH", f"{API}/catalog/hops/{hop['id']}", {"alpha_typical_pct": 1}),
        ("DELETE", f"{API}/catalog/hops/{hop['id']}", None),
        ("PATCH", f"{API}/catalog/yeasts/{yeast['id']}", {"lab": "x"}),
        ("DELETE", f"{API}/catalog/yeasts/{yeast['id']}", None),
    ]
    with make_client(app) as other:
        login_as(other, providers, subject="1002")
        for method, url, body in attempts:
            response = other.request(method, url, json=body, headers=CSRF)
            assert response.status_code == 404, (method, url, response.status_code, response.text)
            assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
        others_recipes = other.get(f"{API}/recipes").json()
        assert others_recipes["items"] == []
        others_hops = other.get(f"{API}/catalog/hops", params={"q": "Mine"}).json()
        assert others_hops["items"] == []

    # Nothing changed for the owner.
    payload = client.get(f"{API}/recipes/{recipe['id']}").json()
    assert payload["name"] == "Appendix A Pale Ale"
    assert (
        client.get(f"{API}/catalog/hops", params={"q": "Mine"}).json()["items"][0][
            "alpha_typical_pct"
        ]
        == 5
    )


def test_recipe_quota(seeded: None, app: FastAPI, providers: FakeProviders) -> None:
    settings = make_test_settings(quota_recipes=2)
    small = create_app(settings)
    small.dependency_overrides = app.dependency_overrides
    small.state.oauth = build_oauth(settings, transport=providers.transport)
    with make_client(small) as client:
        login_as(client, providers)
        create(client, name="one")
        create(client, name="two")
        blocked = client.post(f"{API}/recipes", json=recipe_body(name="three"), headers=CSRF)
        assert blocked.status_code == 409
        assert "limit" in blocked.json()["detail"].lower()
        remaining = client.get(f"{API}/recipes").json()["items"]
        assert len(remaining) == 2
    small.state.engine.dispose()


def test_write_rate_limit_is_per_user(seeded: None, app: FastAPI, providers: FakeProviders) -> None:
    settings = make_test_settings(write_rate_limit_per_minute=3)
    limited = create_app(settings)
    limited.dependency_overrides = app.dependency_overrides
    limited.state.oauth = build_oauth(settings, transport=providers.transport)
    with make_client(limited) as client, make_client(limited) as other:
        login_as(client, providers, subject="1001")
        login_as(other, providers, subject="1002")
        for i in range(3):
            create(client, name=f"r{i}")
        blocked = client.post(f"{API}/recipes", json=recipe_body(), headers=CSRF)
        assert blocked.status_code == 429
        # Another user from the same address is unaffected.
        response_ = other.post(f"{API}/recipes", json=recipe_body(), headers=CSRF)
        assert response_.status_code == 201
    limited.state.engine.dispose()


def test_export_includes_recipes_and_custom_ingredients(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    created = create(client)
    client.post(
        f"{API}/catalog/hops", json={"name": "My Hop", "alpha_typical_pct": 9}, headers=CSRF
    )
    export = client.get(f"{API}/me/export").json()
    assert export["schema_version"] == 4
    assert [r["id"] for r in export["recipes"]] == [created["id"]]
    assert export["recipes"][0]["fermentables"][0]["name"] == "2-row pale malt"
    assert export["recipes"][0]["target_style"] == "american-pale-ale"
    assert [h["name"] for h in export["custom_ingredients"]["hops"]] == ["My Hop"]
    assert export["custom_ingredients"]["fermentables"] == []


def test_account_deletion_removes_recipes(
    seeded: None, client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    me = login_as(client, providers)
    create(client)
    create(client, name="second")
    response_ = client.delete(f"{API}/me", headers=CSRF)
    assert response_.status_code == 204
    user_id = uuid.UUID(me["id"])
    remaining = db_connection.execute(
        select(func.count()).select_from(Recipe).where(Recipe.user_id == user_id)
    ).scalar_one()
    assert remaining == 0
    assert db_connection.execute(select(func.count()).select_from(RecipeHop)).scalar_one() == 0
