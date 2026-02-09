"""Notification service for macOS system notifications."""

import logging
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class NotificationPreferences:
    """Notification preferences configuration."""

    enabled: bool = True
    sound: bool = True
    events: dict = field(default_factory=lambda: {
        "task_complete": True,
        "awaiting_input": True,
    })
    rate_limit_seconds: int = 5
    dashboard_url: str = "http://localhost:5055"


class NotificationService:
    """macOS system notifications via terminal-notifier with rate limiting."""

    def __init__(self, preferences: NotificationPreferences | None = None):
        self.preferences = preferences or NotificationPreferences()
        self._rate_limit_tracker: dict[str, float] = {}
        self._rate_limit_lock = threading.Lock()
        self._availability_checked = False
        self._is_available = False
        self._first_failure_logged = False

    def is_available(self) -> bool:
        """Check if terminal-notifier is installed."""
        if not self._availability_checked:
            self._is_available = shutil.which("terminal-notifier") is not None
            self._availability_checked = True
            if self._is_available:
                logger.info("terminal-notifier detected")
            else:
                logger.warning("terminal-notifier not found - install with: brew install terminal-notifier")
        return self._is_available

    def refresh_availability(self) -> bool:
        """Re-check terminal-notifier availability."""
        self._availability_checked = False
        return self.is_available()

    def _is_rate_limited(self, agent_id: str) -> bool:
        with self._rate_limit_lock:
            now = time.time()
            # Prune stale entries (older than 10x the rate limit window)
            if len(self._rate_limit_tracker) > 10:
                cutoff = now - (self.preferences.rate_limit_seconds * 10)
                self._rate_limit_tracker = {
                    k: v for k, v in self._rate_limit_tracker.items()
                    if v > cutoff
                }
            last = self._rate_limit_tracker.get(agent_id, 0)
            return (now - last) < self.preferences.rate_limit_seconds

    def _update_rate_limit(self, agent_id: str) -> None:
        with self._rate_limit_lock:
            self._rate_limit_tracker[agent_id] = time.time()

    def _build_notification_command(
        self, title: str, subtitle: str, message: str, url: str | None = None,
    ) -> list[str]:
        cmd = [
            "terminal-notifier",
            "-title", title,
            "-subtitle", subtitle,
            "-message", message,
            "-sender", "com.googlecode.iterm2",
        ]
        if self.preferences.sound:
            cmd.extend(["-sound", "default"])
        if url:
            cmd.extend(["-open", url])
        return cmd

    def _build_contextual_message(
        self, event_type: str, task_instruction: str | None = None, turn_text: str | None = None,
    ) -> str:
        parts = []
        if task_instruction:
            parts.append(task_instruction)
        if turn_text:
            prefix = {"task_complete": "\u2713 ", "awaiting_input": "? "}.get(event_type, "")
            parts.append(f"{prefix}{turn_text}")
        if parts:
            return "\n".join(parts)
        defaults = {
            "task_complete": "Task completed - agent is now idle",
            "awaiting_input": "Input needed - agent is waiting for your response",
        }
        return defaults.get(event_type, f"Event: {event_type}")

    def send_notification(
        self,
        agent_id: str,
        agent_name: str,
        event_type: str,
        project: str | None = None,
        dashboard_url: str | None = None,
        task_instruction: str | None = None,
        turn_text: str | None = None,
    ) -> bool:
        """Send a macOS notification for an agent event. Returns True if sent/skipped."""
        if not self.preferences.enabled:
            return True
        if not self.preferences.events.get(event_type, False):
            return True
        if not self.is_available():
            if not self._first_failure_logged:
                logger.warning("Cannot send notification - terminal-notifier not available")
                self._first_failure_logged = True
            return False
        if self._is_rate_limited(agent_id):
            return True

        titles = {"task_complete": "Task Complete", "awaiting_input": "Input Needed"}
        title = titles.get(event_type, "Claude Headspace")
        subtitle = f"{project} ({agent_name})" if project else agent_name
        message = self._build_contextual_message(event_type, task_instruction, turn_text)
        base_url = dashboard_url or self.preferences.dashboard_url
        url = f"{base_url}?highlight={agent_id}"
        cmd = self._build_notification_command(title, subtitle, message, url)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.warning(f"terminal-notifier returned {result.returncode}: {result.stderr}")
                return False
            self._update_rate_limit(agent_id)
            logger.info(f"Notification sent: agent={agent_name}, event={event_type}")
            return True
        except subprocess.TimeoutExpired:
            logger.warning("Notification timed out")
            return False
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
            return False

    def notify_task_complete(self, **kwargs) -> bool:
        """Send notification for task completion."""
        return self.send_notification(event_type="task_complete", **kwargs)

    def notify_awaiting_input(self, **kwargs) -> bool:
        """Send notification when agent is awaiting input."""
        return self.send_notification(event_type="awaiting_input", **kwargs)

    def get_preferences(self) -> dict[str, Any]:
        return {
            "enabled": self.preferences.enabled,
            "sound": self.preferences.sound,
            "events": self.preferences.events.copy(),
            "rate_limit_seconds": self.preferences.rate_limit_seconds,
        }

    def update_preferences(
        self,
        enabled: bool | None = None,
        sound: bool | None = None,
        events: dict | None = None,
        rate_limit_seconds: int | None = None,
    ) -> None:
        if enabled is not None:
            self.preferences.enabled = enabled
        if sound is not None:
            self.preferences.sound = sound
        if events is not None:
            self.preferences.events.update(events)
        if rate_limit_seconds is not None:
            self.preferences.rate_limit_seconds = rate_limit_seconds


# Global notification service instance
_notification_service: NotificationService | None = None
_notification_lock = threading.Lock()


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    with _notification_lock:
        if _notification_service is None:
            _notification_service = NotificationService()
        return _notification_service


def configure_notification_service(preferences: NotificationPreferences) -> None:
    """Configure the global notification service."""
    global _notification_service
    with _notification_lock:
        _notification_service = NotificationService(preferences)
