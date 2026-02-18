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
from ..models.task import TaskState
from ..models.turn import Turn, TurnActor, TurnIntent
from .intent_detector import detect_agent_intent, detect_user_intent
from .state_machine import InvalidTransitionError
from .team_content_detector import is_team_internal_content

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


def reconcile_transcript_entries(agent, task, entries):
    """Reconcile JSONL transcript entries against existing Turns.

    Args:
        agent: Agent record
        task: Current Task record
        entries: List of TranscriptEntry objects with timestamps

    Returns:
        dict with keys:
            updated: list of (turn_id, old_timestamp, new_timestamp) tuples
            created: list of turn_id for newly created turns
    """
    result = {"updated": [], "created": []}

    if not entries:
        return result

    # Get recent turns for this task within the match window
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=MATCH_WINDOW_SECONDS)
    recent_turns = (
        Turn.query
        .filter(Turn.task_id == task.id, Turn.timestamp >= cutoff)
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
        content_key = _content_hash(actor, entry.content.strip())
        legacy_key = _legacy_content_hash(actor, entry.content.strip())

        # Try new hash first, fall back to legacy for migration compatibility
        matched_turn = turn_index.pop(content_key, None)
        if not matched_turn:
            matched_turn = turn_index.pop(legacy_key, None)

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
            turn_text = entry.content.strip()
            if actor == "user":
                intent_result = detect_user_intent(turn_text, task.state)
                detected_intent = intent_result.intent
            else:
                intent_result = detect_agent_intent(turn_text, inference_service=None)
                detected_intent = intent_result.intent
            turn = Turn(
                task_id=task.id,
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
            # Feed recovered turns with state-changing intents into lifecycle
            _apply_recovered_turn_lifecycle(agent, task, turn, intent_result)

    if result["updated"] or result["created"]:
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
                task_instr = None
                if turn.task:
                    task_instr = turn.task.instruction
                broadcaster.broadcast("turn_created", {
                    "agent_id": agent.id,
                    "project_id": agent.project_id,
                    "text": turn.text,
                    "actor": turn.actor.value,
                    "intent": turn.intent.value,
                    "task_id": turn.task_id,
                    "task_instruction": task_instr,
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
    from ..models.task import Task

    if not agent.transcript_path:
        return {"updated": [], "created": []}

    # Read ALL entries from position 0
    entries, _ = read_new_entries_from_position(agent.transcript_path, position=0)
    if not entries:
        return {"updated": [], "created": []}

    # Get ALL turns for this agent's tasks (no time window)
    task_ids = [t.id for t in Task.query.filter_by(agent_id=agent.id).all()]
    existing_turns = Turn.query.filter(Turn.task_id.in_(task_ids)).all() if task_ids else []

    # Build hash index from existing turns using both new and legacy hashes
    existing_hashes = set()
    for turn in existing_turns:
        new_h = _content_hash(turn.actor.value, turn.text)
        old_h = _legacy_content_hash(turn.actor.value, turn.text)
        existing_hashes.add(new_h)
        existing_hashes.add(old_h)
        if turn.jsonl_entry_hash:
            existing_hashes.add(turn.jsonl_entry_hash)

    # Find the most recent task for creating new turns
    latest_task = Task.query.filter_by(agent_id=agent.id).order_by(Task.id.desc()).first()
    if not latest_task:
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
            intent_result = detect_user_intent(turn_text, latest_task.state)
            detected_intent = intent_result.intent
        else:
            intent_result = detect_agent_intent(turn_text, inference_service=None)
            detected_intent = intent_result.intent
        turn = Turn(
            task_id=latest_task.id,
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

    return result


def _apply_recovered_turn_lifecycle(agent, task, turn, intent_result):
    """Feed a recovered turn into the TaskLifecycleManager for state transitions.

    Only triggers state changes for state-relevant intents (QUESTION, COMPLETION,
    END_OF_TASK). PROGRESS turns are informational and don't change state.
    The turn is already committed — a failed transition cannot destroy it.
    """
    if turn.intent not in (TurnIntent.QUESTION, TurnIntent.COMPLETION, TurnIntent.END_OF_TASK):
        return

    try:
        from flask import current_app
        lifecycle = current_app.extensions.get("task_lifecycle")
        if not lifecycle:
            return

        if turn.intent == TurnIntent.QUESTION:
            lifecycle.update_task_state(
                task=task, to_state=TaskState.AWAITING_INPUT,
                trigger="reconciler:recovered_turn",
                confidence=intent_result.confidence,
            )
        elif turn.intent in (TurnIntent.COMPLETION, TurnIntent.END_OF_TASK):
            lifecycle.complete_task(
                task=task, trigger="reconciler:recovered_turn",
                agent_text=turn.text, intent=turn.intent,
            )
        db.session.commit()
        logger.info(
            f"[RECONCILER] Recovered turn {turn.id} triggered state transition: "
            f"{task.state.value}"
        )
        # Broadcast card refresh for state change
        try:
            from .card_state import broadcast_card_refresh
            broadcast_card_refresh(agent, "reconciler")
        except Exception:
            pass
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
