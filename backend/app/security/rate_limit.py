"""In-memory sliding-window rate limits. Correct for one instance; several instances need a
shared store (plan, Section 13)."""

from __future__ import annotations

import math
import threading
import time
from collections import deque
from collections.abc import Callable
from http import HTTPStatus
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from app.config import Settings
from app.models import User
from app.security.sessions import current_user

Clock = Callable[[], float]


class SlidingWindowLimiter:
    def __init__(self, limit: int, window_s: float, clock: Clock = time.monotonic) -> None:
        self.limit = limit
        self.window_s = window_s
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def hit(self, key: str) -> tuple[bool, int]:
        """Record a hit. Returns (allowed, seconds until the next allowed hit)."""
        now = self._clock()
        with self._lock:
            hits = self._hits.get(key)
            if hits is None:
                hits = self._hits[key] = deque()
            cutoff = now - self.window_s
            while hits and hits[0] <= cutoff:
                hits.popleft()
            if len(hits) >= self.limit:
                return False, max(1, math.ceil(hits[0] + self.window_s - now))
            hits.append(now)
            if len(self._hits) > 10_000:
                self._purge(cutoff)
            return True, 0

    def _purge(self, cutoff: float) -> None:
        for key in [k for k, v in self._hits.items() if not v or v[-1] <= cutoff]:
            del self._hits[key]


def client_ip(request: Request) -> str:
    """The client address as uvicorn reports it. With --proxy-headers and a trusted proxy list,
    that is the real client; raw X-Forwarded-For is never read here."""
    return request.client.host if request.client else "unknown"


def _hit(
    request: Request, name: str, limit: int | Callable[[Settings], int], window_s: float, key: str
) -> None:
    limiters: dict[str, SlidingWindowLimiter] = request.app.state.rate_limiters
    limiter = limiters.get(name)
    if limiter is None:
        settings: Settings = request.app.state.settings
        resolved = limit(settings) if callable(limit) else limit
        limiter = limiters[name] = SlidingWindowLimiter(resolved, window_s)
    allowed, retry_after = limiter.hit(key)
    if not allowed:
        raise HTTPException(
            HTTPStatus.TOO_MANY_REQUESTS,
            detail="Too many requests. Try again shortly.",
            headers={"Retry-After": str(retry_after)},
        )


def rate_limit(
    name: str, *, limit: int | Callable[[Settings], int], window_s: float = 60.0
) -> Callable[[Request], None]:
    """Dependency factory: `Depends(rate_limit("login", limit=10))`, keyed by client IP.
    `limit` may be a function of the settings so values stay configurable."""

    def dependency(request: Request) -> None:
        _hit(request, name, limit, window_s, client_ip(request))

    return dependency


def user_rate_limit(
    name: str, *, limit: int | Callable[[Settings], int], window_s: float = 60.0
) -> Callable[..., None]:
    """Like rate_limit but keyed by the signed-in user (401 problem when anonymous)."""

    def dependency(request: Request, user: Annotated[User, Depends(current_user)]) -> None:
        _hit(request, name, limit, window_s, str(user.id))

    return dependency
