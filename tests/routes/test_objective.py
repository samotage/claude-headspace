"""Tests for the objective route and API endpoints."""

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


class TestObjectivePage:
    """Tests for the objective page route."""

    def test_objective_page_renders(self, client):
        """Test that the objective page renders successfully."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value.count.return_value = 0

            response = client.get("/objective")
            assert response.status_code == 200
            assert b"Current Objective" in response.data

    def test_objective_page_shows_current_objective(self, client):
        """Test that the page shows the current objective."""
        mock_objective = MagicMock()
        mock_objective.current_text = "Test objective text"
        mock_objective.constraints = "Test constraints"
        mock_objective.set_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = mock_objective
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value.count.return_value = 0

            response = client.get("/objective")
            assert response.status_code == 200
            assert b"Test objective text" in response.data
            assert b"Test constraints" in response.data

    def test_objective_page_shows_history(self, client):
        """Test that the page shows objective history."""
        mock_history_item = MagicMock()
        mock_history_item.id = 1
        mock_history_item.text = "Previous objective"
        mock_history_item.constraints = None
        mock_history_item.started_at = datetime(2024, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        mock_history_item.ended_at = datetime(2024, 1, 1, 11, 0, 0, tzinfo=timezone.utc)

        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = [mock_history_item]
            mock_db.session.query.return_value.count.return_value = 1

            response = client.get("/objective")
            assert response.status_code == 200
            assert b"Previous objective" in response.data
            assert b"Objective History" in response.data

    def test_objective_page_shows_empty_history_message(self, client):
        """Test that empty history state is displayed."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value.count.return_value = 0

            response = client.get("/objective")
            assert response.status_code == 200
            assert b"No objective history yet" in response.data

    def test_objective_page_shows_load_more_when_needed(self, client):
        """Test that Load more button appears when there are more history items."""
        mock_history_items = [MagicMock() for _ in range(10)]
        for i, item in enumerate(mock_history_items):
            item.id = i + 1
            item.text = f"Objective {i}"
            item.constraints = None
            item.started_at = datetime(2024, 1, 1, tzinfo=timezone.utc)
            item.ended_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = mock_history_items
            mock_db.session.query.return_value.count.return_value = 15  # More than 10

            response = client.get("/objective")
            assert response.status_code == 200
            assert b"Load more" in response.data

    def test_objective_page_includes_javascript(self, client):
        """Test that objective.js is included in the page."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value.count.return_value = 0

            response = client.get("/objective")
            assert response.status_code == 200
            assert b"objective.js" in response.data


class TestGetObjectiveAPI:
    """Tests for GET /api/objective endpoint."""

    def test_get_objective_returns_current(self, client):
        """Test GET returns the current objective."""
        mock_objective = MagicMock()
        mock_objective.id = 1
        mock_objective.current_text = "Test objective"
        mock_objective.constraints = "Test constraints"
        mock_objective.set_at = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = mock_objective

            response = client.get("/api/objective")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["id"] == 1
            assert data["current_text"] == "Test objective"
            assert data["constraints"] == "Test constraints"
            assert data["set_at"] is not None

    def test_get_objective_when_none_exists(self, client):
        """Test GET returns appropriate response when no objective exists."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None

            response = client.get("/api/objective")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "message" in data
            assert data["message"] == "No objective set"


class TestUpdateObjectiveAPI:
    """Tests for POST /api/objective endpoint."""

    def test_create_new_objective(self, client):
        """Test creating a new objective when none exists."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None

            # Mock the Objective class
            with patch("claude_headspace.routes.objective.Objective") as MockObjective:
                mock_new_objective = MagicMock()
                mock_new_objective.id = 1
                mock_new_objective.current_text = "New objective"
                mock_new_objective.constraints = None
                mock_new_objective.set_at = datetime.now(timezone.utc)
                MockObjective.return_value = mock_new_objective

                with patch("claude_headspace.routes.objective.ObjectiveHistory"):
                    response = client.post(
                        "/api/objective",
                        data=json.dumps({"text": "New objective"}),
                        content_type="application/json"
                    )

                    assert response.status_code == 200
                    mock_db.session.add.assert_called()
                    mock_db.session.commit.assert_called()

    def test_update_existing_objective(self, client):
        """Test updating an existing objective."""
        mock_objective = MagicMock()
        mock_objective.id = 1
        mock_objective.current_text = "Old objective"
        mock_objective.constraints = None
        mock_objective.set_at = datetime.now(timezone.utc)

        mock_history = MagicMock()
        mock_history.ended_at = None

        with patch("claude_headspace.routes.objective.db") as mock_db:
            # First query returns the existing objective
            mock_db.session.query.return_value.first.return_value = mock_objective
            # Second query for history returns open history
            mock_db.session.query.return_value.filter.return_value.first.return_value = mock_history

            with patch("claude_headspace.routes.objective.ObjectiveHistory"):
                response = client.post(
                    "/api/objective",
                    data=json.dumps({"text": "Updated objective", "constraints": "New constraints"}),
                    content_type="application/json"
                )

                assert response.status_code == 200
                assert mock_objective.current_text == "Updated objective"
                assert mock_objective.constraints == "New constraints"
                mock_db.session.commit.assert_called()

    def test_update_objective_closes_previous_history(self, client):
        """Test that updating an objective sets ended_at on previous history."""
        mock_objective = MagicMock()
        mock_objective.id = 1

        mock_history = MagicMock()
        mock_history.ended_at = None

        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = mock_objective
            mock_db.session.query.return_value.filter.return_value.first.return_value = mock_history

            with patch("claude_headspace.routes.objective.ObjectiveHistory"):
                response = client.post(
                    "/api/objective",
                    data=json.dumps({"text": "New objective"}),
                    content_type="application/json"
                )

                assert response.status_code == 200
                # Verify ended_at was set on the history
                assert mock_history.ended_at is not None

    def test_update_objective_validation_empty_text(self, client):
        """Test that empty objective text returns validation error."""
        response = client.post(
            "/api/objective",
            data=json.dumps({"text": ""}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data
        assert "required" in data["error"].lower()

    def test_update_objective_validation_whitespace_text(self, client):
        """Test that whitespace-only objective text returns validation error."""
        response = client.post(
            "/api/objective",
            data=json.dumps({"text": "   "}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_update_objective_validation_missing_text(self, client):
        """Test that missing text field returns validation error."""
        response = client.post(
            "/api/objective",
            data=json.dumps({"constraints": "Some constraints"}),
            content_type="application/json"
        )

        assert response.status_code == 400
        data = json.loads(response.data)
        assert "error" in data

    def test_update_objective_non_json_body(self, client):
        """Test that non-JSON body returns error."""
        response = client.post(
            "/api/objective",
            data="not json",
            content_type="text/plain"
        )

        # Flask returns 415 Unsupported Media Type for wrong content-type
        assert response.status_code == 415

    def test_update_objective_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.commit.side_effect = Exception("DB error")

            with patch("claude_headspace.routes.objective.Objective"):
                with patch("claude_headspace.routes.objective.ObjectiveHistory"):
                    response = client.post(
                        "/api/objective",
                        data=json.dumps({"text": "Test"}),
                        content_type="application/json"
                    )

                    assert response.status_code == 500
                    mock_db.session.rollback.assert_called()


class TestGetObjectiveHistoryAPI:
    """Tests for GET /api/objective/history endpoint."""

    def test_get_history_returns_paginated_results(self, client):
        """Test GET returns paginated history items."""
        mock_items = []
        for i in range(5):
            item = MagicMock()
            item.id = i + 1
            item.text = f"Objective {i}"
            item.constraints = None
            item.started_at = datetime(2024, 1, i + 1, tzinfo=timezone.utc)
            item.ended_at = datetime(2024, 1, i + 2, tzinfo=timezone.utc) if i < 4 else None
            mock_items.append(item)

        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.count.return_value = 5
            mock_db.session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = mock_items

            response = client.get("/api/objective/history")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert "items" in data
            assert len(data["items"]) == 5
            assert data["page"] == 1
            assert data["per_page"] == 10
            assert data["total"] == 5

    def test_get_history_with_custom_page(self, client):
        """Test GET with custom page parameter."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.count.return_value = 25
            mock_db.session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = client.get("/api/objective/history?page=2")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["page"] == 2

    def test_get_history_with_custom_per_page(self, client):
        """Test GET with custom per_page parameter."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.count.return_value = 25
            mock_db.session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = client.get("/api/objective/history?per_page=5")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["per_page"] == 5

    def test_get_history_per_page_max_limit(self, client):
        """Test that per_page is capped at 100."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.count.return_value = 200
            mock_db.session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = client.get("/api/objective/history?per_page=500")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["per_page"] == 100

    def test_get_history_invalid_page(self, client):
        """Test that invalid page defaults to 1."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.count.return_value = 10
            mock_db.session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = client.get("/api/objective/history?page=-1")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["page"] == 1

    def test_get_history_empty(self, client):
        """Test GET returns empty list when no history exists."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.count.return_value = 0
            mock_db.session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = client.get("/api/objective/history")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["items"] == []
            assert data["total"] == 0
            assert data["pages"] == 0

    def test_get_history_calculates_pages_correctly(self, client):
        """Test that total pages is calculated correctly."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.count.return_value = 25
            mock_db.session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

            response = client.get("/api/objective/history?per_page=10")
            assert response.status_code == 200

            data = json.loads(response.data)
            assert data["pages"] == 3  # 25 items / 10 per page = 3 pages

    def test_get_history_database_error(self, client):
        """Test that database error returns 500."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.side_effect = Exception("DB error")

            response = client.get("/api/objective/history")
            assert response.status_code == 500

            data = json.loads(response.data)
            assert "error" in data


class TestObjectiveNavigation:
    """Tests for objective tab navigation."""

    def test_header_has_objective_link(self, client):
        """Test that the dashboard header has the objective link."""
        with patch("claude_headspace.routes.dashboard.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.all.return_value = []

            response = client.get("/")
            assert response.status_code == 200
            assert b'href="/objective"' in response.data

    def test_objective_link_is_active_on_objective_page(self, client):
        """Test that the objective link is marked active on the objective page."""
        with patch("claude_headspace.routes.objective.db") as mock_db:
            mock_db.session.query.return_value.first.return_value = None
            mock_db.session.query.return_value.order_by.return_value.limit.return_value.all.return_value = []
            mock_db.session.query.return_value.count.return_value = 0

            response = client.get("/objective")
            assert response.status_code == 200
            # Check that objective link has aria-current="page"
            assert b'aria-current="page"' in response.data
