"""Thread-safe rate limiter for inference calls."""

import logging
import threading
import time
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RateLimitResult:
    """Result of a rate limit check."""

    allowed: bool
    retry_after_seconds: float = 0.0
    reason: str = ""


class InferenceRateLimiter:
    """Sliding-window rate limiter for calls/min and tokens/min."""

    def __init__(self, config: dict):
        rate_config = config.get("openrouter", {}).get("rate_limits", {})
        self.calls_per_minute = rate_config.get("calls_per_minute", 30)
        self.tokens_per_minute = rate_config.get("tokens_per_minute", 50000)
        self._call_timestamps: list[float] = []
        self._token_records: list[tuple[float, int]] = []  # (timestamp, token_count)
        self._lock = threading.Lock()

    def check(self, estimated_tokens: int = 0) -> RateLimitResult:
        """Check if a request is within rate limits.

        Args:
            estimated_tokens: Estimated total tokens for this request

        Returns:
            RateLimitResult indicating if the request is allowed
        """
        now = time.monotonic()
        window_start = now - 60.0

        with self._lock:
            # Prune old entries
            self._call_timestamps = [t for t in self._call_timestamps if t > window_start]
            self._token_records = [(t, c) for t, c in self._token_records if t > window_start]

            # Check calls per minute
            if len(self._call_timestamps) >= self.calls_per_minute:
                oldest = self._call_timestamps[0]
                retry_after = 60.0 - (now - oldest)
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=max(retry_after, 0.1),
                    reason=f"Calls per minute limit reached ({self.calls_per_minute}/min)",
                )

            # Check tokens per minute
            total_tokens = sum(c for _, c in self._token_records) + estimated_tokens
            if total_tokens > self.tokens_per_minute:
                oldest = self._token_records[0][0] if self._token_records else now
                retry_after = 60.0 - (now - oldest)
                return RateLimitResult(
                    allowed=False,
                    retry_after_seconds=max(retry_after, 0.1),
                    reason=f"Tokens per minute limit reached ({self.tokens_per_minute}/min)",
                )

            return RateLimitResult(allowed=True)

    def record(self, tokens: int) -> None:
        """Record a completed call for rate tracking.

        Args:
            tokens: Total tokens consumed (input + output)
        """
        now = time.monotonic()
        with self._lock:
            self._call_timestamps.append(now)
            self._token_records.append((now, tokens))

    @property
    def current_usage(self) -> dict:
        """Get current rate limit usage."""
        now = time.monotonic()
        window_start = now - 60.0

        with self._lock:
            active_calls = [t for t in self._call_timestamps if t > window_start]
            active_tokens = sum(c for t, c in self._token_records if t > window_start)

            return {
                "calls_per_minute": {
                    "current": len(active_calls),
                    "limit": self.calls_per_minute,
                },
                "tokens_per_minute": {
                    "current": active_tokens,
                    "limit": self.tokens_per_minute,
                },
            }
