"""Reconcile JSONL transcript entries against database Turn records.

Implements Phase 2 of the three-phase event pipeline:
- Phase 1: Hook creates Turn with timestamp=now() (approximate)
- Phase 2: THIS — reconciles against JSONL entries, corrects timestamps
- Phase 3: Broadcasts SSE updates for corrections
"""

import hashlib
import logging
from datetime import datetime, timedelta, timezone

from ..database import db
from ..models.turn import Turn, TurnActor, TurnIntent

logger = logging.getLogger(__name__)

# Maximum time window to search for matching hook-created turns
MATCH_WINDOW_SECONDS = 30


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

    # Build index of recent turns by content hash for matching
    turn_index = {}
    for turn in recent_turns:
        key = _content_hash(turn.actor.value, turn.text)
        if key not in turn_index:
            turn_index[key] = turn

    for entry in entries:
        if not entry.content or not entry.content.strip():
            continue

        actor = "user" if entry.role == "user" else "agent"
        content_key = _content_hash(actor, entry.content.strip())

        matched_turn = turn_index.pop(content_key, None)

        if matched_turn and entry.timestamp:
            # Phase 2: Update timestamp to JSONL value
            old_ts = matched_turn.timestamp
            if old_ts != entry.timestamp:
                matched_turn.timestamp = entry.timestamp
                matched_turn.timestamp_source = "jsonl"
                matched_turn.jsonl_entry_hash = content_key
                result["updated"].append((matched_turn.id, old_ts, entry.timestamp))
        elif matched_turn and not entry.timestamp:
            # Matched but no JSONL timestamp — just record the hash for dedup
            if not matched_turn.jsonl_entry_hash:
                matched_turn.jsonl_entry_hash = content_key
        elif not matched_turn:
            # New entry not seen via hooks — create Turn
            turn = Turn(
                task_id=task.id,
                actor=TurnActor.USER if actor == "user" else TurnActor.AGENT,
                intent=_infer_intent(actor, entry),
                text=entry.content.strip(),
                timestamp=entry.timestamp or datetime.now(timezone.utc),
                timestamp_source="jsonl" if entry.timestamp else "server",
                jsonl_entry_hash=content_key,
            )
            db.session.add(turn)
            db.session.flush()
            result["created"].append(turn.id)

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
                    "timestamp": turn.timestamp.isoformat(),
                })
        except Exception as e:
            logger.warning(f"Reconciliation turn_created broadcast failed: {e}")


def _content_hash(actor, text):
    """Generate a content-based hash for dedup matching.

    Uses the first 200 chars of normalized text + actor to produce a
    short hash suitable for matching hook-created turns against JSONL entries.
    """
    # Use first 200 chars to handle truncation differences
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

    # Build hash index from existing turns
    existing_hashes = set()
    for turn in existing_turns:
        h = _content_hash(turn.actor.value, turn.text)
        existing_hashes.add(h)
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
        if content_key in existing_hashes:
            continue
        existing_hashes.add(content_key)
        turn = Turn(
            task_id=latest_task.id,
            actor=TurnActor.USER if actor == "user" else TurnActor.AGENT,
            intent=_infer_intent(actor, entry),
            text=entry.content.strip(),
            timestamp=entry.timestamp or datetime.now(timezone.utc),
            timestamp_source="jsonl" if entry.timestamp else "server",
            jsonl_entry_hash=content_key,
        )
        db.session.add(turn)
        db.session.flush()
        result["created"].append(turn.id)

    return result


def _infer_intent(actor, entry):
    """Infer turn intent from transcript entry context."""
    if actor == "user":
        return TurnIntent.COMMAND
    return TurnIntent.PROGRESS  # Default for unmatched agent entries
