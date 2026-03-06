"""Hook handler for stop events.

Extracted from hook_receiver.py for modularity.
"""

import logging
from datetime import datetime, timezone

from ..models.agent import Agent
from ..models.command import CommandState
from ..models.turn import Turn, TurnActor, TurnIntent
from . import hook_receiver_helpers as _helpers
from .hook_agent_state import get_agent_hook_state
from .hook_receiver_types import HookEventResult, HookEventType, get_receiver_state
from .team_content_detector import is_team_internal_content

logger = logging.getLogger(__name__)


def process_stop(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.STOP)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        # Check if this agent has a handoff in progress — if so, delegate
        # to HandoffExecutor for continuation (file verification, DB record,
        # successor creation) instead of normal stop processing.
        try:
            from flask import current_app as _app

            handoff_executor = _app.extensions.get("handoff_executor")
            if handoff_executor and handoff_executor.is_handoff_in_progress(agent.id):
                logger.info(
                    f"hook_event: type=stop, agent_id={agent.id}, "
                    f"handoff_in_progress — delegating to HandoffExecutor"
                )
                handoff_result = handoff_executor.continue_after_stop(agent)
                if handoff_result.success:
                    logger.info(
                        f"hook_event: type=stop, agent_id={agent.id}, "
                        f"handoff continuation complete"
                    )
                else:
                    logger.error(
                        f"hook_event: type=stop, agent_id={agent.id}, "
                        f"handoff continuation failed: {handoff_result.message}"
                    )
                # Whether handoff succeeded or failed, return — don't do
                # normal stop processing for a handoff agent.
                _helpers.db.session.commit()
                _helpers.broadcast_card_refresh(agent, "stop")
                return HookEventResult(
                    success=handoff_result.success,
                    agent_id=agent.id,
                    error_message=None
                    if handoff_result.success
                    else handoff_result.message,
                )
        except RuntimeError:
            pass  # No app context — skip handoff check

        lifecycle = _helpers._get_lifecycle_manager()
        current_command = lifecycle.get_current_command(agent)
        if not current_command:
            _helpers.db.session.commit()
            _helpers.broadcast_card_refresh(agent, "stop")
            logger.info(
                f"hook_event: type=stop, agent_id={agent.id}, no active command"
            )
            return HookEventResult(success=True, agent_id=agent.id)

        # Guard: if an interactive tool (AskUserQuestion, ExitPlanMode) has
        # already set AWAITING_INPUT via pre_tool_use, the stop hook fires
        # BETWEEN pre_tool_use and post_tool_use while Claude waits for user
        # input.  Processing the transcript here would either create a new
        # Turn without tool_input (shadowing the structured options) or
        # complete the command entirely — both destroy the respond widget.
        if current_command.state == CommandState.AWAITING_INPUT:
            awaiting_tool = get_agent_hook_state().get_awaiting_tool(agent.id)
            if awaiting_tool:
                _helpers.db.session.commit()
                _helpers.broadcast_card_refresh(agent, "stop")
                logger.info(
                    f"hook_event: type=stop, agent_id={agent.id}, "
                    f"preserved AWAITING_INPUT (active interactive tool: {awaiting_tool})"
                )
                return HookEventResult(
                    success=True,
                    agent_id=agent.id,
                    new_state="AWAITING_INPUT",
                )

        # Extract transcript and detect intent.
        # Claude Code may fire the stop hook before flushing the final assistant
        # response to the JSONL file.  If empty on first read, schedule a
        # deferred re-check on a background thread instead of blocking the
        # Flask request handler.
        agent_text = _helpers._extract_transcript_content(agent)
        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"transcript_extracted: len={len(agent_text) if agent_text else 0}, "
            f"empty={not agent_text}"
        )
        if not agent_text:
            # Defer transcript extraction: complete the request now and
            # schedule a background re-check after a short delay.
            logger.info(
                f"[RELAY_FORENSIC] process_stop DEFERRED: agent_id={agent.id}, "
                f"transcript empty — relay will happen in deferred_stop"
            )
            _helpers._schedule_deferred_stop(agent, current_command)
            _helpers.db.session.commit()
            _helpers.broadcast_card_refresh(agent, "stop")
            logger.info(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"transcript empty — deferred re-check scheduled"
            )
            return HookEventResult(
                success=True,
                agent_id=agent.id,
                new_state=current_command.state.value,
            )

        # Deduplicate: if PROGRESS turns already captured intermediate text,
        # only include NEW text in the COMPLETION turn to avoid duplicate
        # content in the voice bridge chat.  full_agent_text retains everything
        # for intent detection and command.full_output.
        full_agent_text = agent_text
        captured = get_agent_hook_state().consume_progress_texts(agent.id)
        completion_text = agent_text
        all_captured_by_progress = False
        if captured:
            pos = get_agent_hook_state().get_transcript_position(agent.id) or 0
            if pos > 0 and agent.transcript_path:
                from .transcript_reader import read_new_entries_from_position

                new_entries, _ = read_new_entries_from_position(
                    agent.transcript_path, pos
                )
                new_texts = [
                    e.content.strip()
                    for e in new_entries
                    if e.role == "assistant" and e.content and e.content.strip()
                ]
                if new_texts:
                    completion_text = "\n\n".join(new_texts)
                else:
                    # All text was captured as PROGRESS turns — upgrade
                    # the last PROGRESS turn instead of creating a duplicate.
                    completion_text = full_agent_text
                    all_captured_by_progress = True
            logger.info(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"progress_dedup: captured={len(captured)} turns, "
                f"full_len={len(full_agent_text)}, completion_len={len(completion_text)}"
            )
        get_agent_hook_state().clear_transcript_position(agent.id)

        try:
            from flask import current_app

            inference_service = current_app.extensions.get("inference_service")
        except RuntimeError:
            inference_service = None

        # Use full text for intent detection (completion patterns may be at the end)
        intent_result = _helpers.detect_agent_intent(
            full_agent_text,
            inference_service=inference_service,
            project_id=agent.project_id,
            agent_id=agent.id,
        )

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"transcript_len={len(full_agent_text) if full_agent_text else 0}, "
            f"intent={intent_result.intent.value}, "
            f"confidence={intent_result.confidence}, "
            f"pattern={intent_result.matched_pattern!r}"
        )
        if full_agent_text:
            tail_lines = [
                line for line in full_agent_text.splitlines() if line.strip()
            ][-5:]
            logger.debug(
                f"hook_event: type=stop, agent_id={agent.id}, "
                f"tail_5_lines={tail_lines!r}"
            )

        # Check for stale notification turn to replace (created by
        # notification hook before this stop hook arrived)
        stale_notification_turn = None
        if current_command.turns:
            for t in reversed(current_command.turns):
                if (
                    t.actor == TurnActor.AGENT
                    and t.intent == TurnIntent.QUESTION
                    and t.text == "Claude is waiting for your input"
                ):
                    stale_notification_turn = t
                    break

        from .transcript_reconciler import _content_hash, is_content_duplicate

        agent_content_key = _content_hash("agent", full_agent_text or "")

        # Dedup guard: check if reconciler already created a turn with this
        # content (race condition — JSONL reconciliation can run between the
        # agent's response appearing in the transcript and the stop hook firing).
        existing_dup = None
        if full_agent_text and current_command.turns:
            for t in reversed(current_command.turns):
                if t.actor != TurnActor.AGENT:
                    continue
                # Tier 1: exact hash match
                if t.jsonl_entry_hash and t.jsonl_entry_hash == agent_content_key:
                    existing_dup = t
                    break
                # Tier 2: paragraph-level duck-typing for near-identical content
                # (e.g. minor whitespace/formatting differences between hook and JSONL text)
                if t.intent in (
                    TurnIntent.QUESTION,
                    TurnIntent.COMPLETION,
                    TurnIntent.END_OF_COMMAND,
                    TurnIntent.PROGRESS,
                ):
                    if is_content_duplicate(t.text, full_agent_text, actor="agent"):
                        existing_dup = t
                        logger.info(
                            f"[HOOK_RECEIVER] process_stop dedup: fuzzy match against "
                            f"turn {t.id} (paragraph similarity) — skipping duplicate"
                        )
                        break

        if existing_dup:
            # Reconciler already has this turn — update it in-place rather than
            # creating a duplicate. Upgrade intent if the stop hook detected a
            # more specific one (e.g. QUESTION vs PROGRESS).
            if (
                existing_dup.intent == TurnIntent.PROGRESS
                and intent_result.intent != TurnIntent.PROGRESS
            ):
                existing_dup.intent = intent_result.intent
            if intent_result.intent == TurnIntent.QUESTION:
                existing_dup.question_text = full_agent_text or ""
                existing_dup.question_source_type = "free_text"
            if not existing_dup.jsonl_entry_hash:
                existing_dup.jsonl_entry_hash = agent_content_key
            _helpers.db.session.commit()
            logger.info(
                f"[HOOK_RECEIVER] process_stop dedup: reusing existing turn {existing_dup.id} "
                f"(hash={agent_content_key}) instead of creating duplicate"
            )
            # Still drive lifecycle for COMPLETION/END_OF_COMMAND — the reconciler
            # may not have driven it (e.g. lifecycle failed on first attempt).
            # complete_command is idempotent via the state machine; if already
            # COMPLETE, the transition fails harmlessly and gets caught below.
            if intent_result.intent in (
                TurnIntent.END_OF_COMMAND,
                TurnIntent.COMPLETION,
            ):
                try:
                    trigger = (
                        "hook:stop:end_of_command"
                        if intent_result.intent == TurnIntent.END_OF_COMMAND
                        else "hook:stop"
                    )
                    lifecycle.complete_command(
                        command=current_command,
                        trigger=trigger,
                        agent_text=completion_text,
                        intent=intent_result.intent,
                    )
                    if completion_text != full_agent_text:
                        current_command.full_output = full_agent_text
                    _helpers.db.session.commit()
                except Exception as e:
                    _helpers.db.session.rollback()
                    logger.debug(
                        f"[HOOK_RECEIVER] process_stop dedup lifecycle (expected if already complete): {e}"
                    )
        elif all_captured_by_progress:
            # All agent text was captured as PROGRESS turns — upgrade the
            # last PROGRESS turn's intent rather than creating a duplicate
            # COMPLETION turn with the same content.
            progress_turns = [
                t
                for t in current_command.turns
                if t.actor == TurnActor.AGENT and t.intent == TurnIntent.PROGRESS
            ]
            if progress_turns:
                last_progress = progress_turns[-1]
                if intent_result.intent != TurnIntent.PROGRESS:
                    last_progress.intent = intent_result.intent
                if intent_result.intent == TurnIntent.QUESTION:
                    last_progress.question_text = full_agent_text or ""
                    last_progress.question_source_type = "free_text"
                if not last_progress.jsonl_entry_hash:
                    last_progress.jsonl_entry_hash = agent_content_key
                _helpers.db.session.commit()
                logger.info(
                    f"[HOOK_RECEIVER] process_stop: all text captured by PROGRESS — "
                    f"upgraded turn {last_progress.id} to {intent_result.intent.value}"
                )
                if intent_result.intent in (
                    TurnIntent.END_OF_COMMAND,
                    TurnIntent.COMPLETION,
                ):
                    try:
                        trigger = (
                            "hook:stop:end_of_command"
                            if intent_result.intent == TurnIntent.END_OF_COMMAND
                            else "hook:stop"
                        )
                        lifecycle.complete_command(
                            command=current_command,
                            trigger=trigger,
                            agent_text=completion_text,
                            intent=intent_result.intent,
                        )
                        if completion_text != full_agent_text:
                            current_command.full_output = full_agent_text
                        _helpers.db.session.commit()
                    except Exception as e:
                        _helpers.db.session.rollback()
                        logger.debug(
                            f"[HOOK_RECEIVER] process_stop progress-upgrade lifecycle: {e}"
                        )
        elif intent_result.intent == TurnIntent.QUESTION:
            if stale_notification_turn:
                stale_notification_turn.text = full_agent_text or ""
                stale_notification_turn.question_text = full_agent_text or ""
                stale_notification_turn.question_source_type = "free_text"
                stale_notification_turn.jsonl_entry_hash = agent_content_key
            else:
                turn = Turn(
                    command_id=current_command.id,
                    actor=TurnActor.AGENT,
                    intent=TurnIntent.QUESTION,
                    text=full_agent_text or "",
                    question_text=full_agent_text or "",
                    question_source_type="free_text",
                    is_internal=is_team_internal_content(full_agent_text),
                    jsonl_entry_hash=agent_content_key,
                )
                _helpers.db.session.add(turn)
            # Commit turn FIRST — turn must survive even if state transition fails.
            _helpers.db.session.commit()
        elif intent_result.intent == TurnIntent.END_OF_COMMAND:
            if stale_notification_turn:
                stale_notification_turn.text = completion_text or ""
                stale_notification_turn.intent = TurnIntent.END_OF_COMMAND
                stale_notification_turn.question_text = None
                stale_notification_turn.question_source_type = None
                stale_notification_turn.jsonl_entry_hash = agent_content_key
            # Commit turn FIRST — turn must survive even if complete_command fails.
            _helpers.db.session.commit()
            # Now attempt completion in a separate commit scope.
            try:
                lifecycle.complete_command(
                    command=current_command,
                    trigger="hook:stop:end_of_command",
                    agent_text=completion_text,
                    intent=TurnIntent.END_OF_COMMAND,
                )
                # Preserve full output even when completion turn is deduplicated
                if completion_text != full_agent_text:
                    current_command.full_output = full_agent_text
                _helpers.db.session.commit()
            except Exception as e:
                _helpers.db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_stop complete_command (END_OF_COMMAND) failed: "
                    f"error={e} — turn preserved"
                )
        else:
            if stale_notification_turn:
                stale_notification_turn.text = completion_text or ""
                stale_notification_turn.intent = TurnIntent.COMPLETION
                stale_notification_turn.question_text = None
                stale_notification_turn.question_source_type = None
                stale_notification_turn.jsonl_entry_hash = agent_content_key
            # Commit turn FIRST — turn must survive even if complete_command fails.
            _helpers.db.session.commit()
            # Now attempt completion in a separate commit scope.
            try:
                lifecycle.complete_command(
                    command=current_command,
                    trigger="hook:stop",
                    agent_text=completion_text,
                )
                if completion_text != full_agent_text:
                    current_command.full_output = full_agent_text
                _helpers.db.session.commit()
            except Exception as e:
                _helpers.db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_stop complete_command (COMPLETION) failed: "
                    f"error={e} — turn preserved"
                )

        # Two-commit pattern complete: turns committed above, state transitions
        # (complete_command or QUESTION handling below) in separate commit scopes.
        _helpers._trigger_priority_scoring()

        # Channel delivery: relay agent responses and drain queued messages.
        # Single lookup for the delivery service used by both relay and drain.
        try:
            from flask import current_app as _cd_app

            ch_delivery = _cd_app.extensions.get("channel_delivery_service")
        except Exception:
            ch_delivery = None

        logger.info(
            f"[RELAY_FORENSIC] process_stop channel relay check: "
            f"agent_id={agent.id}, intent={intent_result.intent.value}, "
            f"ch_delivery={'yes' if ch_delivery else 'no'}, "
            f"cmd_state={current_command.state.value}"
        )

        # Channel relay: relay agent responses to the channel.
        # relay_agent_response handles intent filtering internally —
        # channel-prompted agents relay all intents except PROGRESS,
        # non-channel-prompted agents relay only COMPLETION/END_OF_COMMAND.
        if ch_delivery and intent_result.intent != TurnIntent.PROGRESS:
            try:
                # Find the most recent agent turn for source tracking
                relay_turn_id = None
                if current_command.turns:
                    for t in reversed(current_command.turns):
                        if t.actor == TurnActor.AGENT and t.intent in (
                            TurnIntent.COMPLETION,
                            TurnIntent.END_OF_COMMAND,
                            TurnIntent.QUESTION,
                        ):
                            relay_turn_id = t.id
                            break
                ch_delivery.relay_agent_response(
                    agent=agent,
                    turn_text=completion_text or full_agent_text or "",
                    turn_intent=intent_result.intent,
                    turn_id=relay_turn_id,
                    command_id=current_command.id,
                )
            except Exception as ch_err:
                logger.warning(f"Channel relay failed (non-fatal): {ch_err}")

        # Queue drain: deliver oldest queued channel message if agent
        # is now in a safe state after completion (FR13).
        if ch_delivery and current_command.state == CommandState.COMPLETE:
            try:
                ch_delivery.drain_queue(agent)
            except Exception as qd_err:
                logger.warning(f"Channel queue drain failed (non-fatal): {qd_err}")

        pending = lifecycle.get_pending_summarisations()

        # Now attempt state transition (for QUESTION intent only — complete_command
        # handles its own transitions advisorily and already ran above).
        if intent_result.intent == TurnIntent.QUESTION:
            try:
                lifecycle.update_command_state(
                    command=current_command,
                    to_state=CommandState.AWAITING_INPUT,
                    trigger="hook:stop:question_detected",
                    confidence=intent_result.confidence,
                )
                _helpers.db.session.commit()
            except Exception as e:
                _helpers.db.session.rollback()
                logger.warning(
                    f"[HOOK_RECEIVER] process_stop state transition failed: "
                    f"from={current_command.state.value} actor=AGENT intent=QUESTION "
                    f"error={e} — turn preserved"
                )

        # Broadcast agent turn for voice chat IMMEDIATELY after commit —
        # before card_refresh and summarisation so the chat updates first.
        # Summarisation involves blocking LLM calls that can delay turn
        # visibility by several seconds.
        if current_command.turns:
            broadcast_turn = None
            for t in reversed(current_command.turns):
                if t.actor == TurnActor.AGENT and t.intent in (
                    TurnIntent.QUESTION,
                    TurnIntent.COMPLETION,
                    TurnIntent.END_OF_COMMAND,
                ):
                    broadcast_turn = t
                    break
            # Fallback: when progress dedup captured all agent text and no
            # COMPLETION turn was created, broadcast the last PROGRESS turn
            # so the voice chat gets the agent's response via SSE.
            if not broadcast_turn:
                for t in reversed(current_command.turns):
                    if (
                        t.actor == TurnActor.AGENT
                        and t.intent == TurnIntent.PROGRESS
                        and t.text
                    ):
                        broadcast_turn = t
                        break
            if broadcast_turn:
                _helpers._broadcast_turn_created(
                    agent,
                    broadcast_turn.text,
                    current_command,
                    tool_input=broadcast_turn.tool_input,
                    turn_id=broadcast_turn.id,
                    intent=broadcast_turn.intent.value,
                    question_source_type=broadcast_turn.question_source_type,
                )

        _helpers.broadcast_card_refresh(agent, "stop")
        _helpers._execute_pending_summarisations(pending)

        actual_state = current_command.state.value
        _helpers._broadcast_state_change(
            agent, "stop", actual_state, message=f"\u2192 {actual_state.upper()}"
        )

        # Send completion notification AFTER summarisation so it contains
        # the AI-generated summary instead of raw transcript text.
        if current_command.state == CommandState.COMPLETE:
            _helpers._send_completion_notification(agent, current_command)

        logger.info(
            f"hook_event: type=stop, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state={actual_state}"
        )
        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=True,
            new_state=actual_state,
        )
    except Exception as e:
        logger.exception(f"Error processing stop: {e}")
        _helpers.db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
