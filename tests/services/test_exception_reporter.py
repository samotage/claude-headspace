"""Tests for ExceptionReporter service."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.exception_reporter import ExceptionReporter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    enabled=True,
    webhook_url="https://example.com/webhooks/exceptions/test",
    timeout=5,
    rate_limit=5,
):
    return {
        "otagemon": {
            "enabled": enabled,
            "webhook_url": webhook_url,
            "timeout": timeout,
            "rate_limit_per_second": rate_limit,
        },
    }


def _make_reporter(config=None, secret="test-secret"):
    if config is None:
        config = _make_config()
    with patch.dict("os.environ", {"OTAGEMON_WEBHOOK_SECRET": secret}):
        return ExceptionReporter(config)


# ---------------------------------------------------------------------------
# Configuration & is_configured
# ---------------------------------------------------------------------------

class TestConfiguration:
    def test_is_configured_when_all_present(self):
        reporter = _make_reporter()
        assert reporter.is_configured is True

    def test_not_configured_when_disabled(self):
        reporter = _make_reporter(config=_make_config(enabled=False))
        assert reporter.is_configured is False

    def test_not_configured_when_no_url(self):
        reporter = _make_reporter(config=_make_config(webhook_url=""))
        assert reporter.is_configured is False

    def test_not_configured_when_no_secret(self):
        reporter = _make_reporter(secret="")
        assert reporter.is_configured is False

    def test_defaults_from_empty_config(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove env var if present
            import os
            os.environ.pop("OTAGEMON_WEBHOOK_SECRET", None)
            reporter = ExceptionReporter({})
        assert reporter.is_configured is False
        assert reporter._timeout == 5
        assert reporter._rate_limit == 5

    def test_secret_from_config_fallback(self):
        config = _make_config()
        config["otagemon"]["webhook_secret"] = "config-secret"
        with patch.dict("os.environ", {}, clear=False):
            import os
            os.environ.pop("OTAGEMON_WEBHOOK_SECRET", None)
            reporter = ExceptionReporter(config)
        assert reporter._webhook_secret == "config-secret"
        assert reporter.is_configured is True

    def test_env_var_takes_precedence_over_config(self):
        config = _make_config()
        config["otagemon"]["webhook_secret"] = "config-secret"
        reporter = _make_reporter(config=config, secret="env-secret")
        assert reporter._webhook_secret == "env-secret"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:
    def test_allows_up_to_rate_limit(self):
        reporter = _make_reporter(config=_make_config(rate_limit=3))
        assert reporter._try_consume_token() is True
        assert reporter._try_consume_token() is True
        assert reporter._try_consume_token() is True
        assert reporter._try_consume_token() is False

    def test_refills_over_time(self):
        reporter = _make_reporter(config=_make_config(rate_limit=5))
        # Exhaust all tokens
        for _ in range(5):
            reporter._try_consume_token()
        assert reporter._try_consume_token() is False

        # Advance time by simulating refill
        reporter._last_refill = time.monotonic() - 1.0  # 1 second ago
        assert reporter._try_consume_token() is True

    def test_does_not_exceed_burst_size(self):
        reporter = _make_reporter(config=_make_config(rate_limit=3))
        # Even after a long time, tokens cap at rate_limit
        reporter._last_refill = time.monotonic() - 100.0
        for _ in range(3):
            assert reporter._try_consume_token() is True
        assert reporter._try_consume_token() is False


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

class TestReport:
    @patch("claude_headspace.services.exception_reporter.ExceptionReporter._send")
    def test_report_sends_correct_payload(self, mock_send):
        reporter = _make_reporter()
        exc = ValueError("test error")
        try:
            raise exc
        except ValueError as e:
            reporter.report(
                exc=e,
                source="request",
                severity="error",
                context={"request_path": "/api/test"},
            )

        # Wait for the daemon thread to call _send
        time.sleep(0.1)

        mock_send.assert_called_once()
        payload = mock_send.call_args[0][0]
        assert payload["exception_type"] == "ValueError"
        assert payload["message"] == "test error"
        assert "Traceback" in payload["traceback"]
        assert payload["source"] == "request"
        assert payload["severity"] == "error"
        assert payload["context"]["request_path"] == "/api/test"

    @patch("claude_headspace.services.exception_reporter.ExceptionReporter._send")
    def test_report_skips_when_not_configured(self, mock_send):
        reporter = _make_reporter(config=_make_config(enabled=False))
        reporter.report(exc=RuntimeError("oops"))
        time.sleep(0.1)
        mock_send.assert_not_called()

    @patch("claude_headspace.services.exception_reporter.ExceptionReporter._send")
    def test_report_skips_when_rate_limited(self, mock_send):
        reporter = _make_reporter(config=_make_config(rate_limit=1))
        reporter.report(exc=RuntimeError("first"))
        reporter.report(exc=RuntimeError("second"))  # Should be dropped
        time.sleep(0.1)
        assert mock_send.call_count == 1

    @patch("claude_headspace.services.exception_reporter.ExceptionReporter._send")
    def test_report_defaults(self, mock_send):
        reporter = _make_reporter()
        reporter.report(exc=RuntimeError("boom"))
        time.sleep(0.1)
        payload = mock_send.call_args[0][0]
        assert payload["source"] == "unknown"
        assert payload["severity"] == "error"
        assert payload["context"] == {}

    @patch("claude_headspace.services.exception_reporter.ExceptionReporter._send")
    def test_report_handles_exception_without_traceback(self, mock_send):
        reporter = _make_reporter()
        # Exception created without raising — no __traceback__
        exc = RuntimeError("no traceback")
        reporter.report(exc=exc)
        time.sleep(0.1)
        payload = mock_send.call_args[0][0]
        assert payload["exception_type"] == "RuntimeError"
        assert payload["message"] == "no traceback"


# ---------------------------------------------------------------------------
# HTTP sending
# ---------------------------------------------------------------------------

class TestSend:
    @patch("claude_headspace.services.exception_reporter.requests.post")
    def test_send_posts_to_webhook(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "status": "accepted",
            "exception_event_id": 42,
            "issue_id": None,
        }
        mock_post.return_value = mock_response

        reporter = _make_reporter()
        payload = {
            "exception_type": "ValueError",
            "message": "bad value",
        }
        reporter._send(payload)

        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"] == payload
        assert "Bearer test-secret" in call_kwargs[1]["headers"]["Authorization"]
        assert call_kwargs[1]["timeout"] == 5
        assert call_kwargs[1]["verify"] is False

    @patch("claude_headspace.services.exception_reporter.requests.post")
    def test_send_handles_non_200_response(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_post.return_value = mock_response

        reporter = _make_reporter()
        # Should not raise
        reporter._send({"exception_type": "Error", "message": "test"})

    @patch("claude_headspace.services.exception_reporter.requests.post")
    def test_send_handles_connection_error(self, mock_post):
        mock_post.side_effect = ConnectionError("refused")

        reporter = _make_reporter()
        # Should not raise
        reporter._send({"exception_type": "Error", "message": "test"})

    @patch("claude_headspace.services.exception_reporter.requests.post")
    def test_send_handles_timeout(self, mock_post):
        import requests as req_lib
        mock_post.side_effect = req_lib.exceptions.Timeout("timed out")

        reporter = _make_reporter()
        # Should not raise
        reporter._send({"exception_type": "Error", "message": "test"})


# ---------------------------------------------------------------------------
# App integration
# ---------------------------------------------------------------------------

class TestAppIntegration:
    def test_exception_reporter_registered_in_extensions(self, app):
        assert "exception_reporter" in app.extensions
        assert isinstance(app.extensions["exception_reporter"], ExceptionReporter)
