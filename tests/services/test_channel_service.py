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
    ChannelDeletePreconditionError,
    ChannelNotFoundError,
    NoCreationCapabilityError,
    NotAMemberError,
    NotChairError,
    PersonaNotFoundError,
    PromoteToGroupError,
    SoleChairError,
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
        channel_service.create_channel(
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
        projects = result["projects"]
        assert len(projects) >= 1
        project_group = projects[0]
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
        all_agent_ids = [
            a["agent_id"] for group in result["projects"] for a in group["agents"]
        ]
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
        all_agent_ids = [
            a["agent_id"] for group in result["projects"] for a in group["agents"]
        ]
        assert no_persona_agent.id not in all_agent_ids

    def test_excludes_inactive_persona(self, channel_service, setup_data):
        """Agents whose persona status != 'active' are excluded."""
        setup_data["persona_b"].status = "inactive"
        db.session.commit()
        result = channel_service.get_available_members()
        all_agent_ids = [
            a["agent_id"] for group in result["projects"] for a in group["agents"]
        ]
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

    def test_create_with_members_auto_activates(self, channel_service, setup_data):
        """Bug #4: Channel transitions to active when members are added at creation."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="auto-active-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        assert ch.status == "active"

    def test_create_without_members_stays_pending(self, channel_service, setup_data):
        """Channel without additional members stays pending after creation."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="stays-pending-test",
            channel_type="workshop",
        )
        assert ch.status == "pending"


class TestCompleteChannelReleasesMembers:
    """Bug #2: complete_channel releases active memberships."""

    def test_active_memberships_set_to_left(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="release-complete-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        memberships = ChannelMembership.query.filter_by(channel_id=ch.id).all()
        for m in memberships:
            assert m.status == "left"
            assert m.left_at is not None


class TestArchiveChannelReleasesMembers:
    """Bug #2: archive_channel releases remaining memberships."""

    def test_remaining_memberships_released(self, channel_service, setup_data):
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="release-archive-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        channel_service.archive_channel(ch.slug, setup_data["persona_a"])
        memberships = ChannelMembership.query.filter_by(channel_id=ch.id).all()
        for m in memberships:
            assert m.status == "left"
            assert m.left_at is not None


class TestGetAvailableMembersPersonas:
    """Bug #1: get_available_members includes person-type personas."""

    def test_returns_personas_section(self, channel_service, setup_data):
        """Response includes a 'personas' key."""
        result = channel_service.get_available_members()
        assert "personas" in result

    def test_person_type_personas_included(self, channel_service, setup_data):
        """Person-type personas appear in the personas list."""
        # Create a person-type persona (id=3 = person/internal)
        pt_person = db.session.get(PersonaType, 3)
        role = setup_data["role"]
        operator = Persona(
            name="Operator Sam",
            role_id=role.id,
            role=role,
            persona_type_id=pt_person.id,
            status="active",
        )
        db.session.add(operator)
        db.session.commit()
        db.session.refresh(operator)

        result = channel_service.get_available_members()
        persona_slugs = [p["persona_slug"] for p in result["personas"]]
        assert operator.slug in persona_slugs

    def test_agent_type_personas_excluded_from_personas_list(
        self, channel_service, setup_data
    ):
        """Agent-type personas without active agents do NOT appear in personas list."""
        # Make agent_b ended so persona_b has no active agent
        setup_data["agent_b"].ended_at = datetime.now(timezone.utc)
        db.session.commit()

        result = channel_service.get_available_members()
        persona_slugs = [p["persona_slug"] for p in result["personas"]]
        # persona_b is agent/internal type, should NOT be in personas list
        assert setup_data["persona_b"].slug not in persona_slugs

    def test_deduplicates_agents_by_persona_and_project(
        self, channel_service, setup_data
    ):
        """Bug #3: Duplicate agents for the same persona in the same project are deduplicated."""
        # Create a second agent for persona_a on the same project
        dupe_agent = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=setup_data["persona_a"].id,
        )
        db.session.add(dupe_agent)
        db.session.commit()

        result = channel_service.get_available_members()
        # Count how many times persona_a appears in the test-project group
        for group in result["projects"]:
            if group["project_id"] == setup_data["project"].id:
                persona_a_entries = [
                    a
                    for a in group["agents"]
                    if a["persona_slug"] == setup_data["persona_a"].slug
                ]
                assert len(persona_a_entries) == 1


class TestAgentChannelConflictScoping:
    """Bug fix: _check_agent_channel_conflict only blocks for open channels."""

    def test_no_conflict_after_channel_completed(self, channel_service, setup_data):
        """Agent can join a new channel after their previous channel was completed."""
        ch1 = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="old-channel",
            channel_type="workshop",
        )
        channel_service.add_member(
            ch1.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
        )
        channel_service.complete_channel(ch1.slug, setup_data["persona_a"])

        # Should NOT raise — the completed channel doesn't block
        channel_service._check_agent_channel_conflict(setup_data["agent_b"])

    def test_conflict_still_raised_for_active_channel(
        self, channel_service, setup_data
    ):
        """Agent in an active channel still triggers conflict."""
        ch1 = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="active-channel",
            channel_type="workshop",
        )
        channel_service.add_member(
            ch1.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
        )

        with pytest.raises(AgentChannelConflictError):
            channel_service._check_agent_channel_conflict(setup_data["agent_b"])


class TestJoinChannel:
    """Tests for join_channel — self-join without membership/chair check."""

    def test_join_success(self, channel_service, setup_data):
        """Persona can self-join a channel they're not a member of."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="open-channel",
            channel_type="workshop",
        )
        membership = channel_service.join_channel(ch.slug, setup_data["persona_b"])
        assert membership.persona_id == setup_data["persona_b"].id
        assert membership.status == "active"
        assert membership.is_chair is False

    def test_join_transitions_pending_to_active(self, channel_service, setup_data):
        """Joining a pending channel transitions it to active."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="pending-channel",
            channel_type="workshop",
        )
        assert ch.status == "pending"
        channel_service.join_channel(ch.slug, setup_data["persona_b"])
        assert ch.status == "active"

    def test_join_already_member_raises(self, channel_service, setup_data):
        """Cannot join a channel you're already a member of."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="member-channel",
            channel_type="workshop",
        )
        with pytest.raises(AlreadyMemberError):
            channel_service.join_channel(ch.slug, setup_data["persona_a"])

    def test_join_closed_channel_raises(self, channel_service, setup_data):
        """Cannot join a completed channel."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="closed-channel",
            channel_type="workshop",
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        with pytest.raises(ChannelClosedError):
            channel_service.join_channel(ch.slug, setup_data["persona_b"])

    def test_join_creates_system_message(self, channel_service, setup_data):
        """Joining posts a system message."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="msg-channel",
            channel_type="workshop",
        )
        channel_service.join_channel(ch.slug, setup_data["persona_b"])
        messages = Message.query.filter_by(
            channel_id=ch.id, message_type=MessageType.SYSTEM
        ).all()
        join_msgs = [m for m in messages if "Bob joined" in m.content]
        assert len(join_msgs) == 1


# ──────────────────────────────────────────────────────────────
# Delete Channel Tests
# ──────────────────────────────────────────────────────────────


class TestDeleteChannel:
    """Test ChannelService.delete_channel."""

    def test_delete_archived_channel(self, channel_service, setup_data):
        """Archived channel can be deleted."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="to-delete",
            channel_type="workshop",
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        channel_service.archive_channel(ch.slug, setup_data["persona_a"])
        channel_service.delete_channel(ch.slug, setup_data["persona_a"])

        # Verify deleted
        from claude_headspace.models.channel import Channel

        assert Channel.query.filter_by(slug=ch.slug).first() is None

    def test_delete_active_with_members_raises(self, channel_service, setup_data):
        """Active channel with members cannot be deleted."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="active-channel",
            channel_type="workshop",
        )
        with pytest.raises(ChannelDeletePreconditionError):
            channel_service.delete_channel(ch.slug, setup_data["persona_a"])

    def test_delete_not_found_raises(self, channel_service, setup_data):
        """Non-existent channel raises ChannelNotFoundError."""
        with pytest.raises(ChannelNotFoundError):
            channel_service.delete_channel("nonexistent", setup_data["persona_a"])


# ──────────────────────────────────────────────────────────────
# Remove Member Tests
# ──────────────────────────────────────────────────────────────


class TestRemoveMember:
    """Test ChannelService.remove_member."""

    def test_remove_member_success(self, channel_service, setup_data):
        """Chair can remove a non-chair member."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="remove-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        channel_service.remove_member(
            ch.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
        )
        # Verify member is now "left"
        membership = ChannelMembership.query.filter_by(
            channel_id=ch.id, persona_id=setup_data["persona_b"].id
        ).first()
        assert membership.status == "left"

    def test_remove_sole_chair_raises(self, channel_service, setup_data):
        """Cannot remove the sole chair."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="sole-chair-test",
            channel_type="workshop",
        )
        with pytest.raises(SoleChairError):
            channel_service.remove_member(
                ch.slug, setup_data["persona_a"].slug, setup_data["persona_a"]
            )

    def test_remove_non_member_raises(self, channel_service, setup_data):
        """Cannot remove someone who isn't a member."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="non-member-test",
            channel_type="workshop",
        )
        with pytest.raises(NotAMemberError):
            channel_service.remove_member(
                ch.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
            )

    def test_remove_from_closed_channel_raises(self, channel_service, setup_data):
        """Cannot remove from a completed channel."""
        ch = channel_service.create_channel(
            creator_persona=setup_data["persona_a"],
            name="closed-remove-test",
            channel_type="workshop",
            member_slugs=[setup_data["persona_b"].slug],
        )
        channel_service.complete_channel(ch.slug, setup_data["persona_a"])
        with pytest.raises(ChannelClosedError):
            channel_service.remove_member(
                ch.slug, setup_data["persona_b"].slug, setup_data["persona_a"]
            )


# ── Conversation History Retrieval ───────────────────────────────


class TestGetAgentConversationHistory:
    """Tests for get_agent_conversation_history method."""

    def _create_turns(self, agent, n, db_session):
        """Helper: create n turns for an agent across a single command."""
        from datetime import timedelta

        from claude_headspace.models.command import Command, CommandState
        from claude_headspace.models.turn import Turn, TurnActor, TurnIntent

        cmd = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db.session.add(cmd)
        db.session.flush()
        base_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        turns = []
        for i in range(n):
            actor = TurnActor.USER if i % 2 == 0 else TurnActor.AGENT
            intent = TurnIntent.COMMAND if i % 2 == 0 else TurnIntent.PROGRESS
            t = Turn(
                command_id=cmd.id,
                actor=actor,
                intent=intent,
                text=f"Turn {i + 1} text",
                timestamp=base_time + timedelta(minutes=i),
            )
            db.session.add(t)
            turns.append(t)
        db.session.commit()
        return turns

    def test_empty_history(self, channel_service, setup_data):
        """Agent with no turns returns empty list."""
        result = channel_service.get_agent_conversation_history(setup_data["agent_a"])
        assert result == []

    def test_fewer_than_limit(self, channel_service, setup_data, db_session):
        """Agent with 5 turns returns all 5."""
        self._create_turns(setup_data["agent_a"], 5, db_session)
        result = channel_service.get_agent_conversation_history(
            setup_data["agent_a"], limit=20
        )
        assert len(result) == 5
        # Should be in chronological order
        assert result[0].text == "Turn 1 text"
        assert result[4].text == "Turn 5 text"

    def test_exactly_at_limit(self, channel_service, setup_data, db_session):
        """Agent with exactly 20 turns returns 20."""
        self._create_turns(setup_data["agent_a"], 20, db_session)
        result = channel_service.get_agent_conversation_history(
            setup_data["agent_a"], limit=20
        )
        assert len(result) == 20

    def test_more_than_limit(self, channel_service, setup_data, db_session):
        """Agent with 30 turns returns only the last 20."""
        self._create_turns(setup_data["agent_a"], 30, db_session)
        result = channel_service.get_agent_conversation_history(
            setup_data["agent_a"], limit=20
        )
        assert len(result) == 20
        # Should be the most recent 20 (turns 11-30)
        assert result[0].text == "Turn 11 text"
        assert result[19].text == "Turn 30 text"


# ── Promote to Group ─────────────────────────────────────────────


class TestPromoteToGroup:
    """Tests for promote_to_group orchestration."""

    @pytest.fixture
    def promote_personas(self, db_session):
        """Create a dedicated set of personas for promote-to-group tests.

        Creates:
        - operator_persona: the operator (person/internal)
        - original_persona: persona for the original agent
        - target_persona: the persona to add to the group channel
        - original_agent: agent with original_persona
        """
        role = Role(name="promote-dev")
        db.session.add(role)
        db.session.flush()

        pt_internal = db.session.get(PersonaType, 1)

        operator_persona = Persona(
            name="OpPerson",
            role_id=role.id,
            role=role,
            persona_type_id=pt_internal.id,
            status="active",
        )
        original_persona = Persona(
            name="OrigAgent",
            role_id=role.id,
            role=role,
            persona_type_id=pt_internal.id,
            status="active",
        )
        target_persona = Persona(
            name="TargetAgent",
            role_id=role.id,
            role=role,
            persona_type_id=pt_internal.id,
            status="active",
        )
        db.session.add_all([operator_persona, original_persona, target_persona])
        db.session.flush()

        project = Project(
            name="promote-project", slug="promote-project", path="/tmp/promote-project"
        )
        db.session.add(project)
        db.session.flush()

        original_agent = Agent(
            session_uuid=uuid4(),
            project_id=project.id,
            persona_id=original_persona.id,
        )
        db.session.add(original_agent)
        db.session.commit()

        db.session.refresh(operator_persona)
        db.session.refresh(original_persona)
        db.session.refresh(target_persona)

        return {
            "operator": operator_persona,
            "original_persona": original_persona,
            "target_persona": target_persona,
            "original_agent": original_agent,
            "project": project,
        }

    def test_happy_path(self, channel_service, promote_personas, db_session):
        """Successful promote-to-group creates channel with correct members."""
        from claude_headspace.models.channel_membership import ChannelMembership

        d = promote_personas

        with patch(
            "claude_headspace.services.agent_lifecycle.create_agent",
            return_value=MagicMock(success=True, message="ok"),
        ):
            with patch.object(Persona, "get_operator", return_value=d["operator"]):
                channel = channel_service.promote_to_group(
                    agent=d["original_agent"],
                    persona_slug=d["target_persona"].slug,
                )

        assert channel is not None
        assert channel.channel_type.value == "workshop"
        assert channel.status == "active"
        assert channel.spawned_from_agent_id == d["original_agent"].id

        # Check memberships: operator + original persona + target persona = 3
        memberships = ChannelMembership.query.filter_by(channel_id=channel.id).all()
        assert len(memberships) == 3

        # Check system message was posted
        messages = Message.query.filter_by(
            channel_id=channel.id,
            message_type=MessageType.SYSTEM,
        ).all()
        assert len(messages) == 1
        assert "Channel created from conversation" in messages[0].content

    def test_agent_no_persona_raises(self, channel_service, setup_data, db_session):
        """Agent without persona raises AgentNotFoundError."""
        # Create agent with no persona
        agent_no_persona = Agent(
            session_uuid=uuid4(),
            project_id=setup_data["project"].id,
            persona_id=None,
        )
        db.session.add(agent_no_persona)
        db.session.commit()

        with pytest.raises(AgentNotFoundError, match="no persona"):
            channel_service.promote_to_group(
                agent=agent_no_persona,
                persona_slug="some-slug",
            )

    def test_persona_not_found_raises(self, channel_service, setup_data, db_session):
        """Non-existent persona slug raises PersonaNotFoundError."""
        with pytest.raises(PersonaNotFoundError, match="not found"):
            channel_service.promote_to_group(
                agent=setup_data["agent_a"],
                persona_slug="nonexistent-persona",
            )

    def test_cleanup_on_agent_spinup_failure(
        self, channel_service, promote_personas, db_session
    ):
        """Channel is cleaned up if agent spin-up fails."""
        from claude_headspace.models.channel import Channel

        d = promote_personas
        initial_count = Channel.query.count()

        with patch(
            "claude_headspace.services.agent_lifecycle.create_agent",
            return_value=MagicMock(success=False, message="tmux error"),
        ):
            with patch.object(Persona, "get_operator", return_value=d["operator"]):
                with pytest.raises(PromoteToGroupError, match="Failed to create"):
                    channel_service.promote_to_group(
                        agent=d["original_agent"],
                        persona_slug=d["target_persona"].slug,
                    )

        # Channel should have been cleaned up
        assert Channel.query.count() == initial_count


# ── Persona Filtering ────────────────────────────────────────────


class TestPromoteToGroupPersonaFiltering:
    """Tests for persona filtering in promote-to-group."""

    def test_persona_filtering_is_client_side(
        self, channel_service, setup_data, db_session
    ):
        """Persona filtering (excluding original + operator) is done client-side.

        The service accepts any valid persona slug. If duplicate membership
        would result, it raises a DB error. This test verifies the service
        works with distinct personas.
        """
        # Use persona_b as operator, agent_a as original (has persona_a),
        # and persona_ext as target — all three are distinct
        with patch.object(
            Persona, "get_operator", return_value=setup_data["persona_b"]
        ):
            with patch(
                "claude_headspace.services.agent_lifecycle.create_agent",
                return_value=MagicMock(success=True, message="ok"),
            ):
                channel = channel_service.promote_to_group(
                    agent=setup_data["agent_a"],
                    persona_slug=setup_data["persona_ext"].slug,
                )
                assert channel is not None
                assert channel.status == "active"

    def test_operator_not_found_raises(self, channel_service, setup_data, db_session):
        """Missing operator persona raises PromoteToGroupError."""
        with patch.object(Persona, "get_operator", return_value=None):
            with pytest.raises(PromoteToGroupError, match="No operator"):
                channel_service.promote_to_group(
                    agent=setup_data["agent_a"],
                    persona_slug=setup_data["persona_b"].slug,
                )
