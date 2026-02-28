"""Exception reporter service for forwarding unhandled exceptions to otageMon.

Best-effort, non-blocking. If otageMon is unreachable, Headspace keeps running.
Each report fires in a daemon thread with a short timeout. A token bucket
rate limiter caps throughput at a configurable max per second (default 5).
"""

import logging
import os
import threading
import time
import traceback as tb_module
from typing import Any

import requests
import urllib3

logger = logging.getLogger(__name__)

# Suppress InsecureRequestWarning for Tailscale cert calls
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class ExceptionReporter:
    """Reports unhandled exceptions to otageMon's exception webhook."""

    def __init__(self, config: dict) -> None:
        otagemon_config = config.get("otagemon", {})
        self._webhook_url = otagemon_config.get("webhook_url", "")
        self._webhook_secret = (
            os.environ.get("OTAGEMON_WEBHOOK_SECRET")
            or otagemon_config.get("webhook_secret", "")
        )
        self._timeout = otagemon_config.get("timeout", 5)
        self._enabled = otagemon_config.get("enabled", True)

        # Token bucket rate limiter
        self._rate_limit = otagemon_config.get("rate_limit_per_second", 5)
        self._tokens = float(self._rate_limit)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    @property
    def is_configured(self) -> bool:
        """True when the reporter has a URL, secret, and is enabled."""
        return self._enabled and bool(self._webhook_url) and bool(self._webhook_secret)

    # ------------------------------------------------------------------
    # Rate limiting
    # ------------------------------------------------------------------

    def _try_consume_token(self) -> bool:
        """Token bucket rate limiter. Returns True if a send is allowed."""
        with self._lock:
            now = time.monotonic()
            elapsed = max(0, now - self._last_refill)
            self._tokens = min(
                self._rate_limit,
                self._tokens + elapsed * self._rate_limit,
            )
            self._last_refill = now

            if self._tokens >= 1:
                self._tokens -= 1
                return True
            return False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def report(
        self,
        exc: BaseException,
        source: str = "unknown",
        severity: str = "error",
        context: dict[str, Any] | None = None,
    ) -> None:
        """Report an exception to otageMon.

        Non-blocking: the HTTP POST fires in a daemon thread.
        Fails silently if otageMon is unreachable or rate limited.
        """
        if not self.is_configured:
            return

        if not self._try_consume_token():
            logger.debug("Exception report rate-limited, dropping")
            return

        # Build traceback string
        try:
            tb_str = "".join(
                tb_module.format_exception(type(exc), exc, exc.__traceback__)
            )
        except Exception:
            tb_str = str(exc)

        payload = {
            "exception_type": type(exc).__name__,
            "message": str(exc),
            "traceback": tb_str,
            "source": source,
            "severity": severity,
            "context": context or {},
        }

        thread = threading.Thread(
            target=self._send,
            args=(payload,),
            daemon=True,
            name="ExceptionReporter",
        )
        thread.start()

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _send(self, payload: dict) -> None:
        """POST payload to otageMon. Runs in a daemon thread."""
        try:
            response = requests.post(
                self._webhook_url,
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {self._webhook_secret}",
                },
                timeout=self._timeout,
                verify=False,  # Tailscale certs
            )
            if response.status_code in (200, 201):
                data = response.json()
                logger.debug(
                    "Exception reported to otageMon (event_id=%s, issue_id=%s)",
                    data.get("exception_event_id"),
                    data.get("issue_id"),
                )
            else:
                logger.warning(
                    "otageMon webhook returned %d: %s",
                    response.status_code,
                    response.text[:200],
                )
        except Exception:
            # Fail silently — if otageMon is down, Headspace must keep running
            logger.debug("Failed to report exception to otageMon", exc_info=True)
