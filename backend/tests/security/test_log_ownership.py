"""Cross-user matrix for the brewing log (plan Section 12): every owned endpoint and method
answers 404 for another user's IDs, body references to another user's rows are unknown (422),
and account deletion takes the whole log with it."""

from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select

from app.errors import PROBLEM_MEDIA_TYPE
from app.models import Batch, Beer, Reading, Tasting
from tests.api.log_helpers import add_beer, brew, log, save_recipe, taste
from tests.conftest import CSRF, make_client
from tests.fakes import FakeProviders
from tests.helpers import API, login_as


def test_cross_user_matrix_for_the_log(
    seeded: None, app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers, subject="1001")
    recipe = save_recipe(client)
    batch = brew(client, recipe["id"])
    reading = log(client, batch["id"], gravity_sg=1.050)
    beer = add_beer(client)
    batch_tasting = taste(client, batch_id=batch["id"])
    beer_tasting = taste(client, beer_id=beer["id"])

    not_found = [
        ("GET", f"{API}/batches/{batch['id']}", None),
        ("PATCH", f"{API}/batches/{batch['id']}", {"name": "hijack"}),
        ("DELETE", f"{API}/batches/{batch['id']}", None),
        ("GET", f"{API}/batches/{batch['id']}/readings", None),
        ("GET", f"{API}/batches/{batch['id']}/readings?points=10", None),
        ("POST", f"{API}/batches/{batch['id']}/readings", {"gravity_sg": 1.001}),
        ("DELETE", f"{API}/batches/{batch['id']}/readings/{reading['id']}", None),
        ("GET", f"{API}/beers/{beer['id']}", None),
        ("PATCH", f"{API}/beers/{beer['id']}", {"name": "hijack"}),
        ("DELETE", f"{API}/beers/{beer['id']}", None),
        ("GET", f"{API}/tastings/{batch_tasting['id']}", None),
        ("PATCH", f"{API}/tastings/{batch_tasting['id']}", {"rating": 0.5}),
        ("DELETE", f"{API}/tastings/{batch_tasting['id']}", None),
        ("GET", f"{API}/tastings/{beer_tasting['id']}", None),
        ("DELETE", f"{API}/tastings/{beer_tasting['id']}", None),
    ]
    unknown_reference = [
        (f"{API}/batches", {"recipe_id": recipe["id"]}, "recipe_id"),
        (f"{API}/tastings", {"rating": 4.0, "batch_id": batch["id"]}, "batch_id"),
        (f"{API}/tastings", {"rating": 4.0, "beer_id": beer["id"]}, "beer_id"),
    ]
    with make_client(app) as other:
        login_as(other, providers, subject="1002")
        for method, url, body in not_found:
            response = other.request(method, url, json=body, headers=CSRF)
            assert response.status_code == 404, (method, url, response.status_code, response.text)
            assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
        for url, body, field in unknown_reference:
            response = other.post(url, json=body, headers=CSRF)
            assert response.status_code == 422, (url, response.text)
            assert response.json()["errors"][0]["loc"] == ["body", field]
        assert other.get(f"{API}/batches").json()["items"] == []
        assert other.get(f"{API}/beers").json()["items"] == []
        assert other.get(f"{API}/tastings").json()["items"] == []
        filtered = other.get(f"{API}/tastings", params={"batch_id": batch["id"]}).json()
        assert filtered["items"] == []

    # Nothing changed for the owner.
    assert client.get(f"{API}/batches/{batch['id']}").json()["name"] == batch["name"]
    readings = client.get(f"{API}/batches/{batch['id']}/readings").json()["items"]
    assert [r["id"] for r in readings] == [reading["id"]]
    assert client.get(f"{API}/beers/{beer['id']}").json()["name"] == "Pliny the Elder"
    assert client.get(f"{API}/tastings/{batch_tasting['id']}").json()["rating"] == 4.0


def test_account_deletion_removes_the_log(
    seeded: None,
    app: FastAPI,
    client: TestClient,
    providers: FakeProviders,
    db_connection: Connection,
) -> None:
    me = login_as(client, providers, subject="1001")
    user_id = uuid.UUID(me["id"])
    batch = brew(client, save_recipe(client)["id"])
    log(client, batch["id"], gravity_sg=1.050)
    beer = add_beer(client)
    taste(client, batch_id=batch["id"])
    taste(client, beer_id=beer["id"])
    with make_client(app) as bystander:
        login_as(bystander, providers, subject="1002")
        theirs = add_beer(bystander, name="Theirs")
        taste(bystander, beer_id=theirs["id"])

    def count(
        model: type[Batch] | type[Beer] | type[Reading] | type[Tasting], owner: uuid.UUID
    ) -> int:
        return (
            db_connection.execute(
                select(func.count()).select_from(model).where(model.user_id == owner)
            ).scalar()
            or 0
        )

    assert (count(Batch, user_id), count(Reading, user_id)) == (1, 1)
    assert (count(Beer, user_id), count(Tasting, user_id)) == (1, 2)
    response_ = client.delete(f"{API}/me", headers=CSRF)
    assert response_.status_code == 204
    for model in (Batch, Reading, Beer, Tasting):
        assert count(model, user_id) == 0, model
    with make_client(app) as bystander:
        login_as(bystander, providers, subject="1002")
        assert len(bystander.get(f"{API}/tastings").json()["items"]) == 1
