"""OpenTelemetry configuration for distributed tracing.

This module provides optional OpenTelemetry instrumentation for
the FastAPI application. Tracing is only enabled if OTEL_EXPORTER_OTLP_ENDPOINT
is set.

Usage:
    Set environment variables to enable tracing:
    - OTEL_EXPORTER_OTLP_ENDPOINT: OTLP endpoint (e.g., http://localhost:4317)
    - OTEL_SERVICE_NAME: Service name (default: dev-blog-backend)
    - DEV_BLOG_OTEL_ENABLED: Set to "true" to enable (default: false)

Example:
    OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4317 \
    OTEL_SERVICE_NAME=dev-blog-backend \
    DEV_BLOG_OTEL_ENABLED=true \
    uvicorn app.main:app
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import TYPE_CHECKING, Generator

from .config import logger

if TYPE_CHECKING:
    from opentelemetry.trace import Span, Tracer

# Check if tracing should be enabled
OTEL_ENABLED = os.getenv("DEV_BLOG_OTEL_ENABLED", "false").lower() == "true"
OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "")

# Global tracer instance
_tracer: "Tracer | None" = None


def init_telemetry(app_name: str = "dev-blog-backend") -> bool:
    """Initialize OpenTelemetry tracing.

    Args:
        app_name: Service name for traces.

    Returns:
        True if tracing was initialized, False otherwise.
    """
    global _tracer

    if not OTEL_ENABLED or not OTEL_ENDPOINT:
        logger.info("OpenTelemetry tracing disabled (set DEV_BLOG_OTEL_ENABLED=true to enable)")
        return False

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        # Create resource with service info
        resource = Resource.create(
            {
                "service.name": app_name,
                "service.version": "0.1.0",
                "deployment.environment": os.getenv("DEV_BLOG_ENVIRONMENT", "local"),
            }
        )

        # Set up tracer provider
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

        # Set up OTLP exporter
        exporter = OTLPSpanExporter(endpoint=OTEL_ENDPOINT, insecure=True)
        provider.add_span_processor(BatchSpanProcessor(exporter))

        # Get tracer
        _tracer = trace.get_tracer(__name__)

        logger.info("OpenTelemetry tracing initialized (endpoint: %s)", OTEL_ENDPOINT)
        return True

    except ImportError:
        logger.warning(
            "OpenTelemetry packages not installed. Install with: "
            "pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-fastapi opentelemetry-exporter-otlp"
        )
        return False
    except Exception as e:
        logger.error("Failed to initialize OpenTelemetry: %s", str(e))
        return False


def instrument_fastapi(app: object) -> None:
    """Instrument FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance.
    """
    if not OTEL_ENABLED or not OTEL_ENDPOINT:
        return

    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except ImportError:
        pass
    except Exception as e:
        logger.error("Failed to instrument FastAPI: %s", str(e))


def get_tracer() -> "Tracer | None":
    """Get the global tracer instance.

    Returns:
        Tracer instance or None if tracing is disabled.
    """
    return _tracer


@contextmanager
def trace_span(name: str, **attributes: object) -> Generator["Span | None", None, None]:
    """Create a trace span context manager.

    Usage:
        with trace_span("fetch_post", slug=slug):
            post = load_post_by_slug(slug)

    Args:
        name: Span name.
        **attributes: Span attributes.

    Yields:
        Span instance or None if tracing is disabled.
    """
    if _tracer is None:
        yield None
        return

    with _tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            span.set_attribute(key, str(value))
        yield span
