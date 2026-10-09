"""Style recommendations: the cold start, ratings per style and family gathered from beers
and batches, explained suggestions, and isolation between users (plan Phase 4)."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.api.log_helpers import add_beer, brew, save_recipe, taste
from tests.conftest import CSRF, make_client
from tests.fakes import FakeProviders
from tests.helpers import API, login_as

URL = f"{API}/recommendations/styles"
ANSWERS = {"strength": "strong", "bitterness": "bitter", "color": "pale"}


def test_requires_sign_in(seeded: None, client: TestClient) -> None:
    assert client.get(URL).status_code == 401


def test_cold_start_asks_for_answers_and_uses_them(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    empty = client.get(URL)
    assert empty.status_code == 200, empty.text
    assert empty.json() == {
        "tastings_with_style": 0,
        "min_tastings": 5,
        "cold_start": True,
        "answered": False,
        "styles": [],
        "families": [],
        "suggestions": [],
    }

    answered = client.get(URL, params={**ANSWERS, "limit": 3}).json()
    assert answered["cold_start"] is True and answered["answered"] is True
    assert len(answered["suggestions"]) == 3
    first = answered["suggestions"][0]
    assert "IPA" in first["style"]["display_name"]
    assert first["style"]["ranges"], "suggestions carry the style's ranges for display"
    assert first["score"] > 0
    (reason,) = first["because"]
    assert reason["kind"] == "answers"
    assert reason["style"] is None and reason["rating"] is None and reason["count"] == 0
    assert reason["distance"] >= 0
    assert all(d["direction"] in ("higher", "lower") for d in first["differences"])
    scores = [s["score"] for s in answered["suggestions"]]
    assert scores == sorted(scores, reverse=True)

    one_answer = client.get(URL, params={"color": "dark"}).json()
    assert one_answer["answered"] is True
    assert len(one_answer["suggestions"]) == 10


def test_ratings_from_beers_and_batches_drive_the_suggestions(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    recipe = save_recipe(client)  # targets 18B American Pale Ale
    batch = brew(client, recipe["id"])
    ipa = add_beer(client, name="Two Hearted", brewery_name="Bell's", style="american-ipa")
    dipa = add_beer(client)  # Pliny, double-ipa
    stout = add_beer(client, name="Guinness", brewery_name="Guinness", style="irish-stout")
    lager = add_beer(client, name="Budweiser", brewery_name="AB", style="american-lager")
    unstyled = add_beer(client, name="Mystery", brewery_name=None, style=None, abv=None)
    for rating in (4.5, 4.5, 5.0, 4.0):
        taste(client, beer_id=ipa["id"], rating=rating)
    taste(client, beer_id=dipa["id"], rating=4.0)
    for rating in (4.0, 4.0, 4.0):
        taste(client, beer_id=stout["id"], rating=rating)
    taste(client, beer_id=lager["id"], rating=2.0)
    taste(client, beer_id=lager["id"], rating=2.0)
    taste(client, batch_id=batch["id"], rating=3.5)  # counts through the recipe snapshot
    taste(client, beer_id=unstyled["id"], rating=5.0)  # no style: cannot count

    result = client.get(URL).json()
    assert result["tastings_with_style"] == 11
    assert result["cold_start"] is False and result["answered"] is False
    assert [(s["slug"], s["count"], s["mean"]) for s in result["styles"]] == [
        ("american-ipa", 4, 4.5),
        ("irish-stout", 3, 4.0),
        ("double-ipa", 1, 4.0),
        ("american-pale-ale", 1, 3.5),
        ("american-lager", 2, 2.0),
    ]
    assert result["styles"][0]["display_name"] == "21A American IPA"
    assert result["styles"][0]["category_name"] == "IPA"
    assert [(f["category_code"], f["count"], f["mean"]) for f in result["families"]] == [
        ("21", 4, 4.5),
        ("15", 3, 4.0),
        ("22", 1, 4.0),
        ("18", 1, 3.5),
        ("1", 2, 2.0),
    ]
    assert result["families"][1]["category_name"] == "Irish Beer"

    suggestions = result["suggestions"]
    assert len(suggestions) == 10
    tried = {s["slug"] for s in result["styles"]}
    assert not tried & {s["style"]["slug"] for s in suggestions}
    assert "english-ipa" in [s["style"]["slug"] for s in suggestions[:3]]
    for suggestion in suggestions:
        reason = suggestion["because"][0]
        assert reason["kind"] == "style"
        assert reason["style"]["slug"] in {"american-ipa", "irish-stout", "double-ipa"}
        assert reason["count"] >= 1 and reason["rating"] >= 4.0
    english_ipa = next(s for s in suggestions if s["style"]["slug"] == "english-ipa")
    assert english_ipa["because"][0]["style"]["display_name"] == "21A American IPA"
    assert english_ipa["because"][0] == {
        "kind": "style",
        "style": {
            "slug": "american-ipa",
            "display_name": "21A American IPA",
            "category_code": "21",
            "category_name": "IPA",
        },
        "rating": 4.5,
        "count": 4,
        "distance": english_ipa["because"][0]["distance"],
    }

    three = client.get(URL, params={"limit": 3}).json()
    assert [s["style"]["slug"] for s in three["suggestions"]] == [
        s["style"]["slug"] for s in suggestions[:3]
    ]

    # Answers still count alongside ratings, but the mode is no longer a cold start.
    blended = client.get(URL, params={"color": "dark"}).json()
    assert blended["cold_start"] is False and blended["answered"] is True
    assert any(r["kind"] == "answers" for s in blended["suggestions"] for r in s["because"])

    # The batch keeps counting after its recipe is gone (the snapshot names the style).
    deleted = client.delete(f"{API}/recipes/{recipe['id']}", headers=CSRF)
    assert deleted.status_code == 204
    after = client.get(URL).json()
    assert ("american-pale-ale", 1, 3.5) in [
        (s["slug"], s["count"], s["mean"]) for s in after["styles"]
    ]
    # Deleting a beer takes its tastings, and so its rating, with it.
    gone = client.delete(f"{API}/beers/{lager['id']}", headers=CSRF)
    assert gone.status_code == 204
    after = client.get(URL).json()
    assert "american-lager" not in [s["slug"] for s in after["styles"]]
    assert after["tastings_with_style"] == 9


def test_parameters_are_validated_without_echoing_them(
    seeded: None, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    for params in ({"limit": 0}, {"limit": 51}, {"strength": "zzqqxx"}, {"color": "zzqqxx"}):
        response = client.get(URL, params=params)
        assert response.status_code == 422, params
        assert "zzqqxx" not in response.text


def test_other_users_tastings_never_count(
    seeded: None, app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers, subject="1001")
    ipa = add_beer(client, style="american-ipa")
    for _ in range(5):
        taste(client, beer_id=ipa["id"], rating=5.0)
    mine = client.get(URL).json()
    assert mine["tastings_with_style"] == 5 and mine["cold_start"] is False

    with make_client(app) as other:
        login_as(other, providers, subject="1002")
        theirs = other.get(URL).json()
        assert theirs["tastings_with_style"] == 0
        assert theirs["styles"] == [] and theirs["suggestions"] == []
        assert theirs["cold_start"] is True
