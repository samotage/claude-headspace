"""Hook receiver API endpoints for Claude Code integration."""

import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from ..services.hook_receiver import (
    HookMode,
    get_receiver_state,
    process_notification,
    process_session_end,
    process_session_start,
    process_stop,
    process_user_prompt_submit,
)
from ..services.session_correlator import correlate_session

logger = logging.getLogger(__name__)

hooks_bp = Blueprint("hooks", __name__)


def _validate_hook_payload(required_fields: list[str]) -> tuple[dict | None, str | None]:
    """
    Validate incoming hook event payload.

    Args:
        required_fields: List of required field names

    Returns:
        Tuple of (payload, error_message). If validation fails, payload is None.
    """
    if not request.is_json:
        return None, "Content-Type must be application/json"

    data = request.get_json(silent=True)
    if data is None:
        return None, "Invalid JSON payload"

    missing = [f for f in required_fields if f not in data]
    if missing:
        return None, f"Missing required fields: {', '.join(missing)}"

    return data, None


def _log_hook_event(event_type: str, session_id: str | None, latency_ms: int) -> None:
    """Log a hook event for debugging."""
    logger.info(
        f"hook_received: type={event_type}, session_id={session_id}, "
        f"latency_ms={latency_ms}"
    )


@hooks_bp.route("/hook/session-start", methods=["POST"])
def hook_session_start():
    """
    Handle Claude Code session start hook.

    Expected payload:
    {
        "session_id": "claude-session-id",
        "working_directory": "/path/to/project"  # optional
    }

    Returns:
        200: Event processed successfully
        400: Invalid payload
        500: Processing error
    """
    start_time = time.time()

    # Check if hooks are enabled
    state = get_receiver_state()
    if not state.enabled:
        return jsonify({"status": "ignored", "reason": "hooks_disabled"}), 200

    # Validate payload
    data, error = _validate_hook_payload(["session_id"])
    if error:
        return jsonify({"status": "error", "message": error}), 400

    session_id = data["session_id"]
    working_directory = data.get("working_directory")

    try:
        # Correlate session to agent
        correlation = correlate_session(session_id, working_directory)

        # Process the event
        result = process_session_start(correlation.agent, session_id)

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("session_start", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "is_new_agent": correlation.is_new,
                "correlation_method": correlation.correlation_method,
                "state": result.new_state,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except Exception as e:
        logger.exception(f"Error handling session_start hook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@hooks_bp.route("/hook/session-end", methods=["POST"])
def hook_session_end():
    """
    Handle Claude Code session end hook.

    Expected payload:
    {
        "session_id": "claude-session-id"
    }

    Returns:
        200: Event processed successfully
        400: Invalid payload
        404: Session not found
        500: Processing error
    """
    start_time = time.time()

    state = get_receiver_state()
    if not state.enabled:
        return jsonify({"status": "ignored", "reason": "hooks_disabled"}), 200

    data, error = _validate_hook_payload(["session_id"])
    if error:
        return jsonify({"status": "error", "message": error}), 400

    session_id = data["session_id"]
    working_directory = data.get("working_directory")

    try:
        correlation = correlate_session(session_id, working_directory)
        result = process_session_end(correlation.agent, session_id)

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("session_end", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "state": result.new_state,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except Exception as e:
        logger.exception(f"Error handling session_end hook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@hooks_bp.route("/hook/user-prompt-submit", methods=["POST"])
def hook_user_prompt_submit():
    """
    Handle Claude Code user prompt submit hook.

    Expected payload:
    {
        "session_id": "claude-session-id"
    }

    Returns:
        200: Event processed successfully
        400: Invalid payload
        500: Processing error
    """
    start_time = time.time()

    state = get_receiver_state()
    if not state.enabled:
        return jsonify({"status": "ignored", "reason": "hooks_disabled"}), 200

    data, error = _validate_hook_payload(["session_id"])
    if error:
        return jsonify({"status": "error", "message": error}), 400

    session_id = data["session_id"]
    working_directory = data.get("working_directory")

    try:
        correlation = correlate_session(session_id, working_directory)
        result = process_user_prompt_submit(correlation.agent, session_id)

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("user_prompt_submit", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "state": result.new_state,
                "state_changed": result.state_changed,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except Exception as e:
        logger.exception(f"Error handling user_prompt_submit hook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@hooks_bp.route("/hook/stop", methods=["POST"])
def hook_stop():
    """
    Handle Claude Code stop (turn complete) hook.

    Expected payload:
    {
        "session_id": "claude-session-id"
    }

    Returns:
        200: Event processed successfully
        400: Invalid payload
        500: Processing error
    """
    start_time = time.time()

    state = get_receiver_state()
    if not state.enabled:
        return jsonify({"status": "ignored", "reason": "hooks_disabled"}), 200

    data, error = _validate_hook_payload(["session_id"])
    if error:
        return jsonify({"status": "error", "message": error}), 400

    session_id = data["session_id"]
    working_directory = data.get("working_directory")

    try:
        correlation = correlate_session(session_id, working_directory)
        result = process_stop(correlation.agent, session_id)

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("stop", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "state": result.new_state,
                "state_changed": result.state_changed,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except Exception as e:
        logger.exception(f"Error handling stop hook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@hooks_bp.route("/hook/notification", methods=["POST"])
def hook_notification():
    """
    Handle Claude Code notification hook.

    Expected payload:
    {
        "session_id": "claude-session-id"
    }

    Returns:
        200: Event processed successfully
        400: Invalid payload
        500: Processing error
    """
    start_time = time.time()

    state = get_receiver_state()
    if not state.enabled:
        return jsonify({"status": "ignored", "reason": "hooks_disabled"}), 200

    data, error = _validate_hook_payload(["session_id"])
    if error:
        return jsonify({"status": "error", "message": error}), 400

    session_id = data["session_id"]
    working_directory = data.get("working_directory")

    try:
        correlation = correlate_session(session_id, working_directory)
        result = process_notification(correlation.agent, session_id)

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("notification", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except Exception as e:
        logger.exception(f"Error handling notification hook: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


@hooks_bp.route("/hook/status", methods=["GET"])
def hook_status():
    """
    Get hook receiver status.

    Returns:
        200: Status information
    """
    state = get_receiver_state()

    # Check if we should fall back to polling
    state.check_fallback()

    last_event_ago = None
    if state.last_event_at:
        elapsed = (datetime.now(timezone.utc) - state.last_event_at).total_seconds()
        if elapsed < 60:
            last_event_ago = f"{int(elapsed)}s ago"
        elif elapsed < 3600:
            last_event_ago = f"{int(elapsed / 60)}m ago"
        else:
            last_event_ago = f"{int(elapsed / 3600)}h ago"

    return jsonify({
        "enabled": state.enabled,
        "mode": state.mode.value,
        "last_event_at": state.last_event_at.isoformat() if state.last_event_at else None,
        "last_event_ago": last_event_ago,
        "last_event_type": state.last_event_type.value if state.last_event_type else None,
        "events_received": state.events_received,
        "polling_interval": state.get_polling_interval(),
        "config": {
            "polling_interval_with_hooks": state.polling_interval_with_hooks,
            "polling_interval_fallback": state.polling_interval_fallback,
            "fallback_timeout": state.fallback_timeout,
        },
    }), 200
