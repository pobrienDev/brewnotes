"""Drive the sign-in flow the way a browser would."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlsplit

import httpx2
from fastapi.testclient import TestClient

from tests.fakes import FakeProviders

API = "/api/v1"


def split_location(response: httpx2.Response) -> tuple[str, dict[str, str]]:
    """The Location header as (url without query, query params)."""
    location = response.headers["location"]
    parts = urlsplit(location)
    base = location.split("?", 1)[0]
    query = {k: v[0] for k, v in parse_qs(parts.query, keep_blank_values=True).items()}
    return base, query


def start_login(
    client: TestClient, provider: str, **params: str
) -> tuple[httpx2.Response, dict[str, str]]:
    response = client.get(f"{API}/auth/login/{provider}", params=params)
    assert response.status_code == 302, response.text
    _, query = split_location(response)
    return response, query


def start_link(client: TestClient, provider: str) -> tuple[httpx2.Response, dict[str, str]]:
    response = client.get(f"{API}/auth/link/{provider}")
    assert response.status_code == 302, response.text
    _, query = split_location(response)
    return response, query


def finish(
    client: TestClient, provider: str, state: str, *, code: str = "auth-code-123", **extra: str
) -> httpx2.Response:
    params = {"code": code, "state": state, **extra}
    return client.get(f"{API}/auth/callback/{provider}", params=params)


def login(
    client: TestClient, providers: FakeProviders, provider: str = "github", **params: str
) -> httpx2.Response:
    """Full flow: start, (for Google) copy the nonce into the fake, then the callback."""
    _, query = start_login(client, provider, **params)
    if provider == "google":
        providers.google_nonce = query["nonce"]
    return finish(client, provider, query["state"])


def login_as(
    client: TestClient,
    providers: FakeProviders,
    *,
    provider: str = "github",
    subject: str | None = None,
    name: str | None = None,
) -> dict[str, Any]:
    """Sign the client in and return the /me payload."""
    if provider == "github":
        if subject is not None:
            providers.github_profile["id"] = int(subject)
        if name is not None:
            providers.github_profile["name"] = name
    else:
        if subject is not None:
            providers.google_claims["sub"] = subject
        if name is not None:
            providers.google_claims["name"] = name
    response = login(client, providers, provider)
    assert response.status_code == 303, response.text
    me = client.get(f"{API}/me")
    assert me.status_code == 200, me.text
    result: dict[str, Any] = me.json()
    return result


def set_cookie_headers(response: httpx2.Response, name: str) -> list[str]:
    return [h for h in response.headers.get_list("set-cookie") if h.startswith(f"{name}=")]


def cookie_attributes(header: str) -> dict[str, str]:
    """`name=value; Path=/; HttpOnly` -> {"path": "/", "httponly": ""} (keys lower-cased)."""
    attrs: dict[str, str] = {}
    for part in header.split(";")[1:]:
        key, _, value = part.strip().partition("=")
        attrs[key.lower()] = value
    return attrs


def is_cleared(header: str) -> bool:
    """A Set-Cookie header that deletes the cookie (Max-Age=0 or an expiry in the past)."""
    attrs = cookie_attributes(header)
    return attrs.get("max-age") == "0" or attrs.get("expires", "").startswith("Thu, 01 Jan 1970")
