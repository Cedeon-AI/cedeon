"""Structured logging via structlog, with a request/job correlation id.

Never log treaty text, claim data, or PII here (see docs/SECURITY.md §6). Log
identifiers, counts, and status only.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

import structlog
from structlog.typing import EventDict, WrappedLogger

correlation_id_var: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str | None) -> None:
    correlation_id_var.set(value)


def get_correlation_id() -> str | None:
    return correlation_id_var.get()


def _add_correlation_id(_logger: WrappedLogger, _method: str, event_dict: EventDict) -> EventDict:
    cid = correlation_id_var.get()
    if cid is not None:
        event_dict.setdefault("correlation_id", cid)
    return event_dict


def configure_logging(*, level: str = "INFO", json_output: bool = False) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _add_correlation_id,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    renderer: structlog.typing.Processor = (
        structlog.processors.JSONRenderer()
        if json_output
        else structlog.dev.ConsoleRenderer(colors=True)
    )

    structlog.configure(
        processors=[*shared, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy) through a plain handler at the same level.
    logging.basicConfig(
        format="%(message)s",
        level=logging.getLevelNamesMapping().get(level.upper(), logging.INFO),
        force=True,
    )
    for noisy in ("uvicorn.access",):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
