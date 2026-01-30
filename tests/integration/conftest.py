"""Database lifecycle fixtures for integration tests.

Manages a dedicated Postgres test database:
- Session-scoped: create/drop test database, create schema
- Function-scoped: per-test session with rollback for isolation
"""

import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from claude_headspace.config import load_config, get_database_url
from claude_headspace.database import db


def _get_test_database_url() -> str:
    """Build the test database URL.

    Priority:
    1. TEST_DATABASE_URL env var
    2. Production config with '_test' suffix on database name
    """
    test_url = os.environ.get("TEST_DATABASE_URL")
    if test_url:
        return test_url

    # Load production config and modify the database name
    project_root = Path(__file__).parent.parent.parent
    config = load_config(str(project_root / "config.yaml"))
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
    """Get a connection URL to the 'postgres' database for admin operations."""
    test_url = _get_test_database_url()
    # Replace the database name with 'postgres' for admin connection
    # URL format: postgresql://user[:password]@host:port/dbname
    parts = test_url.rsplit("/", 1)
    return parts[0] + "/postgres"


def _get_test_db_name() -> str:
    """Extract the test database name from the URL."""
    test_url = _get_test_database_url()
    return test_url.rsplit("/", 1)[1]


@pytest.fixture(scope="session")
def test_database_url():
    """Provide the test database URL."""
    return _get_test_database_url()


@pytest.fixture(scope="session")
def test_db_engine(test_database_url):
    """Create and drop the test database for the entire test session.

    - Connects to the 'postgres' database to create/drop the test DB
    - Creates all tables from model metadata
    - Yields an engine connected to the test database
    - Drops the test database after all tests complete
    """
    admin_url = _get_admin_url()
    db_name = _get_test_db_name()

    # Connect to admin database to create/drop test database
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    try:
        with admin_engine.connect() as conn:
            # Drop if exists (handles interrupted previous runs)
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
    finally:
        admin_engine.dispose()

    # Create engine for the test database
    engine = create_engine(test_database_url)

    # Import all models to ensure they're registered with metadata
    from claude_headspace import models  # noqa: F401

    # Create all tables
    db.metadata.create_all(engine)

    yield engine

    # Teardown: drop test database
    engine.dispose()

    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            # Terminate any remaining connections
            conn.execute(text(
                f"SELECT pg_terminate_backend(pg_stat_activity.pid) "
                f"FROM pg_stat_activity "
                f"WHERE pg_stat_activity.datname = '{db_name}' "
                f"AND pid <> pg_backend_pid()"
            ))
            conn.execute(text(f'DROP DATABASE IF EXISTS "{db_name}"'))
    finally:
        admin_engine.dispose()


@pytest.fixture(scope="session")
def TestSessionFactory(test_db_engine):
    """Provide a sessionmaker bound to the test database engine."""
    return sessionmaker(bind=test_db_engine)


@pytest.fixture
def db_session(test_db_engine, TestSessionFactory):
    """Provide a database session with per-test isolation via rollback.

    Each test gets a session wrapped in a transaction that is rolled back
    after the test completes, ensuring no data leaks between tests.
    """
    connection = test_db_engine.connect()
    transaction = connection.begin()
    session = TestSessionFactory(bind=connection)

    yield session

    session.close()
    if transaction.is_active:
        transaction.rollback()
    connection.close()
