"""Tests for retry mechanism."""

from unittest.mock import MagicMock, patch

import pytest

from provisioning.exceptions import (
    AuthenticationError,
    ConnectionError,
    RateLimitError,
)
from provisioning.retry import calculate_backoff, retry_on_transient_error


class TestCalculateBackoff:
    """Tests for calculate_backoff function."""

    def test_exponential_increase(self) -> None:
        """Backoff increases exponentially."""
        # Without jitter for deterministic test
        with patch("provisioning.retry.random.random", return_value=0.5):
            delay_0 = calculate_backoff(0, base_delay=1.0, jitter_factor=0.0)
            delay_1 = calculate_backoff(1, base_delay=1.0, jitter_factor=0.0)
            delay_2 = calculate_backoff(2, base_delay=1.0, jitter_factor=0.0)
            delay_3 = calculate_backoff(3, base_delay=1.0, jitter_factor=0.0)

        assert delay_0 == 1.0  # 1 * 2^0
        assert delay_1 == 2.0  # 1 * 2^1
        assert delay_2 == 4.0  # 1 * 2^2
        assert delay_3 == 8.0  # 1 * 2^3

    def test_max_delay_cap(self) -> None:
        """Backoff is capped at max_delay."""
        with patch("provisioning.retry.random.random", return_value=0.5):
            delay = calculate_backoff(10, base_delay=1.0, max_delay=30.0, jitter_factor=0.0)

        assert delay == 30.0

    def test_jitter_adds_randomness(self) -> None:
        """Jitter adds randomness to delay."""
        # With jitter_factor=0.5, delay can vary by +/- 50%
        with patch("provisioning.retry.random.random", return_value=0.0):
            delay_min = calculate_backoff(1, base_delay=2.0, jitter_factor=0.5)

        with patch("provisioning.retry.random.random", return_value=1.0):
            delay_max = calculate_backoff(1, base_delay=2.0, jitter_factor=0.5)

        # Base delay at attempt 1 is 4.0
        # With jitter 0.5, range is 4 +/- 2 = [2, 6]
        assert delay_min == pytest.approx(2.0, rel=0.01)
        assert delay_max == pytest.approx(6.0, rel=0.01)


class TestRetryDecorator:
    """Tests for retry_on_transient_error decorator."""

    def test_success_on_first_try(self) -> None:
        """Function succeeds without retries."""
        mock_func = MagicMock(return_value="success")
        decorated = retry_on_transient_error(max_attempts=3)(mock_func)

        result = decorated()

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retries_on_transient_error(self) -> None:
        """Function retries on TransientError."""
        mock_func = MagicMock(
            side_effect=[ConnectionError("fail"), ConnectionError("fail"), "success"]
        )
        mock_func.__name__ = "mock_func"  # Required for @wraps
        decorated = retry_on_transient_error(max_attempts=3, base_delay=0.01, jitter_factor=0.0)(
            mock_func
        )

        with patch("provisioning.retry.time.sleep"):
            result = decorated()

        assert result == "success"
        assert mock_func.call_count == 3

    def test_fails_after_max_attempts(self) -> None:
        """Function fails after max attempts exhausted."""
        mock_func = MagicMock(side_effect=ConnectionError("persistent failure"))
        mock_func.__name__ = "mock_func"  # Required for @wraps
        decorated = retry_on_transient_error(max_attempts=3, base_delay=0.01, jitter_factor=0.0)(
            mock_func
        )

        with patch("provisioning.retry.time.sleep"):
            with pytest.raises(ConnectionError, match="persistent failure"):
                decorated()

        assert mock_func.call_count == 3

    def test_no_retry_on_permanent_error(self) -> None:
        """Function does not retry on PermanentError."""
        mock_func = MagicMock(side_effect=AuthenticationError("bad credentials"))
        mock_func.__name__ = "mock_func"  # Required for @wraps
        decorated = retry_on_transient_error(max_attempts=3)(mock_func)

        with pytest.raises(AuthenticationError, match="bad credentials"):
            decorated()

        assert mock_func.call_count == 1

    def test_respects_rate_limit_retry_after(self) -> None:
        """Uses Retry-After header value for rate limit errors."""
        mock_func = MagicMock(side_effect=[RateLimitError(retry_after=5), "success"])
        mock_func.__name__ = "mock_func"  # Required for @wraps
        decorated = retry_on_transient_error(max_attempts=3, base_delay=0.01)(mock_func)

        with patch("provisioning.retry.time.sleep") as mock_sleep:
            result = decorated()

        assert result == "success"
        # Should use retry_after value (5) instead of calculated backoff
        mock_sleep.assert_called_once_with(5.0)
