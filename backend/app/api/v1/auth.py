"""Sign-in, identity linking and sign-out.

The two OAuth routes are `async def` because Authlib's client is asynchronous; all of their
database work runs in the thread pool via run_in_threadpool, so the event loop is never
blocked by a synchronous session.
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated, Any

import httpx2
from authlib.common.errors import AuthlibBaseError
from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import RedirectResponse
from joserfc.errors import JoseError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from app.config import Settings
from app.db import get_db
from app.models import User, UserSession
from app.schemas.account import ProvidersOut, SignedOutEverywhere
from app.security.oauth import fetch_identity, provider_client, safe_next_path
from app.security.rate_limit import rate_limit
from app.security.sessions import (
    clear_session_cookie,
    current_session,
    current_user,
    optional_user,
    set_session_cookie,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)

META_PREFIX = "oauth_meta_"
SIGN_IN_PAGE = "/sign-in"
ACCOUNT_PAGE = "/account"

login_rate_limit = rate_limit("login", limit=lambda s: s.login_rate_limit_per_minute)

REDIRECT_RESPONSES: dict[int | str, dict[str, Any]] = {
    302: {"description": "Redirect to the provider's authorization page"},
}


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def _client(request: Request, provider: str) -> Any:
    client = provider_client(request, provider)
    if client is None:
        raise HTTPException(
            HTTPStatus.NOT_FOUND, detail="Unknown or unconfigured sign-in provider."
        )
    return client


async def _start_flow(
    request: Request, provider: str, *, intent: str, next_path: str, user_id: str | None
) -> RedirectResponse:
    client = _client(request, provider)
    settings = _settings(request)
    state = secrets.token_urlsafe(32)
    # One flow at a time per browser: drop leftovers from abandoned attempts.
    for key in [k for k in request.session if k.startswith(META_PREFIX)]:
        request.session.pop(key)
    request.session[META_PREFIX + state] = {
        "provider": provider,
        "intent": intent,
        "next": next_path,
        "user_id": user_id,
    }
    response: RedirectResponse = await client.authorize_redirect(
        request, settings.oauth_redirect_uri(provider), state=state
    )
    return response


@router.get("/providers", summary="Sign-in providers that are configured")
def providers(request: Request) -> ProvidersOut:
    return ProvidersOut(providers=_settings(request).configured_providers)  # type: ignore[arg-type]


@router.get(
    "/login/{provider}",
    status_code=302,
    response_class=RedirectResponse,
    responses=REDIRECT_RESPONSES,
    dependencies=[Depends(login_rate_limit)],
    summary="Start sign-in with GitHub or Google",
)
async def login(
    provider: str,
    request: Request,
    next_path: Annotated[str | None, Query(alias="next", max_length=500)] = None,
) -> RedirectResponse:
    return await _start_flow(
        request, provider, intent="login", next_path=safe_next_path(next_path), user_id=None
    )


@router.get(
    "/link/{provider}",
    status_code=302,
    response_class=RedirectResponse,
    responses=REDIRECT_RESPONSES,
    dependencies=[Depends(login_rate_limit)],
    summary="Link another provider to the signed-in account",
)
async def link(
    provider: str, request: Request, user: Annotated[User, Depends(current_user)]
) -> RedirectResponse:
    return await _start_flow(
        request, provider, intent="link", next_path=ACCOUNT_PAGE, user_id=str(user.id)
    )


def _failed(page: str, code: str) -> RedirectResponse:
    key = "error" if page == SIGN_IN_PAGE else "link"
    return RedirectResponse(f"{page}?{key}={code}", status_code=HTTPStatus.SEE_OTHER)


@router.get(
    "/callback/{provider}",
    status_code=303,
    response_class=RedirectResponse,
    responses={303: {"description": "Redirect into the app; on failure to the sign-in page"}},
    dependencies=[Depends(login_rate_limit)],
    summary="OAuth callback",
)
async def callback(
    provider: str,
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    signed_in: Annotated[User | None, Depends(optional_user)],
) -> RedirectResponse:
    client = _client(request, provider)
    settings = _settings(request)
    state = request.query_params.get("state", "")
    meta = request.session.pop(META_PREFIX + state, None) if state else None
    if not isinstance(meta, dict) or meta.get("provider") != provider:
        logger.warning("oauth state mismatch", extra={"data": {"provider": provider}})
        return _failed(SIGN_IN_PAGE, "state")
    page = ACCOUNT_PAGE if meta.get("intent") == "link" else SIGN_IN_PAGE

    provider_error = request.query_params.get("error")
    if provider_error:
        request.session.clear()
        return _failed(page, "cancelled" if provider_error == "access_denied" else "provider")
    if not request.query_params.get("code"):
        request.session.clear()
        return _failed(page, "provider")

    try:
        identity = await fetch_identity(client, provider, request)
    except (AuthlibBaseError, JoseError, httpx2.HTTPError, ValueError, KeyError) as exc:
        detail = getattr(exc, "error", None) if isinstance(exc, OAuthError) else None
        logger.warning(
            "oauth callback failed",
            extra={"data": {"provider": provider, "error": type(exc).__name__, "code": detail}},
        )
        return _failed(page, "provider")

    now = datetime.now(UTC)
    if meta.get("intent") == "link":
        if signed_in is None or str(signed_in.id) != meta.get("user_id"):
            return _failed(ACCOUNT_PAGE, "failed")
        outcome = await run_in_threadpool(auth_service.link, db, signed_in, identity, now)
        return RedirectResponse(
            f"{ACCOUNT_PAGE}?link={outcome.value}", status_code=HTTPStatus.SEE_OTHER
        )

    _user, raw_token = await run_in_threadpool(auth_service.sign_in, db, settings, identity, now)
    response = RedirectResponse(meta.get("next") or "/", status_code=HTTPStatus.SEE_OTHER)
    set_session_cookie(response, settings, raw_token)
    return response


@router.post("/logout", status_code=204, summary="End this session")
def logout(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession | None, Depends(current_session)],
) -> Response:
    if session is not None:
        auth_service.sign_out(db, session)
    response = Response(status_code=HTTPStatus.NO_CONTENT)
    clear_session_cookie(response, _settings(request))
    return response


@router.post("/logout-all", summary="End every session of this account")
def logout_all(
    request: Request,
    response: Response,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> SignedOutEverywhere:
    revoked = auth_service.sign_out_everywhere(db, user.id)
    clear_session_cookie(response, _settings(request))
    return SignedOutEverywhere(sessions_revoked=revoked)
