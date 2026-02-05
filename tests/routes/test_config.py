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
def app(tmp_path):
    """Create a test Flask application."""
    app = Flask(__name__)
    app.register_blueprint(config_bp)
    app.config["TESTING"] = True
    app.config["APP_ROOT"] = str(tmp_path)
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

    @patch("src.claude_headspace.routes.config.load_config_file")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.get_config_schema")
    @patch("src.claude_headspace.routes.config.render_template")
    def test_config_page_passes_inference_available_true(self, mock_render, mock_schema, mock_merge, mock_load, client, app):
        """Config page should pass inference_available=True when inference service is registered."""
        mock_load.return_value = {}
        mock_merge.return_value = {"server": {"port": 5050}}
        mock_schema.return_value = [{"name": "server", "title": "Server", "fields": []}]
        mock_render.return_value = "<html>Config Page</html>"

        with app.app_context():
            app.extensions["inference_service"] = MagicMock()
            response = client.get("/config")
            assert response.status_code == 200
            call_kwargs = mock_render.call_args[1]
            assert call_kwargs.get("inference_available") is True

    @patch("src.claude_headspace.routes.config.load_config_file")
    @patch("src.claude_headspace.routes.config.merge_with_defaults")
    @patch("src.claude_headspace.routes.config.get_config_schema")
    @patch("src.claude_headspace.routes.config.render_template")
    def test_config_page_passes_inference_available_false(self, mock_render, mock_schema, mock_merge, mock_load, client, app):
        """Config page should pass inference_available=False when inference service is not registered."""
        mock_load.return_value = {}
        mock_merge.return_value = {"server": {"port": 5050}}
        mock_schema.return_value = [{"name": "server", "title": "Server", "fields": []}]
        mock_render.return_value = "<html>Config Page</html>"

        with app.app_context():
            # Ensure no inference service
            app.extensions.pop("inference_service", None)
            response = client.get("/config")
            assert response.status_code == 200
            call_kwargs = mock_render.call_args[1]
            assert call_kwargs.get("inference_available") is False


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

    def test_save_config_requires_confirm_header(self, client):
        """Should reject requests without X-Confirm-Destructive header."""
        response = client.post("/api/config", data="not json")

        assert response.status_code == 403
        data = response.get_json()
        assert "X-Confirm-Destructive" in data["message"]

    def test_save_config_requires_json(self, client):
        """Should require JSON content type."""
        response = client.post(
            "/api/config",
            data="not json",
            headers={"X-Confirm-Destructive": "true"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert "application/json" in data["message"]

    def test_save_config_requires_valid_json(self, client):
        """Should require valid JSON payload."""
        response = client.post(
            "/api/config",
            data="invalid json",
            content_type="application/json",
            headers={"X-Confirm-Destructive": "true"},
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
            headers={"X-Confirm-Destructive": "true"},
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
            headers={"X-Confirm-Destructive": "true"},
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
            headers={"X-Confirm-Destructive": "true"},
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
            headers={"X-Confirm-Destructive": "true"},
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
            headers={"X-Confirm-Destructive": "true"},
        )

        data = response.get_json()
        error = data["errors"][0]
        assert error["section"] == "server"
        assert error["field"] == "port"
        assert error["message"] == "must be an integer"


class TestRestartServer:
    """Tests for POST /api/config/restart."""

    def test_restart_requires_confirm_header(self, client, app):
        """Should reject requests without X-Confirm-Destructive header."""
        with app.app_context():
            response = client.post("/api/config/restart")

        assert response.status_code == 403
        data = response.get_json()
        assert "X-Confirm-Destructive" in data["message"]

    @patch("src.claude_headspace.routes.config.subprocess.Popen")
    def test_restart_success(self, mock_popen, client, app, tmp_path):
        """Should launch restart_server.sh and return 200."""
        # Create the script file so the endpoint finds it
        script = tmp_path / "restart_server.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(0o755)

        with app.app_context():
            response = client.post(
                "/api/config/restart",
                headers={"X-Confirm-Destructive": "true"},
            )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        assert "Restart initiated" in data["message"]
        mock_popen.assert_called_once()

    def test_restart_script_not_found(self, client, app, tmp_path):
        """Should return 500 when restart_server.sh doesn't exist."""
        # tmp_path has no script file
        with app.app_context():
            response = client.post(
                "/api/config/restart",
                headers={"X-Confirm-Destructive": "true"},
            )

        assert response.status_code == 500
        data = response.get_json()
        assert data["status"] == "error"
        assert "not found" in data["message"]

    @patch("src.claude_headspace.routes.config.subprocess.Popen")
    def test_restart_handles_popen_error(self, mock_popen, client, app, tmp_path):
        """Should return 500 when Popen raises OSError."""
        script = tmp_path / "restart_server.sh"
        script.write_text("#!/bin/bash\nexit 0\n")
        script.chmod(0o755)

        mock_popen.side_effect = OSError("Permission denied")

        with app.app_context():
            response = client.post(
                "/api/config/restart",
                headers={"X-Confirm-Destructive": "true"},
            )

        assert response.status_code == 500
        data = response.get_json()
        assert data["status"] == "error"
        assert "Permission denied" in data["message"]
