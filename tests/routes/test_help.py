"""Tests for help API routes."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from flask import Flask

from src.claude_headspace.routes.help import help_bp, extract_excerpt, extract_title


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(help_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def temp_help_dir():
    """Create temporary help directory with test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        help_dir = Path(tmpdir) / "docs" / "help"
        help_dir.mkdir(parents=True)

        # Create test files
        (help_dir / "index.md").write_text("# Help Overview\n\nWelcome to help.")
        (help_dir / "getting-started.md").write_text("# Getting Started\n\nQuick start guide.")
        (help_dir / "dashboard.md").write_text("# Dashboard\n\nDashboard overview.")

        yield help_dir


class TestListTopics:
    """Tests for GET /api/help/topics."""

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_returns_topics_list(self, mock_get_dir, client, temp_help_dir):
        """Should return list of topics."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/topics")

        assert response.status_code == 200
        data = response.get_json()
        assert "topics" in data
        assert len(data["topics"]) > 0

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_topics_have_required_fields(self, mock_get_dir, client, temp_help_dir):
        """Should return topics with slug, title, excerpt."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/topics")

        data = response.get_json()
        for topic in data["topics"]:
            assert "slug" in topic
            assert "title" in topic
            assert "excerpt" in topic

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_extracts_title_from_content(self, mock_get_dir, client, temp_help_dir):
        """Should extract title from markdown h1."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/topics")

        data = response.get_json()
        index_topic = next(t for t in data["topics"] if t["slug"] == "index")
        assert index_topic["title"] == "Help Overview"


class TestGetTopic:
    """Tests for GET /api/help/topics/<slug>."""

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_returns_topic_content(self, mock_get_dir, client, temp_help_dir):
        """Should return topic content."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/topics/index")

        assert response.status_code == 200
        data = response.get_json()
        assert data["slug"] == "index"
        assert "Help Overview" in data["content"]

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_returns_404_for_unknown_topic(self, mock_get_dir, client, temp_help_dir):
        """Should return 404 for unknown topic."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/topics/nonexistent")

        assert response.status_code == 404
        data = response.get_json()
        assert data["error"] == "not_found"

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_returns_400_for_invalid_slug(self, mock_get_dir, client, temp_help_dir):
        """Should return 400 for invalid slug with special characters."""
        mock_get_dir.return_value = temp_help_dir

        # Use uppercase letters which are invalid per the regex
        response = client.get("/api/help/topics/INVALID")

        assert response.status_code == 400
        data = response.get_json()
        assert data["error"] == "invalid_slug"

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_includes_title_in_response(self, mock_get_dir, client, temp_help_dir):
        """Should include extracted title in response."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/topics/dashboard")

        data = response.get_json()
        assert data["title"] == "Dashboard"


class TestSearchIndex:
    """Tests for GET /api/help/search."""

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_returns_search_index(self, mock_get_dir, client, temp_help_dir):
        """Should return all topics with content for indexing."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/search")

        assert response.status_code == 200
        data = response.get_json()
        assert "topics" in data
        assert len(data["topics"]) > 0

    @patch("src.claude_headspace.routes.help.get_help_dir")
    def test_index_includes_full_content(self, mock_get_dir, client, temp_help_dir):
        """Should include full content for search indexing."""
        mock_get_dir.return_value = temp_help_dir

        response = client.get("/api/help/search")

        data = response.get_json()
        for topic in data["topics"]:
            assert "content" in topic
            assert len(topic["content"]) > 0


class TestExtractExcerpt:
    """Tests for excerpt extraction."""

    def test_removes_headers(self):
        """Should remove markdown headers."""
        content = "# Header\n\nSome text here."
        excerpt = extract_excerpt(content)
        assert "Header" not in excerpt
        assert "Some text" in excerpt

    def test_removes_links(self):
        """Should convert links to plain text."""
        content = "Check [this link](http://example.com) out."
        excerpt = extract_excerpt(content)
        assert "[" not in excerpt
        assert "this link" in excerpt

    def test_truncates_long_content(self):
        """Should truncate content over max length."""
        content = "A" * 200
        excerpt = extract_excerpt(content, max_length=100)
        assert len(excerpt) <= 103  # 100 + "..."

    def test_removes_code_blocks(self):
        """Should remove code blocks."""
        content = "Before ```code here``` after"
        excerpt = extract_excerpt(content)
        assert "code here" not in excerpt


class TestExtractTitle:
    """Tests for title extraction."""

    def test_extracts_h1_title(self):
        """Should extract h1 heading as title."""
        content = "# My Title\n\nSome content."
        title = extract_title(content, "Default")
        assert title == "My Title"

    def test_returns_default_if_no_h1(self):
        """Should return default if no h1 found."""
        content = "Some content without a title."
        title = extract_title(content, "Default Title")
        assert title == "Default Title"

    def test_uses_first_h1(self):
        """Should use first h1 if multiple exist."""
        content = "# First Title\n\n# Second Title"
        title = extract_title(content, "Default")
        assert title == "First Title"
