"""Tests for E9-S11 channel API route extensions.

Covers:
- POST /api/channels with persona_slugs + project_id (S11 path)
- POST /api/channels with name (V0 legacy path — backward compat)
- POST /api/channels missing project_id → 400
- POST /api/channels/<slug>/members with project_id → 201
- POST /api/channels/<slug>/members without project_id → 201 (uses channel project)
"""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from claude_headspace.routes.channels_api import channels_api_bp
from claude_headspace.services.channel_service import (
    PersonaNotFoundError,
    ProjectNotFoundError,
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
    operator = MagicMock()
    operator.id = 1
    operator.slug = "person-sam-1"
    operator.name = "Sam"
    operator.can_create_channel = True
    return operator


@pytest.fixture
def app(token_service, mock_channel_service):
    """Test Flask app with channels API blueprint."""
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


def _make_mock_channel(slug="workshop-s11-1", name="Robbo + Con", status="pending"):
    ch = MagicMock()
    ch.id = 1
    ch.slug = slug
    ch.name = name
    ch.channel_type.value = "workshop"
    ch.status = status
    ch.description = None
    ch.intent_override = None
    ch.organisation_id = None
    ch.project_id = 1
    ch.created_at.isoformat.return_value = "2026-03-06T00:00:00+00:00"
    ch.completed_at = None
    ch.archived_at = None
    chair = MagicMock()
    chair.is_chair = True
    chair.status = "active"
    chair.persona.slug = "person-sam-1"
    ch.memberships = [chair]
    return ch


def _make_mock_membership():
    m = MagicMock()
    m.id = 10
    m.channel_id = 1
    m.persona_id = 2
    m.agent_id = None
    m.is_chair = False
    m.status = "active"
    m.joined_at.isoformat.return_value = "2026-03-06T00:00:00+00:00"
    m.left_at = None  # Must be None so isoformat() is not called on it
    m.persona.slug = "robbo"
    m.persona.name = "Robbo"
    return m


def _patch_operator(mock_operator):
    return patch(
        "claude_headspace.models.persona.Persona.get_operator",
        return_value=mock_operator,
    )


def _patch_resolve_caller(persona, agent=None):
    return patch(
        "claude_headspace.routes.channels_api._resolve_caller",
        return_value=(persona, agent),
    )


# ──────────────────────────────────────────────────────────────
# POST /api/channels — S11 path (persona_slugs + project_id)
# ──────────────────────────────────────────────────────────────


class TestCreateChannelS11Path:
    def test_s11_path_returns_201_with_pending_channel(
        self, client, mock_operator, mock_channel_service
    ):
        """POST with persona_slugs + project_id → 201, status=pending."""
        mock_channel = _make_mock_channel()
        mock_channel_service.create_channel_from_personas.return_value = mock_channel

        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={
                    "project_id": 1,
                    "channel_type": "workshop",
                    "persona_slugs": ["robbo", "con"],
                },
                content_type="application/json",
            )

        assert resp.status_code == 201
        data = resp.get_json()
        assert data["status"] == "pending"
        mock_channel_service.create_channel_from_personas.assert_called_once()
        call_kwargs = mock_channel_service.create_channel_from_personas.call_args.kwargs
        assert call_kwargs["project_id"] == 1
        assert call_kwargs["persona_slugs"] == ["robbo", "con"]
        assert call_kwargs["channel_type"] == "workshop"

    def test_s11_path_missing_project_id_returns_400(
        self, client, mock_operator, mock_channel_service
    ):
        """persona_slugs without project_id → 400."""
        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={
                    "channel_type": "workshop",
                    "persona_slugs": ["robbo"],
                },
                content_type="application/json",
            )

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "missing_fields"

    def test_s11_path_empty_persona_slugs_returns_400(
        self, client, mock_operator, mock_channel_service
    ):
        """Empty persona_slugs list → 400."""
        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={
                    "project_id": 1,
                    "channel_type": "workshop",
                    "persona_slugs": [],
                },
                content_type="application/json",
            )

        assert resp.status_code == 400

    def test_s11_path_invalid_project_id_type_returns_400(
        self, client, mock_operator, mock_channel_service
    ):
        """String project_id → 400."""
        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={
                    "project_id": "not-an-int",
                    "channel_type": "workshop",
                    "persona_slugs": ["robbo"],
                },
                content_type="application/json",
            )

        assert resp.status_code == 400

    def test_s11_path_project_not_found_returns_404(
        self, client, mock_operator, mock_channel_service
    ):
        """ProjectNotFoundError from service → 404."""
        mock_channel_service.create_channel_from_personas.side_effect = (
            ProjectNotFoundError("Error: Project #999 not found.")
        )

        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={
                    "project_id": 999,
                    "channel_type": "workshop",
                    "persona_slugs": ["robbo"],
                },
                content_type="application/json",
            )

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "project_not_found"

    def test_s11_path_persona_not_found_returns_404(
        self, client, mock_operator, mock_channel_service
    ):
        """PersonaNotFoundError from service → 404."""
        mock_channel_service.create_channel_from_personas.side_effect = (
            PersonaNotFoundError("Error: Persona 'nobody' not found.")
        )

        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={
                    "project_id": 1,
                    "channel_type": "workshop",
                    "persona_slugs": ["nobody"],
                },
                content_type="application/json",
            )

        assert resp.status_code == 404
        data = resp.get_json()
        assert data["error"]["code"] == "persona_not_found"


# ──────────────────────────────────────────────────────────────
# POST /api/channels — V0 legacy path (backward compat)
# ──────────────────────────────────────────────────────────────


class TestCreateChannelV0Compat:
    def test_v0_name_path_still_works(
        self, client, mock_operator, mock_channel_service
    ):
        """POST with name (no persona_slugs) → 201, uses V0 create_channel."""
        mock_channel = _make_mock_channel(name="My Channel", status="pending")
        mock_channel_service.create_channel.return_value = mock_channel

        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={"name": "My Channel", "channel_type": "workshop"},
                content_type="application/json",
            )

        assert resp.status_code == 201
        mock_channel_service.create_channel.assert_called_once()
        # Ensure S11 method was NOT called
        mock_channel_service.create_channel_from_personas.assert_not_called()

    def test_v0_missing_name_returns_400(
        self, client, mock_operator, mock_channel_service
    ):
        """V0 path: name required, missing → 400."""
        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels",
                json={"channel_type": "workshop"},
                content_type="application/json",
            )

        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# POST /api/channels/<slug>/members — project_id support
# ──────────────────────────────────────────────────────────────


class TestAddMemberWithProjectId:
    def test_add_member_with_project_id_returns_201(
        self, client, mock_operator, mock_channel_service
    ):
        """POST members with project_id → 201, project_id passed to service."""
        mock_membership = _make_mock_membership()
        mock_channel_service.add_member.return_value = mock_membership

        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels/workshop-s11-1/members",
                json={"persona_slug": "robbo", "project_id": 2},
                content_type="application/json",
            )

        assert resp.status_code == 201
        call_kwargs = mock_channel_service.add_member.call_args.kwargs
        assert call_kwargs["project_id"] == 2
        assert call_kwargs["persona_slug"] == "robbo"

    def test_add_member_without_project_id_returns_201(
        self, client, mock_operator, mock_channel_service
    ):
        """POST members without project_id → 201, project_id=None passed to service."""
        mock_membership = _make_mock_membership()
        mock_channel_service.add_member.return_value = mock_membership

        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels/workshop-s11-1/members",
                json={"persona_slug": "robbo"},
                content_type="application/json",
            )

        assert resp.status_code == 201
        call_kwargs = mock_channel_service.add_member.call_args.kwargs
        assert call_kwargs.get("project_id") is None

    def test_add_member_invalid_project_id_type_returns_400(
        self, client, mock_operator, mock_channel_service
    ):
        """String project_id → 400."""
        with _patch_operator(mock_operator), _patch_resolve_caller(mock_operator):
            resp = client.post(
                "/api/channels/workshop-s11-1/members",
                json={"persona_slug": "robbo", "project_id": "bad"},
                content_type="application/json",
            )

        assert resp.status_code == 400
        data = resp.get_json()
        assert data["error"]["code"] == "invalid_field"
