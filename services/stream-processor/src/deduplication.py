"""Event deduplication using Redis."""

import logging
from datetime import timedelta

import redis

logger = logging.getLogger(__name__)


class EventDeduplicator:
    """Redis-based event deduplication using event_id.

    Uses Redis SET NX with TTL to track processed event IDs.
    Events seen within the TTL window are considered duplicates.
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        ttl: timedelta = timedelta(hours=1),
        key_prefix: str = "event:processed:",
    ):
        self._redis = redis_client
        self._ttl_seconds = int(ttl.total_seconds())
        self._key_prefix = key_prefix
        self._duplicates_skipped = 0
        self._events_processed = 0

    def is_duplicate(self, event_id: str) -> bool:
        """Check if event was already processed.

        Returns True if duplicate (already seen), False if new event.
        Uses atomic SET NX to both check and mark in one operation.
        """
        if not event_id:
            return False

        key = f"{self._key_prefix}{event_id}"
        was_set = self._redis.set(key, "1", nx=True, ex=self._ttl_seconds)

        if was_set:
            self._events_processed += 1
            return False
        else:
            self._duplicates_skipped += 1
            logger.debug(f"Skipping duplicate event: {event_id}")
            return True

    @property
    def duplicates_skipped(self) -> int:
        return self._duplicates_skipped

    @property
    def events_processed(self) -> int:
        return self._events_processed

    def get_stats(self) -> dict:
        return {
            "events_processed": self._events_processed,
            "duplicates_skipped": self._duplicates_skipped,
        }
