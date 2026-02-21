"""Tests for Flask application."""

import json
import os
import tempfile
import time
from pathlib import Path

import pytest
import yaml

from claude_headspace import __version__
from claude_headspace.app import create_app
from claude_headspace.config import load_config


class TestAppFactory:
    """Test application factory."""

    def test_create_app_returns_flask_app(self, app):
        """Test that create_app returns a Flask application instance."""
        assert app is not None
        assert hasattr(app, 'test_client')

    def test_app_has_health_blueprint(self, app):
        """Test that health blueprint is registered."""
        assert 'health' in app.blueprints

    def test_app_has_version_config(self, app):
        """Test that app version is configured."""
        assert app.config.get('APP_VERSION') == __version__


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_returns_200(self, client):
        """Test GET /health returns 200 status."""
        response = client.get('/health')
        assert response.status_code == 200

    def test_health_returns_json(self, client):
        """Test GET /health returns JSON content type."""
        response = client.get('/health')
        assert response.content_type == 'application/json'

    def test_health_response_has_status(self, client):
        """Test GET /health response has status field."""
        response = client.get('/health')
        data = json.loads(response.data)
        # Status can be 'healthy' (all systems up) or 'degraded' (database down)
        assert data['status'] in ['healthy', 'degraded']

    def test_health_response_has_version(self, client):
        """Test GET /health response has version field."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert 'version' in data
        assert data['version'] == __version__


class TestConfigLoading:
    """Test configuration loading."""

    def test_load_default_config(self):
        """Test loading config with defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({}, f)
            config = load_config(f.name)
        os.unlink(f.name)

        assert config['server']['host'] == '0.0.0.0'
        assert config['server']['port'] == 5055
        assert config['server']['debug'] is False

    def test_load_yaml_config(self):
        """Test loading config from YAML file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({'server': {'port': 8080}}, f)
            config = load_config(f.name)
        os.unlink(f.name)

        assert config['server']['port'] == 8080

    def test_env_override_port(self):
        """Test environment variable overrides config file."""
        original = os.environ.get('FLASK_SERVER_PORT')
        os.environ['FLASK_SERVER_PORT'] = '9000'
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({'server': {'port': 5050}}, f)
                config = load_config(f.name)
            os.unlink(f.name)
            assert config['server']['port'] == 9000
        finally:
            if original is None:
                del os.environ['FLASK_SERVER_PORT']
            else:
                os.environ['FLASK_SERVER_PORT'] = original

    def test_env_override_debug(self):
        """Test FLASK_DEBUG environment variable override."""
        original = os.environ.get('FLASK_DEBUG')
        os.environ['FLASK_DEBUG'] = 'true'
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({'server': {'debug': False}}, f)
                config = load_config(f.name)
            os.unlink(f.name)
            assert config['server']['debug'] is True
        finally:
            if original is None:
                del os.environ['FLASK_DEBUG']
            else:
                os.environ['FLASK_DEBUG'] = original


class TestErrorPages:
    """Test error page handlers."""

    def test_404_returns_404_status(self, client):
        """Test requesting nonexistent route returns 404."""
        response = client.get('/nonexistent-page')
        assert response.status_code == 404

    def test_404_returns_html(self, client):
        """Test 404 page returns HTML."""
        response = client.get('/nonexistent-page')
        assert 'text/html' in response.content_type

    def test_404_page_has_message(self, client):
        """Test 404 page contains error message."""
        response = client.get('/nonexistent-page')
        assert b'Page not found' in response.data or b'404' in response.data


class TestBaseTemplate:
    """Test base template rendering."""

    def test_404_has_dark_theme_classes(self, client):
        """Test error page uses dark theme classes."""
        response = client.get('/nonexistent-page')
        html = response.data.decode('utf-8')
        # Check for dark theme background class
        assert 'bg-void' in html or '--bg-void' in html or '#08080a' in html


class TestStartupPerformance:
    """Test application startup performance."""

    def test_startup_under_2_seconds(self):
        """Test application starts in under 2 seconds."""
        project_root = Path(__file__).parent.parent
        original_cwd = os.getcwd()
        os.chdir(project_root)

        try:
            start = time.time()
            app = create_app(config_path=str(project_root / "config.yaml"), testing=True)
            elapsed = time.time() - start
            assert elapsed < 2.0, f"Startup took {elapsed:.2f}s, expected < 2s"
        finally:
            os.chdir(original_cwd)
