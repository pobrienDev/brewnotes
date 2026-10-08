"""Sign-in with GitHub and Google, sessions, logout and identity linking."""

from __future__ import annotations

import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Connection, select, update

from app.config import Settings
from app.errors import PROBLEM_MEDIA_TYPE
from app.models import UserSession
from app.security.oauth import GITHUB_AUTHORIZE_URL
from app.security.sessions import hash_token
from tests.conftest import CSRF, make_client
from tests.fakes import GOOGLE_AUTHORIZE_URL, FakeProviders
from tests.helpers import (
    API,
    cookie_attributes,
    finish,
    is_cleared,
    login,
    login_as,
    set_cookie_headers,
    split_location,
    start_link,
    start_login,
)

SESSION_COOKIE = "__Host-session"
OAUTH_COOKIE = "__Host-oauth"


def _is_problem(response: object) -> bool:

    r: Any = response
    return (
        r.headers["content-type"].startswith(PROBLEM_MEDIA_TYPE)
        and r.json()["status"] == r.status_code
    )


# -- discovery ---------------------------------------------------------------------------


def test_providers_lists_configured_ones(client: TestClient) -> None:
    response = client.get(f"{API}/auth/providers")
    assert response.status_code == 200
    assert response.json() == {"providers": ["github", "google"]}


def test_unknown_provider_is_404(client: TestClient) -> None:
    for path in ("/auth/login/facebook", "/auth/callback/facebook", "/auth/link/facebook"):
        response = client.get(f"{API}{path}")
        assert response.status_code in (401, 404), path
        assert _is_problem(response)
    assert client.get(f"{API}/auth/login/facebook").status_code == 404


# -- starting the flow -------------------------------------------------------------------


def test_login_redirects_to_github_with_state_and_exact_redirect_uri(client: TestClient) -> None:
    response, query = start_login(client, "github")
    base, _ = split_location(response)
    assert base == GITHUB_AUTHORIZE_URL
    assert query["client_id"] == "gh-client-id"
    assert query["redirect_uri"] == "https://testserver/api/v1/auth/callback/github"
    assert query["response_type"] == "code"
    assert len(query["state"]) >= 32
    # GitHub OAuth apps do not support PKCE and only identity is needed, so neither is asked.
    assert "code_challenge" not in query
    assert query.get("scope", "") == ""

    [header] = set_cookie_headers(response, OAUTH_COOKIE)
    attrs = cookie_attributes(header)
    assert attrs["path"] == "/"
    assert attrs["max-age"] == "600"
    assert "httponly" in attrs
    assert "secure" in attrs
    assert attrs["samesite"] == "lax"
    assert "domain" not in attrs


def test_login_redirects_to_google_with_pkce_and_nonce(client: TestClient) -> None:
    response, query = start_login(client, "google")
    base, _ = split_location(response)
    assert base == GOOGLE_AUTHORIZE_URL
    assert query["scope"] == "openid profile"
    assert query["code_challenge_method"] == "S256"
    assert len(query["code_challenge"]) >= 43
    assert len(query["nonce"]) >= 20
    assert query["redirect_uri"] == "https://testserver/api/v1/auth/callback/google"


# -- completing the flow -----------------------------------------------------------------


def test_github_login_creates_account_and_session(
    client: TestClient, providers: FakeProviders
) -> None:
    response = login(client, providers, "github")
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    [header] = set_cookie_headers(response, SESSION_COOKIE)
    attrs = cookie_attributes(header)
    assert attrs["path"] == "/"
    assert attrs["max-age"] == str(30 * 86400)
    assert "httponly" in attrs
    assert "secure" in attrs
    assert attrs["samesite"] == "lax"
    assert "domain" not in attrs
    # The OAuth state cookie is gone once the flow completes.
    [oauth_header] = set_cookie_headers(response, OAUTH_COOKIE)
    assert is_cleared(oauth_header)

    me = client.get(f"{API}/me")
    assert me.status_code == 200
    body = me.json()
    uuid.UUID(body["id"])
    assert body["display_name"] == "Octo Cat"
    assert body["avatar_url"] == providers.github_profile["avatar_url"]
    assert body["unit_pref"] == "imperial"
    assert [i["provider"] for i in body["identities"]] == ["github"]
    assert "email" not in body

    # The token itself is never stored: only its hash is in the database.
    [body_bodies] = providers.token_requests()
    assert body_bodies["code"] == "auth-code-123"
    assert "code_verifier" not in body_bodies


def test_google_login_validates_id_token_and_uses_pkce(
    client: TestClient, providers: FakeProviders
) -> None:
    response = login(client, providers, "google")
    assert response.status_code == 303, response.headers.get("location")
    [token_request] = providers.token_requests()
    assert token_request["code"] == "auth-code-123"
    assert len(token_request["code_verifier"]) >= 43

    me = client.get(f"{API}/me").json()
    assert me["display_name"] == "Gee Mail"
    assert me["avatar_url"] == providers.google_claims["picture"]
    assert [i["provider"] for i in me["identities"]] == ["google"]


@pytest.mark.parametrize(
    "spoil",
    [
        pytest.param({"nonce": "not-the-nonce"}, id="nonce"),
        pytest.param({"exp": int(time.time()) - 600}, id="expired"),
        pytest.param({"aud": "someone-else"}, id="audience"),
        pytest.param({"iss": "https://evil.example"}, id="issuer"),
        pytest.param({"sub": ""}, id="empty-subject"),
        pytest.param("wrong-key", id="signature"),
    ],
)
def test_google_rejects_invalid_id_tokens(
    client: TestClient, providers: FakeProviders, spoil: dict[str, object] | str
) -> None:
    if spoil == "wrong-key":
        providers.sign_with_wrong_key = True
    else:
        assert isinstance(spoil, dict)
        providers.claim_overrides = spoil
    response = login(client, providers, "google")
    assert response.status_code == 303
    assert response.headers["location"] == "/sign-in?error=provider"
    assert not set_cookie_headers(response, SESSION_COOKIE)
    assert client.get(f"{API}/me").status_code == 401


def test_display_name_falls_back_to_login_then_default(
    client: TestClient, providers: FakeProviders
) -> None:
    providers.github_profile["name"] = None
    assert login_as(client, providers)["display_name"] == "octocat"


def test_avatar_from_unexpected_host_is_dropped(
    client: TestClient, providers: FakeProviders
) -> None:
    providers.github_profile["avatar_url"] = "https://evil.example/pixel.png"
    assert login_as(client, providers)["avatar_url"] is None


@pytest.mark.parametrize(
    ("requested", "expected"),
    [
        (
            "/recipes/0192f3a0-1234-7abc-8def-0123456789ab",
            "/recipes/0192f3a0-1234-7abc-8def-0123456789ab",
        ),
        ("/styles?category=21", "/styles?category=21"),
        ("//evil.example/x", "/"),
        ("https://evil.example/x", "/"),
        ("/\\evil.example", "/"),
        ("/api/v1/me/export", "/"),
        ("recipes", "/"),
        ("/has space", "/"),
    ],
)
def test_post_login_destination_is_restricted_to_in_app_paths(
    client: TestClient, providers: FakeProviders, requested: str, expected: str
) -> None:
    response = login(client, providers, "github", next=requested)
    assert response.status_code == 303
    assert response.headers["location"] == expected


def test_tampered_state_is_rejected(client: TestClient, providers: FakeProviders) -> None:
    _, query = start_login(client, "github")
    response = finish(client, "github", query["state"] + "x")
    assert response.status_code == 303
    assert response.headers["location"] == "/sign-in?error=state"
    assert not set_cookie_headers(response, SESSION_COOKIE)
    assert providers.token_requests() == []
    assert client.get(f"{API}/me").status_code == 401


def test_callback_cannot_be_replayed(client: TestClient, providers: FakeProviders) -> None:
    _, query = start_login(client, "github")
    first = finish(client, "github", query["state"])
    assert first.status_code == 303 and first.headers["location"] == "/"
    replay = finish(client, "github", query["state"])
    assert replay.headers["location"] == "/sign-in?error=state"
    assert len(providers.token_requests()) == 1
    # The session from the first, legitimate completion still works.
    assert client.get(f"{API}/me").status_code == 200


def test_callback_without_the_state_cookie_is_rejected(app: FastAPI, client: TestClient) -> None:
    """Login CSRF: an attacker starts a flow and sends the callback URL to a victim."""
    _, query = start_login(client, "github")
    with make_client(app) as victim:
        response = finish(victim, "github", query["state"])
        assert response.headers["location"] == "/sign-in?error=state"
        assert victim.get(f"{API}/me").status_code == 401


def test_provider_denial_is_reported_as_cancelled(client: TestClient) -> None:
    _, query = start_login(client, "github")
    response = client.get(
        f"{API}/auth/callback/github",
        params={
            "error": "access_denied",
            "error_description": "The user denied",
            "state": query["state"],
        },
    )
    assert response.headers["location"] == "/sign-in?error=cancelled"


def test_missing_code_is_a_provider_error(client: TestClient) -> None:
    _, query = start_login(client, "github")
    response = client.get(f"{API}/auth/callback/github", params={"state": query["state"]})
    assert response.headers["location"] == "/sign-in?error=provider"


def test_failed_token_exchange(client: TestClient, providers: FakeProviders) -> None:
    providers.token_endpoint_fails = True
    response = login(client, providers, "github")
    assert response.headers["location"] == "/sign-in?error=provider"
    assert client.get(f"{API}/me").status_code == 401


def test_failed_profile_fetch(client: TestClient, providers: FakeProviders) -> None:
    providers.github_user_fails = True
    response = login(client, providers, "github")
    assert response.headers["location"] == "/sign-in?error=provider"


def test_same_subject_signs_in_to_the_same_account(
    client: TestClient, providers: FakeProviders
) -> None:
    first = login_as(client, providers, subject="1001", name="Octo Cat")
    providers.github_profile["name"] = "Renamed On GitHub"
    providers.github_profile["avatar_url"] = "https://avatars.githubusercontent.com/u/1001?v=5"
    second = login_as(client, providers, subject="1001")
    assert second["id"] == first["id"]
    # The user owns their display name; the avatar follows the provider.
    assert second["display_name"] == "Octo Cat"
    assert second["avatar_url"] == "https://avatars.githubusercontent.com/u/1001?v=5"


def test_different_subjects_get_different_accounts(
    app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    a = login_as(client, providers, subject="1001")
    with make_client(app) as other:
        b = login_as(other, providers, subject="1002", name="Second Brewer")
    assert a["id"] != b["id"]


# -- rate limits -------------------------------------------------------------------------


def test_login_start_is_rate_limited_per_ip(client: TestClient, settings: Settings) -> None:
    limit = settings.login_rate_limit_per_minute
    for _ in range(limit):
        assert client.get(f"{API}/auth/login/github").status_code == 302
    blocked = client.get(f"{API}/auth/login/github")
    assert blocked.status_code == 429
    assert _is_problem(blocked)
    assert int(blocked.headers["retry-after"]) >= 1
    # Callbacks share the login limiter.
    assert client.get(f"{API}/auth/callback/github", params={"state": "x"}).status_code == 429


# -- sessions ----------------------------------------------------------------------------


def _session_row(db: Connection, user_id: str) -> Any:
    rows = db.execute(
        select(UserSession.token_hash, UserSession.last_seen_at, UserSession.expires_at).where(
            UserSession.user_id == uuid.UUID(user_id)
        )
    ).all()
    assert len(rows) == 1
    return rows[0]


def test_session_cookie_is_hashed_in_the_database(
    client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    me = login_as(client, providers)
    raw = client.cookies[SESSION_COOKIE]
    row = _session_row(db_connection, me["id"])
    assert row.token_hash == hash_token(raw)
    assert raw not in row.token_hash
    assert len(raw) >= 43  # 32 random bytes, URL-safe base64


def test_garbage_session_cookie_is_ignored(client: TestClient) -> None:
    client.cookies.set(SESSION_COOKIE, "not-a-real-token")
    assert client.get(f"{API}/me").status_code == 401
    client.cookies.set(SESSION_COOKIE, "x" * 500)
    assert client.get(f"{API}/me").status_code == 401


def test_session_expires_absolutely(
    client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    me = login_as(client, providers)
    now = datetime.now(UTC)
    db_connection.execute(
        update(UserSession)
        .where(UserSession.user_id == uuid.UUID(me["id"]))
        .values(created_at=now - timedelta(days=31), expires_at=now - timedelta(seconds=1))
    )
    assert client.get(f"{API}/me").status_code == 401


def test_session_expires_when_idle(
    client: TestClient, providers: FakeProviders, db_connection: Connection, settings: Settings
) -> None:
    me = login_as(client, providers)
    db_connection.execute(
        update(UserSession)
        .where(UserSession.user_id == uuid.UUID(me["id"]))
        .values(
            last_seen_at=datetime.now(UTC) - timedelta(days=settings.session_idle_days, minutes=1)
        )
    )
    assert client.get(f"{API}/me").status_code == 401


def test_last_seen_is_written_at_most_hourly(
    client: TestClient, providers: FakeProviders, db_connection: Connection
) -> None:
    me = login_as(client, providers)
    user_id = uuid.UUID(me["id"])
    two_hours_ago = datetime.now(UTC) - timedelta(hours=2)
    db_connection.execute(
        update(UserSession).where(UserSession.user_id == user_id).values(last_seen_at=two_hours_ago)
    )
    assert client.get(f"{API}/me").status_code == 200
    touched = _session_row(db_connection, me["id"]).last_seen_at
    assert touched > two_hours_ago + timedelta(hours=1)

    ten_minutes_ago = datetime.now(UTC) - timedelta(minutes=10)
    db_connection.execute(
        update(UserSession)
        .where(UserSession.user_id == user_id)
        .values(last_seen_at=ten_minutes_ago)
    )
    assert client.get(f"{API}/me").status_code == 200
    assert _session_row(db_connection, me["id"]).last_seen_at == ten_minutes_ago


# -- logout ------------------------------------------------------------------------------


def test_logout_requires_matching_origin(client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers)
    missing = client.post(f"{API}/auth/logout")
    assert missing.status_code == 403
    assert _is_problem(missing)
    wrong = client.post(f"{API}/auth/logout", headers={"Origin": "https://evil.example"})
    assert wrong.status_code == 403
    null_origin = client.post(f"{API}/auth/logout", headers={"Origin": "null"})
    assert null_origin.status_code == 403
    assert client.get(f"{API}/me").status_code == 200


def test_logout_revokes_the_session_and_clears_the_cookie(
    client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers)
    raw = client.cookies[SESSION_COOKIE]
    response = client.post(f"{API}/auth/logout", headers=CSRF)
    assert response.status_code == 204
    [header] = set_cookie_headers(response, SESSION_COOKIE)
    assert is_cleared(header)
    assert client.get(f"{API}/me").status_code == 401
    # The old token is dead server-side, not just forgotten by the browser.
    client.cookies.set(SESSION_COOKIE, raw)
    assert client.get(f"{API}/me").status_code == 401


def test_logout_when_not_signed_in_is_fine(client: TestClient) -> None:
    assert client.post(f"{API}/auth/logout", headers=CSRF).status_code == 204


def test_logout_everywhere_revokes_all_sessions_of_this_user_only(
    app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    login_as(client, providers, subject="1001")
    with make_client(app) as phone, make_client(app) as someone_else:
        login_as(phone, providers, subject="1001")
        login_as(someone_else, providers, subject="1002")
        assert phone.get(f"{API}/me").status_code == 200

        response = client.post(f"{API}/auth/logout-all", headers=CSRF)
        assert response.status_code == 200
        assert response.json() == {"sessions_revoked": 2}
        assert client.get(f"{API}/me").status_code == 401
        assert phone.get(f"{API}/me").status_code == 401
        assert someone_else.get(f"{API}/me").status_code == 200


def test_logout_everywhere_requires_sign_in(client: TestClient) -> None:
    response = client.post(f"{API}/auth/logout-all", headers=CSRF)
    assert response.status_code == 401
    assert _is_problem(response)


# -- linking -----------------------------------------------------------------------------


def test_link_requires_sign_in(client: TestClient) -> None:
    response = client.get(f"{API}/auth/link/google")
    assert response.status_code == 401
    assert _is_problem(response)


def test_link_second_provider(client: TestClient, providers: FakeProviders) -> None:
    me = login_as(client, providers, provider="github")
    _, query = start_link(client, "google")
    providers.google_nonce = query["nonce"]
    response = finish(client, "google", query["state"])
    assert response.status_code == 303
    assert response.headers["location"] == "/account?link=linked"
    assert not set_cookie_headers(response, SESSION_COOKIE)

    after = client.get(f"{API}/me").json()
    assert after["id"] == me["id"]
    assert [i["provider"] for i in after["identities"]] == ["github", "google"]

    _, query = start_link(client, "google")
    providers.google_nonce = query["nonce"]
    again = finish(client, "google", query["state"])
    assert again.headers["location"] == "/account?link=already_linked"

    # Signing in with the linked Google identity lands on the same account.
    with make_client(client.app) as fresh:  # type: ignore[arg-type]
        assert login_as(fresh, providers, provider="google")["id"] == me["id"]


def test_cannot_link_an_identity_that_belongs_to_another_account(
    app: FastAPI, client: TestClient, providers: FakeProviders
) -> None:
    with make_client(app) as other:
        login_as(other, providers, provider="google", subject="google-2002")
    me = login_as(client, providers, provider="github")
    _, query = start_link(client, "google")
    providers.google_nonce = query["nonce"]
    response = finish(client, "google", query["state"])
    assert response.headers["location"] == "/account?link=in_use"
    assert [i["provider"] for i in client.get(f"{API}/me").json()["identities"]] == ["github"]
    assert client.get(f"{API}/me").json()["id"] == me["id"]


def test_link_fails_when_signed_out_midway(client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers, provider="github")
    _, query = start_link(client, "google")
    providers.google_nonce = query["nonce"]
    assert client.post(f"{API}/auth/logout", headers=CSRF).status_code == 204
    response = finish(client, "google", query["state"])
    assert response.headers["location"] == "/account?link=failed"
    assert client.get(f"{API}/me").status_code == 401


def test_unlink_keeps_at_least_one_identity(client: TestClient, providers: FakeProviders) -> None:
    login_as(client, providers, provider="github")
    _, query = start_link(client, "google")
    providers.google_nonce = query["nonce"]
    finish(client, "google", query["state"])

    assert client.delete(f"{API}/me/identities/github").status_code == 403  # CSRF
    assert client.delete(f"{API}/me/identities/github", headers=CSRF).status_code == 204
    assert [i["provider"] for i in client.get(f"{API}/me").json()["identities"]] == ["google"]

    last = client.delete(f"{API}/me/identities/google", headers=CSRF)
    assert last.status_code == 409
    assert _is_problem(last)

    gone = client.delete(f"{API}/me/identities/github", headers=CSRF)
    assert gone.status_code == 404
    assert client.delete(f"{API}/me/identities/twitter", headers=CSRF).status_code == 422
