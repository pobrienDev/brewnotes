"""Accounts: users, the OAuth identities that sign them in, and their server-side sessions.

No email, no password. An account is identified by (provider, provider_subject).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.common import Timestamps, UUIDv7PrimaryKey, now_utc


class Provider(StrEnum):
    GITHUB = "github"
    GOOGLE = "google"


class UnitPref(StrEnum):
    METRIC = "metric"
    IMPERIAL = "imperial"


MAX_DISPLAY_NAME = 200
MAX_URL = 2000


class User(UUIDv7PrimaryKey, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            f"char_length(display_name) BETWEEN 1 AND {MAX_DISPLAY_NAME}",
            name="display_name_length",
        ),
        CheckConstraint("unit_pref IN ('metric', 'imperial')", name="unit_pref"),
    )

    display_name: Mapped[str] = mapped_column(String(MAX_DISPLAY_NAME), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(MAX_URL))
    unit_pref: Mapped[str] = mapped_column(
        String(16), nullable=False, default=UnitPref.IMPERIAL.value, server_default="imperial"
    )

    identities: Mapped[list[OAuthIdentity]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="OAuthIdentity.created_at",
    )
    sessions: Mapped[list[UserSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class OAuthIdentity(UUIDv7PrimaryKey, Base):
    __tablename__ = "oauth_identities"
    __table_args__ = (
        UniqueConstraint("provider", "provider_subject"),
        CheckConstraint("provider IN ('github', 'google')", name="provider"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    provider_subject: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now()
    )
    last_login_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="identities")


class UserSession(UUIDv7PrimaryKey, Base):
    """A browser session. Only the SHA-256 of the cookie token is stored."""

    __tablename__ = "sessions"
    __table_args__ = (CheckConstraint("expires_at > created_at", name="expires_after_created"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=now_utc, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )

    user: Mapped[User] = relationship(back_populates="sessions")
