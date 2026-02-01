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
    """
    Service for sending macOS system notifications via terminal-notifier.

    Features:
    - Send notifications for agent state changes
    - Rate limiting per agent to prevent spam
    - Click-to-navigate with agent highlight
    - Graceful degradation when terminal-notifier unavailable
    """

    def __init__(self, preferences: NotificationPreferences | None = None):
        """
        Initialize the notification service.

        Args:
            preferences: Notification preferences (uses defaults if None)
        """
        self.preferences = preferences or NotificationPreferences()
        self._rate_limit_tracker: dict[str, float] = {}
        self._rate_limit_lock = threading.Lock()
        self._availability_checked = False
        self._is_available = False
        self._first_failure_logged = False

    def is_available(self) -> bool:
        """
        Check if terminal-notifier is available.

        Returns:
            True if terminal-notifier is installed and accessible
        """
        if not self._availability_checked:
            self._is_available = shutil.which("terminal-notifier") is not None
            self._availability_checked = True
            if self._is_available:
                logger.info("terminal-notifier detected - notifications available")
            else:
                logger.warning(
                    "terminal-notifier not found - notifications unavailable. "
                    "Install with: brew install terminal-notifier"
                )
        return self._is_available

    def refresh_availability(self) -> bool:
        """
        Re-check terminal-notifier availability.

        Returns:
            True if terminal-notifier is now available
        """
        self._availability_checked = False
        return self.is_available()

    def _is_rate_limited(self, agent_id: str) -> bool:
        """
        Check if notifications for this agent are rate-limited.

        Args:
            agent_id: The agent identifier

        Returns:
            True if notifications should be suppressed
        """
        with self._rate_limit_lock:
            now = time.time()
            last_notification = self._rate_limit_tracker.get(agent_id, 0)
            elapsed = now - last_notification
            return elapsed < self.preferences.rate_limit_seconds

    def _update_rate_limit(self, agent_id: str) -> None:
        """
        Record that a notification was sent for this agent.

        Args:
            agent_id: The agent identifier
        """
        with self._rate_limit_lock:
            self._rate_limit_tracker[agent_id] = time.time()

    def _build_notification_command(
        self,
        title: str,
        subtitle: str,
        message: str,
        url: str | None = None,
    ) -> list[str]:
        """
        Build the terminal-notifier command.

        Args:
            title: Notification title
            subtitle: Notification subtitle
            message: Notification body message
            url: Optional URL to open on click

        Returns:
            Command as list of arguments
        """
        cmd = [
            "terminal-notifier",
            "-title", title,
            "-subtitle", subtitle,
            "-message", message,
        ]

        if self.preferences.sound:
            cmd.extend(["-sound", "default"])

        if url:
            cmd.extend(["-open", url])

        return cmd

    def send_notification(
        self,
        agent_id: str,
        agent_name: str,
        event_type: str,
        project: str | None = None,
        dashboard_url: str | None = None,
    ) -> bool:
        """
        Send a macOS notification for an agent event.

        Args:
            agent_id: The agent identifier for rate limiting
            agent_name: Human-readable agent name
            event_type: Event type (task_complete, awaiting_input)
            project: Optional project name
            dashboard_url: Base URL for the dashboard

        Returns:
            True if notification was sent (or skipped due to settings)
            False if sending failed
        """
        # Check if globally enabled
        if not self.preferences.enabled:
            logger.debug("Notifications disabled globally")
            return True

        # Check if this event type is enabled
        if not self.preferences.events.get(event_type, False):
            logger.debug(f"Notifications disabled for event type: {event_type}")
            return True

        # Check availability
        if not self.is_available():
            if not self._first_failure_logged:
                logger.warning(
                    "Cannot send notification - terminal-notifier not available"
                )
                self._first_failure_logged = True
            return False

        # Check rate limiting
        if self._is_rate_limited(agent_id):
            logger.debug(
                f"Notification rate-limited for agent {agent_id} "
                f"(cooldown: {self.preferences.rate_limit_seconds}s)"
            )
            return True

        # Build notification content
        title = "Claude Headspace"

        if project:
            subtitle = f"Agent: {agent_name} ({project})"
        else:
            subtitle = f"Agent: {agent_name}"

        if event_type == "task_complete":
            message = "Task completed - agent is now idle"
        elif event_type == "awaiting_input":
            message = "Input needed - agent is waiting for your response"
        else:
            message = f"Event: {event_type}"

        # Build click-to-navigate URL
        base_url = dashboard_url or self.preferences.dashboard_url
        url = f"{base_url}?highlight={agent_id}"

        # Build and execute command
        cmd = self._build_notification_command(title, subtitle, message, url)

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=0.5,  # 500ms timeout for NFR1
            )

            if result.returncode != 0:
                logger.warning(
                    f"terminal-notifier returned non-zero: {result.returncode}, "
                    f"stderr: {result.stderr}"
                )
                return False

            # Update rate limit tracker
            self._update_rate_limit(agent_id)

            logger.info(
                f"Notification sent: agent={agent_name}, event={event_type}"
            )
            return True

        except subprocess.TimeoutExpired:
            logger.warning("Notification timed out (>500ms)")
            return False
        except Exception as e:
            logger.warning(f"Failed to send notification: {e}")
            return False

    def notify_task_complete(
        self,
        agent_id: str,
        agent_name: str,
        project: str | None = None,
    ) -> bool:
        """
        Send notification for task completion.

        Args:
            agent_id: The agent identifier
            agent_name: Human-readable agent name
            project: Optional project name

        Returns:
            True if notification was sent successfully
        """
        return self.send_notification(
            agent_id=agent_id,
            agent_name=agent_name,
            event_type="task_complete",
            project=project,
        )

    def notify_awaiting_input(
        self,
        agent_id: str,
        agent_name: str,
        project: str | None = None,
    ) -> bool:
        """
        Send notification when agent is awaiting input.

        Args:
            agent_id: The agent identifier
            agent_name: Human-readable agent name
            project: Optional project name

        Returns:
            True if notification was sent successfully
        """
        return self.send_notification(
            agent_id=agent_id,
            agent_name=agent_name,
            event_type="awaiting_input",
            project=project,
        )

    def get_preferences(self) -> dict[str, Any]:
        """
        Get current notification preferences as a dictionary.

        Returns:
            Dictionary of current preferences
        """
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
        """
        Update notification preferences.

        Args:
            enabled: Global enable/disable
            sound: Sound enable/disable
            events: Event type settings
            rate_limit_seconds: Rate limit period
        """
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


def get_notification_service() -> NotificationService:
    """Get the global notification service instance."""
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service


def configure_notification_service(preferences: NotificationPreferences) -> None:
    """
    Configure the global notification service.

    Args:
        preferences: Notification preferences to use
    """
    global _notification_service
    _notification_service = NotificationService(preferences)
