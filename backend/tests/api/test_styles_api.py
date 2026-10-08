from __future__ import annotations

from fastapi.testclient import TestClient

from app.errors import PROBLEM_MEDIA_TYPE
from tests.helpers import API


def _collect(client: TestClient, url: str) -> list[dict[str, object]]:
    items: list[dict[str, object]] = []
    cursor = None
    for _ in range(20):
        response = client.get(url, params={"cursor": cursor} if cursor else None)
        assert response.status_code == 200, response.text
        page = response.json()
        items.extend(page["items"])
        cursor = page["next_cursor"]
        if cursor is None:
            return items
    raise AssertionError("pagination never ended")


def test_styles_are_paginated_in_guideline_order(seeded: None, client: TestClient) -> None:
    first = client.get(f"{API}/styles").json()
    assert len(first["items"]) == 50
    assert first["next_cursor"]
    assert first["items"][0]["slug"] == "american-light-lager"

    everything = _collect(client, f"{API}/styles")
    assert len(everything) == 124
    slugs = [s["slug"] for s in everything]
    assert len(set(slugs)) == 124
    # Variants follow their parent, categories follow the guideline numbering.
    assert (
        slugs.index("specialty-ipa")
        < slugs.index("specialty-ipa-black-ipa")
        < slugs.index("hazy-ipa")
    )
    assert slugs.index("baltic-porter") < slugs.index("weissbier")

    small = _collect(client, f"{API}/styles?limit=7")
    assert [s["slug"] for s in small] == slugs


def test_category_and_search_filters(seeded: None, client: TestClient) -> None:
    ipa = client.get(f"{API}/styles", params={"category": "21"}).json()
    assert [s["display_name"] for s in ipa["items"]][:3] == [
        "21A American IPA",
        "21B Specialty IPA",
        "21B Specialty IPA: Belgian IPA",
    ]
    assert len(ipa["items"]) == 10
    assert ipa["next_cursor"] is None

    by_code = client.get(f"{API}/styles", params={"search": "18B"}).json()
    assert [s["slug"] for s in by_code["items"]] == ["american-pale-ale"]

    by_name = client.get(f"{API}/styles", params={"search": "stout"}).json()
    assert {"irish-stout", "oatmeal-stout", "imperial-stout"} <= {
        s["slug"] for s in by_name["items"]
    }

    nothing = client.get(f"{API}/styles", params={"search": "zzzz"}).json()
    assert nothing == {"items": [], "next_cursor": None}


def test_pagination_parameters_are_validated(seeded: None, client: TestClient) -> None:
    response_ = client.get(f"{API}/styles", params={"limit": 0})
    assert response_.status_code == 422
    response_ = client.get(f"{API}/styles", params={"limit": 101})
    assert response_.status_code == 422
    bad = client.get(f"{API}/styles", params={"cursor": "not-a-cursor"})
    assert bad.status_code == 422
    assert bad.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert (
        client.get(f"{API}/styles", params={"cursor": "WzEsMl0"}).status_code == 422
    )  # [1,2]: bad id


def test_style_detail_with_ranges_variants_and_parent(seeded: None, client: TestClient) -> None:
    apa = client.get(f"{API}/styles/american-pale-ale")
    assert apa.status_code == 200
    body = apa.json()
    assert body["display_name"] == "18B American Pale Ale"
    assert body["guideline"] == "BJCP" and body["guideline_version"] == "2021"
    assert body["parent"] is None and body["variants"] == []
    assert {r["metric"]: (r["min"], r["max"]) for r in body["ranges"]} == {
        "og": (1.045, 1.06),
        "fg": (1.01, 1.015),
        "abv": (4.5, 6.2),
        "ibu": (30, 50),
        "srm": (5, 10),
    }
    assert body["summary"] and "bjcp.org" in body["source_url"]

    specialty = client.get(f"{API}/styles/specialty-ipa").json()
    assert specialty["ranges"] == []
    assert [v["name"] for v in specialty["variants"]][:2] == ["Belgian IPA", "Black IPA"]
    assert specialty["variants"][1]["display_name"] == "21B Specialty IPA: Black IPA"

    black = client.get(f"{API}/styles/specialty-ipa-black-ipa").json()
    assert black["code"] is None
    assert black["parent_slug"] == "specialty-ipa"
    assert black["parent"]["display_name"] == "21B Specialty IPA"

    saison = client.get(f"{API}/styles/saison").json()
    abv = [(r["min"], r["max"], r["label"]) for r in saison["ranges"] if r["metric"] == "abv"]
    expected = [(3.5, 5.0, "table"), (5.0, 7.0, "standard"), (7.0, 9.5, "super")]
    assert [tuple(x) for x in abv] == expected

    missing = client.get(f"{API}/styles/no-such-style")
    assert missing.status_code == 404
    assert missing.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)


def test_public_reads_are_rate_limited(seeded: None, client: TestClient) -> None:
    for _ in range(120):
        response_ = client.get(f"{API}/styles/american-pale-ale")
        assert response_.status_code == 200
    blocked = client.get(f"{API}/styles/american-pale-ale")
    assert blocked.status_code == 429
    assert "retry-after" in blocked.headers
    # The catalog shares the public read budget.
    response_ = client.get(f"{API}/catalog/hops")
    assert response_.status_code == 429
