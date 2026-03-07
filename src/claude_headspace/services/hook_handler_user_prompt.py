"""Hook handler for user_prompt_submit events.

Extracted from hook_receiver.py for modularity.
"""

import logging
from datetime import datetime, timezone

from ..models.agent import Agent
from ..models.command import CommandState
from ..models.turn import TurnActor
from . import hook_receiver_helpers as _helpers
from .hook_agent_state import get_agent_hook_state
from .hook_extractors import mark_question_answered as _mark_question_answered
from .hook_receiver_types import HookEventResult, HookEventType, get_receiver_state
from .team_content_detector import (
    filter_skill_expansion,
    is_persona_injection,
    is_skill_expansion,
    is_team_internal_content,
)

logger = logging.getLogger(__name__)


def process_user_prompt_submit(
    agent: Agent,
    claude_session_id: str,
    prompt_text: str | None = None,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.USER_PROMPT_SUBMIT)
    try:
        # Check if this prompt was already handled by the dashboard respond handler.
        # When a user responds via the tmux bridge, the respond handler creates the
        # turn and transitions AWAITING_INPUT -> PROCESSING.  Claude Code then fires
        # user_prompt_submit for the same text — skip it to avoid a duplicate command.
        # Check if a voice/respond send is in-flight (pre-commit).
        # The voice bridge sets this before tmux send to close the race
        # window between send and respond_pending (set after commit).
        if get_agent_hook_state().is_respond_inflight(agent.id):
            # Skip turn/state work (respond handler already did that), but still
            # initialize transcript position for the new response cycle.  Without
            # this, _capture_progress_text sees position=None on the first
            # post_tool_use, initializes to current file size (past any agent text
            # already written), and that text is permanently orphaned.
            get_agent_hook_state().consume_progress_texts(agent.id)
            if agent.transcript_path:
                import os

                try:
                    get_agent_hook_state().set_transcript_position(
                        agent.id, os.path.getsize(agent.transcript_path)
                    )
                except OSError:
                    get_agent_hook_state().clear_transcript_position(agent.id)
            agent.last_seen_at = datetime.now(timezone.utc)
            _helpers.db.session.commit()
            _helpers.broadcast_card_refresh(
                agent, "user_prompt_submit_respond_inflight"
            )
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=respond_inflight"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=False,
                new_state=None,
            )

        # Use non-consuming check so the flag persists for the full TTL.
        # Slash commands (skills) trigger a second user_prompt_submit when
        # the Skill tool expands the command content — consuming the flag on
        # the first hook would leave the expansion hook unguarded, creating
        # a "COMMAND" bubble with the raw skill definition text.
        if get_agent_hook_state().is_respond_pending(agent.id):
            # Same as respond_inflight: skip turn/state work but initialize
            # transcript position so progress capture works for this cycle.
            get_agent_hook_state().consume_progress_texts(agent.id)
            if agent.transcript_path:
                import os

                try:
                    get_agent_hook_state().set_transcript_position(
                        agent.id, os.path.getsize(agent.transcript_path)
                    )
                except OSError:
                    get_agent_hook_state().clear_transcript_position(agent.id)
            agent.last_seen_at = datetime.now(timezone.utc)
            _helpers.db.session.commit()
            _helpers.broadcast_card_refresh(agent, "user_prompt_submit_respond_pending")
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=respond_pending"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=False,
                new_state=None,
            )

        # Filter out system-injected XML messages that aren't real user input.
        # Claude Code injects <task-notification> when background tasks complete,
        # and <system-reminder> for internal plumbing.  These fire the
        # user_prompt_submit hook but should NOT create turns or trigger state
        # transitions — they'd appear as nonsensical "COMMAND" bubbles in chat.
        if prompt_text and (
            "<task-notification>" in prompt_text or "<system-reminder>" in prompt_text
        ):
            agent.last_seen_at = datetime.now(timezone.utc)
            _helpers.db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=system_xml"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=False,
                new_state=None,
            )

        # Filter out Claude Code interruption artifacts from tool use key injection.
        # When the voice bridge sends Down+Enter during an interactive tool,
        # Claude Code may interpret it as a user interruption.
        if prompt_text and "[Request interrupted by user for tool use]" in prompt_text:
            agent.last_seen_at = datetime.now(timezone.utc)
            _helpers.db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=tool_interruption_artifact"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=False,
                new_state=None,
            )

        # Detect persona injection priming messages by content pattern.
        # When inject_persona_skills() sends a priming message via tmux,
        # Claude Code echoes it back as user_prompt_submit.  We must NOT
        # skip this entirely — a Command + internal Turn must be created
        # so the subsequent stop hook has a command to attach the agent's
        # introduction response to.  Without a command, the introduction
        # text is orphaned and absorbed into the next real command's
        # transcript.  The flag is used at process_turn() to mark the
        # Turn as is_internal so it doesn't appear in voice chat.
        content_is_persona_injection = bool(
            prompt_text and is_persona_injection(prompt_text)
        )
        if content_is_persona_injection:
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, persona_injection_content=true "
                f"(len={len(prompt_text)})"
            )

        # Detect skill expansion content BEFORE filter_skill_expansion truncates
        # it. Mark as is_internal so voice chat suppresses the raw skill .md file.
        content_is_skill_expansion = bool(
            prompt_text and is_skill_expansion(prompt_text)
        )

        # Content deduplication: suppress identical prompts within 30s.
        # Defence-in-depth against Claude Code firing the same hook hundreds
        # of times (e.g. persona injection storm — 395 times in 97 seconds).
        if prompt_text and get_agent_hook_state().is_duplicate_prompt(
            agent.id, prompt_text
        ):
            agent.last_seen_at = datetime.now(timezone.utc)
            _helpers.db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=content_dedup "
                f"(len={len(prompt_text)})"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=False,
                new_state=None,
            )

        # Command creation rate limiting: cap blast radius even if dedup misses.
        # Max 5 commands per 10s per agent.
        if get_agent_hook_state().is_command_rate_limited(agent.id):
            agent.last_seen_at = datetime.now(timezone.utc)
            _helpers.db.session.commit()
            logger.warning(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=command_rate_limited"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=False,
                new_state=None,
            )

        # Filter out skill/command expansion content.  When a user invokes a
        # slash command, Claude Code's Skill tool fires a SECOND
        # user_prompt_submit with the full .md file content.  For voice-bridge
        # commands this is already caught by respond_pending above, but for
        # commands typed directly in the terminal respond_pending is NOT set.
        # This defense-in-depth check prevents the expanded content from
        # creating a spurious COMMAND turn ("command prompt injection").
        if prompt_text and is_skill_expansion(prompt_text):
            agent.last_seen_at = datetime.now(timezone.utc)
            _helpers.db.session.commit()
            logger.info(
                f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
                f"session_id={claude_session_id}, skipped=skill_expansion "
                f"(len={len(prompt_text)})"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                state_changed=False,
                new_state=None,
            )

        agent.last_seen_at = datetime.now(timezone.utc)
        get_agent_hook_state().clear_awaiting_tool(
            agent.id
        )  # Clear pending tool tracking
        get_agent_hook_state().consume_progress_texts(agent.id)  # New response cycle

        # Handoff intent detection: check the raw prompt text (before
        # filter_skill_expansion or persona-injection label replacement)
        # to decide whether HandoffExecutor should be triggered after
        # the turn is committed.
        from .intent_detector import detect_handoff_intent

        is_handoff, handoff_context = detect_handoff_intent(prompt_text)

        # Initialize transcript position for incremental PROGRESS capture.
        # Set to current file size so post_tool_use only reads NEW content.
        if agent.transcript_path:
            import os

            try:
                get_agent_hook_state().set_transcript_position(
                    agent.id, os.path.getsize(agent.transcript_path)
                )
            except OSError:
                get_agent_hook_state().clear_transcript_position(agent.id)

        lifecycle = _helpers._get_lifecycle_manager()

        # Mark any pending question as answered before processing the new turn
        current_command = lifecycle.get_current_command(agent)
        if current_command and current_command.state == CommandState.AWAITING_INPUT:
            _mark_question_answered(current_command)
            # Detect plan approval: resuming from AWAITING_INPUT with plan content
            if current_command.plan_content and not current_command.plan_approved_at:
                current_command.plan_approved_at = datetime.now(timezone.utc)
                logger.info(
                    f"plan_approved: agent_id={agent.id}, command_id={current_command.id}"
                )

        pending_file_meta = get_agent_hook_state().consume_file_metadata_pending(
            agent.id
        )
        # When the upload endpoint set file metadata, it includes a clean
        # display text (_display_text) so the turn stores the user's text
        # rather than the raw tmux text (which has the file path prepended).
        # This lets the frontend dedup match the optimistic bubble text.
        if pending_file_meta and "_display_text" in pending_file_meta:
            prompt_text = pending_file_meta.pop("_display_text")
        # Truncate skill/command expansion content (e.g. /orch:40-test expands
        # to the full .md file).  Must match the same filter in transcript_reconciler.
        prompt_text = filter_skill_expansion(prompt_text)

        # Suppress persona skill injection priming from voice chat.
        # When inject_persona_skills() sends the priming message via tmux,
        # Claude Code echoes it back as a user_prompt_submit.  That turn is
        # system plumbing, not real user input — mark it internal so the
        # voice transcript query filters it out.
        # Two detection layers: flag-based (set during session_start) and
        # content-based (set earlier in this function).
        is_injection = get_agent_hook_state().consume_skill_injection_pending(agent.id)

        # Replace persona injection priming text with a clean label so the
        # dashboard card shows the persona name, not raw guardrails/skill content.
        if is_injection or content_is_persona_injection:
            persona = getattr(agent, "persona", None)
            persona_name = persona.name if persona else "agent"
            prompt_text = f"{persona_name} is ready"

        result = lifecycle.process_turn(
            agent=agent,
            actor=TurnActor.USER,
            text=prompt_text,
            file_metadata=pending_file_meta,
            is_internal=is_injection
            or content_is_persona_injection
            or content_is_skill_expansion
            or is_team_internal_content(prompt_text),
        )

        if result.success:
            _helpers._trigger_priority_scoring()
            # Record command creation for rate limiting
            if result.new_command_created:
                get_agent_hook_state().record_command_creation(agent.id)

        # Commit turn FIRST — turn must survive even if state transition fails.
        pending = lifecycle.get_pending_summarisations()
        _helpers.db.session.commit()

        # Now attempt state transition in a separate commit scope.
        # Auto-transition COMMANDED → PROCESSING
        # Use agent:progress trigger because this transition represents the
        # agent starting to work, not the user issuing another command.
        if (
            result.success
            and result.command
            and result.command.state == CommandState.COMMANDED
        ):
            try:
                lifecycle.update_command_state(
                    command=result.command,
                    to_state=CommandState.PROCESSING,
                    trigger="agent:progress",
                    confidence=1.0,
                )
                _helpers.db.session.commit()
            except Exception as e:
                _helpers.db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_user_prompt_submit state transition failed: "
                    f"error={e} — turn(s) preserved"
                )

        # Handoff trigger: if the user's message was a handoff request,
        # kick off the HandoffExecutor flow now that the turn is committed.
        # The turn was still processed as a normal COMMAND — handoff is an
        # additional routing action, not a replacement.
        if is_handoff and result.success:
            try:
                from flask import current_app as _app

                handoff_executor = _app.extensions.get("handoff_executor")
                if handoff_executor:
                    handoff_result = handoff_executor.trigger_handoff(
                        agent.id, reason="intent_detected", context=handoff_context
                    )
                    if handoff_result.success:
                        logger.info(
                            f"hook_event: handoff triggered — agent_id={agent.id}, "
                            f"context={repr(handoff_context)}"
                        )
                    else:
                        logger.warning(
                            f"hook_event: handoff trigger failed — agent_id={agent.id}, "
                            f"error={handoff_result.message}, code={handoff_result.error_code}"
                        )
            except Exception as e:
                logger.warning(f"hook_event: handoff trigger error — {e}")

        # Broadcast user turn for voice chat IMMEDIATELY after commit —
        # before summarisation and card_refresh so the chat updates first.
        if prompt_text:
            try:
                from .broadcaster import get_broadcaster

                # Find the turn_id for the user turn just created by process_turn
                user_turn_id = None
                if result.command and result.command.turns:
                    for t in reversed(result.command.turns):
                        if t.actor == TurnActor.USER:
                            user_turn_id = t.id
                            break
                get_broadcaster().broadcast(
                    "turn_created",
                    {
                        "agent_id": agent.id,
                        "project_id": agent.project_id,
                        "text": prompt_text,
                        "actor": "user",
                        "intent": result.intent.intent.value
                        if result.intent
                        else "command",
                        "command_id": result.command.id if result.command else None,
                        "command_instruction": result.command.instruction
                        if result.command
                        else None,
                        "turn_id": user_turn_id,
                        "is_internal": is_injection
                        or content_is_persona_injection
                        or content_is_skill_expansion
                        or is_team_internal_content(prompt_text),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
            except Exception as e:
                logger.warning(f"Turn created broadcast failed: {e}")

        # Execute summarisations BEFORE the card refresh so that the
        # instruction (and turn summary) are already persisted when the card
        # JSON is built.  Previously the card refresh fired first, producing
        # a card with instruction=None on line 03.
        _helpers._execute_pending_summarisations(pending)
        _helpers.broadcast_card_refresh(agent, "user_prompt_submit")

        new_state = (
            result.command.state.value
            if result.command
            else CommandState.PROCESSING.value
        )
        _helpers._broadcast_state_change(
            agent, "user_prompt_submit", new_state, message=prompt_text
        )

        logger.info(
            f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state={new_state}"
        )
        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=True,
            new_state=new_state,
            error_message=result.error,
        )
    except Exception as e:
        logger.exception(f"Error processing user_prompt_submit: {e}")
        _helpers.db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
