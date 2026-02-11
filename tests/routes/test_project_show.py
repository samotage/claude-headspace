"""Tests for the project show page route and slug functionality."""

import os
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask

from src.claude_headspace.routes.projects import projects_bp
from src.claude_headspace.models.project import generate_slug

# Resolve template folder relative to the project root
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_TEMPLATE_DIR = os.path.join(_PROJECT_ROOT, "templates")


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__, template_folder=_TEMPLATE_DIR)
    app.register_blueprint(projects_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def mock_db():
    """Mock database session."""
    with patch("src.claude_headspace.routes.projects.db") as mock:
        mock.session = MagicMock()
        # Configure query chain to return sensible defaults for counts/lists
        mock_query = mock.session.query.return_value
        mock_query.filter.return_value = mock_query
        mock_query.filter_by.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.options.return_value = mock_query
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.count.return_value = 0
        mock_query.all.return_value = []
        mock_query.join.return_value = mock_query
        mock_query.group_by.return_value = mock_query
        yield mock


@pytest.fixture
def mock_project():
    """Create a mock project with slug."""
    project = MagicMock()
    project.id = 1
    project.name = "test-project"
    project.slug = "test-project"
    project.path = "/path/to/project"
    project.github_repo = "https://github.com/test/repo"
    project.description = "A test project"
    project.current_branch = "main"
    project.inference_paused = False
    project.inference_paused_at = None
    project.inference_paused_reason = None
    project.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    project.agents = []
    return project


class TestGenerateSlug:
    """Tests for the generate_slug utility function."""

    def test_basic_slug(self):
        """Test basic slug generation from a simple name."""
        assert generate_slug("My Project") == "my-project"

    def test_special_characters(self):
        """Test slug generation strips special characters."""
        assert generate_slug("My Project!!") == "my-project"

    def test_multiple_spaces(self):
        """Test slug collapses multiple spaces/hyphens."""
        assert generate_slug("My   Cool   Project") == "my-cool-project"

    def test_leading_trailing_hyphens(self):
        """Test slug strips leading/trailing hyphens."""
        assert generate_slug("--my-project--") == "my-project"

    def test_uppercase(self):
        """Test slug is lowercase."""
        assert generate_slug("MY PROJECT") == "my-project"

    def test_numbers(self):
        """Test slug preserves numbers."""
        assert generate_slug("Project 42") == "project-42"

    def test_all_special_characters(self):
        """Test slug with only special characters returns fallback."""
        assert generate_slug("!!!") == "project"

    def test_empty_string(self):
        """Test slug with empty string returns fallback."""
        assert generate_slug("") == "project"

    def test_already_slug(self):
        """Test slug generation is idempotent for valid slugs."""
        assert generate_slug("my-project") == "my-project"

    def test_dots_and_underscores(self):
        """Test slug replaces dots and underscores with hyphens."""
        assert generate_slug("my.project_name") == "my-project-name"


class TestProjectShowRoute:
    """Tests for GET /projects/<slug>."""

    def test_show_page_returns_200(self, client, mock_db, mock_project):
        """Test show page returns 200 for valid slug."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject, \
             patch("src.claude_headspace.routes.projects.render_template", return_value="ok") as mock_render:
            MockProject.query.filter_by.return_value.first.return_value = mock_project

            response = client.get("/projects/test-project")
            assert response.status_code == 200
            mock_render.assert_called_once()
            call_args = mock_render.call_args
            assert call_args[0][0] == "project_show.html"
            assert call_args[1]["project"] == mock_project

    def test_show_page_returns_404_for_invalid_slug(self, client, mock_db):
        """Test show page returns 404 for invalid slug."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject, \
             patch("src.claude_headspace.routes.projects.render_template", return_value="not found") as mock_render:
            MockProject.query.filter_by.return_value.first.return_value = None

            response = client.get("/projects/nonexistent-slug")
            assert response.status_code == 404
            mock_render.assert_called_once()
            call_args = mock_render.call_args
            assert call_args[0][0] == "404.html"


class TestSlugInApiResponses:
    """Tests for slug field in API responses."""

    def test_list_includes_slug(self, client, mock_db, mock_project):
        """Test that list response includes slug field."""
        mock_db.session.query.return_value.options.return_value.order_by.return_value.all.return_value = [mock_project]

        response = client.get("/api/projects")
        data = response.get_json()
        assert len(data) == 1
        assert "slug" in data[0]
        assert data[0]["slug"] == "test-project"

    def test_get_includes_slug(self, client, mock_db, mock_project):
        """Test that get response includes slug field."""
        mock_db.session.get.return_value = mock_project

        response = client.get("/api/projects/1")
        data = response.get_json()
        assert "slug" in data
        assert data["slug"] == "test-project"

    def test_create_includes_slug(self, client, mock_db):
        """Test that create response includes slug field."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.return_value = None

            mock_project = MagicMock()
            mock_project.id = 1
            mock_project.name = "new-project"
            mock_project.slug = "new-project"
            mock_project.path = "/path/to/new"
            mock_project.github_repo = None
            mock_project.description = None
            mock_project.inference_paused = False
            mock_project.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
            MockProject.return_value = mock_project

            response = client.post("/api/projects", json={
                "name": "new-project",
                "path": "/path/to/new",
            })

            assert response.status_code == 201
            data = response.get_json()
            assert "slug" in data

    def test_update_includes_slug(self, client, mock_db, mock_project):
        """Test that update response includes slug field."""
        mock_db.session.get.return_value = mock_project

        response = client.put("/api/projects/1", json={"description": "Updated"})
        data = response.get_json()
        assert "slug" in data
        assert data["slug"] == "test-project"


class TestSlugRegeneration:
    """Tests for slug regeneration on name update."""

    def test_slug_updates_on_name_change(self, client, mock_db, mock_project):
        """Test that updating name regenerates slug."""
        mock_db.session.get.return_value = mock_project

        with patch("src.claude_headspace.routes.projects._unique_slug", return_value="updated-name") as mock_unique:
            response = client.put("/api/projects/1", json={"name": "Updated Name"})
            assert response.status_code == 200
            mock_unique.assert_called_once_with("Updated Name", exclude_id=1)

    def test_slug_not_updated_when_name_unchanged(self, client, mock_db, mock_project):
        """Test that slug is not regenerated when name hasn't changed."""
        mock_db.session.get.return_value = mock_project

        with patch("src.claude_headspace.routes.projects._unique_slug") as mock_unique:
            response = client.put("/api/projects/1", json={"name": "test-project"})
            assert response.status_code == 200
            mock_unique.assert_not_called()


class TestUniqueSlug:
    """Tests for slug collision handling."""

    def test_unique_slug_no_collision(self, client, mock_db):
        """Test unique slug when no collision exists."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            MockProject.query.filter_by.return_value.first.return_value = None

            from src.claude_headspace.routes.projects import _unique_slug
            result = _unique_slug("My Project")
            assert result == "my-project"

    def test_unique_slug_with_collision(self, client, mock_db):
        """Test unique slug appends numeric suffix on collision."""
        with patch("src.claude_headspace.routes.projects.Project") as MockProject:
            existing = MagicMock()
            # First call (slug="my-project") returns existing, second call (slug="my-project-2") returns None
            MockProject.query.filter_by.return_value.filter.return_value.first.side_effect = [existing, None]
            MockProject.query.filter_by.return_value.first.side_effect = [existing, None]

            from src.claude_headspace.routes.projects import _unique_slug
            result = _unique_slug("My Project")
            assert result == "my-project-2"
