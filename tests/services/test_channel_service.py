"""Tests for ChannelService — all channel business logic."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from claude_headspace.database import db
from claude_headspace.models.agent import Agent
from claude_headspace.models.channel import ChannelType
from claude_headspace.models.channel_membership import ChannelMembership
from claude_headspace.models.message import Message, MessageType
from claude_headspace.models.persona import Persona
from claude_headspace.models.persona_type import PersonaType
from claude_headspace.models.project import Project
from claude_headspace.models.role import Role
from claude_headspace.services.channel_service import (
    AgentChannelConflictError,
    AgentNotFoundError,
    AlreadyMemberError,
    ChannelClosedError,
    ChannelNotFoundError,
    NoCreationCapabilityError,
    NotAMemberError,
    NotChairError,
)


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
def channel_service(app, db_session):
    """Get the ChannelService from app extensions."""
    return app.extensions["channel_service"]


@pytest.fixture
def setup_data(app, db_session):
    """Create test data: role, personas, project, agents."""
    role = Role(name="developer")
    db.session.add(role)
    db.session.flush()

    pt_internal = db.session.get(PersonaType, 1)
    pt_external = db.session.get(PersonaType, 2)

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
    persona_ext = Persona(
        name="ExtUser",
        role_id=role.id,
        role=role,
        persona_type_id=pt_external.id,
        status="active",
    )
    db.session.add_all([persona_a, persona_b, persona_ext])
    db.session.flush()

    project = Project(
        name="test-project", slug="test-project", path="/tmp/test-project"
    )
    db.session.add(project)
    db.session.flush()

    agent_a = Agent(
        session_uuid=uuid4(), project_id=project.id, persona_id=persona_a.id
    )
    agent_b = Agent(
        session_uuid=uuid4(), project_id=project.id, persona_id=persona_b.id
    )
    db.session.add_all([agent_a, agent_b])
    db.session.commit()

    db.session.refresh(persona_a)
    db.session.refresh(persona_b)
    db.session.refresh(persona_ext)

    return {
        "persona_a": persona_a,
        "persona_b": persona_b,
        "persona_ext": persona_ext,
        "agent_a": agent_a,
        "agent_b": agent_b,
        "project": project,
        "role": role,
    }


class TestCreateChannel:
    def test_create_channel_success(self, channel_service, setup_data):
        channel = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="test-channel",
            channel_type="workshop",
            description="Test description",
        )
        assert channel.id is not None
        assert "workshop-test-channel" in channel.slug
        assert channel.status == "pending"
        assert channel.channel_type == ChannelType.WORKSHOP
        assert channel.description == "Test description"
        memberships = ChannelMembership.query.filter_by(channel_id=channel.id).all()
        assert len(memberships) == 1
        assert memberships[0].is_chair is True
        assert memberships[0].persona_id == setup_data["persona_a"].id

    def test_create_channel_with_members(self, channel_service, setup_data):
        channel = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="team-channel",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        memberships = ChannelMembership.query.filter_by(channel_id=channel.id).all()
        assert len(memberships) == 2

    def test_create_channel_no_capability(self, channel_service, setup_data):
        with pytest.raises(NoCreationCapabilityError) as exc_info:
            channel_service.create_channel(
                creator_persona=setup_data["persona_ext"],
                name="fail-channel",
                channel_type="workshop",
            )
        assert "does not have channel creation capability" in str(exc_info.value)


class TestListChannels:
    def test_list_member_scoped(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="my-channel",
            channel_type="workshop",
        )
        result = channel_service.list_channels(setup_data["persona_a"])
        assert len(result) == 1
        assert result[0].id == ch.id
        result = channel_service.list_channels(setup_data["persona_b"])
        assert len(result) == 0

    def test_list_all_visible(self, channel_service, setup_data):
        channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="visible",
            channel_type="workshop",
        )
        result = channel_service.list_channels(
            setup_data["persona_b"], all_visible=True
        )
        assert len(result) >= 1


class TestGetChannel:
    def test_get_channel_success(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="get-test",
            channel_type="review",
        )
        result = channel_service.get_channel(ch.slug)
        assert result.id == ch.id
        assert result.name == "get-test"

    def test_get_channel_not_found(self, channel_service, db_session):
        with pytest.raises(ChannelNotFoundError):
            channel_service.get_channel("nonexistent-slug")


class TestUpdateChannel:
    def test_update_by_chair(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="update-test",
            channel_type="workshop",
        )
        updated = channel_service.update_channel(
            ch.slug,
            setup_data["persona_a"],
            description="Updated desc",
            intent_override="New intent",
        )
        assert updated.description == "Updated desc"
        assert updated.intent_override == "New intent"

    def test_update_by_non_chair_fails(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="update-fail",
            channel_type="workshop",
        )
        with pytest.raises(NotChairError):
            channel_service.update_channel(
                ch.slug, setup_data["persona_b"], description="Nope"
            )


class TestCompleteChannel:
    def test_complete_by_chair(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="complete-test",
            channel_type="workshop",
        )
        completed = channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        assert completed.status == "complete"
        assert completed.completed_at is not None

    def test_complete_by_non_chair_fails(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="complete-fail",
            channel_type="workshop",
        )
        with pytest.raises(NotChairError):
            channel_service.complete_channel(ch.slug, setup_data["persona_b"])


class TestArchiveChannel:
    def test_archive_complete_channel(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="archive-test",
            channel_type="workshop",
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        archived = channel_service.archive_channel(ch.slug, setup_data["persona_a"])
        assert archived.status == "archived"
        assert archived.archived_at is not None

    def test_archive_active_channel_fails(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="archive-fail",
            channel_type="workshop",
        )
        with pytest.raises(ChannelClosedError):
            channel_service.archive_channel(ch.slug, setup_data["persona_a"])


class TestAddMember:
    def test_add_member_success(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="add-test",
            channel_type="workshop",
        )
        membership = channel_service.add_member(
            ch.slug,
            setup_data["persona_b"].slug,
            setup_data["persona_a"],
        )
        assert membership.persona_id == setup_data["persona_b"].id
        assert membership.status == "active"
        msgs = Message.query.filter_by(
            channel_id=ch.id, message_type=MessageType.SYSTEM
        ).all()
        assert any("Bob joined" in m.content for m in msgs)

    def test_add_member_already_member(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="dup-test",
            channel_type="workshop",
        )
        channel_service.add_member(
            ch.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
        )
        with pytest.raises(AlreadyMemberError):
            channel_service.add_member(
                ch.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
            )

    def test_add_member_closed_channel(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="closed-test",
            channel_type="workshop",
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        with pytest.raises(ChannelClosedError):
            channel_service.add_member(
                ch.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
            )

    def test_add_member_spin_up(self, channel_service, setup_data):
        setup_data["agent_b"].ended_at = datetime.now(timezone.utc)
        db.session.commit()
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="spinup-test",
            channel_type="workshop",
        )
        with patch(
            "claude_headspace.services.agent_lifecycle.create_agent"
        ) as mock_create:
            mock_result = MagicMock()
            mock_result.success = True
            mock_create.return_value = mock_result
            membership = channel_service.add_member(
                ch.slug,
                setup_data["persona_b"].slug,
                setup_data["persona_a"],
            )
            assert membership.agent_id is None


class TestAgentChannelConflict:
    def test_conflict_detected(self, channel_service, setup_data):
        ch1 = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="channel-1",
            channel_type="workshop",
        )
        channel_service.add_member(
            ch1.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
        )
        with pytest.raises(AgentChannelConflictError) as exc_info:
            channel_service._check_agent_channel_conflict(setup_data["agent_b"])
        assert "already an active member" in str(exc_info.value)
        assert "flask channel leave" in str(exc_info.value)


class TestLeaveChannel:
    def test_leave_success(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="leave-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        channel_service.leave_channel(ch.slug, setup_data["persona_b"])
        membership = ChannelMembership.query.filter_by(
            channel_id=ch.id, persona_id=setup_data["persona_b"].id
        ).first()
        assert membership.status == "left"
        assert membership.left_at is not None

    def test_last_member_leave_auto_completes(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="autocomp-test",
            channel_type="workshop",
        )
        channel_service.leave_channel(ch.slug, setup_data["persona_a"])
        db.session.refresh(ch)
        assert ch.status == "complete"


class TestTransferChair:
    def test_transfer_success(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="transfer-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        channel_service.transfer_chair(
            ch.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
        )
        a_m = ChannelMembership.query.filter_by(
            channel_id=ch.id, persona_id=setup_data["persona_a"].id
        ).first()
        b_m = ChannelMembership.query.filter_by(
            channel_id=ch.id, persona_id=setup_data["persona_b"].id
        ).first()
        assert a_m.is_chair is False
        assert b_m.is_chair is True

    def test_transfer_by_non_chair(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="transfer-fail",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        with pytest.raises(NotChairError):
            channel_service.transfer_chair(
                ch.slug, setup_data["persona_a"].slug, setup_data["persona_b"]
            )


class TestMuteUnmute:
    def test_mute_and_unmute(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="mute-test",
            channel_type="workshop",
        )
        channel_service.mute_channel(ch.slug, setup_data["persona_a"])
        membership = ChannelMembership.query.filter_by(
            channel_id=ch.id, persona_id=setup_data["persona_a"].id
        ).first()
        assert membership.status == "muted"

        channel_service.unmute_channel(ch.slug, setup_data["persona_a"])
        db.session.refresh(membership)
        assert membership.status == "active"


class TestSendMessage:
    def test_send_message_success(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="msg-test",
            channel_type="workshop",
        )
        msg = channel_service.send_message(ch.slug, "Hello!", setup_data["persona_a"])
        assert msg.id is not None
        assert msg.content == "Hello!"
        assert msg.message_type == MessageType.MESSAGE

    def test_first_message_activates_channel(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="activate-test",
            channel_type="workshop",
        )
        assert ch.status == "pending"
        channel_service.send_message(ch.slug, "First message", setup_data["persona_a"])
        db.session.refresh(ch)
        assert ch.status == "active"

    def test_send_to_closed_channel(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="closed-msg-test",
            channel_type="workshop",
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        with pytest.raises(ChannelClosedError):
            channel_service.send_message(ch.slug, "Nope", setup_data["persona_a"])

    def test_send_by_non_member(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="non-member-msg",
            channel_type="workshop",
        )
        with pytest.raises(NotAMemberError):
            channel_service.send_message(ch.slug, "Nope", setup_data["persona_b"])

    def test_system_message_type_rejected(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="system-reject",
            channel_type="workshop",
        )
        with pytest.raises(ValueError):
            channel_service.send_message(
                ch.slug, "hack", setup_data["persona_a"], message_type="system"
            )


class TestGetHistory:
    def test_history_success(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="history-test",
            channel_type="workshop",
        )
        channel_service.send_message(ch.slug, "First", setup_data["persona_a"])
        channel_service.send_message(ch.slug, "Second", setup_data["persona_a"])
        msgs = channel_service.get_history(ch.slug, setup_data["persona_a"])
        user_msgs = [m for m in msgs if m.message_type == MessageType.MESSAGE]
        assert len(user_msgs) == 2
        assert user_msgs[0].content == "First"

    def test_history_left_member_can_read(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="left-history",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        channel_service.send_message(ch.slug, "Before leave", setup_data["persona_a"])
        channel_service.leave_channel(ch.slug, setup_data["persona_b"])
        msgs = channel_service.get_history(ch.slug, setup_data["persona_b"])
        assert len(msgs) > 0

    def test_history_non_member_rejected(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="no-access",
            channel_type="workshop",
        )
        with pytest.raises(NotAMemberError):
            channel_service.get_history(ch.slug, setup_data["persona_b"])

    def test_history_pagination(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="paginate-test",
            channel_type="workshop",
        )
        for i in range(5):
            channel_service.send_message(ch.slug, f"Msg {i}", setup_data["persona_a"])
        msgs = channel_service.get_history(ch.slug, setup_data["persona_a"], limit=2)
        assert len(msgs) == 2


class TestContextBriefing:
    def test_briefing_format(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="briefing-test",
            channel_type="workshop",
        )
        channel_service.send_message(ch.slug, "Test message", setup_data["persona_a"])
        briefing = channel_service._generate_context_briefing(ch)
        assert "Context briefing" in briefing
        assert "Test message" in briefing
        assert "End of context briefing" in briefing

    def test_briefing_empty_channel(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="empty-briefing",
            channel_type="workshop",
        )
        briefing = channel_service._generate_context_briefing(ch)
        assert briefing == ""


class TestSSEBroadcasting:
    def test_broadcast_message(self, app, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="sse-msg-test",
            channel_type="workshop",
        )
        mock_broadcaster = MagicMock()
        app.extensions["broadcaster"] = mock_broadcaster
        channel_service.send_message(ch.slug, "SSE test", setup_data["persona_a"])
        calls = [
            c
            for c in mock_broadcaster.broadcast.call_args_list
            if c[0][0] == "channel_message"
        ]
        assert len(calls) >= 1

    def test_broadcast_update(self, app, channel_service, setup_data):
        mock_broadcaster = MagicMock()
        app.extensions["broadcaster"] = mock_broadcaster
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="sse-update-test",
            channel_type="workshop",
        )
        calls = [
            c
            for c in mock_broadcaster.broadcast.call_args_list
            if c[0][0] == "channel_update"
        ]
        assert len(calls) >= 1


class TestGetAvailableMembers:
    def test_returns_grouped_by_project(self, channel_service, setup_data):
        """Active agents with personas are returned grouped by project."""
        result = channel_service.get_available_members()
        assert len(result) >= 1
        project_group = result[0]
        assert "project_id" in project_group
        assert "project_name" in project_group
        assert "agents" in project_group
        agent_entry = project_group["agents"][0]
        assert "agent_id" in agent_entry
        assert "persona_name" in agent_entry
        assert "persona_slug" in agent_entry
        assert "role" in agent_entry

    def test_excludes_ended_agents(self, channel_service, setup_data):
        """Agents with ended_at set are excluded."""
        setup_data["agent_b"].ended_at = datetime.now(timezone.utc)
        db.session.commit()
        result = channel_service.get_available_members()
        all_agent_ids = [a["agent_id"] for group in result for a in group["agents"]]
        assert setup_data["agent_b"].id not in all_agent_ids

    def test_excludes_agents_without_persona(self, channel_service, setup_data):
        """Agents with persona_id=NULL are excluded."""
        no_persona_agent = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=None,
        )
        db.session.add(no_persona_agent)
        db.session.commit()
        result = channel_service.get_available_members()
        all_agent_ids = [a["agent_id"] for group in result for a in group["agents"]]
        assert no_persona_agent.id not in all_agent_ids

    def test_excludes_inactive_persona(self, channel_service, setup_data):
        """Agents whose persona status != 'active' are excluded."""
        setup_data["persona_b"].status = "inactive"
        db.session.commit()
        result = channel_service.get_available_members()
        all_agent_ids = [a["agent_id"] for group in result for a in group["agents"]]
        assert setup_data["agent_b"].id not in all_agent_ids


class TestAddMemberByAgent:
    def test_success(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="agent-add-test",
            channel_type="workshop",
        )
        membership = channel_service.add_member_by_agent(
            ch.slug, setup_data["agent_b"].id, setup_data["persona_a"]
        )
        assert membership.persona_id == setup_data["persona_b"].id
        assert membership.agent_id == setup_data["agent_b"].id
        assert membership.status == "active"

    def test_nonexistent_agent(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="agent-404-test",
            channel_type="workshop",
        )
        with pytest.raises(AgentNotFoundError):
            channel_service.add_member_by_agent(ch.slug, 99999, setup_data["persona_a"])

    def test_ended_agent(self, channel_service, setup_data):
        setup_data["agent_b"].ended_at = datetime.now(timezone.utc)
        db.session.commit()
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="agent-ended-test",
            channel_type="workshop",
        )
        with pytest.raises(AgentNotFoundError):
            channel_service.add_member_by_agent(
                ch.slug, setup_data["agent_b"].id, setup_data["persona_a"]
            )

    def test_already_member(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="agent-dup-test",
            channel_type="workshop",
        )
        channel_service.add_member_by_agent(
            ch.slug, setup_data["agent_b"].id, setup_data["persona_a"]
        )
        with pytest.raises(AlreadyMemberError):
            channel_service.add_member_by_agent(
                ch.slug, setup_data["agent_b"].id, setup_data["persona_a"]
            )


class TestCreateChannelWithAgentIds:
    def test_creates_with_agent_ids(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="agent-create-test",
            channel_type="workshop",
            member_agent_ids=[setup_data["agent_b"].id],
        )
        memberships = ChannelMembership.query.filter_by(channel_id=ch.id).all()
        assert len(memberships) == 2  # chair + 1 member
        agent_ids = [m.agent_id for m in memberships if m.agent_id]
        assert setup_data["agent_b"].id in agent_ids

    def test_agent_ids_take_precedence_over_slugs(self, channel_service, setup_data):
        """When both member_agent_ids and member_slugs are provided, agent_ids win."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="precedence-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
            member_agent_ids=[setup_data["agent_b"].id],
        )
        memberships = ChannelMembership.query.filter_by(channel_id=ch.id).all()
        # Should have 2 (chair + agent_b via agent_ids path)
        assert len(memberships) == 2
        non_chair = [m for m in memberships if not m.is_chair]
        assert len(non_chair) == 1
        assert non_chair[0].agent_id == setup_data["agent_b"].id
