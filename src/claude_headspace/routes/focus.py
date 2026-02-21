"""Focus API endpoint for iTerm2 pane focusing, tmux attach, and agent dismissal."""

import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, jsonify

from ..database import db
from ..models.agent import Agent
from ..services.iterm_focus import (
    AttachResult,
    FocusErrorType,
    FocusResult,
    attach_tmux_session,
    check_tmux_session_exists,
    focus_iterm_by_tty,
    focus_iterm_pane,
)
from ..services.tmux_bridge import get_pane_client_tty, select_pane

logger = logging.getLogger(__name__)

focus_bp = Blueprint("focus", __name__)


def _get_fallback_path(agent: Agent) -> str | None:
    """
    Get fallback path for an agent (project path or working directory).

    Args:
        agent: The Agent model instance

    Returns:
        Path string or None if not available
    """
    if agent.project and agent.project.path:
        return agent.project.path
    return None


def _log_focus_event(
    agent_id: int,
    pane_id: str | None,
    success: bool,
    error_type: str | None,
    latency_ms: int,
    tmux_pane_id: str | None = None,
    method: str | None = None,
) -> None:
    """
    Log a focus attempt event.

    Args:
        agent_id: The agent ID
        pane_id: The iTerm pane ID (if available)
        success: Whether focus succeeded
        error_type: Error type if failed
        latency_ms: Operation latency in milliseconds
        tmux_pane_id: The tmux pane ID (if available)
        method: The focus method used (tmux, iterm, tmux_fallback_iterm)
    """
    outcome = "success" if success else "failure"
    logger.info(
        f"focus_attempted: agent_id={agent_id}, pane_id={pane_id}, "
        f"tmux_pane_id={tmux_pane_id}, method={method}, "
        f"outcome={outcome}, error_type={error_type}, latency_ms={latency_ms}"
    )


def _focus_via_tmux(tmux_pane_id: str, iterm_pane_id: str | None) -> tuple[FocusResult, str]:
    """Focus an agent via tmux pane resolution.

    1. Resolve the tmux pane to a client TTY
    2. Select the correct tmux pane (switch window + pane)
    3. Focus the iTerm window by TTY

    Falls back to iterm_pane_id if TTY resolution fails.

    Args:
        tmux_pane_id: The tmux pane ID (e.g., %29)
        iterm_pane_id: The iTerm pane ID for fallback (may be None)

    Returns:
        Tuple of (FocusResult, method_string)
    """
    # Step 1: Resolve pane to client TTY
    tty_result = get_pane_client_tty(tmux_pane_id)

    if not tty_result.success:
        # TTY resolution failed — fall back to iterm_pane_id if available
        if iterm_pane_id:
            logger.info(
                f"tmux TTY resolution failed for {tmux_pane_id}, "
                f"falling back to iterm_pane_id: {iterm_pane_id}"
            )
            result = focus_iterm_pane(iterm_pane_id)
            return result, "tmux_fallback_iterm"
        else:
            return FocusResult(
                success=False,
                error_type=FocusErrorType.PANE_NOT_FOUND,
                error_message=tty_result.error_message or "Failed to resolve tmux pane TTY.",
                latency_ms=0,
            ), "tmux"

    # Step 2: Select the correct tmux pane (before focusing iTerm)
    select_result = select_pane(tmux_pane_id)
    if not select_result.success:
        logger.warning(f"tmux select-pane failed for {tmux_pane_id}: {select_result.error_message}")
        # Continue anyway — focusing the iTerm window is still useful

    # Step 3: Focus the iTerm window by TTY
    result = focus_iterm_by_tty(tty_result.tty)
    return result, "tmux"


@focus_bp.route("/api/focus/<int:agent_id>", methods=["POST"])
def focus_agent(agent_id: int):
    """
    Trigger iTerm2 focus for a specific agent's terminal session.

    For agents with a tmux_pane_id, resolves the pane's client TTY and
    uses that to find the iTerm window (stable across window close/reopen).
    Falls back to the existing iterm_pane_id path for non-tmux sessions.

    Args:
        agent_id: Database ID of the agent

    Returns:
        200: Focus succeeded
        404: Agent not found
        500: Focus failed (with error details)
    """
    start_time = time.time()

    # Lookup agent
    agent = db.session.get(Agent, agent_id)

    if agent is None:
        _log_focus_event(
            agent_id=agent_id,
            pane_id=None,
            success=False,
            error_type="agent_not_found",
            latency_ms=int((time.time() - start_time) * 1000),
        )
        return jsonify({
            "error": f"Agent with ID {agent_id} not found.",
            "detail": "agent_not_found",
        }), 404

    fallback_path = _get_fallback_path(agent)
    pane_id = agent.iterm_pane_id
    tmux_pane_id = agent.tmux_pane_id

    # Check if agent has any pane ID
    if not pane_id and not tmux_pane_id:
        latency_ms = int((time.time() - start_time) * 1000)
        _log_focus_event(
            agent_id=agent_id,
            pane_id=None,
            success=False,
            error_type="pane_not_found",
            latency_ms=latency_ms,
        )
        return jsonify({
            "error": "This agent does not have a pane ID.",
            "detail": "pane_not_found",
            "fallback_path": fallback_path,
        }), 400

    # Route to appropriate focus method
    if tmux_pane_id:
        result, method = _focus_via_tmux(tmux_pane_id, pane_id)
    else:
        result = focus_iterm_pane(pane_id)
        method = "iterm"

    # Log the event
    _log_focus_event(
        agent_id=agent_id,
        pane_id=pane_id,
        success=result.success,
        error_type=result.error_type.value if result.error_type else None,
        latency_ms=result.latency_ms,
        tmux_pane_id=tmux_pane_id,
        method=method,
    )

    if result.success:
        return jsonify({
            "status": "ok",
            "agent_id": agent_id,
            "pane_id": pane_id,
            "method": method,
        }), 200
    else:
        status_code = 500

        return jsonify({
            "error": result.error_message,
            "detail": result.error_type.value if result.error_type else "unknown",
            "fallback_path": fallback_path,
            "method": method,
        }), status_code


@focus_bp.route("/api/agents/<int:agent_id>/dismiss", methods=["POST"])
def dismiss_agent(agent_id: int):
    """
    Dismiss an agent by marking it as ended.

    Used from the dashboard when an agent's terminal window is no longer
    reachable (closed externally, no pane ID, etc.).

    Args:
        agent_id: Database ID of the agent

    Returns:
        200: Agent dismissed
        404: Agent not found
        409: Agent already ended
    """
    agent = db.session.get(Agent, agent_id)

    if agent is None:
        return jsonify({
            "error": f"Agent {agent_id} not found",
        }), 404

    if agent.ended_at is not None:
        return jsonify({
            "error": "Agent already ended",
        }), 409

    try:
        now = datetime.now(timezone.utc)
        agent.ended_at = now
        agent.last_seen_at = now
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Failed to dismiss agent %s", agent_id)
        return jsonify({"error": "Failed to dismiss agent"}), 500

    logger.warning(
        f"DISMISS_KILL: agent_id={agent_id} uuid={agent.session_uuid} "
        f"tmux_pane={agent.tmux_pane_id} project={agent.project.name if agent.project else 'N/A'}"
    )

    # Broadcast so other dashboard clients also remove the card
    try:
        from ..services.broadcaster import get_broadcaster
        get_broadcaster().broadcast("session_ended", {
            "agent_id": agent_id,
            "reason": "dismissed",
            "timestamp": now.isoformat(),
        })
    except Exception as e:
        logger.warning(f"Dismiss broadcast failed: {e}")

    return jsonify({
        "status": "ok",
        "agent_id": agent_id,
    }), 200


def _log_attach_event(
    agent_id: int,
    tmux_session: str | None,
    success: bool,
    error_type: str | None,
    latency_ms: int,
    method: str | None = None,
) -> None:
    """Log a tmux attach attempt event."""
    outcome = "success" if success else "failure"
    logger.info(
        f"attach_attempted: agent_id={agent_id}, tmux_session={tmux_session}, "
        f"method={method}, outcome={outcome}, error_type={error_type}, "
        f"latency_ms={latency_ms}"
    )


@focus_bp.route("/api/agents/<int:agent_id>/attach", methods=["POST"])
def attach_agent(agent_id: int):
    """
    Attach to an agent's tmux session via iTerm2.

    Opens a new iTerm2 tab running `tmux attach -t <session_name>`,
    or focuses an existing tab if one is already attached.

    Args:
        agent_id: Database ID of the agent

    Returns:
        200: Attach succeeded
        400: Agent has no tmux session or session not found
        404: Agent not found
        500: Attach failed (iTerm2 error)
    """
    start_time = time.time()

    agent = db.session.get(Agent, agent_id)

    if agent is None:
        _log_attach_event(
            agent_id=agent_id,
            tmux_session=None,
            success=False,
            error_type="agent_not_found",
            latency_ms=int((time.time() - start_time) * 1000),
        )
        return jsonify({
            "error": f"Agent with ID {agent_id} not found.",
            "detail": "agent_not_found",
        }), 404

    tmux_session_name = agent.tmux_session
    if not tmux_session_name:
        _log_attach_event(
            agent_id=agent_id,
            tmux_session=None,
            success=False,
            error_type="no_tmux_session",
            latency_ms=int((time.time() - start_time) * 1000),
        )
        return jsonify({
            "error": "This agent does not have a tmux session.",
            "detail": "no_tmux_session",
        }), 400

    # Verify the tmux session still exists
    if not check_tmux_session_exists(tmux_session_name):
        _log_attach_event(
            agent_id=agent_id,
            tmux_session=tmux_session_name,
            success=False,
            error_type="session_not_found",
            latency_ms=int((time.time() - start_time) * 1000),
        )
        return jsonify({
            "error": f"Tmux session '{tmux_session_name}' no longer exists.",
            "detail": "session_not_found",
        }), 400

    result = attach_tmux_session(tmux_session_name)

    _log_attach_event(
        agent_id=agent_id,
        tmux_session=tmux_session_name,
        success=result.success,
        error_type=result.error_type.value if result.error_type else None,
        latency_ms=result.latency_ms,
        method=result.method,
    )

    if result.success:
        return jsonify({
            "status": "ok",
            "agent_id": agent_id,
            "tmux_session": tmux_session_name,
            "method": result.method,
        }), 200
    else:
        return jsonify({
            "error": result.error_message,
            "detail": result.error_type.value if result.error_type else "unknown",
        }), 500
