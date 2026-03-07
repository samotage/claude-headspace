"""ChannelMembershipMixin — membership operations.

Extracted from channel_service.py. Depends on ChannelHelpersMixin
for validation and broadcast methods, and on the facade for get_channel.
"""

import logging
from datetime import datetime, timezone

from ..database import db
from ..models.agent import Agent
from ..models.channel_membership import ChannelMembership
from ..models.persona import Persona
from ..models.project import Project
from ..models.role import Role
from .channel_errors import (
    AgentNotFoundError,
    AlreadyMemberError,
    NotAMemberError,
    PersonaNotFoundError,
    SoleChairError,
)

logger = logging.getLogger(__name__)


class ChannelMembershipMixin:
    """Membership operations — add, join, leave, transfer, mute, list."""

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
        project_id: int | None = None,
    ) -> ChannelMembership:
        """Add a persona to a channel.

        Args:
            slug: Channel slug.
            persona_slug: Slug of the persona to add.
            caller_persona: The persona making the request.
            project_id: Project to spin up the new agent under. Falls back to
                the channel's own project_id if None.

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

        # Determine effective project_id — prefer caller-supplied, fall back to channel's
        effective_project_id = (
            project_id if project_id is not None else channel.project_id
        )

        # Spin up fresh agent (S11: always fresh, no reuse)
        self._spin_up_agent_for_persona(target_persona, project_id=effective_project_id)

        # Create membership with agent_id=None (agent links via session-start hook)
        membership = ChannelMembership(
            channel_id=channel.id,
            persona_id=target_persona.id,
            agent_id=None,
            is_chair=False,
            status="active",
        )
        db.session.add(membership)

        self._post_system_message(channel, f"{target_persona.name} joined the channel")
        db.session.commit()

        members = self._get_member_names(channel)
        self._broadcast_update(
            channel,
            "channel_member_added",
            {
                "slug": channel.slug,
                "persona_slug": persona_slug,
                "persona_name": target_persona.name,
                "agent_id": None,
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
