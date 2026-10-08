"""Fake GitHub and Google OAuth servers behind an httpx MockTransport.

Authlib talks to these exactly as it would to the real providers, so state handling, PKCE
and ID token validation run for real; only the network is faked.
"""

from __future__ import annotations

import json
import time
from functools import cache
from typing import Any
from urllib.parse import parse_qs

import httpx2 as httpx
from joserfc import jwt
from joserfc.jwk import KeyParameters, RSAKey

from app.security.oauth import GITHUB_API_BASE_URL, GITHUB_TOKEN_URL, GOOGLE_METADATA_URL

GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
GITHUB_USER_URL = GITHUB_API_BASE_URL + "user"

GITHUB_AVATAR = "https://avatars.githubusercontent.com/u/1001?v=4"
GOOGLE_PICTURE = "https://lh3.googleusercontent.com/a/photo=s96-c"


KID = "fake-google-key"


@cache
def _signing_keys() -> tuple[RSAKey, RSAKey]:
    """One real key and one impostor key, generated once per test run."""
    parameters: KeyParameters = {"kid": KID, "use": "sig", "alg": "RS256"}
    return (
        RSAKey.generate_key(2048, parameters=parameters),
        RSAKey.generate_key(2048, parameters=parameters),
    )


def _json(status: int, payload: Any) -> httpx.Response:
    return httpx.Response(status, json=payload)


class FakeProviders:
    def __init__(self, google_client_id: str) -> None:
        self.google_client_id = google_client_id
        self.github_profile: dict[str, Any] = {
            "id": 1001,
            "login": "octocat",
            "name": "Octo Cat",
            "avatar_url": GITHUB_AVATAR,
        }
        self.google_claims: dict[str, Any] = {
            "sub": "google-2002",
            "name": "Gee Mail",
            "picture": GOOGLE_PICTURE,
        }
        # The nonce Authlib put in the authorization URL; tests copy it here so the fake can
        # put it into the ID token like Google would.
        self.google_nonce: str | None = None
        self.claim_overrides: dict[str, Any] = {}
        self.sign_with_wrong_key = False
        self.token_endpoint_fails = False
        self.github_user_fails = False
        self.requests: list[httpx.Request] = []
        self.key, self.wrong_key = _signing_keys()
        self.kid = KID
        self.transport = httpx.MockTransport(self.handle)

    # -- inspection helpers ------------------------------------------------------------
    def token_requests(self) -> list[dict[str, str]]:
        bodies = []
        for request in self.requests:
            if request.method == "POST" and str(request.url) in (
                GITHUB_TOKEN_URL,
                GOOGLE_TOKEN_URL,
            ):
                parsed = parse_qs(request.content.decode())
                bodies.append({k: v[0] for k, v in parsed.items()})
        return bodies

    # -- the fake servers --------------------------------------------------------------
    def handle(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if request.method == "POST" and url == GITHUB_TOKEN_URL:
            if self.token_endpoint_fails:
                return _json(400, {"error": "bad_verification_code"})
            return _json(
                200, {"access_token": "gh-access-token", "token_type": "bearer", "scope": ""}
            )
        if request.method == "GET" and url == GITHUB_USER_URL:
            if request.headers.get("authorization", "").lower() not in (
                "bearer gh-access-token",
                "token gh-access-token",
            ):
                return _json(401, {"message": "Requires authentication"})
            if self.github_user_fails:
                return _json(500, {"message": "boom"})
            return _json(200, self.github_profile)
        if request.method == "GET" and url == GOOGLE_METADATA_URL:
            return _json(
                200,
                {
                    "issuer": GOOGLE_ISSUER,
                    "authorization_endpoint": GOOGLE_AUTHORIZE_URL,
                    "token_endpoint": GOOGLE_TOKEN_URL,
                    "jwks_uri": GOOGLE_JWKS_URL,
                    "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
                    "response_types_supported": ["code"],
                    "subject_types_supported": ["public"],
                    "id_token_signing_alg_values_supported": ["RS256"],
                    "scopes_supported": ["openid", "profile"],
                    "code_challenge_methods_supported": ["S256"],
                },
            )
        if request.method == "GET" and url == GOOGLE_JWKS_URL:
            return _json(200, {"keys": [self.key.as_dict(private=False)]})
        if request.method == "POST" and url == GOOGLE_TOKEN_URL:
            if self.token_endpoint_fails:
                return _json(400, {"error": "invalid_grant"})
            return _json(
                200,
                {
                    "access_token": "google-access-token",
                    "token_type": "Bearer",
                    "expires_in": 3600,
                    "id_token": self._id_token(),
                },
            )
        return httpx.Response(404, text=f"fake provider has no route for {request.method} {url}")

    def _id_token(self) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": GOOGLE_ISSUER,
            "aud": self.google_client_id,
            "iat": now,
            "exp": now + 300,
            "nonce": self.google_nonce,
            **self.google_claims,
        }
        claims.update(self.claim_overrides)
        key = self.wrong_key if self.sign_with_wrong_key else self.key
        return jwt.encode({"alg": "RS256", "kid": self.kid}, claims, key)


def decode_unverified(token: str) -> dict[str, Any]:
    """Payload of a JWT without checking it (for assertions in tests only)."""
    import base64

    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    result: dict[str, Any] = json.loads(base64.urlsafe_b64decode(payload))
    return result
