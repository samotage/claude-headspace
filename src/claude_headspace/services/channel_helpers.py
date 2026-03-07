"""ChannelHelpersMixin — shared validation, broadcast, and state helpers.

Extracted from channel_service.py. These methods are used by multiple
other mixins (membership, messages, orchestration) via self.* calls.
"""

import logging
from datetime import datetime, timezone

from ..database import db
from ..models.agent import Agent
from ..models.channel import Channel
from ..models.channel_membership import ChannelMembership
from ..models.message import Message, MessageType
from ..models.persona import Persona
from .channel_errors import (
    AgentChannelConflictError,
    ChannelClosedError,
    NotAMemberError,
    NotChairError,
)

logger = logging.getLogger(__name__)


class ChannelHelpersMixin:
    """Shared validation, broadcast, and state helpers for ChannelService."""

    # ── Validation helpers ───────────────────────────────────────────

    def _check_membership(
        self,
        channel: Channel,
        persona: Persona,
        require_active: bool = True,
    ) -> ChannelMembership:
        """Validate that a persona is a member of a channel.

        Args:
            channel: The channel.
            persona: The persona to check.
            require_active: If True, only 'active' status is valid.
                If False, 'active', 'left', and 'muted' are all valid.

        Returns:
            The ChannelMembership record.

        Raises:
            NotAMemberError: If the persona is not a valid member.
        """
        query = ChannelMembership.query.filter_by(
            channel_id=channel.id, persona_id=persona.id
        )
        if require_active:
            query = query.filter_by(status="active")

        membership = query.first()
        if not membership:
            raise NotAMemberError(f"Error: You are not a member of #{channel.slug}.")
        return membership

    def _check_chair(self, channel: Channel, persona: Persona) -> ChannelMembership:
        """Validate that a persona is the chair of a channel.

        Args:
            channel: The channel.
            persona: The persona to check.

        Returns:
            The ChannelMembership record.

        Raises:
            NotChairError: If the persona is not the chair.
        """
        membership = ChannelMembership.query.filter_by(
            channel_id=channel.id, persona_id=persona.id, is_chair=True
        ).first()
        if not membership:
            raise NotChairError(
                "Error: Only the channel chair can perform this operation."
            )
        return membership

    def _check_chair_or_operator(
        self, channel: Channel, persona: Persona
    ) -> ChannelMembership | None:
        """Validate that a persona is the chair or the operator.

        Returns the membership if the persona is the chair, None if the
        persona is the operator but not a member.

        Raises:
            NotChairError: If the persona is neither chair nor operator.
        """
        membership = ChannelMembership.query.filter_by(
            channel_id=channel.id, persona_id=persona.id, is_chair=True
        ).first()
        if membership:
            return membership

        # Check if this is the operator persona
        operator = Persona.get_operator()
        if operator and operator.id == persona.id:
            return None

        raise NotChairError("Error: Only the channel chair can perform this operation.")

    def _check_closed(self, channel: Channel) -> None:
        """Raise ChannelClosedError if channel is complete or archived.

        Args:
            channel: The channel to check.

        Raises:
            ChannelClosedError: If the channel is not active or pending.
        """
        if channel.status in ("complete", "archived"):
            raise ChannelClosedError(
                f"Error: Channel #{channel.slug} is {channel.status}. "
                f"Create a new channel to continue."
            )

    def _check_agent_channel_conflict(self, agent: Agent) -> None:
        """Check if the agent is already active in an open channel.

        Only blocks if the agent has an active membership in a channel
        that is still pending or active.  Completed/archived channels
        do not block.

        Args:
            agent: The agent to check.

        Raises:
            AgentChannelConflictError: If the agent is already active
                in an open channel.
        """
        if agent is None:
            return
        existing = (
            ChannelMembership.query.join(Channel)
            .filter(
                ChannelMembership.agent_id == agent.id,
                ChannelMembership.status == "active",
                Channel.status.in_(["pending", "active"]),
            )
            .first()
        )
        if existing:
            ch = existing.channel
            raise AgentChannelConflictError(
                f"Error: Agent #{agent.id} ({agent.persona.name if agent.persona else 'unknown'}) "
                f"is already an active member of #{ch.slug}.\n"
                f"Leave that channel first: flask channel leave {ch.slug}"
            )

    # ── State transition helpers ─────────────────────────────────────

    def _transition_to_active(self, channel: Channel) -> None:
        """Transition a channel from pending to active.

        Args:
            channel: The channel to transition.
        """
        if channel.status == "pending":
            channel.status = "active"
            logger.info(f"Channel #{channel.slug} transitioned from pending to active")

    def _auto_complete_if_empty(self, channel: Channel) -> bool:
        """Auto-complete a channel if the last active member has left.

        Uses advisory lock on channel ID to prevent race conditions.

        Args:
            channel: The channel to check.

        Returns:
            True if the channel was auto-completed.
        """
        from .advisory_lock import LockNamespace, advisory_lock

        try:
            with advisory_lock(LockNamespace.CHANNEL, channel.id, timeout=5.0):
                active_count = ChannelMembership.query.filter_by(
                    channel_id=channel.id, status="active"
                ).count()

                if active_count == 0 and channel.status not in ("complete", "archived"):
                    channel.status = "complete"
                    channel.completed_at = datetime.now(timezone.utc)
                    self._post_system_message(
                        channel, "Channel completed (last member left)"
                    )
                    db.session.commit()

                    self._broadcast_update(
                        channel,
                        "channel_auto_completed",
                        {
                            "slug": channel.slug,
                        },
                    )
                    logger.info(
                        f"Channel #{channel.slug} auto-completed "
                        f"(last active member left)"
                    )
                    return True
        except Exception as e:
            logger.warning(
                f"Auto-complete advisory lock failed for channel #{channel.slug}: {e}"
            )

        return False

    # ── Attachment validation ────────────────────────────────────────

    @staticmethod
    def _validate_attachment_path(path: str) -> None:
        """Validate that an attachment path is safe.

        Rejects path traversal (``..``), absolute paths, and control
        characters to prevent directory escape and injection attacks.

        Args:
            path: The attachment path string to validate.

        Raises:
            ValueError: If the path is unsafe.
        """
        if ".." in path:
            raise ValueError(
                "Invalid attachment_path: path traversal ('..') is not allowed."
            )
        if path.startswith("/") or path.startswith("\\"):
            raise ValueError("Invalid attachment_path: absolute paths are not allowed.")
        # Reject control characters (0x00–0x1F, 0x7F)
        if any(c < " " or c == "\x7f" for c in path):
            raise ValueError(
                "Invalid attachment_path: control characters are not allowed."
            )

    # ── System messages ──────────────────────────────────────────────

    def _post_system_message(self, channel: Channel, content: str) -> Message:
        """Create a system message in a channel.

        System messages have persona_id=NULL and agent_id=NULL.

        Args:
            channel: The channel to post to.
            content: System message text.

        Returns:
            The created Message.
        """
        message = Message(
            channel_id=channel.id,
            persona_id=None,
            agent_id=None,
            content=content,
            message_type=MessageType.SYSTEM,
        )
        db.session.add(message)
        return message

    # ── Member name helper ───────────────────────────────────────────

    def _get_member_names(self, channel: Channel) -> list[str]:
        """Get display names of active/muted members for SSE payloads.

        Used by _broadcast_update to include the current member list so
        channel-cards.js can update the card's member display in real time.

        Args:
            channel: The channel to query.

        Returns:
            List of persona names for active and muted members.
        """
        memberships = (
            ChannelMembership.query.filter_by(channel_id=channel.id)
            .filter(ChannelMembership.status.in_(["active", "muted"]))
            .all()
        )
        return [m.persona.name for m in memberships if m.persona]

    # ── SSE Broadcasting ─────────────────────────────────────────────

    def _broadcast_message(self, message: Message, channel: Channel) -> None:
        """Broadcast a channel_message SSE event after message persistence.

        Args:
            message: The persisted Message.
            channel: The channel containing the message.
        """
        try:
            broadcaster = self.app.extensions.get("broadcaster")
            if broadcaster:
                broadcaster.broadcast(
                    "channel_message",
                    {
                        "channel_slug": channel.slug,
                        "channel_name": channel.name,
                        "message_id": message.id,
                        "persona_name": (
                            message.persona.name if message.persona else None
                        ),
                        "agent_id": message.agent_id,
                        "content": message.content,
                        "message_type": message.message_type.value,
                        "sent_at": message.sent_at.isoformat(),
                    },
                )
        except Exception as e:
            logger.warning(f"SSE broadcast failed for message: {e}")

    def _broadcast_update(
        self, channel: Channel, update_type: str, detail: dict
    ) -> None:
        """Broadcast a channel_update SSE event after state changes.

        Args:
            channel: The channel that changed.
            update_type: Type of update (e.g. 'member_added', 'channel_completed').
            detail: Additional detail dict.
        """
        try:
            broadcaster = self.app.extensions.get("broadcaster")
            if broadcaster:
                broadcaster.broadcast(
                    "channel_update",
                    {
                        "channel_slug": channel.slug,
                        "update_type": update_type,
                        "status": channel.status,
                        **detail,
                    },
                )
        except Exception as e:
            logger.warning(f"SSE broadcast failed for channel update: {e}")
