"""The public calculator: Appendix A through the API, and every input bound."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.domain.units import gal_to_l, lb_to_kg, oz_to_g
from app.errors import PROBLEM_MEDIA_TYPE
from tests.conftest import CSRF
from tests.fixtures import (
    APPENDIX_A_EXPECTED,
    APPENDIX_A_IBU_NO_PRE_BOIL,
    APPENDIX_A_IBU_WITH_PRE_BOIL,
)
from tests.helpers import API


def appendix_a_body(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "batch_volume_l": gal_to_l(5.5),
        "boil_time_min": 60,
        "brewhouse_efficiency_pct": 72,
        "fermentables": [
            {
                "name": "2-row pale malt",
                "amount_kg": lb_to_kg(10),
                "ppg": 37,
                "color_lovibond": 2,
                "addition": "mash",
            },
            {
                "name": "Munich malt",
                "amount_kg": lb_to_kg(0.5),
                "ppg": 35,
                "color_lovibond": 9,
                "addition": "mash",
            },
            {
                "name": "Crystal 40",
                "amount_kg": lb_to_kg(1),
                "ppg": 34,
                "color_lovibond": 40,
                "addition": "mash",
            },
        ],
        "hops": [
            {
                "name": "Cascade",
                "amount_g": oz_to_g(1),
                "alpha_pct": 6.5,
                "use": "boil",
                "time_min": 60,
            },
            {
                "name": "Cascade",
                "amount_g": oz_to_g(1),
                "alpha_pct": 6.5,
                "use": "boil",
                "time_min": 10,
            },
            {
                "name": "Centennial",
                "amount_g": oz_to_g(1),
                "alpha_pct": 10,
                "use": "boil",
                "time_min": 5,
            },
        ],
        "yeasts": [{"name": "US-05", "attenuation_pct": 75}],
        "target_style": "american-pale-ale",
    }
    body.update(overrides)
    return body


def _errors(response: Any) -> set[tuple[str | int, ...]]:
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    return {tuple(e["loc"]) for e in response.json()["errors"]}


def test_appendix_a_through_the_api(seeded: None, client: TestClient) -> None:
    response = client.post(f"{API}/calc", json=appendix_a_body(), headers=CSRF)
    assert response.status_code == 200, response.text
    body = response.json()
    stats = body["stats"]
    e = APPENDIX_A_EXPECTED
    assert stats["og"] == pytest.approx(e.og, abs=0.001)
    assert stats["fg"] == pytest.approx(e.fg, abs=0.001)
    assert stats["abv"] == pytest.approx(e.abv, abs=0.1)
    assert stats["ibu"] == pytest.approx(APPENDIX_A_IBU_NO_PRE_BOIL.total, abs=1)
    assert stats["srm"] == pytest.approx(e.srm, abs=0.5)
    assert stats["boil_gravity_mode"] == "og"
    assert [round(c["ibu"], 2) for c in stats["hop_contributions"]] == list(
        APPENDIX_A_IBU_NO_PRE_BOIL.ibu
    )

    top = body["style_matches"][0]
    assert top["slug"] == "american-pale-ale"
    assert top["display_name"] == "18B American Pale Ale"
    assert top["fits"] is True
    assert {m["metric"]: m["status"] for m in top["metrics"]} == dict.fromkeys(
        ("og", "fg", "abv", "ibu", "srm"), "in"
    )
    assert len(body["style_matches"]) == 5
    assert any("original gravity" in note for note in body["notes"])


def test_pre_boil_volume_changes_the_boil_gravity_mode(seeded: None, client: TestClient) -> None:
    response = client.post(
        f"{API}/calc", json=appendix_a_body(pre_boil_volume_l=gal_to_l(6.5)), headers=CSRF
    )
    stats = response.json()["stats"]
    assert stats["boil_gravity_mode"] == "average_of_pre_boil_and_og"
    assert stats["ibu"] == pytest.approx(APPENDIX_A_IBU_WITH_PRE_BOIL.total, abs=1)
    assert any("average of the pre-boil" in note for note in response.json()["notes"])


def test_target_style_is_included_even_when_it_misses(seeded: None, client: TestClient) -> None:
    body = appendix_a_body(target_style="belgian-dark-strong-ale")
    response = client.post(f"{API}/calc", json=body, headers=CSRF)
    matches = response.json()["style_matches"]
    assert len(matches) == 6
    assert matches[-1]["slug"] == "belgian-dark-strong-ale"
    assert matches[-1]["fits"] is False
    low = {m["metric"] for m in matches[-1]["metrics"] if m["status"] == "low"}
    assert {"og", "abv"} <= low


def test_assumed_attenuation_and_whirlpool_notes(seeded: None, client: TestClient) -> None:
    body = appendix_a_body(yeasts=[])
    body["hops"].append(
        {"name": "Citra", "amount_g": 28, "alpha_pct": 12, "use": "whirlpool", "time_min": 20}
    )
    response = client.post(f"{API}/calc", json=body, headers=CSRF).json()
    assert response["stats"]["attenuation_assumed"] is True
    assert response["stats"]["hop_contributions"][-1]["estimated"] is True
    assert any("assumed" in n for n in response["notes"])
    assert any("Whirlpool" in n for n in response["notes"])


def test_calc_requires_origin(seeded: None, client: TestClient) -> None:
    response_ = client.post(f"{API}/calc", json=appendix_a_body())
    assert response_.status_code == 403


@pytest.mark.parametrize(
    ("overrides", "loc"),
    [
        ({"batch_volume_l": 0.4}, ("body", "batch_volume_l")),
        ({"batch_volume_l": 2001}, ("body", "batch_volume_l")),
        ({"pre_boil_volume_l": 2501}, ("body", "pre_boil_volume_l")),
        ({"pre_boil_volume_l": 10}, ("body",)),  # below the batch volume
        ({"boil_time_min": -1}, ("body", "boil_time_min")),
        ({"boil_time_min": 361}, ("body", "boil_time_min")),
        ({"brewhouse_efficiency_pct": 19}, ("body", "brewhouse_efficiency_pct")),
        ({"brewhouse_efficiency_pct": 101}, ("body", "brewhouse_efficiency_pct")),
        ({"steep_efficiency_pct": 19}, ("body", "steep_efficiency_pct")),
        ({"target_style": "x" * 121}, ("body", "target_style")),
        ({"notes": "unknown field"}, ("body", "notes")),
    ],
)
def test_recipe_bounds(
    seeded: None, client: TestClient, overrides: dict[str, Any], loc: tuple[str, ...]
) -> None:
    response = client.post(f"{API}/calc", json=appendix_a_body(**overrides), headers=CSRF)
    assert loc in _errors(response)


@pytest.mark.parametrize(
    "fermentable",
    [
        {"amount_kg": 0},
        {"amount_kg": 1001},
        {"ppg": -1},
        {"ppg": 51},
        {"color_lovibond": 701},
        {"addition": "sprinkle"},
        {"name": ""},
        {"name": "x" * 201},
    ],
)
def test_fermentable_bounds(seeded: None, client: TestClient, fermentable: dict[str, Any]) -> None:
    body = appendix_a_body()
    body["fermentables"][0].update(fermentable)
    response = client.post(f"{API}/calc", json=body, headers=CSRF)
    assert ("body", "fermentables", 0, *fermentable) in _errors(response)


@pytest.mark.parametrize(
    "hop",
    [
        {"amount_g": 0},
        {"amount_g": 10_001},
        {"alpha_pct": 25.1},
        {"time_min": 361},
        {"time_min": -1},
        {"use": "boil", "time_min": 61},  # longer than the 60 minute boil
        {"use": "boil", "time_min": None},
        {"use": "dry_hop", "time_min": None, "dry_hop_days": None},
        {"use": "dry_hop", "time_min": None, "dry_hop_days": 31},
        {"use": "first_wort", "time_min": 30},
        {"use": "whirlpool", "time_min": 20, "dry_hop_days": 2},
    ],
)
def test_hop_bounds(seeded: None, client: TestClient, hop: dict[str, Any]) -> None:
    body = appendix_a_body()
    body["hops"][0].update(hop)
    response = client.post(f"{API}/calc", json=body, headers=CSRF)
    errors = _errors(response)
    assert any(e[:2] == ("body", "hops") or e == ("body",) for e in errors), errors


@pytest.mark.parametrize("attenuation", [39, 101])
def test_yeast_bounds(seeded: None, client: TestClient, attenuation: float) -> None:
    body = appendix_a_body(yeasts=[{"name": "y", "attenuation_pct": attenuation}])
    assert ("body", "yeasts", 0, "attenuation_pct") in _errors(
        client.post(f"{API}/calc", json=body, headers=CSRF)
    )


def test_too_many_ingredients(seeded: None, client: TestClient) -> None:
    body = appendix_a_body()
    body["hops"] = [body["hops"][0]] * 51
    response = client.post(f"{API}/calc", json=body, headers=CSRF)
    assert ("body", "hops") in _errors(response)


def test_nan_is_rejected(seeded: None, client: TestClient) -> None:
    raw = b'{"batch_volume_l": NaN, "boil_time_min": 60}'
    response = client.post(
        f"{API}/calc", content=raw, headers={"content-type": "application/json", **CSRF}
    )
    assert response.status_code == 422


def test_absurd_combination_is_a_validation_error(seeded: None, client: TestClient) -> None:
    body = appendix_a_body(batch_volume_l=0.5)
    body["fermentables"][0]["amount_kg"] = 1000
    response = client.post(f"{API}/calc", json=body, headers=CSRF)
    assert ("body", "fermentables") in _errors(response)
    assert "1.200" in response.json()["detail"]


def test_scale_to_ten_gallons(seeded: None, client: TestClient) -> None:
    response = client.post(
        f"{API}/calc/scale",
        json={
            "recipe": appendix_a_body(pre_boil_volume_l=gal_to_l(6.5)),
            "batch_volume_l": gal_to_l(10),
        },
        headers=CSRF,
    )
    assert response.status_code == 200, response.text
    body = response.json()
    recipe = body["recipe"]
    assert [round(f["amount_kg"] / lb_to_kg(1), 2) for f in recipe["fermentables"]] == [
        18.18,
        0.91,
        1.82,
    ]
    assert all(round(h["amount_g"] / oz_to_g(1), 2) == 1.82 for h in recipe["hops"])
    assert recipe["pre_boil_volume_l"] / gal_to_l(1) == pytest.approx(11.82, abs=0.005)
    assert recipe["boil_time_min"] == 60
    assert recipe["target_style"] == "american-pale-ale"
    assert body["stats"]["og"] == pytest.approx(1.055, abs=0.001)
    assert body["stats"]["ibu"] == pytest.approx(APPENDIX_A_IBU_WITH_PRE_BOIL.total, abs=1)


def test_scale_efficiency_keeps_og(seeded: None, client: TestClient) -> None:
    before = client.post(f"{API}/calc", json=appendix_a_body(), headers=CSRF).json()["stats"]["og"]
    response = client.post(
        f"{API}/calc/scale",
        json={"recipe": appendix_a_body(), "brewhouse_efficiency_pct": 80},
        headers=CSRF,
    ).json()
    assert response["recipe"]["brewhouse_efficiency_pct"] == 80
    assert response["recipe"]["fermentables"][0]["amount_kg"] == pytest.approx(
        lb_to_kg(10) * 72 / 80
    )
    assert response["stats"]["og"] == pytest.approx(before, abs=1e-9)


def test_scale_needs_a_target_and_respects_limits(seeded: None, client: TestClient) -> None:
    nothing = client.post(f"{API}/calc/scale", json={"recipe": appendix_a_body()}, headers=CSRF)
    assert nothing.status_code == 422
    body = appendix_a_body(batch_volume_l=0.5)
    body["fermentables"][0]["amount_kg"] = 900
    too_big = client.post(
        f"{API}/calc/scale", json={"recipe": body, "batch_volume_l": 2000}, headers=CSRF
    )
    assert too_big.status_code == 422
    assert "input limits" in too_big.json()["detail"]


def test_calc_is_rate_limited(seeded: None, client: TestClient) -> None:
    for _ in range(60):
        response_ = client.post(f"{API}/calc", json=appendix_a_body(), headers=CSRF)
        assert response_.status_code == 200
    response_ = client.post(f"{API}/calc", json=appendix_a_body(), headers=CSRF)
    assert response_.status_code == 429
