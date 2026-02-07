"""Tests for NotificationService.

Covers: rate limiting, command building, contextual messages,
dispatch methods, availability detection, and singleton thread-safety.
"""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.notification_service import (
    NotificationPreferences,
    NotificationService,
    configure_notification_service,
    get_notification_service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def prefs():
    """Default preferences with notifications enabled."""
    return NotificationPreferences(
        enabled=True,
        sound=True,
        events={"task_complete": True, "awaiting_input": True},
        rate_limit_seconds=5,
        dashboard_url="http://localhost:5055",
    )


@pytest.fixture
def service(prefs):
    return NotificationService(prefs)


@pytest.fixture
def available_service(service):
    """Service that reports terminal-notifier as available."""
    service._availability_checked = True
    service._is_available = True
    return service


# ---------------------------------------------------------------------------
# NotificationPreferences
# ---------------------------------------------------------------------------

class TestNotificationPreferences:

    def test_defaults(self):
        p = NotificationPreferences()
        assert p.enabled is True
        assert p.sound is True
        assert p.rate_limit_seconds == 5
        assert p.events["task_complete"] is True
        assert p.events["awaiting_input"] is True

    def test_custom_values(self):
        p = NotificationPreferences(enabled=False, sound=False, rate_limit_seconds=10)
        assert p.enabled is False
        assert p.sound is False
        assert p.rate_limit_seconds == 10


# ---------------------------------------------------------------------------
# Availability detection
# ---------------------------------------------------------------------------

class TestAvailability:

    @patch("claude_headspace.services.notification_service.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    def test_is_available_when_installed(self, mock_which, service):
        assert service.is_available() is True
        mock_which.assert_called_once_with("terminal-notifier")

    @patch("claude_headspace.services.notification_service.shutil.which", return_value=None)
    def test_not_available_when_missing(self, mock_which, service):
        assert service.is_available() is False

    @patch("claude_headspace.services.notification_service.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    def test_caches_availability_check(self, mock_which, service):
        service.is_available()
        service.is_available()
        # Only called once due to caching
        mock_which.assert_called_once()

    @patch("claude_headspace.services.notification_service.shutil.which", return_value="/usr/local/bin/terminal-notifier")
    def test_refresh_availability_resets_cache(self, mock_which, service):
        service.is_available()
        service.refresh_availability()
        assert mock_which.call_count == 2


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------

class TestRateLimiting:

    def test_first_call_not_rate_limited(self, service):
        assert service._is_rate_limited("agent-1") is False

    def test_second_call_within_window_is_limited(self, service):
        service._update_rate_limit("agent-1")
        assert service._is_rate_limited("agent-1") is True

    def test_different_agents_independent(self, service):
        service._update_rate_limit("agent-1")
        assert service._is_rate_limited("agent-2") is False

    def test_expired_entry_allows_new_call(self, service):
        service.preferences.rate_limit_seconds = 0  # Immediate expiry
        service._update_rate_limit("agent-1")
        time.sleep(0.01)
        assert service._is_rate_limited("agent-1") is False

    def test_pruning_when_tracker_exceeds_100(self, service):
        service.preferences.rate_limit_seconds = 0  # Entries expire instantly
        # Populate 101 stale entries
        for i in range(101):
            service._rate_limit_tracker[f"agent-{i}"] = 0.0
        time.sleep(0.01)
        # Trigger pruning by checking rate limit
        service._is_rate_limited("agent-new")
        assert len(service._rate_limit_tracker) < 101


# ---------------------------------------------------------------------------
# Command building
# ---------------------------------------------------------------------------

class TestBuildNotificationCommand:

    def test_basic_command(self, service):
        cmd = service._build_notification_command("Title", "Sub", "Msg")
        assert cmd[0] == "terminal-notifier"
        assert "-title" in cmd
        idx = cmd.index("-title")
        assert cmd[idx + 1] == "Title"
        assert "-subtitle" in cmd
        assert "-message" in cmd

    def test_includes_sound_when_enabled(self, service):
        service.preferences.sound = True
        cmd = service._build_notification_command("T", "S", "M")
        assert "-sound" in cmd

    def test_no_sound_when_disabled(self, service):
        service.preferences.sound = False
        cmd = service._build_notification_command("T", "S", "M")
        assert "-sound" not in cmd

    def test_includes_url_when_provided(self, service):
        cmd = service._build_notification_command("T", "S", "M", url="http://example.com")
        assert "-open" in cmd
        idx = cmd.index("-open")
        assert cmd[idx + 1] == "http://example.com"

    def test_no_url_when_none(self, service):
        cmd = service._build_notification_command("T", "S", "M", url=None)
        assert "-open" not in cmd

    def test_includes_sender(self, service):
        cmd = service._build_notification_command("T", "S", "M")
        assert "-sender" in cmd
        idx = cmd.index("-sender")
        assert cmd[idx + 1] == "com.googlecode.iterm2"


# ---------------------------------------------------------------------------
# Contextual message building
# ---------------------------------------------------------------------------

class TestBuildContextualMessage:

    def test_task_complete_with_turn_text(self, service):
        msg = service._build_contextual_message("task_complete", turn_text="All done")
        assert "\u2713" in msg
        assert "All done" in msg

    def test_awaiting_input_with_turn_text(self, service):
        msg = service._build_contextual_message("awaiting_input", turn_text="What next?")
        assert "?" in msg
        assert "What next?" in msg

    def test_with_instruction_and_turn_text(self, service):
        msg = service._build_contextual_message(
            "task_complete",
            task_instruction="Implement feature X",
            turn_text="Feature done",
        )
        assert "Implement feature X" in msg
        assert "Feature done" in msg

    def test_default_task_complete_message(self, service):
        msg = service._build_contextual_message("task_complete")
        assert "Task completed" in msg

    def test_default_awaiting_input_message(self, service):
        msg = service._build_contextual_message("awaiting_input")
        assert "Input needed" in msg

    def test_unknown_event_type_fallback(self, service):
        msg = service._build_contextual_message("unknown_event")
        assert "unknown_event" in msg


# ---------------------------------------------------------------------------
# send_notification
# ---------------------------------------------------------------------------

class TestSendNotification:

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_successful_send(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=0)
        result = available_service.send_notification(
            agent_id="a1", agent_name="Agent 1",
            event_type="task_complete", project="My Project",
        )
        assert result is True
        mock_run.assert_called_once()

    def test_disabled_returns_true_without_sending(self, available_service):
        available_service.preferences.enabled = False
        result = available_service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        assert result is True

    def test_event_type_disabled_returns_true(self, available_service):
        available_service.preferences.events["task_complete"] = False
        result = available_service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        assert result is True

    @patch("claude_headspace.services.notification_service.shutil.which", return_value=None)
    def test_not_available_returns_false(self, mock_which, service):
        result = service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        assert result is False

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_rate_limited_returns_true(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=0)
        available_service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        # Second call immediately should be rate-limited (returns True, no send)
        result = available_service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        assert result is True
        assert mock_run.call_count == 1  # Only first call actually sent

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_nonzero_returncode_returns_false(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        result = available_service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        assert result is False

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_timeout_returns_false(self, mock_run, available_service):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="terminal-notifier", timeout=5)
        result = available_service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        assert result is False

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_exception_returns_false(self, mock_run, available_service):
        mock_run.side_effect = OSError("File not found")
        result = available_service.send_notification(
            agent_id="a1", agent_name="Agent 1", event_type="task_complete",
        )
        assert result is False

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_subtitle_with_project(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=0)
        available_service.send_notification(
            agent_id="a1", agent_name="Agent 1",
            event_type="task_complete", project="MyProj",
        )
        cmd = mock_run.call_args[0][0]
        sub_idx = cmd.index("-subtitle")
        assert "MyProj" in cmd[sub_idx + 1]
        assert "Agent 1" in cmd[sub_idx + 1]

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_subtitle_without_project(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=0)
        available_service.send_notification(
            agent_id="a1", agent_name="Agent 1",
            event_type="task_complete", project=None,
        )
        cmd = mock_run.call_args[0][0]
        sub_idx = cmd.index("-subtitle")
        assert cmd[sub_idx + 1] == "Agent 1"

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_custom_dashboard_url(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=0)
        available_service.send_notification(
            agent_id="a1", agent_name="Agent 1",
            event_type="task_complete",
            dashboard_url="http://custom:9999",
        )
        cmd = mock_run.call_args[0][0]
        open_idx = cmd.index("-open")
        assert "http://custom:9999" in cmd[open_idx + 1]


# ---------------------------------------------------------------------------
# Dispatch convenience methods
# ---------------------------------------------------------------------------

class TestDispatchMethods:

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_notify_task_complete(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=0)
        result = available_service.notify_task_complete(
            agent_id="a1", agent_name="Agent 1",
        )
        assert result is True

    @patch("claude_headspace.services.notification_service.subprocess.run")
    def test_notify_awaiting_input(self, mock_run, available_service):
        mock_run.return_value = MagicMock(returncode=0)
        result = available_service.notify_awaiting_input(
            agent_id="a1", agent_name="Agent 1",
        )
        assert result is True


# ---------------------------------------------------------------------------
# Preferences get/update
# ---------------------------------------------------------------------------

class TestPreferences:

    def test_get_preferences(self, service):
        prefs = service.get_preferences()
        assert prefs["enabled"] is True
        assert prefs["sound"] is True
        assert prefs["rate_limit_seconds"] == 5
        assert "task_complete" in prefs["events"]

    def test_update_preferences_partial(self, service):
        service.update_preferences(enabled=False)
        assert service.preferences.enabled is False
        assert service.preferences.sound is True  # Unchanged

    def test_update_preferences_events(self, service):
        service.update_preferences(events={"new_event": True})
        assert service.preferences.events["new_event"] is True
        assert service.preferences.events["task_complete"] is True  # Merged, not replaced

    def test_update_preferences_all(self, service):
        service.update_preferences(
            enabled=False, sound=False, rate_limit_seconds=30,
        )
        assert service.preferences.enabled is False
        assert service.preferences.sound is False
        assert service.preferences.rate_limit_seconds == 30


# ---------------------------------------------------------------------------
# Singleton / thread-safety
# ---------------------------------------------------------------------------

class TestSingleton:

    def test_get_notification_service_returns_instance(self):
        import claude_headspace.services.notification_service as ns
        original = ns._notification_service
        try:
            ns._notification_service = None
            svc = get_notification_service()
            assert isinstance(svc, NotificationService)
        finally:
            ns._notification_service = original

    def test_get_notification_service_returns_same_instance(self):
        import claude_headspace.services.notification_service as ns
        original = ns._notification_service
        try:
            ns._notification_service = None
            svc1 = get_notification_service()
            svc2 = get_notification_service()
            assert svc1 is svc2
        finally:
            ns._notification_service = original

    def test_configure_replaces_instance(self):
        import claude_headspace.services.notification_service as ns
        original = ns._notification_service
        try:
            ns._notification_service = None
            svc1 = get_notification_service()
            configure_notification_service(NotificationPreferences(sound=False))
            svc2 = get_notification_service()
            assert svc2 is not svc1
            assert svc2.preferences.sound is False
        finally:
            ns._notification_service = original

    def test_thread_safe_creation(self):
        import claude_headspace.services.notification_service as ns
        original = ns._notification_service
        try:
            ns._notification_service = None
            instances = []

            def get_instance():
                instances.append(get_notification_service())

            threads = [threading.Thread(target=get_instance) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            # All threads should get the same instance
            assert all(inst is instances[0] for inst in instances)
        finally:
            ns._notification_service = original
