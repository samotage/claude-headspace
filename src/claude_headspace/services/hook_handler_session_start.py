"""Hook handler for session_start events.

Extracted from hook_receiver.py for modularity.
"""

import logging
from datetime import datetime, timezone

from ..models.agent import Agent
from . import hook_receiver_helpers as _helpers
from .hook_agent_state import get_agent_hook_state
from .hook_receiver_proxies import _progress_texts_for_agent, _transcript_positions
from .hook_receiver_types import HookEventResult, HookEventType, get_receiver_state

logger = logging.getLogger(__name__)


def process_session_start(
    agent: Agent,
    claude_session_id: str,
    transcript_path: str | None = None,
    tmux_pane_id: str | None = None,
    tmux_session: str | None = None,
    persona_slug: str | None = None,
    previous_agent_id: str | None = None,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_START)
    try:
        agent.last_seen_at = datetime.now(timezone.utc)
        agent.ended_at = None  # Clear ended state for new session

        # Assign persona to agent by looking up the Persona record by slug
        if persona_slug:
            try:
                from ..models.persona import Persona

                persona = Persona.query.filter_by(slug=persona_slug).first()
                if persona:
                    agent.persona_id = persona.id
                    logger.info(
                        f"session_start: persona assigned — slug={persona_slug}, "
                        f"persona_id={persona.id}, agent_id={agent.id}"
                    )
                    # Update any active ChannelMembership rows for this persona
                    # to point to the new agent (fixes stale agent_id after handoff
                    # or new session — Finding F10).
                    try:
                        from ..models.channel_membership import ChannelMembership

                        updated = (
                            ChannelMembership.query.filter_by(
                                persona_id=persona.id, status="active"
                            )
                            .filter(ChannelMembership.agent_id != agent.id)
                            .update({"agent_id": agent.id})
                        )
                        if updated:
                            logger.info(
                                f"session_start: updated {updated} channel membership(s) "
                                f"agent_id -> {agent.id} for persona {persona.slug}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"session_start: channel membership update failed "
                            f"for persona {persona.slug}: {e}"
                        )
                else:
                    logger.warning(
                        f"session_start: unrecognised persona_slug={persona_slug}, "
                        f"agent_id={agent.id} — agent created without persona"
                    )
            except Exception as e:
                logger.error(
                    f"session_start: DB error during Persona lookup for "
                    f"slug={persona_slug}, agent_id={agent.id}: {e}"
                )

        # Assign previous_agent_id (convert string from hook payload to int)
        if previous_agent_id:
            try:
                agent.previous_agent_id = int(previous_agent_id)
                logger.info(
                    f"session_start: previous_agent_id={previous_agent_id} "
                    f"set on agent_id={agent.id}"
                )
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"session_start: invalid previous_agent_id={previous_agent_id!r}, "
                    f"agent_id={agent.id}: {e}"
                )
        # Always update transcript_path — context compression creates a new
        # Claude session (and new JSONL file).  The old guard `not agent.transcript_path`
        # caused the agent to read a stale file for the rest of its lifetime.
        if transcript_path:
            agent.transcript_path = transcript_path
        # Track the current Claude session ID so correlator/reconciler use the right file
        if claude_session_id:
            agent.claude_session_id = claude_session_id

        # Reset transcript position tracking for new session
        _transcript_positions.pop(agent.id, None)
        _progress_texts_for_agent.pop(agent.id, None)

        # Store tmux pane ID and register with availability tracker + watchdog
        if tmux_pane_id:
            agent.tmux_pane_id = tmux_pane_id
            try:
                from flask import current_app

                availability = current_app.extensions.get("commander_availability")
                if availability:
                    availability.register_agent(agent.id, tmux_pane_id)
                watchdog = current_app.extensions.get("tmux_watchdog")
                if watchdog:
                    watchdog.register_agent(agent.id, tmux_pane_id)
            except RuntimeError:
                logger.debug("No app context for commander_availability/tmux_watchdog")

        # Store tmux session name for dashboard attach action
        if tmux_session and not agent.tmux_session:
            agent.tmux_session = tmux_session

        _helpers.db.session.commit()
        _helpers.broadcast_card_refresh(agent, "session_start")

        # Emit synthetic turn listing recent handoffs for persona-backed agents.
        # This runs after persona assignment is committed so the dashboard gets
        # visibility into prior handoffs. The agent never sees this — it is
        # dashboard-only via SSE.
        if agent.persona_id:
            try:
                from flask import current_app as _app

                detection_svc = _app.extensions.get("handoff_detection_service")
                if detection_svc:
                    detection_svc.detect_and_emit(agent)
            except Exception as e:
                logger.debug(
                    f"session_start: handoff detection failed for agent_id={agent.id}: {e}"
                )

        # Link agent to pending ChannelMembership records (FR14).
        # When add_member() spins up an agent asynchronously, the membership
        # is created with agent_id=NULL. Here we link the agent once it
        # registers via session-start, and deliver context briefing (FR14a).
        _linked_channel_memberships = []
        if agent.persona_id:
            try:
                from ..models.channel_membership import ChannelMembership

                pending_memberships = ChannelMembership.query.filter_by(
                    persona_id=agent.persona_id,
                    agent_id=None,
                    status="active",
                ).all()
                for membership in pending_memberships:
                    membership.agent_id = agent.id
                    _linked_channel_memberships.append(membership)
                    logger.info(
                        f"session_start: linked agent_id={agent.id} to "
                        f"channel_membership_id={membership.id} "
                        f"(channel_id={membership.channel_id})"
                    )
                if _linked_channel_memberships:
                    _helpers.db.session.commit()
            except Exception as e:
                logger.debug(
                    f"session_start: channel membership linking failed "
                    f"for agent_id={agent.id}: {e}"
                )

        # S11: Link agent to pending channel memberships and trigger readiness check.
        # This handles channels created via create_channel_from_personas where
        # memberships are created with agent_id=None and channels stay pending
        # until all agents register.
        if agent.persona_id:
            try:
                from flask import current_app as _app

                channel_svc = _app.extensions.get("channel_service")
                if channel_svc:
                    channel_svc.link_agent_to_pending_membership(agent)
            except Exception as e:
                logger.debug(
                    f"session_start: link_agent_to_pending_membership failed "
                    f"for agent_id={agent.id}: {e}"
                )

        # Inject persona skill files for persona-backed agents with a tmux pane
        if agent.persona_id and agent.tmux_pane_id:
            try:
                from .skill_injector import inject_persona_skills

                injected = inject_persona_skills(agent)
                if injected:
                    # Flag the agent so the next user_prompt_submit (the priming
                    # message echoed back by Claude Code) is marked is_internal.
                    get_agent_hook_state().set_skill_injection_pending(agent.id)
            except Exception as e:
                logger.error(
                    f"session_start: skill injection failed for agent_id={agent.id}: {e}"
                )

        # Deliver handoff or revival injection prompt for successor agents.
        # This runs AFTER skill injection so the successor is primed before
        # receiving the handoff/revival context.
        if agent.previous_agent_id and agent.tmux_pane_id:
            try:
                from flask import current_app as _app

                handoff_executor = _app.extensions.get("handoff_executor")
                handoff_delivered = False
                if handoff_executor:
                    injection_result = handoff_executor.deliver_injection_prompt(agent)
                    if injection_result.success:
                        handoff_delivered = True
                        logger.info(
                            f"session_start: handoff injection delivered — "
                            f"agent_id={agent.id}, predecessor_id={agent.previous_agent_id}"
                        )
                    elif injection_result.error_code != "no_handoff_record":
                        # no_handoff_record is expected for non-handoff successors
                        logger.warning(
                            f"session_start: handoff injection failed — "
                            f"agent_id={agent.id}: {injection_result.message}"
                        )

                # Revival injection: if no handoff record exists on the
                # predecessor, this is a revival successor. Inject the
                # revival instruction telling the agent to read its
                # predecessor's transcript.
                if not handoff_delivered:
                    from .revival_service import (
                        compose_revival_instruction,
                        is_revival_successor,
                    )

                    if is_revival_successor(agent):
                        revival_msg = compose_revival_instruction(
                            agent.previous_agent_id
                        )
                        from . import tmux_bridge

                        send_result = tmux_bridge.send_text(
                            agent.tmux_pane_id, revival_msg
                        )
                        if send_result.success:
                            logger.info(
                                f"session_start: revival injection delivered — "
                                f"agent_id={agent.id}, predecessor_id={agent.previous_agent_id}"
                            )
                        else:
                            logger.warning(
                                f"session_start: revival injection failed — "
                                f"agent_id={agent.id}: {send_result.error_message}"
                            )
            except RuntimeError:
                pass  # No app context
            except Exception as e:
                logger.error(
                    f"session_start: handoff/revival injection error for agent_id={agent.id}: {e}"
                )

        # Deliver context briefing for channel memberships linked earlier (FR14a).
        # This runs AFTER skill injection so the agent is primed before
        # receiving the channel context.
        if _linked_channel_memberships and agent.tmux_pane_id:
            try:
                from flask import current_app as _app

                channel_svc = _app.extensions.get("channel_service")
                if channel_svc:
                    for membership in _linked_channel_memberships:
                        channel_svc._deliver_context_briefing(membership.channel, agent)
            except Exception as e:
                logger.debug(
                    f"session_start: channel context briefing failed "
                    f"for agent_id={agent.id}: {e}"
                )

        # Commit post-injection state (prompt_injected_at) so the
        # idempotency guard survives across requests (e.g. context compression
        # re-triggering session_start for the same agent).
        _helpers.db.session.commit()

        logger.info(
            f"hook_event: type=session_start, agent_id={agent.id}, session_id={claude_session_id}"
        )
        return HookEventResult(
            success=True, agent_id=agent.id, new_state=agent.state.value
        )
    except Exception as e:
        logger.exception(f"Error processing session_start: {e}")
        _helpers.db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
