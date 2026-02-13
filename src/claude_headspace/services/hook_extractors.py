"""Pure extraction functions for hook receiver.

These are stateless functions that extract, parse, or transform
hook event data. Moved from hook_receiver.py to reduce module size.
"""

import logging

from ..models.turn import TurnActor, TurnIntent

logger = logging.getLogger(__name__)


def extract_question_text(tool_name: str | None, tool_input: dict | None) -> str:
    """Extract human-readable question text from hook tool data."""
    if tool_input and isinstance(tool_input, dict):
        questions = tool_input.get("questions")
        if questions and isinstance(questions, list) and len(questions) > 0:
            # Multi-question: join all question texts
            if len(questions) > 1:
                texts = []
                for q in questions:
                    if isinstance(q, dict) and q.get("question"):
                        texts.append(q["question"])
                if texts:
                    return " | ".join(texts)
            q = questions[0]
            if isinstance(q, dict) and q.get("question"):
                return q["question"]
        # Non-AskUserQuestion tool_input with raw params (e.g. {"command": "..."})
        # Use permission summarizer for a meaningful description
        if tool_name and tool_name != "AskUserQuestion" and not questions:
            from .permission_summarizer import summarize_permission_command
            return summarize_permission_command(tool_name, tool_input)
    if tool_name:
        return f"Permission needed: {tool_name}"
    return "Awaiting input"


def extract_structured_options(tool_name: str | None, tool_input: dict | None) -> dict | None:
    """Extract structured AskUserQuestion data for storage in Turn.tool_input.

    Returns the full tool_input dict when the tool is AskUserQuestion and
    contains valid questions with options. Returns None otherwise.
    """
    if tool_name != "AskUserQuestion" or not tool_input or not isinstance(tool_input, dict):
        return None
    questions = tool_input.get("questions")
    if not questions or not isinstance(questions, list) or len(questions) == 0:
        return None
    q = questions[0]
    if not isinstance(q, dict) or not q.get("options"):
        return None
    return tool_input


def synthesize_permission_options(
    agent,
    tool_name: str | None,
    tool_input: dict | None,
) -> dict | None:
    """Capture permission dialog context from tmux pane and build AskUserQuestion-compatible dict.

    When a permission-request hook fires, the actual numbered options (e.g. "1. Yes / 2. No")
    are rendered in the terminal but not included in the hook payload. This function captures
    the tmux pane content, parses the options and command context, and wraps them in the same
    format that AskUserQuestion uses so the existing button-rendering pipeline works unchanged.

    Also generates a meaningful summary (e.g. "Bash: curl from localhost:5055") instead of
    the generic "Permission needed: Bash" using pattern matching on the tool_input.

    Returns None if the agent has no tmux_pane_id or if capture/parse fails.
    """
    if not agent.tmux_pane_id:
        return None

    try:
        from . import tmux_bridge
        pane_context = tmux_bridge.capture_permission_context(agent.tmux_pane_id)
    except Exception as e:
        logger.warning(f"Permission context capture failed for agent {agent.id}: {e}")
        return None

    if not pane_context:
        return None

    options = pane_context.get("options")
    if not options:
        return None

    # Generate meaningful summary using permission summarizer
    from .permission_summarizer import summarize_permission_command, classify_safety
    question_text = summarize_permission_command(tool_name, tool_input, pane_context)
    safety = classify_safety(tool_name, tool_input, pane_context)

    # Build command context for future auto-responder
    command_context = {}
    if pane_context.get("command"):
        command_context["command"] = pane_context["command"]
    if pane_context.get("description"):
        command_context["description"] = pane_context["description"]

    result = {
        "questions": [{
            "question": question_text,
            "options": options,
        }],
        "source": "permission_pane_capture",
        "safety": safety,
    }
    if command_context:
        result["command_context"] = command_context

    return result


def mark_question_answered(task) -> None:
    """Mark the most recent QUESTION turn's tool_input status as complete.

    Called when a question is answered to prevent stale options from
    being rendered on subsequent AWAITING_INPUT transitions.
    """
    if not task or not hasattr(task, 'turns') or not task.turns:
        return
    for turn in reversed(task.turns):
        if turn.actor == TurnActor.AGENT and turn.intent == TurnIntent.QUESTION:
            if turn.tool_input and isinstance(turn.tool_input, dict):
                # Reassign dict (not mutate) so SQLAlchemy detects the change
                turn.tool_input = {**turn.tool_input, "status": "complete"}
            break


def capture_plan_write(agent, tool_input: dict | None) -> bool:
    """Capture plan file content when agent writes to .claude/plans/.

    Returns True if plan content was captured and committed.
    """
    from ..database import db
    from .card_state import broadcast_card_refresh

    if not tool_input or not isinstance(tool_input, dict):
        return False
    file_path = tool_input.get("file_path", "")
    content = tool_input.get("content", "")
    if not file_path or ".claude/plans/" not in file_path or not content:
        return False

    current_task = agent.get_current_task()
    if not current_task:
        return False

    current_task.plan_file_path = file_path
    current_task.plan_content = content
    db.session.commit()
    broadcast_card_refresh(agent, "plan_file_captured")
    logger.info(
        f"plan_capture: agent_id={agent.id}, task_id={current_task.id}, "
        f"file={file_path}, content_len={len(content)}"
    )
    return True
