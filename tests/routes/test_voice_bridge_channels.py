"""Integration tests for voice bridge channel routing (e9-s8).

Tests the /api/voice/command endpoint with channel-targeted utterances,
verifying correct routing to ChannelService and error handling.
"""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.voice_bridge import voice_bridge_bp


# ── Fixtures ──────────────────────────────────────────────────────


@pytest.fixture
def app():
    """Create a test Flask app with voice bridge blueprint."""
    app = Flask(__name__)
    app.register_blueprint(voice_bridge_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "dashboard": {"active_timeout_minutes": 5},
        "tmux_bridge": {
            "subprocess_timeout": 5,
            "text_enter_delay_ms": 100,
        },
    }

    # Mock formatter
    mock_formatter = MagicMock()
    mock_formatter.format_channel_message_sent.return_value = {
        "status_line": "Message sent.", "results": [], "next_action": "none"
    }
    mock_formatter.format_channel_history.return_value = {
        "status_line": "History.", "results": [], "next_action": "none"
    }
    mock_formatter.format_channel_list.return_value = {
        "status_line": "Channels.", "results": [], "next_action": "none"
    }
    mock_formatter.format_error.return_value = {
        "status_line": "Error", "results": [], "next_action": "Fix"
    }

    app.extensions = {
        "voice_auth": None,
        "voice_formatter": mock_formatter,
        "channel_service": None,
    }
    return app


@pytest.fixture
def client(app):
    return app.test_client()


def _make_mock_channel(name="Test Channel", slug="workshop-test-1", status="active"):
    ch = SimpleNamespace()
    ch.name = name
    ch.slug = slug
    ch.status = status
    ch.channel_type = SimpleNamespace(value="workshop")
    return ch


def _make_mock_message(persona_name="Robbo", content="Hello"):
    msg = SimpleNamespace()
    msg.persona = SimpleNamespace(name=persona_name)
    msg.content = content
    return msg


# ═══════════════════════════════════════════════════════════════════
# 3.5.1 Channel send routes to ChannelService.send_message()
# ═══════════════════════════════════════════════════════════════════


class TestChannelSendRoute:
    """Test that channel send commands route to ChannelService."""

    def test_send_routes_to_channel_service(self, app, client):
        mock_channel = _make_mock_channel()
        mock_service = MagicMock()
        app.extensions["channel_service"] = mock_service

        mock_persona = MagicMock()
        mock_persona.name = "Operator"

        # Patch at the route module location (where the names are used)
        with patch(
            "src.claude_headspace.routes.voice_bridge.Channel"
        ) as MockChannel, patch(
            "src.claude_headspace.routes.voice_bridge.Persona"
        ) as MockPersona:
            MockChannel.query.filter.return_value.all.return_value = [mock_channel]
            MockPersona.get_operator.return_value = mock_persona

            resp = client.post(
                "/api/voice/command",
                json={"text": "send to test channel: hello world"},
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )

        assert resp.status_code == 200
        mock_service.send_message.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 3.5.2 Channel history route
# ═══════════════════════════════════════════════════════════════════


class TestChannelHistoryRoute:
    """Test that channel history commands retrieve messages."""

    def test_history_routes_to_get_history(self, app, client):
        mock_channel = _make_mock_channel()
        mock_service = MagicMock()
        mock_service.get_history.return_value = [
            _make_mock_message("Robbo", "Hello"),
        ]
        app.extensions["channel_service"] = mock_service

        mock_persona = MagicMock()
        mock_persona.name = "Operator"

        with patch(
            "src.claude_headspace.routes.voice_bridge.Channel"
        ) as MockChannel, patch(
            "src.claude_headspace.routes.voice_bridge.Persona"
        ) as MockPersona:
            MockChannel.query.filter.return_value.all.return_value = [mock_channel]
            MockPersona.get_operator.return_value = mock_persona

            resp = client.post(
                "/api/voice/command",
                json={"text": "what's happening in the test channel?"},
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )

        assert resp.status_code == 200
        mock_service.get_history.assert_called_once()


# ═══════════════════════════════════════════════════════════════════
# 3.5.3 Returns 503 when channel_service not registered
# ═══════════════════════════════════════════════════════════════════


class TestChannelServiceUnavailable:
    """Test graceful degradation when ChannelService is not available."""

    def test_returns_503_no_channel_service(self, app, client):
        app.extensions["channel_service"] = None
        resp = client.post(
            "/api/voice/command",
            json={"text": "send to workshop: hello"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        assert resp.status_code == 503
        data = resp.get_json()
        assert "not available" in data.get("error", "").lower() or \
               "not available" in data.get("voice", {}).get("status_line", "").lower()


# ═══════════════════════════════════════════════════════════════════
# 3.5.4 Existing agent commands unaffected
# ═══════════════════════════════════════════════════════════════════


class TestExistingAgentPath:
    """Test that non-channel utterances still route to agents."""

    def test_plain_text_does_not_trigger_channel(self, app, client):
        """A plain text command without channel patterns falls through to agent path."""
        # Mock db.session.get to return None (agent not found)
        with patch("src.claude_headspace.routes.voice_bridge.db") as mock_db:
            mock_db.session.get.return_value = None
            resp = client.post(
                "/api/voice/command",
                json={"text": "run the test suite", "agent_id": 999},
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )
        # Should get 404 (agent not found), NOT a channel routing response
        assert resp.status_code == 404

    def test_status_check_not_channel(self, app, client):
        """'what are you working on' is not a channel command."""
        with patch("src.claude_headspace.routes.voice_bridge.db") as mock_db:
            mock_db.session.get.return_value = None
            resp = client.post(
                "/api/voice/command",
                json={"text": "what are you working on?", "agent_id": 999},
                environ_base={"REMOTE_ADDR": "127.0.0.1"},
            )
        # Should try agent resolution, not channel routing
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# 3.5.5 Pipeline ordering
# ═══════════════════════════════════════════════════════════════════


class TestPipelineOrdering:
    """Test that detection pipeline follows correct order."""

    def test_channel_detected_before_agent_resolution(self, app, client):
        """Channel commands should work without an agent_id."""
        app.extensions["channel_service"] = None  # Will get 503, not 400
        resp = client.post(
            "/api/voice/command",
            json={"text": "list channels"},  # No agent_id
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        # Should hit channel detection (503 because channel_service is None)
        # NOT "No agent specified" (400)
        assert resp.status_code == 503

    def test_list_channels_returns_503_not_400(self, app, client):
        """'list channels' routes to channel handler, not agent path."""
        app.extensions["channel_service"] = None
        resp = client.post(
            "/api/voice/command",
            json={"text": "show channels"},
            environ_base={"REMOTE_ADDR": "127.0.0.1"},
        )
        # Channel detection fires -> 503 (no channel service)
        # NOT 400 (no agent specified)
        assert resp.status_code == 503
