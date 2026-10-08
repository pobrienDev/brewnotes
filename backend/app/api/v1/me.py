"""The signed-in user's profile, data export, linked identities and account deletion."""

from __future__ import annotations

from datetime import UTC, datetime
from http import HTTPStatus
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import User, UserSession
from app.models.user import Provider
from app.schemas.account import UserOut, UserUpdate
from app.security.sessions import clear_session_cookie, current_session, current_user
from app.services import account_service, auth_service

router = APIRouter(prefix="/me", tags=["account"])


@router.get("", summary="Profile and linked providers")
def read_me(user: Annotated[User, Depends(current_user)]) -> UserOut:
    return UserOut.model_validate(user)


@router.patch("", summary="Update display name or unit preference")
def update_me(
    patch: UserUpdate,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> UserOut:
    return UserOut.model_validate(account_service.update_profile(db, user, patch))


@router.get(
    "/export",
    summary="Download everything the app holds about this account as JSON",
    response_class=JSONResponse,
    responses={200: {"content": {"application/json": {"schema": {"type": "object"}}}}},
)
def export_me(
    db: Annotated[Session, Depends(get_db)],
    session: Annotated[UserSession | None, Depends(current_session)],
) -> JSONResponse:
    if session is None:
        raise HTTPException(HTTPStatus.UNAUTHORIZED, detail="Sign in required.")
    data = account_service.export(
        db, session.user, current_token_hash=session.token_hash, now=datetime.now(UTC)
    )
    return JSONResponse(
        content=jsonable_encoder(data),
        headers={"Content-Disposition": 'attachment; filename="brewnotes-export.json"'},
    )


@router.delete("", status_code=204, summary="Delete the account and all of its data")
def delete_me(
    request: Request,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    account_service.delete_account(db, user)
    response = Response(status_code=HTTPStatus.NO_CONTENT)
    clear_session_cookie(response, request.app.state.settings)
    return response


@router.delete("/identities/{provider}", status_code=204, summary="Unlink a sign-in provider")
def unlink_identity(
    provider: Provider,
    db: Annotated[Session, Depends(get_db)],
    user: Annotated[User, Depends(current_user)],
) -> Response:
    try:
        removed = auth_service.unlink(db, user, provider.value)
    except auth_service.LastIdentityError:
        raise HTTPException(
            HTTPStatus.CONFLICT,
            detail="Link another sign-in method before removing this one.",
        ) from None
    if not removed:
        raise HTTPException(HTTPStatus.NOT_FOUND, detail="That provider is not linked.")
    return Response(status_code=HTTPStatus.NO_CONTENT)
