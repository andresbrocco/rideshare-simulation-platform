"""Test configuration — mock heavy dependencies not available outside Docker."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

# Stub out opentelemetry before any src.* imports so metrics_exporter can load.
_otel_mock = MagicMock()
sys.modules.setdefault("opentelemetry", _otel_mock)
sys.modules.setdefault("opentelemetry.metrics", _otel_mock.metrics)
sys.modules.setdefault("opentelemetry.instrumentation", _otel_mock.instrumentation)
sys.modules.setdefault("opentelemetry.instrumentation.fastapi", _otel_mock.instrumentation.fastapi)
sys.modules.setdefault("opentelemetry.sdk", _otel_mock.sdk)
sys.modules.setdefault("opentelemetry.exporter", _otel_mock.exporter)
sys.modules.setdefault("opentelemetry.exporter.otlp", _otel_mock.exporter.otlp)
