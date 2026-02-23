"""Tests for resolve_persona_slug() short-name matching in launcher."""

from unittest.mock import MagicMock, patch

import pytest

from src.claude_headspace.cli.launcher import resolve_persona_slug


class TestResolvePersonaSlug:
    """Tests for resolve_persona_slug() short-name resolution."""

    def _mock_response(self, status_code, json_data):
        """Create a mock requests response."""
        mock = MagicMock()
        mock.status_code = status_code
        mock.json.return_value = json_data
        return mock

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_single_match_returns_slug(self, mock_get):
        """Single matching persona returns its slug directly."""
        mock_get.return_value = self._mock_response(200, [
            {"name": "Con", "slug": "developer-con-1", "status": "active", "role": "developer"},
            {"name": "Robbo", "slug": "developer-robbo-2", "status": "active", "role": "developer"},
        ])

        slug, error = resolve_persona_slug("https://test:5055", "con")

        assert slug == "developer-con-1"
        assert error is None

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_case_insensitive_matching(self, mock_get):
        """Matching is case-insensitive."""
        mock_get.return_value = self._mock_response(200, [
            {"name": "Con", "slug": "developer-con-1", "status": "active", "role": "developer"},
        ])

        slug, error = resolve_persona_slug("https://test:5055", "CON")

        assert slug == "developer-con-1"
        assert error is None

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_substring_matching(self, mock_get):
        """Partial name matches via substring."""
        mock_get.return_value = self._mock_response(200, [
            {"name": "Constantine", "slug": "developer-constantine-1", "status": "active", "role": "developer"},
            {"name": "Robbo", "slug": "developer-robbo-2", "status": "active", "role": "developer"},
        ])

        slug, error = resolve_persona_slug("https://test:5055", "const")

        assert slug == "developer-constantine-1"
        assert error is None

    @patch("src.claude_headspace.cli.launcher.requests.get")
    @patch("click.prompt", return_value=2)
    def test_multiple_matches_disambiguation(self, mock_prompt, mock_get):
        """Multiple matches present disambiguation prompt."""
        mock_get.return_value = self._mock_response(200, [
            {"name": "Con", "slug": "developer-con-1", "status": "active", "role": "developer"},
            {"name": "Connie", "slug": "tester-connie-3", "status": "active", "role": "tester"},
        ])

        slug, error = resolve_persona_slug("https://test:5055", "con")

        assert slug == "tester-connie-3"
        assert error is None
        mock_prompt.assert_called_once()

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_no_match_returns_error(self, mock_get):
        """No matches return an error message."""
        mock_get.return_value = self._mock_response(200, [
            {"name": "Con", "slug": "developer-con-1", "status": "active", "role": "developer"},
        ])

        slug, error = resolve_persona_slug("https://test:5055", "xyz")

        assert slug is None
        assert "No persona matching 'xyz'" in error

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_only_active_personas_matched(self, mock_get):
        """Only active personas are matched (archived excluded)."""
        mock_get.return_value = self._mock_response(200, [
            {"name": "Con", "slug": "developer-con-1", "status": "archived", "role": "developer"},
            {"name": "Robbo", "slug": "developer-robbo-2", "status": "active", "role": "developer"},
        ])

        slug, error = resolve_persona_slug("https://test:5055", "con")

        assert slug is None
        assert "No persona matching 'con'" in error

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_connection_error(self, mock_get):
        """Connection error returns descriptive error."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError()

        slug, error = resolve_persona_slug("https://test:5055", "con")

        assert slug is None
        assert "Cannot connect" in error

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_server_error_status(self, mock_get):
        """Non-200 status returns error."""
        mock_get.return_value = self._mock_response(500, {"error": "Internal error"})

        slug, error = resolve_persona_slug("https://test:5055", "con")

        assert slug is None
        assert "status 500" in error

    @patch("src.claude_headspace.cli.launcher.requests.get")
    def test_empty_personas_list(self, mock_get):
        """Empty persona list returns error."""
        mock_get.return_value = self._mock_response(200, [])

        slug, error = resolve_persona_slug("https://test:5055", "con")

        assert slug is None
        assert "No persona matching 'con'" in error
