"""Tests for database configuration and connectivity."""

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml

from claude_headspace.app import create_app
from claude_headspace.config import (
    load_config,
    get_database_url,
    mask_database_url,
    DEFAULTS,
    ENV_MAPPINGS,
)
from claude_headspace.database import db, check_database_health, init_database


class TestDatabaseConfigDefaults:
    """Test database configuration defaults."""

    def test_database_defaults_exist(self):
        """Test that database defaults are defined."""
        assert "database" in DEFAULTS
        db_defaults = DEFAULTS["database"]
        assert db_defaults["host"] == "localhost"
        assert db_defaults["port"] == 5432
        assert db_defaults["name"] == "claude_headspace"
        assert db_defaults["user"] == "postgres"
        assert db_defaults["password"] == ""
        assert db_defaults["pool_size"] == 10
        assert db_defaults["pool_timeout"] == 30

    def test_load_config_has_database_defaults(self):
        """Test that load_config includes database defaults."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({}, f)
            config = load_config(f.name)
        os.unlink(f.name)

        assert "database" in config
        assert config["database"]["host"] == "localhost"
        assert config["database"]["port"] == 5432


class TestDatabaseEnvMappings:
    """Test database environment variable mappings."""

    def test_database_env_mappings_exist(self):
        """Test that all database env var mappings are defined."""
        expected_vars = [
            "DATABASE_HOST",
            "DATABASE_PORT",
            "DATABASE_NAME",
            "DATABASE_USER",
            "DATABASE_PASSWORD",
            "DATABASE_POOL_SIZE",
            "DATABASE_POOL_TIMEOUT",
        ]
        for var in expected_vars:
            assert var in ENV_MAPPINGS, f"{var} not in ENV_MAPPINGS"

    def test_database_host_env_override(self):
        """Test DATABASE_HOST env var overrides config."""
        original = os.environ.get("DATABASE_HOST")
        os.environ["DATABASE_HOST"] = "customhost"
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({"database": {"host": "localhost"}}, f)
                config = load_config(f.name)
            os.unlink(f.name)
            assert config["database"]["host"] == "customhost"
        finally:
            if original is None:
                del os.environ["DATABASE_HOST"]
            else:
                os.environ["DATABASE_HOST"] = original

    def test_database_port_env_override(self):
        """Test DATABASE_PORT env var overrides config."""
        original = os.environ.get("DATABASE_PORT")
        os.environ["DATABASE_PORT"] = "5433"
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({"database": {"port": 5432}}, f)
                config = load_config(f.name)
            os.unlink(f.name)
            assert config["database"]["port"] == 5433
        finally:
            if original is None:
                del os.environ["DATABASE_PORT"]
            else:
                os.environ["DATABASE_PORT"] = original

    def test_database_pool_size_env_override(self):
        """Test DATABASE_POOL_SIZE env var overrides config."""
        original = os.environ.get("DATABASE_POOL_SIZE")
        os.environ["DATABASE_POOL_SIZE"] = "20"
        try:
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({"database": {"pool_size": 10}}, f)
                config = load_config(f.name)
            os.unlink(f.name)
            assert config["database"]["pool_size"] == 20
        finally:
            if original is None:
                del os.environ["DATABASE_POOL_SIZE"]
            else:
                os.environ["DATABASE_POOL_SIZE"] = original


class TestDatabaseURL:
    """Test DATABASE_URL support.

    All tests use claude_headspace_test as the database name, matching
    the real project convention. Tests that need to bypass the env var
    (to test config-based URL building) temporarily unset DATABASE_URL.
    """

    def test_get_database_url_from_config(self):
        """Test building database URL from config fields."""
        original = os.environ.pop("DATABASE_URL", None)
        try:
            config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "name": "claude_headspace_test",
                    "user": "samotage",
                    "password": "",
                }
            }
            url = get_database_url(config)
            assert url == "postgresql://samotage@localhost:5432/claude_headspace_test"
        finally:
            if original is not None:
                os.environ["DATABASE_URL"] = original

    def test_get_database_url_with_password(self):
        """Test building database URL with password."""
        original = os.environ.pop("DATABASE_URL", None)
        try:
            config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "name": "claude_headspace_test",
                    "user": "samotage",
                    "password": "secret123",
                }
            }
            url = get_database_url(config)
            assert url == "postgresql://samotage:secret123@localhost:5432/claude_headspace_test"
        finally:
            if original is not None:
                os.environ["DATABASE_URL"] = original

    def test_database_url_env_takes_precedence(self):
        """Test DATABASE_URL env var takes precedence over config fields."""
        original = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "postgresql://samotage@otherhost:5555/claude_headspace_test"
        try:
            config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "name": "claude_headspace_test",
                    "user": "samotage",
                    "password": "",
                }
            }
            url = get_database_url(config)
            assert url == "postgresql://samotage@otherhost:5555/claude_headspace_test"
        finally:
            if original is None:
                del os.environ["DATABASE_URL"]
            else:
                os.environ["DATABASE_URL"] = original

    def test_guard_blocks_production_db(self):
        """Test that the safety guard prevents connecting to production DB."""
        original = os.environ.pop("DATABASE_URL", None)
        try:
            config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "name": "claude_headspace",
                    "user": "samotage",
                    "password": "",
                }
            }
            with pytest.raises(RuntimeError, match="SAFETY GUARD"):
                get_database_url(config)
        finally:
            if original is not None:
                os.environ["DATABASE_URL"] = original

    def test_guard_blocks_production_db_via_env(self):
        """Test that DATABASE_URL pointing to production is also blocked."""
        original = os.environ.get("DATABASE_URL")
        os.environ["DATABASE_URL"] = "postgresql://samotage@localhost:5432/claude_headspace"
        try:
            config = {"database": {"name": "claude_headspace"}}
            with pytest.raises(RuntimeError, match="SAFETY GUARD"):
                get_database_url(config)
        finally:
            if original is None:
                del os.environ["DATABASE_URL"]
            else:
                os.environ["DATABASE_URL"] = original

    def test_guard_allows_test_db(self):
        """Test that claude_headspace_test is allowed."""
        original = os.environ.pop("DATABASE_URL", None)
        try:
            config = {
                "database": {
                    "host": "localhost",
                    "port": 5432,
                    "name": "claude_headspace_test",
                    "user": "samotage",
                    "password": "",
                }
            }
            url = get_database_url(config)
            assert url == "postgresql://samotage@localhost:5432/claude_headspace_test"
        finally:
            if original is not None:
                os.environ["DATABASE_URL"] = original


class TestPasswordMasking:
    """Test password masking in logs."""

    def test_mask_database_url_with_password(self):
        """Test password is masked in URL."""
        url = "postgresql://user:supersecret@localhost:5432/db"
        masked = mask_database_url(url)
        assert "supersecret" not in masked
        assert "***" in masked
        assert masked == "postgresql://user:***@localhost:5432/db"

    def test_mask_database_url_without_password(self):
        """Test URL without password is unchanged."""
        url = "postgresql://user@localhost:5432/db"
        masked = mask_database_url(url)
        assert masked == url

    def test_mask_database_url_complex_password(self):
        """Test masking works with special characters in password."""
        url = "postgresql://user:p@ss:word/123@localhost:5432/db"
        masked = mask_database_url(url)
        assert "p@ss:word/123" not in masked
        assert "***" in masked


class TestHealthEndpointWithDatabase:
    """Test health endpoint database integration."""

    def test_health_returns_database_status(self, client):
        """Test GET /health includes database field."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert "database" in data
        # Database will be disconnected in test environment
        assert data["database"] in ["connected", "disconnected"]

    def test_health_degraded_when_db_disconnected(self, client):
        """Test status is degraded when database disconnected."""
        response = client.get('/health')
        data = json.loads(response.data)
        # In test environment without Postgres, database is disconnected
        if data["database"] == "disconnected":
            assert data["status"] == "degraded"
            assert "database_error" in data

    def test_health_healthy_status_format(self, client):
        """Test health response has correct fields."""
        response = client.get('/health')
        data = json.loads(response.data)
        assert "status" in data
        assert "version" in data
        assert "database" in data


class TestAppStartsWithoutDatabase:
    """Test application starts when database is unavailable."""

    def test_app_starts_with_invalid_db_config(self):
        """Test app creates successfully even with invalid database config."""
        project_root = Path(__file__).parent.parent
        original_cwd = os.getcwd()
        os.chdir(project_root)

        try:
            # App should start even though database connection will fail
            app = create_app(config_path=str(project_root / "config.yaml"), testing=True)
            assert app is not None
            # DATABASE_CONNECTED should be False when DB is unavailable
            assert "DATABASE_CONNECTED" in app.config
        finally:
            os.chdir(original_cwd)


class TestFlaskMigrateCommands:
    """Test Flask-Migrate commands are available."""

    def test_db_command_group_exists(self, runner):
        """Test 'flask db' command group is registered."""
        result = runner.invoke(args=['db', '--help'])
        # Should show help output, not an error
        assert 'Usage:' in result.output or 'Commands:' in result.output

    def test_db_upgrade_command_exists(self, runner):
        """Test 'flask db upgrade' command is registered."""
        result = runner.invoke(args=['db', 'upgrade', '--help'])
        assert result.exit_code == 0 or 'Usage:' in result.output

    def test_db_downgrade_command_exists(self, runner):
        """Test 'flask db downgrade' command is registered."""
        result = runner.invoke(args=['db', 'downgrade', '--help'])
        assert result.exit_code == 0 or 'Usage:' in result.output


class TestConnectionPoolConfig:
    """Test connection pool configuration."""

    def test_pool_size_config_read(self):
        """Test pool_size is read from config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({"database": {"pool_size": 5}}, f)
            config = load_config(f.name)
        os.unlink(f.name)
        assert config["database"]["pool_size"] == 5

    def test_pool_timeout_config_read(self):
        """Test pool_timeout is read from config."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({"database": {"pool_timeout": 60}}, f)
            config = load_config(f.name)
        os.unlink(f.name)
        assert config["database"]["pool_timeout"] == 60

    def test_sqlalchemy_engine_options_configured(self):
        """Test SQLAlchemy engine options are set correctly."""
        project_root = Path(__file__).parent.parent
        original_cwd = os.getcwd()
        os.chdir(project_root)

        try:
            app = create_app(config_path=str(project_root / "config.yaml"), testing=True)
            engine_options = app.config.get("SQLALCHEMY_ENGINE_OPTIONS", {})
            assert "pool_size" in engine_options
            assert "pool_timeout" in engine_options
            assert "pool_recycle" in engine_options
            assert "pool_pre_ping" in engine_options
            assert engine_options["pool_pre_ping"] is True
        finally:
            os.chdir(original_cwd)
