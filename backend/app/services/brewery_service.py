"""Breweries: sync from Open Brewery DB and the public map, search and detail queries."""

from __future__ import annotations

import csv
import io
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from http import HTTPStatus
from pathlib import Path

import httpx2
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.config import Settings
from app.errors import FieldError, ValidationProblemError
from app.models import Brewery
from app.repositories import brewery_repo
from app.schemas.breweries import (
    BreweryDetail,
    BreweryMapResult,
    BreweryRow,
    BrewerySummary,
    BreweryTypeCount,
    parse_bbox,
)
from app.schemas.pagination import Page, decode_name_cursor, encode_cursor

logger = logging.getLogger(__name__)

DOWNLOAD_TIMEOUT_S = 60.0
MAX_WARNINGS = 50
Fetcher = Callable[[str, int], str]


def _not_found() -> HTTPException:
    return HTTPException(HTTPStatus.NOT_FOUND, detail="No such brewery.")


# -- queries ---------------------------------------------------------------------------------


def to_summary(brewery: Brewery) -> BrewerySummary:
    return BrewerySummary.model_validate(brewery)


def map_breweries(
    db: Session,
    settings: Settings,
    *,
    bbox: str,
    types: list[str] | None,
    include_closed: bool,
) -> BreweryMapResult:
    try:
        box = parse_bbox(bbox)
    except ValueError as exc:
        raise ValidationProblemError(
            [FieldError(loc=["query", "bbox"], msg=str(exc), type="value_error")]
        ) from None
    limit = settings.map_max_results
    cleaned = [t.strip().lower() for t in types if t.strip()] if types else None
    rows = brewery_repo.in_bbox(
        db, box, types=cleaned or None, include_closed=include_closed, limit=limit
    )
    truncated = len(rows) > limit
    return BreweryMapResult(
        items=[to_summary(b) for b in rows[:limit]], truncated=truncated, limit=limit
    )


def search(db: Session, *, q: str, cursor: str | None, limit: int) -> Page[BrewerySummary]:
    after = decode_name_cursor(cursor) if cursor else None
    rows = brewery_repo.search(db, q, after=after, limit=limit)
    has_more = len(rows) > limit
    rows = rows[:limit]
    next_cursor = encode_cursor(rows[-1].name, rows[-1].id) if has_more and rows else None
    return Page(items=[to_summary(b) for b in rows], next_cursor=next_cursor)


def get(db: Session, brewery_id: uuid.UUID) -> BreweryDetail:
    brewery = brewery_repo.get(db, brewery_id)
    if brewery is None:
        raise _not_found()
    return BreweryDetail.model_validate(brewery)


def type_counts(db: Session) -> list[BreweryTypeCount]:
    return [
        BreweryTypeCount(brewery_type=brewery_type, count=count)
        for brewery_type, count in brewery_repo.type_counts(db)
    ]


def check_reference(db: Session, brewery_id: uuid.UUID | None) -> None:
    """A brewery referenced from a beer or tasting must exist (removed ones still count:
    the user may well have been there before it closed)."""
    if brewery_id is not None and brewery_repo.get(db, brewery_id) is None:
        raise ValidationProblemError(
            [FieldError(loc=["body", "brewery_id"], msg="unknown brewery", type="value_error")]
        )


# -- sync ------------------------------------------------------------------------------------


@dataclass
class SyncCounts:
    created: int = 0
    updated: int = 0
    restored: int = 0
    removed: int = 0
    skipped: int = 0
    present: int = 0
    warnings: list[str] = field(default_factory=list)

    def warn(self, message: str) -> None:
        if len(self.warnings) < MAX_WARNINGS:
            self.warnings.append(message)
        elif len(self.warnings) == MAX_WARNINGS:
            self.warnings.append("further warnings suppressed")


def fetch_text(source: str, max_bytes: int) -> str:
    """The CSV from a local path or an https URL, refusing anything over max_bytes."""
    if not source.startswith(("http://", "https://")):
        path = Path(source)
        if path.stat().st_size > max_bytes:
            raise ValueError(f"{source} is larger than {max_bytes} bytes")
        return path.read_text(encoding="utf-8")
    with (
        httpx2.Client(timeout=DOWNLOAD_TIMEOUT_S, follow_redirects=True) as client,
        client.stream("GET", source) as response,
    ):
        response.raise_for_status()
        declared = response.headers.get("content-length")
        if declared and int(declared) > max_bytes:
            raise ValueError(f"{source} declares {declared} bytes, over {max_bytes}")
        chunks: list[bytes] = []
        received = 0
        for chunk in response.iter_bytes():
            received += len(chunk)
            if received > max_bytes:
                raise ValueError(f"{source} exceeded {max_bytes} bytes")
            chunks.append(chunk)
    return b"".join(chunks).decode("utf-8")


def parse_rows(text: str, counts: SyncCounts) -> dict[str, BreweryRow]:
    """Validated rows keyed by upstream id; invalid or duplicate lines are skipped."""
    rows: dict[str, BreweryRow] = {}
    reader = csv.DictReader(io.StringIO(text))
    for number, raw in enumerate(reader, start=2):
        try:
            row = BreweryRow.model_validate({k: v for k, v in raw.items() if k is not None})
        except ValidationError as exc:
            counts.skipped += 1
            first = exc.errors()[0]
            counts.warn(f"line {number}: {'.'.join(str(p) for p in first['loc'])}: {first['msg']}")
            continue
        if row.id in rows:
            counts.skipped += 1
            counts.warn(f"line {number}: duplicate id {row.id}")
            continue
        rows[row.id] = row
    return rows


_COPIED_FIELDS = (
    "name",
    "brewery_type",
    "address_1",
    "address_2",
    "address_3",
    "city",
    "state_province",
    "postal_code",
    "country",
    "latitude",
    "longitude",
    "website_url",
    "phone",
)


def _apply(brewery: Brewery, row: BreweryRow) -> bool:
    changed = False
    for name in _COPIED_FIELDS:
        value = getattr(row, name)
        if getattr(brewery, name) != value:
            setattr(brewery, name, value)
            changed = True
    return changed


def sync(
    db: Session,
    settings: Settings,
    *,
    source: str | None = None,
    now: datetime | None = None,
    fetcher: Fetcher = fetch_text,
) -> SyncCounts:
    """Upsert every upstream row by obdb_id and flag the rest as removed. Idempotent.

    An empty or unparseable file is refused rather than treated as "everything vanished".
    """
    counts = SyncCounts()
    moment = now or datetime.now(UTC)
    text = fetcher(source or settings.brewery_dump_url, settings.brewery_dump_max_bytes)
    rows = parse_rows(text, counts)
    if not rows:
        raise ValueError("the brewery data contained no valid rows; nothing changed")
    existing = brewery_repo.by_obdb_ids(db, rows.keys())
    new_rows: list[Brewery] = []
    for obdb_id, row in rows.items():
        brewery = existing.get(obdb_id)
        if brewery is None:
            brewery = Brewery(obdb_id=obdb_id, synced_at=moment)
            _apply(brewery, row)
            new_rows.append(brewery)
            counts.created += 1
            continue
        if brewery.removed_at is not None:
            brewery.removed_at = None
            counts.restored += 1
        if _apply(brewery, row):
            counts.updated += 1
        brewery.synced_at = moment
    brewery_repo.add_all(db, new_rows)
    db.flush()
    counts.removed = brewery_repo.mark_removed_except(db, list(rows.keys()), moment)
    counts.present = len(rows)
    logger.info(
        "breweries synced",
        extra={
            "created": counts.created,
            "updated": counts.updated,
            "restored": counts.restored,
            "removed": counts.removed,
            "skipped": counts.skipped,
        },
    )
    return counts
