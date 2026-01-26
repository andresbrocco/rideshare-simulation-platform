"""Rating event handler with pass-through logic."""

import json
import logging

from pydantic import ValidationError

from ..events.schemas import RatingEvent
from ..metrics import get_metrics_collector
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class RatingHandler(BaseHandler):
    """Handler for rating events.

    Pass-through handler that routes rating events to the appropriate
    Redis channel (driver-updates or rider-updates) based on ratee_type.
    Adds event_type marker for frontend identification.
    """

    def __init__(self):
        """Initialize rating handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a rating event message.

        Routes to driver-updates or rider-updates based on ratee_type.
        """
        try:
            raw = json.loads(message)
            validated = RatingEvent.model_validate(raw)
            event = validated.model_dump(mode="json")
        except ValidationError as e:
            logger.warning(f"Rating validation error: {e}")
            get_metrics_collector().record_validation_error("rating")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse rating event: {e}")
            get_metrics_collector().record_validation_error("rating")
            return []

        self.messages_processed += 1

        # Add event_type for frontend identification
        event["event_type"] = "rating_update"

        # Route to appropriate channel based on ratee_type
        if validated.ratee_type == "driver":
            channel = "driver-updates"
        else:
            channel = "rider-updates"

        return [(channel, event)]

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for rating events."""
        return []
