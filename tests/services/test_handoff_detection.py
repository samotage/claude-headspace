"""Tests for HandoffDetectionService."""

from unittest.mock import MagicMock, patch

from claude_headspace.services.handoff_detection import HandoffDetectionService


def _make_agent(agent_id=1, persona_slug="developer-con-1"):
    """Create a mock agent with optional persona."""
    agent = MagicMock()
    agent.id = agent_id
    if persona_slug:
        persona = MagicMock()
        persona.slug = persona_slug
        agent.persona = persona
        agent.persona_id = 10
    else:
        agent.persona = None
        agent.persona_id = None
    return agent


class TestDetectAndEmit:
    """Tests for HandoffDetectionService.detect_and_emit()."""

    def test_no_persona_returns_false(self, app):
        """Agent without persona should not trigger detection."""
        svc = HandoffDetectionService(app=app)
        agent = _make_agent(persona_slug=None)

        result = svc.detect_and_emit(agent)

        assert result is False

    def test_none_agent_returns_false(self, app):
        """None agent should not trigger detection."""
        svc = HandoffDetectionService(app=app)

        result = svc.detect_and_emit(None)

        assert result is False

    def test_missing_handoff_dir_returns_false(self, app, tmp_path):
        """No handoff directory should return False without error."""
        with app.app_context():
            app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
            svc = HandoffDetectionService(app=app)
            agent = _make_agent()

            result = svc.detect_and_emit(agent)

        assert result is False

    def test_empty_handoff_dir_returns_false(self, app, tmp_path):
        """Empty handoff directory should return False."""
        with app.app_context():
            app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
            handoff_dir = tmp_path / "developer-con-1" / "handoffs"
            handoff_dir.mkdir(parents=True)

            svc = HandoffDetectionService(app=app)
            agent = _make_agent()

            result = svc.detect_and_emit(agent)

        assert result is False

    def test_emits_synthetic_turn_with_files(self, app, tmp_path):
        """Should emit synthetic_turn SSE event with handoff filenames."""
        with app.app_context():
            app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
            handoff_dir = tmp_path / "developer-con-1" / "handoffs"
            handoff_dir.mkdir(parents=True)

            # Create some handoff files
            (handoff_dir / "2026-01-01T10:00:00_first-task_agent-id:100.md").write_text(
                "# Handoff 1"
            )
            (
                handoff_dir / "2026-01-02T10:00:00_second-task_agent-id:101.md"
            ).write_text("# Handoff 2")

            svc = HandoffDetectionService(app=app)
            agent = _make_agent()

            with patch(
                "claude_headspace.services.broadcaster.get_broadcaster"
            ) as mock_get_bc:
                mock_broadcaster = MagicMock()
                mock_get_bc.return_value = mock_broadcaster

                result = svc.detect_and_emit(agent)

            assert result is True
            mock_broadcaster.broadcast.assert_called_once()
            call_args = mock_broadcaster.broadcast.call_args
            assert call_args[0][0] == "synthetic_turn"
            data = call_args[0][1]
            assert data["agent_id"] == 1
            assert data["persona_slug"] == "developer-con-1"
            assert len(data["turns"]) == 1
            turn = data["turns"][0]
            assert turn["type"] == "handoff_listing"
            assert len(turn["filenames"]) == 2

    def test_returns_top_3_sorted_reverse(self, app, tmp_path):
        """Should return at most 3 files, sorted newest first."""
        with app.app_context():
            app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
            handoff_dir = tmp_path / "developer-con-1" / "handoffs"
            handoff_dir.mkdir(parents=True)

            # Create 5 files
            for i in range(1, 6):
                fname = f"2026-01-0{i}T10:00:00_task-{i}_agent-id:{100 + i}.md"
                (handoff_dir / fname).write_text(f"# Handoff {i}")

            svc = HandoffDetectionService(app=app)
            agent = _make_agent()

            with patch(
                "claude_headspace.services.broadcaster.get_broadcaster"
            ) as mock_get_bc:
                mock_broadcaster = MagicMock()
                mock_get_bc.return_value = mock_broadcaster

                result = svc.detect_and_emit(agent)

            assert result is True
            data = mock_broadcaster.broadcast.call_args[0][1]
            filenames = data["turns"][0]["filenames"]
            assert len(filenames) == 3
            # Newest first (reverse sort by filename)
            assert "task-5" in filenames[0]
            assert "task-4" in filenames[1]
            assert "task-3" in filenames[2]

    def test_includes_absolute_file_paths(self, app, tmp_path):
        """File paths in the event should be absolute."""
        with app.app_context():
            app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
            handoff_dir = tmp_path / "developer-con-1" / "handoffs"
            handoff_dir.mkdir(parents=True)

            (handoff_dir / "2026-01-01T10:00:00_some-task_agent-id:1.md").write_text(
                "# Content"
            )

            svc = HandoffDetectionService(app=app)
            agent = _make_agent()

            with patch(
                "claude_headspace.services.broadcaster.get_broadcaster"
            ) as mock_get_bc:
                mock_broadcaster = MagicMock()
                mock_get_bc.return_value = mock_broadcaster

                svc.detect_and_emit(agent)

            data = mock_broadcaster.broadcast.call_args[0][1]
            file_paths = data["turns"][0]["file_paths"]
            assert len(file_paths) == 1
            import os

            assert os.path.isabs(file_paths[0])

    def test_broadcast_failure_returns_false(self, app, tmp_path):
        """If broadcast raises, return False gracefully."""
        with app.app_context():
            app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
            handoff_dir = tmp_path / "developer-con-1" / "handoffs"
            handoff_dir.mkdir(parents=True)
            (handoff_dir / "2026-01-01T10:00:00_task_agent-id:1.md").write_text("# X")

            svc = HandoffDetectionService(app=app)
            agent = _make_agent()

            with patch(
                "claude_headspace.services.broadcaster.get_broadcaster"
            ) as mock_get_bc:
                mock_get_bc.side_effect = RuntimeError("No broadcaster")

                result = svc.detect_and_emit(agent)

            assert result is False

    def test_handoff_executor_successor_still_gets_listing(self, app, tmp_path):
        """Successors (with previous_agent_id) should still get the listing."""
        with app.app_context():
            app.config["PERSONA_DATA_ROOT"] = str(tmp_path)
            handoff_dir = tmp_path / "developer-con-1" / "handoffs"
            handoff_dir.mkdir(parents=True)
            (
                handoff_dir / "2026-01-01T10:00:00_previous-work_agent-id:99.md"
            ).write_text("# Previous")

            svc = HandoffDetectionService(app=app)
            agent = _make_agent(agent_id=100)
            agent.previous_agent_id = 99

            with patch(
                "claude_headspace.services.broadcaster.get_broadcaster"
            ) as mock_get_bc:
                mock_broadcaster = MagicMock()
                mock_get_bc.return_value = mock_broadcaster

                result = svc.detect_and_emit(agent)

            assert result is True
