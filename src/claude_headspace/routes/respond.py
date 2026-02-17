"""Respond API endpoint for sending text input to Claude Code sessions."""

import logging
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request

from ..database import db
from ..models.agent import Agent
from ..models.task import TaskState
from ..models.turn import Turn, TurnActor, TurnIntent
from ..services import tmux_bridge
from ..services.card_state import broadcast_card_refresh
from ..services.tmux_bridge import TmuxBridgeErrorType

logger = logging.getLogger(__name__)

respond_bp = Blueprint("respond", __name__)


def _get_commander_availability():
    """Get the commander availability service from app extensions."""
    return current_app.extensions.get("commander_availability")


def _get_tmux_bridge():
    """Get the tmux bridge service from app extensions."""
    return current_app.extensions.get("tmux_bridge")


def _count_options(task) -> int:
    """Count the number of options in the most recent QUESTION turn's tool_input."""
    if not task or not task.turns:
        return 0
    for turn in reversed(task.turns):
        if turn.actor == TurnActor.AGENT and turn.intent == TurnIntent.QUESTION:
            if turn.tool_input and isinstance(turn.tool_input, dict):
                questions = turn.tool_input.get("questions")
                if questions and isinstance(questions, list) and len(questions) > 0:
                    options = questions[0].get("options", [])
                    return len(options) if isinstance(options, list) else 0
            return 0
    return 0


def _build_multi_select_keys(answers: list) -> list[str]:
    """Build tmux key sequence for multi-tab AskUserQuestion answers.

    Each answer navigates one question tab. Single-select uses Down+Enter
    (auto-advances to next tab). Multi-select uses Space toggles then Enter.
    After all tabs, a final Enter confirms the Submit button.

    Args:
        answers: List of dicts, each with 'option_index' (int) or 'option_indices' (list[int]).

    Returns:
        List of tmux key names.
    """
    keys: list[str] = []
    for ans in answers:
        if "option_indices" in ans and isinstance(ans["option_indices"], list):
            # Multi-select: navigate and toggle each option with Space
            indices = sorted(ans["option_indices"])
            current_pos = 0
            for opt_idx in indices:
                delta = opt_idx - current_pos
                keys.extend(["Down"] * delta)
                keys.append("Space")
                current_pos = opt_idx
            keys.append("Enter")
        else:
            # Single-select: Down × N, then Enter (auto-advances)
            option_index = ans.get("option_index", 0)
            keys.extend(["Down"] * option_index)
            keys.append("Enter")
    # Final Enter to confirm the Submit tab
    keys.append("Enter")
    return keys


def _tmux_error_response(result, agent_id):
    """Build error response for tmux bridge failures."""
    if result.error_type == TmuxBridgeErrorType.PANE_NOT_FOUND:
        status_code = 503
    elif result.error_type == TmuxBridgeErrorType.TMUX_NOT_INSTALLED:
        status_code = 503
    elif result.error_type == TmuxBridgeErrorType.TIMEOUT:
        status_code = 502
    else:
        status_code = 502

    logger.warning(
        f"respond_failed: agent_id={agent_id}, error={result.error_type}, "
        f"message={result.error_message}, latency_ms={result.latency_ms}"
    )

    return jsonify({
        "status": "error",
        "error_type": result.error_type.value if result.error_type else "unknown",
        "message": result.error_message,
        "latency_ms": result.latency_ms,
    }), status_code


@respond_bp.route("/api/respond/<int:agent_id>", methods=["POST"])
def respond_to_agent(agent_id: int):
    """Send a response to a Claude Code session via tmux.

    Supports three modes:
    - text (default/legacy): Send literal text + Enter
    - select: Navigate AskUserQuestion options with arrow keys
    - other: Select "Other" option then type custom text

    Args:
        agent_id: Database ID of the agent

    Request body:
        Text mode:   {"text": "response text"} or {"mode": "text", "text": "..."}
        Select mode: {"mode": "select", "option_index": 0}
        Other mode:  {"mode": "other", "text": "custom input"}

    Returns:
        200: Response sent successfully
        400: Invalid request
        404: Agent not found
        409: Agent not in AWAITING_INPUT state
        502/503: tmux send failed
    """
    start_time = time.time()

    # Parse request body
    data = request.get_json(silent=True) or {}
    mode = data.get("mode", "text")

    if mode not in ("text", "select", "other", "multi_select"):
        return jsonify({
            "status": "error",
            "error_type": "invalid_mode",
            "message": f"Invalid mode '{mode}'. Must be 'text', 'select', 'other', or 'multi_select'.",
        }), 400

    # Validate mode-specific parameters
    if mode == "text":
        text = data.get("text", "").strip()
        if not text:
            return jsonify({
                "status": "error",
                "error_type": "missing_text",
                "message": "Response text is required.",
            }), 400
    elif mode == "select":
        option_index = data.get("option_index")
        if option_index is None or not isinstance(option_index, int) or option_index < 0:
            return jsonify({
                "status": "error",
                "error_type": "invalid_option_index",
                "message": "option_index must be a non-negative integer.",
            }), 400
    elif mode == "other":
        text = data.get("text", "").strip()
        if not text:
            return jsonify({
                "status": "error",
                "error_type": "missing_text",
                "message": "Text is required for 'other' mode.",
            }), 400
    elif mode == "multi_select":
        answers = data.get("answers")
        if not answers or not isinstance(answers, list) or len(answers) == 0:
            return jsonify({
                "status": "error",
                "error_type": "invalid_answers",
                "message": "answers must be a non-empty array for 'multi_select' mode.",
            }), 400
        for idx, ans in enumerate(answers):
            if not isinstance(ans, dict):
                return jsonify({
                    "status": "error",
                    "error_type": "invalid_answers",
                    "message": f"answers[{idx}] must be an object.",
                }), 400
            has_single = "option_index" in ans and isinstance(ans["option_index"], int) and ans["option_index"] >= 0
            has_multi = "option_indices" in ans and isinstance(ans["option_indices"], list) and len(ans["option_indices"]) > 0
            if not has_single and not has_multi:
                return jsonify({
                    "status": "error",
                    "error_type": "invalid_answers",
                    "message": f"answers[{idx}] must have option_index (int >= 0) or option_indices (non-empty list).",
                }), 400

    # Lookup agent with row lock to prevent concurrent state mutations (SRV-C1)
    agent = db.session.get(Agent, agent_id, with_for_update=True)
    if agent is None:
        return jsonify({
            "status": "error",
            "error_type": "agent_not_found",
            "message": f"Agent with ID {agent_id} not found.",
        }), 404

    # Check agent has a tmux pane ID
    if not agent.tmux_pane_id:
        return jsonify({
            "status": "error",
            "error_type": "no_pane_id",
            "message": "Agent has no tmux pane ID — cannot send input.",
        }), 400

    # Check agent is in AWAITING_INPUT state
    current_task = agent.get_current_task()
    if current_task is None or current_task.state != TaskState.AWAITING_INPUT:
        actual_state = current_task.state.value if current_task else "no_task"
        return jsonify({
            "status": "error",
            "error_type": "wrong_state",
            "message": f"Agent is not awaiting input (current state: {actual_state}).",
        }), 409

    # Get tmux bridge config
    config = current_app.config.get("APP_CONFIG", {})
    bridge_config = config.get("tmux_bridge", {})
    subprocess_timeout = bridge_config.get("subprocess_timeout", 5)
    text_enter_delay_ms = bridge_config.get("text_enter_delay_ms", 120)
    sequential_delay_ms = bridge_config.get("sequential_delay_ms", 150)
    select_other_delay_ms = bridge_config.get("select_other_delay_ms", 500)

    # Execute the appropriate tmux action based on mode
    if mode == "text":
        result = tmux_bridge.send_text(
            pane_id=agent.tmux_pane_id,
            text=text,
            timeout=subprocess_timeout,
            text_enter_delay_ms=text_enter_delay_ms,
        )
        record_text = text

    elif mode == "select":
        # Build key sequence: Down × option_index, then Enter
        keys = ["Down"] * option_index + ["Enter"]
        result = tmux_bridge.send_keys(
            agent.tmux_pane_id,
            *keys,
            timeout=subprocess_timeout,
            sequential_delay_ms=sequential_delay_ms,
            verify_enter=True,
        )
        option_label = data.get("option_label", "").strip()
        record_text = option_label if option_label else f"[selected option {option_index}]"

    elif mode == "other":
        # Navigate to "Other" (last item) then type custom text
        num_options = _count_options(current_task)
        # "Other" is always appended after all options by AskUserQuestion
        keys = ["Down"] * num_options + ["Enter"]
        result = tmux_bridge.send_keys(
            agent.tmux_pane_id,
            *keys,
            timeout=subprocess_timeout,
            sequential_delay_ms=sequential_delay_ms,
            verify_enter=True,
        )
        if result.success:
            # Wait for the "Other" text input to appear
            time.sleep(select_other_delay_ms / 1000.0)
            # Type the custom text
            result = tmux_bridge.send_text(
                pane_id=agent.tmux_pane_id,
                text=text,
                timeout=subprocess_timeout,
                text_enter_delay_ms=text_enter_delay_ms,
            )
        record_text = text

    elif mode == "multi_select":
        keys = _build_multi_select_keys(answers)
        result = tmux_bridge.send_keys(
            agent.tmux_pane_id,
            *keys,
            timeout=subprocess_timeout,
            sequential_delay_ms=sequential_delay_ms,
            verify_enter=True,
        )
        # Build descriptive summary for the turn record
        parts = []
        for i, ans in enumerate(answers):
            if "option_indices" in ans and isinstance(ans["option_indices"], list):
                parts.append(f"Q{i+1}: options {ans['option_indices']}")
            else:
                parts.append(f"Q{i+1}: option {ans.get('option_index', 0)}")
        record_text = "[multi-select: " + ", ".join(parts) + "]"

    if not result.success:
        return _tmux_error_response(result, agent_id)

    # Success: create Turn record and transition state
    try:
        # Find the most recent QUESTION turn for answer linking
        answered_turn_id = None
        if current_task.turns:
            for t in reversed(current_task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    answered_turn_id = t.id
                    break

        from ..services.hook_extractors import mark_question_answered
        mark_question_answered(current_task)

        turn = Turn(
            task_id=current_task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.ANSWER,
            text=record_text,
            answered_by_turn_id=answered_turn_id,
        )
        db.session.add(turn)

        from ..services.state_machine import validate_transition
        from ..models.turn import TurnIntent as _TurnIntent
        _vr = validate_transition(current_task.state, TurnActor.USER, _TurnIntent.ANSWER)
        if _vr.valid:
            current_task.state = _vr.to_state
        else:
            # Fallback: force PROCESSING (respond always means user answered)
            logger.warning(f"respond: invalid transition {current_task.state.value} -> PROCESSING, forcing")
            current_task.state = TaskState.PROCESSING
        agent.last_seen_at = datetime.now(timezone.utc)

        # Clear the awaiting tool tracker so subsequent hooks (stop, post_tool_use)
        # don't incorrectly preserve AWAITING_INPUT state
        from ..services.hook_agent_state import get_agent_hook_state
        get_agent_hook_state().clear_awaiting_tool(agent_id)

        db.session.commit()

        # Flag this agent so the upcoming user_prompt_submit hook is skipped
        # (the respond handler owns the turn creation and state transition).
        # Set AFTER commit so the flag is never orphaned if the commit fails.
        from ..services.hook_agent_state import get_agent_hook_state
        get_agent_hook_state().set_respond_pending(agent.id)

        broadcast_card_refresh(agent, "respond")
        _broadcast_state_change(agent, record_text, turn_id=turn.id)

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(
            f"respond_success: agent_id={agent_id}, mode={mode}, "
            f"text_length={len(record_text)}, latency_ms={latency_ms}"
        )

        return jsonify({
            "status": "ok",
            "agent_id": agent_id,
            "mode": mode,
            "new_state": TaskState.PROCESSING.value,
            "latency_ms": latency_ms,
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error recording response for agent {agent_id}: {e}")
        return jsonify({
            "status": "error",
            "error_type": "internal_error",
            "message": "Response was sent but recording failed. State will self-correct.",
        }), 500


@respond_bp.route("/api/respond/<int:agent_id>/availability", methods=["GET"])
def check_availability(agent_id: int):
    """Check tmux pane availability for an agent.

    Args:
        agent_id: Database ID of the agent

    Returns:
        200: Availability status
        404: Agent not found
    """
    agent = db.session.get(Agent, agent_id)
    if agent is None:
        return jsonify({
            "status": "error",
            "error_type": "agent_not_found",
            "message": f"Agent with ID {agent_id} not found.",
        }), 404

    availability = _get_commander_availability()
    if availability and agent.tmux_pane_id:
        available = availability.check_agent(agent_id, agent.tmux_pane_id)
    else:
        available = False

    return jsonify({
        "status": "ok",
        "agent_id": agent_id,
        "commander_available": available,
    }), 200


def _broadcast_state_change(agent: Agent, response_text: str, turn_id: int | None = None) -> None:
    """Broadcast state change and turn creation after response."""
    try:
        from ..services.broadcaster import get_broadcaster

        broadcaster = get_broadcaster()
        broadcaster.broadcast("state_changed", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "event_type": "respond",
            "new_state": "PROCESSING",
            "message": "User responded via dashboard",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        _task = agent.get_current_task()
        broadcaster.broadcast("turn_created", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "text": response_text,
            "actor": "user",
            "intent": "answer",
            "task_id": _task.id if _task else None,
            "task_instruction": _task.instruction if _task else None,
            "turn_id": turn_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"Response broadcast failed: {e}")
