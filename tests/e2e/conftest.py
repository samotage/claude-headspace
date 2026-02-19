"""E2E test fixtures: Flask server, browser, hook client, database cleanup.

Starts a real Flask server in a background thread, connects Playwright
to the dashboard, and provides a HookSimulator for firing lifecycle hooks.
"""

import os
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from werkzeug.serving import make_server

from .helpers.dashboard_assertions import DashboardAssertions
from .helpers.hook_simulator import HookSimulator
from .helpers.voice_assertions import VoiceAssertions


# ---------------------------------------------------------------------------
# Database URL helpers (reuses integration test pattern)
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent


def _get_test_database_url() -> str:
    """Build the E2E test database URL."""
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        return test_url

    from claude_headspace.config import load_config
    config = load_config(str(PROJECT_ROOT / "config.yaml"))
    db_config = config.get("database", {})
    host = db_config.get("host", "localhost")
    port = db_config.get("port", 5432)
    user = db_config.get("user", "postgres")
    password = db_config.get("password", "")
    name = db_config.get("name", "claude_headspace") + "_test"

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    return f"postgresql://{user}@{host}:{port}/{name}"


def _get_admin_url() -> str:
    parts = _get_test_database_url().rsplit("/", 1)
    return parts[0] + "/postgres"


def _get_test_db_name() -> str:
    return _get_test_database_url().rsplit("/", 1)[1]


# ---------------------------------------------------------------------------
# Session-scoped: test database creation
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def e2e_test_db():
    """Create and drop the E2E test database for the session."""
    admin_url = _get_admin_url()
    db_name = _get_test_db_name()
    test_url = _get_test_database_url()

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()

    yield test_url

    # Teardown
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            conn.execute(text(
                f"SELECT pg_terminate_backend(pg_stat_activity.pid) "
                f"FROM pg_stat_activity "
                f"WHERE pg_stat_activity.datname = '{db_name}' "
                f"AND pid <> pg_backend_pid()"
            ))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    finally:
        admin_engine.dispose()


# ---------------------------------------------------------------------------
# Session-scoped: Flask app + server
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def e2e_app(e2e_test_db):
    """Create a Flask app configured for E2E testing."""
    test_url = e2e_test_db

    # Set DATABASE_URL env var BEFORE create_app so init_database picks it up
    original_db_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = test_url

    from claude_headspace.app import create_app
    from claude_headspace.database import db

    app = create_app(config_path=str(PROJECT_ROOT / "config.yaml"))
    app.config["TESTING"] = True

    # Create tables in the test database and seed required data
    with app.app_context():
        from claude_headspace import models  # noqa: F401
        from claude_headspace.models.project import Project, generate_slug
        db.create_all()

        # Seed a project matching the working_directory used by hook_client
        project_path = str(PROJECT_ROOT)
        project_name = PROJECT_ROOT.name
        existing = db.session.query(Project).filter_by(path=project_path).first()
        if not existing:
            project = Project(
                name=project_name,
                slug=generate_slug(project_name),
                path=project_path,
            )
            db.session.add(project)
            db.session.commit()

    yield app

    # Restore original DATABASE_URL
    if original_db_url is not None:
        os.environ["DATABASE_URL"] = original_db_url
    else:
        os.environ.pop("DATABASE_URL", None)


@pytest.fixture(scope="session")
def e2e_server(e2e_app):
    """Start Flask in a background thread, yield the base URL."""
    server = make_server("127.0.0.1", 0, e2e_app, threaded=True)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    # Wait for server to be ready
    import requests
    for _ in range(50):
        try:
            resp = requests.get(f"{base_url}/health", timeout=1)
            if resp.status_code == 200:
                break
        except requests.ConnectionError:
            time.sleep(0.1)
    else:
        raise RuntimeError("E2E server failed to start")

    yield base_url

    server.shutdown()


# ---------------------------------------------------------------------------
# Session-scoped: browser configuration (pytest-playwright)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def browser_context_args():
    return {
        "viewport": {"width": 1280, "height": 800},
        "permissions": ["clipboard-read", "clipboard-write"],
    }


# ---------------------------------------------------------------------------
# Function-scoped: per-test cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_db(e2e_app):
    """Truncate all tables, re-seed project, and reset global state between tests."""
    yield  # Run the test first

    from claude_headspace.database import db

    with e2e_app.app_context():
        # Truncate tables in dependency order
        for table in reversed(db.metadata.sorted_tables):
            db.session.execute(text(f'TRUNCATE TABLE "{table.name}" CASCADE'))
        db.session.commit()

        # Re-seed the test project (hook_client needs a registered project)
        from claude_headspace.models.project import Project, generate_slug
        project_path = str(PROJECT_ROOT)
        project_name = PROJECT_ROOT.name
        project = Project(
            name=project_name,
            slug=generate_slug(project_name),
            path=project_path,
        )
        db.session.add(project)
        db.session.commit()

    # Reset global state
    from claude_headspace.services.session_correlator import clear_session_cache
    from claude_headspace.services.hook_receiver import reset_receiver_state

    reset_receiver_state()
    clear_session_cache()


# ---------------------------------------------------------------------------
# Function-scoped: hook client
# ---------------------------------------------------------------------------

@pytest.fixture
def hook_client(e2e_server):
    """Provide a HookSimulator bound to a fresh session."""
    session_id = str(uuid4())
    # Use the real project directory (session correlator rejects /tmp)
    working_directory = str(PROJECT_ROOT)
    return HookSimulator(e2e_server, session_id, working_directory)


def _make_hook_client(base_url: str, working_directory: str | None = None):
    """Factory for creating additional hook clients (multi-agent tests)."""
    session_id = str(uuid4())
    wd = working_directory or str(PROJECT_ROOT)
    return HookSimulator(base_url, session_id, wd)


@pytest.fixture
def make_hook_client(e2e_server):
    """Factory fixture for creating additional hook clients."""
    def factory(working_directory: str | None = None):
        return _make_hook_client(e2e_server, working_directory)
    return factory


# ---------------------------------------------------------------------------
# Function-scoped: dashboard page with SSE
# ---------------------------------------------------------------------------

@pytest.fixture
def dashboard(page, e2e_server):
    """Navigate to dashboard and wait for SSE connection."""
    page.goto(e2e_server)
    page.wait_for_load_state("domcontentloaded")
    da = DashboardAssertions(
        page,
        Path(__file__).parent / "screenshots",
    )
    da.assert_sse_connected(timeout=10000)
    return da


@pytest.fixture
def dashboard_page(page, e2e_server):
    """Navigate to dashboard, return raw page (for tests that manage their own assertions)."""
    page.goto(e2e_server)
    page.wait_for_load_state("domcontentloaded")
    return page


# ---------------------------------------------------------------------------
# Function-scoped: voice app page with credentials
# ---------------------------------------------------------------------------

@pytest.fixture
def voice_page(page, e2e_server):
    """Navigate to voice app with pre-injected credentials."""
    va = VoiceAssertions(
        page,
        Path(__file__).parent / "screenshots" / "voice",
    )
    va.navigate_to_voice(e2e_server)
    return va
