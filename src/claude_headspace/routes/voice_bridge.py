"""Voice bridge API endpoints for voice-driven interaction with agents."""

import logging
import os
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, request, send_from_directory

from ..database import db
from ..models.agent import Agent
from ..models.task import Task, TaskState
from ..models.turn import Turn, TurnActor, TurnIntent
from ..services import tmux_bridge
from ..services.card_state import broadcast_card_refresh

logger = logging.getLogger(__name__)

voice_bridge_bp = Blueprint("voice_bridge", __name__)


def _get_voice_formatter():
    return current_app.extensions.get("voice_formatter")


def _get_voice_auth():
    return current_app.extensions.get("voice_auth")


def _voice_error(error_type: str, suggestion: str, status_code: int = 400):
    """Build a voice-friendly error response."""
    formatter = _get_voice_formatter()
    if formatter:
        body = {"voice": formatter.format_error(error_type, suggestion)}
    else:
        body = {"voice": {"status_line": error_type, "results": [], "next_action": suggestion}}
    body["error"] = error_type
    return jsonify(body), status_code


def _get_active_agents():
    """Get all active agents (not ended, recently seen)."""
    config = current_app.config.get("APP_CONFIG", {})
    timeout_minutes = config.get("dashboard", {}).get("active_timeout_minutes", 5)
    cutoff = datetime.now(timezone.utc).timestamp() - (timeout_minutes * 60)

    agents = (
        db.session.query(Agent)
        .filter(
            Agent.ended_at.is_(None),
        )
        .all()
    )
    # Filter by last_seen_at in Python (avoids timezone arithmetic issues in SQL)
    return [a for a in agents if a.last_seen_at and a.last_seen_at.timestamp() > cutoff]


def _agent_to_voice_dict(agent: Agent) -> dict:
    """Convert an agent to a voice-friendly dict."""
    current_task = agent.get_current_task()
    state = current_task.state.value if current_task else "idle"
    awaiting = current_task is not None and current_task.state == TaskState.AWAITING_INPUT

    # Get task summary
    summary = None
    if current_task:
        summary = current_task.completion_summary or current_task.instruction
        if not summary and current_task.turns:
            for t in reversed(current_task.turns):
                if t.summary:
                    summary = t.summary
                    break
                if t.text:
                    summary = t.text[:100]
                    break

    # Time since last activity
    if agent.last_seen_at:
        elapsed = (datetime.now(timezone.utc) - agent.last_seen_at).total_seconds()
        if elapsed < 60:
            ago = f"{int(elapsed)}s ago"
        elif elapsed < 3600:
            ago = f"{int(elapsed / 60)}m ago"
        else:
            ago = f"{int(elapsed / 3600)}h ago"
    else:
        ago = "unknown"

    return {
        "agent_id": agent.id,
        "name": agent.name,
        "project": agent.project.name if agent.project else "unknown",
        "state": state,
        "awaiting_input": awaiting,
        "summary": summary,
        "last_activity_ago": ago,
    }


@voice_bridge_bp.route("/voice")
def serve_voice_app():
    """Serve the voice bridge PWA entry point."""
    static_dir = os.path.join(current_app.root_path, "..", "..", "static", "voice")
    static_dir = os.path.normpath(static_dir)
    return send_from_directory(static_dir, "voice.html")


def _is_local_or_lan(addr: str) -> bool:
    """Check if an address is localhost or a private/LAN IP."""
    if addr in ("127.0.0.1", "::1", "localhost"):
        return True
    # Private network ranges (RFC 1918)
    if addr.startswith("10."):
        return True
    if addr.startswith("192.168."):
        return True
    if addr.startswith("172."):
        parts = addr.split(".")
        if len(parts) >= 2:
            try:
                second = int(parts[1])
                if 16 <= second <= 31:
                    return True
            except ValueError:
                pass
    return False


@voice_bridge_bp.before_request
def voice_auth_check():
    """Apply token authentication to API endpoints.

    Bypasses auth for:
    - The /voice page itself
    - Any request from localhost or LAN IPs (same trust boundary as dashboard)
    """
    if request.path == "/voice":
        return None
    # Bypass auth for localhost and LAN requests
    remote = request.remote_addr or ""
    if _is_local_or_lan(remote):
        return None
    auth = _get_voice_auth()
    if auth:
        return auth.authenticate()
    return None


@voice_bridge_bp.route("/api/voice/sessions", methods=["GET"])
def list_sessions():
    """List active agents with voice-friendly status (FR5)."""
    start_time = time.time()
    verbosity = request.args.get("verbosity")
    formatter = _get_voice_formatter()

    agents = _get_active_agents()
    agent_dicts = [_agent_to_voice_dict(a) for a in agents]

    if formatter:
        voice = formatter.format_sessions(agent_dicts, verbosity=verbosity)
    else:
        voice = {"status_line": f"{len(agents)} agents active.", "results": [], "next_action": "none"}

    config = current_app.config.get("APP_CONFIG", {})
    auto_target = config.get("voice_bridge", {}).get("auto_target", False)

    latency_ms = int((time.time() - start_time) * 1000)
    return jsonify({
        "voice": voice,
        "agents": agent_dicts,
        "settings": {"auto_target": auto_target},
        "latency_ms": latency_ms,
    }), 200


@voice_bridge_bp.route("/api/voice/command", methods=["POST"])
def voice_command():
    """Submit a voice command to an agent (FR4)."""
    start_time = time.time()
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    agent_id = data.get("agent_id")

    if not text:
        return _voice_error("No command text provided.", "Say your command and try again.")

    formatter = _get_voice_formatter()

    # Resolve target agent
    if agent_id:
        agent = db.session.get(Agent, agent_id)
        if not agent:
            return _voice_error("Agent not found.", "Check the agent ID and try again.", 404)
    else:
        # Auto-target: find the single agent awaiting input (if enabled)
        config = current_app.config.get("APP_CONFIG", {})
        auto_target = config.get("voice_bridge", {}).get("auto_target", False)
        if not auto_target:
            return _voice_error(
                "No agent specified.",
                "Select an agent first, then send your command.",
                400,
            )
        active = _get_active_agents()
        awaiting = [a for a in active if a.get_current_task() and a.get_current_task().state == TaskState.AWAITING_INPUT]
        if len(awaiting) == 0:
            # No agents awaiting input — return status summary
            agent_dicts = [_agent_to_voice_dict(a) for a in active]
            if formatter:
                voice = formatter.format_error(
                    "No agents are waiting for input.",
                    "Check agent status for what they're working on.",
                )
                voice["results"] = [f"{d['project']}: {d['state']}" for d in agent_dicts[:3]]
            else:
                voice = {"status_line": "No agents awaiting input.", "results": [], "next_action": "none"}
            return jsonify({"voice": voice}), 409
        elif len(awaiting) > 1:
            names = [a.name for a in awaiting]
            return _voice_error(
                f"Multiple agents need input: {', '.join(names)}.",
                "Specify which agent by including agent_id.",
                409,
            )
        agent = awaiting[0]

    # Determine agent state
    current_task = agent.get_current_task()
    current_state = current_task.state if current_task else None
    is_answering = current_state == TaskState.AWAITING_INPUT
    is_idle = current_state in (None, TaskState.IDLE, TaskState.COMPLETE)

    # Reject if agent is busy (PROCESSING or COMMANDED)
    if not is_answering and not is_idle:
        state_str = current_state.value if current_state else "idle"
        return _voice_error(
            f"Agent is {state_str}, not ready for input.",
            "Try again in a moment when the agent finishes processing.",
            409,
        )

    # Check tmux pane
    if not agent.tmux_pane_id:
        return _voice_error(
            "Cannot reach this agent.",
            "The agent has no terminal connection for input.",
            503,
        )

    # Send via tmux bridge
    config = current_app.config.get("APP_CONFIG", {})
    bridge_config = config.get("tmux_bridge", {})
    subprocess_timeout = bridge_config.get("subprocess_timeout", 5)
    text_enter_delay_ms = bridge_config.get("text_enter_delay_ms", 100)

    result = tmux_bridge.send_text(
        pane_id=agent.tmux_pane_id,
        text=text,
        timeout=subprocess_timeout,
        text_enter_delay_ms=text_enter_delay_ms,
    )

    if not result.success:
        error_msg = result.error_message or "Send failed"
        if formatter:
            voice = formatter.format_command_result(agent.name, False, error_msg)
        else:
            voice = {"status_line": f"Command failed: {error_msg}", "results": [], "next_action": "Try again."}
        return jsonify({"voice": voice, "error": "send_failed"}), 502

    if is_idle:
        # IDLE/COMPLETE: just send via tmux — the hook receiver will handle
        # task creation + turn recording when Claude Code's hooks fire.
        # Do NOT create a task here (avoids duplication with hook receiver).
        agent.last_seen_at = datetime.now(timezone.utc)
        db.session.commit()

        latency_ms = int((time.time() - start_time) * 1000)
        if formatter:
            voice = formatter.format_command_result(agent.name, True)
        else:
            voice = {"status_line": f"Command sent to {agent.name}.", "results": [], "next_action": "none"}

        return jsonify({
            "voice": voice,
            "agent_id": agent.id,
            "new_state": "idle",
            "latency_ms": latency_ms,
        }), 200

    # AWAITING_INPUT path: create ANSWER turn and transition state
    try:
        answered_turn_id = None
        if current_task.turns:
            for t in reversed(current_task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    answered_turn_id = t.id
                    break

        turn = Turn(
            task_id=current_task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.ANSWER,
            text=text,
            answered_by_turn_id=answered_turn_id,
        )
        db.session.add(turn)

        from ..services.state_machine import validate_transition
        vr = validate_transition(current_task.state, TurnActor.USER, TurnIntent.ANSWER)
        if vr.valid:
            current_task.state = vr.to_state
        else:
            # Intentional fallback: respond always means user answered, so force
            # PROCESSING even if the state machine rejects the transition (e.g.
            # if the task was concurrently modified by another hook).
            logger.warning(
                f"voice_bridge: invalid transition {current_task.state.value} -> PROCESSING, "
                f"forcing (agent_id={agent.id}, task_id={current_task.id})"
            )
            current_task.state = TaskState.PROCESSING
        agent.last_seen_at = datetime.now(timezone.utc)

        from ..services.hook_receiver import _awaiting_tool_for_agent
        _awaiting_tool_for_agent.pop(agent.id, None)

        db.session.commit()

        # Flag respond-pending AFTER commit to prevent duplicate turn from hook.
        # Set after commit so the flag is never orphaned if the commit fails.
        from ..services.hook_receiver import _respond_pending_for_agent
        _respond_pending_for_agent[agent.id] = time.time()

        broadcast_card_refresh(agent, "voice_command")

        latency_ms = int((time.time() - start_time) * 1000)
        if formatter:
            voice = formatter.format_command_result(agent.name, True)
        else:
            voice = {"status_line": f"Command sent to {agent.name}.", "results": [], "next_action": "none"}

        return jsonify({
            "voice": voice,
            "agent_id": agent.id,
            "new_state": current_task.state.value,
            "latency_ms": latency_ms,
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error recording voice command for agent {agent.id}: {e}")
        return _voice_error(
            "Command was sent but recording failed.",
            "The agent received your input. State will self-correct.",
            500,
        )


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/output", methods=["GET"])
def agent_output(agent_id: int):
    """Get recent agent output (FR6)."""
    start_time = time.time()
    verbosity = request.args.get("verbosity")
    limit = request.args.get("limit", 5, type=int)
    formatter = _get_voice_formatter()

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return _voice_error("Agent not found.", "Check the agent ID and try again.", 404)

    tasks = (
        db.session.query(Task)
        .filter(Task.agent_id == agent_id)
        .order_by(Task.started_at.desc())
        .limit(limit)
        .all()
    )

    task_dicts = []
    for task in tasks:
        task_dicts.append({
            "task_id": task.id,
            "state": task.state.value,
            "instruction": task.instruction,
            "completion_summary": task.completion_summary,
            "full_command": task.full_command,
            "full_output": task.full_output,
        })

    if formatter:
        voice = formatter.format_output(agent.name, task_dicts, verbosity=verbosity)
    else:
        voice = {"status_line": f"{len(tasks)} recent tasks.", "results": [], "next_action": "none"}

    latency_ms = int((time.time() - start_time) * 1000)
    return jsonify({"voice": voice, "tasks": task_dicts, "latency_ms": latency_ms}), 200


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/question", methods=["GET"])
def agent_question(agent_id: int):
    """Get full question context for an agent awaiting input (FR7)."""
    start_time = time.time()
    formatter = _get_voice_formatter()

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return _voice_error("Agent not found.", "Check the agent ID and try again.", 404)

    current_task = agent.get_current_task()
    if not current_task or current_task.state != TaskState.AWAITING_INPUT:
        state_str = current_task.state.value if current_task else "idle"
        return _voice_error(
            f"Agent is {state_str}, not waiting for input.",
            "No question to show right now.",
            409,
        )

    # Find most recent QUESTION turn
    question_turn = None
    if current_task.turns:
        for t in reversed(current_task.turns):
            if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                question_turn = t
                break

    if not question_turn:
        return _voice_error(
            "Agent is waiting but no question was captured.",
            "Check the dashboard for details.",
            404,
        )

    # Build question data — prefer new voice bridge columns, fall back to tool_input
    q_text = question_turn.question_text or question_turn.text or "Unknown question"
    q_options = question_turn.question_options
    q_source = question_turn.question_source_type or "unknown"

    # Fallback: extract options from tool_input if question_options not populated
    if not q_options and question_turn.tool_input:
        ti = question_turn.tool_input
        questions = ti.get("questions", [])
        if questions and isinstance(questions, list):
            opts = questions[0].get("options", []) if questions else []
            if opts:
                q_options = [
                    {"label": o.get("label", ""), "description": o.get("description", "")}
                    for o in opts if isinstance(o, dict)
                ]
                if not q_source or q_source == "unknown":
                    q_source = "ask_user_question"

    agent_data = {
        "project": agent.project.name if agent.project else "unknown",
        "agent_id": agent.id,
        "question_text": q_text,
        "question_options": q_options,
        "question_source_type": q_source,
    }

    if formatter:
        voice = formatter.format_question(agent_data)
    else:
        voice = {"status_line": "Question from agent.", "results": [q_text], "next_action": "Respond."}

    latency_ms = int((time.time() - start_time) * 1000)
    return jsonify({"voice": voice, "question": agent_data, "latency_ms": latency_ms}), 200


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/transcript", methods=["GET"])
def agent_transcript(agent_id: int):
    """Get agent-lifetime conversation history with cursor-based pagination.

    Query params:
        before: Turn ID cursor — return turns older than this ID
        limit: Number of turns to return (default 50, max 200)
    """
    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    # Parse pagination params
    before = request.args.get("before", type=int)
    limit = min(request.args.get("limit", 50, type=int), 200)

    # Query turns across ALL tasks for this agent
    query = (
        db.session.query(Turn, Task)
        .join(Task, Turn.task_id == Task.id)
        .filter(Task.agent_id == agent_id)
    )

    if before:
        query = query.filter(Turn.id < before)

    # Order descending to get most recent first, then reverse for chronological
    query = query.order_by(Turn.id.desc()).limit(limit + 1)
    results = query.all()

    # Check if there are more older turns
    has_more = len(results) > limit
    if has_more:
        results = results[:limit]

    # Reverse to chronological order
    results.reverse()

    turn_list = []
    for t, task in results:
        # Filter out PROGRESS turns with no meaningful text
        if t.intent == TurnIntent.PROGRESS and (not t.text or not t.text.strip()):
            continue
        turn_list.append({
            "id": t.id,
            "actor": t.actor.value,
            "intent": t.intent.value,
            "text": t.text,
            "summary": t.summary,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "tool_input": t.tool_input,
            "question_text": t.question_text,
            "question_options": t.question_options,
            "question_source_type": t.question_source_type,
            "answered_by_turn_id": t.answered_by_turn_id,
            "task_id": task.id,
            "task_instruction": task.instruction,
            "task_state": task.state.value,
        })

    # Determine current agent state
    current_task = agent.get_current_task()
    agent_state = current_task.state.value if current_task else "idle"
    agent_ended = agent.ended_at is not None

    return jsonify({
        "turns": turn_list,
        "has_more": has_more,
        "agent_state": agent_state,
        "agent_ended": agent_ended,
        "project": agent.project.name if agent.project else "unknown",
        "agent_name": agent.name,
    }), 200
