"""Performance controller entry point."""

import logging
import os
import signal
import sys

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from .api import set_controller, start_api_server_thread
from .controller import PerformanceController
from .logging_setup import setup_logging
from .settings import get_settings

logger = logging.getLogger(__name__)


def init_otel_sdk() -> None:
    """Initialize OpenTelemetry SDK for metrics and traces."""
    resource = Resource.create(
        {
            "service.name": "performance-controller",
            "service.version": "0.1.0",
            "deployment.environment": os.getenv("DEPLOYMENT_ENV", "local"),
        }
    )

    # Tracing
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")
    trace_provider = TracerProvider(resource=resource)
    trace_provider.add_span_processor(
        BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True))
    )
    trace.set_tracer_provider(trace_provider)
    logger.info("OpenTelemetry tracing initialized (endpoint=%s)", otlp_endpoint)

    # Metrics
    metric_reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=otlp_endpoint, insecure=True),
        export_interval_millis=4_000,
    )
    meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
    metrics.set_meter_provider(meter_provider)
    logger.info("OpenTelemetry metrics initialized")


def main() -> None:
    """Main entry point for the performance controller."""
    settings = get_settings()

    setup_logging(
        level=settings.log_level,
        json_output=os.environ.get("LOG_FORMAT") == "json",
        environment=os.environ.get("ENVIRONMENT", "development"),
    )

    # Initialize OTel SDK before starting app
    init_otel_sdk()

    logger.info("Starting performance controller...")
    logger.info("Prometheus: %s", settings.prometheus.url)
    logger.info("Simulation API: %s", settings.simulation.base_url)
    logger.info("Target speed: %d", settings.controller.target_speed)
    logger.info("Poll interval: %.1fs", settings.controller.poll_interval_seconds)

    # Start HTTP API server in background thread
    start_api_server_thread(settings.api.host, settings.api.port)

    # Create controller and wire into API
    controller = PerformanceController(settings)
    set_controller(controller)

    # Handle shutdown signals
    def shutdown_handler(signum: int, frame: object) -> None:
        sig_name = signal.Signals(signum).name
        logger.info("Received %s, initiating graceful shutdown...", sig_name)
        controller.stop()

    signal.signal(signal.SIGTERM, shutdown_handler)
    signal.signal(signal.SIGINT, shutdown_handler)

    # Run the control loop (blocks until stopped)
    try:
        controller.run()
    except Exception as e:
        logger.exception("Fatal error in performance controller: %s", e)
        sys.exit(1)

    logger.info("Performance controller exited")


if __name__ == "__main__":
    main()
