"""Pure ASGI middleware: request IDs and access log, body size limit, security headers."""

from __future__ import annotations

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from http import HTTPStatus
from typing import Any

from app.config import Settings
from app.errors import PROBLEM_MEDIA_TYPE, problem_body_bytes
from app.logging import request_id_var

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]
ASGIApp = Callable[[Scope, Receive, Send], Awaitable[None]]

access_logger = logging.getLogger("brewnotes.access")

_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def _header(scope: Scope, name: bytes) -> bytes | None:
    for key, value in scope.get("headers", []):
        if key == name:
            return bytes(value)
    return None


class RequestIDMiddleware:
    """Accepts a well-formed X-Request-ID or generates one, echoes it on the response, binds it
    to the logging context and writes one access-log line per request (path only, no query
    string, no client address)."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = _header(scope, b"x-request-id")
        request_id = (
            incoming.decode("latin-1")
            if incoming and _REQUEST_ID_RE.match(incoming.decode("latin-1"))
            else str(uuid.uuid4())
        )
        scope.setdefault("state", {})["request_id"] = request_id
        token = request_id_var.set(request_id)
        started = time.perf_counter()
        status_code = 500

        async def send_with_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                headers = list(message.get("headers", []))
                headers.append((b"x-request-id", request_id.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_id)
        finally:
            access_logger.info(
                "request",
                extra={
                    "data": {
                        "method": scope.get("method"),
                        "path": scope.get("path"),
                        "status": status_code,
                        "duration_ms": round((time.perf_counter() - started) * 1000, 1),
                    }
                },
            )
            request_id_var.reset(token)


class BodySizeLimitMiddleware:
    """Rejects request bodies over the limit with 413 before the application parses them.
    A declared Content-Length is checked up front; chunked bodies are counted as they stream."""

    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = _header(scope, b"content-length")
        if declared is not None:
            try:
                if int(declared) > self.max_bytes:
                    await self._reject(send)
                    return
            except ValueError:
                pass

        received = 0
        rejected = False
        response_started = False

        async def counting_receive() -> Message:
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes and not rejected:
                    rejected = True
                    if not response_started:
                        await self._reject(send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            nonlocal response_started
            if rejected:
                return
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        await self.app(scope, counting_receive, guarded_send)

    async def _reject(self, send: Send) -> None:
        body = problem_body_bytes(
            HTTPStatus.CONTENT_TOO_LARGE,
            detail=f"Request body may not exceed {self.max_bytes} bytes.",
        )
        await send(
            {
                "type": "http.response.start",
                "status": HTTPStatus.CONTENT_TOO_LARGE,
                "headers": [
                    (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


def build_content_security_policy(settings: Settings) -> str:
    image_hosts = [
        "'self'",
        "data:",
        "https://avatars.githubusercontent.com",
        "https://lh3.googleusercontent.com",
    ]
    connect = ["'self'"]
    if settings.sentry_dsn:
        connect.append("https://*.sentry.io")
    directives = [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self'",
        f"img-src {' '.join(image_hosts)}",
        f"connect-src {' '.join(connect)}",
        "font-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
    return "; ".join(directives)


_DOCS_PATHS = frozenset({"/api/v1/docs", "/api/v1/openapi.json"})


def security_headers(
    settings: Settings, path: str, status: int, existing: set[bytes]
) -> list[tuple[bytes, bytes]]:
    """Headers to add to a response, skipping any the application already set."""
    headers: list[tuple[bytes, bytes]] = [
        (b"x-content-type-options", b"nosniff"),
        (b"referrer-policy", b"strict-origin-when-cross-origin"),
        (b"permissions-policy", b"geolocation=(self)"),
    ]
    # Swagger UI loads its assets from a CDN, so the docs page (development only) is the one
    # place without a CSP.
    if not (settings.is_development and path in _DOCS_PATHS):
        headers.append(
            (b"content-security-policy", build_content_security_policy(settings).encode())
        )
    if settings.is_production:
        # Short max-age to start; raise it once HTTPS is known to be stable.
        headers.append((b"strict-transport-security", b"max-age=86400"))
    if path.startswith("/assets/") and status == HTTPStatus.OK:
        headers.append((b"cache-control", b"public, max-age=31536000, immutable"))
    return [(k, v) for k, v in headers if k not in existing]


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                existing = {bytes(key) for key, _ in headers}
                headers.extend(security_headers(self.settings, path, message["status"], existing))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_with_headers)


HEALTH_PATH_PREFIX = "/api/v1/health/"


def _host_matches(host: str, allowed: list[str]) -> bool:
    if host.startswith("["):  # IPv6 literal, e.g. [::1]:8000
        host = host[: host.index("]") + 1] if "]" in host else host
    else:
        host = host.split(":", 1)[0]
    host = host.lower()
    for pattern in allowed:
        pattern = pattern.lower()
        if pattern == "*" or host == pattern:
            return True
        if pattern.startswith("*.") and host.endswith(pattern[1:]):
            return True
    return False


class TrustedHostMiddleware:
    """Rejects requests whose Host header is not one of ours with a problem-details 400, so a
    misrouted request can never reach the application. The health endpoints accept any Host
    so the container runtime and the platform can probe them by IP address."""

    def __init__(self, app: ASGIApp, allowed_hosts: list[str]) -> None:
        self.app = app
        self.allowed_hosts = list(allowed_hosts)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        host = (_header(scope, b"host") or b"").decode("latin-1")
        if path.startswith(HEALTH_PATH_PREFIX) or _host_matches(host, self.allowed_hosts):
            await self.app(scope, receive, send)
            return
        body = problem_body_bytes(HTTPStatus.BAD_REQUEST, detail="Invalid host header.")
        await send(
            {
                "type": "http.response.start",
                "status": HTTPStatus.BAD_REQUEST,
                "headers": [
                    (b"content-type", PROBLEM_MEDIA_TYPE.encode()),
                    (b"content-length", str(len(body)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
