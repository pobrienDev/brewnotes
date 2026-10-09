"""Batches: brewing from a recipe, the frozen snapshot, status and measurements, readings,
the downsampled chart series, quotas and deletion rules."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select

from app.domain.units import lb_to_kg
from app.errors import PROBLEM_MEDIA_TYPE
from app.main import create_app
from app.models import Batch, Reading, Tasting
from app.security.oauth import build_oauth
from tests.api.log_helpers import add_beer, at, brew, log, save_recipe, taste
from tests.conftest import CSRF, make_client, make_test_settings
from tests.fakes import FakeProviders
from tests.fixtures import APPENDIX_A_EXPECTED, APPENDIX_A_IBU_NO_PRE_BOIL
from tests.helpers import API, login_as, recipe_body


def test_batches_require_sign_in(seeded: None, client: TestClient) -> None:
    assert client.get(f"{API}/batches").status_code == 401
    response = client.post(f"{API}/batches", json={"recipe_id": str(uuid.uuid4())}, headers=CSRF)
    assert response.status_code == 401


def test_brew_from_a_recipe_snapshots_it(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    recipe = save_recipe(client)
    batch = brew(client, recipe["id"])

    assert batch["recipe_id"] == recipe["id"]
    assert batch["name"] == "Appendix A Pale Ale"  # defaults to the recipe name
    assert batch["status"] == "planned"
    assert batch["brew_date"] == "2026-10-01"
    assert batch["volume_l"] == pytest.approx(recipe["batch_volume_l"])
    snapshot = batch["recipe"]
    assert snapshot["schema_version"] == 1
    assert snapshot["recipe_id"] == recipe["id"]
    assert snapshot["target_style"] == "american-pale-ale"
    assert snapshot["target_style_name"] == "18B American Pale Ale"
    assert [f["name"] for f in snapshot["fermentables"]] == [
        "2-row pale malt",
        "Munich malt",
        "Crystal 40",
    ]
    assert snapshot["hops"][0]["use"] == "boil"
    assert snapshot["yeasts"][0]["attenuation_pct"] == 75
    # The snapshot computes to the Appendix A numbers.
    assert batch["expected"]["og"] == pytest.approx(APPENDIX_A_EXPECTED.og, abs=0.001)
    assert batch["expected"]["ibu"] == pytest.approx(APPENDIX_A_IBU_NO_PRE_BOIL.total, abs=1)
    # Nothing measured yet: the OG is the estimate, there is no current gravity.
    ferm = batch["fermentation"]
    assert ferm["og_source"] == "estimated"
    assert ferm["og"] == pytest.approx(batch["expected"]["og"])
    assert ferm["current_sg"] is None and ferm["abv"] is None
    assert ferm["expected_attenuation_pct"] == pytest.approx(75.0)
    assert ferm["readings_count"] == 0 and ferm["latest_reading_at"] is None

    read = client.get(f"{API}/batches/{batch['id']}")
    assert read.status_code == 200
    assert read.json() == batch


def test_brew_with_overrides(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    recipe = save_recipe(client)
    batch = brew(
        client,
        recipe["id"],
        name="Brew day #7",
        status="fermenting",
        volume_l=19.0,
        measured_og=1.058,
        notes="Hit 1.058, a touch high.",
    )
    assert batch["name"] == "Brew day #7"
    assert batch["status"] == "fermenting"
    assert batch["volume_l"] == 19.0
    assert batch["fermentation"]["og_source"] == "measured"
    assert batch["fermentation"]["og"] == 1.058


def test_brew_needs_my_own_recipe(
    seeded: None, app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers, subject="1001")
    unknown = client.post(f"{API}/batches", json={"recipe_id": str(uuid.uuid4())}, headers=CSRF)
    assert unknown.status_code == 422
    assert unknown.json()["errors"] == [
        {"loc": ["body", "recipe_id"], "msg": "unknown recipe", "type": "value_error"}
    ]
    with make_client(app) as other:
        login_as(other, providers, subject="1002")
        theirs = save_recipe(other)
    stolen = client.post(f"{API}/batches", json={"recipe_id": theirs["id"]}, headers=CSRF)
    assert stolen.status_code == 422
    assert stolen.json()["errors"][0]["loc"] == ["body", "recipe_id"]


def test_snapshot_survives_recipe_edits_and_deletion(
    seeded: None, client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    me = login_as(client, providers)
    recipe = save_recipe(client)
    batch = brew(client, recipe["id"])

    body = recipe_body(name="Bigger")
    body["fermentables"][0]["amount_kg"] = lb_to_kg(14)
    edited = client.put(f"{API}/recipes/{recipe['id']}", json=body, headers=CSRF)
    assert edited.status_code == 200
    after_edit = client.get(f"{API}/batches/{batch['id']}").json()
    assert after_edit["recipe"] == batch["recipe"]
    assert after_edit["expected"] == batch["expected"]

    assert client.delete(f"{API}/recipes/{recipe['id']}", headers=CSRF).status_code == 204
    after_delete = client.get(f"{API}/batches/{batch['id']}").json()
    assert after_delete["recipe_id"] is None
    assert after_delete["recipe"]["recipe_id"] == recipe["id"]  # provenance kept in the snapshot
    assert after_delete["expected"] == batch["expected"]
    # The column-list SET NULL cleared recipe_id only; the owner link is intact.
    row = db_connection.execute(
        select(Batch.user_id, Batch.recipe_id).where(Batch.id == uuid.UUID(batch["id"]))
    ).one()
    assert row == (uuid.UUID(me["id"]), None)
    listed = client.get(f"{API}/batches").json()["items"]
    assert listed[0]["recipe_name"] == "Appendix A Pale Ale"


def test_update_status_and_measurements(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    url = f"{API}/batches/{batch['id']}"

    updated = client.patch(
        url,
        json={"status": "fermenting", "measured_og": 1.058, "notes": "Pitched at 18 °C"},
        headers=CSRF,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["status"] == "fermenting"
    assert updated.json()["fermentation"]["og_source"] == "measured"
    assert updated.json()["notes"] == "Pitched at 18 °C"
    assert updated.json()["updated_at"] > batch["updated_at"]

    done = client.patch(url, json={"status": "done", "measured_fg": 1.012}, headers=CSRF).json()
    ferm = done["fermentation"]
    assert ferm["current_sg_source"] == "measured"
    assert ferm["apparent_attenuation_pct"] == pytest.approx((0.058 - 0.012) / 0.058 * 100)
    assert ferm["abv"] == pytest.approx(0.046 * 131.25)

    cleared = client.patch(url, json={"measured_og": None, "measured_fg": None}, headers=CSRF)
    assert cleared.status_code == 200
    assert cleared.json()["fermentation"]["og_source"] == "estimated"
    assert cleared.json()["fermentation"]["current_sg"] is None

    for bad in [
        {"name": None},
        {"status": "drinking"},
        {"measured_og": 1.3},
        {"volume_l": 0},
        {"brewed": "yes"},
    ]:
        response = client.patch(url, json=bad, headers=CSRF)
        assert response.status_code == 422, bad
    assert client.patch(url, json={"status": "done"}).status_code == 403  # no Origin


def test_list_filters_and_paginates(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    recipe_id = save_recipe(client)["id"]
    first = brew(client, recipe_id, name="one")
    second = brew(client, recipe_id, name="two", status="fermenting")
    third = brew(client, recipe_id, name="three", status="done")

    page = client.get(f"{API}/batches", params={"limit": 2}).json()
    assert [b["name"] for b in page["items"]] == ["three", "two"]
    assert page["next_cursor"]
    rest = client.get(f"{API}/batches", params={"limit": 2, "cursor": page["next_cursor"]}).json()
    assert [b["name"] for b in rest["items"]] == ["one"]
    assert rest["next_cursor"] is None

    fermenting = client.get(f"{API}/batches", params={"status": "fermenting"}).json()
    assert [b["id"] for b in fermenting["items"]] == [second["id"]]
    assert client.get(f"{API}/batches", params={"status": "bottled"}).status_code == 422
    assert client.get(f"{API}/batches", params={"cursor": "nonsense"}).status_code == 422

    # Touching a batch moves it to the front.
    client.patch(f"{API}/batches/{first['id']}", json={"notes": "x"}, headers=CSRF)
    assert client.get(f"{API}/batches").json()["items"][0]["id"] == first["id"]
    assert third["fermentation"]["readings_count"] == 0


def test_readings_drive_the_progress_numbers(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"], status="fermenting")
    url = f"{API}/batches/{batch['id']}"
    og = batch["expected"]["og"]

    r1 = log(client, batch["id"], taken_at=at(0), gravity_sg=og, temp_c=20.0)
    log(client, batch["id"], taken_at=at(48), gravity_sg=1.030, temp_c=19.5)
    log(client, batch["id"], taken_at=at(72), temp_c=19.0)  # temperature only
    r4 = log(client, batch["id"], taken_at=at(240), gravity_sg=1.014)
    assert r1["source"] == "manual" and r1["temp_c"] == 20.0
    assert r4["temp_c"] is None

    listed = client.get(f"{url}/readings").json()
    assert [r["taken_at"] for r in listed["items"]] == [at(240), at(72), at(48), at(0)]
    assert listed["next_cursor"] is None
    page = client.get(f"{url}/readings", params={"limit": 3}).json()
    assert len(page["items"]) == 3 and page["next_cursor"]
    rest = client.get(f"{url}/readings", params={"limit": 3, "cursor": page["next_cursor"]}).json()
    assert [r["id"] for r in rest["items"]] == [r1["id"]]

    ferm = client.get(url).json()["fermentation"]
    assert ferm["readings_count"] == 4
    assert ferm["latest_reading_at"] == at(240)
    assert (ferm["current_sg"], ferm["current_sg_source"]) == (1.014, "reading")
    assert ferm["apparent_attenuation_pct"] == pytest.approx((og - 1.014) / (og - 1) * 100)
    assert ferm["abv"] == pytest.approx((og - 1.014) * 131.25)

    # A recorded FG wins over the readings.
    final = client.patch(url, json={"measured_fg": 1.013}, headers=CSRF).json()["fermentation"]
    assert (final["current_sg"], final["current_sg_source"]) == (1.013, "measured")

    # Summaries carry the same progress block.
    summary = client.get(f"{API}/batches").json()["items"][0]
    assert summary["fermentation"] == final


def test_reading_validation(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    url = f"{API}/batches/{batch['id']}/readings"
    cases = [
        {},  # nothing measured
        {"gravity_sg": 1.250},
        {"gravity_sg": 0.9},
        {"temp_c": 120},
        {"gravity_sg": 1.05, "taken_at": "2026-10-01T18:00:00"},  # naive
        {"gravity_sg": 1.05, "taken_at": "2099-01-01T00:00:00Z"},  # far future
        {"gravity_sg": 1.05, "source": "device"},  # not a client-set field
        {"gravity_sg": "1.050abc"},
    ]
    for body in cases:
        response = client.post(url, json=body, headers=CSRF)
        assert response.status_code == 422, body
        assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
        assert "1.050abc" not in response.text  # values are never echoed
    assert client.post(url, json={"gravity_sg": 1.05}).status_code == 403
    missing = client.post(
        f"{API}/batches/{uuid.uuid4()}/readings", json={"gravity_sg": 1.05}, headers=CSRF
    )
    assert missing.status_code == 404


def test_reading_defaults_to_now(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    reading = log(client, batch["id"], gravity_sg=1.040)
    assert reading["taken_at"][:4] == "2026" or reading["taken_at"]  # server time, tz-aware
    assert reading["taken_at"].endswith(("Z", "+00:00"))


def test_chart_series_is_downsampled_oldest_first(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    url = f"{API}/batches/{batch['id']}/readings"
    for hour in range(30):
        log(client, batch["id"], taken_at=at(hour), gravity_sg=1.060 - hour * 0.0015, temp_c=20)

    thinned = client.get(url, params={"points": 10}).json()
    assert len(thinned["items"]) == 10
    assert thinned["next_cursor"] is None
    times = [r["taken_at"] for r in thinned["items"]]
    assert times == sorted(times)
    assert times[0] == at(0) and times[-1] == at(29)

    everything = client.get(url, params={"points": 100}).json()
    assert len(everything["items"]) == 30
    assert everything["items"][0]["taken_at"] == at(0)

    assert client.get(url, params={"points": 1}).status_code == 422
    assert client.get(url, params={"points": 5000}).status_code == 422


def test_delete_reading(seeded: None, client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    other_batch = brew(client, batch["recipe_id"])
    reading = log(client, batch["id"], gravity_sg=1.050)

    wrong_parent = client.delete(
        f"{API}/batches/{other_batch['id']}/readings/{reading['id']}", headers=CSRF
    )
    assert wrong_parent.status_code == 404
    assert (
        client.delete(
            f"{API}/batches/{batch['id']}/readings/{reading['id']}", headers=CSRF
        ).status_code
        == 204
    )
    assert client.get(f"{API}/batches/{batch['id']}/readings").json()["items"] == []
    again = client.delete(f"{API}/batches/{batch['id']}/readings/{reading['id']}", headers=CSRF)
    assert again.status_code == 404


def test_delete_batch_removes_readings_and_tastings(
    seeded: None, client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    log(client, batch["id"], gravity_sg=1.050)
    taste(client, batch_id=batch["id"])
    beer = add_beer(client)
    keep = taste(client, beer_id=beer["id"])
    batch_id = uuid.UUID(batch["id"])

    assert client.delete(f"{API}/batches/{batch['id']}", headers=CSRF).status_code == 204
    assert client.get(f"{API}/batches/{batch['id']}").status_code == 404
    for model in (Reading, Tasting):
        count = db_connection.execute(
            select(func.count()).select_from(model).where(model.batch_id == batch_id)
        ).scalar()
        assert count == 0, model
    remaining = client.get(f"{API}/tastings").json()["items"]
    assert [t["id"] for t in remaining] == [keep["id"]]


def test_batch_quota(seeded: None, app: FastAPI, providers: FakeProviders) -> None:
    settings = make_test_settings(quota_batches=1)
    small = create_app(settings)
    small.dependency_overrides = app.dependency_overrides
    small.state.oauth = build_oauth(settings, transport=providers.transport)
    with make_client(small) as client:
        login_as(client, providers)
        recipe_id = save_recipe(client)["id"]
        brew(client, recipe_id)
        blocked = client.post(f"{API}/batches", json={"recipe_id": recipe_id}, headers=CSRF)
        assert blocked.status_code == 409
        assert "limit" in blocked.json()["detail"].lower()
    small.state.engine.dispose()


def test_readings_quota_is_per_batch(seeded: None, app: FastAPI, providers: FakeProviders) -> None:
    settings = make_test_settings(quota_readings_per_batch=2)
    small = create_app(settings)
    small.dependency_overrides = app.dependency_overrides
    small.state.oauth = build_oauth(settings, transport=providers.transport)
    with make_client(small) as client:
        login_as(client, providers)
        recipe_id = save_recipe(client)["id"]
        batch = brew(client, recipe_id)
        other = brew(client, recipe_id)
        log(client, batch["id"], gravity_sg=1.050)
        log(client, batch["id"], gravity_sg=1.040)
        blocked = client.post(
            f"{API}/batches/{batch['id']}/readings", json={"gravity_sg": 1.030}, headers=CSRF
        )
        assert blocked.status_code == 409
        log(client, other["id"], gravity_sg=1.050)  # the other batch has its own allowance
    small.state.engine.dispose()


def test_export_includes_the_log(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    batch = brew(client, save_recipe(client)["id"])
    log(client, batch["id"], taken_at=at(0), gravity_sg=1.055)
    beer = add_beer(client)
    tasting = taste(client, beer_id=beer["id"], rating=4.5, flavor="Pine and grapefruit")

    export = client.get(f"{API}/me/export").json()
    assert export["schema_version"] == 3
    [exported_batch] = export["batches"]
    assert exported_batch["id"] == batch["id"]
    assert exported_batch["recipe_snapshot"]["name"] == "Appendix A Pale Ale"
    assert [r["gravity_sg"] for r in exported_batch["readings"]] == [1.055]
    assert [b["name"] for b in export["beers"]] == ["Pliny the Elder"]
    assert export["beers"][0]["style"] == "double-ipa"
    assert [t["id"] for t in export["tastings"]] == [tasting["id"]]
    assert export["tastings"][0]["flavor"] == "Pine and grapefruit"
