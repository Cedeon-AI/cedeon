"""RFC 9457 (problem+json) error responses."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_correlation_id, get_logger
from app.services.errors import ServiceError

log = get_logger(__name__)

PROBLEM_TYPE_BASE = "https://cedeon.dev/problems/"
PROBLEM_MEDIA_TYPE = "application/problem+json"

_STATUS_TITLES = {
    400: "Bad Request",
    401: "Unauthorized",
    403: "Forbidden",
    404: "Not Found",
    409: "Conflict",
    422: "Unprocessable Entity",
    500: "Internal Server Error",
}


def problem_response(
    *,
    status: int,
    code: str,
    detail: str,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"{PROBLEM_TYPE_BASE}{code}",
        "title": _STATUS_TITLES.get(status, "Error"),
        "status": status,
        "detail": detail,
    }
    correlation_id = get_correlation_id()
    if correlation_id:
        body["correlation_id"] = correlation_id
    if extra:
        body.update(extra)
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_MEDIA_TYPE)


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ServiceError)
    async def _service_error(_request: Request, exc: ServiceError) -> JSONResponse:
        return problem_response(
            status=exc.status,
            code=exc.code,
            detail=exc.message,
            extra=exc.detail or None,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Report location/message/type only — never echo submitted input (may be a password).
        errors = [
            {"loc": list(err.get("loc", [])), "msg": err.get("msg"), "type": err.get("type")}
            for err in exc.errors()
        ]
        return problem_response(
            status=422,
            code="validation_error",
            detail="the request body failed validation",
            extra={"errors": errors},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return problem_response(
            status=exc.status_code,
            code=_STATUS_TITLES.get(exc.status_code, "error").lower().replace(" ", "_"),
            detail=str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def _unhandled(_request: Request, exc: Exception) -> JSONResponse:
        log.exception("request.unhandled_error", error_type=type(exc).__name__)
        return problem_response(
            status=500,
            code="internal_error",
            detail="an unexpected error occurred",
        )
