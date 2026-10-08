"""Sign-in, identity linking and session lifecycle."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy.orm import Session

from app.config import Settings
from app.models import User, UserSession
from app.repositories import identity_repo, session_repo, user_repo
from app.security.sessions import generate_token, hash_token

logger = logging.getLogger(__name__)


def _log(event: str, provider: str, user_id: uuid.UUID) -> None:
    logger.info(event, extra={"data": {"provider": provider, "user_id": str(user_id)}})


@dataclass(frozen=True)
class ProviderIdentity:
    """What a provider told us about the person who just authenticated."""

    provider: str
    subject: str
    display_name: str
    avatar_url: str | None


class LinkOutcome(StrEnum):
    LINKED = "linked"
    ALREADY_LINKED = "already_linked"
    IN_USE = "in_use"


class LastIdentityError(Exception):
    """Raised when unlinking would leave the account with no way to sign in."""


def _start_session(db: Session, settings: Settings, user: User, now: datetime) -> str:
    raw_token = generate_token()
    session_repo.create(
        db,
        user_id=user.id,
        token_hash=hash_token(raw_token),
        now=now,
        lifetime=timedelta(days=settings.session_absolute_days),
    )
    return raw_token


def sign_in(
    db: Session, settings: Settings, identity: ProviderIdentity, now: datetime
) -> tuple[User, str]:
    """Find the account for this (provider, subject) or create one, then open a session.

    Accounts are never matched by email or name, only by the provider's stable subject ID,
    so an attacker who controls an email address cannot take over an account.
    """
    existing = identity_repo.get_by_subject(db, identity.provider, identity.subject)
    if existing is None:
        user = user_repo.create(
            db, display_name=identity.display_name, avatar_url=identity.avatar_url
        )
        identity_repo.create(
            db, user_id=user.id, provider=identity.provider, subject=identity.subject, now=now
        )
        _log("account created", identity.provider, user.id)
    else:
        user = existing.user
        existing.last_login_at = now
        if identity.avatar_url and user.avatar_url != identity.avatar_url:
            user.avatar_url = identity.avatar_url
    raw_token = _start_session(db, settings, user, now)
    _log("signed in", identity.provider, user.id)
    return user, raw_token


def link(db: Session, user: User, identity: ProviderIdentity, now: datetime) -> LinkOutcome:
    """Attach a second provider to a signed-in account."""
    existing = identity_repo.get_by_subject(db, identity.provider, identity.subject)
    if existing is not None:
        return LinkOutcome.ALREADY_LINKED if existing.user_id == user.id else LinkOutcome.IN_USE
    identity_repo.create(
        db, user_id=user.id, provider=identity.provider, subject=identity.subject, now=now
    )
    _log("identity linked", identity.provider, user.id)
    return LinkOutcome.LINKED


def unlink(db: Session, user: User, provider: str) -> bool:
    """Remove a provider from the account. Returns False when the user has no such identity."""
    identity = identity_repo.get_for_user(db, user.id, provider)
    if identity is None:
        return False
    if identity_repo.count_for_user(db, user.id) <= 1:
        raise LastIdentityError
    identity_repo.delete(db, identity)
    return True


def sign_out(db: Session, session: UserSession) -> None:
    session_repo.delete_one(db, session)


def sign_out_everywhere(db: Session, user_id: uuid.UUID) -> int:
    return session_repo.delete_all_for_user(db, user_id)


def purge_expired_sessions(db: Session, settings: Settings, now: datetime) -> int:
    return session_repo.delete_expired(db, now=now, idle=timedelta(days=settings.session_idle_days))
