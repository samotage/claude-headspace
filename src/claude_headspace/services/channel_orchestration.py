"""ChannelOrchestrationMixin — promote-to-group, S11 creation, agent spin-up.

Extracted from channel_service.py. Depends on ChannelHelpersMixin
for validation and broadcast methods, and on the facade for get_channel.
"""

import logging

from ..database import db
from ..models.agent import Agent
from ..models.channel import Channel, ChannelType
from ..models.channel_membership import ChannelMembership
from ..models.command import Command
from ..models.message import Message
from ..models.persona import Persona
from ..models.project import Project
from ..models.turn import Turn
from .channel_errors import (
    CHANNEL_PROTOCOL,
    AgentNotFoundError,
    PersonaNotFoundError,
    ProjectNotFoundError,
    PromoteToGroupError,
)

logger = logging.getLogger(__name__)


class ChannelOrchestrationMixin:
    """Orchestration operations — promote-to-group, S11 creation, agent lifecycle."""

    # ── Promote to Group ─────────────────────────────────────────────

    def get_agent_conversation_history(
        self, agent: Agent, limit: int = 20
    ) -> list[Turn]:
        """Retrieve the last N turns from an agent's conversation history.

        Fetches turns across all commands for the agent, ordered
        chronologically (oldest first), capped at `limit`.

        Args:
            agent: The agent to retrieve history for.
            limit: Maximum number of turns to return (default 20).

        Returns:
            List of Turn instances in chronological order.
        """
        # Get the most recent `limit` turns across all agent commands,
        # then reverse to chronological order.
        rows = (
            Turn.query.join(Command, Turn.command_id == Command.id)
            .filter(Command.agent_id == agent.id)
            .order_by(Turn.timestamp.desc())
            .limit(limit)
            .all()
        )
        rows.reverse()
        return rows

    def _format_agent_turns_briefing(self, turns: list[Turn], agent: Agent) -> str:
        """Format agent turns as a context briefing for tmux injection.

        Args:
            turns: List of Turn instances in chronological order.
            agent: The originating agent.

        Returns:
            Formatted briefing text, or empty string if no turns.
        """
        if not turns:
            return ""

        persona_name = agent.persona.name if agent.persona else f"Agent #{agent.id}"
        lines = [
            f"=== Context briefing: conversation with {persona_name} "
            f"(last {len(turns)} turns) ===\n"
        ]
        for turn in turns:
            actor = turn.actor.value.upper()
            timestamp = turn.timestamp.strftime("%d %b %Y, %H:%M")
            # Truncate long turn text for briefing
            text = turn.text
            if len(text) > 500:
                text = text[:497] + "..."
            lines.append(f"[{actor}] ({timestamp}): {text}\n")
        lines.append("=== End of context briefing ===")
        return "\n".join(lines)

    def promote_to_group(
        self,
        agent: Agent,
        persona_slug: str,
    ) -> Channel:
        """Orchestrate the promote-to-group flow.

        Creates a new group channel from an existing agent's 1:1 conversation,
        adds the operator, original agent's persona, and a new agent for the
        selected persona. Seeds the new agent with context from the original
        conversation.

        Args:
            agent: The originating agent (must have a persona).
            persona_slug: Slug of the persona for the new agent.

        Returns:
            The created Channel.

        Raises:
            AgentNotFoundError: If the agent has no persona.
            PersonaNotFoundError: If persona_slug not found.
            PromoteToGroupError: If orchestration fails.
        """
        if not agent.persona:
            raise AgentNotFoundError("Agent has no persona assigned")

        # Resolve the target persona
        target_persona = Persona.query.filter_by(
            slug=persona_slug, status="active"
        ).first()
        if not target_persona:
            raise PersonaNotFoundError(
                f"Persona '{persona_slug}' not found or not active"
            )

        # Resolve operator persona
        operator = Persona.get_operator()
        if not operator:
            raise PromoteToGroupError("No operator persona found")

        original_persona = agent.persona

        # Auto-generate channel name
        channel_name = f"{original_persona.name} + {target_persona.name}"

        # Step 1: Create the channel
        channel = Channel(
            name=channel_name,
            channel_type=ChannelType.WORKSHOP,
            description=(
                f"Group channel spawned from conversation with {original_persona.name}"
            ),
            spawned_from_agent_id=agent.id,
            created_by_persona_id=operator.id,
            status="active",
        )
        db.session.add(channel)
        db.session.flush()  # Get ID + trigger slug generation

        try:
            # Step 2: Add operator as chair
            chair = ChannelMembership(
                channel_id=channel.id,
                persona_id=operator.id,
                is_chair=True,
                status="active",
            )
            db.session.add(chair)

            # Step 3: Add original agent's persona as member
            original_membership = ChannelMembership(
                channel_id=channel.id,
                persona_id=original_persona.id,
                agent_id=agent.id,
                is_chair=False,
                status="active",
            )
            db.session.add(original_membership)

            # Step 4: Spin up a new agent for the selected persona
            from .agent_lifecycle import create_agent as create_agent_fn

            create_result = create_agent_fn(
                project_id=agent.project_id,
                persona_slug=persona_slug,
            )
            if not create_result.success:
                raise PromoteToGroupError(
                    f"Failed to create agent for persona "
                    f"'{persona_slug}': {create_result.message}"
                )

            # Step 5: Add target persona as member
            # Agent creation is async — the agent_id will be linked
            # when the agent registers via session-start hook.
            target_membership = ChannelMembership(
                channel_id=channel.id,
                persona_id=target_persona.id,
                agent_id=None,  # Linked asynchronously
                is_chair=False,
                status="active",
            )
            db.session.add(target_membership)

            # Step 6: Retrieve conversation history and prepare briefing
            turns = self.get_agent_conversation_history(agent, limit=20)
            briefing = self._format_agent_turns_briefing(turns, agent)

            # Step 7: Post system origin message
            turn_count = len(turns)
            origin_msg = (
                f"Channel created from conversation with {original_persona.name}."
            )
            if turn_count > 0:
                origin_msg += f" Context: last {turn_count} messages shared."
            self._post_system_message(channel, origin_msg)

            db.session.commit()
            db.session.refresh(channel)

            # Step 8: Deliver context briefing to new agent via tmux
            # This happens post-commit since the agent may not have a
            # tmux pane yet (async spin-up). Best-effort delivery.
            if briefing:
                # Try to find the newly created agent by persona
                new_agent = (
                    Agent.query.filter_by(persona_id=target_persona.id, ended_at=None)
                    .order_by(Agent.started_at.desc())
                    .first()
                )
                if new_agent and new_agent.tmux_pane_id:
                    try:
                        tmux_bridge = self.app.extensions.get("tmux_bridge")
                        if tmux_bridge:
                            tmux_bridge.send_text(new_agent.tmux_pane_id, briefing)
                            logger.info(
                                f"Context briefing delivered to new agent "
                                f"{new_agent.id} for promote-to-group "
                                f"channel #{channel.slug}"
                            )
                    except Exception as e:
                        logger.warning(
                            f"Context briefing delivery failed for "
                            f"promote-to-group: {e}"
                        )

            # Step 9: Broadcast channel_update SSE event
            self._broadcast_channel_created(channel)

            logger.info(
                f"Promote-to-group complete: channel #{channel.slug} "
                f"with {original_persona.name} + {target_persona.name}"
            )
            return channel

        except PromoteToGroupError:
            self._cleanup_channel_after_failure(channel.id)
            raise
        except Exception as e:
            self._cleanup_channel_after_failure(channel.id)
            raise PromoteToGroupError(f"Promote-to-group failed: {e}") from e

    # ── S11: Persona-based channel creation ──────────────────────────

    def create_channel_from_personas(
        self,
        creator_persona: Persona,
        channel_type: str,
        project_id: int,
        persona_slugs: list[str],
    ) -> Channel:
        """Create a pending channel and spin up fresh agents for each persona.

        S11 creation path: no name input required — the channel name is
        auto-generated from the persona names (e.g. "Robbo + Con + Wado").
        Agents are spun up asynchronously; each membership starts with
        ``agent_id = None`` and is linked when the agent registers via the
        session-start hook.

        Args:
            creator_persona: Operator persona creating the channel.
            channel_type: One of the ChannelType enum values.
            project_id: Project to spin up agents under.
            persona_slugs: Non-empty list of persona slugs to invite.

        Returns:
            The created Channel (status="pending").

        Raises:
            ProjectNotFoundError: If project_id does not resolve to a project.
            PersonaNotFoundError: If any slug does not resolve to an active persona.
            NoCreationCapabilityError: If creator cannot create channels.
            ValueError: If persona_slugs is empty.
        """
        if not persona_slugs:
            raise ValueError("persona_slugs must be a non-empty list")

        # Validate project
        project = db.session.get(Project, project_id)
        if not project:
            raise ProjectNotFoundError(f"Error: Project #{project_id} not found.")

        # Resolve all personas first — fail fast before any DB writes
        target_personas: list[Persona] = []
        for slug in persona_slugs:
            persona = Persona.query.filter_by(slug=slug, status="active").first()
            if not persona:
                raise PersonaNotFoundError(
                    f"Error: Persona '{slug}' not found or not active."
                )
            target_personas.append(persona)

        # Auto-generate name from persona names
        channel_name = " + ".join(p.name for p in target_personas)

        # Create channel (pending status is the default in create_channel;
        # no member_agent_ids/member_slugs are passed, so it stays pending).
        channel = self.create_channel(
            creator_persona=creator_persona,
            name=channel_name,
            channel_type=channel_type,
            project_id=project_id,
        )

        # Create memberships (agent_id=None) and kick off spin-up for each persona
        for persona in target_personas:
            membership = ChannelMembership(
                channel_id=channel.id,
                persona_id=persona.id,
                agent_id=None,
                is_chair=False,
                status="active",
            )
            db.session.add(membership)

        db.session.commit()

        # Spin up agents after memberships are committed so link_agent_to_pending_membership
        # can find the records when the session-start hook fires.
        for persona in target_personas:
            self._spin_up_agent_for_persona(persona, project_id=project_id)

        # Inject initiation system message
        self._post_system_message(channel, "Channel initiating...")
        db.session.commit()

        logger.info(
            f"create_channel_from_personas: created channel #{channel.slug} "
            f"({channel_name}) with {len(target_personas)} pending agents"
        )
        return channel

    def link_agent_to_pending_membership(self, agent: Agent) -> None:
        """Link a newly-registered agent to its pending ChannelMembership.

        Called from the session-start hook after the agent is persisted and
        its persona_id is set. Finds the oldest pending membership for the
        agent's persona and links the agent to it, then triggers a readiness
        check on the channel.

        Args:
            agent: The agent that just registered via session-start.
        """
        if not agent.persona_id:
            return

        # Find oldest pending membership for this persona
        membership = (
            ChannelMembership.query.join(Channel)
            .filter(
                ChannelMembership.persona_id == agent.persona_id,
                ChannelMembership.agent_id.is_(None),
                Channel.status == "pending",
            )
            .order_by(ChannelMembership.joined_at.asc())
            .first()
        )

        if not membership:
            return

        membership.agent_id = agent.id
        try:
            db.session.commit()
            logger.info(
                f"link_agent_to_pending_membership: linked agent_id={agent.id} "
                f"to membership_id={membership.id} (channel_id={membership.channel_id})"
            )
        except Exception as e:
            logger.warning(
                f"link_agent_to_pending_membership: commit failed for agent_id={agent.id}: {e}"
            )
            db.session.rollback()
            return

        self.check_channel_ready(membership.channel_id)

    def check_channel_ready(self, channel_id: int) -> bool:
        """Check whether all non-chair members of a pending channel are connected.

        If all connected, transitions the channel to active, injects a
        go-signal system message, and broadcasts ``channel_ready`` SSE.
        Always broadcasts ``channel_member_connected`` with the current counts.

        Args:
            channel_id: ID of the channel to check.

        Returns:
            True if the channel was transitioned to active, False otherwise.
        """
        channel = db.session.get(Channel, channel_id)
        if not channel:
            return False
        if channel.status != "pending":
            return False

        # Count non-chair memberships (these are the agent slots being spun up)
        non_chair_memberships = ChannelMembership.query.filter_by(
            channel_id=channel_id, is_chair=False, status="active"
        ).all()

        total = len(non_chair_memberships)
        connected = sum(1 for m in non_chair_memberships if m.agent_id is not None)

        # Determine the persona that just connected for the SSE payload.
        # Derive from the already-loaded list to avoid an extra DB query.
        connected_memberships = [
            m for m in non_chair_memberships if m.agent_id is not None
        ]
        just_connected_membership = (
            max(connected_memberships, key=lambda m: m.joined_at or 0)
            if connected_memberships
            else None
        )

        persona_name = ""
        persona_slug = ""
        agent_id = None
        if just_connected_membership and just_connected_membership.persona:
            persona_name = just_connected_membership.persona.name
            persona_slug = just_connected_membership.persona.slug
            agent_id = just_connected_membership.agent_id

        # Broadcast member-connected event
        self._broadcast_update(
            channel,
            "channel_member_connected",
            {
                "slug": channel.slug,
                "persona_name": persona_name,
                "persona_slug": persona_slug,
                "agent_id": agent_id,
                "connected_count": connected,
                "total_count": total,
            },
        )

        if total > 0 and connected >= total:
            # All agents connected — transition to active
            self._transition_to_active(channel)
            self._post_system_message(
                channel,
                "All agents connected — channel is ready.",
            )
            db.session.commit()
            self._broadcast_update(
                channel,
                "channel_ready",
                {
                    "slug": channel.slug,
                    "name": channel.name,
                },
            )
            logger.info(
                f"check_channel_ready: channel #{channel.slug} is now active "
                f"({connected}/{total} agents connected)"
            )
            return True

        logger.info(
            f"check_channel_ready: channel #{channel.slug} still pending "
            f"({connected}/{total} agents connected)"
        )
        return False

    # ── Internal orchestration helpers ───────────────────────────────

    def _broadcast_channel_created(self, channel: Channel) -> None:
        """Broadcast a ``channel_created`` SSE event with nested card data.

        Used by both ``create_channel`` and ``promote_to_group`` to notify
        the dashboard that a new channel card should be rendered.

        Args:
            channel: The newly created channel.
        """
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

    def _cleanup_channel_after_failure(self, channel_id: int) -> None:
        """Rollback and delete a channel after a failed orchestration.

        Used by promote_to_group to clean up partially-created channels
        when agent creation or other steps fail.

        Args:
            channel_id: The ID of the channel to clean up.
        """
        db.session.rollback()
        try:
            ch = db.session.get(Channel, channel_id)
            if ch:
                db.session.delete(ch)
                db.session.commit()
                logger.info(
                    f"Cleaned up channel #{channel_id} after promote-to-group failure"
                )
        except Exception as cleanup_err:
            logger.warning(
                f"Cleanup failed after promote-to-group error: {cleanup_err}"
            )

    def _spin_up_agent_for_persona(
        self, persona: Persona, project_id: int | None = None
    ) -> Agent | None:
        """Create a fresh agent for a persona.

        S11: Always spins up a new agent — never reuses an existing active
        agent. If ``project_id`` is None, logs a warning and returns None
        rather than silently falling back to an arbitrary project.

        Args:
            persona: The persona to spin up an agent for.
            project_id: Project to spin up the agent under. Required.

        Returns:
            None — agent creation is async. The agent will link to its
            ChannelMembership when it registers via the session-start hook.
        """
        if project_id is None:
            logger.warning(
                f"_spin_up_agent_for_persona: project_id is None for persona "
                f"{persona.slug} — cannot spin up without a project"
            )
            return None

        try:
            from .agent_lifecycle import create_agent

            result = create_agent(
                project_id=project_id,
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
            logger.info(
                f"Agent spin-up initiated for persona {persona.slug} "
                f"under project_id={project_id}"
            )
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
            # No history yet, but still inject the channel protocol
            return CHANNEL_PROTOCOL

        messages.reverse()  # Chronological order

        lines = [
            CHANNEL_PROTOCOL + "\n",
            f"=== Context briefing: #{channel.slug} "
            f"(last {len(messages)} messages) ===\n",
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
