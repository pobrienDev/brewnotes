"""Breweries: syncing from the upstream CSV, the map query, search, detail, and the links from
beers and tastings."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from app.cli import cli
from app.config import Settings, get_settings
from app.main import create_app
from app.models import Brewery
from app.security.oauth import build_oauth
from app.services import brewery_service
from tests.api.log_helpers import add_beer, brew, save_recipe, taste
from tests.conftest import CSRF, make_client, make_test_settings
from tests.fakes import FakeProviders
from tests.helpers import API, login_as

SAMPLE = Path(__file__).resolve().parent.parent / "data" / "breweries_sample.csv"
T0 = datetime(2026, 9, 1, tzinfo=UTC)
PORTLAND = "-122.75,45.45,-122.55,45.60"


@pytest.fixture
def synced(db_connection: Connection, settings: Settings) -> dict[str, uuid.UUID]:
    """The sample CSV loaded inside the test's transaction; returns ids by name."""
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db, db.begin():
        brewery_service.sync(db, settings, source=str(SAMPLE), now=T0)
        rows = db.scalars(select(Brewery)).all()
        return {b.name: b.id for b in rows}


def _sync(db_connection: Connection, settings: Settings, text: str, now: datetime) -> Any:
    with Session(bind=db_connection, join_transaction_mode="create_savepoint") as db, db.begin():
        return brewery_service.sync(db, settings, source="unused", now=now, fetcher=lambda *_: text)


def test_sync_loads_valid_rows_and_skips_bad_ones(
    db_connection: Connection, settings: Settings
) -> None:
    text = SAMPLE.read_text(encoding="utf-8")
    counts = _sync(db_connection, settings, text, T0)
    assert (counts.created, counts.updated, counts.removed, counts.skipped) == (9, 0, 0, 1)
    assert counts.present == 9
    assert any("longitude" in w for w in counts.warnings)  # the -999 row
    with Session(bind=db_connection) as db:
        taproom = db.scalars(select(Brewery).where(Brewery.name == "Taproom Twenty")).one()
        assert taproom.website_url is None  # "notaurl" dropped, the rest kept
        assert taproom.brewery_type == "taproom"
        someday = db.scalars(select(Brewery).where(Brewery.name == "Someday Brewing")).one()
        assert (someday.latitude, someday.longitude) == (None, None)
        assert someday.synced_at == T0 and someday.removed_at is None
        fiji = db.scalars(select(Brewery).where(Brewery.name == "Dateline Brewing")).one()
        assert fiji.longitude == pytest.approx(178.4419)

    # Running it again changes nothing.
    again = _sync(db_connection, settings, text, T0 + timedelta(days=7))
    assert (again.created, again.updated, again.restored, again.removed) == (0, 0, 0, 0)


def test_sync_updates_removes_and_restores(db_connection: Connection, settings: Settings) -> None:
    lines = SAMPLE.read_text(encoding="utf-8").splitlines()
    _sync(db_connection, settings, "\n".join(lines), T0)
    # Second week: Cascade Hollow renamed, Burnside gone.
    renamed = [
        line.replace("Cascade Hollow Brewing", "Cascade Hollow Beer Co")
        for line in lines
        if "Burnside Brewpub" not in line
    ]
    week2 = _sync(db_connection, settings, "\n".join(renamed), T0 + timedelta(days=7))
    assert (week2.created, week2.updated, week2.removed, week2.restored) == (0, 1, 1, 0)
    with Session(bind=db_connection) as db:
        burnside = db.scalars(select(Brewery).where(Brewery.name == "Burnside Brewpub")).one()
        assert burnside.removed_at == T0 + timedelta(days=7)  # kept, flagged, never deleted
        cascade = db.scalars(select(Brewery).where(Brewery.name == "Cascade Hollow Beer Co")).one()
        assert cascade.synced_at == T0 + timedelta(days=7)
    # Third week: Burnside is back.
    week3 = _sync(db_connection, settings, "\n".join(lines), T0 + timedelta(days=14))
    assert (week3.restored, week3.updated, week3.removed) == (1, 1, 0)  # the rename reverts
    with Session(bind=db_connection) as db:
        burnside = db.scalars(select(Brewery).where(Brewery.name == "Burnside Brewpub")).one()
        assert burnside.removed_at is None


def test_sync_refuses_an_empty_file(db_connection: Connection, settings: Settings) -> None:
    _sync(db_connection, settings, SAMPLE.read_text(encoding="utf-8"), T0)
    with pytest.raises(ValueError, match="no valid rows"):
        _sync(db_connection, settings, "id,name\n", T0 + timedelta(days=7))
    with Session(bind=db_connection) as db:
        assert (
            db.scalar(select(Brewery.removed_at).where(Brewery.name == "Burnside Brewpub")) is None
        )


def test_sync_refuses_oversized_sources(settings: Settings, tmp_path: Path) -> None:
    big = tmp_path / "big.csv"
    big.write_text("x" * 2000)
    with pytest.raises(ValueError, match="larger than"):
        brewery_service.fetch_text(str(big), max_bytes=1000)


def test_map_query(synced: dict[str, uuid.UUID], client: TestClient) -> None:
    response = client.get(f"{API}/breweries", params={"bbox": PORTLAND})
    assert response.status_code == 200, response.text
    data = response.json()
    names = sorted(b["name"] for b in data["items"])
    # Closed is hidden by default; no coordinates means not on the map; bad row never loaded.
    assert names == ["Burnside Brewpub", "Cascade Hollow Brewing", "Taproom Twenty"]
    assert data["truncated"] is False and data["limit"] == 500
    item = next(b for b in data["items"] if b["name"] == "Burnside Brewpub")
    assert item["brewery_type"] == "brewpub"
    assert item["latitude"] == pytest.approx(45.523) and item["longitude"] == pytest.approx(
        -122.6587
    )
    assert item["removed_at"] is None
    assert "address_1" not in item  # summaries stay small

    closed = client.get(f"{API}/breweries", params={"bbox": PORTLAND, "include_closed": "true"})
    assert "Old Town Brewery" in [b["name"] for b in closed.json()["items"]]
    only = client.get(
        f"{API}/breweries", params=[("bbox", PORTLAND), ("type", "micro"), ("type", "closed")]
    )
    assert sorted(b["name"] for b in only.json()["items"]) == [
        "Cascade Hollow Brewing",
        "Old Town Brewery",
    ]
    nothing = client.get(f"{API}/breweries", params={"bbox": "10,10,11,11"})
    assert nothing.json()["items"] == []


def test_map_query_across_the_antimeridian(
    synced: dict[str, uuid.UUID], client: TestClient
) -> None:
    # A box from 170°E across the dateline to 170°W (west > east) holds Fiji and the Chathams.
    response = client.get(f"{API}/breweries", params={"bbox": "170,-50,-170,-10"})
    assert sorted(b["name"] for b in response.json()["items"]) == [
        "Chatham Rise Brewing",
        "Dateline Brewing",
    ]


@pytest.mark.parametrize(
    "bbox",
    ["", "1,2,3", "a,b,c,d", "-122,45,-121,44", "-200,0,-100,10", "0,-95,10,10", "nan,0,1,1"],
)
def test_map_query_rejects_bad_boxes(
    synced: dict[str, uuid.UUID], client: TestClient, bbox: str
) -> None:
    response = client.get(f"{API}/breweries", params={"bbox": bbox})
    assert response.status_code == 422, bbox
    if bbox:
        assert bbox not in response.text  # never echoed


def test_map_query_is_capped(synced: dict[str, uuid.UUID], app: FastAPI) -> None:
    settings = make_test_settings(map_max_results=2)
    small = create_app(settings)
    small.dependency_overrides = app.dependency_overrides
    small.state.oauth = build_oauth(settings, transport=FakeProviders("x").transport)
    with make_client(small) as client:
        data = client.get(f"{API}/breweries", params={"bbox": PORTLAND}).json()
        assert len(data["items"]) == 2 and data["truncated"] is True and data["limit"] == 2
    small.state.engine.dispose()


def test_search_and_types(synced: dict[str, uuid.UUID], client: TestClient) -> None:
    by_city = client.get(f"{API}/breweries/search", params={"q": "portland"}).json()
    assert [b["name"] for b in by_city["items"]] == [
        "Burnside Brewpub",
        "Cascade Hollow Brewing",
        "Old Town Brewery",
        "Someday Brewing",
        "Taproom Twenty",
    ]
    page = client.get(f"{API}/breweries/search", params={"q": "portland", "limit": 2}).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = client.get(
        f"{API}/breweries/search",
        params={"q": "portland", "limit": 2, "cursor": page["next_cursor"]},
    ).json()
    assert [b["name"] for b in rest["items"]] == ["Old Town Brewery", "Someday Brewing"]
    by_name = client.get(f"{API}/breweries/search", params={"q": "giesinger"}).json()
    assert [b["city"] for b in by_name["items"]] == ["München"]
    assert client.get(f"{API}/breweries/search").status_code == 422  # q is required

    types = client.get(f"{API}/breweries/types").json()
    assert {t["brewery_type"]: t["count"] for t in types} == {
        "micro": 3,
        "brewpub": 1,
        "closed": 1,
        "planning": 1,
        "regional": 1,
        "nano": 1,
        "taproom": 1,
    }


def test_detail(synced: dict[str, uuid.UUID], client: TestClient) -> None:
    response = client.get(f"{API}/breweries/{synced['Burnside Brewpub']}")
    assert response.status_code == 200
    data = response.json()
    assert data["address_1"] == "456 E Burnside St" and data["address_2"] == "Suite 2"
    assert data["website_url"] == "https://burnside.example"
    assert data["synced_at"].startswith("2026-09-01")
    assert client.get(f"{API}/breweries/{uuid.uuid4()}").status_code == 404
    assert client.get(f"{API}/breweries/not-a-uuid").status_code == 422


def test_beers_and_tastings_can_link_a_brewery(
    seeded: None, synced: dict[str, uuid.UUID], client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    burnside = str(synced["Burnside Brewpub"])
    beer = add_beer(
        client, name="Burnside IPA", brewery_name="Burnside Brewpub", brewery_id=burnside
    )
    assert beer["brewery"]["id"] == burnside and beer["brewery"]["city"] == "Portland"
    tasting = taste(client, beer_id=beer["id"], brewery_id=burnside)
    assert tasting["brewery"]["name"] == "Burnside Brewpub"
    batch = brew(client, save_recipe(client)["id"])
    at_home = taste(client, batch_id=batch["id"])
    assert at_home["brewery"] is None

    unknown = client.post(
        f"{API}/beers", json={"name": "x", "brewery_id": str(uuid.uuid4())}, headers=CSRF
    )
    assert unknown.status_code == 422
    assert unknown.json()["errors"][0] == {
        "loc": ["body", "brewery_id"],
        "msg": "unknown brewery",
        "type": "value_error",
    }
    unknown_tasting = client.post(
        f"{API}/tastings",
        json={"rating": 4, "beer_id": beer["id"], "brewery_id": str(uuid.uuid4())},
        headers=CSRF,
    )
    assert unknown_tasting.status_code == 422

    moved = client.patch(f"{API}/tastings/{tasting['id']}", json={"brewery_id": None}, headers=CSRF)
    assert moved.status_code == 200 and moved.json()["brewery"] is None
    relinked = client.patch(
        f"{API}/beers/{beer['id']}",
        json={"brewery_id": str(synced["Giesinger Bräu"])},
        headers=CSRF,
    )
    assert relinked.json()["brewery"]["name"] == "Giesinger Bräu"

    export = client.get(f"{API}/me/export").json()
    assert export["schema_version"] == 4
    assert export["beers"][0]["brewery_id"] == str(synced["Giesinger Bräu"])
    assert {t["brewery_id"] for t in export["tastings"]} == {None}


def test_breweries_are_public_and_rate_limited(
    synced: dict[str, uuid.UUID], client: TestClient
) -> None:
    for _ in range(3):
        assert client.get(f"{API}/breweries", params={"bbox": PORTLAND}).status_code == 200
    assert client.get(f"{API}/breweries/types").status_code == 200


def test_sync_breweries_command(
    engine: Any, settings: Settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        for name, value in {
            "APP_ENV": "test",
            "DATABASE_URL": settings.database_url,
            "SECRET_KEY": settings.secret_key,
            "PUBLIC_BASE_URL": settings.public_base_url,
        }.items():
            monkeypatch.setenv(name, value)
        get_settings.cache_clear()
        result = CliRunner().invoke(cli, ["sync-breweries", "--source", str(SAMPLE)])
        assert result.exit_code == 0, result.output
        assert "9 present upstream; 9 created" in result.output
        assert "warning: line 11: longitude" in result.output
        again = CliRunner().invoke(cli, ["sync-breweries", "--source", str(SAMPLE)])
        assert "0 created, 0 updated" in again.output
        missing = CliRunner().invoke(cli, ["sync-breweries", "--source", "/nonexistent.csv"])
        assert missing.exit_code != 0
    finally:
        get_settings.cache_clear()
        with Session(engine) as db, db.begin():
            for row in db.scalars(select(Brewery)):
                db.delete(row)
