"""ChannelService — single point of truth for all channel operations.

Handles channel CRUD, membership management, message persistence,
lifecycle transitions, capability checks, and SSE broadcasting.
Registered as app.extensions["channel_service"].

All business logic lives here. CLI commands and API routes are thin
wrappers that delegate to this service.
"""

import logging
from datetime import datetime, timezone

from ..database import db
from ..models.agent import Agent
from ..models.channel import Channel, ChannelType
from ..models.channel_membership import ChannelMembership
from ..models.message import Message, MessageType
from ..models.persona import Persona
from ..models.project import Project
from ..models.role import Role

logger = logging.getLogger(__name__)


# ── Error hierarchy ──────────────────────────────────────────────────────


class ChannelError(Exception):
    """Base exception for channel operations."""


class ChannelNotFoundError(ChannelError):
    """Channel with the given slug does not exist."""


class NotAMemberError(ChannelError):
    """Caller is not a member of the channel."""


class NotChairError(ChannelError):
    """Caller is not the chair of the channel."""


class ChannelClosedError(ChannelError):
    """Channel is complete or archived — no further operations allowed."""


class AlreadyMemberError(ChannelError):
    """Persona is already a member of the channel."""


class NoCreationCapabilityError(ChannelError):
    """Persona does not have channel creation capability."""


class PersonaNotFoundError(ChannelError):
    """Persona with the given slug does not exist."""


class AgentChannelConflictError(ChannelError):
    """Agent is already active in another channel."""


class ContentTooLongError(ChannelError):
    """Message content exceeds the configured maximum length."""


class AgentNotFoundError(ChannelError):
    """Agent with the given ID does not exist or is not active."""


class ChannelDeletePreconditionError(ChannelError):
    """Channel cannot be deleted — must be archived or have no active members."""


class SoleChairError(ChannelError):
    """Cannot remove the last chair from a channel."""


# ── Service ──────────────────────────────────────────────────────────────


class ChannelService:
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

        # Build member name list for the JS card
        members = self._get_member_names(channel)
        self._broadcast_update(
            channel,
            "channel_created",
            {
                "slug": channel.slug,
                "name": channel.name,
                "channel_type": channel.channel_type.value,
                # Nested channel object for channel-cards.js _addCard()
                "channel": {
                    "slug": channel.slug,
                    "name": channel.name,
                    "channel_type": channel.channel_type.value,
                    "status": channel.status,
                    "members": members,
                },
            },
        )

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

    def remove_member(
        self, slug: str, persona_slug: str, caller_persona: Persona
    ) -> None:
        """Remove a member from a channel (admin action).

        Enforces sole-chair prevention: cannot remove the last chair.

        Args:
            slug: Channel slug.
            persona_slug: Slug of the persona to remove.
            caller_persona: The persona making the request (must be chair or operator).

        Raises:
            ChannelNotFoundError: If channel not found.
            NotChairError: If caller is not chair or operator.
            ChannelClosedError: If channel is complete/archived.
            PersonaNotFoundError: If persona not found.
            NotAMemberError: If persona is not an active member.
            SoleChairError: If removing would leave no chair.
        """
        channel = self.get_channel(slug)
        self._check_chair_or_operator(channel, caller_persona)
        self._check_closed(channel)

        # Resolve target persona
        target_persona = Persona.query.filter_by(slug=persona_slug).first()
        if not target_persona:
            raise PersonaNotFoundError(f"Error: Persona '{persona_slug}' not found.")

        # Find active membership
        membership = (
            ChannelMembership.query.filter_by(
                channel_id=channel.id,
                persona_id=target_persona.id,
            )
            .filter(ChannelMembership.status.in_(("active", "muted")))
            .first()
        )

        if not membership:
            raise NotAMemberError(
                f"Error: Persona '{target_persona.name}' is not an active member "
                f"of #{channel.slug}."
            )

        # Sole chair prevention
        if membership.is_chair:
            chair_count = (
                ChannelMembership.query.filter_by(channel_id=channel.id, is_chair=True)
                .filter(ChannelMembership.status.in_(("active", "muted")))
                .count()
            )
            if chair_count <= 1:
                raise SoleChairError(
                    f"Error: Cannot remove '{target_persona.name}' — they are the "
                    f"sole chair of #{channel.slug}. Transfer chair first."
                )

        membership.status = "left"
        membership.left_at = datetime.now(timezone.utc)

        self._post_system_message(
            channel, f"{target_persona.name} was removed by {caller_persona.name}"
        )
        db.session.commit()

        # Check if this was the last active member
        self._auto_complete_if_empty(channel)

        members = self._get_member_names(channel)
        self._broadcast_update(
            channel,
            "member_removed",
            {
                "slug": channel.slug,
                "persona_slug": persona_slug,
                "persona_name": target_persona.name,
                "members": members,
            },
        )

    # ── Membership ───────────────────────────────────────────────────

    def list_members(self, slug: str) -> list[ChannelMembership]:
        """List all memberships for a channel.

        No membership check is performed. Any authenticated caller can
        list a channel's members without being a member themselves. This
        is intentional — it supports observer/supervisor patterns (e.g.
        the operator reviewing channel composition, or a monitoring
        service auditing membership).

        Args:
            slug: Channel slug.

        Returns:
            List of ChannelMembership instances with persona details loaded.

        Raises:
            ChannelNotFoundError: If channel not found.
        """
        channel = self.get_channel(slug)
        return (
            ChannelMembership.query.filter_by(channel_id=channel.id)
            .order_by(ChannelMembership.joined_at.asc())
            .all()
        )

    def add_member(
        self,
        slug: str,
        persona_slug: str,
        caller_persona: Persona,
    ) -> ChannelMembership:
        """Add a persona to a channel.

        Args:
            slug: Channel slug.
            persona_slug: Slug of the persona to add.
            caller_persona: The persona making the request.

        Returns:
            The created ChannelMembership.

        Raises:
            ChannelNotFoundError: If channel not found.
            ChannelClosedError: If channel is complete/archived.
            NotAMemberError: If caller is not an active member.
            AlreadyMemberError: If target persona is already a member.
            AgentChannelConflictError: If the persona's agent is in another channel.
        """
        channel = self.get_channel(slug)
        self._check_closed(channel)
        self._check_membership(channel, caller_persona, require_active=True)

        # Resolve target persona
        target_persona = Persona.query.filter_by(slug=persona_slug).first()
        if not target_persona:
            raise PersonaNotFoundError(f"Error: Persona '{persona_slug}' not found.")

        # Check not already a member
        existing = ChannelMembership.query.filter_by(
            channel_id=channel.id, persona_id=target_persona.id
        ).first()
        if existing:
            raise AlreadyMemberError(
                f"Error: Persona '{target_persona.name}' is already a member "
                f"of #{channel.slug}."
            )

        # Find or spin up agent
        active_agent = self._spin_up_agent_for_persona(target_persona)

        # Check one-agent-one-channel constraint
        if active_agent:
            self._check_agent_channel_conflict(active_agent)

        # Create membership
        membership = ChannelMembership(
            channel_id=channel.id,
            persona_id=target_persona.id,
            agent_id=active_agent.id if active_agent else None,
            is_chair=False,
            status="active",
        )
        db.session.add(membership)

        self._post_system_message(channel, f"{target_persona.name} joined the channel")
        db.session.commit()

        # Deliver context briefing if the agent is available and channel has messages
        if active_agent and active_agent.tmux_pane_id:
            self._deliver_context_briefing(channel, active_agent)

        members = self._get_member_names(channel)
        self._broadcast_update(
            channel,
            "member_added",
            {
                "slug": channel.slug,
                "persona_slug": persona_slug,
                "persona_name": target_persona.name,
                "members": members,
            },
        )
        return membership

    def get_available_members(self) -> dict:
        """Return active agents grouped by project, plus agentless personas.

        An "available" agent is one where:
        - ended_at IS NULL (session active)
        - persona_id IS NOT NULL (has an assigned persona)
        - persona.status == 'active'

        Additionally returns personas that have no active agent session
        (e.g. the human operator) so they can be added to channels too.

        Returns:
            Dict with ``projects`` (agents grouped by project) and
            ``personas`` (active personas without a live agent).
        """

        agents = (
            Agent.query.join(Persona, Agent.persona_id == Persona.id)
            .join(Role, Persona.role_id == Role.id)
            .join(Project, Agent.project_id == Project.id)
            .filter(
                Agent.ended_at.is_(None),
                Agent.persona_id.isnot(None),
                Persona.status == "active",
            )
            .order_by(Project.name, Persona.name, Agent.last_seen_at.desc())
            .all()
        )

        grouped: dict[int, dict] = {}
        persona_ids_with_agents: set[int] = set()
        seen_persona_project: set[tuple[int, int]] = set()
        for agent in agents:
            pid = agent.project_id
            key = (agent.persona_id, pid)
            persona_ids_with_agents.add(agent.persona_id)

            # Deduplicate: keep only the most recently seen agent per
            # persona per project (query is ordered by last_seen_at desc)
            if key in seen_persona_project:
                continue
            seen_persona_project.add(key)

            if pid not in grouped:
                grouped[pid] = {
                    "project_id": pid,
                    "project_name": agent.project.name,
                    "agents": [],
                }
            grouped[pid]["agents"].append(
                {
                    "agent_id": agent.id,
                    "persona_name": agent.persona.name,
                    "persona_slug": agent.persona.slug,
                    "role": agent.persona.role.name,
                }
            )

        # Human personas only (person-type) — agent personas should only
        # appear when they have active agent sessions in the projects list
        from ..models.persona_type import PersonaType

        agentless_personas = (
            Persona.query.join(Role, Persona.role_id == Role.id)
            .join(PersonaType, Persona.persona_type_id == PersonaType.id)
            .filter(
                Persona.status == "active",
                PersonaType.type_key == "person",
            )
            .order_by(Persona.name)
            .all()
        )

        personas_list = [
            {
                "persona_name": p.name,
                "persona_slug": p.slug,
                "role": p.role.name,
            }
            for p in agentless_personas
        ]

        return {
            "projects": list(grouped.values()),
            "personas": personas_list,
        }

    def add_member_by_agent(
        self,
        slug: str,
        agent_id: int,
        caller_persona: Persona,
    ) -> ChannelMembership:
        """Add a member to a channel by agent ID.

        Args:
            slug: Channel slug.
            agent_id: ID of the agent to add.
            caller_persona: The persona making the request.

        Returns:
            The created ChannelMembership.

        Raises:
            AgentNotFoundError: If agent doesn't exist or is inactive.
            ChannelNotFoundError: If channel not found.
            ChannelClosedError: If channel is complete/archived.
            NotAMemberError: If caller is not an active member.
            AlreadyMemberError: If target persona is already a member.
            AgentChannelConflictError: If the agent is in another channel.
        """
        channel = self.get_channel(slug)
        self._check_closed(channel)
        self._check_membership(channel, caller_persona, require_active=True)

        # Resolve agent
        agent = db.session.get(Agent, agent_id)
        if not agent or agent.ended_at is not None:
            raise AgentNotFoundError(
                f"Error: Agent #{agent_id} not found or not active."
            )
        if not agent.persona_id or not agent.persona:
            raise AgentNotFoundError(
                f"Error: Agent #{agent_id} has no assigned persona."
            )
        if agent.persona.status != "active":
            raise AgentNotFoundError(
                f"Error: Agent #{agent_id}'s persona is not active."
            )

        # Check not already a member (by persona)
        existing = ChannelMembership.query.filter_by(
            channel_id=channel.id, persona_id=agent.persona_id
        ).first()
        if existing:
            raise AlreadyMemberError(
                f"Error: Persona '{agent.persona.name}' is already a member "
                f"of #{channel.slug}."
            )

        # Check one-agent-one-channel constraint
        self._check_agent_channel_conflict(agent)

        # Create membership with both persona_id and agent_id
        membership = ChannelMembership(
            channel_id=channel.id,
            persona_id=agent.persona_id,
            agent_id=agent.id,
            is_chair=False,
            status="active",
        )
        db.session.add(membership)

        self._post_system_message(channel, f"{agent.persona.name} joined the channel")
        db.session.commit()

        # Deliver context briefing if tmux available
        if agent.tmux_pane_id:
            self._deliver_context_briefing(channel, agent)

        members = self._get_member_names(channel)
        self._broadcast_update(
            channel,
            "member_added",
            {
                "slug": channel.slug,
                "persona_slug": agent.persona.slug,
                "persona_name": agent.persona.name,
                "agent_id": agent.id,
                "members": members,
            },
        )
        return membership

    def join_channel(self, slug: str, persona: Persona) -> ChannelMembership:
        """Self-join a channel without requiring existing membership or chair.

        This is a distinct action from add_member — it allows a persona to
        join a channel they can see but are not yet a member of. No caller
        membership check and no chair permission required.

        Args:
            slug: Channel slug.
            persona: The persona joining.

        Returns:
            The created ChannelMembership.

        Raises:
            ChannelNotFoundError: If channel not found.
            ChannelClosedError: If channel is complete/archived.
            AlreadyMemberError: If persona is already a member.
        """
        channel = self.get_channel(slug)
        self._check_closed(channel)

        # Check not already a member
        existing = ChannelMembership.query.filter_by(
            channel_id=channel.id, persona_id=persona.id
        ).first()
        if existing:
            raise AlreadyMemberError(
                f"Error: You are already a member of #{channel.slug}."
            )

        membership = ChannelMembership(
            channel_id=channel.id,
            persona_id=persona.id,
            agent_id=None,
            is_chair=False,
            status="active",
        )
        db.session.add(membership)

        self._post_system_message(channel, f"{persona.name} joined the channel")
        self._transition_to_active(channel)
        db.session.commit()

        members = self._get_member_names(channel)
        self._broadcast_update(
            channel,
            "member_added",
            {
                "slug": channel.slug,
                "persona_slug": persona.slug,
                "persona_name": persona.name,
                "members": members,
            },
        )
        return membership

    def leave_channel(self, slug: str, persona: Persona) -> None:
        """Leave a channel.

        Args:
            slug: Channel slug.
            persona: The persona leaving.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotAMemberError: If caller is not an active member.
        """
        channel = self.get_channel(slug)
        membership = self._check_membership(channel, persona, require_active=True)

        membership.status = "left"
        membership.left_at = datetime.now(timezone.utc)

        self._post_system_message(channel, f"{persona.name} left the channel")
        db.session.commit()

        # Check if this was the last active member
        self._auto_complete_if_empty(channel)

        members = self._get_member_names(channel)
        self._broadcast_update(
            channel,
            "member_left",
            {
                "slug": channel.slug,
                "persona_name": persona.name,
                "members": members,
            },
        )

    def transfer_chair(
        self,
        slug: str,
        target_persona_slug: str,
        caller_persona: Persona,
    ) -> None:
        """Transfer chair role to another member.

        Args:
            slug: Channel slug.
            target_persona_slug: Slug of the new chair.
            caller_persona: Current chair persona.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotChairError: If caller is not the current chair.
            NotAMemberError: If target is not an active member.
        """
        channel = self.get_channel(slug)
        self._check_closed(channel)
        current_chair = self._check_chair(channel, caller_persona)

        # Find target persona
        target_persona = Persona.query.filter_by(slug=target_persona_slug).first()
        if not target_persona:
            raise PersonaNotFoundError(
                f"Error: Persona '{target_persona_slug}' not found."
            )

        # Validate target is an active member
        target_membership = ChannelMembership.query.filter_by(
            channel_id=channel.id,
            persona_id=target_persona.id,
            status="active",
        ).first()
        if not target_membership:
            raise NotAMemberError(
                f"Error: Persona '{target_persona.name}' is not an active "
                f"member of #{channel.slug}."
            )

        # Swap chair status
        current_chair.is_chair = False
        target_membership.is_chair = True

        self._post_system_message(
            channel,
            f"Chair transferred from {caller_persona.name} to {target_persona.name}",
        )
        db.session.commit()

        self._broadcast_update(
            channel,
            "chair_transferred",
            {
                "slug": channel.slug,
                "from": caller_persona.name,
                "to": target_persona.name,
            },
        )

    def mute_channel(self, slug: str, persona: Persona) -> None:
        """Mute a channel for a persona.

        Args:
            slug: Channel slug.
            persona: The persona muting.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotAMemberError: If caller is not an active member.
        """
        channel = self.get_channel(slug)
        membership = self._check_membership(channel, persona, require_active=True)

        membership.status = "muted"

        self._post_system_message(channel, f"{persona.name} muted the channel")
        db.session.commit()

        self._broadcast_update(
            channel,
            "member_muted",
            {
                "slug": channel.slug,
                "persona_name": persona.name,
            },
        )

    def unmute_channel(self, slug: str, persona: Persona) -> None:
        """Unmute a channel for a persona.

        Args:
            slug: Channel slug.
            persona: The persona unmuting.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotAMemberError: If caller is not a muted member.
        """
        channel = self.get_channel(slug)
        membership = ChannelMembership.query.filter_by(
            channel_id=channel.id,
            persona_id=persona.id,
            status="muted",
        ).first()
        if not membership:
            raise NotAMemberError(
                f"Error: You are not a muted member of #{channel.slug}."
            )

        membership.status = "active"

        self._post_system_message(channel, f"{persona.name} unmuted the channel")
        db.session.commit()

        self._broadcast_update(
            channel,
            "member_unmuted",
            {
                "slug": channel.slug,
                "persona_name": persona.name,
            },
        )

    # ── Messages ─────────────────────────────────────────────────────

    def send_message(
        self,
        slug: str,
        content: str,
        persona: Persona,
        agent: Agent | None = None,
        message_type: str = "message",
        attachment_path: str | None = None,
        source_turn_id: int | None = None,
        source_command_id: int | None = None,
    ) -> Message:
        """Send a message to a channel.

        Args:
            slug: Channel slug.
            content: Message text content.
            persona: Sending persona.
            agent: Optional agent instance.
            message_type: One of 'message', 'delegation', 'escalation'.
            attachment_path: Optional file path.
            source_turn_id: Optional source turn FK.
            source_command_id: Optional source command FK.

        Returns:
            The created Message.

        Raises:
            ChannelNotFoundError: If channel not found.
            ChannelClosedError: If channel is complete/archived.
            NotAMemberError: If sender is not an active member.
            ValueError: If message_type is 'system'.
        """
        if message_type == "system":
            raise ValueError(
                "System messages are generated by the service, not callable directly."
            )

        # Content length validation
        max_len = (
            self.app.config.get("APP_CONFIG", {})
            .get("channels", {})
            .get("max_message_content_length", 50000)
        )
        if len(content) > max_len:
            raise ContentTooLongError(
                f"Error: Message content exceeds maximum length "
                f"({len(content):,} > {max_len:,} characters)."
            )

        # Attachment path validation
        if attachment_path is not None:
            self._validate_attachment_path(attachment_path)

        channel = self.get_channel(slug)
        self._check_closed(channel)
        self._check_membership(channel, persona, require_active=True)

        mt = MessageType(message_type)
        message = Message(
            channel_id=channel.id,
            persona_id=persona.id,
            agent_id=agent.id if agent else None,
            content=content,
            message_type=mt,
            attachment_path=attachment_path,
            source_turn_id=source_turn_id,
            source_command_id=source_command_id,
        )
        db.session.add(message)

        # Pending -> active on first non-system message
        if channel.status == "pending":
            self._transition_to_active(channel)

        db.session.commit()

        self._broadcast_message(message, channel)

        # Deliver to agent members via tmux (post-commit side effect)
        delivery_service = self.app.extensions.get("channel_delivery_service")
        if delivery_service:
            delivery_service.deliver_message(message, channel)

        return message

    def get_history(
        self,
        slug: str,
        persona: Persona,
        limit: int = 50,
        since: str | None = None,
        before: str | None = None,
    ) -> list[Message]:
        """Get message history for a channel.

        Args:
            slug: Channel slug.
            persona: Calling persona (must be a member: active, left, or muted).
            limit: Maximum messages to return.
            since: ISO timestamp — return messages after this time.
            before: ISO timestamp — return messages before this time.

        Returns:
            List of Message instances in chronological order.

        Raises:
            ChannelNotFoundError: If channel not found.
            NotAMemberError: If caller is not a member (any status).
        """
        channel = self.get_channel(slug)
        # Allow active, left, and muted members to read history
        self._check_membership(channel, persona, require_active=False)

        query = Message.query.filter_by(channel_id=channel.id)

        if since:
            since_dt = datetime.fromisoformat(since)
            query = query.filter(Message.sent_at > since_dt)

        if before:
            before_dt = datetime.fromisoformat(before)
            query = query.filter(Message.sent_at < before_dt)

        # Fetch the *newest* messages up to `limit`, then reverse so the
        # caller receives them in chronological (oldest-first) order.
        # Without this, limit=50 on a 200-message channel returns the
        # oldest 50 — hiding all recent conversation.
        rows = query.order_by(Message.sent_at.desc()).limit(limit).all()
        rows.reverse()
        return rows

    # ── Internal helpers ─────────────────────────────────────────────

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

    def _spin_up_agent_for_persona(self, persona: Persona) -> Agent | None:
        """Find or create an agent for a persona.

        Returns the active agent, or None if spin-up was initiated
        asynchronously (agent will link via session-start hook).

        Args:
            persona: The persona to find/create an agent for.

        Returns:
            Active Agent instance, or None if agent is being spun up.
        """
        # Check for existing active agent
        active_agent = Agent.query.filter_by(
            persona_id=persona.id, ended_at=None
        ).first()
        if active_agent:
            return active_agent

        # No active agent — spin up
        try:
            # Need a project to spin up an agent — use the first project
            from ..models.project import Project
            from .agent_lifecycle import create_agent

            project = Project.query.first()
            if not project:
                logger.warning(
                    f"Cannot spin up agent for persona {persona.slug}: "
                    f"no projects found"
                )
                return None

            result = create_agent(
                project_id=project.id,
                persona_slug=persona.slug,
            )
            if not result.success:
                logger.warning(
                    f"Agent spin-up failed for persona {persona.slug}: {result.message}"
                )
                return None

            # Agent creation is async — agent_id not immediately available.
            # Return None and let the membership be created with agent_id=NULL.
            # The agent will be linked when it registers via session-start hook.
            logger.info(f"Agent spin-up initiated for persona {persona.slug}")
            return None
        except Exception as e:
            logger.warning(f"Agent spin-up error for persona {persona.slug}: {e}")
            return None

    def _generate_context_briefing(self, channel: Channel, limit: int = 10) -> str:
        """Generate a context briefing from recent channel messages.

        Returns a formatted text block with the last N messages,
        suitable for injection into an agent's tmux session.

        Args:
            channel: The channel to generate briefing for.
            limit: Maximum messages to include.

        Returns:
            Formatted briefing text, or empty string if no messages.
        """
        messages = (
            Message.query.filter_by(channel_id=channel.id)
            .order_by(Message.sent_at.desc())
            .limit(limit)
            .all()
        )
        if not messages:
            return ""

        messages.reverse()  # Chronological order

        lines = [
            f"=== Context briefing: #{channel.slug} "
            f"(last {len(messages)} messages) ===\n"
        ]
        for msg in messages:
            sender = msg.persona.name if msg.persona else "SYSTEM"
            timestamp = msg.sent_at.strftime("%d %b %Y, %H:%M")
            lines.append(f"[{sender}] ({timestamp}): {msg.content}\n")
        lines.append("=== End of context briefing ===")

        return "\n".join(lines)

    def _deliver_context_briefing(self, channel: Channel, agent: Agent) -> None:
        """Deliver a context briefing to an agent via tmux.

        Args:
            channel: The channel to generate briefing for.
            agent: The agent to deliver to.
        """
        briefing = self._generate_context_briefing(channel)
        if not briefing:
            return

        try:
            tmux_bridge = self.app.extensions.get("tmux_bridge")
            if tmux_bridge and agent.tmux_pane_id:
                tmux_bridge.send_text(agent.tmux_pane_id, briefing)
                logger.info(
                    f"Context briefing delivered to agent {agent.id} "
                    f"for channel #{channel.slug}"
                )
        except Exception as e:
            logger.warning(
                f"Context briefing delivery failed for agent {agent.id}: {e}"
            )

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
