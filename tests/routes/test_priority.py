"""Unit tests for priority scoring API endpoints."""

from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.priority import priority_bp


@pytest.fixture
def app():
    """Create a test Flask application with priority blueprint."""
    app = Flask(__name__)
    app.register_blueprint(priority_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_service():
    service = MagicMock()
    return service


@pytest.fixture
def mock_inference():
    service = MagicMock()
    service.is_available = True
    return service


class TestTriggerScoringEndpoint:

    def test_score_success(self, app, client, mock_service, mock_inference):
        app.extensions["priority_scoring_service"] = mock_service
        app.extensions["inference_service"] = mock_inference

        mock_service.score_all_agents.return_value = {
            "scored": 2,
            "agents": [
                {"agent_id": 1, "score": 85, "reason": "Aligned", "scored_at": "2026-01-31T10:00:00+00:00"},
                {"agent_id": 2, "score": 60, "reason": "Moderate", "scored_at": "2026-01-31T10:00:00+00:00"},
            ],
            "context_type": "objective",
        }

        with patch("src.claude_headspace.database.db") as mock_db:
            response = client.post("/api/priority/score")

        assert response.status_code == 200
        data = response.get_json()
        assert data["scored"] == 2
        assert len(data["agents"]) == 2
        assert data["context_type"] == "objective"

    def test_score_no_agents(self, app, client, mock_service, mock_inference):
        app.extensions["priority_scoring_service"] = mock_service
        app.extensions["inference_service"] = mock_inference
        mock_service.score_all_agents.return_value = {
            "scored": 0,
            "agents": [],
            "context_type": "none",
        }

        with patch("src.claude_headspace.database.db"):
            response = client.post("/api/priority/score")

        assert response.status_code == 200
        data = response.get_json()
        assert data["scored"] == 0
        assert data["agents"] == []

    def test_score_no_service(self, app, client):
        app.extensions.pop("priority_scoring_service", None)
        response = client.post("/api/priority/score")
        assert response.status_code == 503

    def test_score_inference_unavailable(self, app, client, mock_service):
        app.extensions["priority_scoring_service"] = mock_service
        mock_inference = MagicMock()
        mock_inference.is_available = False
        app.extensions["inference_service"] = mock_inference

        response = client.post("/api/priority/score")
        assert response.status_code == 503

    def test_score_error_returns_500(self, app, client, mock_service, mock_inference):
        app.extensions["priority_scoring_service"] = mock_service
        app.extensions["inference_service"] = mock_inference
        mock_service.score_all_agents.return_value = {
            "scored": 0,
            "agents": [],
            "context_type": "objective",
            "error": "API failure",
        }

        with patch("src.claude_headspace.database.db"):
            response = client.post("/api/priority/score")

        assert response.status_code == 500


class TestRankingsEndpoint:

    def test_rankings_success(self, app, client, mock_service):
        app.extensions["priority_scoring_service"] = mock_service

        mock_agent_1 = MagicMock()
        mock_agent_1.id = 1
        mock_agent_1.project.name = "project-a"
        mock_agent_1.state.value = "processing"
        mock_agent_1.priority_score = 85
        mock_agent_1.priority_reason = "Aligned with objective"
        mock_agent_1.priority_updated_at = MagicMock()
        mock_agent_1.priority_updated_at.isoformat.return_value = "2026-01-31T10:00:00+00:00"

        mock_agent_2 = MagicMock()
        mock_agent_2.id = 2
        mock_agent_2.project.name = "project-b"
        mock_agent_2.state.value = "idle"
        mock_agent_2.priority_score = 40
        mock_agent_2.priority_reason = "Low priority"
        mock_agent_2.priority_updated_at = MagicMock()
        mock_agent_2.priority_updated_at.isoformat.return_value = "2026-01-31T10:00:00+00:00"

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = [
                mock_agent_1, mock_agent_2
            ]
            response = client.get("/api/priority/rankings")

        assert response.status_code == 200
        data = response.get_json()
        assert len(data["agents"]) == 2
        assert data["agents"][0]["score"] == 85
        assert data["agents"][1]["score"] == 40

    def test_rankings_no_service(self, app, client):
        app.extensions.pop("priority_scoring_service", None)
        response = client.get("/api/priority/rankings")
        assert response.status_code == 503

    def test_rankings_empty(self, app, client, mock_service):
        app.extensions["priority_scoring_service"] = mock_service

        with patch("src.claude_headspace.database.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.order_by.return_value.all.return_value = []
            response = client.get("/api/priority/rankings")

        assert response.status_code == 200
        data = response.get_json()
        assert data["agents"] == []

    def test_rankings_agent_without_score(self, app, client, mock_service):
        app.extensions["priority_scoring_service"] = mock_service

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
