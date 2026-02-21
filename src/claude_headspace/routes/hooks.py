"""Hook receiver API endpoints for Claude Code integration."""

import logging
import os
import threading
import time
from collections import defaultdict
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, jsonify, request

from ..database import db
from ..services.hook_receiver import (
    HookMode,
    get_receiver_state,
    process_notification,
    process_permission_request,
    process_post_tool_use,
    process_pre_tool_use,
    process_session_end,
    process_session_start,
    process_stop,
    process_user_prompt_submit,
)
from ..services.notification_service import get_notification_service
from ..services.session_correlator import correlate_session

logger = logging.getLogger(__name__)

hooks_bp = Blueprint("hooks", __name__)


# --- SRV-C7: IP-based rate limiting for hook endpoints ---

_rate_limit_lock = threading.Lock()
_rate_limit_counters: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_MAX_REQUESTS = 60  # per window
RATE_LIMIT_WINDOW_SECONDS = 60  # sliding window


def _check_rate_limit(ip: str) -> bool:
    """Check if an IP has exceeded the rate limit. Returns True if allowed."""
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    with _rate_limit_lock:
        timestamps = _rate_limit_counters[ip]
        # Prune old entries
        _rate_limit_counters[ip] = [t for t in timestamps if t > cutoff]
        # Clean up empty keys to prevent unbounded dict growth
        if not _rate_limit_counters[ip]:
            del _rate_limit_counters[ip]
            return True
        if len(_rate_limit_counters[ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        _rate_limit_counters[ip].append(now)
        return True


def rate_limited(f):
    """Decorator that applies IP-based rate limiting to hook endpoints."""
    @wraps(f)
    def decorated(*args, **kwargs):
        ip = request.remote_addr or "unknown"
        if not _check_rate_limit(ip):
            logger.warning(f"Rate limit exceeded for IP {ip} on {request.path}")
            return jsonify({
                "status": "error",
                "message": "Rate limit exceeded. Max 60 requests per minute.",
            }), 429
        return f(*args, **kwargs)
    return decorated


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


def _backfill_tmux_pane(agent, tmux_pane: str | None, tmux_session: str | None = None) -> None:
    """Store tmux_pane_id and tmux_session on agent if not yet set (late discovery).

    Flushes (not commits) after setting values so downstream code
    within the same request can see them before the final commit
    in the hook processor.

    Also registers the agent with the availability tracker so health
    checks begin immediately.
    """
    dirty = False
    pane_is_new = False
    if tmux_pane and not agent.tmux_pane_id:
        agent.tmux_pane_id = tmux_pane
        dirty = True
        pane_is_new = True
    if tmux_session and not agent.tmux_session:
        agent.tmux_session = tmux_session
        dirty = True
    if not dirty:
        return
    db.session.flush()
    if pane_is_new:
        try:
            from flask import current_app
            availability = current_app.extensions.get("commander_availability")
            if availability:
                availability.register_agent(agent.id, tmux_pane)
        except RuntimeError:
            logger.debug("No app context for commander_availability")


@hooks_bp.route("/hook/session-start", methods=["POST"])
@rate_limited
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
    headspace_session_id = data.get("headspace_session_id")
    transcript_path = data.get("transcript_path")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")
    persona_slug = data.get("persona_slug")
    previous_agent_id = data.get("previous_agent_id")

    # SRV-C7: Validate working_directory is a real path
    if working_directory and not os.path.isdir(working_directory):
        logger.warning(f"session-start: invalid working_directory: {working_directory}")
        return jsonify({
            "status": "error",
            "message": "working_directory is not a valid directory",
        }), 400

    try:
        # Correlate session to agent
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)

        # Process the event
        result = process_session_start(
            correlation.agent, session_id, transcript_path=transcript_path,
            tmux_pane_id=tmux_pane, tmux_session=tmux_session,
            persona_slug=persona_slug, previous_agent_id=previous_agent_id,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("session_start", session_id, latency_ms)

        if result.success:
            if correlation.is_new:
                try:
                    from ..services.broadcaster import get_broadcaster
                    get_broadcaster().broadcast("session_created", {
                        "agent_id": result.agent_id,
                        "project_id": correlation.agent.project_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as e:
                    logger.warning(f"Session created broadcast failed: {e}")

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

    except ValueError as e:
        logger.warning(f"Session correlation failed for session_start: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling session_start hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


@hooks_bp.route("/hook/session-end", methods=["POST"])
@rate_limited
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
    headspace_session_id = data.get("headspace_session_id")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")

    try:
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)
        _backfill_tmux_pane(correlation.agent, tmux_pane, tmux_session)
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

    except ValueError as e:
        logger.warning(f"Session correlation failed for session_end: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling session_end hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


@hooks_bp.route("/hook/user-prompt-submit", methods=["POST"])
@rate_limited
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
    headspace_session_id = data.get("headspace_session_id")
    prompt_text = data.get("prompt")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")

    try:
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)
        _backfill_tmux_pane(correlation.agent, tmux_pane, tmux_session)
        result = process_user_prompt_submit(correlation.agent, session_id, prompt_text=prompt_text)

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

    except ValueError as e:
        logger.warning(f"Session correlation failed for user_prompt_submit: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling user_prompt_submit hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


@hooks_bp.route("/hook/stop", methods=["POST"])
@rate_limited
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
    headspace_session_id = data.get("headspace_session_id")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")

    try:
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)
        _backfill_tmux_pane(correlation.agent, tmux_pane, tmux_session)
        result = process_stop(correlation.agent, session_id)

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("stop", session_id, latency_ms)

        if result.success:
            # The stop hook fires at end-of-turn only, so this indicates
            # the agent has finished its current turn and the command is complete.

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

    except ValueError as e:
        logger.warning(f"Session correlation failed for stop: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling stop hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


@hooks_bp.route("/hook/notification", methods=["POST"])
@rate_limited
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
    headspace_session_id = data.get("headspace_session_id")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")

    message = data.get("message")
    title = data.get("title")
    notification_type = data.get("notification_type")

    try:
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)
        _backfill_tmux_pane(correlation.agent, tmux_pane, tmux_session)
        result = process_notification(
            correlation.agent,
            session_id,
            message=message,
            title=title,
            notification_type=notification_type,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("notification", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "state_changed": result.state_changed,
                "new_state": result.new_state,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except ValueError as e:
        logger.warning(f"Session correlation failed for notification: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling notification hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


@hooks_bp.route("/hook/post-tool-use", methods=["POST"])
@rate_limited
def hook_post_tool_use():
    """
    Handle Claude Code PostToolUse hook.

    Fires after a tool completes. When the agent is in AWAITING_INPUT state,
    this signals that the user has responded and the agent is resuming.

    Expected payload:
    {
        "session_id": "claude-session-id",
        "tool_name": "tool-name",         // optional
        "transcript_path": "/path/to/transcript.jsonl"  // optional
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
    headspace_session_id = data.get("headspace_session_id")
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")

    try:
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)
        _backfill_tmux_pane(correlation.agent, tmux_pane, tmux_session)

        # Backfill transcript_path if provided and not yet set
        transcript_path = data.get("transcript_path")
        if transcript_path and not correlation.agent.transcript_path:
            correlation.agent.transcript_path = transcript_path

        result = process_post_tool_use(
            correlation.agent, session_id, tool_name=tool_name,
            tool_input=tool_input,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("post_tool_use", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "state_changed": result.state_changed,
                "new_state": result.new_state,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except ValueError as e:
        logger.warning(f"Session correlation failed for post_tool_use: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling post_tool_use hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


@hooks_bp.route("/hook/pre-tool-use", methods=["POST"])
@rate_limited
def hook_pre_tool_use():
    """
    Handle Claude Code PreToolUse hook.

    Fires before a tool executes. When the tool is AskUserQuestion, this
    signals AWAITING_INPUT immediately (faster than the Notification hook).

    Expected payload:
    {
        "session_id": "claude-session-id",
        "tool_name": "AskUserQuestion"  // optional
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
    headspace_session_id = data.get("headspace_session_id")
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")

    try:
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)
        _backfill_tmux_pane(correlation.agent, tmux_pane, tmux_session)
        result = process_pre_tool_use(
            correlation.agent, session_id, tool_name=tool_name, tool_input=tool_input
        )

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("pre_tool_use", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "state_changed": result.state_changed,
                "new_state": result.new_state,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except ValueError as e:
        logger.warning(f"Session correlation failed for pre_tool_use: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling pre_tool_use hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


@hooks_bp.route("/hook/permission-request", methods=["POST"])
@rate_limited
def hook_permission_request():
    """
    Handle Claude Code PermissionRequest hook.

    Fires when a permission dialog is shown to the user. Signals
    AWAITING_INPUT immediately (faster than the Notification hook).

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
    headspace_session_id = data.get("headspace_session_id")
    tool_name = data.get("tool_name")
    tool_input = data.get("tool_input")
    tmux_pane = data.get("tmux_pane")
    tmux_session = data.get("tmux_session")

    try:
        correlation = correlate_session(session_id, working_directory, headspace_session_id, tmux_pane_id=tmux_pane)
        _backfill_tmux_pane(correlation.agent, tmux_pane, tmux_session)
        result = process_permission_request(
            correlation.agent, session_id, tool_name=tool_name, tool_input=tool_input
        )

        latency_ms = int((time.time() - start_time) * 1000)
        _log_hook_event("permission_request", session_id, latency_ms)

        if result.success:
            return jsonify({
                "status": "ok",
                "agent_id": result.agent_id,
                "state_changed": result.state_changed,
                "new_state": result.new_state,
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": result.error_message,
            }), 500

    except ValueError as e:
        logger.warning(f"Session correlation failed for permission_request: {e}")
        return jsonify({"status": "dropped", "message": "Session correlation failed"}), 404

    except Exception:
        logger.exception("Error handling permission_request hook")
        return jsonify({"status": "error", "message": "Internal processing error"}), 500


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
