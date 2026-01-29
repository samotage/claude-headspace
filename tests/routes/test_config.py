"""Tests for config API routes."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from flask import Flask

from src.claude_headspace.routes.config import config_bp


@pytest.fixture
def app():
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(config_bp)
    app.config["TESTING"] = True
    return app


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


class TestConfigPage:
    """Tests for GET /config (HTML page)."""

    @patch("src.claude_headspace.routes.config.load_config_file")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.get_config_schema")
    @patch("src.claude_headspace.routes.config.render_template")
    def test_config_page_returns_html(self, mock_render, mock_schema, mock_merge, mock_load, client, app):
        """Config page should return HTML."""
        mock_load.return_value = {}
        mock_merge.return_value = {"server": {"port": 5050}}
        mock_schema.return_value = [{"name": "server", "title": "Server", "fields": []}]
        mock_render.return_value = "<html>Config Page</html>"

        with app.app_context():
            response = client.get("/config")
            assert response.status_code == 200
            mock_render.assert_called_once()


class TestGetConfigAPI:
    """Tests for GET /api/config."""

    @patch("src.claude_headspace.routes.config.load_config_file")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.get_config_schema")
    def test_get_config_returns_json(self, mock_schema, mock_merge, mock_load, client):
        """GET /api/config should return JSON."""
        mock_load.return_value = {}
        mock_merge.return_value = {"server": {"port": 5050}}
        mock_schema.return_value = [{"name": "server", "title": "Server", "fields": []}]

        response = client.get("/api/config")

        assert response.status_code == 200
        assert response.content_type == "application/json"

    @patch("src.claude_headspace.routes.config.load_config_file")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.get_config_schema")
    def test_get_config_has_expected_fields(self, mock_schema, mock_merge, mock_load, client):
        """Response should have status, config, and schema."""
        mock_load.return_value = {}
        mock_merge.return_value = {"server": {"port": 5050}}
        mock_schema.return_value = [{"name": "server", "title": "Server", "fields": []}]

        response = client.get("/api/config")
        data = response.get_json()

        assert data["status"] == "ok"
        assert "config" in data
        assert "schema" in data

    @patch("src.claude_headspace.routes.config.load_config_file")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.get_config_schema")
    def test_get_config_returns_merged_config(self, mock_schema, mock_merge, mock_load, client):
        """Should return config with defaults merged."""
        mock_load.return_value = {"server": {"port": 9000}}
        mock_merge.return_value = {"server": {"port": 9000, "host": "127.0.0.1"}}
        mock_schema.return_value = []

        response = client.get("/api/config")
        data = response.get_json()

        assert data["config"]["server"]["port"] == 9000
        assert data["config"]["server"]["host"] == "127.0.0.1"

    @patch("src.claude_headspace.routes.config.load_config_file")
    def test_get_config_handles_error(self, mock_load, client):
        """Should return 500 on error."""
        mock_load.side_effect = Exception("File error")

        response = client.get("/api/config")

        assert response.status_code == 500
        data = response.get_json()
        assert data["status"] == "error"


class TestSaveConfigAPI:
    """Tests for POST /api/config."""

    def test_save_config_requires_json(self, client):
        """Should require JSON content type."""
        response = client.post("/api/config", data="not json")

        assert response.status_code == 400
        data = response.get_json()
        assert "application/json" in data["message"]

    def test_save_config_requires_valid_json(self, client):
        """Should require valid JSON payload."""
        response = client.post(
            "/api/config",
            data="invalid json",
            content_type="application/json",
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "Invalid JSON" in data["message"]

    @patch("src.claude_headspace.routes.config.validate_config")
    def test_save_config_validates_payload(self, mock_validate, client):
        """Should validate configuration before saving."""
        from claude_headspace.services.config_editor import ValidationError, ValidationResult

        mock_validate.return_value = ValidationResult(
            valid=False,
            errors=[ValidationError("server", "port", "must be an integer")],
        )

        response = client.post(
            "/api/config",
            json={"server": {"port": "abc"}},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["status"] == "error"
        assert "errors" in data
        assert data["errors"][0]["field"] == "port"

    @patch("src.claude_headspace.routes.config.validate_config")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.save_config_file")
    def test_save_config_success(self, mock_save, mock_merge, mock_validate, client):
        """Should save valid configuration."""
        from claude_headspace.services.config_editor import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, errors=[])
        mock_merge.return_value = {"server": {"port": 5050}}
        mock_save.return_value = (True, None)

        response = client.post(
            "/api/config",
            json={"server": {"port": 5050}},
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert data["message"] == "Configuration saved"
        assert data["requires_restart"] is True

    @patch("src.claude_headspace.routes.config.validate_config")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.save_config_file")
    def test_save_config_handles_save_error(self, mock_save, mock_merge, mock_validate, client):
        """Should return 500 when save fails."""
        from claude_headspace.services.config_editor import ValidationResult

        mock_validate.return_value = ValidationResult(valid=True, errors=[])
        mock_merge.return_value = {"server": {"port": 5050}}
        mock_save.return_value = (False, "Permission denied")

        response = client.post(
            "/api/config",
            json={"server": {"port": 5050}},
        )

        assert response.status_code == 500
        data = response.get_json()
        assert data["status"] == "error"
        assert "Permission denied" in data["message"]


class TestValidationErrorResponse:
    """Tests for validation error response format."""

    @patch("src.claude_headspace.routes.config.validate_config")
    def test_multiple_validation_errors(self, mock_validate, client):
        """Should return all validation errors."""
        from claude_headspace.services.config_editor import ValidationError, ValidationResult

        mock_validate.return_value = ValidationResult(
            valid=False,
            errors=[
                ValidationError("server", "port", "must be an integer"),
                ValidationError("server", "host", "is required"),
                ValidationError("database", "pool_size", "must be at least 1"),
            ],
        )

        response = client.post(
            "/api/config",
            json={"server": {"port": "abc"}},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert len(data["errors"]) == 3

    @patch("src.claude_headspace.routes.config.validate_config")
    def test_error_format(self, mock_validate, client):
        """Each error should have section, field, message."""
        from claude_headspace.services.config_editor import ValidationError, ValidationResult

        mock_validate.return_value = ValidationResult(
            valid=False,
            errors=[ValidationError("server", "port", "must be an integer")],
        )

        response = client.post(
            "/api/config",
            json={"server": {"port": "abc"}},
        )

        data = response.get_json()
        error = data["errors"][0]
        assert error["section"] == "server"
        assert error["field"] == "port"
        assert error["message"] == "must be an integer"
