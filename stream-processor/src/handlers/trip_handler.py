"""Trip event handler with pass-through logic."""

import json
import logging

from pydantic import ValidationError

from ..events.schemas import TripEvent
from ..metrics import get_metrics_collector
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class TripHandler(BaseHandler):
    """Handler for trip events.

    Pass-through handler that immediately emits trip events to Redis.
    Trip state changes are critical and should not be aggregated.
    """

    def __init__(self):
        """Initialize trip handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a trip event message."""
        try:
            raw = json.loads(message)
            validated = TripEvent.model_validate(raw)
            event = validated.model_dump(mode="json")
        except ValidationError as e:
            logger.warning(f"Trip validation error: {e}")
            get_metrics_collector().record_validation_error("trip")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse trip event: {e}")
            get_metrics_collector().record_validation_error("trip")
            return []

        self.messages_processed += 1
        return [("trip-updates", event)]

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for trip events."""
        return []
