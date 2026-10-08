"""Idempotent loading of reference data: styles by slug, built-in ingredients by name.

Runs from the `seed` CLI command and from tests. Re-running updates values in place, so the
data files are the source of truth and deploys can re-seed safely.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import Fermentable, Hop, Style, StyleRange, Yeast

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
METRICS = ("og", "fg", "abv", "ibu", "srm")


@dataclass
class SeedCounts:
    styles_created: int = 0
    styles_updated: int = 0
    ranges: int = 0
    fermentables: int = 0
    hops: int = 0
    yeasts: int = 0
    warnings: list[str] = field(default_factory=list)


def load_json(path: Path) -> Any:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


# -- styles --------------------------------------------------------------------------------


def _ranges_from(raw: dict[str, Any], slug: str, counts: SeedCounts) -> list[StyleRange]:
    ranges: list[StyleRange] = []
    for metric, entries in raw.items():
        if metric not in METRICS:
            counts.warnings.append(f"{slug}: unknown metric {metric!r} ignored")
            continue
        for entry in entries:
            low, high = float(entry[0]), float(entry[1])
            label = str(entry[2]) if len(entry) > 2 and entry[2] is not None else None
            if low > high:
                raise ValueError(f"{slug}: {metric} range {low} > {high}")
            ranges.append(StyleRange(metric=metric, min=low, max=high, label=label))
    return ranges


def _upsert_style(
    db: Session,
    raw: dict[str, Any],
    *,
    category_code: str,
    category_name: str,
    parent: Style | None,
    sort_order: int,
    guideline: str,
    version: str,
    counts: SeedCounts,
) -> Style:
    slug = raw["slug"]
    style = db.scalars(select(Style).where(Style.slug == slug)).one_or_none()
    if style is None:
        style = Style(slug=slug, sort_order=sort_order)
        db.add(style)
        counts.styles_created += 1
    else:
        counts.styles_updated += 1
    style.guideline = guideline
    style.guideline_version = version
    style.category_code = category_code
    style.category_name = category_name
    style.code = raw.get("code") if parent is None else None
    style.name = raw["name"]
    style.summary = raw.get("summary", "")
    style.source_url = raw.get("source_url")
    style.sort_order = sort_order
    style.parent = parent
    db.flush()
    db.execute(delete(StyleRange).where(StyleRange.style_id == style.id))
    ranges = _ranges_from(raw.get("ranges", {}), slug, counts)
    for style_range in ranges:
        style_range.style_id = style.id
        db.add(style_range)
    counts.ranges += len(ranges)
    db.flush()
    return style


def seed_styles(db: Session, data: dict[str, Any], counts: SeedCounts | None = None) -> SeedCounts:
    counts = counts or SeedCounts()
    guideline = data.get("guideline", "BJCP")
    version = str(data.get("version", "2021"))
    seen: set[str] = set()
    order = 0
    for category in data["categories"]:
        for raw in category["styles"]:
            order += 10
            parent = _upsert_style(
                db,
                raw,
                category_code=str(category["code"]),
                category_name=category["name"],
                parent=None,
                sort_order=order,
                guideline=guideline,
                version=version,
                counts=counts,
            )
            seen.add(raw["slug"])
            for variant in raw.get("variants", []):
                order += 1
                _upsert_style(
                    db,
                    variant,
                    category_code=str(category["code"]),
                    category_name=category["name"],
                    parent=parent,
                    sort_order=order,
                    guideline=guideline,
                    version=version,
                    counts=counts,
                )
                seen.add(variant["slug"])
    stale = db.scalars(
        select(Style.slug).where(
            Style.guideline == guideline,
            Style.guideline_version == version,
            Style.slug.notin_(seen),
        )
    ).all()
    for slug in stale:
        # Never hard-delete styles (recipes may point at them); just flag it.
        counts.warnings.append(f"style {slug!r} is in the database but not in the data file")
    return counts


# -- ingredients ---------------------------------------------------------------------------


def seed_fermentables(db: Session, items: Iterable[dict[str, Any]], counts: SeedCounts) -> None:
    for item in items:
        row = db.scalars(
            select(Fermentable).where(
                Fermentable.owner_user_id.is_(None), Fermentable.name == item["name"]
            )
        ).one_or_none()
        if row is None:
            row = Fermentable(name=item["name"])
            db.add(row)
        row.type = item["type"]
        row.ppg = float(item["ppg"])
        row.color_lovibond = float(item["color_lovibond"])
        row.default_addition = item["default_addition"]
        counts.fermentables += 1
    db.flush()


def seed_hops(db: Session, items: Iterable[dict[str, Any]], counts: SeedCounts) -> None:
    for item in items:
        row = db.scalars(
            select(Hop).where(Hop.owner_user_id.is_(None), Hop.name == item["name"])
        ).one_or_none()
        if row is None:
            row = Hop(name=item["name"])
            db.add(row)
        row.alpha_typical_pct = float(item["alpha_typical_pct"])
        row.origin = item.get("origin")
        counts.hops += 1
    db.flush()


def seed_yeasts(db: Session, items: Iterable[dict[str, Any]], counts: SeedCounts) -> None:
    for item in items:
        row = db.scalars(
            select(Yeast).where(
                Yeast.owner_user_id.is_(None), Yeast.lab == item["lab"], Yeast.name == item["name"]
            )
        ).one_or_none()
        if row is None:
            row = Yeast(name=item["name"], lab=item["lab"])
            db.add(row)
        row.product_code = item.get("product_code")
        row.attenuation_min_pct = float(item["attenuation_min_pct"])
        row.attenuation_max_pct = float(item["attenuation_max_pct"])
        counts.yeasts += 1
    db.flush()


def seed_all(db: Session, data_dir: Path = DATA_DIR) -> SeedCounts:
    counts = SeedCounts()
    seed_styles(db, load_json(data_dir / "styles_bjcp_2021.json"), counts)
    seed_fermentables(db, load_json(data_dir / "fermentables.json")["items"], counts)
    seed_hops(db, load_json(data_dir / "hops.json")["items"], counts)
    seed_yeasts(db, load_json(data_dir / "yeasts.json")["items"], counts)
    return counts
