from __future__ import annotations

import uuid
from typing import ClassVar, Literal

from pydantic import Field, ValidationInfo, computed_field, field_validator, model_validator

from app.models.catalog import MAX_NAME
from app.schemas.base import Schema

FermentableType = Literal["grain", "extract", "sugar", "adjunct"]
AdditionName = Literal["mash", "steep", "boil", "fermenter"]


class CatalogItemOut(Schema):
    id: uuid.UUID
    name: str
    owner_user_id: uuid.UUID | None = Field(exclude=True, default=None)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def custom(self) -> bool:
        """True for the signed-in user's own entries, False for built-ins."""
        return self.owner_user_id is not None


class FermentableOut(CatalogItemOut):
    type: Literal["grain", "extract", "sugar", "adjunct"]
    ppg: float
    color_lovibond: float
    default_addition: Literal["mash", "steep", "boil", "fermenter"]


class HopOut(CatalogItemOut):
    alpha_typical_pct: float
    origin: str | None


class YeastOut(CatalogItemOut):
    lab: str
    product_code: str | None
    attenuation_min_pct: float
    attenuation_max_pct: float
    attenuation_midpoint_pct: float


# -- writing custom ingredients ----------------------------------------------------------------


class _PartialUpdate(Schema):
    """Partial updates: omit a field to keep it. Only fields listed in `nullable` may be set
    to null (to clear an optional value); any other explicit null is rejected."""

    nullable: ClassVar[frozenset[str]] = frozenset()

    @field_validator("*", mode="before")
    @classmethod
    def _reject_explicit_null(cls, value: object, info: ValidationInfo) -> object:
        if value is None and info.field_name not in cls.nullable:
            raise ValueError("may not be null; omit the field to leave it unchanged")
        return value


class FermentableWrite(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    type: FermentableType
    ppg: float = Field(ge=0, le=50)
    color_lovibond: float = Field(ge=0, le=700)
    default_addition: AdditionName


class FermentableUpdate(_PartialUpdate):
    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    type: FermentableType | None = None
    ppg: float | None = Field(default=None, ge=0, le=50)
    color_lovibond: float | None = Field(default=None, ge=0, le=700)
    default_addition: AdditionName | None = None


class HopWrite(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    alpha_typical_pct: float = Field(ge=0, le=25)
    origin: str | None = Field(default=None, max_length=100)


class HopUpdate(_PartialUpdate):
    nullable: ClassVar[frozenset[str]] = frozenset({"origin"})

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    alpha_typical_pct: float | None = Field(default=None, ge=0, le=25)
    origin: str | None = Field(default=None, max_length=100)


class YeastWrite(Schema):
    name: str = Field(min_length=1, max_length=MAX_NAME)
    lab: str = Field(min_length=1, max_length=100)
    product_code: str | None = Field(default=None, max_length=50)
    attenuation_min_pct: float = Field(ge=40, le=100)
    attenuation_max_pct: float = Field(ge=40, le=100)

    @model_validator(mode="after")
    def _min_le_max(self) -> YeastWrite:
        if self.attenuation_min_pct > self.attenuation_max_pct:
            raise ValueError("attenuation_min_pct must not exceed attenuation_max_pct")
        return self


class YeastUpdate(_PartialUpdate):
    nullable: ClassVar[frozenset[str]] = frozenset({"product_code"})

    name: str | None = Field(default=None, min_length=1, max_length=MAX_NAME)
    lab: str | None = Field(default=None, min_length=1, max_length=100)
    product_code: str | None = Field(default=None, max_length=50)
    attenuation_min_pct: float | None = Field(default=None, ge=40, le=100)
    attenuation_max_pct: float | None = Field(default=None, ge=40, le=100)
