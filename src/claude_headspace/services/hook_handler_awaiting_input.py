"""Hook handlers for awaiting-input events (notification, pre_tool_use, permission_request).

Extracted from hook_receiver.py for modularity.
"""

import logging
from datetime import datetime, timezone

from ..models.agent import Agent
from ..models.command import CommandState
from ..models.turn import Turn, TurnActor, TurnIntent
from .hook_extractors import (
    capture_plan_write as _capture_plan_write,
    extract_question_text as _extract_question_text,
    extract_structured_options as _extract_structured_options,
    mark_question_answered as _mark_question_answered,
    synthesize_permission_options as _synthesize_permission_options,
)
from . import hook_receiver_helpers as _helpers
from .hook_receiver_proxies import _awaiting_tool_for_agent
from .hook_receiver_types import (
    HookEventResult,
    HookEventType,
    PRE_TOOL_USE_INTERACTIVE,
    get_receiver_state,
)
from .team_content_detector import is_team_internal_content

logger = logging.getLogger(__name__)


def _handle_awaiting_input(
    agent: Agent,
    event_type_enum: HookEventType,
    event_type_str: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
    message: str | None = None,
    title: str | None = None,
) -> HookEventResult:
    """Common handler for hooks that transition to AWAITING_INPUT."""
    state = get_receiver_state()
    state.record_event(event_type_enum)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)
        current_command = agent.get_current_command()

        if not current_command or current_command.state not in (
            CommandState.PROCESSING,
            CommandState.COMMANDED,
        ):
            _helpers.db.session.commit()
            _helpers.broadcast_card_refresh(agent, event_type_str)
            logger.info(
                f"hook_event: type={event_type_str}, agent_id={agent.id}, ignored (no active processing command)"
            )
            return HookEventResult(success=True, agent_id=agent.id)

        # Flush any pending agent output from the transcript BEFORE creating
        # the question turn. This captures text the agent printed (e.g. plan
        # details, colour palette options, analysis) between the last tool
        # completion and this interactive tool call.
        _helpers._capture_progress_text(agent, current_command)

        # Build question text and create turn BEFORE state transition
        question_text = None
        question_turn = None
        structured_options = None
        permission_summary_needed = False
        if tool_name is not None or tool_input is not None:
            # pre_tool_use / permission_request: always create turn
            question_text = _extract_question_text(tool_name, tool_input)
            structured_options = _extract_structured_options(tool_name, tool_input)
            # Determine question source type and voice-friendly options
            q_source_type = None
            q_options = None
            if tool_name == "AskUserQuestion" and structured_options:
                q_source_type = "ask_user_question"
                # Extract normalized options for voice bridge
                questions = structured_options.get("questions", [])
                if questions and isinstance(questions, list) and len(questions) > 1:
                    # Multi-question: store full structure array for rendering
                    q_options = [
                        {
                            "question": qq.get("question", ""),
                            "header": qq.get("header", ""),
                            "multiSelect": qq.get("multiSelect", False),
                            "options": [
                                {
                                    "label": o.get("label", ""),
                                    "description": o.get("description", ""),
                                }
                                for o in qq.get("options", [])
                                if isinstance(o, dict)
                            ],
                        }
                        for qq in questions
                        if isinstance(qq, dict)
                    ]
                elif questions and isinstance(questions, list):
                    q = questions[0] if questions else {}
                    opts = q.get("options", [])
                    if opts:
                        q_options = [
                            {
                                "label": o.get("label", ""),
                                "description": o.get("description", ""),
                            }
                            for o in opts
                            if isinstance(o, dict)
                        ]
            elif event_type_enum == HookEventType.PERMISSION_REQUEST:
                q_source_type = "permission_request"
            # For ExitPlanMode, synthesize default approval options + attach plan content
            if structured_options is None and tool_name == "ExitPlanMode":
                question_text = "Approve plan and proceed?"
                structured_options = {
                    "questions": [
                        {
                            "question": question_text,
                            "options": [
                                {
                                    "label": "Yes",
                                    "description": "Approve the plan and begin implementation",
                                },
                                {
                                    "label": "No",
                                    "description": "Reject and stay in plan mode",
                                },
                            ],
                        }
                    ],
                    "source": "exit_plan_mode_default",
                }
                # Attach plan content so the voice chat can display it
                if current_command.plan_content:
                    structured_options["plan_content"] = current_command.plan_content
                    if current_command.plan_file_path:
                        structured_options["plan_file_path"] = (
                            current_command.plan_file_path
                        )
                q_source_type = "ask_user_question"
                q_options = [
                    {
                        "label": "Yes",
                        "description": "Approve the plan and begin implementation",
                    },
                    {"label": "No", "description": "Reject and stay in plan mode"},
                ]
            # For permission_request, try capturing options + context from the tmux pane
            if (
                structured_options is None
                and event_type_enum == HookEventType.PERMISSION_REQUEST
            ):
                structured_options = _synthesize_permission_options(
                    agent, tool_name, tool_input
                )
                # Use the synthesized question text (from permission summarizer) if available
                if structured_options:
                    synth_questions = structured_options.get("questions", [])
                    if synth_questions and synth_questions[0].get("question"):
                        question_text = synth_questions[0]["question"]
                    # Extract options for voice bridge
                    if synth_questions:
                        opts = synth_questions[0].get("options", [])
                        if opts:
                            q_options = [
                                {
                                    "label": o.get("label", ""),
                                    "description": o.get("description", ""),
                                }
                                for o in opts
                                if isinstance(o, dict)
                            ]
                    # Check if LLM fallback needed (generic summary)
                    if question_text and question_text.startswith("Permission:"):
                        permission_summary_needed = True
            if structured_options:
                structured_options["status"] = "pending"
            question_turn = Turn(
                command_id=current_command.id,
                actor=TurnActor.AGENT,
                intent=TurnIntent.QUESTION,
                text=question_text,
                tool_input=structured_options,
                question_text=question_text,
                question_options=q_options,
                question_source_type=q_source_type,
                is_internal=is_team_internal_content(question_text),
            )
            _helpers.db.session.add(question_turn)
        elif message or title:
            # Skip turn creation for standard NOTIFICATION hooks — they carry
            # generic text ("Claude is waiting for your input") with no actual
            # response content.  The stop hook creates the proper turn with
            # real transcript text.  State transition + OS notification still fire.
            if event_type_enum == HookEventType.NOTIFICATION:
                pass
            else:
                # Non-notification path (future code paths): dedup against recent turn
                has_recent = False
                if current_command.turns:
                    for t in reversed(current_command.turns):
                        if (
                            t.actor == TurnActor.AGENT
                            and t.intent == TurnIntent.QUESTION
                        ):
                            has_recent = (
                                datetime.now(timezone.utc) - t.timestamp
                            ).total_seconds() < 10
                            break
                if not has_recent:
                    question_text = (f"[{title}] " if title else "") + (message or "")
                    question_text = question_text.strip()
                    if question_text:
                        question_turn = Turn(
                            command_id=current_command.id,
                            actor=TurnActor.AGENT,
                            intent=TurnIntent.QUESTION,
                            text=question_text,
                            question_text=question_text,
                            question_source_type="free_text",
                            is_internal=is_team_internal_content(question_text),
                        )
                        _helpers.db.session.add(question_turn)

        # Track which tool triggered AWAITING_INPUT so post_tool_use only
        # resumes when the matching tool completes (not unrelated tools)
        if tool_name:
            _awaiting_tool_for_agent[agent.id] = tool_name

        # Commit turn FIRST — turn must survive even if state transition fails.
        _helpers.db.session.commit()

        # Now attempt state transition in a separate commit scope.
        lifecycle = _helpers._get_lifecycle_manager()
        try:
            lifecycle.update_command_state(
                current_command,
                CommandState.AWAITING_INPUT,
                trigger=event_type_str,
                confidence=1.0,
            )
            _helpers.db.session.commit()
        except Exception as e:
            _helpers.db.session.rollback()
            logger.warning(
                f"[HOOK_RECEIVER] _handle_awaiting_input state transition failed: "
                f"error={e} — turn preserved"
            )
        _helpers.broadcast_card_refresh(agent, event_type_str)

        # Broadcast
        _helpers._broadcast_state_change(agent, event_type_str, "AWAITING_INPUT")
        if question_text:
            _helpers._broadcast_turn_created(
                agent,
                question_text,
                current_command,
                tool_input=structured_options,
                turn_id=question_turn.id if question_turn else None,
                question_source_type=question_turn.question_source_type
                if question_turn
                else None,
            )
        elif current_command.turns:
            # Broadcast existing turn (dedup case: pre_tool_use fired first)
            for t in reversed(current_command.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    _helpers._broadcast_turn_created(
                        agent,
                        t.text,
                        current_command,
                        tool_input=t.tool_input,
                        turn_id=t.id,
                        question_source_type=t.question_source_type,
                    )
                    break

        # Queue LLM fallback for generic permission summaries
        if permission_summary_needed and current_command.turns:
            for t in reversed(current_command.turns):
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.QUESTION:
                    from .command_lifecycle import SummarisationRequest

                    _helpers._execute_pending_summarisations(
                        [
                            SummarisationRequest(type="permission_summary", turn=t),
                        ]
                    )
                    break

        logger.info(
            f"hook_event: type={event_type_str}, agent_id={agent.id}, AWAITING_INPUT"
        )
        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=True,
            new_state="AWAITING_INPUT",
        )
    except Exception as e:
        logger.exception(f"Error processing {event_type_str}: {e}")
        _helpers.db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


def process_notification(
    agent: Agent,
    claude_session_id: str,
    message: str | None = None,
    title: str | None = None,
    notification_type: str | None = None,
) -> HookEventResult:
    # Filter team-internal XML notifications (sub-agent comms).
    if message and ("<task-notification>" in message or "<system-reminder>" in message):
        state = get_receiver_state()
        state.record_event(HookEventType.NOTIFICATION)
        agent.last_seen_at = datetime.now(timezone.utc)
        _helpers.db.session.commit()
        logger.info(
            f"hook_event: type=notification, agent_id={agent.id}, "
            f"session_id={claude_session_id}, skipped=system_xml"
        )
        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=False,
            new_state=None,
        )
    # Filter interruption artifact notifications from tmux key injection.
    if message and "Interruption detected" in message:
        state = get_receiver_state()
        state.record_event(HookEventType.NOTIFICATION)
        agent.last_seen_at = datetime.now(timezone.utc)
        _helpers.db.session.commit()
        logger.info(
            f"hook_event: type=notification, agent_id={agent.id}, "
            f"session_id={claude_session_id}, skipped=interruption_artifact"
        )
        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=False,
            new_state=None,
        )
    return _handle_awaiting_input(
        agent,
        HookEventType.NOTIFICATION,
        "notification",
        message=message,
        title=title,
    )


def process_pre_tool_use(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    # Only transition to AWAITING_INPUT for known interactive tools
    # (where user interaction happens AFTER the tool completes).
    # For all other tools, pre_tool_use is just activity — no state change.
    if tool_name in PRE_TOOL_USE_INTERACTIVE:
        # Mark plan mode entry before handling the AWAITING_INPUT transition
        if tool_name == "EnterPlanMode":
            try:
                current_command = agent.get_current_command()
                if current_command and not current_command.plan_file_path:
                    current_command.plan_file_path = "pending"
                    # Don't commit yet — _handle_awaiting_input will commit
            except Exception as e:
                logger.warning(f"Failed to mark plan mode entry: {e}")
        return _handle_awaiting_input(
            agent,
            HookEventType.PRE_TOOL_USE,
            "pre_tool_use",
            tool_name=tool_name,
            tool_input=tool_input,
        )

    # Non-interactive tool: lightweight update, but recover stale AWAITING_INPUT.
    # If the agent is running a non-interactive tool, it's clearly not waiting
    # for user input. This recovers from lost post_tool_use hooks (e.g. server
    # restart killed the process before the hook could be received).
    receiver_state = get_receiver_state()
    receiver_state.record_event(HookEventType.PRE_TOOL_USE)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        # Capture plan file writes (Write to .claude/plans/)
        if tool_name == "Write":
            _capture_plan_write(agent, tool_input)

        current_command = agent.get_current_command()
        if current_command and current_command.state == CommandState.AWAITING_INPUT:
            _mark_question_answered(current_command)
            lifecycle = _helpers._get_lifecycle_manager()
            lifecycle.update_command_state(
                command=current_command,
                to_state=CommandState.PROCESSING,
                trigger="hook:pre_tool_use:stale_awaiting_recovery",
                confidence=0.9,
            )
            _awaiting_tool_for_agent.pop(agent.id, None)
            _helpers.db.session.commit()
            _helpers.broadcast_card_refresh(agent, "pre_tool_use_recovery")
            _helpers._broadcast_state_change(
                agent, "pre_tool_use", CommandState.PROCESSING.value
            )
            logger.info(
                f"hook_event: type=pre_tool_use, agent_id={agent.id}, tool={tool_name}, "
                f"recovered stale AWAITING_INPUT → PROCESSING"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=True,
                new_state=CommandState.PROCESSING.value,
            )

        _helpers.db.session.commit()
        logger.debug(
            f"hook_event: type=pre_tool_use, agent_id={agent.id}, tool={tool_name}, no state change"
        )
        return HookEventResult(success=True, agent_id=agent.id)
    except Exception as e:
        logger.exception(f"Error processing pre_tool_use: {e}")
        _helpers.db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


def process_permission_request(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    return _handle_awaiting_input(
        agent,
        HookEventType.PERMISSION_REQUEST,
        "permission_request",
        tool_name=tool_name,
        tool_input=tool_input,
    )
