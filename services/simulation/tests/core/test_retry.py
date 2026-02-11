"""Tests for retry utilities."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import (
    NetworkError,
    PermanentError,
    TransientError,
    ValidationError,
)
from src.core.retry import RetryConfig, with_retry, with_retry_sync


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestRetryConfig:
    """Test RetryConfig defaults and customization."""

    def test_default_config(self):
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.base_delay == 0.5
        assert config.multiplier == 2.0
        assert config.max_delay == 30.0
        assert config.retryable_exceptions == (TransientError,)

    def test_custom_config(self):
        config = RetryConfig(
            max_attempts=5,
            base_delay=0.1,
            multiplier=3.0,
            max_delay=10.0,
            retryable_exceptions=(NetworkError, ValueError),
        )
        assert config.max_attempts == 5
        assert config.base_delay == 0.1
        assert config.multiplier == 3.0
        assert config.max_delay == 10.0
        assert config.retryable_exceptions == (NetworkError, ValueError)


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestWithRetryAsync:
    """Test async retry functionality."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self):
        """Operation succeeds immediately without retry."""
        operation = AsyncMock(return_value="success")

        result = await with_retry(operation)

        assert result == "success"
        assert operation.call_count == 1

    @pytest.mark.asyncio
    async def test_succeeds_after_transient_failures(self):
        """Operation succeeds after transient failures."""
        call_count = 0

        async def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("connection failed")
            return "success"

        config = RetryConfig(base_delay=0.01)
        result = await with_retry(flaky_operation, config)

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_fails_after_max_attempts(self):
        """Raises exception after max attempts exhausted."""

        async def always_fails():
            raise NetworkError("always fails")

        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(NetworkError, match="always fails"):
            await with_retry(always_fails, config)

    @pytest.mark.asyncio
    async def test_permanent_error_not_retried(self):
        """Permanent errors are raised immediately without retry."""
        call_count = 0

        async def fails_with_permanent():
            nonlocal call_count
            call_count += 1
            raise ValidationError("invalid input")

        config = RetryConfig(base_delay=0.01)

        with pytest.raises(ValidationError):
            await with_retry(fails_with_permanent, config)

        assert call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff_delays(self):
        """Verify exponential backoff timing."""
        delays = []

        async def always_fails():
            raise NetworkError("fail")

        async def mock_sleep(delay):
            delays.append(delay)

        config = RetryConfig(max_attempts=4, base_delay=1.0, multiplier=2.0)

        with (
            patch("src.core.retry.asyncio.sleep", side_effect=mock_sleep),
            pytest.raises(NetworkError),
        ):
            await with_retry(always_fails, config)

        # Expected delays: 1.0, 2.0, 4.0 (3 retries after 4 attempts)
        assert len(delays) == 3
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Delay should not exceed max_delay."""
        delays = []

        async def always_fails():
            raise NetworkError("fail")

        async def mock_sleep(delay):
            delays.append(delay)

        config = RetryConfig(
            max_attempts=5,
            base_delay=10.0,
            multiplier=3.0,
            max_delay=20.0,
        )

        with (
            patch("src.core.retry.asyncio.sleep", side_effect=mock_sleep),
            pytest.raises(NetworkError),
        ):
            await with_retry(always_fails, config)

        # All delays should be capped at max_delay
        assert all(d <= 20.0 for d in delays)

    @pytest.mark.asyncio
    async def test_on_retry_callback_called(self):
        """on_retry callback is called on each retry."""
        retries = []

        async def fails_twice():
            if len(retries) < 2:
                raise NetworkError("fail")
            return "success"

        def on_retry(exc, attempt):
            retries.append((type(exc).__name__, attempt))

        config = RetryConfig(base_delay=0.01)
        await with_retry(fails_twice, config, on_retry=on_retry)

        assert len(retries) == 2
        assert retries[0] == ("NetworkError", 0)
        assert retries[1] == ("NetworkError", 1)

    @pytest.mark.asyncio
    async def test_custom_retryable_exceptions(self):
        """Custom retryable exceptions are retried."""
        call_count = 0

        async def fails_with_value_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ValueError("custom error")
            return "success"

        config = RetryConfig(
            base_delay=0.01,
            retryable_exceptions=(ValueError,),
        )
        result = await with_retry(fails_with_value_error, config)

        assert result == "success"
        assert call_count == 2


@pytest.mark.unit
@pytest.mark.critical
@pytest.mark.unit
@pytest.mark.critical
class TestWithRetrySync:
    """Test synchronous retry functionality."""

    def test_succeeds_on_first_attempt(self):
        """Operation succeeds immediately without retry."""
        operation = MagicMock(return_value="success")

        result = with_retry_sync(operation)

        assert result == "success"
        assert operation.call_count == 1

    def test_succeeds_after_transient_failures(self):
        """Operation succeeds after transient failures."""
        call_count = 0

        def flaky_operation():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise NetworkError("connection failed")
            return "success"

        config = RetryConfig(base_delay=0.01)
        result = with_retry_sync(flaky_operation, config)

        assert result == "success"
        assert call_count == 3

    def test_fails_after_max_attempts(self):
        """Raises exception after max attempts exhausted."""

        def always_fails():
            raise NetworkError("always fails")

        config = RetryConfig(max_attempts=3, base_delay=0.01)

        with pytest.raises(NetworkError, match="always fails"):
            with_retry_sync(always_fails, config)

    def test_permanent_error_not_retried(self):
        """Permanent errors are raised immediately without retry."""
        call_count = 0

        def fails_with_permanent():
            nonlocal call_count
            call_count += 1
            raise ValidationError("invalid input")

        config = RetryConfig(base_delay=0.01)

        with pytest.raises(ValidationError):
            with_retry_sync(fails_with_permanent, config)

        assert call_count == 1

    def test_exponential_backoff_delays(self):
        """Verify exponential backoff timing."""
        delays = []

        def always_fails():
            raise NetworkError("fail")

        def mock_sleep(delay):
            delays.append(delay)

        config = RetryConfig(max_attempts=4, base_delay=1.0, multiplier=2.0)

        with patch("time.sleep", side_effect=mock_sleep), pytest.raises(NetworkError):
            with_retry_sync(always_fails, config)

        # Expected delays: 1.0, 2.0, 4.0 (3 retries after 4 attempts)
        assert len(delays) == 3
        assert delays[0] == 1.0
        assert delays[1] == 2.0
        assert delays[2] == 4.0
