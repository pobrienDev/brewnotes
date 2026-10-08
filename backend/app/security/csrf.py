"""CSRF: every unsafe request must come from our own origin.

Together with SameSite=Lax cookies this blocks cross-site form posts and fetches. The Origin
header is sent by every current browser on POST, PUT, PATCH and DELETE.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, MutableMapping
from http import HTTPStatus
from typing import Any

from app.errors import PROBLEM_MEDIA_TYPE, problem_body_bytes

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginCheckMiddleware:
    def __init__(
        self, app: ASGIApp, allowed_origin: str, exempt_paths: tuple[str, ...] = ()
    ) -> None:
        self.app = app
        self.allowed_origin = allowed_origin.rstrip("/").lower()
        self.exempt_paths = exempt_paths

    def _origin_ok(self, scope: Scope) -> bool:
        origin: bytes | None = None
        for key, value in scope.get("headers", []):
            if key == b"origin":
                origin = bytes(value)
                break
        if origin is None:
            return False
        return origin.decode("latin-1").rstrip("/").lower() == self.allowed_origin

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("method", "GET") not in UNSAFE_METHODS:
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        if path.startswith(self.exempt_paths) if self.exempt_paths else False:
            await self.app(scope, receive, send)
            return
        if self._origin_ok(scope):
            await self.app(scope, receive, send)
            return
        body = problem_body_bytes(
            HTTPStatus.FORBIDDEN, detail="Cross-site request blocked: Origin does not match."
        )
        await send(
            {
                "type": "http.response.start",
                "status": HTTPStatus.FORBIDDEN,
                "headers": [
                    (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
