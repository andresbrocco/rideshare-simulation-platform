"""Driver status event handler with pass-through logic."""

import json
import logging

from pydantic import ValidationError

from ..events.schemas import DriverStatusEvent
from ..metrics import get_metrics_collector
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class DriverStatusHandler(BaseHandler):
    """Handler for driver status events.

    Pass-through handler that immediately emits driver status changes
    to Redis. Status changes are important and should not be aggregated.
    """

    def __init__(self):
        """Initialize driver status handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a driver status event message."""
        try:
            raw = json.loads(message)
            validated = DriverStatusEvent.model_validate(raw)
            event = validated.model_dump(mode="json")
        except ValidationError as e:
            logger.warning(f"Driver status validation error: {e}")
            get_metrics_collector().record_validation_error("driver_status")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse driver status event: {e}")
            get_metrics_collector().record_validation_error("driver_status")
            return []

        self.messages_processed += 1
        return [("driver-updates", event)]

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for driver status events."""
        return []
