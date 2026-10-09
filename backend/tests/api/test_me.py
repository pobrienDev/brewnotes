"""Profile, export and account deletion."""

from __future__ import annotations

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, func, select

from app.errors import PROBLEM_MEDIA_TYPE
from app.models import OAuthIdentity, User, UserSession
from tests.conftest import CSRF, make_client
from tests.fakes import FakeProviders
from tests.helpers import API, is_cleared, login_as, set_cookie_headers


def test_me_requires_sign_in(client: TestClient) -> None:
    response = client.get(f"{API}/me")
    assert response.status_code == 401
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert response.json()["detail"] == "Sign in required."


def test_update_profile(client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    response = client.patch(
        f"{API}/me", json={"display_name": "  Pat  ", "unit_pref": "metric"}, headers=CSRF
    )
    assert response.status_code == 200
    assert response.json()["display_name"] == "Pat"
    assert response.json()["unit_pref"] == "metric"
    me = client.get(f"{API}/me").json()
    assert (me["display_name"], me["unit_pref"]) == ("Pat", "metric")

    only_units = client.patch(f"{API}/me", json={"unit_pref": "imperial"}, headers=CSRF)
    assert only_units.json()["display_name"] == "Pat"
    assert only_units.json()["unit_pref"] == "imperial"


@pytest.mark.parametrize(
    "body",
    [
        {"unit_pref": "stone"},
        {"display_name": ""},
        {"display_name": "   "},
        {"display_name": "x" * 201},
        {"nickname": "not-a-field"},
        {"display_name": None},
    ],
)
def test_invalid_profile_updates_are_rejected(
    client: TestClient, providers: FakeProviders, body: dict[str, object]
) -> None:
    login_as(client, providers)
    response = client.patch(f"{API}/me", json=body, headers=CSRF)
    assert response.status_code == 422, response.text
    assert response.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
    assert "x" * 201 not in response.text


def test_update_requires_origin(client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    response_ = client.patch(f"{API}/me", json={"display_name": "Pat"})
    assert response_.status_code == 403
    assert client.get(f"{API}/me").json()["display_name"] == "Octo Cat"


def test_export_contains_everything_about_the_account(
    app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    me = login_as(client, providers)
    with make_client(app) as phone:
        login_as(phone, providers)
    response = client.get(f"{API}/me/export")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="brewnotes-export.json"'
    data = response.json()
    assert data["schema_version"] == 4
    assert data["user"]["id"] == me["id"]
    assert data["user"]["display_name"] == "Octo Cat"
    assert data["identities"] == [
        {
            "provider": "github",
            "provider_subject": "1001",
            "linked_at": data["identities"][0]["linked_at"],
            "last_login_at": data["identities"][0]["last_login_at"],
        }
    ]
    assert sorted(s["current"] for s in data["sessions"]) == [False, True]
    assert all("token" not in key for session in data["sessions"] for key in session)


def test_export_requires_sign_in(client: TestClient) -> None:
    response_ = client.get(f"{API}/me/export")
    assert response_.status_code == 401


def test_delete_account_removes_everything(
    app: FastAPI, client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    me = login_as(client, providers, subject="1001")
    user_id = uuid.UUID(me["id"])
    with make_client(app) as phone, make_client(app) as bystander:
        login_as(phone, providers, subject="1001")
        bystander_me = login_as(bystander, providers, subject="1002")

        response_ = client.delete(f"{API}/me")
        assert response_.status_code == 403  # CSRF
        response = client.delete(f"{API}/me", headers=CSRF)
        assert response.status_code == 204
        [header] = set_cookie_headers(response, "__Host-session")
        assert is_cleared(header)

        response_ = client.get(f"{API}/me")
        assert response_.status_code == 401
        response_ = phone.get(f"{API}/me")
        assert response_.status_code == 401
        response_ = bystander.get(f"{API}/me")
        assert response_.status_code == 200

        def count(model: type[User] | type[OAuthIdentity] | type[UserSession]) -> int:
            column = model.id if model is User else model.user_id  # type: ignore[union-attr]
            return db_connection.execute(
                select(func.count()).select_from(model).where(column == user_id)
            ).scalar_one()

        assert (count(User), count(OAuthIdentity), count(UserSession)) == (0, 0, 0)

        # Signing in again with the same GitHub identity creates a brand new account.
        again = login_as(client, providers, subject="1001")
        assert again["id"] not in (me["id"], bystander_me["id"])
