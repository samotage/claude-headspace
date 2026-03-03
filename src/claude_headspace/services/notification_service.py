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
        "command_complete": True,
        "awaiting_input": True,
    })
    rate_limit_seconds: int = 5
    dashboard_url: str = "https://localhost:5055"


class NotificationService:
    """macOS system notifications via terminal-notifier with rate limiting."""

    # Per-channel rate limit window in seconds
    CHANNEL_RATE_LIMIT_SECONDS = 30

    def __init__(self, preferences: NotificationPreferences | None = None):
        self.preferences = preferences or NotificationPreferences()
        self._rate_limit_tracker: dict[str, float] = {}
        self._rate_limit_lock = threading.Lock()
        self._channel_rate_limit_tracker: dict[str, float] = {}
        self._channel_rate_limit_lock = threading.Lock()
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
        self, event_type: str, command_instruction: str | None = None, turn_text: str | None = None,
    ) -> str:
        parts = []
        if command_instruction:
            parts.append(command_instruction)
        if turn_text:
            prefix = {"command_complete": "\u2713 ", "awaiting_input": "? "}.get(event_type, "")
            parts.append(f"{prefix}{turn_text}")
        if parts:
            return "\n".join(parts)
        defaults = {
            "command_complete": "Command completed - agent is now idle",
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
        command_instruction: str | None = None,
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

        titles = {"command_complete": "Command Complete", "awaiting_input": "Input Needed"}
        title = titles.get(event_type, "Claude Headspace")
        subtitle = f"{project} ({agent_name})" if project else agent_name
        message = self._build_contextual_message(event_type, command_instruction, turn_text)
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

    def _is_channel_rate_limited(self, channel_slug: str) -> bool:
        """Check if a channel notification is rate-limited (30s window).

        Args:
            channel_slug: The channel slug to check.

        Returns:
            True if a notification was sent for this channel within the
            rate limit window.
        """
        with self._channel_rate_limit_lock:
            now = time.time()
            # Prune stale entries
            if len(self._channel_rate_limit_tracker) > 20:
                cutoff = now - (self.CHANNEL_RATE_LIMIT_SECONDS * 2)
                self._channel_rate_limit_tracker = {
                    k: v for k, v in self._channel_rate_limit_tracker.items()
                    if v > cutoff
                }
            last = self._channel_rate_limit_tracker.get(channel_slug, 0)
            return (now - last) < self.CHANNEL_RATE_LIMIT_SECONDS

    def _update_channel_rate_limit(self, channel_slug: str) -> None:
        """Update the channel rate limit tracker."""
        with self._channel_rate_limit_lock:
            self._channel_rate_limit_tracker[channel_slug] = time.time()

    def send_channel_notification(
        self,
        channel_slug: str,
        sender_name: str,
        content_preview: str,
    ) -> bool:
        """Send a macOS notification for a channel message.

        Per-channel rate-limited to 30s to avoid notification spam
        during active channel conversations.

        Args:
            channel_slug: The channel slug.
            sender_name: The name of the message sender.
            content_preview: A preview of the message content.

        Returns:
            True if sent or rate-limited (suppressed), False on failure.
        """
        if not self.preferences.enabled:
            return True
        if not self.is_available():
            return False
        if self._is_channel_rate_limited(channel_slug):
            return True  # Suppressed, not failed

        title = "Channel Message"
        subtitle = f"#{channel_slug}"
        message = f"{sender_name}: {content_preview}"
        cmd = self._build_notification_command(title, subtitle, message)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode != 0:
                logger.warning(
                    f"Channel notification failed: terminal-notifier "
                    f"returned {result.returncode}"
                )
                return False
            self._update_channel_rate_limit(channel_slug)
            logger.info(
                f"Channel notification sent: #{channel_slug} from {sender_name}"
            )
            return True
        except subprocess.TimeoutExpired:
            logger.warning("Channel notification timed out")
            return False
        except Exception as e:
            logger.warning(f"Channel notification failed: {e}")
            return False

    def notify_command_complete(self, **kwargs) -> bool:
        """Send notification for command completion."""
        return self.send_notification(event_type="command_complete", **kwargs)

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
