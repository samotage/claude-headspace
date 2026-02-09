"""Token-based authentication middleware for voice bridge API endpoints."""

import logging
import time
from collections import defaultdict
from functools import wraps

from flask import current_app, jsonify, request

logger = logging.getLogger(__name__)


class VoiceAuth:
    """Token validation and rate limiting for voice bridge endpoints."""

    def __init__(self, config: dict):
        vb_config = config.get("voice_bridge", {})
        auth_config = vb_config.get("auth", {})
        self.token = auth_config.get("token", "")
        self.localhost_bypass = auth_config.get("localhost_bypass", True)
        rate_config = vb_config.get("rate_limit", {})
        self.requests_per_minute = rate_config.get("requests_per_minute", 60)
        # Sliding window rate limiter: {token: [timestamps]}
        self._request_times: dict[str, list[float]] = defaultdict(list)

    def reload_config(self, config: dict) -> None:
        """Reload auth config without restart."""
        vb_config = config.get("voice_bridge", {})
        auth_config = vb_config.get("auth", {})
        self.token = auth_config.get("token", "")
        self.localhost_bypass = auth_config.get("localhost_bypass", True)
        rate_config = vb_config.get("rate_limit", {})
        self.requests_per_minute = rate_config.get("requests_per_minute", 60)

    def _is_localhost(self) -> bool:
        """Check if the request originates from localhost."""
        remote = request.remote_addr or ""
        return remote in ("127.0.0.1", "::1", "localhost")

    def _check_rate_limit(self, token: str) -> bool:
        """Check if request is within rate limit. Returns True if allowed."""
        now = time.time()
        window_start = now - 60.0
        # Clean old entries
        self._request_times[token] = [
            t for t in self._request_times[token] if t > window_start
        ]
        if len(self._request_times[token]) >= self.requests_per_minute:
            return False
        self._request_times[token].append(now)
        return True

    def authenticate(self):
        """Flask before_request handler for voice bridge authentication.

        Returns None to allow the request, or a response tuple to deny it.
        """
        start_time = time.time()

        # Localhost bypass
        if self.localhost_bypass and self._is_localhost():
            self._log_access(auth_status="bypass_localhost")
            return None

        # Check for token
        if not self.token:
            # No token configured — voice bridge is effectively open
            self._log_access(auth_status="no_token_configured")
            return None

        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            self._log_access(auth_status="missing_token")
            return jsonify({
                "voice": {
                    "status_line": "Authentication required.",
                    "results": [],
                    "next_action": "Include a valid Bearer token in the Authorization header.",
                },
                "error": "missing_token",
            }), 401

        provided_token = auth_header[7:]  # Strip "Bearer "
        if provided_token != self.token:
            self._log_access(auth_status="invalid_token")
            return jsonify({
                "voice": {
                    "status_line": "Invalid authentication token.",
                    "results": [],
                    "next_action": "Check your token and try again.",
                },
                "error": "invalid_token",
            }), 401

        # Rate limiting
        if not self._check_rate_limit(provided_token):
            self._log_access(auth_status="rate_limited")
            return jsonify({
                "voice": {
                    "status_line": "Too many requests. Please wait a moment.",
                    "results": [],
                    "next_action": "Try again in a few seconds.",
                },
                "error": "rate_limited",
            }), 429

        latency_ms = (time.time() - start_time) * 1000
        self._log_access(auth_status="authenticated", latency_ms=latency_ms)
        return None

    def _log_access(self, auth_status: str, latency_ms: float | None = None) -> None:
        """Log voice bridge API access."""
        agent_id = request.view_args.get("agent_id") if request.view_args else None
        logger.info(
            f"voice_bridge_access: endpoint={request.path}, "
            f"method={request.method}, source_ip={request.remote_addr}, "
            f"agent_id={agent_id}, auth_status={auth_status}"
            + (f", latency_ms={latency_ms:.1f}" if latency_ms is not None else "")
        )
