"""Error handling and DLQ routing utilities for streaming jobs."""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List


@dataclass
class DLQRecord:
    """A record destined for the Dead Letter Queue."""

    should_route_to_dlq: bool
    error_type: str
    raw_message: bytes
    kafka_topic: str
    kafka_partition: int
    kafka_offset: int
    error_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_details: str = ""


class ErrorHandler:
    """Handles errors and routes malformed messages to DLQ."""

    def __init__(self, dlq_table_path: str):
        self.dlq_table_path = dlq_table_path
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def handle_parse_error(
        self,
        raw_message: bytes,
        topic: str,
        partition: int,
        offset: int,
    ) -> DLQRecord:
        """Handle JSON parse errors and create DLQ record."""
        self.logger.error(f"Parse error for message at {topic}:{partition}:{offset}")
        return DLQRecord(
            should_route_to_dlq=True,
            error_type="json_parse_error",
            raw_message=raw_message,
            kafka_topic=topic,
            kafka_partition=partition,
            kafka_offset=offset,
        )

    def handle_schema_error(
        self,
        parsed_message: str,
        topic: str,
        partition: int,
        offset: int,
        validation_errors: List[str],
    ) -> DLQRecord:
        """Handle schema validation errors and create DLQ record."""
        error_details = "; ".join(validation_errors)
        self.logger.error(
            f"Schema validation error for message at {topic}:{partition}:{offset}: {error_details}"
        )
        return DLQRecord(
            should_route_to_dlq=True,
            error_type="schema_validation_error",
            raw_message=(
                parsed_message.encode("utf-8")
                if isinstance(parsed_message, str)
                else parsed_message
            ),
            kafka_topic=topic,
            kafka_partition=partition,
            kafka_offset=offset,
            error_details=error_details,
        )
