"""Tests for voice bridge file upload and serving routes."""

import io
import os
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.models.task import TaskState
from src.claude_headspace.models.turn import TurnActor, TurnIntent
from src.claude_headspace.routes.voice_bridge import voice_bridge_bp
from src.claude_headspace.services.file_upload import FileUploadService
from src.claude_headspace.services.tmux_bridge import SendResult


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────


@pytest.fixture
def upload_dir(tmp_path):
    d = tmp_path / "uploads"
    d.mkdir()
    return d


@pytest.fixture
def file_upload_service(upload_dir, tmp_path):
    config = {
        "file_upload": {
            "upload_dir": "uploads",
            "max_file_size_mb": 10,
            "max_total_storage_mb": 500,
            "retention_days": 7,
            "allowed_image_types": ["png", "jpg", "jpeg", "gif", "webp"],
            "allowed_document_types": ["pdf"],
            "allowed_text_types": ["txt", "md", "py"],
        }
    }
    svc = FileUploadService(config=config, app_root=str(tmp_path))
    svc.ensure_upload_dir()
    return svc


@pytest.fixture
def app(file_upload_service):
    app = Flask(__name__)
    app.register_blueprint(voice_bridge_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "tmux_bridge": {
            "subprocess_timeout": 5,
            "text_enter_delay_ms": 100,
        },
    }
    app.extensions = {
        "voice_auth": None,
        "voice_formatter": None,
        "file_upload": file_upload_service,
    }
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_db():
    with patch("src.claude_headspace.routes.voice_bridge.db") as mock:
        mock.session = MagicMock()
        yield mock


@pytest.fixture
def mock_project():
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    return project


@pytest.fixture
def mock_agent_awaiting(mock_project):
    agent = MagicMock()
    agent.id = 1
    agent.name = "agent-1"
    agent.project = mock_project
    agent.tmux_pane_id = "%5"
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None

    task = MagicMock()
    task.id = 10
    task.state = TaskState.AWAITING_INPUT
    task.turns = []
    agent.get_current_task.return_value = task
    return agent


@pytest.fixture
def mock_agent_idle(mock_project):
    agent = MagicMock()
    agent.id = 2
    agent.name = "agent-2"
    agent.project = mock_project
    agent.tmux_pane_id = "%6"
    agent.last_seen_at = datetime.now(timezone.utc)
    agent.ended_at = None
    agent.get_current_task.return_value = None
    return agent


@pytest.fixture
def mock_agent_no_pane(mock_project):
    agent = MagicMock()
    agent.id = 3
    agent.name = "agent-3"
    agent.project = mock_project
    agent.tmux_pane_id = None
    agent.ended_at = None
    return agent


# ──────────────────────────────────────────────────────────────
# Upload endpoint tests
# ──────────────────────────────────────────────────────────────


class TestUploadEndpoint:
    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_upload_valid_image(self, mock_tmux, mock_broadcast, client, mock_db, mock_agent_awaiting):
        mock_db.session.get.return_value = mock_agent_awaiting
        mock_tmux.send_text.return_value = SendResult(success=True)

        with patch("src.claude_headspace.services.hook_receiver._mark_question_answered"):
            with patch("src.claude_headspace.services.state_machine.validate_transition") as mock_vt:
                mock_vt.return_value = MagicMock(valid=True, to_state=TaskState.PROCESSING)
                data = {"file": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "test.png")}
                resp = client.post("/api/voice/agents/1/upload", data=data, content_type="multipart/form-data")

        assert resp.status_code == 200
        json_data = resp.get_json()
        assert "file_metadata" in json_data
        assert json_data["file_metadata"]["original_filename"] == "test.png"
        assert json_data["file_metadata"]["file_type"] == "image"

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_upload_valid_text_file(self, mock_tmux, mock_broadcast, client, mock_db, mock_agent_idle):
        mock_db.session.get.return_value = mock_agent_idle
        mock_tmux.send_text.return_value = SendResult(success=True)

        data = {"file": (io.BytesIO(b"print('hello')"), "code.py")}
        resp = client.post("/api/voice/agents/2/upload", data=data, content_type="multipart/form-data")

        assert resp.status_code == 200
        json_data = resp.get_json()
        assert json_data["file_metadata"]["file_type"] == "text"

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_upload_with_text(self, mock_tmux, mock_broadcast, client, mock_db, mock_agent_idle):
        mock_db.session.get.return_value = mock_agent_idle
        mock_tmux.send_text.return_value = SendResult(success=True)

        data = {
            "file": (io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100), "screenshot.png"),
            "text": "Check this screenshot",
        }
        resp = client.post("/api/voice/agents/2/upload", data=data, content_type="multipart/form-data")

        assert resp.status_code == 200
        # Verify tmux was called with both text and file path
        call_args = mock_tmux.send_text.call_args
        sent_text = call_args.kwargs.get("text", call_args[1].get("text", ""))
        assert "Check this screenshot" in sent_text
        assert "Please look at this file:" in sent_text

    def test_upload_invalid_file_type(self, client, mock_db, mock_agent_awaiting):
        mock_db.session.get.return_value = mock_agent_awaiting

        data = {"file": (io.BytesIO(b"malware"), "virus.exe")}
        resp = client.post("/api/voice/agents/1/upload", data=data, content_type="multipart/form-data")

        assert resp.status_code == 400
        json_data = resp.get_json()
        assert "not allowed" in json_data.get("error", "")

    def test_upload_no_file(self, client, mock_db, mock_agent_awaiting):
        mock_db.session.get.return_value = mock_agent_awaiting

        resp = client.post("/api/voice/agents/1/upload", data={}, content_type="multipart/form-data")

        assert resp.status_code == 400

    def test_upload_agent_not_found(self, client, mock_db):
        mock_db.session.get.return_value = None

        data = {"file": (io.BytesIO(b"test"), "test.txt")}
        resp = client.post("/api/voice/agents/999/upload", data=data, content_type="multipart/form-data")

        assert resp.status_code == 404

    def test_upload_agent_no_tmux_pane(self, client, mock_db, mock_agent_no_pane):
        mock_db.session.get.return_value = mock_agent_no_pane

        data = {"file": (io.BytesIO(b"test"), "test.txt")}
        resp = client.post("/api/voice/agents/3/upload", data=data, content_type="multipart/form-data")

        assert resp.status_code == 503


# ──────────────────────────────────────────────────────────────
# File serving endpoint tests
# ──────────────────────────────────────────────────────────────


class TestServeUpload:
    def test_serve_valid_file(self, client, file_upload_service):
        # Write a test file to the upload dir
        test_file = file_upload_service.upload_dir / "abc123.txt"
        test_file.write_bytes(b"hello world")

        resp = client.get("/api/voice/uploads/abc123.txt")
        assert resp.status_code == 200
        assert resp.data == b"hello world"

    def test_serve_path_traversal_rejected(self, client):
        # Flask normalizes ../../../ in the URL path before routing,
        # so test with a filename that contains .. as part of the name
        resp = client.get("/api/voice/uploads/..secret.txt")
        assert resp.status_code == 400

    def test_serve_null_byte_rejected(self, client):
        resp = client.get("/api/voice/uploads/test%00.txt")
        assert resp.status_code == 400

    def test_serve_nonexistent_file(self, client):
        resp = client.get("/api/voice/uploads/nonexistent.txt")
        assert resp.status_code == 404


# ──────────────────────────────────────────────────────────────
# Transcript includes file_metadata
# ──────────────────────────────────────────────────────────────


class TestTranscriptFileMetadata:
    def test_transcript_includes_file_metadata(self, client, mock_db, mock_agent_awaiting):
        mock_db.session.get.return_value = mock_agent_awaiting

        # Mock turn with file_metadata
        mock_turn = MagicMock()
        mock_turn.id = 50
        mock_turn.actor = TurnActor.USER
        mock_turn.intent = TurnIntent.ANSWER
        mock_turn.text = "[File: screenshot.png]"
        mock_turn.summary = None
        mock_turn.timestamp = datetime.now(timezone.utc)
        mock_turn.tool_input = None
        mock_turn.question_text = None
        mock_turn.question_options = None
        mock_turn.question_source_type = None
        mock_turn.answered_by_turn_id = None
        mock_turn.file_metadata = {
            "original_filename": "screenshot.png",
            "file_type": "image",
            "file_size": 12345,
        }

        mock_task = MagicMock()
        mock_task.id = 10
        mock_task.instruction = "Fix bug"
        mock_task.state = TaskState.AWAITING_INPUT

        # Mock query chain
        mock_query = MagicMock()
        mock_db.session.query.return_value = mock_query
        mock_query.join.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [(mock_turn, mock_task)]

        mock_agent_awaiting.session_uuid = "abcd1234-5678"

        resp = client.get("/api/voice/agents/1/transcript")
        assert resp.status_code == 200
        data = resp.get_json()
        turns = data["turns"]
        assert len(turns) == 1
        assert turns[0]["file_metadata"]["original_filename"] == "screenshot.png"


# ──────────────────────────────────────────────────────────────
# Existing text-only command still works
# ──────────────────────────────────────────────────────────────


class TestExistingCommandUnchanged:
    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_text_only_command(self, mock_tmux, mock_broadcast, client, mock_db, mock_agent_awaiting):
        mock_db.session.get.return_value = mock_agent_awaiting
        mock_tmux.send_text.return_value = SendResult(success=True)

        with patch("src.claude_headspace.services.hook_receiver._mark_question_answered"):
            with patch("src.claude_headspace.services.state_machine.validate_transition") as mock_vt:
                mock_vt.return_value = MagicMock(valid=True, to_state=TaskState.PROCESSING)
                resp = client.post(
                    "/api/voice/command",
                    json={"text": "Use option A", "agent_id": 1},
                )

        assert resp.status_code == 200
        # Text was sent without file path
        call_args = mock_tmux.send_text.call_args
        sent_text = call_args.kwargs.get("text", call_args[1].get("text", ""))
        assert sent_text == "Use option A"
        assert "file" not in sent_text.lower()

    @patch("src.claude_headspace.routes.voice_bridge.broadcast_card_refresh")
    @patch("src.claude_headspace.routes.voice_bridge.tmux_bridge")
    def test_command_with_file_path(self, mock_tmux, mock_broadcast, client, mock_db, mock_agent_awaiting):
        mock_db.session.get.return_value = mock_agent_awaiting
        mock_tmux.send_text.return_value = SendResult(success=True)

        with patch("src.claude_headspace.services.hook_receiver._mark_question_answered"):
            with patch("src.claude_headspace.services.state_machine.validate_transition") as mock_vt:
                mock_vt.return_value = MagicMock(valid=True, to_state=TaskState.PROCESSING)
                resp = client.post(
                    "/api/voice/command",
                    json={"text": "Look at this", "agent_id": 1, "file_path": "/tmp/test.png"},
                )

        assert resp.status_code == 200
        call_args = mock_tmux.send_text.call_args
        sent_text = call_args.kwargs.get("text", call_args[1].get("text", ""))
        assert "Look at this" in sent_text
        assert "/tmp/test.png" in sent_text
