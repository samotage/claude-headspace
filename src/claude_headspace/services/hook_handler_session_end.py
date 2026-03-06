"""Hook handler for session_end events.

Extracted from hook_receiver.py for modularity.
"""

import logging
from datetime import datetime, timezone

from ..models.agent import Agent
from ..models.command import CommandState
from . import hook_receiver_helpers as _helpers
from .hook_agent_state import get_agent_hook_state
from .hook_receiver_types import HookEventResult, HookEventType, get_receiver_state

logger = logging.getLogger(__name__)


def process_session_end(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    state = get_receiver_state()
    state.record_event(HookEventType.SESSION_END)
    try:
        now = datetime.now(timezone.utc)
        logger.warning(
            f"SESSION_END_KILL: agent_id={agent.id} uuid={agent.session_uuid} "
            f"claude_session_id={claude_session_id} "
            f"tmux_pane={agent.tmux_pane_id} project={agent.project.name if agent.project else 'N/A'} "
            f"age={(now - agent.started_at).total_seconds() if agent.started_at else 'N/A'}s"
        )
        agent.last_seen_at = now
        agent.ended_at = now
        get_agent_hook_state().clear_awaiting_tool(agent.id)
        get_agent_hook_state().clear_transcript_position(agent.id)
        get_agent_hook_state().consume_progress_texts(agent.id)

        # Clear skill injection idempotency record
        from .skill_injector import clear_injection_record

        clear_injection_record(agent.id)

        # Centralized cache cleanup (correlator, hook_agent_state, commander, watchdog)
        from .session_correlator import invalidate_agent_caches

        invalidate_agent_caches(agent.id, session_id=claude_session_id)
        try:
            from flask import current_app

            watchdog = current_app.extensions.get("tmux_watchdog")
            if watchdog:
                watchdog.unregister_agent(agent.id)
        except RuntimeError:
            pass

        lifecycle = _helpers._get_lifecycle_manager()
        current_command = lifecycle.get_current_command(agent)
        if current_command:
            lifecycle.complete_command(current_command, trigger="hook:session_end")
        pending = lifecycle.get_pending_summarisations()

        # Phase 2: Reconcile JSONL transcript to backfill missed turns
        try:
            from .transcript_reconciler import (
                broadcast_reconciliation,
                reconcile_agent_session,
            )

            recon_result = reconcile_agent_session(agent)
            if recon_result["created"]:
                logger.info(
                    f"session_end reconciliation: agent_id={agent.id}, "
                    f"created={len(recon_result['created'])} turns from JSONL"
                )
        except Exception as e:
            recon_result = None
            logger.warning(f"Session-end reconciliation failed: {e}")

        _helpers.db.session.commit()
        _helpers.broadcast_card_refresh(agent, "session_end")
        _helpers._execute_pending_summarisations(pending)

        # Phase 3: Broadcast reconciliation results after commit
        if recon_result and recon_result.get("created"):
            try:
                broadcast_reconciliation(agent, recon_result)
            except Exception as e:
                logger.warning(f"Session-end reconciliation broadcast failed: {e}")

        _helpers._broadcast_state_change(
            agent, "session_end", CommandState.COMPLETE.value, message="Session ended"
        )
        try:
            from .broadcaster import get_broadcaster

            get_broadcaster().broadcast(
                "session_ended",
                {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "session_uuid": str(agent.session_uuid),
                    "timestamp": now.isoformat(),
                },
            )
        except Exception as e:
            logger.warning(f"Session ended broadcast failed: {e}")

        logger.info(
            f"hook_event: type=session_end, agent_id={agent.id}, session_id={claude_session_id}"
        )
        return HookEventResult(
            success=True,
            agent_id=agent.id,
            state_changed=True,
            new_state=CommandState.COMPLETE.value,
        )
    except Exception as e:
        logger.exception(f"Error processing session_end: {e}")
        _helpers.db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))
