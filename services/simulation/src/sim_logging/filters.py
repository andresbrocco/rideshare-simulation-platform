"""Log filters for PII masking and correlation ID injection."""

import logging
import re


class PIIFilter(logging.Filter):
    """Masks PII (emails, phone numbers) in log messages."""

    EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
    PHONE_PATTERN = re.compile(r"\d{3}[-.\s]?\d{3}[-.\s]?\d{4}")

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            msg = record.msg
            if "@" in msg:
                msg = self.EMAIL_PATTERN.sub("[EMAIL]", msg)
            if any(c.isdigit() for c in msg):
                msg = self.PHONE_PATTERN.sub("[PHONE]", msg)
            record.msg = msg
        return True


class DefaultCorrelationFilter(logging.Filter):
    """Adds default correlation_id if not present.

    Note: For full correlation support, use src.core.correlation.CorrelationFilter
    which integrates with the distributed tracing context.
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "correlation_id"):
            record.correlation_id = "-"
        return True
