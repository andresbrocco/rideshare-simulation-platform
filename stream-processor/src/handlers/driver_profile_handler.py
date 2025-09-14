"""Driver profile event handler with pass-through logic."""

import json
import logging

from pydantic import ValidationError

from ..events.schemas import DriverProfileEvent
from ..metrics import get_metrics_collector
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class DriverProfileHandler(BaseHandler):
    """Handler for driver profile events.

    Pass-through handler that immediately emits driver creation/update events
    to Redis. These are important for real-time visualization of new drivers.
    """

    def __init__(self):
        """Initialize driver profile handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a driver profile event message."""
        try:
            raw = json.loads(message)
            validated = DriverProfileEvent.model_validate(raw)
            event = validated.model_dump(mode="json")
        except ValidationError as e:
            logger.warning(f"Driver profile validation error: {e}")
            get_metrics_collector().record_validation_error("driver_profile")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse driver profile event: {e}")
            get_metrics_collector().record_validation_error("driver_profile")
            return []

        self.messages_processed += 1
        return [("driver-updates", event)]

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for driver profile events."""
        return []
