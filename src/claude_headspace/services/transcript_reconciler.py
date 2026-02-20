"""Reconcile JSONL transcript entries against database Turn records.

Implements Phase 2 of the three-phase event pipeline:
- Phase 1: Hook creates Turn with timestamp=now() (approximate)
- Phase 2: THIS — reconciles against JSONL entries, corrects timestamps
- Phase 3: Broadcasts SSE updates for corrections
"""

import hashlib
import logging
import threading
from datetime import datetime, timedelta, timezone

from ..database import db
from ..models.command import CommandState
from ..models.turn import Turn, TurnActor, TurnIntent
from .intent_detector import detect_agent_intent, detect_user_intent
from .state_machine import InvalidTransitionError
from .team_content_detector import filter_skill_expansion, is_team_internal_content

logger = logging.getLogger(__name__)

# Maximum time window to search for matching hook-created turns.
# 120s is generous enough to catch delayed JSONL writes without matching stale turns.
MATCH_WINDOW_SECONDS = 120

# Per-agent reconciliation locks to prevent concurrent reconciliation
# (manual endpoint + watchdog racing).
_reconcile_locks: dict[int, threading.Lock] = {}
_reconcile_locks_guard = threading.Lock()


def get_reconcile_lock(agent_id: int) -> threading.Lock:
    """Get or create a per-agent reconciliation lock."""
    with _reconcile_locks_guard:
        if agent_id not in _reconcile_locks:
            _reconcile_locks[agent_id] = threading.Lock()
        return _reconcile_locks[agent_id]


def remove_reconcile_lock(agent_id: int) -> None:
    """Remove a per-agent reconciliation lock (cleanup on session end / reap)."""
    with _reconcile_locks_guard:
        _reconcile_locks.pop(agent_id, None)


def reconcile_transcript_entries(agent, command, entries):
    """Reconcile JSONL transcript entries against existing Turns.

    Args:
        agent: Agent record
        command: Current Command record
        entries: List of TranscriptEntry objects with timestamps

    Returns:
        dict with keys:
            updated: list of (turn_id, old_timestamp, new_timestamp) tuples
            created: list of turn_id for newly created turns
    """
    result = {"updated": [], "created": []}

    if not entries:
        return result

    # Get recent turns for this command within the match window
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=MATCH_WINDOW_SECONDS)
    recent_turns = (
        Turn.query
        .filter(Turn.command_id == command.id, Turn.timestamp >= cutoff)
        .order_by(Turn.timestamp.asc())
        .all()
    )

    # Build index of recent turns by content hash for matching.
    # Use both new (full-content) and legacy (200-char) hashes for migration compatibility.
    turn_index = {}
    for turn in recent_turns:
        new_key = _content_hash(turn.actor.value, turn.text)
        old_key = _legacy_content_hash(turn.actor.value, turn.text)
        if new_key not in turn_index:
            turn_index[new_key] = turn
        if old_key not in turn_index:
            turn_index[old_key] = turn

    for entry in entries:
        if not entry.content or not entry.content.strip():
            continue

        actor = "user" if entry.role == "user" else "agent"
        # Apply the same skill-expansion filter used in the hook receiver
        # so that content hashes match the truncated text stored in turns.
        entry_text = filter_skill_expansion(entry.content.strip()) or entry.content.strip()
        content_key = _content_hash(actor, entry_text)
        legacy_key = _legacy_content_hash(actor, entry_text)

        # Try new hash first, fall back to legacy for migration compatibility
        matched_turn = turn_index.pop(content_key, None)
        if not matched_turn:
            matched_turn = turn_index.pop(legacy_key, None)

        if matched_turn:
            # Remove the other key for this turn to prevent double-matching (H3).
            # Each turn has two keys (new + legacy); popping one leaves the other.
            other_new = _content_hash(matched_turn.actor.value, matched_turn.text)
            other_old = _legacy_content_hash(matched_turn.actor.value, matched_turn.text)
            turn_index.pop(other_new, None)
            turn_index.pop(other_old, None)

        if matched_turn and entry.timestamp:
            # Phase 2: Update timestamp to JSONL value
            old_ts = matched_turn.timestamp
            if old_ts != entry.timestamp:
                matched_turn.timestamp = entry.timestamp
                matched_turn.timestamp_source = "jsonl"
                matched_turn.jsonl_entry_hash = content_key
                result["updated"].append((matched_turn.id, old_ts, entry.timestamp))
                logger.info(
                    f"[RECONCILER] Updated turn {matched_turn.id} timestamp: "
                    f"{old_ts.isoformat()} -> {entry.timestamp.isoformat()}"
                )
        elif matched_turn and not entry.timestamp:
            # Matched but no JSONL timestamp — just record the hash for dedup
            if not matched_turn.jsonl_entry_hash:
                matched_turn.jsonl_entry_hash = content_key
        elif not matched_turn:
            # New entry not seen via hooks — create Turn with proper intent detection
            turn_text = entry_text  # already filtered by filter_skill_expansion above
            if actor == "user":
                intent_result = detect_user_intent(turn_text, command.state)
                detected_intent = intent_result.intent
            else:
                intent_result = detect_agent_intent(turn_text, inference_service=None)
                detected_intent = intent_result.intent
            turn = Turn(
                command_id=command.id,
                actor=TurnActor.USER if actor == "user" else TurnActor.AGENT,
                intent=detected_intent,
                text=turn_text,
                timestamp=entry.timestamp or datetime.now(timezone.utc),
                timestamp_source="jsonl" if entry.timestamp else "server",
                jsonl_entry_hash=content_key,
                is_internal=is_team_internal_content(turn_text),
            )
            db.session.add(turn)
            db.session.flush()
            result["created"].append(turn.id)
            logger.info(
                f"[RECONCILER] Created turn {turn.id} from JSONL entry "
                f"(agent={agent.id}, intent={turn.intent.value}, hash={content_key}) "
                f"— no matching hook-created turn found"
            )
            # Commit turn BEFORE lifecycle call — the two-commit pattern.
            # This also commits any pending timestamp updates from earlier iterations.
            db.session.commit()
            # Feed recovered turns with state-changing intents into lifecycle.
            # The turn is now safe in DB — a failed transition cannot destroy it.
            _apply_recovered_turn_lifecycle(agent, command, turn, intent_result)

    # Commit any remaining timestamp updates not yet committed
    if result["updated"]:
        db.session.commit()

    return result


def broadcast_reconciliation(agent, reconciliation_result):
    """Broadcast SSE updates after transcript reconciliation (Phase 3).

    Sends:
    - turn_updated events for timestamp corrections (existing turns)
    - turn_created events for newly discovered turns
    """
    from .broadcaster import get_broadcaster

    if not reconciliation_result["updated"] and not reconciliation_result["created"]:
        return

    try:
        broadcaster = get_broadcaster()
    except Exception as e:
        logger.warning(f"Reconciliation broadcast failed (no broadcaster): {e}")
        return

    # Broadcast timestamp corrections for existing turns
    for turn_id, old_ts, new_ts in reconciliation_result["updated"]:
        try:
            broadcaster.broadcast("turn_updated", {
                "agent_id": agent.id,
                "project_id": agent.project_id,
                "turn_id": turn_id,
                "timestamp": new_ts.isoformat(),
                "update_type": "timestamp_correction",
            })
        except Exception as e:
            logger.warning(f"Reconciliation turn_updated broadcast failed: {e}")

    # Broadcast newly created turns
    for turn_id in reconciliation_result["created"]:
        try:
            turn = db.session.get(Turn, turn_id)
            if turn:
                command_instr = None
                if turn.command:
                    command_instr = turn.command.instruction
                broadcaster.broadcast("turn_created", {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "text": turn.text,
                    "actor": turn.actor.value,
                    "intent": turn.intent.value,
                    "command_id": turn.command_id,
                    "command_instruction": command_instr,
                    "turn_id": turn.id,
                    "question_source_type": turn.question_source_type,
                    "timestamp": turn.timestamp.isoformat(),
                })
        except Exception as e:
            logger.warning(f"Reconciliation turn_created broadcast failed: {e}")


def _content_hash(actor, text):
    """Generate a content-based hash for dedup matching.

    Uses the full normalized text + actor to produce a short hash suitable
    for matching hook-created turns against JSONL entries.
    """
    normalized = f"{actor}:{text.strip().lower()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _legacy_content_hash(actor, text):
    """Generate the old 200-char content hash for migration compatibility.

    Existing turns in the DB may have hashes computed with the old format.
    This function preserves backward compatibility during the transition period.
    """
    normalized = f"{actor}:{text[:200].strip().lower()}"
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def reconcile_agent_session(agent):
    """Full-session reconciliation — run at session end.

    Reads ALL JSONL entries for the agent's transcript and creates
    Turn records for any entries not already captured by hooks.

    Args:
        agent: Agent record with transcript_path

    Returns:
        dict with keys:
            updated: list (always empty for full-session mode)
            created: list of turn_id for newly created turns
    """
    from .transcript_reader import read_new_entries_from_position
    from ..models.command import Command

    if not agent.transcript_path:
        return {"updated": [], "created": []}

    # Read ALL entries from position 0
    entries, _ = read_new_entries_from_position(agent.transcript_path, position=0)
    if not entries:
        return {"updated": [], "created": []}

    # Get ALL turns for this agent's commands (no time window)
    command_ids = [t.id for t in Command.query.filter_by(agent_id=agent.id).all()]
    existing_turns = Turn.query.filter(Turn.command_id.in_(command_ids)).all() if command_ids else []

    # Build hash index from existing turns using both new and legacy hashes
    existing_hashes = set()
    for turn in existing_turns:
        new_h = _content_hash(turn.actor.value, turn.text)
        old_h = _legacy_content_hash(turn.actor.value, turn.text)
        existing_hashes.add(new_h)
        existing_hashes.add(old_h)
        if turn.jsonl_entry_hash:
            existing_hashes.add(turn.jsonl_entry_hash)

    # Find the most recent command for creating new turns
    latest_command = Command.query.filter_by(agent_id=agent.id).order_by(Command.id.desc()).first()
    if not latest_command:
        return {"updated": [], "created": []}

    result = {"updated": [], "created": []}
    for entry in entries:
        if not entry.content or not entry.content.strip():
            continue
        actor = "user" if entry.role == "user" else "agent"
        content_key = _content_hash(actor, entry.content.strip())
        legacy_key = _legacy_content_hash(actor, entry.content.strip())
        if content_key in existing_hashes or legacy_key in existing_hashes:
            continue
        existing_hashes.add(content_key)
        existing_hashes.add(legacy_key)
        turn_text = entry.content.strip()
        if actor == "user":
            intent_result = detect_user_intent(turn_text, latest_command.state)
            detected_intent = intent_result.intent
        else:
            intent_result = detect_agent_intent(turn_text, inference_service=None)
            detected_intent = intent_result.intent
        turn = Turn(
            command_id=latest_command.id,
            actor=TurnActor.USER if actor == "user" else TurnActor.AGENT,
            intent=detected_intent,
            text=turn_text,
            timestamp=entry.timestamp or datetime.now(timezone.utc),
            timestamp_source="jsonl" if entry.timestamp else "server",
            jsonl_entry_hash=content_key,
            is_internal=is_team_internal_content(turn_text),
        )
        db.session.add(turn)
        db.session.flush()
        result["created"].append(turn.id)
        logger.info(
            f"[RECONCILER] Created turn {turn.id} from JSONL entry "
            f"(agent={agent.id}, intent={turn.intent.value}, hash={content_key}) "
            f"— no matching hook-created turn found (session reconciliation)"
        )
        # Commit turn BEFORE lifecycle call — the two-commit pattern.
        db.session.commit()
        # Feed recovered turns into lifecycle (same as reconcile_transcript_entries).
        _apply_recovered_turn_lifecycle(agent, latest_command, turn, intent_result)

    return result


def _apply_recovered_turn_lifecycle(agent, command, turn, intent_result):
    """Feed a recovered turn into the CommandLifecycleManager for state transitions.

    Only triggers state changes for state-relevant intents (QUESTION, COMPLETION,
    END_OF_COMMAND). PROGRESS turns are informational and don't change state.

    IMPORTANT: The caller MUST commit the turn to the database BEFORE calling
    this function. This ensures a failed state transition rollback cannot
    destroy the turn (the "two-commit" pattern).
    """
    if turn.intent not in (TurnIntent.QUESTION, TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND):
        return

    try:
        from flask import current_app
        lifecycle = current_app.extensions.get("command_lifecycle")
        if not lifecycle:
            return

        from_state = command.state
        if turn.intent == TurnIntent.QUESTION:
            lifecycle.update_command_state(
                command=command, to_state=CommandState.AWAITING_INPUT,
                trigger="reconciler:recovered_turn",
                confidence=intent_result.confidence,
            )
        elif turn.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND):
            # Set full_output directly — do NOT pass agent_text to complete_command
            # because the recovered turn already exists (committed above via
            # two-commit pattern). Passing agent_text would create a duplicate.
            command.full_output = turn.text
            lifecycle.complete_command(
                command=command, trigger="reconciler:recovered_turn",
                agent_text="", intent=turn.intent,
            )
        # Drain pending summarisation requests to prevent leaking into next
        # hook event's batch (lifecycle manager is a shared singleton).
        lifecycle.get_pending_summarisations()
        db.session.commit()
        logger.info(
            f"[RECONCILER] Recovered turn {turn.id} triggered state transition: "
            f"{from_state.value} -> {command.state.value}"
        )
        # Broadcast card refresh for state change
        try:
            from .card_state import broadcast_card_refresh
            broadcast_card_refresh(agent, "reconciler")
        except Exception:
            logger.debug("Card refresh broadcast failed during reconciliation")
    except InvalidTransitionError as e:
        db.session.rollback()
        logger.warning(
            f"[RECONCILER] Recovered turn {turn.id} state transition failed: "
            f"{e} — turn preserved"
        )
    except Exception as e:
        db.session.rollback()
        logger.warning(
            f"[RECONCILER] Recovered turn {turn.id} lifecycle integration failed: {e}"
        )
