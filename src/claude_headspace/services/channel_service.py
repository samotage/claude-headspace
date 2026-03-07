"""ChannelService — single point of truth for all channel operations.

Handles channel CRUD, membership management, message persistence,
lifecycle transitions, capability checks, and SSE broadcasting.
Registered as app.extensions["channel_service"].

All business logic lives here. CLI commands and API routes are thin
wrappers that delegate to this service.

Implementation is split across mixin modules for maintainability:
- channel_errors.py    — CHANNEL_PROTOCOL constant + exception hierarchy
- channel_helpers.py   — ChannelHelpersMixin (validation, broadcast, state)
- channel_membership.py — ChannelMembershipMixin (add, join, leave, etc.)
- channel_messages.py  — ChannelMessagesMixin (send_message, get_history)
- channel_orchestration.py — ChannelOrchestrationMixin (promote-to-group, S11)
"""

import logging
from datetime import datetime, timezone

from ..database import db
from ..models.agent import Agent
from ..models.channel import Channel, ChannelType
from ..models.channel_membership import ChannelMembership
from ..models.persona import Persona
from .channel_errors import (  # noqa: F401
    CHANNEL_PROTOCOL,
    AgentChannelConflictError,
    AgentNotFoundError,
    AlreadyMemberError,
    ChannelClosedError,
    ChannelDeletePreconditionError,
    ChannelError,
    ChannelNotFoundError,
    ContentTooLongError,
    NoCreationCapabilityError,
    NotAMemberError,
    NotChairError,
    PersonaNotFoundError,
    ProjectNotFoundError,
    PromoteToGroupError,
    SoleChairError,
)
from .channel_helpers import ChannelHelpersMixin
from .channel_membership import ChannelMembershipMixin
from .channel_messages import ChannelMessagesMixin
from .channel_orchestration import ChannelOrchestrationMixin

logger = logging.getLogger(__name__)


# ── Service ──────────────────────────────────────────────────────────────


class ChannelService(
    ChannelHelpersMixin,
    ChannelMembershipMixin,
    ChannelMessagesMixin,
    ChannelOrchestrationMixin,
):
    """Single service class for all channel operations."""

    def __init__(self, app):
        self.app = app

    # ── Channel CRUD ─────────────────────────────────────────────────

    def create_channel(
        self,
        creator_persona: Persona,
        name: str,
        channel_type: str,
        description: str | None = None,
        intent_override: str | None = None,
        organisation_id: int | None = None,
        project_id: int | None = None,
        member_slugs: list[str] | None = None,
        member_agent_ids: list[int] | None = None,
    ) -> Channel:
        """Create a new channel with the creator as chair.

        Args:
            creator_persona: Persona creating the channel.
            name: Human-readable channel name.
            channel_type: One of the ChannelType enum values.
            description: Optional channel description.
            intent_override: Optional intent override text.
            organisation_id: Optional organisation FK.
            project_id: Optional project FK.
            member_slugs: Optional list of persona slugs to add as members.
            member_agent_ids: Optional list of agent IDs to add as members.
                Takes precedence over member_slugs if both provided.

        Returns:
            The created Channel with slug populated.

        Raises:
            NoCreationCapabilityError: If the creator cannot create channels.
        """
        if not creator_persona.can_create_channel:
            raise NoCreationCapabilityError(
                f"Error: Persona '{creator_persona.name}' does not have "
                f"channel creation capability."
            )

        # Map string to enum
        ct = ChannelType(channel_type)

        channel = Channel(
            name=name,
            channel_type=ct,
            description=description,
            intent_override=intent_override,
            organisation_id=organisation_id,
            project_id=project_id,
            created_by_persona_id=creator_persona.id,
            status="pending",
        )
        db.session.add(channel)
        # Flush to get the ID and trigger slug generation
        db.session.flush()

        # Create chair membership
        chair_membership = ChannelMembership(
            channel_id=channel.id,
            persona_id=creator_persona.id,
            is_chair=True,
            status="active",
        )
        # Link the creator's running agent if available
        active_agent = Agent.query.filter_by(
            persona_id=creator_persona.id, ended_at=None
        ).first()
        if active_agent:
            chair_membership.agent_id = active_agent.id
        db.session.add(chair_membership)

        db.session.commit()
        # Re-read the slug after commit (after_insert event sets it)
        db.session.refresh(channel)

        # Add additional members — both agent IDs and persona slugs
        if member_agent_ids:
            for aid in member_agent_ids:
                try:
                    self.add_member_by_agent(channel.slug, aid, creator_persona)
                except ChannelError as e:
                    logger.warning(
                        f"create_channel: failed to add member agent #{aid}: {e}"
                    )
        if member_slugs:
            for slug in member_slugs:
                try:
                    self.add_member(channel.slug, slug, creator_persona)
                except ChannelError as e:
                    logger.warning(
                        f"create_channel: failed to add member '{slug}': {e}"
                    )

        # Transition to active if members were added alongside the chair
        if channel.status == "pending" and (member_agent_ids or member_slugs):
            self._transition_to_active(channel)
            db.session.commit()

        self._broadcast_channel_created(channel)

        return channel

    def list_channels(
        self,
        persona: Persona,
        status: str | None = None,
        channel_type: str | None = None,
        all_visible: bool = False,
    ) -> list[Channel]:
        """List channels visible to the persona.

        Args:
            persona: The calling persona.
            status: Optional status filter.
            channel_type: Optional type filter.
            all_visible: If True, return all non-archived channels.

        Returns:
            List of Channel instances.
        """
        if all_visible:
            query = Channel.query.filter(Channel.status != "archived")
        else:
            query = Channel.query.join(ChannelMembership).filter(
                ChannelMembership.persona_id == persona.id,
                ChannelMembership.status.in_(["active", "muted"]),
            )

        if status:
            query = query.filter(Channel.status == status)

        if channel_type:
            ct = ChannelType(channel_type)
            query = query.filter(Channel.channel_type == ct)

        return query.order_by(Channel.created_at.desc()).all()

    def get_channel(self, slug: str) -> Channel:
        """Get a channel by slug.

        No membership check is performed. Any authenticated caller can
        retrieve channel metadata by slug. This is intentional — it
        supports observer/supervisor patterns where an operator or
        monitoring tool needs to inspect a channel without being a member.

        Args:
            slug: The channel slug.

        Returns:
            The Channel instance.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = Channel.query.filter_by(slug=slug).first()
        if not channel:
            raise ChannelNotFoundError(f"Error: Channel #{slug} not found.")
        return channel

    def update_channel(
        self,
        slug: str,
        persona: Persona,
        description: str | None = None,
        intent_override: str | None = None,
    ) -> Channel:
        """Update mutable channel fields.

        Args:
            slug: Channel slug.
            persona: Calling persona (must be chair or operator).
            description: New description (if provided).
            intent_override: New intent override (if provided).

        Returns:
            The updated Channel.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotChairError: If caller is not chair or operator.
        """
        channel = self.get_channel(slug)
        self._check_chair_or_operator(channel, persona)

        if description is not None:
            channel.description = description
        if intent_override is not None:
            channel.intent_override = intent_override

        db.session.commit()

        self._broadcast_update(
            channel,
            "channel_updated",
            {
                "slug": channel.slug,
            },
        )
        return channel

    def complete_channel(self, slug: str, persona: Persona) -> Channel:
        """Transition a channel to complete status.

        Args:
            slug: Channel slug.
            persona: Calling persona (must be chair).

        Returns:
            The completed Channel.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotChairError: If caller is not the chair.
            ChannelClosedError: If channel is already complete/archived.
        """
        channel = self.get_channel(slug)
        self._check_closed(channel)
        self._check_chair(channel, persona)

        channel.status = "complete"
        channel.completed_at = datetime.now(timezone.utc)

        # Release all active memberships so agents can join new channels
        now = datetime.now(timezone.utc)
        for m in channel.memberships:
            if m.status == "active":
                m.status = "left"
                m.left_at = now

        self._post_system_message(channel, f"Channel completed by {persona.name}")
        db.session.commit()

        self._broadcast_update(
            channel,
            "channel_completed",
            {
                "slug": channel.slug,
            },
        )
        return channel

    def archive_channel(self, slug: str, persona: Persona) -> Channel:
        """Transition a channel from complete to archived.

        Args:
            slug: Channel slug.
            persona: Calling persona (must be chair or operator).

        Returns:
            The archived Channel.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotChairError: If caller is not chair or operator.
            ChannelClosedError: If channel is not in complete state.
        """
        channel = self.get_channel(slug)
        self._check_chair_or_operator(channel, persona)

        if channel.status != "complete":
            raise ChannelClosedError(
                f"Error: Channel #{slug} must be in 'complete' state to archive. "
                f"Current status: {channel.status}."
            )

        channel.status = "archived"
        channel.archived_at = datetime.now(timezone.utc)

        # Release any remaining active memberships
        now = datetime.now(timezone.utc)
        for m in channel.memberships:
            if m.status in ("active", "muted"):
                m.status = "left"
                m.left_at = now

        self._post_system_message(channel, f"Channel archived by {persona.name}")
        db.session.commit()

        self._broadcast_update(
            channel,
            "channel_archived",
            {
                "slug": channel.slug,
            },
        )
        return channel

    def delete_channel(self, slug: str, persona: Persona) -> None:
        """Permanently delete a channel.

        Precondition: channel must be archived OR have zero active members.

        Args:
            slug: Channel slug.
            persona: Calling persona (must be chair or operator).

        Raises:
            ChannelNotFoundError: If channel not found.
            NotChairError: If caller is not chair or operator.
            ChannelDeletePreconditionError: If precondition not met.
        """
        channel = self.get_channel(slug)
        self._check_chair_or_operator(channel, persona)

        # Check precondition: archived or no active members
        active_members = [
            m for m in channel.memberships if m.status in ("active", "muted")
        ]
        if channel.status != "archived" and len(active_members) > 0:
            raise ChannelDeletePreconditionError(
                f"Error: Channel #{slug} must be archived or have no active members "
                f"before it can be deleted. Current status: {channel.status}, "
                f"active members: {len(active_members)}."
            )

        channel_slug = channel.slug
        channel_status = channel.status
        db.session.delete(channel)
        db.session.commit()

        logger.info("Deleted channel %s", channel_slug)

        # Broadcast directly — the channel object is detached after delete+commit,
        # so we cannot pass it to _broadcast_update (which accesses channel.slug/status).
        try:
            broadcaster = self.app.extensions.get("broadcaster")
            if broadcaster:
                broadcaster.broadcast(
                    "channel_update",
                    {
                        "channel_slug": channel_slug,
                        "update_type": "channel_deleted",
                        "status": channel_status,
                        "slug": channel_slug,
                    },
                )
        except Exception as e:
            logger.warning(f"SSE broadcast failed for channel delete: {e}")
