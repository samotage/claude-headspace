"""Pytest fixtures for Claude Headspace tests."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from claude_headspace.app import create_app


@pytest.fixture
def temp_config():
    """Create a temporary config file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        config = {
            "server": {
                "host": "127.0.0.1",
                "port": 5050,
                "debug": False,
            },
            "logging": {
                "level": "DEBUG",
                "file": "logs/test.log",
            },
        }
        yaml.dump(config, f)
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def app(temp_config):
    """Create a Flask application for testing."""
    # Change to a temp directory that has templates
    original_cwd = os.getcwd()

    # Use the actual project root for templates
    project_root = Path(__file__).parent.parent
    os.chdir(project_root)

    app = create_app(config_path=str(project_root / "config.yaml"))
    app.config.update({
        "TESTING": True,
    })

    yield app

    os.chdir(original_cwd)


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


@pytest.fixture
def runner(app):
    """Create a test CLI runner."""
    return app.test_cli_runner()
