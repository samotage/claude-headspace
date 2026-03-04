"""Transcript export service — assembles agent session and channel chat transcripts."""

import logging
import os
from datetime import datetime, timezone
from pathlib import Path

from flask import current_app

from ..database import db
from ..models import (
    Agent,
    Channel,
    ChannelMembership,
    Command,
    Message,
    Turn,
    TurnActor,
)

logger = logging.getLogger(__name__)


class TranscriptExportService:
    """Assembles conversation transcripts from database records into Markdown files.

    Supports two transcript types:
    - Agent session transcripts: all turns across all commands for an agent
    - Channel chat transcripts: all messages in a channel

    Each transcript is formatted as Markdown with YAML frontmatter metadata
    and saved server-side to data/transcripts/.
    """

    def __init__(self, app=None):
        self._app = app
        self._transcripts_dir = None

    @property
    def transcripts_dir(self) -> Path:
        if self._transcripts_dir is None:
            app = self._app or current_app._get_current_object()
            app_root = app.config.get("APP_ROOT", os.getcwd())
            self._transcripts_dir = Path(app_root) / "data" / "transcripts"
            self._transcripts_dir.mkdir(parents=True, exist_ok=True)
        return self._transcripts_dir

    def assemble_agent_transcript(self, agent_id: int) -> tuple[str, str]:
        """Assemble a complete transcript for an agent session.

        Queries all Turns across all Commands for the agent, ordered
        chronologically, excluding internal turns (team sub-agent comms).

        Args:
            agent_id: The agent's database ID.

        Returns:
            Tuple of (filename, markdown_content).

        Raises:
            ValueError: If the agent is not found.
        """
        agent = db.session.get(Agent, agent_id)
        if agent is None:
            raise ValueError(f"Agent {agent_id} not found")

        # Query all non-internal turns across all commands, chronologically
        turns = (
            db.session.query(Turn)
            .join(Command, Turn.command_id == Command.id)
            .filter(
                Command.agent_id == agent_id,
                Turn.is_internal.is_(False),
            )
            .order_by(Turn.timestamp.asc())
            .all()
        )

        # Resolve persona info
        persona_slug = "unknown"
        persona_name = "Agent"
        if agent.persona:
            persona_slug = agent.persona.slug
            persona_name = agent.persona.name

        # Resolve project info
        project_name = agent.project.name if agent.project else "unknown"

        # Build participants list
        participants = [
            {"name": "Operator", "role": "operator"},
            {"name": persona_name, "role": "agent"},
        ]

        # Compute time range
        start_time = turns[0].timestamp.isoformat() if turns else None
        end_time = turns[-1].timestamp.isoformat() if turns else None

        # Build frontmatter
        now = datetime.now(timezone.utc)
        frontmatter = _build_frontmatter(
            type_="chat",
            identifier=str(agent.session_uuid),
            project=project_name,
            persona=persona_slug,
            agent_id=agent_id,
            participants=participants,
            start_time=start_time,
            end_time=end_time,
            message_count=len(turns),
            exported_at=now.isoformat(),
        )

        # Build message body
        body_lines = []
        for turn in turns:
            actor_name = "Operator" if turn.actor == TurnActor.USER else persona_name
            ts = _format_timestamp(turn.timestamp)
            body_lines.append(f"### {actor_name} — {ts}\n")
            body_lines.append(turn.text.strip() + "\n")

        content = frontmatter + "\n" + "\n".join(body_lines)

        # Generate filename and persist
        filename = _generate_filename("chat", persona_slug, agent_id, now)
        self._persist(filename, content)

        return filename, content

    def assemble_channel_transcript(self, channel_slug: str) -> tuple[str, str]:
        """Assemble a complete transcript for a channel chat.

        Queries all Messages for the channel, ordered chronologically.

        Args:
            channel_slug: The channel's slug identifier.

        Returns:
            Tuple of (filename, markdown_content).

        Raises:
            ValueError: If the channel is not found.
        """
        channel = db.session.query(Channel).filter_by(slug=channel_slug).first()
        if channel is None:
            raise ValueError(f"Channel '{channel_slug}' not found")

        # Query all messages chronologically
        messages = (
            db.session.query(Message)
            .filter(Message.channel_id == channel.id)
            .order_by(Message.sent_at.asc())
            .all()
        )

        # Resolve chair persona
        chair_membership = (
            db.session.query(ChannelMembership)
            .filter(
                ChannelMembership.channel_id == channel.id,
                ChannelMembership.is_chair.is_(True),
            )
            .first()
        )
        chair_persona_slug = "unknown"
        if chair_membership and chair_membership.persona:
            chair_persona_slug = chair_membership.persona.slug

        # Resolve project info
        project_name = channel.project.name if channel.project else "unknown"

        # Build participants from memberships
        memberships = (
            db.session.query(ChannelMembership)
            .filter(ChannelMembership.channel_id == channel.id)
            .all()
        )
        participants = []
        for m in memberships:
            name = m.persona.name if m.persona else "Unknown"
            role = "chair" if m.is_chair else "member"
            participants.append({"name": name, "role": role})

        # Compute time range
        start_time = messages[0].sent_at.isoformat() if messages else None
        end_time = messages[-1].sent_at.isoformat() if messages else None

        # Build frontmatter
        now = datetime.now(timezone.utc)
        frontmatter = _build_frontmatter(
            type_="channel",
            identifier=channel_slug,
            project=project_name,
            persona=chair_persona_slug,
            agent_id=None,
            participants=participants,
            start_time=start_time,
            end_time=end_time,
            message_count=len(messages),
            exported_at=now.isoformat(),
        )

        # Build message body
        body_lines = []
        for msg in messages:
            actor_name = msg.persona.name if msg.persona else "Unknown"
            ts = _format_timestamp(msg.sent_at)
            body_lines.append(f"### {actor_name} — {ts}\n")
            body_lines.append(msg.content.strip() + "\n")

        content = frontmatter + "\n" + "\n".join(body_lines)

        # Generate filename and persist
        # Use channel.id as the identifier in filename for uniqueness
        filename = _generate_filename("channel", chair_persona_slug, channel.id, now)
        self._persist(filename, content)

        return filename, content

    def _persist(self, filename: str, content: str) -> Path:
        """Save transcript to server-side storage.

        Args:
            filename: The transcript filename.
            content: The Markdown content.

        Returns:
            Path to the saved file.
        """
        filepath = self.transcripts_dir / filename
        filepath.write_text(content, encoding="utf-8")
        logger.info("Transcript saved: %s", filepath)
        return filepath


def _build_frontmatter(
    type_: str,
    identifier: str,
    project: str,
    persona: str,
    agent_id: int | None,
    participants: list[dict],
    start_time: str | None,
    end_time: str | None,
    message_count: int,
    exported_at: str,
) -> str:
    """Build YAML frontmatter for a transcript."""
    lines = ["---"]
    lines.append(f"type: {type_}")
    lines.append(f"identifier: {identifier}")
    lines.append(f"project: {project}")
    lines.append(f"persona: {persona}")
    if agent_id is not None:
        lines.append(f"agent_id: {agent_id}")
    lines.append("participants:")
    for p in participants:
        lines.append(f"  - name: {p['name']}")
        lines.append(f"    role: {p['role']}")
    lines.append(f"start_time: {start_time or 'null'}")
    lines.append(f"end_time: {end_time or 'null'}")
    lines.append(f"message_count: {message_count}")
    lines.append(f"exported_at: {exported_at}")
    lines.append("---\n")
    return "\n".join(lines)


def _format_timestamp(dt: datetime) -> str:
    """Format a datetime for display in transcript body."""
    if dt.tzinfo is not None:
        # Convert to local-ish display
        return dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _generate_filename(type_: str, persona_slug: str, id_: int, dt: datetime) -> str:
    """Generate a transcript filename.

    Format: {type}-{persona_slug}-{id}-{datetime}.md
    """
    dt_str = dt.strftime("%Y%m%d-%H%M%S")
    return f"{type_}-{persona_slug}-{id_}-{dt_str}.md"
