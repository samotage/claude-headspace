"""Notification preferences API routes."""

import logging

from flask import Blueprint, current_app, jsonify, request

from ..services.notification_service import (
    NotificationPreferences,
    get_notification_service,
)
from ..services.config_editor import load_config_file, save_config_file

logger = logging.getLogger(__name__)

notifications_bp = Blueprint("notifications", __name__)


def get_notifications_config() -> dict:
    """
    Get notifications configuration from config file.

    Returns:
        Notifications config dict with defaults applied
    """
    config = load_config_file()
    notifications = config.get("notifications", {})

    # Apply defaults
    defaults = {
        "enabled": True,
        "sound": True,
        "events": {
            "command_complete": True,
            "awaiting_input": True,
        },
        "rate_limit_seconds": 5,
    }

    for key, value in defaults.items():
        if key not in notifications:
            notifications[key] = value
        elif key == "events" and isinstance(value, dict):
            for event_key, event_value in value.items():
                if event_key not in notifications[key]:
                    notifications[key][event_key] = event_value

    return notifications


def save_notifications_config(notifications: dict) -> tuple[bool, str | None]:
    """
    Save notifications configuration to config file.

    Args:
        notifications: Notifications config to save

    Returns:
        Tuple of (success, error_message)
    """
    config = load_config_file()
    config["notifications"] = notifications
    return save_config_file(config)


@notifications_bp.route("/api/notifications/preferences", methods=["GET"])
def get_preferences():
    """
    Get current notification preferences and availability status.

    Returns:
        200: {
            "status": "ok",
            "preferences": {...},
            "available": true/false,
            "setup_instructions": "..." (if not available)
        }
    """
    try:
        service = get_notification_service()

        # Get preferences from config file
        preferences = get_notifications_config()

        # Sync service with config
        service.update_preferences(
            enabled=preferences.get("enabled"),
            sound=preferences.get("sound"),
            events=preferences.get("events"),
            rate_limit_seconds=preferences.get("rate_limit_seconds"),
        )

        response = {
            "status": "ok",
            "preferences": preferences,
            "available": service.is_available(),
        }

        if not service.is_available():
            response["setup_instructions"] = (
                "terminal-notifier is required for macOS notifications. "
                "Install with: brew install terminal-notifier"
            )

        return jsonify(response), 200

    except Exception as e:
        logger.exception(f"Error getting notification preferences: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to get notification preferences",
        }), 500


@notifications_bp.route("/api/notifications/preferences", methods=["PUT"])
def update_preferences():
    """
    Update notification preferences.

    Expected payload:
    {
        "enabled": true/false,
        "sound": true/false,
        "events": {
            "command_complete": true/false,
            "awaiting_input": true/false
        },
        "rate_limit_seconds": 5
    }

    Returns:
        200: Preferences updated successfully
        400: Invalid payload
        500: Save failed
    """
    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Content-Type must be application/json",
        }), 400

    data = request.get_json(silent=True)
    if data is None:
        return jsonify({
            "status": "error",
            "message": "Invalid JSON payload",
        }), 400

    try:
        # Get current config
        preferences = get_notifications_config()

        # Update with provided values (validate types)
        if "enabled" in data:
            if not isinstance(data["enabled"], bool):
                return jsonify({
                    "status": "error",
                    "message": "enabled must be a boolean",
                }), 400
            preferences["enabled"] = data["enabled"]

        if "sound" in data:
            if not isinstance(data["sound"], bool):
                return jsonify({
                    "status": "error",
                    "message": "sound must be a boolean",
                }), 400
            preferences["sound"] = data["sound"]

        if "events" in data:
            if not isinstance(data["events"], dict):
                return jsonify({
                    "status": "error",
                    "message": "events must be an object",
                }), 400
            for event_type, value in data["events"].items():
                if event_type not in ["command_complete", "awaiting_input"]:
                    return jsonify({
                        "status": "error",
                        "message": f"Unknown event type: {event_type}",
                    }), 400
                if not isinstance(value, bool):
                    return jsonify({
                        "status": "error",
                        "message": f"Event {event_type} value must be a boolean",
                    }), 400
                preferences["events"][event_type] = value

        if "rate_limit_seconds" in data:
            if not isinstance(data["rate_limit_seconds"], int):
                return jsonify({
                    "status": "error",
                    "message": "rate_limit_seconds must be an integer",
                }), 400
            if data["rate_limit_seconds"] < 0 or data["rate_limit_seconds"] > 60:
                return jsonify({
                    "status": "error",
                    "message": "rate_limit_seconds must be between 0 and 60",
                }), 400
            preferences["rate_limit_seconds"] = data["rate_limit_seconds"]

        # Save to config file
        success, error_message = save_notifications_config(preferences)

        if not success:
            return jsonify({
                "status": "error",
                "message": error_message or "Failed to save preferences",
            }), 500

        # Update the service instance
        service = get_notification_service()
        service.update_preferences(
            enabled=preferences.get("enabled"),
            sound=preferences.get("sound"),
            events=preferences.get("events"),
            rate_limit_seconds=preferences.get("rate_limit_seconds"),
        )

        logger.info("Notification preferences updated")

        return jsonify({
            "status": "ok",
            "message": "Preferences updated",
            "preferences": preferences,
        }), 200

    except Exception as e:
        logger.exception(f"Error updating notification preferences: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to update preferences",
        }), 500


@notifications_bp.route("/api/notifications/refresh-availability", methods=["POST"])
def refresh_availability():
    """
    Re-check terminal-notifier availability.

    Useful after user installs terminal-notifier.

    Returns:
        200: {
            "status": "ok",
            "available": true/false
        }
    """
    try:
        service = get_notification_service()
        available = service.refresh_availability()

        return jsonify({
            "status": "ok",
            "available": available,
        }), 200

    except Exception as e:
        logger.exception(f"Error refreshing availability: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to refresh availability",
        }), 500


@notifications_bp.route("/api/notifications/test", methods=["POST"])
def test_notification():
    """
    Send a test notification.

    Returns:
        200: Test notification sent
        400: Notifications disabled or unavailable
    """
    try:
        service = get_notification_service()

        if not service.is_available():
            return jsonify({
                "status": "error",
                "message": "Notifications unavailable - terminal-notifier not installed",
            }), 400

        if not service.preferences.enabled:
            return jsonify({
                "status": "error",
                "message": "Notifications are disabled",
            }), 400

        # Send test notification (bypass rate limiting by using unique ID)
        import time
        success = service.send_notification(
            agent_id=f"test-{time.time()}",
            agent_name="Test Agent",
            event_type="command_complete",
            project="Test Project",
        )

        if success:
            return jsonify({
                "status": "ok",
                "message": "Test notification sent",
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to send test notification",
            }), 500

    except Exception as e:
        logger.exception(f"Error sending test notification: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to send test notification",
        }), 500
