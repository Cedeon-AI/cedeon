"""OpenTelemetry tracing setup.

Tracing is wired from Phase 1 (cheap early, painful to retrofit). By default a
no-op/console provider is used; an OTLP exporter is attached only when
``CEDEON_OTEL_ENABLED`` is true and an endpoint is configured. Optional
instrumentation packages live in the ``otel`` extra and are imported defensively.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from app.core.config import Settings
from app.core.logging import get_logger

if TYPE_CHECKING:
    from fastapi import FastAPI

log = get_logger(__name__)
_configured = False


def configure_telemetry(settings: Settings) -> None:
    global _configured
    if _configured:
        return

    resource = Resource.create(
        {
            "service.name": settings.service_name,
            "deployment.environment": settings.env,
        }
    )
    provider = TracerProvider(resource=resource)

    if settings.otel_enabled and settings.otel_exporter_otlp_endpoint:
        try:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=settings.otel_exporter_otlp_endpoint))
            )
            log.info("telemetry.otlp_enabled", endpoint=settings.otel_exporter_otlp_endpoint)
        except ImportError:
            log.warning("telemetry.otlp_unavailable", hint="install the 'otel' extra")
    elif settings.env == "local":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    trace.set_tracer_provider(provider)
    _configured = True


def instrument_fastapi(app: FastAPI) -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except ImportError:
        log.debug("telemetry.fastapi_instrumentation_unavailable")


def get_tracer(name: str = "cedeon") -> trace.Tracer:
    return trace.get_tracer(name)
