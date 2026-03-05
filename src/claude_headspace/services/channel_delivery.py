"""ChannelDeliveryService — fan-out engine for channel message delivery.

Delivers channel messages to members via tmux (agents), notifications
(operators), and defers for offline personas. Captures agent responses
back into the channel when stop hooks fire with COMPLETION or END_OF_COMMAND
intents.

Registered as app.extensions["channel_delivery_service"].

Design decisions from Inter-Agent Communication Workshop:
- Post-commit side effect pattern (same as SSE broadcasts and notifications)
- In-memory delivery queue (dict[int, deque[int]]) — no new DB tables
- State safety: only AWAITING_INPUT and IDLE are safe for tmux delivery
- Completion-only relay: only COMPLETION and END_OF_COMMAND turns fan out
- Best-effort delivery: no retry logic
- Feedback loop prevention: completion-only relay + source tracking + IntentDetector gating
"""

import logging
import re
import threading
from collections import deque

from ..database import db
from ..models.agent import Agent
from ..models.channel import Channel
from ..models.channel_membership import ChannelMembership
from ..models.command import CommandState
from ..models.message import Message
from ..models.turn import TurnIntent

logger = logging.getLogger(__name__)

# Regex to strip the COMMAND COMPLETE footer from relayed content.
# The footer format is:
#   ---
#   COMMAND COMPLETE — <summary>
#   ---
# Optionally followed by test results or trailing whitespace.
_COMMAND_COMPLETE_RE = re.compile(
    r"\n*---\s*\nCOMMAND COMPLETE\s*[—–-].*?\n---\s*$",
    re.DOTALL,
)

# States where tmux delivery is safe (agent is idle or waiting for input)
_SAFE_DELIVERY_STATES = frozenset({CommandState.AWAITING_INPUT, CommandState.IDLE})


class ChannelDeliveryService:
    """Fan-out engine for channel message delivery and agent response capture.

    Responsible for:
    - Delivering messages to channel members after ChannelService.send_message() commits
    - Formatting tmux envelopes for agent delivery
    - Managing an in-memory delivery queue for agents in unsafe states
    - Relaying agent COMPLETION/END_OF_COMMAND responses back into the channel
    - Per-channel notification rate limiting for operators
    """

    def __init__(self, app):
        self.app = app
        # In-memory delivery queue: agent_id -> deque of Message IDs
        self._queue: dict[int, deque[int]] = {}
        self._queue_lock = threading.Lock()
        # Track which agents were last prompted by a channel message delivery.
        # Only agents in this set should have their completions relayed back
        # into the channel. Prevents DM responses from leaking into channels.
        self._channel_prompted: set[int] = set()
        self._max_queue_depth = (
            app.config.get("APP_CONFIG", {})
            .get("channels", {})
            .get("max_queue_depth_per_agent", 50)
        )

    # ── Envelope formatting ──────────────────────────────────────────

    @staticmethod
    def _format_envelope(
        channel_slug: str,
        sender_name: str,
        sender_agent_id: int | None,
        content: str,
    ) -> str:
        """Format a message in the channel envelope for tmux delivery.

        Format:
            [#channel-slug] PersonaName (agent:ID):
            {content}

        Args:
            channel_slug: The channel's slug identifier.
            sender_name: The sender's persona name.
            sender_agent_id: The sender's agent ID, or None for operators.
            content: The message content (COMMAND COMPLETE already stripped).

        Returns:
            Formatted envelope string.
        """
        agent_label = f"agent:{sender_agent_id}" if sender_agent_id else "operator"
        return f"[#{channel_slug}] {sender_name} ({agent_label}):\n{content}"

    @staticmethod
    def _strip_command_complete(text: str) -> str:
        """Strip the COMMAND COMPLETE footer from message content.

        The footer is a machine-parseable signal for monitoring software,
        not conversational content. It is retained on the agent's Turn
        record but stripped before channel relay.

        Args:
            text: The raw message/turn text.

        Returns:
            Text with the COMMAND COMPLETE footer removed.
        """
        return _COMMAND_COMPLETE_RE.sub("", text).rstrip()

    # ── State safety ─────────────────────────────────────────────────

    @staticmethod
    def _is_safe_state(agent: Agent) -> bool:
        """Check if an agent is in a state safe for tmux message delivery.

        Only AWAITING_INPUT and IDLE are safe. PROCESSING, COMMANDED, and
        COMPLETE mean the agent is busy or finished, and injecting text
        could corrupt the session.

        Args:
            agent: The agent to check.

        Returns:
            True if the agent is in a safe delivery state.
        """
        command = agent.get_current_command()
        if command is None:
            # No active command = effectively IDLE
            return True
        return command.state in _SAFE_DELIVERY_STATES

    # ── Queue operations ─────────────────────────────────────────────

    def _enqueue(self, agent_id: int, message_id: int) -> None:
        """Add a message to an agent's delivery queue (thread-safe).

        Args:
            agent_id: The target agent's ID.
            message_id: The Message ID to queue.
        """
        with self._queue_lock:
            if agent_id not in self._queue:
                self._queue[agent_id] = deque()
            self._queue[agent_id].append(message_id)
            # Enforce max queue depth — drop oldest messages on overflow
            q = self._queue[agent_id]
            while len(q) > self._max_queue_depth:
                dropped = q.popleft()
                logger.warning(
                    f"Queue overflow for agent {agent_id}: dropped oldest "
                    f"message {dropped} (depth exceeded {self._max_queue_depth})"
                )
        logger.debug(
            f"Queued message {message_id} for agent {agent_id} "
            f"(queue depth: {len(self._queue.get(agent_id, []))})"
        )

    def _dequeue(self, agent_id: int) -> int | None:
        """Remove and return the oldest message from an agent's queue.

        Args:
            agent_id: The agent's ID.

        Returns:
            The oldest Message ID, or None if queue is empty.
        """
        with self._queue_lock:
            q = self._queue.get(agent_id)
            if not q:
                # Clean up empty queue entry
                self._queue.pop(agent_id, None)
                return None
            message_id = q.popleft()
            if not q:
                del self._queue[agent_id]
            return message_id

    def clear_agent_queue(self, agent_id: int) -> int:
        """Remove all queued messages for a given agent.

        Called during agent cleanup (e.g. by the AgentReaper) to prevent
        stale messages from accumulating for dead agents.

        Args:
            agent_id: The agent whose queue should be cleared.

        Returns:
            The number of messages that were removed.
        """
        with self._queue_lock:
            q = self._queue.pop(agent_id, None)
            count = len(q) if q else 0
        self._channel_prompted.discard(agent_id)
        if count:
            logger.info(f"Cleared {count} queued message(s) for agent {agent_id}")
        return count

    # ── Single-agent delivery ────────────────────────────────────────

    def _deliver_to_agent(
        self,
        agent: Agent,
        envelope_text: str,
    ) -> bool:
        """Deliver a formatted envelope to a single agent via tmux.

        Checks CommanderAvailability and agent state before delivery.

        Args:
            agent: The target agent.
            envelope_text: Pre-formatted envelope text.

        Returns:
            True if delivered successfully, False if queued or failed.
        """
        if not agent.tmux_pane_id:
            logger.warning(f"Cannot deliver to agent {agent.id}: no tmux_pane_id")
            return False

        # Check pane health via CommanderAvailability
        commander = self.app.extensions.get("commander_availability")
        if commander and not commander.is_available(agent.id):
            logger.warning(
                f"Cannot deliver to agent {agent.id}: pane unavailable "
                f"(CommanderAvailability)"
            )
            return False

        # Deliver via tmux bridge
        tmux_bridge = self.app.extensions.get("tmux_bridge")
        if not tmux_bridge:
            logger.warning("tmux_bridge not available for channel delivery")
            return False

        try:
            result = tmux_bridge.send_text(agent.tmux_pane_id, envelope_text)
            if hasattr(result, "success") and not result.success:
                logger.warning(f"tmux delivery failed for agent {agent.id}: {result}")
                return False
            logger.info(f"Channel message delivered to agent {agent.id} via tmux")
            return True
        except Exception as e:
            logger.warning(f"tmux delivery exception for agent {agent.id}: {e}")
            return False

    # ── Fan-out engine ───────────────────────────────────────────────

    def deliver_message(self, message: Message, channel: Channel) -> None:
        """Fan out a message to all active members excluding the sender.

        Called as a post-commit side effect after ChannelService.send_message().
        Iterates active (non-muted) memberships, delivers per member type:
        - Agent (online, safe state): tmux send_text with envelope
        - Agent (online, unsafe state): queue for later delivery
        - Agent (offline): deferred (message persists in channel history)
        - Operator/external: notification only (SSE already handled by ChannelService)

        Args:
            message: The persisted Message to deliver.
            channel: The channel the message belongs to.
        """
        # Build envelope content
        sender_name = message.persona.name if message.persona else "System"
        content = self._strip_command_complete(message.content)
        envelope = self._format_envelope(
            channel_slug=channel.slug,
            sender_name=sender_name,
            sender_agent_id=message.agent_id,
            content=content,
        )

        # Get all active memberships, excluding sender
        memberships = ChannelMembership.query.filter_by(
            channel_id=channel.id, status="active"
        ).all()

        logger.info(
            f"[DELIVERY_FORENSIC] deliver_message: channel=#{channel.slug}, "
            f"sender_persona={message.persona_id}, sender_agent={message.agent_id}, "
            f"total_memberships={len(memberships)}, "
            f"member_ids=[{', '.join(f'p{m.persona_id}/a{m.agent_id}' for m in memberships)}]"
        )

        for membership in memberships:
            # Skip the sender
            if message.persona_id and membership.persona_id == message.persona_id:
                continue

            try:
                self._deliver_to_member(membership, message, envelope)
            except Exception as e:
                # FR4: failure isolation — log and continue
                logger.warning(
                    f"Delivery failed for membership {membership.id} "
                    f"(persona_id={membership.persona_id}): {e}"
                )

            # Operator notification — independent of agent delivery path.
            # The operator may not have an agent (dashboard-only), so
            # _notify_operator_if_applicable must run for every recipient
            # membership, not just those with tmux delivery.
            try:
                self._notify_operator_if_applicable(membership, message)
            except Exception as e:
                logger.debug(f"Operator notification check failed: {e}")

    def _deliver_to_member(
        self,
        membership: ChannelMembership,
        message: Message,
        envelope: str,
    ) -> None:
        """Deliver a message to a single channel member.

        Determines delivery mechanism based on member type and agent status.

        Args:
            membership: The target ChannelMembership.
            message: The Message being delivered.
            envelope: Pre-formatted envelope text for tmux delivery.
        """
        agent = membership.agent

        # No agent linked or agent ended — try to self-heal by finding a
        # live agent for the same persona (handles new sessions replacing old).
        if agent is None or agent.ended_at is not None:
            live_agent = (
                Agent.query.filter_by(
                    persona_id=membership.persona_id,
                )
                .filter(Agent.ended_at.is_(None))
                .order_by(Agent.id.desc())
                .first()
            )
            if live_agent and live_agent.tmux_pane_id:
                try:
                    membership.agent_id = live_agent.id
                    db.session.commit()
                    agent = live_agent
                    logger.info(
                        f"Self-healed channel membership {membership.id}: "
                        f"agent_id updated to {agent.id} (inbound delivery)"
                    )
                except Exception:
                    db.session.rollback()
                    agent = None

            if agent is None or agent.ended_at is not None:
                logger.debug(
                    f"Deferred delivery for persona {membership.persona_id} "
                    f"(no active agent)"
                )
                return

        # Agent exists — check if it's an internal agent with tmux
        if not agent.tmux_pane_id:
            # Remote/external agent — SSE already handled by ChannelService
            logger.debug(
                f"Skipping tmux delivery for agent {agent.id} "
                f"(no tmux_pane_id — remote/external)"
            )
            return

        # Internal agent with tmux — check state safety
        if not self._is_safe_state(agent):
            # Queue for later delivery — but still mark as channel-prompted
            # so the agent's completion response gets relayed back to the
            # channel. The agent was prompted by a channel conversation even
            # if the message delivery is deferred.
            current_cmd = agent.get_current_command()
            cmd_state = current_cmd.state.value if current_cmd else "NO_CMD"
            self._enqueue(agent.id, message.id)
            self._channel_prompted.add(agent.id)
            logger.info(
                f"[DELIVERY_FORENSIC] QUEUED message {message.id} for agent "
                f"{agent.id} (unsafe state={cmd_state}, persona_id={agent.persona_id}), "
                f"channel_prompted set={sorted(self._channel_prompted)}"
            )
            return

        # Safe state — deliver immediately
        logger.info(
            f"[DELIVERY_FORENSIC] Attempting tmux delivery to agent {agent.id} "
            f"(persona_id={agent.persona_id}, pane={agent.tmux_pane_id})"
        )
        delivered = self._deliver_to_agent(agent, envelope)
        if delivered:
            # Mark agent as channel-prompted so relay_agent_response knows
            # the next completion is a channel response, not a DM response.
            self._channel_prompted.add(agent.id)
            logger.info(
                f"[DELIVERY_FORENSIC] agent {agent.id} added to _channel_prompted "
                f"(set now={sorted(self._channel_prompted)})"
            )
        else:
            # Delivery failed — queue for retry on next state transition
            self._enqueue(agent.id, message.id)
            logger.info(
                f"[DELIVERY_FORENSIC] tmux delivery FAILED for agent {agent.id}, "
                f"queued message {message.id}"
            )

    def _notify_operator_if_applicable(
        self,
        membership: ChannelMembership,
        message: Message,
    ) -> None:
        """Send a macOS notification if the member is the operator.

        Operators get notifications for channel messages so they can see
        activity without watching the dashboard.

        Args:
            membership: The target membership.
            message: The message being delivered.
        """
        try:
            from ..models.persona import Persona

            persona = membership.persona
            if not persona:
                return

            # Check if this persona is the operator (person/internal type)
            operator = Persona.get_operator()
            if not operator or operator.id != persona.id:
                return

            notification_service = self.app.extensions.get("notification_service")
            if notification_service:
                channel = membership.channel
                sender_name = message.persona.name if message.persona else "System"
                notification_service.send_channel_notification(
                    channel_slug=channel.slug,
                    sender_name=sender_name,
                    content_preview=message.content[:100],
                )
        except Exception as e:
            logger.debug(f"Operator notification failed (non-fatal): {e}")

    # ── Agent response capture ───────────────────────────────────────

    def relay_agent_response(
        self,
        agent: Agent,
        turn_text: str,
        turn_intent: TurnIntent,
        turn_id: int | None = None,
        command_id: int | None = None,
    ) -> bool:
        """Relay an agent's completion response to the agent's active channel.

        Called from hook_receiver.process_stop() when a Turn is classified as
        COMPLETION or END_OF_COMMAND for a channel member.

        Args:
            agent: The agent whose response is being relayed.
            turn_text: The agent's response text.
            turn_intent: The classified intent (must be COMPLETION or END_OF_COMMAND).
            turn_id: The source Turn ID for traceability.
            command_id: The source Command ID for traceability.

        Returns:
            True if the response was posted as a channel Message, False otherwise.
        """
        logger.info(
            f"[RELAY_FORENSIC] relay_agent_response ENTRY: "
            f"agent_id={agent.id}, persona_id={agent.persona_id}, "
            f"intent={turn_intent.value}, turn_id={turn_id}, "
            f"command_id={command_id}, "
            f"channel_prompted_set={sorted(self._channel_prompted)}, "
            f"text_len={len(turn_text) if turn_text else 0}"
        )

        # FR9: completion-only relay — BUT channel-prompted agents get a wider
        # gate because channel conversations naturally contain question marks
        # (e.g. "Should we use approach A or B?") that the IntentDetector
        # classifies as QUESTION.  These are still valid channel responses.
        # Only PROGRESS is filtered out for channel-prompted agents.
        is_channel_prompted = agent.id in self._channel_prompted
        if is_channel_prompted:
            if turn_intent == TurnIntent.PROGRESS:
                logger.info(
                    f"[RELAY_FORENSIC] SKIP: intent=progress for "
                    f"channel-prompted agent={agent.id}"
                )
                return False
        else:
            if turn_intent not in (TurnIntent.COMPLETION, TurnIntent.END_OF_COMMAND):
                logger.info(
                    f"[RELAY_FORENSIC] SKIP: intent={turn_intent.value} "
                    f"not COMPLETION/END_OF_COMMAND (agent={agent.id})"
                )
                return False

        if not agent.persona_id:
            logger.info(f"[RELAY_FORENSIC] SKIP: no persona_id (agent={agent.id})")
            return False

        # Only relay if this agent was prompted by a channel message delivery.
        # Without this check, DM/direct conversations with a channel member
        # would leak into the channel (every completion gets relayed).
        if agent.id not in self._channel_prompted:
            logger.info(
                f"[RELAY_FORENSIC] SKIP: agent {agent.id} NOT in "
                f"_channel_prompted={sorted(self._channel_prompted)} — "
                f"likely a direct/DM conversation"
            )
            return False
        # Consume the flag — one delivery, one relay
        self._channel_prompted.discard(agent.id)
        logger.info(
            f"[RELAY_FORENSIC] PASSED channel_prompted gate: agent={agent.id}, "
            f"remaining_prompted={sorted(self._channel_prompted)}"
        )

        # Look up the agent's active channel membership (by agent_id only).
        # No persona fallback here — self-heal belongs on the inbound delivery
        # path (deliver_message), not on the outbound relay path.  A new agent
        # for the same persona should NOT be auto-enrolled into old channels
        # just because it completed a turn.
        membership = ChannelMembership.query.filter_by(
            agent_id=agent.id, status="active"
        ).first()

        if not membership:
            logger.info(
                f"[RELAY_FORENSIC] SKIP: no active membership for agent_id={agent.id} "
                f"(persona_id={agent.persona_id})"
            )
            return False

        logger.info(
            f"[RELAY_FORENSIC] Found membership: agent={agent.id}, "
            f"channel=#{membership.channel.slug if membership.channel else '?'}, "
            f"membership_id={membership.id}"
        )

        channel = membership.channel
        if channel.status not in ("active", "pending"):
            logger.debug(
                f"Agent {agent.id} channel #{channel.slug} is "
                f"{channel.status} — skipping relay"
            )
            return False

        # Dedup: if this turn was already relayed (e.g., hook_receiver relayed it
        # and reconciler also tries), skip to prevent duplicate channel messages.
        if turn_id:
            existing = Message.query.filter_by(
                channel_id=channel.id, source_turn_id=turn_id
            ).first()
            if existing:
                logger.info(
                    f"[RELAY_FORENSIC] SKIP DEDUP: agent {agent.id} turn {turn_id} "
                    f"already relayed to #{channel.slug} (msg_id={existing.id})"
                )
                return False

        # Strip COMMAND COMPLETE footer from the response
        cleaned_text = self._strip_command_complete(turn_text)
        if not cleaned_text.strip():
            logger.debug(
                f"Agent {agent.id} response is empty after stripping — skipping relay"
            )
            return False

        # Post the response as a channel Message via ChannelService
        try:
            channel_service = self.app.extensions.get("channel_service")
            if not channel_service:
                logger.warning("channel_service not available for response relay")
                return False

            channel_service.send_message(
                slug=channel.slug,
                content=cleaned_text,
                persona=membership.persona,
                agent=agent,
                message_type="message",
                source_turn_id=turn_id,
                source_command_id=command_id,
            )
            logger.info(
                f"Relayed agent {agent.id} response to channel "
                f"#{channel.slug} (turn_id={turn_id})"
            )
            return True
        except Exception as e:
            logger.warning(f"Channel relay failed for agent {agent.id}: {e}")
            return False

    # ── Delivery queue drain ─────────────────────────────────────────

    def drain_queue(self, agent: Agent) -> bool:
        """Deliver the oldest queued message for an agent.

        Called when the CommandLifecycleManager transitions an agent to a
        safe state (AWAITING_INPUT or IDLE). Delivers one message per
        transition — the agent processes it, eventually transitions to a
        safe state again, and the next queued message delivers on that
        transition.

        Args:
            agent: The agent to drain the queue for.

        Returns:
            True if a message was delivered, False if queue was empty.
        """
        message_id = self._dequeue(agent.id)
        if message_id is None:
            return False

        # Look up the message
        try:
            message = db.session.get(Message, message_id)
        except Exception as exc:
            logger.exception(
                "DB error looking up queued message %s for agent %s: %s",
                message_id,
                agent.id,
                exc,
            )
            message = None

        if not message:
            logger.warning(
                f"Queued message {message_id} not found for agent {agent.id} — skipping"
            )
            return False

        channel = message.channel
        if not channel:
            logger.warning(f"Message {message_id} has no channel — skipping drain")
            return False

        # Don't deliver to completed/archived channels
        if channel.status not in ("active", "pending"):
            logger.debug(
                f"Channel #{channel.slug} is {channel.status} — "
                f"dropping queued message {message_id} for agent {agent.id}"
            )
            return False

        # Build envelope
        sender_name = message.persona.name if message.persona else "System"
        content = self._strip_command_complete(message.content)
        envelope = self._format_envelope(
            channel_slug=channel.slug,
            sender_name=sender_name,
            sender_agent_id=message.agent_id,
            content=content,
        )

        # Check agent is still alive and has tmux
        if agent.ended_at or not agent.tmux_pane_id:
            logger.warning(
                f"Agent {agent.id} no longer available for queued "
                f"delivery — dropping message {message_id}"
            )
            return False

        delivered = self._deliver_to_agent(agent, envelope)
        if delivered:
            self._channel_prompted.add(agent.id)
        else:
            # Re-queue if delivery failed (front of queue for FIFO)
            with self._queue_lock:
                if agent.id not in self._queue:
                    self._queue[agent.id] = deque()
                self._queue[agent.id].appendleft(message_id)
            logger.warning(
                f"Queue drain delivery failed for agent {agent.id}, "
                f"message {message_id} — re-queued"
            )

        return delivered
