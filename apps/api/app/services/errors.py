"""Service-layer errors. The API layer maps these to RFC 9457 problem responses."""

from __future__ import annotations

from typing import Any


class ServiceError(Exception):
    """Base class. ``code`` is a stable slug; ``status`` is the HTTP status."""

    code: str = "service_error"
    status: int = 400

    def __init__(self, message: str, *, detail: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.detail = detail or {}


class NotFoundError(ServiceError):
    code = "not_found"
    status = 404


class ConflictError(ServiceError):
    code = "conflict"
    status = 409


class ValidationError(ServiceError):
    code = "validation_error"
    status = 422


class AuthenticationError(ServiceError):
    code = "authentication_failed"
    status = 401


class PermissionDeniedError(ServiceError):
    code = "permission_denied"
    status = 403


class UsageLimitError(ServiceError):
    """The organization has hit a usage/spend limit (ADR-0028). 402 Payment Required."""

    code = "usage_limit_reached"
    status = 402
