from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field, computed_field

from app.schemas.base import Schema


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
