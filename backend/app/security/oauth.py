"""OAuth sign-in with GitHub and Google through Authlib.

State, PKCE (Google) and nonce live in a short-lived signed cookie managed by Starlette's
SessionMiddleware; Authlib checks state on the callback and validates Google's ID token
(signature, issuer, audience, expiry, nonce). Only identity scopes are requested and no
email is read or stored.
"""

from __future__ import annotations

import re
from typing import Any

import httpx2
from authlib.integrations.starlette_client import OAuth, StarletteOAuth2App
from fastapi import Request

from app.config import Settings
from app.models.user import MAX_DISPLAY_NAME, MAX_URL
from app.services.auth_service import ProviderIdentity

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"  # noqa: S105  # a URL, not a secret
GITHUB_API_BASE_URL = "https://api.github.com/"
GOOGLE_METADATA_URL = "https://accounts.google.com/.well-known/openid-configuration"

PROVIDER_TIMEOUT_S = 10.0
FALLBACK_DISPLAY_NAME = "Brewer"
_ALLOWED_AVATAR_HOSTS = ("avatars.githubusercontent.com", "lh3.googleusercontent.com")
_SAFE_PATH = re.compile(r"^/(?![/\\])[^\s\\\x00-\x1f\x7f]*$")


def build_oauth(settings: Settings, *, transport: httpx2.AsyncBaseTransport | None = None) -> OAuth:
    """Register every provider that has credentials. `transport` lets tests fake the providers."""
    oauth = OAuth()
    http_kwargs: dict[str, Any] = {"timeout": PROVIDER_TIMEOUT_S}
    if transport is not None:
        http_kwargs["transport"] = transport
    if "github" in settings.configured_providers:
        oauth.register(
            "github",
            client_id=settings.github_client_id,
            client_secret=settings.github_client_secret,
            authorize_url=GITHUB_AUTHORIZE_URL,
            access_token_url=GITHUB_TOKEN_URL,
            api_base_url=GITHUB_API_BASE_URL,
            # Empty scope: read-only access to public profile information.
            # GitHub does not support PKCE for OAuth apps, so none is requested.
            client_kwargs={"scope": "", "headers": {"Accept": "application/json"}, **http_kwargs},
        )
    if "google" in settings.configured_providers:
        oauth.register(
            "google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=GOOGLE_METADATA_URL,
            client_kwargs={
                "scope": "openid profile",
                "code_challenge_method": "S256",
                **http_kwargs,
            },
        )
    return oauth


def provider_client(request: Request, provider: str) -> StarletteOAuth2App | None:
    oauth: OAuth = request.app.state.oauth
    if provider not in ("github", "google"):
        return None
    client: StarletteOAuth2App | None = oauth.create_client(provider)
    return client


def safe_next_path(value: str | None) -> str:
    """Only relative in-app paths are allowed as post-login destinations, so the login flow
    cannot be used as an open redirect."""
    if value and len(value) <= 500 and _SAFE_PATH.match(value) and not value.startswith("/api/"):
        return value
    return "/"


def _clean_display_name(value: object) -> str:
    text = str(value).strip() if isinstance(value, str) else ""
    return text[:MAX_DISPLAY_NAME] or FALLBACK_DISPLAY_NAME


def _clean_avatar_url(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > MAX_URL:
        return None
    try:
        url = httpx2.URL(value)
    except httpx2.InvalidURL:
        return None
    if url.scheme != "https" or url.host not in _ALLOWED_AVATAR_HOSTS:
        return None
    return value


async def fetch_identity(
    client: StarletteOAuth2App, provider: str, request: Request
) -> ProviderIdentity:
    """Finish the authorization-code exchange and return who the provider says this is.

    Raises Authlib errors (state mismatch, token errors, invalid ID token) or httpx errors.
    """
    token = await client.authorize_access_token(request)
    if provider == "github":
        response = await client.get("user", token=token)
        response.raise_for_status()
        profile = response.json()
        subject = str(profile["id"])
        name = profile.get("name") or profile.get("login")
        avatar = profile.get("avatar_url")
    else:
        claims = token.get("userinfo")
        if not claims or not claims.get("sub"):
            raise ValueError("Google response had no validated ID token")
        subject = str(claims["sub"])
        name = claims.get("name")
        avatar = claims.get("picture")
    if not subject or len(subject) > 255:
        raise ValueError("Provider returned an unusable subject identifier")
    return ProviderIdentity(
        provider=provider,
        subject=subject,
        display_name=_clean_display_name(name),
        avatar_url=_clean_avatar_url(avatar),
    )
