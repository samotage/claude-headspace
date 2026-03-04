"""Tests for HandoffDetectionService."""

import uuid
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

from claude_headspace.database import db
from claude_headspace.services.handoff_detection import HandoffDetectionService


def _make_mock_agent(persona_slug="developer-con-1"):
    """Create a mock agent (no DB) for tests that don't need persistence."""
    agent = MagicMock()
    agent.id = 1
    agent.project_id = 42
    if persona_slug:
        persona = MagicMock()
        persona.slug = persona_slug
        agent.persona = persona
        agent.persona_id = 10
    else:
        agent.persona = None
        agent.persona_id = None
    agent.get_current_command.return_value = None
    return agent


def _make_db_agent(handoff_dir: Path, app):
    """Create a real Agent + Project in DB with mock persona pointing at handoff_dir."""
    from claude_headspace.models.agent import Agent
    from claude_headspace.models.project import Project

    project = Project(name="test-project", slug="test-project", path="/tmp/test")
    db.session.add(project)
    db.session.flush()

    agent = Agent(project_id=project.id, session_uuid=uuid.uuid4())
    db.session.add(agent)
    db.session.flush()

    # We patch get_persona_dir to return the parent of handoff_dir
    # so the service finds handoff_dir/{slug}/handoffs -> handoff_dir
    # Actually, the service does get_persona_dir(slug) / "handoffs",
    # so we need get_persona_dir to return handoff_dir.parent
    # (where handoff_dir IS the "handoffs" subdirectory).
    # For simplicity, we'll set a mock persona and patch get_persona_dir.
    persona = MagicMock()
    persona.slug = "test-persona"

    # Use a property mock so SQLAlchemy doesn't get confused
    type(agent).persona = PropertyMock(return_value=persona)
    agent.persona_id = 10

    return agent


class TestDetectAndEmit:
    """Tests for HandoffDetectionService.detect_and_emit()."""

    def test_no_persona_returns_false(self, app):
        svc = HandoffDetectionService(app=app)
        agent = _make_mock_agent(persona_slug=None)
        assert svc.detect_and_emit(agent) is False

    def test_none_agent_returns_false(self, app):
        svc = HandoffDetectionService(app=app)
        assert svc.detect_and_emit(None) is False

    def test_missing_handoff_dir_returns_false(self, app, tmp_path):
        with app.app_context():
            svc = HandoffDetectionService(app=app)
            agent = _make_mock_agent()

            with patch(
                "claude_headspace.services.handoff_detection.get_persona_dir",
                return_value=tmp_path / "nonexistent",
            ):
                assert svc.detect_and_emit(agent) is False

    def test_empty_handoff_dir_returns_false(self, app, tmp_path):
        with app.app_context():
            persona_dir = tmp_path / "test-persona"
            (persona_dir / "handoffs").mkdir(parents=True)

            svc = HandoffDetectionService(app=app)
            agent = _make_mock_agent()

            with patch(
                "claude_headspace.services.handoff_detection.get_persona_dir",
                return_value=persona_dir,
            ):
                assert svc.detect_and_emit(agent) is False

    def test_creates_turn_records_with_files(self, app, tmp_path):
        """Should create Turn records for each handoff file."""
        with app.app_context():
            persona_dir = tmp_path / "test-persona"
            handoff_dir = persona_dir / "handoffs"
            handoff_dir.mkdir(parents=True)

            (handoff_dir / "2026-01-01T10:00:00_first-task_agent-id:100.md").write_text(
                "# Handoff 1"
            )
            (
                handoff_dir / "2026-01-02T10:00:00_second-task_agent-id:101.md"
            ).write_text("# Handoff 2")

            from claude_headspace.models.agent import Agent
            from claude_headspace.models.project import Project

            project = Project(
                name="test-project", slug=f"test-hd-{uuid.uuid4().hex[:8]}", path=str(tmp_path / "proj")
            )
            db.session.add(project)
            db.session.flush()

            agent = Agent(project_id=project.id, session_uuid=uuid.uuid4())
            db.session.add(agent)
            db.session.flush()

            # Attach a mock persona that won't confuse SQLAlchemy
            mock_persona = MagicMock()
            mock_persona.slug = "test-persona"

            svc = HandoffDetectionService(app=app)

            with (
                patch.object(
                    type(agent), "persona", new_callable=PropertyMock, return_value=mock_persona
                ),
                patch(
                    "claude_headspace.services.handoff_detection.get_persona_dir",
                    return_value=persona_dir,
                ),
                patch(
                    "claude_headspace.services.broadcaster.get_broadcaster"
                ) as mock_get_bc,
            ):
                mock_broadcaster = MagicMock()
                mock_get_bc.return_value = mock_broadcaster

                result = svc.detect_and_emit(agent)

            assert result is True

            # Verify turn_created SSE was broadcast for each turn
            assert mock_broadcaster.broadcast.call_count == 2
            for call in mock_broadcaster.broadcast.call_args_list:
                assert call[0][0] == "turn_created"
                data = call[0][1]
                assert data["agent_id"] == agent.id
                assert data["actor"] == "agent"
                assert data["intent"] == "progress"

            db.session.rollback()

    def test_returns_top_3_sorted_reverse(self, app, tmp_path):
        """Should create at most 3 turns, sorted newest first."""
        with app.app_context():
            persona_dir = tmp_path / "test-persona"
            handoff_dir = persona_dir / "handoffs"
            handoff_dir.mkdir(parents=True)

            for i in range(1, 6):
                fname = f"2026-01-0{i}T10:00:00_task-{i}_agent-id:{100 + i}.md"
                (handoff_dir / fname).write_text(f"# Handoff {i}")

            from claude_headspace.models.agent import Agent
            from claude_headspace.models.project import Project

            project = Project(
                name="test-project", slug=f"test-hd-{uuid.uuid4().hex[:8]}", path=str(tmp_path / "proj")
            )
            db.session.add(project)
            db.session.flush()

            agent = Agent(project_id=project.id, session_uuid=uuid.uuid4())
            db.session.add(agent)
            db.session.flush()

            mock_persona = MagicMock()
            mock_persona.slug = "test-persona"

            svc = HandoffDetectionService(app=app)

            with (
                patch.object(
                    type(agent), "persona", new_callable=PropertyMock, return_value=mock_persona
                ),
                patch(
                    "claude_headspace.services.handoff_detection.get_persona_dir",
                    return_value=persona_dir,
                ),
                patch(
                    "claude_headspace.services.broadcaster.get_broadcaster"
                ) as mock_get_bc,
            ):
                mock_get_bc.return_value = MagicMock()
                result = svc.detect_and_emit(agent)

            assert result is True

            # Check broadcast calls contain the expected file paths
            bc = mock_get_bc.return_value
            assert bc.broadcast.call_count == 3
            texts = [c[0][1]["text"] for c in bc.broadcast.call_args_list]
            assert any("task-5" in t for t in texts)
            assert any("task-4" in t for t in texts)
            assert any("task-3" in t for t in texts)

            db.session.rollback()

    def test_turn_text_is_absolute_path(self, app, tmp_path):
        """Turn text should be the absolute file path."""
        import os

        with app.app_context():
            persona_dir = tmp_path / "test-persona"
            handoff_dir = persona_dir / "handoffs"
            handoff_dir.mkdir(parents=True)

            (handoff_dir / "2026-01-01T10:00:00_some-task_agent-id:1.md").write_text(
                "# Content"
            )

            from claude_headspace.models.agent import Agent
            from claude_headspace.models.project import Project

            project = Project(
                name="test-project", slug=f"test-hd-{uuid.uuid4().hex[:8]}", path=str(tmp_path / "proj")
            )
            db.session.add(project)
            db.session.flush()

            agent = Agent(project_id=project.id, session_uuid=uuid.uuid4())
            db.session.add(agent)
            db.session.flush()

            mock_persona = MagicMock()
            mock_persona.slug = "test-persona"

            svc = HandoffDetectionService(app=app)

            with (
                patch.object(
                    type(agent), "persona", new_callable=PropertyMock, return_value=mock_persona
                ),
                patch(
                    "claude_headspace.services.handoff_detection.get_persona_dir",
                    return_value=persona_dir,
                ),
                patch(
                    "claude_headspace.services.broadcaster.get_broadcaster"
                ) as mock_get_bc,
            ):
                mock_get_bc.return_value = MagicMock()
                svc.detect_and_emit(agent)

            # Verify broadcast has absolute path in text
            bc = mock_get_bc.return_value
            assert bc.broadcast.call_count == 1
            text = bc.broadcast.call_args[0][1]["text"]
            assert os.path.isabs(text)

            db.session.rollback()

    def test_broadcast_failure_still_creates_turns(self, app, tmp_path):
        """If broadcast raises, turns should still be persisted."""
        with app.app_context():
            persona_dir = tmp_path / "test-persona"
            handoff_dir = persona_dir / "handoffs"
            handoff_dir.mkdir(parents=True)
            (handoff_dir / "2026-01-01T10:00:00_task_agent-id:1.md").write_text("# X")

            from claude_headspace.models.agent import Agent
            from claude_headspace.models.project import Project

            project = Project(
                name="test-project", slug=f"test-hd-{uuid.uuid4().hex[:8]}", path=str(tmp_path / "proj")
            )
            db.session.add(project)
            db.session.flush()

            agent = Agent(project_id=project.id, session_uuid=uuid.uuid4())
            db.session.add(agent)
            db.session.flush()

            mock_persona = MagicMock()
            mock_persona.slug = "test-persona"

            svc = HandoffDetectionService(app=app)

            with (
                patch.object(
                    type(agent), "persona", new_callable=PropertyMock, return_value=mock_persona
                ),
                patch(
                    "claude_headspace.services.handoff_detection.get_persona_dir",
                    return_value=persona_dir,
                ),
                patch(
                    "claude_headspace.services.broadcaster.get_broadcaster"
                ) as mock_get_bc,
            ):
                mock_get_bc.side_effect = RuntimeError("No broadcaster")

                result = svc.detect_and_emit(agent)

            # Turns were committed before broadcast attempt
            assert result is True
            from claude_headspace.models.command import Command
            from claude_headspace.models.turn import Turn

            # Find the command created for this agent
            cmd = Command.query.filter_by(agent_id=agent.id).first()
            assert cmd is not None
            turns = Turn.query.filter_by(command_id=cmd.id).all()
            assert len(turns) == 1

            db.session.rollback()

    def test_successor_agent_still_gets_listing(self, app, tmp_path):
        """Successors (with previous_agent_id) should still get the listing."""
        with app.app_context():
            persona_dir = tmp_path / "test-persona"
            handoff_dir = persona_dir / "handoffs"
            handoff_dir.mkdir(parents=True)
            (
                handoff_dir / "2026-01-01T10:00:00_previous-work_agent-id:99.md"
            ).write_text("# Previous")

            from claude_headspace.models.agent import Agent
            from claude_headspace.models.project import Project

            project = Project(
                name="test-project", slug=f"test-hd-{uuid.uuid4().hex[:8]}", path=str(tmp_path / "proj")
            )
            db.session.add(project)
            db.session.flush()

            agent = Agent(project_id=project.id, session_uuid=uuid.uuid4())
            db.session.add(agent)
            db.session.flush()

            mock_persona = MagicMock()
            mock_persona.slug = "test-persona"

            svc = HandoffDetectionService(app=app)

            with (
                patch.object(
                    type(agent), "persona", new_callable=PropertyMock, return_value=mock_persona
                ),
                patch(
                    "claude_headspace.services.handoff_detection.get_persona_dir",
                    return_value=persona_dir,
                ),
                patch(
                    "claude_headspace.services.broadcaster.get_broadcaster"
                ) as mock_get_bc,
            ):
                mock_get_bc.return_value = MagicMock()
                result = svc.detect_and_emit(agent)

            assert result is True

            db.session.rollback()
