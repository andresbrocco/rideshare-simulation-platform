"""Surge pricing event handler with pass-through logic."""

import json
import logging

from pydantic import ValidationError

from ..events.schemas import SurgeUpdateEvent
from ..metrics import get_metrics_collector
from .base_handler import BaseHandler

logger = logging.getLogger(__name__)


class SurgeHandler(BaseHandler):
    """Handler for surge pricing events.

    Pass-through handler that immediately emits surge pricing updates
    to Redis. Pricing changes are critical and should not be aggregated.
    """

    def __init__(self):
        """Initialize surge handler."""
        self.messages_processed = 0

    def handle(self, message: bytes) -> list[tuple[str, dict]]:
        """Process a surge pricing event message."""
        try:
            raw = json.loads(message)
            validated = SurgeUpdateEvent.model_validate(raw)
            event = validated.model_dump(mode="json")
        except ValidationError as e:
            logger.warning(f"Surge validation error: {e}")
            get_metrics_collector().record_validation_error("surge")
            return []
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse surge event: {e}")
            get_metrics_collector().record_validation_error("surge")
            return []

        self.messages_processed += 1
        return [("surge-updates", event)]

    def flush(self) -> list[tuple[str, dict]]:
        """No buffering for surge events."""
        return []
