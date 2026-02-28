"""Voice bridge API endpoints for voice-driven interaction with agents."""

import logging
import os
import time
from datetime import datetime, timedelta, timezone

from flask import Blueprint, current_app, jsonify, make_response, request, send_from_directory

from ..database import db
from ..models.agent import Agent
from ..models.command import Command, CommandState
from ..models.turn import Turn, TurnActor, TurnIntent
from ..services import tmux_bridge
from ..services.agent_lifecycle import (
    create_agent,
    get_context_usage,
    shutdown_agent,
)
from ..services.card_state import broadcast_card_refresh

logger = logging.getLogger(__name__)

# Affirmative patterns for matching voice text to "Yes" options
_AFFIRMATIVE_PATTERNS = {"yes", "yeah", "yep", "yup", "sure", "ok", "okay", "approve", "go", "proceed", "do it", "go ahead", "absolutely", "confirmed", "confirm"}


def _match_picker_option(text: str, labels: list[str]) -> int:
    """Match voice text to the best picker option by label.

    Used for TUI pickers that don't have an "Other" option (e.g., ExitPlanMode).
    Tries exact match first, then fuzzy/semantic matching.

    Args:
        text: The user's voice text (e.g., "Yes", "go ahead", "no")
        labels: The option labels in order (e.g., ["Yes", "No"])

    Returns:
        Index of the best matching option (0-based). Defaults to 0 (first option)
        if no confident match is found — safer to approve than to reject for plan
        approval where the user explicitly initiated the response.
    """
    normalized = text.strip().lower()

    # Exact match (case-insensitive)
    for i, label in enumerate(labels):
        if normalized == label.lower():
            return i

    # Substring match — user text contains an option label
    for i, label in enumerate(labels):
        if label.lower() in normalized:
            return i

    # Semantic match — check for affirmative/negative intent
    if any(p in normalized for p in _AFFIRMATIVE_PATTERNS):
        # Find the "Yes" option
        for i, label in enumerate(labels):
            if label.lower() in ("yes", "approve", "ok", "proceed"):
                return i
        return 0  # Default to first option for affirmative

    # Negative patterns
    if any(p in normalized for p in ("no", "nope", "nah", "reject", "don't", "stop", "cancel")):
        for i, label in enumerate(labels):
            if label.lower() in ("no", "reject", "cancel"):
                return i
        return min(1, len(labels) - 1)  # Default to second option for negative

    # No confident match — default to first option (typically "Yes"/approve).
    # The user explicitly sent a response to an AWAITING_INPUT agent, so they
    # almost certainly intended to approve rather than reject.
    logger.warning(
        f"No confident match for '{text}' against options {labels}, "
        f"defaulting to index 0 ({labels[0] if labels else '?'})"
    )
    return 0


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


def _get_ended_agents(hours: int = 24) -> list:
    """Get recently ended agents (last N hours), newest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.session.query(Agent)
        .filter(Agent.ended_at.isnot(None))
        .filter(Agent.ended_at >= cutoff)
        .order_by(Agent.ended_at.desc())
        .all()
    )


def _agent_to_voice_dict(agent: Agent, include_ended_fields: bool = False) -> dict:
    """Convert an agent to a voice-friendly dict."""
    from ..services.card_state import (
        get_effective_state,
        get_state_info,
        get_command_instruction,
        get_command_summary,
        get_command_completion_summary,
    )

    current_command = agent.get_current_command()
    effective_state = get_effective_state(agent)
    state_name = effective_state if isinstance(effective_state, str) else effective_state.name
    state_info = get_state_info(effective_state)
    awaiting = current_command is not None and current_command.state == CommandState.AWAITING_INPUT

    # Command details from card_state helpers (consistent with dashboard)
    command_instruction = get_command_instruction(agent, _current_command=current_command)
    command_summary = get_command_summary(agent, _current_command=current_command)
    command_completion_summary = get_command_completion_summary(agent)

    # Turn count for current command
    turn_count = 0
    if current_command and current_command.turns:
        turn_count = len(current_command.turns)

    # Agent identity: hero chars from session UUID (matches dashboard)
    truncated_uuid = str(agent.session_uuid)[:8] if agent.session_uuid else ""
    hero_chars = truncated_uuid[:2] if truncated_uuid else ""
    hero_trail = truncated_uuid[2:] if truncated_uuid else ""
    project_name = agent.project.name if agent.project else "unknown"
    persona_name = agent.persona.name if agent.persona else None
    persona_role = agent.persona.role.name if agent.persona and agent.persona.role else None

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

    # Context usage (persisted by ContextPoller)
    context = None
    if agent.context_percent_used is not None:
        context = {
            "percent_used": agent.context_percent_used,
            "remaining_tokens": agent.context_remaining_tokens or "",
        }

    result = {
        "agent_id": agent.id,
        "name": agent.name,
        "hero_chars": hero_chars,
        "hero_trail": hero_trail,
        "project": project_name,
        "state": state_name,
        "state_label": state_info.get("label", state_name),
        "awaiting_input": awaiting,
        "command_instruction": command_instruction,
        "command_summary": command_summary,
        "command_completion_summary": command_completion_summary,
        "turn_count": turn_count,
        "summary": command_summary or command_instruction,
        "last_activity_ago": ago,
        "context": context,
        "tmux_session": agent.tmux_session,
        "persona_name": persona_name,
        "persona_role": persona_role,
        "started_at": agent.started_at.isoformat() if agent.started_at else None,
    }

    if include_ended_fields and agent.ended_at:
        result["ended"] = True
        result["ended_at"] = agent.ended_at.isoformat()

    return result


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
    include_ended = request.args.get("include_ended", "").lower() == "true"
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
    response_data = {
        "voice": voice,
        "agents": agent_dicts,
        "settings": {"auto_target": auto_target},
        "latency_ms": latency_ms,
    }

    if include_ended:
        ended = _get_ended_agents(hours=24)
        response_data["ended_agents"] = [
            _agent_to_voice_dict(a, include_ended_fields=True) for a in ended
        ]

    return jsonify(response_data), 200


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
        awaiting = [a for a in active if a.get_current_command() and a.get_current_command().state == CommandState.AWAITING_INPUT]
        if len(awaiting) == 0:
            # No agents awaiting input — return status summary
            logger.warning(
                f"voice_command_rejected: reason=no_agents_awaiting_input, "
                f"text_length={len(text) if text else 0}, active_agents={len(active)}"
            )
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

    # ── Handoff intent detection ─────────────────────────────────────
    # If the user says "handoff" or "hand off", route to the handoff flow
    # instead of sending the text to the agent via tmux. Any text beyond
    # the trigger keyword becomes operator context for the handoff.
    import re
    handoff_match = re.match(
        r"^(?:please\s+)?(?:do\s+a?\s*)?hand\s*off\b[.!]?\s*(.*)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if handoff_match:
        handoff_context = handoff_match.group(1).strip() or None
        handoff_executor = current_app.extensions.get("handoff_executor")
        if not handoff_executor:
            return _voice_error(
                "Handoff not available.", "Server configuration error.", 503
            )
        result = handoff_executor.trigger_handoff(
            agent.id, reason="voice", context=handoff_context
        )
        if not result.success:
            return _voice_error(result.message, "Check agent eligibility.", 400)

        latency_ms = int((time.time() - start_time) * 1000)
        if formatter:
            voice = formatter.format_command_result(agent.name, True, "Handoff initiated")
        else:
            voice = {
                "status_line": f"Handoff initiated for {agent.name}.",
                "results": [],
                "next_action": "Successor agent will be created when summary is written.",
            }
        return jsonify({"voice": voice, "agent_id": agent.id, "handoff": True, "latency_ms": latency_ms}), 200

    # Determine agent state
    current_command = agent.get_current_command()
    current_state = current_command.state if current_command else None
    is_answering = current_state == CommandState.AWAITING_INPUT
    is_idle = current_state in (None, CommandState.IDLE, CommandState.COMPLETE)
    is_processing = current_state in (CommandState.PROCESSING, CommandState.COMMANDED)

    # Detect if the agent's current question has structured options (picker).
    # Voice chat always sends free text, which works fine for free-text prompts
    # but garbles AskUserQuestion picker UIs (C2 bug). When a picker is active,
    # route through the "Other" option instead of typing literal text.
    #
    # ExitPlanMode is a special case: its TUI has Yes/No options but NO "Other"
    # option (unlike AskUserQuestion which always appends "Other"). Navigating
    # past the last option causes Claude Code to interpret it as a rejection,
    # killing the session. For ExitPlanMode, match the user's answer to an
    # option and select it directly.
    has_picker = False
    is_plan_approval = False
    picker_option_count = 0
    picker_option_labels = []
    if is_answering and current_command and current_command.turns:
        for t in reversed(current_command.turns):
            if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                # Count options from tool_input (canonical source for TUI navigation)
                if t.tool_input and isinstance(t.tool_input, dict):
                    questions = t.tool_input.get("questions", [])
                    if questions and isinstance(questions, list) and len(questions) > 0:
                        opts = questions[0].get("options", [])
                        if isinstance(opts, list) and len(opts) > 0:
                            has_picker = True
                            picker_option_count = len(opts)
                            picker_option_labels = [
                                o.get("label", "") for o in opts if isinstance(o, dict)
                            ]
                    # Detect ExitPlanMode — has "source": "exit_plan_mode_default"
                    if t.tool_input.get("source") == "exit_plan_mode_default":
                        is_plan_approval = True
                # Fallback: question_options column (may not have tool_input)
                if not has_picker and t.question_options:
                    has_picker = True
                break
        if has_picker:
            route_desc = "plan approval (direct select)" if is_plan_approval else "'Other'"
            logger.info(
                f"Voice command to agent {agent.id} targeting a picker question "
                f"({picker_option_count} options). Will route through {route_desc}."
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
    text_enter_delay_ms = bridge_config.get("text_enter_delay_ms", 120)

    # Prepend file_path reference if provided (file before text so the
    # instruction can reference it).  Single line — no embedded newlines
    # which cause premature submission via tmux send-keys.
    send_text = text
    if file_path:
        if send_text:
            send_text = f"{file_path} {send_text}"
        else:
            send_text = file_path

    # Set inflight flag BEFORE tmux send to close the race window between
    # send and respond_pending (set after commit).  The hook's
    # process_user_prompt_submit checks this to skip duplicate turn creation.
    from ..services.hook_agent_state import get_agent_hook_state
    get_agent_hook_state().set_respond_inflight(agent.id)

    if has_picker and is_answering and is_plan_approval:
        # ExitPlanMode plan approval — NO "Other" option exists in this TUI.
        # Match the user's answer to one of the options (Yes/No) and navigate
        # directly to it. Sending Down past the last option causes Claude Code
        # to interpret the input as a rejection, killing the session.
        sequential_delay_ms = bridge_config.get("sequential_delay_ms", 150)
        target_index = _match_picker_option(send_text, picker_option_labels)
        logger.info(
            f"Plan approval for agent {agent.id}: "
            f"matched '{send_text}' to option {target_index} "
            f"({picker_option_labels[target_index] if target_index < len(picker_option_labels) else '?'})"
        )
        # Navigate: Down × target_index (0 for first option) + Enter
        keys = ["Down"] * target_index + ["Enter"]
        result = tmux_bridge.send_keys(
            agent.tmux_pane_id,
            *keys,
            timeout=subprocess_timeout,
            sequential_delay_ms=sequential_delay_ms,
            verify_enter=True,
        )
    elif has_picker and is_answering:
        # AskUserQuestion picker — navigate to "Other" option then type text,
        # instead of sending literal text into the TUI arrow-key selector (C2).
        sequential_delay_ms = bridge_config.get("sequential_delay_ms", 150)
        select_other_delay_ms = bridge_config.get("select_other_delay_ms", 500)
        # "Other" is always appended after all options by AskUserQuestion
        keys = ["Down"] * picker_option_count + ["Enter"]
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
                text=send_text,
                timeout=subprocess_timeout,
                text_enter_delay_ms=text_enter_delay_ms,
                verify_enter=True,
            )
    else:
        if is_processing:
            # Agent is busy — interrupt first (Escape), then send the new instruction
            result = tmux_bridge.interrupt_and_send_text(
                pane_id=agent.tmux_pane_id,
                text=send_text,
                timeout=subprocess_timeout,
                text_enter_delay_ms=text_enter_delay_ms,
                verify_enter=True,
            )
        else:
            # Always verify Enter — autocomplete can swallow it on long text
            # or slash commands, leaving the command sitting in the input box.
            result = tmux_bridge.send_text(
                pane_id=agent.tmux_pane_id,
                text=send_text,
                timeout=subprocess_timeout,
                text_enter_delay_ms=text_enter_delay_ms,
                verify_enter=True,
            )

    if not result.success:
        get_agent_hook_state().clear_respond_inflight(agent.id)
        error_msg = result.error_message or "Send failed"
        logger.warning(
            f"voice_command_rejected: agent_id={agent.id}, reason=tmux_send_failed, "
            f"error={error_msg}, text_length={len(send_text) if send_text else 0}"
        )
        if formatter:
            voice = formatter.format_command_result(agent.name, False, error_msg)
        else:
            voice = {"status_line": f"Command failed: {error_msg}", "results": [], "next_action": "Try again."}
        return jsonify({"voice": voice, "error": "send_failed"}), 502

    if is_idle or is_processing:
        # Create turn directly so the user's message is persisted and
        # broadcast regardless of whether hooks fire.  Previously this path
        # relied entirely on hook_receiver.process_user_prompt_submit to
        # create the Turn — but hooks can fail when context compression
        # changes session_id, after session_end invalidates caches, or if
        # the Claude Code process has exited.  The optimistic voice chat
        # bubble would expire after 10s with no SSE confirmation.
        turn_result = None
        try:
            from ..services.command_lifecycle import CommandLifecycleManager
            event_writer = current_app.extensions.get("event_writer")
            lifecycle = CommandLifecycleManager(
                session=db.session,
                event_writer=event_writer,
            )
            turn_result = lifecycle.process_turn(
                agent=agent, actor=TurnActor.USER, text=send_text,
            )
            # Auto-transition COMMANDED → PROCESSING
            if turn_result.success and turn_result.command and turn_result.command.state == CommandState.COMMANDED:
                lifecycle.update_command_state(
                    command=turn_result.command, to_state=CommandState.PROCESSING,
                    trigger="voice_command", confidence=1.0,
                )

            pending = lifecycle.get_pending_summarisations()
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()

            # Broadcast turn_created immediately after commit
            if turn_result.success and turn_result.command:
                try:
                    from ..services.broadcaster import get_broadcaster
                    user_turn_id = None
                    if turn_result.command.turns:
                        for t in reversed(turn_result.command.turns):
                            if t.actor == TurnActor.USER:
                                user_turn_id = t.id
                                break
                    get_broadcaster().broadcast("turn_created", {
                        "agent_id": agent.id,
                        "project_id": agent.project_id,
                        "text": send_text,
                        "actor": "user",
                        "intent": turn_result.intent.intent.value if turn_result.intent else "command",
                        "command_id": turn_result.command.id,
                        "command_instruction": turn_result.command.instruction,
                        "turn_id": user_turn_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                except Exception as e:
                    logger.warning(f"Voice command turn_created broadcast failed: {e}")

            # Set respond_pending AFTER commit so hook's user_prompt_submit
            # skips duplicate turn creation
            from ..services.hook_agent_state import get_agent_hook_state
            get_agent_hook_state().set_respond_pending(agent.id)

            broadcast_card_refresh(agent, "voice_command")

            # Execute summarisations (instruction + turn)
            if pending:
                try:
                    summarisation_service = current_app.extensions.get("summarisation_service")
                    if summarisation_service:
                        summarisation_service.execute_pending(pending, db.session)
                except Exception as e:
                    logger.warning(f"Voice command summarisation failed: {e}")

        except Exception as e:
            # Lifecycle processing failed but tmux send already succeeded.
            # Fall back: no turn persisted, hooks may still handle it.
            logger.warning(f"Voice command turn creation failed (tmux send succeeded): {e}")
            db.session.rollback()
            get_agent_hook_state().clear_respond_inflight(agent.id)
            agent.last_seen_at = datetime.now(timezone.utc)
            db.session.commit()
            broadcast_card_refresh(agent, "voice_command")

        latency_ms = int((time.time() - start_time) * 1000)
        if formatter:
            voice = formatter.format_command_result(agent.name, True)
        else:
            voice = {"status_line": f"Command sent to {agent.name}.", "results": [], "next_action": "none"}

        new_state = "processing"
        if turn_result and turn_result.command:
            new_state = turn_result.command.state.value

        response_data = {
            "voice": voice,
            "agent_id": agent.id,
            "new_state": new_state,
            "latency_ms": latency_ms,
        }
        if is_processing:
            response_data["interrupted"] = True
        return jsonify(response_data), 200

    # AWAITING_INPUT path: create ANSWER turn and transition state
    try:
        from ..services.command_lifecycle import complete_answer
        result = complete_answer(current_command, agent, text, source="voice_command")

        latency_ms = int((time.time() - start_time) * 1000)
        if formatter:
            voice = formatter.format_command_result(agent.name, True)
        else:
            voice = {"status_line": f"Command sent to {agent.name}.", "results": [], "next_action": "none"}

        response_data = {
            "voice": voice,
            "agent_id": agent.id,
            "new_state": result.new_state.value,
            "latency_ms": latency_ms,
        }
        if has_picker:
            response_data["has_picker"] = True
        return jsonify(response_data), 200

    except Exception as e:
        db.session.rollback()
        get_agent_hook_state().clear_respond_inflight(agent.id)
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

    # Defense-in-depth: validate filename for path traversal at route level
    from ..services.file_upload import FileUploadService
    if not FileUploadService.is_safe_filename(uploaded_file.filename):
        return _voice_error("Invalid filename.", "Filename contains unsafe characters.", 400)

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
    current_command = agent.get_current_command()
    current_state = current_command.state if current_command else None
    is_answering = current_state == CommandState.AWAITING_INPUT
    is_idle = current_state in (None, CommandState.IDLE, CommandState.COMPLETE)

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
    text_enter_delay_ms = bridge_config.get("text_enter_delay_ms", 120)

    result = tmux_bridge.send_text(
        pane_id=agent.tmux_pane_id,
        text=tmux_text,
        timeout=subprocess_timeout,
        text_enter_delay_ms=text_enter_delay_ms,
        verify_enter=True,
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
        # to the COMMAND turn it creates (IDLE agents have no active command yet).
        # Include the clean display text so the hook uses it instead of the raw
        # tmux text (which has the file path prepended), avoiding a duplicate
        # bubble in the chat UI where the frontend dedup compares by text.
        from ..services.hook_agent_state import get_agent_hook_state
        pending_meta = dict(db_metadata)
        pending_meta["_display_text"] = text or f"[File: {file_metadata['original_filename']}]"
        get_agent_hook_state().set_file_metadata_pending(agent.id, pending_meta)

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
        from ..services.command_lifecycle import complete_answer
        display_text = text if text else f"[File: {file_metadata['original_filename']}]"
        result = complete_answer(
            current_command, agent, display_text,
            file_metadata=db_metadata, source="file_upload",
        )

        latency_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            "file_metadata": file_metadata,
            "agent_id": agent.id,
            "turn_id": result.turn.id,
            "new_state": result.new_state.value,
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

    commands = (
        db.session.query(Command)
        .filter(Command.agent_id == agent_id)
        .order_by(Command.started_at.desc())
        .limit(limit)
        .all()
    )

    command_dicts = []
    for command in commands:
        command_dicts.append({
            "command_id": command.id,
            "state": command.state.value,
            "instruction": command.instruction,
            "completion_summary": command.completion_summary,
            "full_command": command.full_command,
            "full_output": command.full_output,
        })

    if formatter:
        voice = formatter.format_output(agent.name, command_dicts, verbosity=verbosity)
    else:
        voice = {"status_line": f"{len(commands)} recent commands.", "results": [], "next_action": "none"}

    latency_ms = int((time.time() - start_time) * 1000)
    return jsonify({"voice": voice, "commands": command_dicts, "latency_ms": latency_ms}), 200


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/question", methods=["GET"])
def agent_question(agent_id: int):
    """Get full question context for an agent awaiting input (FR7)."""
    start_time = time.time()
    formatter = _get_voice_formatter()

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return _voice_error("Agent not found.", "Check the agent ID and try again.", 404)

    current_command = agent.get_current_command()
    if not current_command or current_command.state != CommandState.AWAITING_INPUT:
        state_str = current_command.state.value if current_command else "idle"
        return _voice_error(
            f"Agent is {state_str}, not waiting for input.",
            "No question to show right now.",
            409,
        )

    # Find most recent QUESTION turn
    question_turn = None
    if current_command.turns:
        for t in reversed(current_command.turns):
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

    # Query turns across ALL commands for this agent (excluding team-internal turns)
    query = (
        db.session.query(Turn, Command)
        .join(Command, Turn.command_id == Command.id)
        .filter(Command.agent_id == agent_id)
        .filter(Turn.is_internal == False)  # noqa: E712
    )

    if before:
        # Look up the cursor turn's timestamp for composite pagination.
        # This ensures correct ordering even when timestamps are corrected
        # by the JSONL reconciler (turn insertion order != conversation order).
        cursor_turn = db.session.get(Turn, before)
        if cursor_turn:
            query = query.filter(
                db.or_(
                    Turn.timestamp < cursor_turn.timestamp,
                    db.and_(Turn.timestamp == cursor_turn.timestamp, Turn.id < before),
                )
            )
        else:
            query = query.filter(Turn.id < before)

    # Order by conversation time (timestamp), then id for deterministic tie-breaking
    query = query.order_by(Turn.timestamp.desc(), Turn.id.desc()).limit(limit + 1)
    results = query.all()

    # Check if there are more older turns
    has_more = len(results) > limit
    if has_more:
        results = results[:limit]

    # Reverse to chronological order
    results.reverse()

    turn_list = []
    for t, command in results:
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
            "command_id": command.id,
            "command_instruction": command.instruction,
            "command_state": command.state.value,
        })

    # Inject synthetic command_boundary entries for commands with no turns in this page.
    # This ensures command dividers appear at their chronological position even when
    # a command lost its turns (e.g. during server downtime).
    if turn_list:
        seen_command_ids = {t["command_id"] for t in turn_list}
        min_ts = min(
            (t["timestamp"] for t in turn_list if t["timestamp"]),
            default=None,
        )
        max_ts = max(
            (t["timestamp"] for t in turn_list if t["timestamp"]),
            default=None,
        )
        if min_ts and max_ts:
            min_dt = datetime.fromisoformat(min_ts)
            max_dt = datetime.fromisoformat(max_ts)
            empty_commands = (
                db.session.query(Command)
                .filter(
                    Command.agent_id == agent_id,
                    Command.started_at >= min_dt,
                    Command.started_at <= max_dt,
                    Command.id.notin_(seen_command_ids),
                )
                .all()
            )
            for cmd in empty_commands:
                ts_iso = cmd.started_at.isoformat() if cmd.started_at else None
                turn_list.append({
                    "type": "command_boundary",
                    "command_id": cmd.id,
                    "command_instruction": cmd.instruction,
                    "command_state": cmd.state.value,
                    "timestamp": ts_iso,
                    "has_turns": False,
                })
            # Re-sort by timestamp to place synthetic entries chronologically
            turn_list.sort(key=lambda x: x.get("timestamp") or "")

    # Determine current agent state
    current_command = agent.get_current_command()
    agent_state = current_command.state.value if current_command else "idle"
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
        "tmux_session": agent.tmux_session,
        "persona_name": agent.persona.name if agent.persona else None,
        "persona_role": agent.persona.role.name if agent.persona and agent.persona.role else None,
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

    persona_slug = data.get("persona_slug")
    result = create_agent(project_id, persona_slug=persona_slug)

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


@voice_bridge_bp.route("/api/voice/agents/<int:agent_id>/recapture-permission", methods=["POST"])
def recapture_permission_options(agent_id: int):
    """Re-capture permission options from tmux when initial capture timed out.

    Called by the voice chat frontend when it detects a question bubble
    with no options for a permission_request turn. Retries the tmux pane
    capture with a generous timeout, updates the turn in the DB, and
    broadcasts a turn_updated SSE event so all connected clients get
    the options.
    """
    start_time = time.time()

    agent = db.session.get(Agent, agent_id)
    if not agent:
        return jsonify({"error": "Agent not found"}), 404

    if not agent.tmux_pane_id:
        return jsonify({"error": "Agent has no tmux pane"}), 400

    # Find the latest QUESTION turn with missing options
    current_command = (
        db.session.query(Command)
        .filter(Command.agent_id == agent_id)
        .order_by(Command.id.desc())
        .first()
    )
    if not current_command:
        return jsonify({"error": "No active command"}), 404

    question_turn = None
    for t in reversed(current_command.turns):
        if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
            question_turn = t
            break

    if not question_turn:
        return jsonify({"error": "No question turn found"}), 404

    # Only recapture permission_request turns — free_text questions are
    # conversational and must not be overwritten with Yes/No buttons.
    if question_turn.question_source_type and question_turn.question_source_type != "permission_request":
        return jsonify({
            "recaptured": False,
            "already_present": False,
            "error": f"Turn is {question_turn.question_source_type}, not a permission request",
            "turn_id": question_turn.id,
        }), 200

    # If options already exist, return them immediately
    existing_options = question_turn.question_options
    if not existing_options and question_turn.tool_input:
        ti = question_turn.tool_input
        questions = ti.get("questions", [])
        if questions and isinstance(questions, list):
            opts = questions[0].get("options", []) if questions else []
            if opts:
                existing_options = [
                    {"label": o.get("label", ""), "description": o.get("description", "")}
                    for o in opts if isinstance(o, dict)
                ]

    if existing_options:
        latency_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            "recaptured": False,
            "already_present": True,
            "turn_id": question_turn.id,
            "question_options": existing_options,
            "latency_ms": latency_ms,
        }), 200

    # Attempt to capture from tmux with generous timeout
    from ..services.hook_extractors import synthesize_permission_options
    structured_options = synthesize_permission_options(
        agent,
        tool_name=None,  # Unknown at this point
        tool_input=None,
    )

    if not structured_options:
        latency_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            "recaptured": False,
            "already_present": False,
            "error": "Could not capture options from terminal",
            "turn_id": question_turn.id,
            "latency_ms": latency_ms,
        }), 200

    # Extract options from the synthesized structure
    synth_questions = structured_options.get("questions", [])
    q_options = None
    if synth_questions:
        opts = synth_questions[0].get("options", [])
        if opts:
            q_options = [
                {"label": o.get("label", ""), "description": o.get("description", "")}
                for o in opts if isinstance(o, dict)
            ]

    if not q_options:
        latency_ms = int((time.time() - start_time) * 1000)
        return jsonify({
            "recaptured": False,
            "already_present": False,
            "error": "Captured context but no options found",
            "turn_id": question_turn.id,
            "latency_ms": latency_ms,
        }), 200

    # Update question text if we got a better one
    if synth_questions and synth_questions[0].get("question"):
        question_turn.question_text = synth_questions[0]["question"]
        question_turn.text = synth_questions[0]["question"]

    # Update the turn
    question_turn.question_options = q_options
    structured_options["status"] = "pending"
    question_turn.tool_input = structured_options
    db.session.commit()

    # Broadcast turn_updated so all clients get the options
    try:
        from ..services.broadcaster import get_broadcaster
        get_broadcaster().broadcast("turn_updated", {
            "agent_id": agent.id,
            "project_id": agent.project_id,
            "turn_id": question_turn.id,
            "update_type": "options_recaptured",
            "question_options": q_options,
            "question_text": question_turn.question_text,
            "tool_input": structured_options,
            "safety": structured_options.get("safety", ""),
        })
    except Exception as e:
        logger.warning(f"Failed to broadcast recaptured options: {e}")

    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(
        f"Recaptured permission options for agent {agent_id}, "
        f"turn {question_turn.id}: {len(q_options)} options ({latency_ms}ms)"
    )
    return jsonify({
        "recaptured": True,
        "turn_id": question_turn.id,
        "question_options": q_options,
        "question_text": question_turn.question_text,
        "tool_input": structured_options,
        "latency_ms": latency_ms,
    }), 200
