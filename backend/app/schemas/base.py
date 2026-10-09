from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


class Schema(BaseModel):
    """Base for every request and response model.

    NaN and infinity are rejected, unknown fields are rejected, strings are stripped so
    bounds apply to what the user actually typed, and ORM objects can be read directly.
    """

    model_config = ConfigDict(
        allow_inf_nan=False,
        extra="forbid",
        str_strip_whitespace=True,
        from_attributes=True,
    )


class PartialUpdate(Schema):
    """Partial updates (PATCH): omit a field to keep it. Only fields listed in `nullable` may
    be set to null (to clear an optional value); any other explicit null is rejected."""

    nullable: ClassVar[frozenset[str]] = frozenset()

    @field_validator("*", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object, info: ValidationInfo) -> object:
        if value is None and info.field_name not in cls.nullable:
            raise ValueError("may not be null; omit the field to leave it unchanged")
        return value
