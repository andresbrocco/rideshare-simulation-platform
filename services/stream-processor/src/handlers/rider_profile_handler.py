"""Rider profile event handler with pass-through logic."""

import json
import logging

from pydantic import ValidationError

from ..events.schemas import RiderProfileEvent
from ..metrics import get_metrics_collector
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class RiderProfileHandler(BaseHandler):
    """Handler for rider profile events.

    Pass-through handler that immediately emits rider creation/update events
    to Redis. These are important for real-time visualization of new riders.
    """

    def __init__(self):
        """Initialize rider profile handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a rider profile event message."""
        try:
            raw = json.loads(message)
            validated = RiderProfileEvent.model_validate(raw)
            event = validated.model_dump(mode="json")
        except ValidationError as e:
            logger.warning(f"Rider profile validation error: {e}")
            get_metrics_collector().record_validation_error("rider_profile")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse rider profile event: {e}")
            get_metrics_collector().record_validation_error("rider_profile")
            return []

        self.messages_processed += 1
        return [("rider-updates", event)]

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for rider profile events."""
        return []
