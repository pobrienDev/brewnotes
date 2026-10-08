from __future__ import annotations

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection
from sqlalchemy.orm import Session

from app.models import Hop
from tests.conftest import make_client
from tests.fakes import FakeProviders
from tests.helpers import API, login_as


def _all(client: TestClient, url: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    cursor = None
    while True:
        page = client.get(url, params={"cursor": cursor} if cursor else None).json()
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            return items


def test_catalog_lists_builtins_alphabetically(seeded: None, client: TestClient) -> None:
    first = client.get(f"{API}/catalog/fermentables").json()
    assert len(first["items"]) == 50 and first["next_cursor"]
    everything = _all(client, f"{API}/catalog/fermentables")
    assert len(everything) == 53
    names = [str(i["name"]) for i in everything]
    assert names == sorted(names)
    assert all(i["custom"] is False for i in everything)
    assert "owner_user_id" not in everything[0]
    crystal = next(i for i in everything if i["name"] == "Crystal 40L")
    assert (crystal["ppg"], crystal["color_lovibond"], crystal["default_addition"]) == (
        34,
        40,
        "steep",
    )


def test_catalog_search(seeded: None, client: TestClient) -> None:
    hops = client.get(f"{API}/catalog/hops", params={"q": "casc"}).json()
    assert [h["name"] for h in hops["items"]] == ["Cascade"]
    assert hops["items"][0]["alpha_typical_pct"] == 5.5
    yeast = client.get(f"{API}/catalog/yeasts", params={"q": "us-05"}).json()
    assert yeast["items"][0]["product_code"] == "US-05"
    assert yeast["items"][0]["attenuation_midpoint_pct"] == 80
    response_ = client.get(f"{API}/catalog/malts")
    assert response_.status_code == 422


def test_users_see_builtins_plus_their_own_entries_only(
    seeded: None,
    app: FastAPI,
    client: TestClient,
    providers: FakeProviders,
    db_connection: Connection,
) -> None:
    me = login_as(client, providers, subject="1001")
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db, db.begin():
        db.add(
            Hop(owner_user_id=uuid.UUID(me["id"]), name="Pat's Backyard Hop", alpha_typical_pct=7.7)
        )

    mine = client.get(f"{API}/catalog/hops", params={"q": "backyard"}).json()["items"]
    assert [h["name"] for h in mine] == ["Pat's Backyard Hop"]
    assert mine[0]["custom"] is True

    assert (
        client.get(f"{API}/catalog/hops", params={"q": "cascade"}).json()["items"][0]["custom"]
        is False
    )

    with make_client(app) as other:
        login_as(other, providers, subject="1002")
        theirs = other.get(f"{API}/catalog/hops", params={"q": "backyard"}).json()
        assert theirs["items"] == []
    with make_client(app) as anonymous:
        public = anonymous.get(f"{API}/catalog/hops", params={"q": "backyard"}).json()
        assert public["items"] == []
