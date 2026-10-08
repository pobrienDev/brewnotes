"""RFC 9457 problem details for every error response, including validation errors."""

from __future__ import annotations

import logging
from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain.brewmath import RecipeOutOfRangeError
from app.logging import request_id_var

PROBLEM_MEDIA_TYPE = "application/problem+json"

logger = logging.getLogger(__name__)


class FieldError(BaseModel):
    loc: list[str | int] = Field(description="Path to the offending field")
    msg: str
    type: str


class Problem(BaseModel):
    """Problem details object (RFC 9457) with a request_id extension member."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    instance: str | None = None
    errors: list[FieldError] | None = None
    request_id: str | None = None


class ValidationProblemError(Exception):
    """Raised by services for input that passed the schema but fails a deeper check, e.g. a
    reference to a catalog item the caller may not use. Becomes a 422 problem."""

    def __init__(
        self, errors: list[FieldError], detail: str = "One or more fields are invalid."
    ) -> None:
        super().__init__(detail)
        self.errors = errors
        self.detail = detail


def problem_response(
    status: int,
    *,
    title: str | None = None,
    detail: str | None = None,
    instance: str | None = None,
    errors: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
    request_id: str | None = None,
) -> JSONResponse:
    problem = Problem(
        title=title or HTTPStatus(status).phrase,
        status=status,
        detail=detail,
        instance=instance,
        errors=errors,
        request_id=request_id or request_id_var.get(),
    )
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
        headers=headers,
    )


def problem_body_bytes(status: int, detail: str | None = None) -> bytes:
    """Serialised problem for middleware that answers before the application runs."""
    return bytes(problem_response(status, detail=detail).body)


def _validation_errors(exc: RequestValidationError) -> list[FieldError]:
    # Deliberately drops `input` and `ctx`, so submitted values never appear in responses or logs.
    return [
        FieldError(
            loc=[part for part in err.get("loc", ()) if isinstance(part, str | int)],
            msg=str(err.get("msg", "Invalid value")),
            type=str(err.get("type", "value_error")),
        )
        for err in exc.errors()
    ]


def _request_id(request: Request) -> str | None:
    value = request.scope.get("state", {}).get("request_id")
    return value if isinstance(value, str) else request_id_var.get()


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else None
        return problem_response(
            exc.status_code,
            detail=detail,
            instance=request.url.path,
            headers=dict(exc.headers) if exc.headers else None,
            request_id=_request_id(request),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_exception(request: Request, exc: RequestValidationError) -> JSONResponse:
        return problem_response(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            title="Validation failed",
            detail="One or more fields are invalid.",
            instance=request.url.path,
            errors=_validation_errors(exc),
            request_id=_request_id(request),
        )

    @app.exception_handler(ValidationProblemError)
    async def _validation_problem(request: Request, exc: ValidationProblemError) -> JSONResponse:
        return problem_response(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            title="Validation failed",
            detail=exc.detail,
            instance=request.url.path,
            errors=exc.errors,
            request_id=_request_id(request),
        )

    @app.exception_handler(RecipeOutOfRangeError)
    async def _recipe_out_of_range(request: Request, exc: RecipeOutOfRangeError) -> JSONResponse:
        return problem_response(
            HTTPStatus.UNPROCESSABLE_CONTENT,
            title="Validation failed",
            detail=exc.message,
            instance=request.url.path,
            errors=[FieldError(loc=["body", exc.field], msg=exc.message, type="value_error")],
            request_id=_request_id(request),
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
        # This handler runs in Starlette's outermost error middleware, outside our own
        # middleware, so the request ID and security headers are attached here by hand.
        from app.middleware import security_headers

        request_id = _request_id(request)
        logger.exception("unhandled error", extra={"data": {"path": request.url.path}})
        headers = {
            k.decode(): v.decode()
            for k, v in security_headers(
                request.app.state.settings,
                request.url.path,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                set(),
            )
        }
        if request_id:
            headers["x-request-id"] = request_id
        return problem_response(
            HTTPStatus.INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred.",
            instance=request.url.path,
            headers=headers,
            request_id=request_id,
        )


def problem_responses() -> dict[int | str, dict[str, Any]]:
    """Default responses added to every operation so problem details appear in the spec."""
    return {
        "4XX": {"model": Problem, "description": "Client error (problem details)"},
        "5XX": {"model": Problem, "description": "Server error (problem details)"},
    }


def use_problem_media_type(schema: dict[str, Any]) -> dict[str, Any]:
    """Rewrite the media type of every Problem response in an OpenAPI document."""
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            for response in operation.get("responses", {}).values():
                content = response.get("content", {})
                body = content.get("application/json")
                if body and body.get("schema", {}).get("$ref", "").endswith("/Problem"):
                    content[PROBLEM_MEDIA_TYPE] = content.pop("application/json")
    return schema
