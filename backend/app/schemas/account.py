from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import Field, field_validator

from app.models.user import MAX_DISPLAY_NAME
from app.schemas.base import Schema

ProviderName = Literal["github", "google"]
UnitPreference = Literal["metric", "imperial"]


class IdentityOut(Schema):
    provider: ProviderName
    linked_at: datetime = Field(validation_alias="created_at")
    last_login_at: datetime


class UserOut(Schema):
    id: uuid.UUID
    display_name: str
    avatar_url: str | None
    unit_pref: UnitPreference
    created_at: datetime
    identities: list[IdentityOut]


class UserUpdate(Schema):
    """Partial update: omit a field to leave it alone. Fields cannot be set to null."""

    display_name: str | None = Field(default=None, min_length=1, max_length=MAX_DISPLAY_NAME)
    unit_pref: UnitPreference | None = None

    @field_validator("display_name", "unit_pref", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("may not be null; omit the field to leave it unchanged")
        return value


class ProvidersOut(Schema):
    providers: list[ProviderName]


class SignedOutEverywhere(Schema):
    sessions_revoked: int
