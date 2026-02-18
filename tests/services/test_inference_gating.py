"""Tests for inference gating when project inference is paused."""

from unittest.mock import MagicMock, patch

import pytest

from claude_headspace.services.summarisation_service import SummarisationService


@pytest.fixture
def mock_inference():
    """Create a mock inference service."""
    service = MagicMock()
    service.is_available = True
    return service


@pytest.fixture
def summarisation_service(mock_inference):
    """Create a SummarisationService with mock inference."""
    return SummarisationService(inference_service=mock_inference)


@pytest.fixture
def paused_project():
    """Create a mock project with inference paused."""
    project = MagicMock()
    project.id = 1
    project.inference_paused = True
    return project


@pytest.fixture
def active_project():
    """Create a mock project with inference active."""
    project = MagicMock()
    project.id = 2
    project.inference_paused = False
    return project


@pytest.fixture
def mock_agent_paused(paused_project):
    """Create a mock agent belonging to a paused project."""
    agent = MagicMock()
    agent.project = paused_project
    agent.project_id = paused_project.id
    return agent


@pytest.fixture
def mock_agent_active(active_project):
    """Create a mock agent belonging to an active project."""
    agent = MagicMock()
    agent.project = active_project
    agent.project_id = active_project.id
    return agent


class TestSummariseTurnGating:
    """Tests for inference gating in summarise_turn."""

    def test_returns_none_when_project_paused(self, summarisation_service, mock_inference, mock_agent_paused):
        """summarise_turn should return None when project inference is paused."""
        cmd = MagicMock()
        cmd.agent = mock_agent_paused
        cmd.agent_id = mock_agent_paused.id

        turn = MagicMock()
        turn.id = 1
        turn.summary = None
        turn.text = "Some text"
        turn.command = cmd
        turn.command_id = cmd.id

        result = summarisation_service.summarise_turn(turn)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_proceeds_when_project_active(self, summarisation_service, mock_inference, mock_agent_active):
        """summarise_turn should call inference when project is active."""
        cmd = MagicMock()
        cmd.agent = mock_agent_active
        cmd.agent_id = mock_agent_active.id
        cmd.instruction = None

        turn = MagicMock()
        turn.id = 1
        turn.summary = None
        turn.text = "Some text"
        turn.command = cmd
        turn.command_id = cmd.id
        turn.intent.value = "command"
        turn.actor.value = "user"

        mock_inference.infer.return_value = MagicMock(text="Summary of turn")

        result = summarisation_service.summarise_turn(turn)

        assert result is not None
        mock_inference.infer.assert_called_once()


class TestSummariseCommandGating:
    """Tests for inference gating in summarise_command."""

    def test_returns_none_when_project_paused(self, summarisation_service, mock_inference, mock_agent_paused):
        """summarise_command should return None when project inference is paused."""
        cmd = MagicMock()
        cmd.id = 1
        cmd.completion_summary = None
        cmd.agent = mock_agent_paused
        cmd.agent_id = mock_agent_paused.id

        result = summarisation_service.summarise_command(cmd)

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_proceeds_when_project_active(self, summarisation_service, mock_inference, mock_agent_active):
        """summarise_command should call inference when project is active."""
        turn = MagicMock()
        turn.text = "Final turn text"
        turn.intent.value = "completion"
        turn.actor.value = "agent"
        turn.summary = None

        cmd = MagicMock()
        cmd.id = 1
        cmd.completion_summary = None
        cmd.agent = mock_agent_active
        cmd.agent_id = mock_agent_active.id
        cmd.instruction = "Do something"
        cmd.turns = [turn]

        mock_inference.infer.return_value = MagicMock(text="Command summary")

        result = summarisation_service.summarise_command(cmd)

        assert result is not None
        mock_inference.infer.assert_called_once()


class TestSummariseInstructionGating:
    """Tests for inference gating in summarise_instruction."""

    def test_returns_none_when_project_paused(self, summarisation_service, mock_inference, mock_agent_paused):
        """summarise_instruction should return None when project inference is paused."""
        cmd = MagicMock()
        cmd.id = 1
        cmd.instruction = None
        cmd.agent = mock_agent_paused
        cmd.agent_id = mock_agent_paused.id

        result = summarisation_service.summarise_instruction(cmd, "Do something")

        assert result is None
        mock_inference.infer.assert_not_called()

    def test_proceeds_when_project_active(self, summarisation_service, mock_inference, mock_agent_active):
        """summarise_instruction should call inference when project is active."""
        cmd = MagicMock()
        cmd.id = 1
        cmd.instruction = None
        cmd.agent = mock_agent_active
        cmd.agent_id = mock_agent_active.id

        mock_inference.infer.return_value = MagicMock(text="Instruction summary")

        result = summarisation_service.summarise_instruction(cmd, "Do something")

        assert result is not None
        mock_inference.infer.assert_called_once()


class TestPriorityScoringGating:
    """Tests for inference gating in priority scoring."""

    @patch("claude_headspace.services.priority_scoring.PriorityScoringService._broadcast_score_update")
    @patch("claude_headspace.services.priority_scoring.PriorityScoringService._broadcast_card_refreshes")
    def test_excludes_paused_project_agents(self, mock_card_refresh, mock_broadcast, mock_inference):
        """score_all_agents should exclude agents from paused projects."""
        from claude_headspace.services.priority_scoring import PriorityScoringService

        service = PriorityScoringService(inference_service=mock_inference)

        db_session = MagicMock()

        # Objective exists and is enabled
        mock_objective = MagicMock()
        mock_objective.priority_enabled = True

        # Query chain: first call for Objective, second for Agent
        db_session.query.return_value.first.return_value = mock_objective

        # Empty agent list (all agents are from paused projects, filtered by query)
        db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.all.return_value = []

        result = service.score_all_agents(db_session)

        assert result["scored"] == 0
        assert result["agents"] == []

    @patch("claude_headspace.services.priority_scoring.PriorityScoringService._broadcast_score_update")
    @patch("claude_headspace.services.priority_scoring.PriorityScoringService._broadcast_card_refreshes")
    def test_scores_active_project_agents(self, mock_card_refresh, mock_broadcast, mock_inference, active_project):
        """score_all_agents should score agents from active projects."""
        from claude_headspace.services.priority_scoring import PriorityScoringService

        service = PriorityScoringService(inference_service=mock_inference)

        db_session = MagicMock()

        # Objective exists and enabled
        mock_objective = MagicMock()
        mock_objective.priority_enabled = True
        mock_objective.current_text = "Build features"
        mock_objective.constraints = ""
        mock_objective.set_at = MagicMock()

        agent = MagicMock()
        agent.id = 1
        agent.project = active_project
        agent.state.value = "idle"
        agent.priority_score = None
        agent.get_current_command.return_value = None

        # Objective query
        db_session.query.return_value.first.return_value = mock_objective
        db_session.query.return_value.order_by.return_value.first.return_value = mock_objective

        # Agent query (filtered to exclude paused)
        db_session.query.return_value.join.return_value.filter.return_value.filter.return_value.all.return_value = [agent]

        mock_inference.infer.return_value = MagicMock(
            text='[{"agent_id": 1, "score": 75, "reason": "Active"}]'
        )

        result = service.score_all_agents(db_session)

        assert result["scored"] == 1
