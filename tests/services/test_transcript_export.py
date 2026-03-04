"""Tests for TranscriptExportService — agent and channel transcript assembly."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

import claude_headspace.services.transcript_export as transcript_export_mod
from claude_headspace.models.turn import TurnActor
from claude_headspace.services.transcript_export import (
    TranscriptExportService,
    _build_frontmatter,
    _format_timestamp,
    _generate_filename,
)

# ---------------------------------------------------------------------------
# Helper factories
# ---------------------------------------------------------------------------


def _make_persona(name="TestAgent", slug="dev-testagent-1"):
    p = MagicMock()
    p.name = name
    p.slug = slug
    return p


def _make_project(name="test-project"):
    p = MagicMock()
    p.name = name
    return p


def _make_agent(agent_id=1, persona=None, project=None, session_uuid=None):
    a = MagicMock()
    a.id = agent_id
    a.session_uuid = session_uuid or uuid4()
    a.persona = persona
    a.project = project or _make_project()
    return a


def _make_turn(actor="user", text="Hello", timestamp=None, is_internal=False):
    t = MagicMock()
    t.actor = TurnActor.USER if actor == "user" else TurnActor.AGENT
    t.text = text
    t.timestamp = timestamp or datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc)
    t.is_internal = is_internal
    return t


def _make_channel(channel_id=1, slug="workshop-test-1", project=None):
    c = MagicMock()
    c.id = channel_id
    c.slug = slug
    c.project = project or _make_project()
    return c


def _make_message(persona=None, content="Test message", sent_at=None):
    m = MagicMock()
    m.persona = persona
    m.content = content
    m.sent_at = sent_at or datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc)
    return m


def _make_membership(persona=None, is_chair=False):
    m = MagicMock()
    m.persona = persona
    m.is_chair = is_chair
    return m


# ---------------------------------------------------------------------------
# Unit tests — pure functions
# ---------------------------------------------------------------------------


class TestBuildFrontmatter:
    def test_basic_frontmatter(self):
        result = _build_frontmatter(
            type_="chat",
            identifier="abc-123",
            project="my-project",
            persona="dev-con-1",
            agent_id=42,
            participants=[{"name": "Operator", "role": "operator"}],
            start_time="2026-03-05T10:00:00+00:00",
            end_time="2026-03-05T11:00:00+00:00",
            message_count=5,
            exported_at="2026-03-05T12:00:00+00:00",
        )
        assert result.startswith("---\n")
        assert result.endswith("---\n")
        assert "type: chat" in result
        assert "identifier: abc-123" in result
        assert "project: my-project" in result
        assert "persona: dev-con-1" in result
        assert "agent_id: 42" in result
        assert "message_count: 5" in result
        assert "  - name: Operator" in result
        assert "    role: operator" in result

    def test_channel_frontmatter_no_agent_id(self):
        result = _build_frontmatter(
            type_="channel",
            identifier="workshop-test-1",
            project="my-project",
            persona="dev-chair-1",
            agent_id=None,
            participants=[],
            start_time=None,
            end_time=None,
            message_count=0,
            exported_at="2026-03-05T12:00:00+00:00",
        )
        assert "agent_id" not in result
        assert "start_time: null" in result
        assert "end_time: null" in result

    def test_multiple_participants(self):
        result = _build_frontmatter(
            type_="channel",
            identifier="test",
            project="proj",
            persona="chair",
            agent_id=None,
            participants=[
                {"name": "Alice", "role": "chair"},
                {"name": "Bob", "role": "member"},
                {"name": "Carol", "role": "member"},
            ],
            start_time="2026-03-05T10:00:00+00:00",
            end_time="2026-03-05T11:00:00+00:00",
            message_count=10,
            exported_at="2026-03-05T12:00:00+00:00",
        )
        assert "  - name: Alice" in result
        assert "  - name: Bob" in result
        assert "  - name: Carol" in result


class TestFormatTimestamp:
    def test_aware_datetime(self):
        dt = datetime(2026, 3, 5, 10, 30, 0, tzinfo=timezone.utc)
        result = _format_timestamp(dt)
        assert "2026-03-05" in result
        assert "10:30:00" in result

    def test_naive_datetime(self):
        dt = datetime(2026, 3, 5, 10, 30, 0)
        result = _format_timestamp(dt)
        assert "2026-03-05 10:30:00" == result


class TestGenerateFilename:
    def test_chat_filename(self):
        dt = datetime(2026, 3, 5, 10, 30, 0, tzinfo=timezone.utc)
        result = _generate_filename("chat", "dev-con-1", 42, dt)
        assert result == "chat-dev-con-1-42-20260305-103000.md"

    def test_channel_filename(self):
        dt = datetime(2026, 3, 5, 14, 0, 0, tzinfo=timezone.utc)
        result = _generate_filename("channel", "dev-chair-1", 7, dt)
        assert result == "channel-dev-chair-1-7-20260305-140000.md"


# ---------------------------------------------------------------------------
# Service tests — agent transcript
# ---------------------------------------------------------------------------


class TestAssembleAgentTranscript:
    def _make_service(self):
        """Create a service instance without app dependency."""
        service = TranscriptExportService.__new__(TranscriptExportService)
        service._app = None
        service._transcripts_dir = None
        return service

    @patch.object(TranscriptExportService, "_persist")
    @patch.object(transcript_export_mod, "db")
    def test_basic_agent_transcript(self, mock_db, mock_persist):
        """Test agent transcript with multiple turns."""
        persona = _make_persona("Con", "dev-con-1")
        project = _make_project("test-project")
        agent = _make_agent(agent_id=1, persona=persona, project=project)

        turns = [
            _make_turn(
                "user",
                "Build a feature",
                datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc),
            ),
            _make_turn(
                "agent",
                "I will implement that.",
                datetime(2026, 3, 5, 10, 0, 30, tzinfo=timezone.utc),
            ),
            _make_turn(
                "user", "Thanks", datetime(2026, 3, 5, 10, 1, 0, tzinfo=timezone.utc)
            ),
        ]

        mock_db.session.get.return_value = agent
        mock_db.session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = turns

        service = self._make_service()
        filename, content = service.assemble_agent_transcript(1)

        assert filename.startswith("chat-dev-con-1-1-")
        assert filename.endswith(".md")
        assert "type: chat" in content
        assert "persona: dev-con-1" in content
        assert "project: test-project" in content
        assert "message_count: 3" in content
        assert "### Operator" in content
        assert "### Con" in content
        assert "Build a feature" in content
        assert "I will implement that." in content

    @patch.object(TranscriptExportService, "_persist")
    @patch.object(transcript_export_mod, "db")
    def test_agent_not_found(self, mock_db, mock_persist):
        mock_db.session.get.return_value = None

        service = self._make_service()
        with pytest.raises(ValueError, match="Agent 999 not found"):
            service.assemble_agent_transcript(999)

    @patch.object(TranscriptExportService, "_persist")
    @patch.object(transcript_export_mod, "db")
    def test_empty_session(self, mock_db, mock_persist):
        """Test agent with no turns."""
        agent = _make_agent(agent_id=1)

        mock_db.session.get.return_value = agent
        mock_db.session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = []

        service = self._make_service()
        filename, content = service.assemble_agent_transcript(1)

        assert "message_count: 0" in content
        assert "start_time: null" in content
        assert "end_time: null" in content

    @patch.object(TranscriptExportService, "_persist")
    @patch.object(transcript_export_mod, "db")
    def test_persona_fallback(self, mock_db, mock_persist):
        """Agents without a persona should use 'unknown' slug and 'Agent' display name."""
        agent = _make_agent(agent_id=1, persona=None)

        turns = [
            _make_turn(
                "agent", "Hello", datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc)
            ),
        ]

        mock_db.session.get.return_value = agent
        mock_db.session.query.return_value.join.return_value.filter.return_value.order_by.return_value.all.return_value = turns

        service = self._make_service()
        filename, content = service.assemble_agent_transcript(1)

        assert "persona: unknown" in content
        assert "### Agent" in content
        assert filename.startswith("chat-unknown-1-")


# ---------------------------------------------------------------------------
# Service tests — channel transcript
# ---------------------------------------------------------------------------


class TestAssembleChannelTranscript:
    def _make_service(self):
        """Create a service instance without app dependency."""
        service = TranscriptExportService.__new__(TranscriptExportService)
        service._app = None
        service._transcripts_dir = None
        return service

    @patch.object(TranscriptExportService, "_persist")
    @patch.object(transcript_export_mod, "db")
    def test_basic_channel_transcript(self, mock_db, mock_persist):
        """Test channel transcript with multiple participants."""
        persona_alice = _make_persona("Alice", "dev-alice-1")
        persona_bob = _make_persona("Bob", "dev-bob-2")
        project = _make_project("test-project")
        channel = _make_channel(channel_id=5, slug="workshop-test-5", project=project)

        messages = [
            _make_message(
                persona_alice,
                "Let's discuss",
                datetime(2026, 3, 5, 10, 0, 0, tzinfo=timezone.utc),
            ),
            _make_message(
                persona_bob,
                "Sure thing",
                datetime(2026, 3, 5, 10, 1, 0, tzinfo=timezone.utc),
            ),
            _make_message(
                persona_alice,
                "Great",
                datetime(2026, 3, 5, 10, 2, 0, tzinfo=timezone.utc),
            ),
        ]

        chair_membership = _make_membership(persona_alice, is_chair=True)
        memberships = [
            chair_membership,
            _make_membership(persona_bob, is_chair=False),
        ]

        # Channel lookup
        mock_db.session.query.return_value.filter_by.return_value.first.return_value = (
            channel
        )
        # Messages query
        query_chain = MagicMock()
        query_chain.filter.return_value.order_by.return_value.all.return_value = (
            messages
        )
        # Chair membership query
        chair_chain = MagicMock()
        chair_chain.filter.return_value.first.return_value = chair_membership
        # All memberships query
        members_chain = MagicMock()
        members_chain.filter.return_value.all.return_value = memberships

        mock_db.session.query.side_effect = [
            mock_db.session.query.return_value,  # Channel (filter_by)
            query_chain,  # Messages
            chair_chain,  # Chair membership
            members_chain,  # All memberships
        ]

        service = self._make_service()
        filename, content = service.assemble_channel_transcript("workshop-test-5")

        assert "type: channel" in content
        assert "identifier: workshop-test-5" in content
        assert "persona: dev-alice-1" in content
        assert "message_count: 3" in content
        assert "### Alice" in content
        assert "### Bob" in content
        assert "Let's discuss" in content
        assert "Sure thing" in content

    @patch.object(TranscriptExportService, "_persist")
    @patch.object(transcript_export_mod, "db")
    def test_channel_not_found(self, mock_db, mock_persist):
        mock_db.session.query.return_value.filter_by.return_value.first.return_value = (
            None
        )

        service = self._make_service()
        with pytest.raises(ValueError, match="Channel 'nonexistent' not found"):
            service.assemble_channel_transcript("nonexistent")

    @patch.object(TranscriptExportService, "_persist")
    @patch.object(transcript_export_mod, "db")
    def test_empty_channel(self, mock_db, mock_persist):
        """Test channel with no messages."""
        channel = _make_channel(channel_id=5, slug="workshop-empty-5")

        mock_db.session.query.return_value.filter_by.return_value.first.return_value = (
            channel
        )
        query_chain = MagicMock()
        query_chain.filter.return_value.order_by.return_value.all.return_value = []
        chair_chain = MagicMock()
        chair_chain.filter.return_value.first.return_value = None
        members_chain = MagicMock()
        members_chain.filter.return_value.all.return_value = []

        mock_db.session.query.side_effect = [
            mock_db.session.query.return_value,
            query_chain,
            chair_chain,
            members_chain,
        ]

        service = self._make_service()
        filename, content = service.assemble_channel_transcript("workshop-empty-5")

        assert "message_count: 0" in content
        assert "start_time: null" in content
        assert "persona: unknown" in content


# ---------------------------------------------------------------------------
# Server-side persistence
# ---------------------------------------------------------------------------


class TestPersist:
    def test_persist_writes_file(self, tmp_path):
        service = TranscriptExportService.__new__(TranscriptExportService)
        service._app = None
        service._transcripts_dir = tmp_path

        filepath = service._persist("test-file.md", "# Test Content\n\nHello world")

        assert filepath.exists()
        assert filepath.name == "test-file.md"
        content = filepath.read_text(encoding="utf-8")
        assert "# Test Content" in content
        assert "Hello world" in content
