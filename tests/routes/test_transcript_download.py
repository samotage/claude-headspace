"""Tests for transcript download API endpoints."""

from unittest.mock import MagicMock

import pytest
from flask import Flask

from src.claude_headspace.routes.transcript_download import transcript_download_bp


@pytest.fixture
def app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.register_blueprint(transcript_download_bp)

    mock_service = MagicMock()
    app.extensions["transcript_export_service"] = mock_service

    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_service(app):
    return app.extensions["transcript_export_service"]


# ---------------------------------------------------------------------------
# Agent transcript endpoint
# ---------------------------------------------------------------------------


class TestAgentTranscriptEndpoint:
    def test_success(self, client, mock_service):
        mock_service.assemble_agent_transcript.return_value = (
            "chat-dev-con-1-42-20260305-100000.md",
            "---\ntype: chat\n---\n\n### Operator\nHello\n",
        )

        response = client.get("/api/agents/42/transcript")

        assert response.status_code == 200
        assert response.content_type.startswith("text/markdown")
        assert b"type: chat" in response.data
        assert b"### Operator" in response.data

        # Check Content-Disposition header
        cd = response.headers.get("Content-Disposition")
        assert cd is not None
        assert "attachment" in cd
        assert "chat-dev-con-1-42-20260305-100000.md" in cd

        mock_service.assemble_agent_transcript.assert_called_once_with(42)

    def test_agent_not_found(self, client, mock_service):
        mock_service.assemble_agent_transcript.side_effect = ValueError(
            "Agent 999 not found"
        )

        response = client.get("/api/agents/999/transcript")

        assert response.status_code == 404
        data = response.get_json()
        assert "not found" in data["error"].lower()

    def test_empty_session(self, client, mock_service):
        """An agent with no turns should still return a valid transcript."""
        mock_service.assemble_agent_transcript.return_value = (
            "chat-unknown-1-20260305-100000.md",
            "---\ntype: chat\nmessage_count: 0\n---\n\n",
        )

        response = client.get("/api/agents/1/transcript")

        assert response.status_code == 200
        assert b"message_count: 0" in response.data

    def test_server_error(self, client, mock_service):
        mock_service.assemble_agent_transcript.side_effect = RuntimeError(
            "Database connection lost"
        )

        response = client.get("/api/agents/1/transcript")

        assert response.status_code == 500
        data = response.get_json()
        assert "failed" in data["error"].lower()

    def test_no_service(self, app):
        app.extensions.pop("transcript_export_service")
        client = app.test_client()

        response = client.get("/api/agents/1/transcript")

        assert response.status_code == 503
        data = response.get_json()
        assert "not available" in data["error"].lower()


# ---------------------------------------------------------------------------
# Channel transcript endpoint
# ---------------------------------------------------------------------------


class TestChannelTranscriptEndpoint:
    def test_success(self, client, mock_service):
        mock_service.assemble_channel_transcript.return_value = (
            "channel-dev-chair-1-5-20260305-100000.md",
            "---\ntype: channel\n---\n\n### Alice\nHello\n",
        )

        response = client.get("/api/channels/workshop-test-5/transcript")

        assert response.status_code == 200
        assert response.content_type.startswith("text/markdown")
        assert b"type: channel" in response.data
        assert b"### Alice" in response.data

        # Check Content-Disposition header
        cd = response.headers.get("Content-Disposition")
        assert cd is not None
        assert "attachment" in cd
        assert "channel-dev-chair-1-5-20260305-100000.md" in cd

        mock_service.assemble_channel_transcript.assert_called_once_with(
            "workshop-test-5"
        )

    def test_channel_not_found(self, client, mock_service):
        mock_service.assemble_channel_transcript.side_effect = ValueError(
            "Channel 'nonexistent' not found"
        )

        response = client.get("/api/channels/nonexistent/transcript")

        assert response.status_code == 404
        data = response.get_json()
        assert "not found" in data["error"].lower()

    def test_empty_channel(self, client, mock_service):
        """A channel with no messages should still return a valid transcript."""
        mock_service.assemble_channel_transcript.return_value = (
            "channel-unknown-5-20260305-100000.md",
            "---\ntype: channel\nmessage_count: 0\n---\n\n",
        )

        response = client.get("/api/channels/workshop-empty-5/transcript")

        assert response.status_code == 200
        assert b"message_count: 0" in response.data

    def test_server_error(self, client, mock_service):
        mock_service.assemble_channel_transcript.side_effect = RuntimeError(
            "Database connection lost"
        )

        response = client.get("/api/channels/workshop-test-5/transcript")

        assert response.status_code == 500
        data = response.get_json()
        assert "failed" in data["error"].lower()

    def test_no_service(self, app):
        app.extensions.pop("transcript_export_service")
        client = app.test_client()

        response = client.get("/api/channels/workshop-test-5/transcript")

        assert response.status_code == 503
        data = response.get_json()
        assert "not available" in data["error"].lower()
