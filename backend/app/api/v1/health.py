"""Liveness (process responds) and readiness (database answers SELECT 1 quickly)."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter(prefix="/health", tags=["health"])
logger = logging.getLogger(__name__)

READINESS_TIMEOUT_MS = 2000


class HealthStatus(BaseModel):
    status: Literal["ok"]


@router.get("/live", summary="Liveness check")
def live() -> HealthStatus:
    return HealthStatus(status="ok")


@router.get("/ready", summary="Readiness check")
def ready(request: Request) -> HealthStatus:
    engine: Engine = request.app.state.engine
    try:
        with engine.connect() as connection:
            connection.execute(text(f"SET LOCAL statement_timeout = {READINESS_TIMEOUT_MS}"))
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        logger.warning("readiness check failed", extra={"data": {"error": type(exc).__name__}})
        raise HTTPException(
            HTTPStatus.SERVICE_UNAVAILABLE, detail="Database is not reachable."
        ) from None
    return HealthStatus(status="ok")
