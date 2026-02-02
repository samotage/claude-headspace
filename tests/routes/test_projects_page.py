"""Tests for the projects page route."""

import pytest


class TestProjectsPage:
    """Test GET /projects page route."""

    def test_projects_page_returns_200(self, client):
        """GET /projects returns 200 with projects template."""
        response = client.get("/projects")
        assert response.status_code == 200

    def test_projects_page_contains_expected_content(self, client):
        """GET /projects renders page with key UI elements."""
        response = client.get("/projects")
        html = response.data.decode("utf-8")

        assert "projects-table" in html
        assert "Add Project" in html
        assert "projects.js" in html

    def test_projects_page_includes_status_counts(self, client):
        """GET /projects provides status_counts context for header stats bar."""
        response = client.get("/projects")
        html = response.data.decode("utf-8")

        # status_counts are rendered in the header stats bar
        assert "[0]" in html  # Default zero counts rendered
