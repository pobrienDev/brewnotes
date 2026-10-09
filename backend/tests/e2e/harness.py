"""BrewNotes with a fake GitHub sign-in, for browser tests and local walk-throughs.

    uv run uvicorn tests.e2e.harness:app --port 8001

Settings come from the environment and .env exactly as for the real server; only the GitHub
OAuth app is replaced. "Continue with GitHub" lands on this process's own
/api/v1/fake-github/authorize, which plays the authorization server and sends the browser
straight back to the callback with a code. The token exchange and profile fetch are answered
by the same in-memory fake the API tests use, so Authlib's state check and the rest of the
sign-in path run for real. GET /api/v1/fake-github/become?subject=1002&name=Second%20Brewer
chooses which GitHub account the next sign-in represents.

This module lives under tests/ and is never imported by the application.
"""

from __future__ import annotations

from http import HTTPStatus
from urllib.parse import urlencode

from fastapi import HTTPException, Request
from fastapi.responses import RedirectResponse, Response
from starlette.routing import Route

from app.config import Settings
from app.main import create_app
from app.security.oauth import build_oauth
from tests.fakes import FakeProviders

FAKE_CODE = "fake-auth-code"
AUTHORIZE_PATH = "/api/v1/fake-github/authorize"
BECOME_PATH = "/api/v1/fake-github/become"


def build() -> tuple[object, FakeProviders]:
    settings = Settings(
        github_client_id="fake-github-client-id",
        github_client_secret="fake-github-client-secret",
        # Browser tests sign in many times a minute from one address.
        login_rate_limit_per_minute=1000,
    )
    application = create_app(settings)
    fake = FakeProviders(google_client_id=settings.google_client_id or "")
    oauth = build_oauth(settings, transport=fake.transport)
    github = oauth.create_client("github")
    github.authorize_url = settings.public_base_url + AUTHORIZE_PATH
    application.state.oauth = oauth
    application.state.fake_providers = fake

    async def authorize(request: Request) -> Response:
        redirect_uri = request.query_params.get("redirect_uri", "")
        state = request.query_params.get("state", "")
        if not redirect_uri.startswith(settings.public_base_url + "/") or not state:
            raise HTTPException(HTTPStatus.BAD_REQUEST, detail="Bad fake authorization request.")
        return RedirectResponse(
            f"{redirect_uri}?{urlencode({'code': FAKE_CODE, 'state': state})}",
            status_code=HTTPStatus.FOUND,
        )

    async def become(request: Request) -> Response:
        subject = request.query_params.get("subject", "1001")
        if not subject.isdigit():
            raise HTTPException(HTTPStatus.BAD_REQUEST, detail="subject must be digits")
        fake.github_profile["id"] = int(subject)
        fake.github_profile["login"] = f"user{subject}"
        fake.github_profile["name"] = request.query_params.get("name", f"Brewer {subject}")
        return Response(status_code=HTTPStatus.NO_CONTENT)

    # In front of everything else so the SPA fallback mount never swallows these paths.
    application.router.routes.insert(0, Route(AUTHORIZE_PATH, authorize, methods=["GET"]))
    application.router.routes.insert(0, Route(BECOME_PATH, become, methods=["GET"]))
    return application, fake


app, fake_providers = build()
