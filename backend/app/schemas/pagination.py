"""Cursor (keyset) pagination: {items, next_cursor}, default 50 per page, at most 100."""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from http import HTTPStatus
from typing import Annotated, Any

from fastapi import HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_LIMIT = 50
MAX_LIMIT = 100

LimitParam = Annotated[int, Query(ge=1, le=MAX_LIMIT, description="Page size")]
CursorParam = Annotated[
    str | None, Query(max_length=400, description="Opaque cursor from a previous page")
]


class Page[ItemT: BaseModel](BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[ItemT]
    next_cursor: str | None = Field(
        description="Pass as ?cursor= to fetch the next page; null on the last page"
    )


def encode_cursor(*values: Any) -> str:
    raw = json.dumps(list(values), default=str, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str, expected_length: int) -> list[Any]:
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        values = json.loads(base64.urlsafe_b64decode(padded.encode()))
    except (ValueError, TypeError):
        values = None
    if not isinstance(values, list) or len(values) != expected_length:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid cursor.")
    return values


def decode_time_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """A (timestamp, id) keyset cursor as produced by `encode_cursor(ts.isoformat(), id)`."""
    raw_ts, raw_id = decode_cursor(cursor, 2)
    try:
        return datetime.fromisoformat(str(raw_ts)), uuid.UUID(str(raw_id))
    except ValueError:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid cursor.") from None


def decode_name_cursor(cursor: str) -> tuple[str, uuid.UUID]:
    """A (name, id) keyset cursor for alphabetical lists."""
    raw_name, raw_id = decode_cursor(cursor, 2)
    try:
        return str(raw_name), uuid.UUID(str(raw_id))
    except ValueError:
        raise HTTPException(HTTPStatus.UNPROCESSABLE_CONTENT, detail="Invalid cursor.") from None
