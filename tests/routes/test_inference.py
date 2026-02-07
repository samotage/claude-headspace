"""Unit tests for inference, summarisation, and priority API endpoints.

Expands test coverage for all inference-related routes including:
- Inference status/usage endpoints
- Summarisation endpoints (turn + task)
- Priority scoring + rankings endpoints
- Error recovery, input validation, rate limiting behavior
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.inference import inference_bp
from src.claude_headspace.routes.summarisation import summarisation_bp
from src.claude_headspace.routes.priority import priority_bp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app():
    """Create a test Flask application with all inference-related blueprints."""
    app = Flask(__name__)
    app.register_blueprint(inference_bp)
    app.register_blueprint(summarisation_bp)
    app.register_blueprint(priority_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_inference():
    service = MagicMock()
    service.is_available = True
    service.get_status.return_value = {
        "available": True,
        "openrouter_connected": True,
        "models": {
            "turn": "anthropic/claude-3-haiku",
            "project": "anthropic/claude-3.5-sonnet",
        },
        "rate_limits": {
            "calls_per_minute": {"current": 5, "limit": 30},
            "tokens_per_minute": {"current": 1000, "limit": 50000},
        },
        "cache": {
            "enabled": True,
            "ttl_seconds": 300,
            "size": 10,
            "hits": 25,
            "misses": 15,
            "hit_rate": 0.625,
        },
    }
    service.get_usage.return_value = {
        "total_calls": 100,
        "calls_by_level": {"turn": 70, "project": 30},
        "calls_by_model": {
            "anthropic/claude-3-haiku": 70,
            "anthropic/claude-3.5-sonnet": 30,
        },
        "total_input_tokens": 15000,
        "total_output_tokens": 5000,
        "total_cost": 0.095,
        "cost_by_model": {
            "anthropic/claude-3-haiku": 0.04,
            "anthropic/claude-3.5-sonnet": 0.055,
        },
    }
    return service


@pytest.fixture
def mock_summarisation():
    return MagicMock()


@pytest.fixture
def mock_priority():
    return MagicMock()


# ===========================================================================
# Inference Status Endpoint
# ===========================================================================

class TestInferenceStatus:

    def test_status_returns_service_status(self, app, client, mock_inference):
        app.extensions["inference_service"] = mock_inference
        response = client.get("/api/inference/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["available"] is True
        assert data["openrouter_connected"] is True
        assert "models" in data
        assert "rate_limits" in data
        assert "cache" in data

    def test_status_no_service_returns_503(self, app, client):
        app.extensions.pop("inference_service", None)
        response = client.get("/api/inference/status")

        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data

    def test_status_returns_rate_limit_info(self, app, client, mock_inference):
        app.extensions["inference_service"] = mock_inference
        response = client.get("/api/inference/status")

        data = response.get_json()
        rl = data["rate_limits"]
        assert rl["calls_per_minute"]["current"] == 5
        assert rl["calls_per_minute"]["limit"] == 30

    def test_status_returns_cache_stats(self, app, client, mock_inference):
        app.extensions["inference_service"] = mock_inference
        response = client.get("/api/inference/status")

        data = response.get_json()
        assert data["cache"]["hit_rate"] == 0.625
        assert data["cache"]["size"] == 10

    def test_status_when_disconnected(self, app, client, mock_inference):
        mock_inference.get_status.return_value = {
            "available": False,
            "openrouter_connected": False,
            "error": "Connection refused",
        }
        app.extensions["inference_service"] = mock_inference
        response = client.get("/api/inference/status")

        assert response.status_code == 200
        data = response.get_json()
        assert data["available"] is False


# ===========================================================================
# Inference Usage Endpoint
# ===========================================================================

class TestInferenceUsage:

    def test_usage_returns_statistics(self, app, client, mock_inference):
        app.extensions["inference_service"] = mock_inference

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session = MagicMock()
            response = client.get("/api/inference/usage")

        assert response.status_code == 200
        data = response.get_json()
        assert data["total_calls"] == 100
        assert data["calls_by_level"]["turn"] == 70
        assert data["total_input_tokens"] == 15000
        assert data["total_cost"] == 0.095

    def test_usage_no_service_returns_503(self, app, client):
        app.extensions.pop("inference_service", None)
        response = client.get("/api/inference/usage")

        assert response.status_code == 503
        data = response.get_json()
        assert "error" in data

    def test_usage_cost_breakdown_by_model(self, app, client, mock_inference):
        app.extensions["inference_service"] = mock_inference

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session = MagicMock()
            response = client.get("/api/inference/usage")

        data = response.get_json()
        assert "cost_by_model" in data
        assert data["cost_by_model"]["anthropic/claude-3-haiku"] == 0.04

    def test_usage_empty_stats(self, app, client, mock_inference):
        mock_inference.get_usage.return_value = {
            "total_calls": 0,
            "calls_by_level": {},
            "calls_by_model": {},
            "total_input_tokens": 0,
            "total_output_tokens": 0,
            "total_cost": 0.0,
            "cost_by_model": {},
        }
        app.extensions["inference_service"] = mock_inference

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session = MagicMock()
            response = client.get("/api/inference/usage")

        assert response.status_code == 200
        data = response.get_json()
        assert data["total_calls"] == 0
        assert data["total_cost"] == 0.0


# ===========================================================================
# Summarisation Endpoints
# ===========================================================================

class TestSummariseTurn:

    def test_success_generates_summary(self, app, client, mock_summarisation, mock_inference):
        app.extensions["summarisation_service"] = mock_summarisation
        app.extensions["inference_service"] = mock_inference

        mock_turn = MagicMock()
        mock_turn.summary = None
        mock_turn.summary_generated_at = None

        def set_summary(turn, db_session=None):
            turn.summary = "Generated turn summary"
            turn.summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
            return "Generated turn summary"

        mock_summarisation.summarise_turn.side_effect = set_summary

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_turn
            response = client.post("/api/summarise/turn/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["summary"] == "Generated turn summary"
        assert data["cached"] is False

    def test_returns_cached_summary(self, app, client, mock_summarisation):
        app.extensions["summarisation_service"] = mock_summarisation

        mock_turn = MagicMock()
        mock_turn.summary = "Cached summary"
        mock_turn.summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_turn
            response = client.post("/api/summarise/turn/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["cached"] is True
        mock_summarisation.summarise_turn.assert_not_called()

    def test_turn_not_found_returns_404(self, app, client, mock_summarisation):
        app.extensions["summarisation_service"] = mock_summarisation

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/summarise/turn/999")

        assert response.status_code == 404

    def test_no_service_returns_503(self, app, client):
        app.extensions.pop("summarisation_service", None)
        response = client.post("/api/summarise/turn/1")
        assert response.status_code == 503

    def test_inference_unavailable_returns_503(self, app, client, mock_summarisation):
        app.extensions["summarisation_service"] = mock_summarisation
        mock_inf = MagicMock()
        mock_inf.is_available = False
        app.extensions["inference_service"] = mock_inf

        mock_turn = MagicMock()
        mock_turn.summary = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_turn
            response = client.post("/api/summarise/turn/1")

        assert response.status_code == 503

    def test_summarisation_failure_returns_500(self, app, client, mock_summarisation, mock_inference):
        app.extensions["summarisation_service"] = mock_summarisation
        app.extensions["inference_service"] = mock_inference

        mock_turn = MagicMock()
        mock_turn.summary = None
        mock_summarisation.summarise_turn.return_value = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_turn
            response = client.post("/api/summarise/turn/1")

        assert response.status_code == 500


class TestSummariseTask:

    def test_success_generates_summary(self, app, client, mock_summarisation, mock_inference):
        app.extensions["summarisation_service"] = mock_summarisation
        app.extensions["inference_service"] = mock_inference

        mock_task = MagicMock()
        mock_task.completion_summary = None
        mock_task.completion_summary_generated_at = None

        def set_summary(task, db_session=None):
            task.completion_summary = "Task done summary"
            task.completion_summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)
            return "Task done summary"

        mock_summarisation.summarise_task.side_effect = set_summary

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_task
            response = client.post("/api/summarise/task/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["summary"] == "Task done summary"
        assert data["cached"] is False

    def test_returns_cached_summary(self, app, client, mock_summarisation):
        app.extensions["summarisation_service"] = mock_summarisation

        mock_task = MagicMock()
        mock_task.completion_summary = "Already summarised"
        mock_task.completion_summary_generated_at = datetime(2026, 1, 31, 10, 0, 0, tzinfo=timezone.utc)

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_task
            response = client.post("/api/summarise/task/1")

        assert response.status_code == 200
        data = response.get_json()
        assert data["cached"] is True
        mock_summarisation.summarise_task.assert_not_called()

    def test_task_not_found_returns_404(self, app, client, mock_summarisation):
        app.extensions["summarisation_service"] = mock_summarisation

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = None
            response = client.post("/api/summarise/task/999")

        assert response.status_code == 404

    def test_no_service_returns_503(self, app, client):
        app.extensions.pop("summarisation_service", None)
        response = client.post("/api/summarise/task/1")
        assert response.status_code == 503

    def test_inference_unavailable_returns_503(self, app, client, mock_summarisation):
        app.extensions["summarisation_service"] = mock_summarisation
        mock_inf = MagicMock()
        mock_inf.is_available = False
        app.extensions["inference_service"] = mock_inf

        mock_task = MagicMock()
        mock_task.completion_summary = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_task
            response = client.post("/api/summarise/task/1")

        assert response.status_code == 503

    def test_summarisation_failure_returns_500(self, app, client, mock_summarisation, mock_inference):
        app.extensions["summarisation_service"] = mock_summarisation
        app.extensions["inference_service"] = mock_inference

        mock_task = MagicMock()
        mock_task.completion_summary = None
        mock_summarisation.summarise_task.return_value = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.get.return_value = mock_task
            response = client.post("/api/summarise/task/1")

        assert response.status_code == 500


# ===========================================================================
# Priority Scoring Endpoints
# ===========================================================================

class TestTriggerScoring:

    def test_score_success(self, app, client, mock_priority, mock_inference):
        app.extensions["priority_scoring_service"] = mock_priority
        app.extensions["inference_service"] = mock_inference

        mock_priority.score_all_agents.return_value = {
            "scored": 2,
            "agents": [
                {"agent_id": 1, "score": 85, "reason": "Aligned"},
                {"agent_id": 2, "score": 60, "reason": "Moderate"},
            ],
            "context_type": "objective",
        }

        with patch("src.claude_headspace.database.db"):
            response = client.post("/api/priority/score")

        assert response.status_code == 200
        data = response.get_json()
        assert data["scored"] == 2
        assert len(data["agents"]) == 2

    def test_score_no_agents(self, app, client, mock_priority, mock_inference):
        app.extensions["priority_scoring_service"] = mock_priority
        app.extensions["inference_service"] = mock_inference
        mock_priority.score_all_agents.return_value = {
            "scored": 0, "agents": [], "context_type": "none",
        }

        with patch("src.claude_headspace.database.db"):
            response = client.post("/api/priority/score")

        assert response.status_code == 200
        data = response.get_json()
        assert data["scored"] == 0

    def test_score_no_service(self, app, client):
        app.extensions.pop("priority_scoring_service", None)
        response = client.post("/api/priority/score")
        assert response.status_code == 503

    def test_score_inference_unavailable(self, app, client, mock_priority):
        app.extensions["priority_scoring_service"] = mock_priority
        mock_inf = MagicMock()
        mock_inf.is_available = False
        app.extensions["inference_service"] = mock_inf
        response = client.post("/api/priority/score")
        assert response.status_code == 503

    def test_score_error_returns_500(self, app, client, mock_priority, mock_inference):
        app.extensions["priority_scoring_service"] = mock_priority
        app.extensions["inference_service"] = mock_inference
        mock_priority.score_all_agents.return_value = {
            "error": "API failure",
        }

        with patch("src.claude_headspace.database.db"):
            response = client.post("/api/priority/score")

        assert response.status_code == 500

    def test_score_no_inference_service(self, app, client, mock_priority):
        app.extensions["priority_scoring_service"] = mock_priority
        app.extensions.pop("inference_service", None)
        response = client.post("/api/priority/score")
        assert response.status_code == 503


class TestRankings:

    def test_rankings_success(self, app, client, mock_priority):
        app.extensions["priority_scoring_service"] = mock_priority

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.project.name = "project-a"
        mock_agent.state.value = "processing"
        mock_agent.priority_score = 85
        mock_agent.priority_reason = "Aligned"
        mock_agent.priority_updated_at = MagicMock()
        mock_agent.priority_updated_at.isoformat.return_value = "2026-01-31T10:00:00+00:00"

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_agent]
            response = client.get("/api/priority/rankings")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["agents"]) == 1
        assert data["agents"][0]["score"] == 85

    def test_rankings_no_service(self, app, client):
        app.extensions.pop("priority_scoring_service", None)
        response = client.get("/api/priority/rankings")
        assert response.status_code == 503

    def test_rankings_empty(self, app, client, mock_priority):
        app.extensions["priority_scoring_service"] = mock_priority

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            response = client.get("/api/priority/rankings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["agents"] == []

    def test_rankings_agent_without_score(self, app, client, mock_priority):
        app.extensions["priority_scoring_service"] = mock_priority

        mock_agent = MagicMock()
        mock_agent.id = 1
        mock_agent.project.name = "test"
        mock_agent.state.value = "idle"
        mock_agent.priority_score = None
        mock_agent.priority_reason = None
        mock_agent.priority_updated_at = None

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [mock_agent]
            response = client.get("/api/priority/rankings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["agents"][0]["score"] is None
        assert data["agents"][0]["scored_at"] is None

    def test_rankings_multiple_agents_ordered(self, app, client, mock_priority):
        app.extensions["priority_scoring_service"] = mock_priority

        agents = []
        for i, score in enumerate([90, 70, 50]):
            agent = MagicMock()
            agent.id = i + 1
            agent.project.name = f"project-{i}"
            agent.state.value = "processing"
            agent.priority_score = score
            agent.priority_reason = f"Reason {i}"
            agent.priority_updated_at = MagicMock()
            agent.priority_updated_at.isoformat.return_value = "2026-01-31T10:00:00+00:00"
            agents.append(agent)

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = agents
            response = client.get("/api/priority/rankings")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["agents"]) == 3
        scores = [a["score"] for a in data["agents"]]
        assert scores == [90, 70, 50]
