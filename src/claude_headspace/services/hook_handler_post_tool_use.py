"""Hook handler for post_tool_use events.

Extracted from hook_receiver.py for modularity.
"""

import logging
from datetime import datetime, timezone

from ..models.agent import Agent
from ..models.command import CommandState
from ..models.turn import Turn, TurnActor, TurnIntent
from .hook_extractors import (
    capture_plan_write as _capture_plan_write,
    mark_question_answered as _mark_question_answered,
)
from . import hook_receiver_helpers as _helpers
from .hook_receiver_proxies import _awaiting_tool_for_agent
from .hook_receiver_types import (
    INFERRED_COMMAND_COOLDOWN_SECONDS,
    USER_INTERACTIVE_TOOLS,
    HookEventResult,
    HookEventType,
    get_receiver_state,
)

logger = logging.getLogger(__name__)


def process_post_tool_use(
    agent: Agent,
    claude_session_id: str,
    tool_name: str | None = None,
    tool_input: dict | None = None,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.POST_TOOL_USE)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        # Capture plan file writes via post_tool_use (pre_tool_use only fires
        # for interactive tools, so Write hooks are only received here)
        if tool_name == "Write":
            _capture_plan_write(agent, tool_input)

        lifecycle = _helpers._get_lifecycle_manager()
        current_command = lifecycle.get_current_command(agent)

        if not current_command:
            # Guard: don't infer a command for ended/reaped agents
            if agent.ended_at is not None:
                _helpers.db.session.commit()
                _helpers.broadcast_card_refresh(agent, "post_tool_use")
                logger.info(
                    f"hook_event: type=post_tool_use, agent_id={agent.id}, skipped (agent ended)"
                )
                return HookEventResult(success=True, agent_id=agent.id)

            # Guard: don't infer a command if the previous one just completed
            # (tail-end tool activity after session_end/stop)
            from ..models.command import Command

            recent_complete = (
                _helpers.db.session.query(Command)
                .filter(
                    Command.agent_id == agent.id,
                    Command.state == CommandState.COMPLETE,
                    Command.completed_at.isnot(None),
                )
                .order_by(Command.completed_at.desc())
                .first()
            )
            if recent_complete and recent_complete.completed_at:
                elapsed = (
                    datetime.now(timezone.utc) - recent_complete.completed_at
                ).total_seconds()
                if elapsed < INFERRED_COMMAND_COOLDOWN_SECONDS:
                    _helpers.db.session.commit()
                    _helpers.broadcast_card_refresh(agent, "post_tool_use")
                    logger.info(
                        f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                        f"skipped inferred command (previous command {recent_complete.id} "
                        f"completed {elapsed:.1f}s ago)"
                    )
                    return HookEventResult(success=True, agent_id=agent.id)

            # No command — infer one from tool use evidence
            new_command = lifecycle.create_command(agent, CommandState.COMMANDED)

            # Defense-in-depth: recover user command from the transcript file.
            # If user_prompt_submit never fires (broken hook, timeout, etc.),
            # this ensures the user's instruction is still captured.
            if agent.transcript_path:
                try:
                    from .transcript_reader import read_last_user_message

                    result = read_last_user_message(agent.transcript_path)
                    if result.success and result.text:
                        new_command.full_command = result.text
                        turn = Turn(
                            command_id=new_command.id,
                            actor=TurnActor.USER,
                            intent=TurnIntent.COMMAND,
                            text=result.text,
                        )
                        _helpers.db.session.add(turn)
                        _helpers.db.session.flush()
                        from .command_lifecycle import SummarisationRequest

                        lifecycle._pending_summarisations.append(
                            SummarisationRequest(type="turn", turn=turn)
                        )
                        lifecycle._pending_summarisations.append(
                            SummarisationRequest(
                                type="instruction",
                                command=new_command,
                                command_text=result.text,
                            )
                        )
                        logger.info(
                            f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                            f"recovered user command from transcript ({len(result.text)} chars)"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to recover user command from transcript: {e}"
                    )

            # Commit turn FIRST — turn must survive even if state transition fails.
            _helpers._trigger_priority_scoring()
            pending = lifecycle.get_pending_summarisations()
            _helpers.db.session.commit()

            # Now attempt state transition in a separate commit scope.
            try:
                lifecycle.update_command_state(
                    command=new_command,
                    to_state=CommandState.PROCESSING,
                    trigger="hook:post_tool_use:inferred",
                    confidence=0.9,
                )
                _helpers.db.session.commit()
            except Exception as e:
                _helpers.db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_post_tool_use inferred command state transition failed: "
                    f"error={e} — turn(s) preserved"
                )

            _helpers.broadcast_card_refresh(agent, "post_tool_use_inferred")
            _helpers._execute_pending_summarisations(pending)
            _helpers._broadcast_state_change(
                agent, "post_tool_use", CommandState.PROCESSING.value
            )
            logger.info(
                f"hook_event: type=post_tool_use, agent_id={agent.id}, inferred PROCESSING command_id={new_command.id}"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=True,
                new_state=CommandState.PROCESSING.value,
            )

        if (
            current_command.state == CommandState.AWAITING_INPUT
            and tool_name in USER_INTERACTIVE_TOOLS
        ):
            # ExitPlanMode fires post_tool_use after showing the plan but before the
            # user approves/rejects — preserve AWAITING_INPUT until user_prompt_submit
            _helpers.db.session.commit()
            logger.info(
                f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                f"preserved AWAITING_INPUT for interactive tool {tool_name}"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                new_state=CommandState.AWAITING_INPUT.value,
            )

        if current_command.state == CommandState.AWAITING_INPUT:
            # Only resume if the completing tool matches the one that triggered
            # AWAITING_INPUT. Otherwise a parallel/unrelated tool completion
            # would incorrectly clear the pending user interaction.
            awaiting_tool = _awaiting_tool_for_agent.get(agent.id)
            if awaiting_tool and tool_name != awaiting_tool:
                # Different tool completed — preserve AWAITING_INPUT.
                # Don't broadcast card_refresh here: nothing changed, and doing so
                # floods the SSE stream when an agent uses many tools while a
                # user-interactive tool (AskUserQuestion) is pending.
                _helpers.db.session.commit()
                logger.info(
                    f"hook_event: type=post_tool_use, agent_id={agent.id}, "
                    f"preserved AWAITING_INPUT (awaiting={awaiting_tool}, got={tool_name})"
                )
                return HookEventResult(
                    success=True,
                    agent_id=agent.id,
                    new_state=CommandState.AWAITING_INPUT.value,
                )

            # Resume: matching tool completed (or no tracking) — user answered
            _mark_question_answered(current_command)
            _awaiting_tool_for_agent.pop(agent.id, None)
            # Detect plan approval via post_tool_use resume
            if current_command.plan_content and not current_command.plan_approved_at:
                current_command.plan_approved_at = datetime.now(timezone.utc)
                logger.info(
                    f"plan_approved: agent_id={agent.id}, command_id={current_command.id} (post_tool_use)"
                )
            result = lifecycle.process_turn(
                agent=agent, actor=TurnActor.USER, text=None
            )
            if result.success:
                _helpers._trigger_priority_scoring()
            pending = lifecycle.get_pending_summarisations()
            _helpers.db.session.commit()
            _helpers.broadcast_card_refresh(agent, "post_tool_use_resume")
            _helpers._execute_pending_summarisations(pending)
            new_state = result.command.state.value if result.command else None
            if new_state == CommandState.PROCESSING.value:
                _helpers._broadcast_state_change(
                    agent,
                    "post_tool_use",
                    CommandState.PROCESSING.value,
                    message=f"Tool: {tool_name}" if tool_name else None,
                )
            logger.info(
                f"hook_event: type=post_tool_use, agent_id={agent.id}, resumed from AWAITING_INPUT"
            )
            return HookEventResult(
                success=result.success,
                agent_id=agent.id,
                state_changed=new_state == CommandState.PROCESSING.value
                if new_state
                else False,
                new_state=new_state,
                error_message=result.error,
            )

        # Already PROCESSING/COMMANDED — capture intermediate PROGRESS text
        _helpers._capture_progress_text(agent, current_command)
        _helpers.db.session.commit()
        logger.info(
            f"hook_event: type=post_tool_use, agent_id={agent.id}, progress_capture (state={current_command.state.value})"
        )
        return HookEventResult(
            success=True, agent_id=agent.id, new_state=current_command.state.value
        )
    except Exception as e:
        logger.exception(f"Error processing post_tool_use: {e}")
        _helpers.db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
