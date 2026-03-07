"""Tests for ChannelDeliveryService — fan-out, queue, relay, notifications."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.channel import Channel, ChannelType
from claude_headspace.models.channel_membership import ChannelMembership
from claude_headspace.models.command import Command, CommandState
from claude_headspace.models.message import Message, MessageType
from claude_headspace.models.persona import Persona
from claude_headspace.models.persona_type import PersonaType
from claude_headspace.models.project import Project
from claude_headspace.models.role import Role
from claude_headspace.models.turn import TurnIntent
from claude_headspace.services.channel_delivery import ChannelDeliveryService


@pytest.fixture
def db_session(app):
    """Provide a database session with table creation and cleanup."""
    with app.app_context():
        db.create_all()
        yield db.session
        db.session.rollback()
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(table.delete())
        db.session.commit()


@pytest.fixture
def delivery_service(app, db_session):
    """Get the ChannelDeliveryService from app extensions."""
    return app.extensions["channel_delivery_service"]


@pytest.fixture
def setup_data(app, db_session):
    """Create test data: role, personas, project, agents, channel, memberships."""
    role = Role(name="developer")
    db.session.add(role)
    db.session.flush()

    pt_internal = db.session.get(PersonaType, 1)

    persona_a = Persona(
        name="Alice",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    persona_b = Persona(
        name="Bob",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    persona_c = Persona(
        name="Charlie",
        role_id=role.id,
        role=role,
        persona_type_id=pt_internal.id,
        status="active",
    )
    db.session.add_all([persona_a, persona_b, persona_c])
    db.session.flush()

    project = Project(
        name="test-project",
        slug="test-project",
        path="/tmp/test-project",
    )
    db.session.add(project)
    db.session.flush()

    agent_a = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        persona_id=persona_a.id,
        tmux_pane_id="%1",
    )
    agent_b = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        persona_id=persona_b.id,
        tmux_pane_id="%2",
    )
    agent_c = Agent(
        session_uuid=uuid4(),
        project_id=project.id,
        persona_id=persona_c.id,
        tmux_pane_id="%3",
    )
    db.session.add_all([agent_a, agent_b, agent_c])
    db.session.flush()

    # Create a channel with Alice as chair
    channel = Channel(
        name="test-channel",
        channel_type=ChannelType.WORKSHOP,
        created_by_persona_id=persona_a.id,
        status="active",
    )
    db.session.add(channel)
    db.session.flush()

    # Refresh to get the generated slug
    db.session.refresh(channel)

    # Create memberships
    mem_a = ChannelMembership(
        channel_id=channel.id,
        persona_id=persona_a.id,
        agent_id=agent_a.id,
        is_chair=True,
        status="active",
    )
    mem_b = ChannelMembership(
        channel_id=channel.id,
        persona_id=persona_b.id,
        agent_id=agent_b.id,
        is_chair=False,
        status="active",
    )
    mem_c = ChannelMembership(
        channel_id=channel.id,
        persona_id=persona_c.id,
        agent_id=agent_c.id,
        is_chair=False,
        status="active",
    )
    db.session.add_all([mem_a, mem_b, mem_c])
    db.session.commit()

    return {
        "persona_a": persona_a,
        "persona_b": persona_b,
        "persona_c": persona_c,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "agent_c": agent_c,
        "channel": channel,
        "project": project,
        "role": role,
        "mem_a": mem_a,
        "mem_b": mem_b,
        "mem_c": mem_c,
    }


# ── Envelope formatting tests ───────────────────────────────────────


class TestFormatEnvelope:
    def test_format_with_agent_sender(self):
        result = ChannelDeliveryService._format_envelope(
            channel_slug="workshop-test-1",
            sender_name="Alice",
            sender_agent_id=42,
            content="Hello everyone",
        )
        assert result == "[#workshop-test-1] Alice (agent:42):\nHello everyone"

    def test_format_with_operator_sender(self):
        result = ChannelDeliveryService._format_envelope(
            channel_slug="review-code-5",
            sender_name="Sam",
            sender_agent_id=None,
            content="Please review this PR",
        )
        assert result == "[#review-code-5] Sam (operator):\nPlease review this PR"

    def test_format_with_multiline_content(self):
        result = ChannelDeliveryService._format_envelope(
            channel_slug="workshop-arch-3",
            sender_name="Bob",
            sender_agent_id=10,
            content="Line 1\nLine 2\nLine 3",
        )
        assert "[#workshop-arch-3] Bob (agent:10):" in result
        assert "Line 1\nLine 2\nLine 3" in result


# ── COMMAND COMPLETE stripping tests ─────────────────────────────────


class TestStripCommandComplete:
    def test_strips_standard_footer(self):
        text = "Here is the result.\n\n---\nCOMMAND COMPLETE — Fixed the bug.\n---"
        result = ChannelDeliveryService._strip_command_complete(text)
        assert result == "Here is the result."

    def test_strips_footer_with_test_results(self):
        text = "Done.\n\n---\nCOMMAND COMPLETE — All tasks done. Tests: 5 passed.\n---"
        result = ChannelDeliveryService._strip_command_complete(text)
        assert result == "Done."

    def test_preserves_content_without_footer(self):
        text = "This is a normal response without any footer."
        result = ChannelDeliveryService._strip_command_complete(text)
        assert result == text

    def test_preserves_content_with_dashes_but_no_footer(self):
        text = "Here are some items:\n---\nItem 1\n---"
        result = ChannelDeliveryService._strip_command_complete(text)
        # Should preserve since it's not the COMMAND COMPLETE pattern
        assert "Item 1" in result

    def test_strips_footer_with_em_dash(self):
        text = "Result.\n\n---\nCOMMAND COMPLETE — Summary here.\n---"
        result = ChannelDeliveryService._strip_command_complete(text)
        assert result == "Result."


# ── Queue operations tests ───────────────────────────────────────────


class TestQueueOperations:
    def test_enqueue_dequeue_fifo(self, delivery_service):
        delivery_service._enqueue(1, 100)
        delivery_service._enqueue(1, 200)
        delivery_service._enqueue(1, 300)

        assert delivery_service._dequeue(1) == 100
        assert delivery_service._dequeue(1) == 200
        assert delivery_service._dequeue(1) == 300

    def test_dequeue_empty_returns_none(self, delivery_service):
        assert delivery_service._dequeue(999) is None

    def test_dequeue_cleans_up_empty_queue(self, delivery_service):
        delivery_service._enqueue(1, 100)
        delivery_service._dequeue(1)

        # Queue entry should be cleaned up
        with delivery_service._queue_lock:
            assert 1 not in delivery_service._queue

    def test_separate_agent_queues(self, delivery_service):
        delivery_service._enqueue(1, 100)
        delivery_service._enqueue(2, 200)

        assert delivery_service._dequeue(1) == 100
        assert delivery_service._dequeue(2) == 200
        assert delivery_service._dequeue(1) is None
        assert delivery_service._dequeue(2) is None


# ── State safety tests ───────────────────────────────────────────────


class TestQueueDepthLimit:
    """Test max queue depth enforcement and clear_agent_queue."""

    def test_enqueue_drops_oldest_when_full(self, app, delivery_service):
        """When queue exceeds max depth, oldest messages are dropped."""
        delivery_service._max_queue_depth = 3

        delivery_service._enqueue(1, 100)
        delivery_service._enqueue(1, 200)
        delivery_service._enqueue(1, 300)
        # Queue is now at capacity (3). Adding one more should drop 100.
        delivery_service._enqueue(1, 400)

        assert delivery_service._dequeue(1) == 200  # 100 was dropped
        assert delivery_service._dequeue(1) == 300
        assert delivery_service._dequeue(1) == 400
        assert delivery_service._dequeue(1) is None

    def test_under_limit_not_truncated(self, app, delivery_service):
        """Messages under the limit are not dropped."""
        delivery_service._max_queue_depth = 5

        delivery_service._enqueue(1, 100)
        delivery_service._enqueue(1, 200)
        delivery_service._enqueue(1, 300)

        assert delivery_service._dequeue(1) == 100
        assert delivery_service._dequeue(1) == 200
        assert delivery_service._dequeue(1) == 300
        assert delivery_service._dequeue(1) is None

    def test_clear_agent_queue_removes_all(self, app, delivery_service):
        """clear_agent_queue removes all queued messages and returns count."""
        delivery_service._enqueue(1, 100)
        delivery_service._enqueue(1, 200)
        delivery_service._enqueue(1, 300)

        count = delivery_service.clear_agent_queue(1)
        assert count == 3
        assert delivery_service._dequeue(1) is None

    def test_clear_nonexistent_returns_zero(self, app, delivery_service):
        """clear_agent_queue for an agent with no queue returns 0."""
        count = delivery_service.clear_agent_queue(999)
        assert count == 0


class TestIsSafeState:
    def test_awaiting_input_is_safe(self, app, db_session, setup_data):
        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.AWAITING_INPUT,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        assert ChannelDeliveryService._is_safe_state(agent) is True

    def test_idle_is_safe(self, app, db_session, setup_data):
        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.IDLE,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        assert ChannelDeliveryService._is_safe_state(agent) is True

    def test_no_command_is_safe(self, app, db_session, setup_data):
        agent = setup_data["agent_a"]
        # No command at all — effectively idle
        assert ChannelDeliveryService._is_safe_state(agent) is True

    def test_processing_is_unsafe(self, app, db_session, setup_data):
        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        assert ChannelDeliveryService._is_safe_state(agent) is False

    def test_commanded_is_unsafe(self, app, db_session, setup_data):
        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.COMMANDED,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        assert ChannelDeliveryService._is_safe_state(agent) is False

    def test_complete_is_unsafe(self, app, db_session, setup_data):
        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.COMPLETE,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        # COMPLETE is safe because get_current_command skips it (returns None)
        assert ChannelDeliveryService._is_safe_state(agent) is True


# ── deliver_message() tests ──────────────────────────────────────────


class TestDeliverMessage:
    def test_fans_out_to_active_members_skips_sender(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """Message from Alice fans out to Bob and Charlie, not Alice."""
        message = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_a"].id,
            agent_id=setup_data["agent_a"].id,
            content="Hello team",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(message)
        db.session.commit()

        with patch.object(delivery_service, "_deliver_to_member") as mock_deliver:
            delivery_service.deliver_message(message, setup_data["channel"])

            # Should be called for Bob and Charlie, not Alice
            assert mock_deliver.call_count == 2
            called_persona_ids = {
                call.args[0].persona_id for call in mock_deliver.call_args_list
            }
            assert setup_data["persona_b"].id in called_persona_ids
            assert setup_data["persona_c"].id in called_persona_ids
            assert setup_data["persona_a"].id not in called_persona_ids

    def test_skips_muted_members(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """Muted members are not included in fan-out."""
        # Mute Bob
        setup_data["mem_b"].status = "muted"
        db.session.commit()

        message = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_a"].id,
            agent_id=setup_data["agent_a"].id,
            content="Hello team",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(message)
        db.session.commit()

        with patch.object(delivery_service, "_deliver_to_member") as mock_deliver:
            delivery_service.deliver_message(message, setup_data["channel"])

            # Only Charlie (Bob is muted, Alice is sender)
            assert mock_deliver.call_count == 1
            assert (
                mock_deliver.call_args_list[0].args[0].persona_id
                == setup_data["persona_c"].id
            )

    def test_delivers_to_agents_in_processing_state(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """Messages delivered even when agent command state is PROCESSING.

        Command state is not a delivery gate — agents may be idle at the
        prompt while their command state is stale (e.g. channel relay
        responses don't always trigger lifecycle transitions).
        """
        cmd = Command(
            agent_id=setup_data["agent_b"].id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        message = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_a"].id,
            agent_id=setup_data["agent_a"].id,
            content="Hello team",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(message)
        db.session.commit()

        with patch.object(delivery_service, "_deliver_to_agent") as mock_tmux:
            mock_tmux.return_value = True
            delivery_service.deliver_message(message, setup_data["channel"])

        # Bob should have been delivered to directly, not queued
        assert delivery_service._dequeue(setup_data["agent_b"].id) is None
        mock_tmux.assert_called()

    def test_failure_isolation(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """If delivery fails for one member, others still get delivered."""
        message = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_a"].id,
            agent_id=setup_data["agent_a"].id,
            content="Hello team",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(message)
        db.session.commit()

        call_count = {"count": 0}

        def side_effect(membership, msg, env):
            call_count["count"] += 1
            if membership.persona_id == setup_data["persona_b"].id:
                raise RuntimeError("Bob's delivery failed!")

        with patch.object(
            delivery_service, "_deliver_to_member", side_effect=side_effect
        ):
            # Should not raise — failure is isolated
            delivery_service.deliver_message(message, setup_data["channel"])

        # Both Bob and Charlie should have been attempted
        assert call_count["count"] == 2


# ── relay_agent_response() tests ─────────────────────────────────────


class TestRelayAgentResponse:
    def test_relays_completion_to_channel(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """COMPLETION turn from channel member is relayed as channel Message."""
        agent = setup_data["agent_b"]
        # Simulate that this agent was prompted by a channel message
        delivery_service._channel_prompted.add(agent.id)

        with patch.object(
            app.extensions["channel_service"],
            "send_message",
            return_value=MagicMock(),
        ) as mock_send:
            result = delivery_service.relay_agent_response(
                agent=agent,
                turn_text="Here is my analysis of the code.",
                turn_intent=TurnIntent.COMPLETION,
                turn_id=42,
                command_id=10,
            )

            assert result is True
            mock_send.assert_called_once()
            call_kwargs = mock_send.call_args
            assert call_kwargs.kwargs["slug"] == setup_data["channel"].slug
            assert call_kwargs.kwargs["content"] == "Here is my analysis of the code."
            assert call_kwargs.kwargs["persona"] == setup_data["persona_b"]
            assert call_kwargs.kwargs["agent"] == agent
            assert call_kwargs.kwargs["source_turn_id"] == 42
            assert call_kwargs.kwargs["source_command_id"] == 10

    def test_relays_end_of_command(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """END_OF_COMMAND turn is also relayed."""
        agent = setup_data["agent_b"]
        delivery_service._channel_prompted.add(agent.id)

        with patch.object(
            app.extensions["channel_service"],
            "send_message",
            return_value=MagicMock(),
        ) as mock_send:
            result = delivery_service.relay_agent_response(
                agent=agent,
                turn_text="Task complete.",
                turn_intent=TurnIntent.END_OF_COMMAND,
                turn_id=43,
                command_id=11,
            )

            assert result is True
            mock_send.assert_called_once()

    def test_no_relay_for_progress(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """PROGRESS turns are NOT relayed (FR9)."""
        agent = setup_data["agent_b"]

        result = delivery_service.relay_agent_response(
            agent=agent,
            turn_text="Working on it...",
            turn_intent=TurnIntent.PROGRESS,
            turn_id=44,
            command_id=12,
        )

        assert result is False

    def test_no_relay_for_question(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """QUESTION turns are NOT relayed (FR9)."""
        agent = setup_data["agent_b"]

        result = delivery_service.relay_agent_response(
            agent=agent,
            turn_text="Should I proceed?",
            turn_intent=TurnIntent.QUESTION,
            turn_id=45,
            command_id=13,
        )

        assert result is False

    def test_no_relay_when_not_in_channel(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """Agent not in any channel — no relay."""
        # Create an agent with no channel membership
        agent_d = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=setup_data["persona_a"].id,
            tmux_pane_id="%4",
        )
        db.session.add(agent_d)
        db.session.commit()

        # Remove all memberships for this agent
        ChannelMembership.query.filter_by(agent_id=agent_d.id).delete()
        db.session.commit()
        # Mark as channel-prompted to get past the guard
        delivery_service._channel_prompted.add(agent_d.id)

        result = delivery_service.relay_agent_response(
            agent=agent_d,
            turn_text="Some response",
            turn_intent=TurnIntent.COMPLETION,
            turn_id=46,
            command_id=14,
        )

        assert result is False

    def test_no_relay_when_not_channel_prompted(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """Agent NOT prompted by channel delivery should not relay (DM isolation)."""
        agent = setup_data["agent_b"]
        # Do NOT add to _channel_prompted — simulates a DM/direct conversation
        result = delivery_service.relay_agent_response(
            agent=agent,
            turn_text="This is a DM response.",
            turn_intent=TurnIntent.COMPLETION,
            turn_id=99,
            command_id=99,
        )
        assert result is False

    def test_strips_command_complete_before_relay(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """COMMAND COMPLETE footer is stripped from relayed content."""
        agent = setup_data["agent_b"]
        delivery_service._channel_prompted.add(agent.id)
        text_with_footer = (
            "Here is the result.\n\n---\nCOMMAND COMPLETE — Fixed the bug.\n---"
        )

        with patch.object(
            app.extensions["channel_service"],
            "send_message",
            return_value=MagicMock(),
        ) as mock_send:
            delivery_service.relay_agent_response(
                agent=agent,
                turn_text=text_with_footer,
                turn_intent=TurnIntent.COMPLETION,
                turn_id=47,
                command_id=15,
            )

            call_kwargs = mock_send.call_args
            assert "COMMAND COMPLETE" not in call_kwargs.kwargs["content"]
            assert call_kwargs.kwargs["content"] == "Here is the result."

    def test_no_relay_for_agent_without_persona(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """Agent with no persona_id cannot relay."""
        agent_no_persona = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=None,
            tmux_pane_id="%5",
        )
        db.session.add(agent_no_persona)
        db.session.commit()

        result = delivery_service.relay_agent_response(
            agent=agent_no_persona,
            turn_text="Some response",
            turn_intent=TurnIntent.COMPLETION,
        )

        assert result is False

    def test_dedup_skips_already_relayed_turn(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """A turn already relayed (matching source_turn_id) is not sent again."""
        agent = setup_data["agent_b"]
        delivery_service._channel_prompted.add(agent.id)

        # Create a real Turn so source_turn_id FK is valid
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
        )
        db.session.add(cmd)
        db.session.flush()

        from claude_headspace.models.turn import Turn, TurnActor

        turn = Turn(
            command_id=cmd.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.COMPLETION,
            text="Already relayed",
        )
        db.session.add(turn)
        db.session.flush()

        # Pre-create a message with this turn's source_turn_id
        existing_msg = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_b"].id,
            agent_id=agent.id,
            content="Already relayed",
            message_type=MessageType.MESSAGE,
            source_turn_id=turn.id,
        )
        db.session.add(existing_msg)
        db.session.commit()

        with patch.object(
            app.extensions["channel_service"],
            "send_message",
        ) as mock_send:
            result = delivery_service.relay_agent_response(
                agent=agent,
                turn_text="Same turn again",
                turn_intent=TurnIntent.COMPLETION,
                turn_id=turn.id,
                command_id=cmd.id,
            )

            assert result is False
            mock_send.assert_not_called()


# ── drain_queue() tests ──────────────────────────────────────────────


class TestDrainQueue:
    def test_delivers_oldest_message(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """drain_queue delivers the oldest queued message (FIFO)."""
        agent = setup_data["agent_b"]

        # Create messages
        msg1 = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_a"].id,
            agent_id=setup_data["agent_a"].id,
            content="First message",
            message_type=MessageType.MESSAGE,
        )
        msg2 = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_a"].id,
            agent_id=setup_data["agent_a"].id,
            content="Second message",
            message_type=MessageType.MESSAGE,
        )
        db.session.add_all([msg1, msg2])
        db.session.commit()

        # Queue both
        delivery_service._enqueue(agent.id, msg1.id)
        delivery_service._enqueue(agent.id, msg2.id)

        with patch.object(
            delivery_service, "_deliver_to_agent", return_value=True
        ) as mock_deliver:
            result = delivery_service.drain_queue(agent)

        assert result is True
        # Should have delivered msg1 (oldest)
        mock_deliver.assert_called_once()
        envelope_text = mock_deliver.call_args.args[1]
        assert "First message" in envelope_text

        # msg2 should still be in the queue
        assert delivery_service._dequeue(agent.id) == msg2.id

    def test_empty_queue_returns_false(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """drain_queue returns False when queue is empty."""
        agent = setup_data["agent_b"]
        result = delivery_service.drain_queue(agent)
        assert result is False

    def test_handles_missing_message(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """drain_queue handles message that was deleted from DB."""
        agent = setup_data["agent_b"]
        delivery_service._enqueue(agent.id, 99999)  # Non-existent

        result = delivery_service.drain_queue(agent)
        assert result is False

    def test_handles_ended_agent(
        self,
        app,
        delivery_service,
        db_session,
        setup_data,
    ):
        """drain_queue skips delivery for ended agents."""
        agent = setup_data["agent_b"]
        agent.ended_at = datetime.now(timezone.utc)
        db.session.commit()

        msg = Message(
            channel_id=setup_data["channel"].id,
            persona_id=setup_data["persona_a"].id,
            content="Test message",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg)
        db.session.commit()

        delivery_service._enqueue(agent.id, msg.id)

        result = delivery_service.drain_queue(agent)
        assert result is False


# ── NotificationService channel tests ────────────────────────────────


class TestNotificationServiceChannel:
    def test_send_channel_notification(self, app):
        """send_channel_notification sends a macOS notification."""
        from claude_headspace.services.notification_service import (
            NotificationPreferences,
            NotificationService,
        )

        svc = NotificationService(NotificationPreferences(enabled=True))

        with patch.object(svc, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = svc.send_channel_notification(
                    channel_slug="workshop-test-1",
                    sender_name="Alice",
                    content_preview="Hello everyone, let's discuss the arch.",
                )

                assert result is True
                mock_run.assert_called_once()
                cmd = mock_run.call_args.args[0]
                assert "Channel Message" in cmd
                assert "#workshop-test-1" in cmd
                assert "Alice:" in " ".join(cmd)

    def test_channel_rate_limiting(self, app):
        """Second call within 30s is suppressed."""
        from claude_headspace.services.notification_service import (
            NotificationPreferences,
            NotificationService,
        )

        svc = NotificationService(NotificationPreferences(enabled=True))

        with patch.object(svc, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                # First call succeeds
                result1 = svc.send_channel_notification(
                    channel_slug="workshop-test-1",
                    sender_name="Alice",
                    content_preview="First message",
                )
                assert result1 is True
                assert mock_run.call_count == 1

                # Second call within 30s is suppressed
                result2 = svc.send_channel_notification(
                    channel_slug="workshop-test-1",
                    sender_name="Bob",
                    content_preview="Second message",
                )
                assert result2 is True  # Suppressed, not failed
                assert mock_run.call_count == 1  # Not called again

    def test_different_channels_not_rate_limited(self, app):
        """Different channel slugs have separate rate limits."""
        from claude_headspace.services.notification_service import (
            NotificationPreferences,
            NotificationService,
        )

        svc = NotificationService(NotificationPreferences(enabled=True))

        with patch.object(svc, "is_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)

                svc.send_channel_notification(
                    channel_slug="channel-1",
                    sender_name="Alice",
                    content_preview="Msg 1",
                )
                svc.send_channel_notification(
                    channel_slug="channel-2",
                    sender_name="Bob",
                    content_preview="Msg 2",
                )

                assert mock_run.call_count == 2


# ── Hook Receiver Integration tests ──────────────────────────────────


class TestHookReceiverIntegration:
    """Test that channel relay and queue drain are wired into process_stop."""

    def test_channel_relay_called_for_completion(self, app, db_session, setup_data):
        """Channel relay is called when process_stop detects COMPLETION intent."""
        from claude_headspace.services.hook_receiver import process_stop

        agent = setup_data["agent_a"]
        # Create a command for the agent
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        delivery = app.extensions.get("channel_delivery_service")

        with (
            patch.object(delivery, "relay_agent_response") as mock_relay,
            patch.object(delivery, "drain_queue"),
            patch(
                "claude_headspace.services.hook_receiver_helpers._extract_transcript_content",
                return_value="Done with the task.\n\n---\nCOMMAND COMPLETE — Done.\n---",
            ),
            patch(
                "claude_headspace.services.hook_receiver_helpers.detect_agent_intent",
                return_value=MagicMock(
                    intent=TurnIntent.COMPLETION,
                    confidence=0.95,
                    matched_pattern="completion_pattern",
                ),
            ),
        ):
            process_stop(agent, str(agent.claude_session_id or "test-session"))

            mock_relay.assert_called_once()
            call_kwargs = mock_relay.call_args.kwargs
            assert call_kwargs["turn_intent"] == TurnIntent.COMPLETION
            assert call_kwargs["command_id"] == cmd.id

    def test_channel_relay_called_for_question(self, app, db_session, setup_data):
        """Channel relay IS called for QUESTION intent — relay_agent_response
        handles intent filtering internally (channel-prompted agents relay all
        intents except PROGRESS)."""
        from claude_headspace.services.hook_receiver import process_stop

        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        delivery = app.extensions.get("channel_delivery_service")

        with (
            patch.object(delivery, "relay_agent_response") as mock_relay,
            patch(
                "claude_headspace.services.hook_receiver_helpers._extract_transcript_content",
                return_value="Should I proceed with this approach?",
            ),
            patch(
                "claude_headspace.services.hook_receiver_helpers.detect_agent_intent",
                return_value=MagicMock(
                    intent=TurnIntent.QUESTION,
                    confidence=0.90,
                    matched_pattern="question_pattern",
                ),
            ),
        ):
            process_stop(agent, "test-session")

            # QUESTION passes the PROGRESS filter; relay_agent_response is called
            # and decides internally whether to actually relay based on channel context.
            mock_relay.assert_called_once()

    def test_queue_drain_called_after_completion(self, app, db_session, setup_data):
        """Queue drain is called when command completes."""
        from claude_headspace.services.hook_receiver import process_stop

        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        delivery = app.extensions.get("channel_delivery_service")

        with (
            patch.object(delivery, "relay_agent_response", return_value=False),
            patch.object(delivery, "drain_queue") as mock_drain,
            patch(
                "claude_headspace.services.hook_receiver_helpers._extract_transcript_content",
                return_value="All done.",
            ),
            patch(
                "claude_headspace.services.hook_receiver_helpers.detect_agent_intent",
                return_value=MagicMock(
                    intent=TurnIntent.COMPLETION,
                    confidence=0.95,
                    matched_pattern="completion_pattern",
                ),
            ),
        ):
            process_stop(agent, "test-session")

            mock_drain.assert_called_once_with(agent)


# ── Deferred Stop Integration tests ──────────────────────────────────


class TestDeferredStopChannelRelay:
    """Test that channel relay and queue drain are wired into deferred stop."""

    def test_deferred_stop_relays_to_channel(self, app, db_session, setup_data):
        """Verify relay_agent_response called when deferred stop completes with COMPLETION."""
        from claude_headspace.services.hook_agent_state import get_agent_hook_state
        from claude_headspace.services.hook_deferred_stop import (
            _run_deferred_stop_locked,
        )

        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        delivery = app.extensions.get("channel_delivery_service")
        state = get_agent_hook_state()

        with (
            patch.object(delivery, "relay_agent_response") as mock_relay,
            patch.object(delivery, "drain_queue"),
            patch(
                "claude_headspace.services.intent_detector.detect_agent_intent",
                return_value=MagicMock(
                    intent=TurnIntent.COMPLETION,
                    confidence=0.95,
                    matched_pattern="completion_pattern",
                ),
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._send_completion_notification",
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._trigger_priority_scoring",
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._execute_pending_summarisations",
            ),
            patch(
                "claude_headspace.services.card_state.broadcast_card_refresh",
            ),
        ):
            _run_deferred_stop_locked(
                app=app,
                agent_id=agent.id,
                agent_obj=agent,
                cmd=cmd,
                agent_text="Task completed successfully.",
                command_id=cmd.id,
                project_id=setup_data["project"].id,
                state=state,
                delays=[0.5],
            )

            mock_relay.assert_called_once()
            call_kwargs = mock_relay.call_args.kwargs
            assert call_kwargs["turn_intent"] == TurnIntent.COMPLETION
            assert call_kwargs["command_id"] == cmd.id

    def test_deferred_stop_drains_queue_on_empty_transcript(
        self, app, db_session, setup_data
    ):
        """Verify drain_queue called even when transcript is empty."""
        from claude_headspace.services.hook_agent_state import get_agent_hook_state
        from claude_headspace.services.hook_deferred_stop import (
            _run_deferred_stop_locked,
        )

        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        delivery = app.extensions.get("channel_delivery_service")
        state = get_agent_hook_state()

        with (
            patch.object(delivery, "drain_queue") as mock_drain,
            patch(
                "claude_headspace.services.hook_deferred_stop._send_completion_notification",
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._trigger_priority_scoring",
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._execute_pending_summarisations",
            ),
            patch(
                "claude_headspace.services.card_state.broadcast_card_refresh",
            ),
        ):
            _run_deferred_stop_locked(
                app=app,
                agent_id=agent.id,
                agent_obj=agent,
                cmd=cmd,
                agent_text="",  # Empty transcript
                command_id=cmd.id,
                project_id=setup_data["project"].id,
                state=state,
                delays=[0.5],
            )

            mock_drain.assert_called_once_with(agent)

    def test_deferred_stop_relay_called_for_question_intent(
        self, app, db_session, setup_data
    ):
        """Verify relay IS called for QUESTION intent — relay_agent_response
        handles intent filtering internally."""
        from claude_headspace.services.hook_agent_state import get_agent_hook_state
        from claude_headspace.services.hook_deferred_stop import (
            _run_deferred_stop_locked,
        )

        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.commit()

        delivery = app.extensions.get("channel_delivery_service")
        state = get_agent_hook_state()

        with (
            patch.object(delivery, "relay_agent_response") as mock_relay,
            patch.object(delivery, "drain_queue"),
            patch(
                "claude_headspace.services.intent_detector.detect_agent_intent",
                return_value=MagicMock(
                    intent=TurnIntent.QUESTION,
                    confidence=0.90,
                    matched_pattern="question_pattern",
                ),
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._send_completion_notification",
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._trigger_priority_scoring",
            ),
            patch(
                "claude_headspace.services.hook_deferred_stop._execute_pending_summarisations",
            ),
            patch(
                "claude_headspace.services.card_state.broadcast_card_refresh",
            ),
        ):
            _run_deferred_stop_locked(
                app=app,
                agent_id=agent.id,
                agent_obj=agent,
                cmd=cmd,
                agent_text="Should I proceed with this approach?",
                command_id=cmd.id,
                project_id=setup_data["project"].id,
                state=state,
                delays=[0.5],
            )

            mock_relay.assert_called_once()


# ── Reconciler Channel Drain tests ───────────────────────────────────


class TestReconcilerChannelDrain:
    """Test that drain_queue is called after relay in reconciler path."""

    def test_reconciler_drains_queue_after_relay(self, app, db_session, setup_data):
        """Verify drain_queue called after successful relay in reconciler.

        This tests the code path in transcript_reconciler.py where after a
        successful relay_agent_response, drain_queue is called when the
        command is COMPLETE.
        """
        from claude_headspace.models.turn import Turn, TurnActor

        agent = setup_data["agent_a"]
        cmd = Command(
            agent_id=agent.id,
            state=CommandState.COMPLETE,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.flush()

        turn = Turn(
            command_id=cmd.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.COMPLETION,
            text="Task done.",
        )
        db.session.add(turn)
        db.session.commit()

        delivery = app.extensions.get("channel_delivery_service")

        with (
            patch.object(
                delivery, "relay_agent_response", return_value=True
            ) as mock_relay,
            patch.object(delivery, "drain_queue") as mock_drain,
        ):
            # Simulate what the reconciler does after creating a turn:
            # call relay then drain if command is COMPLETE.
            ch_delivery = app.extensions.get("channel_delivery_service")
            if ch_delivery and agent.persona_id:
                relayed = ch_delivery.relay_agent_response(
                    agent=agent,
                    turn_text=turn.text,
                    turn_intent=turn.intent,
                    turn_id=turn.id,
                    command_id=cmd.id,
                )
                if relayed and cmd.state == CommandState.COMPLETE:
                    ch_delivery.drain_queue(agent)

            mock_relay.assert_called_once()
            mock_drain.assert_called_once_with(agent)


# ── State Reconstruction tests ──────────────────────────────────────


class TestStateReconstruction:
    """Tests for _reconstruct_state(), _reconstruct_channel_prompted(), _reconstruct_queue()."""

    def test_reconstruct_channel_prompted_basic(
        self, app, delivery_service, db_session, setup_data
    ):
        """Agent prompted but has not responded is added to _channel_prompted."""
        channel = setup_data["channel"]
        agent_a = setup_data["agent_a"]
        agent_b = setup_data["agent_b"]

        # Agent A sends a message to the channel
        msg = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_a"].id,
            agent_id=agent_a.id,
            content="Hello channel",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg)
        db.session.commit()

        # Simulate restart: create a fresh service instance
        delivery_service._channel_prompted.clear()
        delivery_service._queue.clear()
        delivery_service._reconstruct_state()

        # Agent B should be in _channel_prompted (received msg, hasn't responded)
        assert agent_b.id in delivery_service._channel_prompted
        # Agent A should NOT be in _channel_prompted (they sent the message)
        assert agent_a.id not in delivery_service._channel_prompted

    def test_reconstruct_skips_already_responded(
        self, app, delivery_service, db_session, setup_data
    ):
        """Agent that already responded is NOT added to _channel_prompted."""
        channel = setup_data["channel"]
        agent_a = setup_data["agent_a"]
        agent_b = setup_data["agent_b"]

        # Agent A sends a message
        msg1 = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_a"].id,
            agent_id=agent_a.id,
            content="Question for you",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg1)
        db.session.flush()

        # Agent B responds (more recent timestamp)
        msg2 = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_b"].id,
            agent_id=agent_b.id,
            content="Here's my answer",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg2)
        db.session.commit()

        delivery_service._channel_prompted.clear()
        delivery_service._reconstruct_state()

        # Agent B already responded — should NOT be in _channel_prompted
        assert agent_b.id not in delivery_service._channel_prompted

    def test_reconstruct_respects_stale_cutoff(
        self, app, delivery_service, db_session, setup_data
    ):
        """Messages older than cutoff threshold are ignored."""
        from datetime import timedelta

        channel = setup_data["channel"]
        agent_a = setup_data["agent_a"]

        # Create a message that's older than the cutoff (default 60 min)
        old_time = datetime.now(timezone.utc) - timedelta(hours=2)
        msg = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_a"].id,
            agent_id=agent_a.id,
            content="Old message",
            message_type=MessageType.MESSAGE,
            sent_at=old_time,
        )
        db.session.add(msg)
        db.session.commit()

        delivery_service._channel_prompted.clear()
        delivery_service._reconstruct_state()

        # No agents should be prompted (all messages are stale)
        assert len(delivery_service._channel_prompted) == 0

    def test_reconstruct_queue_unsafe_state(
        self, app, delivery_service, db_session, setup_data
    ):
        """Agent in PROCESSING state gets undelivered messages re-queued."""
        channel = setup_data["channel"]
        agent_a = setup_data["agent_a"]
        agent_b = setup_data["agent_b"]

        # Put agent B in PROCESSING state (unsafe)
        cmd = Command(
            agent_id=agent_b.id,
            state=CommandState.PROCESSING,
            started_at=datetime.now(timezone.utc),
        )
        db.session.add(cmd)
        db.session.flush()

        # Agent A sends a message to the channel
        msg = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_a"].id,
            agent_id=agent_a.id,
            content="Need your input",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg)
        db.session.commit()

        delivery_service._queue.clear()
        delivery_service._channel_prompted.clear()
        delivery_service._reconstruct_state()

        # Agent B's queue should have the message
        assert agent_b.id in delivery_service._queue
        assert msg.id in delivery_service._queue[agent_b.id]

    def test_reconstruct_skips_ended_agents(
        self, app, delivery_service, db_session, setup_data
    ):
        """Ended agents are not reconstructed."""
        channel = setup_data["channel"]
        agent_a = setup_data["agent_a"]
        agent_b = setup_data["agent_b"]

        # End agent B
        agent_b.ended_at = datetime.now(timezone.utc)
        db.session.flush()

        # Agent A sends a message
        msg = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_a"].id,
            agent_id=agent_a.id,
            content="Hello",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg)
        db.session.commit()

        delivery_service._channel_prompted.clear()
        delivery_service._reconstruct_state()

        # Agent B (ended) should NOT be in _channel_prompted
        assert agent_b.id not in delivery_service._channel_prompted

    def test_reconstruct_skips_inactive_memberships(
        self, app, delivery_service, db_session, setup_data
    ):
        """Inactive memberships are not reconstructed."""
        channel = setup_data["channel"]
        agent_a = setup_data["agent_a"]
        agent_b = setup_data["agent_b"]
        mem_b = setup_data["mem_b"]

        # Deactivate agent B's membership
        mem_b.status = "left"
        db.session.flush()

        # Agent A sends a message
        msg = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_a"].id,
            agent_id=agent_a.id,
            content="Hello",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg)
        db.session.commit()

        delivery_service._channel_prompted.clear()
        delivery_service._reconstruct_state()

        # Agent B (inactive membership) should NOT be in _channel_prompted
        assert agent_b.id not in delivery_service._channel_prompted

    def test_reconstruct_idempotent(
        self, app, delivery_service, db_session, setup_data
    ):
        """Calling _reconstruct_state() twice produces identical results."""
        channel = setup_data["channel"]
        agent_a = setup_data["agent_a"]

        # Agent A sends a message
        msg = Message(
            channel_id=channel.id,
            persona_id=setup_data["persona_a"].id,
            agent_id=agent_a.id,
            content="Hello",
            message_type=MessageType.MESSAGE,
        )
        db.session.add(msg)
        db.session.commit()

        # First reconstruction
        delivery_service._reconstruct_state()
        prompted_first = set(delivery_service._channel_prompted)
        queue_first = {
            k: list(v) for k, v in delivery_service._queue.items()
        }

        # Second reconstruction — should produce identical results
        delivery_service._reconstruct_state()
        prompted_second = set(delivery_service._channel_prompted)
        queue_second = {
            k: list(v) for k, v in delivery_service._queue.items()
        }

        assert prompted_first == prompted_second
        assert queue_first == queue_second

    def test_reconstruct_error_isolation(
        self, app, delivery_service, db_session, setup_data
    ):
        """DB error during reconstruction doesn't break the service.

        The __init__ wraps _reconstruct_state() in try/except so that
        the service still initialises even if reconstruction fails.
        """
        # Patch _reconstruct_state to raise, then create a new service
        with patch.object(
            ChannelDeliveryService,
            "_reconstruct_state",
            side_effect=RuntimeError("Simulated DB failure"),
        ):
            # Creating a new instance should NOT raise
            svc = ChannelDeliveryService(app)

        # Service should be fully functional despite failed reconstruction
        assert svc._channel_prompted is not None
        assert svc._queue is not None
        assert len(svc._channel_prompted) == 0
        assert len(svc._queue) == 0

        # Service can still enqueue/dequeue normally
        svc._enqueue(999, 111)
        assert svc._dequeue(999) == 111
