from __future__ import annotations

from typing import Literal

from app.models import Style
from app.schemas.base import Schema


class StyleRangeOut(Schema):
    metric: Literal["og", "fg", "abv", "ibu", "srm"]
    min: float
    max: float
    label: str | None


class StyleSummary(Schema):
    slug: str
    code: str | None
    name: str
    display_name: str
    category_code: str
    category_name: str
    parent_slug: str | None
    ranges: list[StyleRangeOut]

    @classmethod
    def from_model(cls, style: Style) -> StyleSummary:
        return cls(
            slug=style.slug,
            code=style.code,
            name=style.name,
            display_name=style.display_name,
            category_code=style.category_code,
            category_name=style.category_name,
            parent_slug=style.parent.slug if style.parent is not None else None,
            ranges=[StyleRangeOut.model_validate(r) for r in style.ranges],
        )


class StyleDetail(StyleSummary):
    guideline: str
    guideline_version: str
    summary: str
    source_url: str | None
    parent: StyleSummary | None
    variants: list[StyleSummary]

    @classmethod
    def from_model(cls, style: Style) -> StyleDetail:
        base = StyleSummary.from_model(style)
        return cls(
            **base.model_dump(),
            guideline=style.guideline,
            guideline_version=style.guideline_version,
            summary=style.summary,
            source_url=style.source_url,
            parent=StyleSummary.from_model(style.parent) if style.parent is not None else None,
            variants=[StyleSummary.from_model(v) for v in style.variants],
        )
