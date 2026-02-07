"""Pytest fixtures for Claude Headspace tests."""

import os
from pathlib import Path

import pytest

from claude_headspace.app import create_app
from claude_headspace.config import load_config


# ---------------------------------------------------------------------------
# Production database safety guard (session-scoped, autouse)
# ---------------------------------------------------------------------------

_PROJECT_ROOT = Path(__file__).parent.parent


def _build_test_database_url() -> str:
    """Build the test database URL from config, appending '_test' suffix."""
    env_url = os.environ.get("TEST_DATABASE_URL")
    if env_url:
        return env_url

    config = load_config(str(_PROJECT_ROOT / "config.yaml"))
    db_config = config.get("database", {})
    host = db_config.get("host", "localhost")
    port = db_config.get("port", 5432)
    user = db_config.get("user", "postgres")
    password = db_config.get("password", "")
    name = db_config.get("name", "claude_headspace") + "_test"

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    return f"postgresql://{user}@{host}:{port}/{name}"


@pytest.fixture(scope="session", autouse=True)
def _force_test_database():
    """Force ALL tests to use the test database. Never connect to production.

    This is a session-scoped autouse fixture that sets DATABASE_URL before any
    test or fixture can create a Flask app. It prevents any test from
    accidentally connecting to the production database.
    """
    test_url = _build_test_database_url()
    original = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url

    yield

    # Restore original (or remove if it wasn't set)
    if original is not None:
        os.environ["DATABASE_URL"] = original
    else:
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture
def app():
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
