"""Voice bridge API endpoints for voice-driven interaction with agents."""

import logging
import os
import time
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, make_response, request, send_from_directory

from ..database import db
from ..models.agent import Agent
from ..models.task import Task, TaskState
from ..models.turn import Turn, TurnActor, TurnIntent
from ..services import tmux_bridge
from ..services.agent_lifecycle import (
    create_agent,
    get_context_usage,
    shutdown_agent,
)
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
    """Get all active agents (not ended) — matches dashboard behaviour."""
    return (
        db.session.query(Agent)
        .filter(Agent.ended_at.is_(None))
        .all()
    )


def _agent_to_voice_dict(agent: Agent) -> dict:
    """Convert an agent to a voice-friendly dict."""
    from ..services.card_state import (
        get_effective_state,
        get_state_info,
        get_task_instruction,
        get_task_summary,
        get_task_completion_summary,
    )

    current_task = agent.get_current_task()
    effective_state = get_effective_state(agent)
    state_name = effective_state if isinstance(effective_state, str) else effective_state.name
    state_info = get_state_info(effective_state)
    awaiting = current_task is not None and current_task.state == TaskState.AWAITING_INPUT

    # Task details from card_state helpers (consistent with dashboard)
    task_instruction = get_task_instruction(agent, _current_task=current_task)
    task_summary = get_task_summary(agent, _current_task=current_task)
    task_completion_summary = get_task_completion_summary(agent)

    # Turn count for current task
    turn_count = 0
    if current_task and current_task.turns:
        turn_count = len(current_task.turns)

    # Agent identity: hero chars from session UUID (matches dashboard)
    truncated_uuid = str(agent.session_uuid)[:8] if agent.session_uuid else ""
    hero_chars = truncated_uuid[:2] if truncated_uuid else ""
    hero_trail = truncated_uuid[2:] if truncated_uuid else ""
    project_name = agent.project.name if agent.project else "unknown"

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
        "hero_chars": hero_chars,
        "hero_trail": hero_trail,
        "project": project_name,
        "state": state_name,
        "state_label": state_info.get("label", state_name),
        "awaiting_input": awaiting,
        "task_instruction": task_instruction,
        "task_summary": task_summary,
        "task_completion_summary": task_completion_summary,
        "turn_count": turn_count,
        "summary": task_summary or task_instruction,
        "last_activity_ago": ago,
    }


@voice_bridge_bp.route("/voice")
def serve_voice_app():
    """Serve the voice bridge PWA entry point."""
    static_dir = os.path.join(current_app.root_path, "..", "..", "static", "voice")
    static_dir = os.path.normpath(static_dir)
    resp = make_response(send_from_directory(static_dir, "voice.html"))
    resp.headers["Cache-Control"] = "no-store"
    return resp


@voice_bridge_bp.route("/voice-sw.js")
def serve_voice_sw():
    """Serve service worker with broadened scope for /voice page control."""
    static_dir = os.path.join(current_app.root_path, "..", "..", "static", "voice")
    static_dir = os.path.normpath(static_dir)
    resp = make_response(send_from_directory(static_dir, "sw.js"))
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


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
    # Tailscale CGNAT range (100.64.0.0/10)
    if addr.startswith("100."):
        return True
    return False


@voice_bridge_bp.before_request
def voice_auth_check():
    """Apply token authentication to API endpoints.

    Bypasses auth for:
    - The /voice page itself
    - Any request from localhost or LAN IPs (same trust boundary as dashboard)
    """
    if request.path in ("/voice", "/voice-sw.js"):
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
    file_path = data.get("file_path", "").strip()

    if not text and not file_path:
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

    # Prepend file_path reference if provided (file before text so the
    # instruction can reference it).  Single line — no embedded newlines
    # which cause premature submission via tmux send-keys.
    send_text = text
    if file_path:
        if send_text:
            send_text = f"{file_path} {send_text}"
        else:
            send_text = file_path

    result = tmux_bridge.send_text(
        pane_id=agent.tmux_pane_id,
        text=send_text,
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
        broadcast_card_refresh(agent, "voice_command")

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

        from ..services.hook_receiver import _mark_question_answered
        _mark_question_answered(current_task)

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


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/upload", methods=["POST"])
def upload_file(agent_id: int):
    """Upload a file to share with an agent."""
    start_time = time.time()

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return _voice_error("Agent not found.", "Check the agent ID and try again.", 404)

    # Check tmux pane
    if not agent.tmux_pane_id:
        return _voice_error(
            "Cannot reach this agent.",
            "The agent has no terminal connection for input.",
            503,
        )

    # Get file from multipart form data
    if "file" not in request.files:
        return _voice_error("No file provided.", "Attach a file and try again.")

    uploaded_file = request.files["file"]
    if not uploaded_file.filename:
        return _voice_error("No file selected.", "Choose a file and try again.")

    text = request.form.get("text", "").strip()

    # Validate and save via FileUploadService
    file_upload = current_app.extensions.get("file_upload")
    if not file_upload:
        return _voice_error("File upload not available.", "Server configuration error.", 503)

    # Read file data to get size
    uploaded_file.seek(0, 2)  # seek to end
    file_size = uploaded_file.tell()
    uploaded_file.seek(0)

    validation = file_upload.validate_file(uploaded_file.filename, file_size, uploaded_file)
    uploaded_file.seek(0)

    if not validation["valid"]:
        return _voice_error(validation["error"], "Check the file and try again.", 400)

    # Determine agent state BEFORE saving file to avoid orphaned files on rejection
    current_task = agent.get_current_task()
    current_state = current_task.state if current_task else None
    is_answering = current_state == TaskState.AWAITING_INPUT
    is_idle = current_state in (None, TaskState.IDLE, TaskState.COMPLETE)

    if not is_answering and not is_idle:
        state_str = current_state.value if current_state else "idle"
        return _voice_error(
            f"Agent is {state_str}, not ready for input.",
            "Try again in a moment when the agent finishes processing.",
            409,
        )

    # Save the file (only after state check passes)
    file_metadata = file_upload.save_file(uploaded_file, uploaded_file.filename)

    # Prepare DB-safe metadata (strip server filesystem path)
    db_metadata = {k: v for k, v in file_metadata.items() if k != "server_path"}

    # Build message for tmux delivery.
    # Use relative path (uploads/<file>) — Claude Code handles relative paths
    # well and absolute paths trigger its interactive file-selection UI.
    # File reference goes first (so the text can reference it), and
    # everything stays on one line to avoid embedded newlines causing
    # premature submission via tmux send-keys.
    rel_path = f"uploads/{file_metadata['stored_filename']}"
    if text:
        tmux_text = f"{rel_path} {text}"
    else:
        tmux_text = rel_path

    # Send via tmux bridge
    config = current_app.config.get("APP_CONFIG", {})
    bridge_config = config.get("tmux_bridge", {})
    subprocess_timeout = bridge_config.get("subprocess_timeout", 5)
    text_enter_delay_ms = bridge_config.get("text_enter_delay_ms", 100)

    result = tmux_bridge.send_text(
        pane_id=agent.tmux_pane_id,
        text=tmux_text,
        timeout=subprocess_timeout,
        text_enter_delay_ms=text_enter_delay_ms,
    )

    if not result.success:
        # Clean up saved file since delivery failed
        from pathlib import Path
        Path(file_metadata["server_path"]).unlink(missing_ok=True)
        error_msg = result.error_message or "Send failed"
        return jsonify({"error": f"File delivery failed: {error_msg}"}), 502

    # Handle state transitions (same logic as voice_command)
    if is_idle:
        # Store file metadata so the next user_prompt_submit hook can attach it
        # to the COMMAND turn it creates (IDLE agents have no active task yet).
        from ..services.hook_receiver import _file_metadata_pending_for_agent
        _file_metadata_pending_for_agent[agent.id] = db_metadata

        agent.last_seen_at = datetime.now(timezone.utc)
        db.session.commit()
        broadcast_card_refresh(agent, "file_upload")

        latency_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            "file_metadata": db_metadata,
            "agent_id": agent.id,
            "new_state": "idle",
            "latency_ms": latency_ms,
        }), 200

    # AWAITING_INPUT path
    try:
        answered_turn_id = None
        if current_task.turns:
            for t in reversed(current_task.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    answered_turn_id = t.id
                    break

        from ..services.hook_receiver import _mark_question_answered
        _mark_question_answered(current_task)

        display_text = text if text else f"[File: {file_metadata['original_filename']}]"
        turn = Turn(
            task_id=current_task.id,
            actor=TurnActor.USER,
            intent=TurnIntent.ANSWER,
            text=display_text,
            file_metadata=db_metadata,
            answered_by_turn_id=answered_turn_id,
        )
        db.session.add(turn)

        from ..services.state_machine import validate_transition
        vr = validate_transition(current_task.state, TurnActor.USER, TurnIntent.ANSWER)
        if vr.valid:
            current_task.state = vr.to_state
        else:
            current_task.state = TaskState.PROCESSING
        agent.last_seen_at = datetime.now(timezone.utc)

        from ..services.hook_receiver import _awaiting_tool_for_agent
        _awaiting_tool_for_agent.pop(agent.id, None)

        db.session.commit()

        from ..services.hook_receiver import _respond_pending_for_agent
        _respond_pending_for_agent[agent.id] = time.time()

        broadcast_card_refresh(agent, "file_upload")

        latency_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            "file_metadata": file_metadata,
            "agent_id": agent.id,
            "turn_id": turn.id,
            "new_state": current_task.state.value,
            "latency_ms": latency_ms,
        }), 200

    except Exception as e:
        db.session.rollback()
        logger.exception(f"Error recording file upload for agent {agent.id}: {e}")
        return _voice_error(
            "File was sent but recording failed.",
            "The agent received your file. State will self-correct.",
            500,
        )


@voice_bridge_bp.route("/api/voice/uploads/<filename>", methods=["GET"])
def serve_upload(filename: str):
    """Serve uploaded files from the configured upload directory."""
    from ..services.file_upload import FileUploadService

    # Validate filename for path traversal
    if not FileUploadService.is_safe_filename(filename):
        return jsonify({"error": "Invalid filename"}), 400

    file_upload = current_app.extensions.get("file_upload")
    if not file_upload:
        return jsonify({"error": "File upload not available"}), 503

    upload_dir = str(file_upload.upload_dir)
    return send_from_directory(upload_dir, filename)


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
            if len(questions) > 1:
                # Multi-question: return full structure array
                q_options = [{
                    "question": qq.get("question", ""),
                    "header": qq.get("header", ""),
                    "multiSelect": qq.get("multiSelect", False),
                    "options": [
                        {"label": o.get("label", ""), "description": o.get("description", "")}
                        for o in qq.get("options", []) if isinstance(o, dict)
                    ],
                } for qq in questions if isinstance(qq, dict)]
                if not q_source or q_source == "unknown":
                    q_source = "ask_user_question"
            else:
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
            "file_metadata": t.file_metadata,
            "task_id": task.id,
            "task_instruction": task.instruction,
            "task_state": task.state.value,
        })

    # Determine current agent state
    current_task = agent.get_current_task()
    agent_state = current_task.state.value if current_task else "idle"
    agent_ended = agent.ended_at is not None

    truncated_uuid = str(agent.session_uuid)[:8] if agent.session_uuid else ""

    return jsonify({
        "turns": turn_list,
        "has_more": has_more,
        "agent_state": agent_state,
        "agent_ended": agent_ended,
        "project": agent.project.name if agent.project else "unknown",
        "agent_name": agent.name,
        "hero_chars": truncated_uuid[:2] if truncated_uuid else "",
        "hero_trail": truncated_uuid[2:] if truncated_uuid else "",
    }), 200


@voice_bridge_bp.route("/api/voice/agents/create", methods=["POST"])
def voice_create_agent():
    """Create a new agent for a project via voice bridge."""
    start_time = time.time()
    data = request.get_json(silent=True) or {}
    formatter = _get_voice_formatter()

    # Accept project_id or project_name
    project_id = data.get("project_id")
    project_name = data.get("project_name", "").strip()

    if not project_id and not project_name:
        return _voice_error(
            "No project specified.",
            "Provide a project name or ID.",
        )

    # Resolve project_name to project_id
    if not project_id and project_name:
        from ..models.project import Project as Proj

        project = (
            db.session.query(Proj)
            .filter(db.func.lower(Proj.name) == project_name.lower())
            .first()
        )
        if not project:
            return _voice_error(
                f"Project '{project_name}' not found.",
                "Check the project name and try again.",
                404,
            )
        project_id = project.id

    result = create_agent(project_id)

    latency_ms = int((time.time() - start_time) * 1000)
    if not result.success:
        if formatter:
            voice = formatter.format_error(result.message, "Check project settings.")
        else:
            voice = {"status_line": result.message, "results": [], "next_action": "none"}
        return jsonify({"voice": voice, "error": result.message, "latency_ms": latency_ms}), 422

    if formatter:
        voice = {"status_line": "Agent starting.", "results": [result.message], "next_action": "Wait for it to appear on the dashboard."}
    else:
        voice = {"status_line": result.message, "results": [], "next_action": "none"}

    return jsonify({
        "voice": voice,
        "message": result.message,
        "tmux_session_name": result.tmux_session_name,
        "latency_ms": latency_ms,
    }), 201


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/shutdown", methods=["POST"])
def voice_shutdown_agent(agent_id: int):
    """Gracefully shut down an agent via voice bridge."""
    start_time = time.time()
    formatter = _get_voice_formatter()

    result = shutdown_agent(agent_id)

    latency_ms = int((time.time() - start_time) * 1000)
    if not result.success:
        status = 404 if "not found" in result.message.lower() else 422
        if formatter:
            voice = formatter.format_error(result.message, "Check the agent status.")
        else:
            voice = {"status_line": result.message, "results": [], "next_action": "none"}
        return jsonify({"voice": voice, "error": result.message, "latency_ms": latency_ms}), status

    if formatter:
        voice = {"status_line": "Shutting down.", "results": [result.message], "next_action": "Agent will disappear when hooks fire."}
    else:
        voice = {"status_line": result.message, "results": [], "next_action": "none"}

    return jsonify({"voice": voice, "message": result.message, "latency_ms": latency_ms}), 200


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/context", methods=["GET"])
def voice_agent_context(agent_id: int):
    """Get context window usage for an agent via voice bridge."""
    start_time = time.time()
    formatter = _get_voice_formatter()

    result = get_context_usage(agent_id)

    latency_ms = int((time.time() - start_time) * 1000)
    if not result.available:
        reason_messages = {
            "agent_not_found": "Agent not found.",
            "agent_ended": "Agent has ended.",
            "no_tmux_pane": "Agent has no terminal connection.",
            "capture_failed": "Could not read agent terminal.",
            "statusline_not_found": "Context info not available for this agent.",
        }
        msg = reason_messages.get(result.reason, "Context unavailable.")
        status = 404 if result.reason == "agent_not_found" else 200
        if formatter:
            voice = {"status_line": msg, "results": [], "next_action": "none"}
        else:
            voice = {"status_line": msg, "results": [], "next_action": "none"}
        return jsonify({
            "voice": voice,
            "available": False,
            "reason": result.reason,
            "latency_ms": latency_ms,
        }), status

    summary = f"{result.percent_used}% used, {result.remaining_tokens} remaining"
    if formatter:
        voice = {"status_line": summary, "results": [result.raw or summary], "next_action": "none"}
    else:
        voice = {"status_line": summary, "results": [], "next_action": "none"}

    return jsonify({
        "voice": voice,
        "available": True,
        "percent_used": result.percent_used,
        "remaining_tokens": result.remaining_tokens,
        "raw": result.raw,
        "latency_ms": latency_ms,
    }), 200
