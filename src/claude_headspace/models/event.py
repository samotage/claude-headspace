"""Event model for audit trail."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from ..database import db


class Event(db.Model):
    """
    Represents an audit trail event.

    Events can reference any combination of project, agent, command, and turn.
    All foreign keys are nullable and use SET NULL on delete to preserve
    the audit trail even when referenced entities are deleted.
    """

    __tablename__ = "events"

    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    # FK design: SET NULL on delete — events form an audit trail with independent
    # value. Retaining event records even when referenced entities are deleted
    # preserves the historical record for debugging and analytics.
    project_id: Mapped[int | None] = mapped_column(
        ForeignKey("projects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    agent_id: Mapped[int | None] = mapped_column(
        ForeignKey("agents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    command_id: Mapped[int | None] = mapped_column(
        ForeignKey("commands.id", ondelete="SET NULL"), nullable=True, index=True
    )
    turn_id: Mapped[int | None] = mapped_column(
        ForeignKey("turns.id", ondelete="SET NULL"), nullable=True, index=True
    )
    event_type: Mapped[str] = mapped_column(nullable=False, index=True)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    def __repr__(self) -> str:
        return f"<Event id={self.id} type={self.event_type} timestamp={self.timestamp}>"


# Event type constants — kept here for backward compatibility with imports
# from models.event. The authoritative, complete definition is in
# services/event_schemas.py (which event_writer.py uses).
class EventType:
    """Supported event types."""

    # Core events
    SESSION_REGISTERED = "session_registered"
    SESSION_ENDED = "session_ended"
    TURN_DETECTED = "turn_detected"
    STATE_TRANSITION = "state_transition"
    OBJECTIVE_CHANGED = "objective_changed"
    NOTIFICATION_SENT = "notification_sent"

    # Generic hook event (legacy)
    HOOK_RECEIVED = "hook_received"

    # Specific hook events
    HOOK_SESSION_START = "hook_session_start"
    HOOK_SESSION_END = "hook_session_end"
    HOOK_USER_PROMPT = "hook_user_prompt"
    HOOK_STOP = "hook_stop"
    HOOK_NOTIFICATION = "hook_notification"
    HOOK_POST_TOOL_USE = "hook_post_tool_use"

    # Content pipeline events
    QUESTION_DETECTED = "question_detected"


# Composite indexes for common query patterns
Index("ix_events_project_id_timestamp", Event.project_id, Event.timestamp)
Index("ix_events_agent_id_timestamp", Event.agent_id, Event.timestamp)
Index("ix_events_event_type_timestamp", Event.event_type, Event.timestamp)
