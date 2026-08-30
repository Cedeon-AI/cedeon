"""Request middleware: correlation id propagation."""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import set_correlation_id

_HEADER_CANDIDATES = ("x-request-id", "x-correlation-id")
CORRELATION_HEADER = "X-Correlation-ID"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = next(
            (request.headers[h] for h in _HEADER_CANDIDATES if h in request.headers),
            None,
        )
        correlation_id = incoming or uuid.uuid4().hex
        set_correlation_id(correlation_id)
        request.state.correlation_id = correlation_id
        try:
            response = await call_next(request)
        finally:
            set_correlation_id(None)
        response.headers[CORRELATION_HEADER] = correlation_id
        return response
