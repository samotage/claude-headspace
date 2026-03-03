"""Tests for the channels API routes."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from claude_headspace.routes.channels_api import channels_api_bp
from claude_headspace.services.channel_service import (
    AgentChannelConflictError,
    AlreadyMemberError,
    ChannelClosedError,
    ChannelNotFoundError,
    ContentTooLongError,
    NoCreationCapabilityError,
    NotAMemberError,
    NotChairError,
)
from claude_headspace.services.session_token import SessionTokenService

# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def token_service():
    return SessionTokenService()


@pytest.fixture
def mock_channel_service():
    return MagicMock()


@pytest.fixture
def mock_operator():
    """Create a mock operator persona."""
    operator = MagicMock()
    operator.id = 1
    operator.slug = "person-sam-1"
    operator.name = "Sam"
    operator.can_create_channel = True
    return operator


@pytest.fixture
def mock_agent_persona():
    """Create a mock agent persona (for token auth)."""
    persona = MagicMock()
    persona.id = 2
    persona.slug = "architect-robbo-2"
    persona.name = "Robbo"
    persona.can_create_channel = True
    return persona


@pytest.fixture
def mock_agent(mock_agent_persona):
    """Create a mock agent with persona."""
    agent = MagicMock()
    agent.id = 100
    agent.persona = mock_agent_persona
    return agent


@pytest.fixture
def app(token_service, mock_channel_service):
    """Create a test Flask application with channels API blueprint."""
    test_app = Flask(__name__)
    test_app.register_blueprint(channels_api_bp)
    test_app.config["TESTING"] = True
    test_app.config["APP_CONFIG"] = {}
    test_app.extensions = {
        "channel_service": mock_channel_service,
        "session_token_service": token_service,
    }
    return test_app


@pytest.fixture
def client(app):
    return app.test_client()


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────


def _make_mock_channel(
    slug="workshop-test-1",
    name="Test",
    status="pending",
    description=None,
    memberships=None,
    completed_at=None,
    archived_at=None,
):
    """Create a mock Channel object for serialization tests."""
    ch = MagicMock()
    ch.id = 1
    ch.slug = slug
    ch.name = name
    ch.channel_type.value = "workshop"
    ch.status = status
    ch.description = description
    ch.intent_override = None
    ch.organisation_id = None
    ch.project_id = None
    ch.created_at.isoformat.return_value = "2026-03-03T10:00:00+00:00"

    if completed_at:
        ch.completed_at.isoformat.return_value = completed_at
    else:
        ch.completed_at = None

    if archived_at:
        ch.archived_at.isoformat.return_value = archived_at
    else:
        ch.archived_at = None

    if memberships is None:
        # Default: one chair member
        chair = MagicMock()
        chair.is_chair = True
        chair.status = "active"
        chair.persona.slug = "person-sam-1"
        ch.memberships = [chair]
    else:
        ch.memberships = memberships

    return ch


def _patch_operator(mock_operator):
    """Patch Persona.get_operator to return our mock operator."""
    return patch(
        "claude_headspace.models.persona.Persona.get_operator",
        return_value=mock_operator,
    )


def _patch_no_operator():
    """Patch Persona.get_operator to return None (no operator)."""
    return patch(
        "claude_headspace.models.persona.Persona.get_operator",
        return_value=None,
    )


def _patch_resolve_caller(persona, agent=None):
    """Patch _resolve_caller to return a specific (persona, agent) tuple."""
    return patch(
        "claude_headspace.routes.channels_api._resolve_caller",
        return_value=(persona, agent),
    )


# ──────────────────────────────────────────────────────────────
# Auth Tests (Section 3.2)
# ──────────────────────────────────────────────────────────────


class TestAuth:
    """Test dual authentication: Bearer token and session cookie."""

    def test_no_auth_returns_401(self, client):
        """No auth mechanism present -> 401."""
        with _patch_no_operator():
            resp = client.get("/api/channels")
            assert resp.status_code == 401
            data = resp.get_json()
            assert data["error"]["code"] == "unauthorized"

    def test_invalid_token_returns_401(self, client):
        """Invalid Bearer token -> 401."""
        with _patch_no_operator():
            resp = client.get(
                "/api/channels",
                headers={"Authorization": "Bearer bad-token"},
            )
            assert resp.status_code == 401
            data = resp.get_json()
            assert data["error"]["code"] == "invalid_session_token"

    def test_valid_token_resolves_to_persona(
        self,
        client,
        token_service,
        mock_channel_service,
        mock_agent,
        mock_agent_persona,
    ):
        """Valid Bearer token resolves agent -> persona."""
        mock_channel_service.list_channels.return_value = []

        with _patch_resolve_caller(mock_agent_persona, mock_agent):
            resp = client.get("/api/channels")
            assert resp.status_code == 200
            mock_channel_service.list_channels.assert_called_once()
            call_kwargs = mock_channel_service.list_channels.call_args
            assert call_kwargs.kwargs["persona"] == mock_agent_persona

    def test_session_cookie_resolves_to_operator(
        self,
        client,
        mock_channel_service,
        mock_operator,
    ):
        """No token, session cookie -> operator persona."""
        mock_channel_service.list_channels.return_value = []
        with _patch_operator(mock_operator):
            resp = client.get("/api/channels")
            assert resp.status_code == 200
            mock_channel_service.list_channels.assert_called_once()
            call_kwargs = mock_channel_service.list_channels.call_args
            assert call_kwargs.kwargs["persona"] == mock_operator

    def test_service_unavailable_returns_503(self, client, app, mock_operator):
        """ChannelService not registered -> 503."""
        app.extensions["channel_service"] = None
        with _patch_operator(mock_operator):
            resp = client.get("/api/channels")
            assert resp.status_code == 503
            data = resp.get_json()
            assert data["error"]["code"] == "service_unavailable"


# ──────────────────────────────────────────────────────────────
# Create Channel Tests (Section 3.1.1)
# ──────────────────────────────────────────────────────────────


class TestCreateChannel:
    """Tests for POST /api/channels (FR1)."""

    def test_missing_fields_returns_400(self, client, mock_operator):
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels", json={})
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "missing_fields"
            assert "name" in data["error"]["message"]
            assert "channel_type" in data["error"]["message"]

    def test_invalid_channel_type_returns_400(self, client, mock_operator):
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels",
                json={"name": "Test", "channel_type": "invalid_type"},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "invalid_field"

    def test_success_returns_201(self, client, mock_operator, mock_channel_service):
        mock_channel = _make_mock_channel()
        mock_channel_service.create_channel.return_value = mock_channel

        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels",
                json={"name": "Test", "channel_type": "workshop"},
            )
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["slug"] == "workshop-test-1"
            assert data["name"] == "Test"
            assert data["status"] == "pending"
            assert data["member_count"] == 1

    def test_no_creation_capability_returns_403(
        self,
        client,
        mock_operator,
        mock_channel_service,
    ):
        mock_channel_service.create_channel.side_effect = NoCreationCapabilityError(
            "Error: Persona 'Sam' does not have channel creation capability."
        )
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels",
                json={"name": "Test", "channel_type": "workshop"},
            )
            assert resp.status_code == 403
            data = resp.get_json()
            assert data["error"]["code"] == "no_creation_capability"


# ──────────────────────────────────────────────────────────────
# List Channels Tests (Section 3.1.2)
# ──────────────────────────────────────────────────────────────


class TestListChannels:
    """Tests for GET /api/channels (FR2)."""

    def test_member_scoped_list(self, client, mock_operator, mock_channel_service):
        mock_channel_service.list_channels.return_value = []
        with _patch_operator(mock_operator):
            resp = client.get("/api/channels")
            assert resp.status_code == 200
            data = resp.get_json()
            assert isinstance(data, list)
            call_kwargs = mock_channel_service.list_channels.call_args.kwargs
            assert call_kwargs["all_visible"] is False

    def test_operator_all_true(self, client, mock_operator, mock_channel_service):
        mock_channel_service.list_channels.return_value = []
        with _patch_operator(mock_operator):
            resp = client.get("/api/channels?all=true")
            assert resp.status_code == 200
            call_kwargs = mock_channel_service.list_channels.call_args.kwargs
            assert call_kwargs["all_visible"] is True

    def test_non_operator_all_true_fallback(
        self,
        client,
        token_service,
        mock_channel_service,
        mock_agent,
        mock_agent_persona,
        mock_operator,
    ):
        """Non-operator passing ?all=true gets silent fallback to member-scoped."""
        mock_channel_service.list_channels.return_value = []

        with (
            _patch_resolve_caller(mock_agent_persona, mock_agent),
            _patch_operator(mock_operator),
        ):
            resp = client.get("/api/channels?all=true")
            assert resp.status_code == 200
            call_kwargs = mock_channel_service.list_channels.call_args.kwargs
            # Should be False -- non-operator can't use all=true
            assert call_kwargs["all_visible"] is False


# ──────────────────────────────────────────────────────────────
# Get Channel Tests (Section 3.1.3)
# ──────────────────────────────────────────────────────────────


class TestGetChannel:
    """Tests for GET /api/channels/<slug> (FR3)."""

    def test_not_found_returns_404(self, client, mock_operator, mock_channel_service):
        mock_channel_service.get_channel.side_effect = ChannelNotFoundError(
            "Error: Channel #bad-slug not found."
        )
        with _patch_operator(mock_operator):
            resp = client.get("/api/channels/bad-slug")
            assert resp.status_code == 404
            data = resp.get_json()
            assert data["error"]["code"] == "channel_not_found"

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel = _make_mock_channel(status="active", description="A test channel")
        mock_channel_service.get_channel.return_value = mock_channel

        with _patch_operator(mock_operator):
            resp = client.get("/api/channels/workshop-test-1")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["slug"] == "workshop-test-1"
            assert data["name"] == "Test"
            assert data["status"] == "active"


# ──────────────────────────────────────────────────────────────
# Update Channel Tests (Section 3.1.4)
# ──────────────────────────────────────────────────────────────


class TestUpdateChannel:
    """Tests for PATCH /api/channels/<slug> (FR4)."""

    def test_not_chair_returns_403(self, client, mock_operator, mock_channel_service):
        mock_channel_service.update_channel.side_effect = NotChairError(
            "Error: Only the channel chair can perform this operation."
        )
        with _patch_operator(mock_operator):
            resp = client.patch(
                "/api/channels/test-slug",
                json={"description": "Updated"},
            )
            assert resp.status_code == 403
            data = resp.get_json()
            assert data["error"]["code"] == "not_chair"

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel = _make_mock_channel(description="Updated description")
        mock_channel_service.update_channel.return_value = mock_channel

        with _patch_operator(mock_operator):
            resp = client.patch(
                "/api/channels/workshop-test-1",
                json={"description": "Updated description"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["description"] == "Updated description"


# ──────────────────────────────────────────────────────────────
# Complete Channel Tests (Section 3.1.5)
# ──────────────────────────────────────────────────────────────


class TestCompleteChannel:
    """Tests for POST /api/channels/<slug>/complete (FR5)."""

    def test_not_chair_returns_403(self, client, mock_operator, mock_channel_service):
        mock_channel_service.complete_channel.side_effect = NotChairError(
            "Error: Only the channel chair can perform this operation."
        )
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/test-slug/complete")
            assert resp.status_code == 403
            data = resp.get_json()
            assert data["error"]["code"] == "not_chair"

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel = _make_mock_channel(
            status="complete",
            completed_at="2026-03-03T11:00:00+00:00",
        )
        mock_channel_service.complete_channel.return_value = mock_channel

        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/workshop-test-1/complete")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "complete"


# ──────────────────────────────────────────────────────────────
# Archive Channel Tests (Section 3.1.6)
# ──────────────────────────────────────────────────────────────


class TestArchiveChannel:
    """Tests for POST /api/channels/<slug>/archive (FR5a)."""

    def test_not_complete_returns_409(
        self, client, mock_operator, mock_channel_service
    ):
        mock_channel_service.archive_channel.side_effect = ChannelClosedError(
            "Error: Channel #test-slug must be in 'complete' state to archive."
        )
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/test-slug/archive")
            assert resp.status_code == 409
            data = resp.get_json()
            assert data["error"]["code"] == "channel_not_active"

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel = _make_mock_channel(
            status="archived",
            memberships=[],
            completed_at="2026-03-03T11:00:00+00:00",
            archived_at="2026-03-03T12:00:00+00:00",
        )
        mock_channel_service.archive_channel.return_value = mock_channel

        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/workshop-test-1/archive")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "archived"


# ──────────────────────────────────────────────────────────────
# List Members Tests (Section 3.1.7)
# ──────────────────────────────────────────────────────────────


class TestListMembers:
    """Tests for GET /api/channels/<slug>/members (FR6)."""

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_member = MagicMock()
        mock_member.id = 1
        mock_member.persona.slug = "architect-robbo-2"
        mock_member.persona.name = "Robbo"
        mock_member.agent_id = 100
        mock_member.is_chair = True
        mock_member.status = "active"
        mock_member.joined_at.isoformat.return_value = "2026-03-03T10:00:00+00:00"
        mock_member.left_at = None
        mock_channel_service.list_members.return_value = [mock_member]

        with _patch_operator(mock_operator):
            resp = client.get("/api/channels/test-slug/members")
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) == 1
            assert data[0]["persona_slug"] == "architect-robbo-2"
            assert data[0]["is_chair"] is True


# ──────────────────────────────────────────────────────────────
# Add Member Tests (Section 3.1.8)
# ──────────────────────────────────────────────────────────────


class TestAddMember:
    """Tests for POST /api/channels/<slug>/members (FR7)."""

    def test_missing_persona_slug_returns_400(self, client, mock_operator):
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/test-slug/members", json={})
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "missing_fields"

    def test_success_returns_201(self, client, mock_operator, mock_channel_service):
        mock_membership = MagicMock()
        mock_membership.id = 5
        mock_membership.persona.slug = "engineer-con-3"
        mock_membership.persona.name = "Con"
        mock_membership.agent_id = 200
        mock_membership.is_chair = False
        mock_membership.status = "active"
        mock_membership.joined_at.isoformat.return_value = "2026-03-03T10:30:00+00:00"
        mock_membership.left_at = None
        mock_channel_service.add_member.return_value = mock_membership

        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/members",
                json={"persona_slug": "engineer-con-3"},
            )
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["persona_slug"] == "engineer-con-3"
            assert data["is_chair"] is False

    def test_already_member_returns_409(
        self, client, mock_operator, mock_channel_service
    ):
        mock_channel_service.add_member.side_effect = AlreadyMemberError(
            "Error: Persona 'Con' is already a member of #test-slug."
        )
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/members",
                json={"persona_slug": "engineer-con-3"},
            )
            assert resp.status_code == 409
            data = resp.get_json()
            assert data["error"]["code"] == "already_a_member"


# ──────────────────────────────────────────────────────────────
# Leave Channel Tests (Section 3.1.9)
# ──────────────────────────────────────────────────────────────


class TestLeaveChannel:
    """Tests for POST /api/channels/<slug>/leave (FR8)."""

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel_service.leave_channel.return_value = None
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/test-slug/leave")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "ok"


# ──────────────────────────────────────────────────────────────
# Mute Channel Tests (Section 3.1.10)
# ──────────────────────────────────────────────────────────────


class TestMuteChannel:
    """Tests for POST /api/channels/<slug>/mute (FR9)."""

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel_service.mute_channel.return_value = None
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/test-slug/mute")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "ok"


# ──────────────────────────────────────────────────────────────
# Unmute Channel Tests (Section 3.1.11)
# ──────────────────────────────────────────────────────────────


class TestUnmuteChannel:
    """Tests for POST /api/channels/<slug>/unmute (FR10)."""

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel_service.unmute_channel.return_value = None
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/test-slug/unmute")
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "ok"


# ──────────────────────────────────────────────────────────────
# Transfer Chair Tests (Section 3.1.12)
# ──────────────────────────────────────────────────────────────


class TestTransferChair:
    """Tests for POST /api/channels/<slug>/transfer-chair (FR11)."""

    def test_missing_persona_slug_returns_400(self, client, mock_operator):
        with _patch_operator(mock_operator):
            resp = client.post("/api/channels/test-slug/transfer-chair", json={})
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "missing_fields"

    def test_not_chair_returns_403(self, client, mock_operator, mock_channel_service):
        mock_channel_service.transfer_chair.side_effect = NotChairError(
            "Error: Only the channel chair can perform this operation."
        )
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/transfer-chair",
                json={"persona_slug": "engineer-con-3"},
            )
            assert resp.status_code == 403
            data = resp.get_json()
            assert data["error"]["code"] == "not_chair"

    def test_success_returns_200(self, client, mock_operator, mock_channel_service):
        mock_channel_service.transfer_chair.return_value = None
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/transfer-chair",
                json={"persona_slug": "engineer-con-3"},
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert data["status"] == "ok"
            assert data["message"] == "Chair transferred"


# ──────────────────────────────────────────────────────────────
# Get Messages Tests (Section 3.1.13)
# ──────────────────────────────────────────────────────────────


class TestGetMessages:
    """Tests for GET /api/channels/<slug>/messages (FR12)."""

    def test_success_with_pagination(self, client, mock_operator, mock_channel_service):
        mock_msg = MagicMock()
        mock_msg.id = 1
        mock_msg.persona.slug = "architect-robbo-2"
        mock_msg.persona.name = "Robbo"
        mock_msg.agent_id = 100
        mock_msg.content = "Hello world"
        mock_msg.message_type.value = "message"
        mock_msg.metadata_ = None
        mock_msg.attachment_path = None
        mock_msg.source_turn_id = None
        mock_msg.source_command_id = None
        mock_msg.sent_at.isoformat.return_value = "2026-03-03T10:00:00+00:00"
        mock_channel_service.get_history.return_value = [mock_msg]

        with _patch_operator(mock_operator):
            resp = client.get(
                "/api/channels/test-slug/messages?limit=20&before=2026-03-03T12:00:00Z"
            )
            assert resp.status_code == 200
            data = resp.get_json()
            assert len(data) == 1
            assert data[0]["content"] == "Hello world"
            assert data[0]["channel_slug"] == "test-slug"

            call_kwargs = mock_channel_service.get_history.call_args.kwargs
            assert call_kwargs["limit"] == 20
            assert call_kwargs["before"] == "2026-03-03T12:00:00Z"

    def test_limit_capped_at_200(self, client, mock_operator, mock_channel_service):
        """Limit values above 200 are capped."""
        mock_channel_service.get_history.return_value = []

        with _patch_operator(mock_operator):
            resp = client.get("/api/channels/test-slug/messages?limit=500")
            assert resp.status_code == 200
            call_kwargs = mock_channel_service.get_history.call_args.kwargs
            assert call_kwargs["limit"] == 200


# ──────────────────────────────────────────────────────────────
# Send Message Tests (Section 3.1.14)
# ──────────────────────────────────────────────────────────────


class TestSendMessage:
    """Tests for POST /api/channels/<slug>/messages (FR13)."""

    def test_missing_content_returns_400(self, client, mock_operator):
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"message_type": "message"},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "missing_fields"

    def test_system_type_returns_400(self, client, mock_operator):
        """The 'system' message type is not API-callable."""
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "Hello", "message_type": "system"},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "invalid_message_type"

    def test_invalid_type_returns_400(self, client, mock_operator):
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "Hello", "message_type": "bogus"},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "invalid_message_type"

    def test_success_returns_201(self, client, mock_operator, mock_channel_service):
        mock_msg = MagicMock()
        mock_msg.id = 42
        mock_msg.persona.slug = "person-sam-1"
        mock_msg.persona.name = "Sam"
        mock_msg.agent_id = None
        mock_msg.content = "Hello channel"
        mock_msg.message_type.value = "message"
        mock_msg.metadata_ = None
        mock_msg.attachment_path = None
        mock_msg.source_turn_id = None
        mock_msg.source_command_id = None
        mock_msg.sent_at.isoformat.return_value = "2026-03-03T10:23:45+00:00"
        mock_channel_service.send_message.return_value = mock_msg

        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "Hello channel"},
            )
            assert resp.status_code == 201
            data = resp.get_json()
            assert data["id"] == 42
            assert data["content"] == "Hello channel"
            assert data["channel_slug"] == "test-slug"
            assert data["message_type"] == "message"

    def test_channel_closed_returns_409(
        self, client, mock_operator, mock_channel_service
    ):
        mock_channel_service.send_message.side_effect = ChannelClosedError(
            "Error: Channel #test-slug is complete. Create a new channel to continue."
        )
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "Hello"},
            )
            assert resp.status_code == 409
            data = resp.get_json()
            assert data["error"]["code"] == "channel_not_active"

    def test_content_too_long_returns_413(self, client, app, mock_operator):
        """Content exceeding max_message_content_length returns 413."""
        app.config["APP_CONFIG"] = {
            "channels": {"max_message_content_length": 100}
        }
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "x" * 101},
            )
            assert resp.status_code == 413
            data = resp.get_json()
            assert data["error"]["code"] == "content_too_long"

    def test_content_at_max_length_succeeds(
        self, client, app, mock_operator, mock_channel_service
    ):
        """Content exactly at max length is accepted."""
        app.config["APP_CONFIG"] = {
            "channels": {"max_message_content_length": 100}
        }
        mock_msg = MagicMock()
        mock_msg.id = 50
        mock_msg.persona.slug = "person-sam-1"
        mock_msg.persona.name = "Sam"
        mock_msg.agent_id = None
        mock_msg.content = "x" * 100
        mock_msg.message_type.value = "message"
        mock_msg.metadata_ = None
        mock_msg.attachment_path = None
        mock_msg.source_turn_id = None
        mock_msg.source_command_id = None
        mock_msg.sent_at.isoformat.return_value = "2026-03-03T10:00:00+00:00"
        mock_channel_service.send_message.return_value = mock_msg

        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "x" * 100},
            )
            assert resp.status_code == 201

    def test_attachment_path_traversal_returns_400(self, client, mock_operator):
        """attachment_path containing '..' is rejected."""
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "Hello", "attachment_path": "../../../etc/passwd"},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "invalid_field"
            assert "traversal" in data["error"]["message"].lower()

    def test_attachment_path_absolute_returns_400(self, client, mock_operator):
        """attachment_path starting with '/' is rejected."""
        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "Hello", "attachment_path": "/etc/passwd"},
            )
            assert resp.status_code == 400
            data = resp.get_json()
            assert data["error"]["code"] == "invalid_field"
            assert "absolute" in data["error"]["message"].lower()

    def test_attachment_path_valid_relative_accepted(
        self, client, mock_operator, mock_channel_service
    ):
        """A valid relative attachment_path is accepted."""
        mock_msg = MagicMock()
        mock_msg.id = 51
        mock_msg.persona.slug = "person-sam-1"
        mock_msg.persona.name = "Sam"
        mock_msg.agent_id = None
        mock_msg.content = "See attached"
        mock_msg.message_type.value = "message"
        mock_msg.metadata_ = None
        mock_msg.attachment_path = "uploads/file.txt"
        mock_msg.source_turn_id = None
        mock_msg.source_command_id = None
        mock_msg.sent_at.isoformat.return_value = "2026-03-03T10:00:00+00:00"
        mock_channel_service.send_message.return_value = mock_msg

        with _patch_operator(mock_operator):
            resp = client.post(
                "/api/channels/test-slug/messages",
                json={"content": "See attached", "attachment_path": "uploads/file.txt"},
            )
            assert resp.status_code == 201


# ──────────────────────────────────────────────────────────────
# Error Envelope Tests (Section 3.3)
# ──────────────────────────────────────────────────────────────


class TestErrorEnvelope:
    """Test that all errors follow the {error: {code, message, status}} format."""

    def test_error_envelope_structure(self, client):
        """All error responses have the standard envelope."""
        with _patch_no_operator():
            resp = client.get("/api/channels")
            data = resp.get_json()

            assert "error" in data
            err = data["error"]
            assert isinstance(err["code"], str)
            assert isinstance(err["message"], str)
            assert isinstance(err["status"], int)

    def test_all_error_codes(self, client, mock_operator, mock_channel_service):
        """Test all defined error codes from Section 6.7 of PRD."""
        error_test_cases = [
            (ChannelNotFoundError("Not found"), 404, "channel_not_found"),
            (NotAMemberError("Not a member"), 403, "not_a_member"),
            (NotChairError("Not chair"), 403, "not_chair"),
            (ChannelClosedError("Closed"), 409, "channel_not_active"),
            (AlreadyMemberError("Already member"), 409, "already_a_member"),
            (NoCreationCapabilityError("No cap"), 403, "no_creation_capability"),
            (AgentChannelConflictError("Conflict"), 409, "agent_already_in_channel"),
            (ContentTooLongError("Too long"), 413, "content_too_long"),
        ]

        for exc, expected_status, expected_code in error_test_cases:
            mock_channel_service.get_channel.side_effect = exc
            with _patch_operator(mock_operator):
                resp = client.get("/api/channels/test-slug")
                assert resp.status_code == expected_status, (
                    f"Expected {expected_status} for {type(exc).__name__}, got {resp.status_code}"
                )
                data = resp.get_json()
                assert data["error"]["code"] == expected_code, (
                    f"Expected code '{expected_code}' for {type(exc).__name__}, "
                    f"got '{data['error']['code']}'"
                )
            mock_channel_service.get_channel.side_effect = None
