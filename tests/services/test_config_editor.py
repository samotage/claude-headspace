"""Tests for config editor service."""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from claude_headspace.services.config_editor import (
    CONFIG_SCHEMA,
    FieldSchema,
    SectionSchema,
    ValidationError,
    ValidationResult,
    get_config_schema,
    load_config_file,
    merge_with_defaults,
    save_config_file,
    validate_config,
)


class TestConfigSchema:
    """Tests for config schema definition."""

    def test_schema_has_all_sections(self):
        """Schema should have all expected sections."""
        section_names = [s.name for s in CONFIG_SCHEMA]
        expected = ["server", "logging", "database", "claude", "file_watcher", "event_system", "sse", "hooks", "notifications"]
        assert section_names == expected

    def test_each_section_has_title(self):
        """Each section should have a title."""
        for section in CONFIG_SCHEMA:
            assert section.title
            assert isinstance(section.title, str)

    def test_each_section_has_fields(self):
        """Each section should have fields."""
        for section in CONFIG_SCHEMA:
            assert len(section.fields) > 0

    def test_field_types_are_valid(self):
        """Field types should be valid."""
        valid_types = {"string", "integer", "float", "boolean", "password"}
        for section in CONFIG_SCHEMA:
            for field in section.fields:
                assert field.field_type in valid_types

    def test_password_field_exists_in_database(self):
        """Database section should have password field."""
        db_section = next(s for s in CONFIG_SCHEMA if s.name == "database")
        password_field = next(f for f in db_section.fields if f.name == "password")
        assert password_field.field_type == "password"


class TestGetConfigSchema:
    """Tests for get_config_schema function."""

    def test_returns_list(self):
        """Should return a list."""
        result = get_config_schema()
        assert isinstance(result, list)

    def test_sections_have_required_keys(self):
        """Each section should have name, title, fields."""
        result = get_config_schema()
        for section in result:
            assert "name" in section
            assert "title" in section
            assert "fields" in section

    def test_fields_have_required_keys(self):
        """Each field should have name, type, description."""
        result = get_config_schema()
        for section in result:
            for field in section["fields"]:
                assert "name" in field
                assert "type" in field
                assert "description" in field


class TestLoadConfigFile:
    """Tests for load_config_file function."""

    def test_returns_empty_dict_for_missing_file(self):
        """Should return empty dict if file doesn't exist."""
        result = load_config_file("/nonexistent/path.yaml")
        assert result == {}

    def test_loads_valid_yaml(self):
        """Should load valid YAML file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump({"server": {"port": 5050}}, f)
            f.flush()
            try:
                result = load_config_file(f.name)
                assert result["server"]["port"] == 5050
            finally:
                os.unlink(f.name)

    def test_returns_empty_dict_for_empty_file(self):
        """Should return empty dict for empty file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("")
            f.flush()
            try:
                result = load_config_file(f.name)
                assert result == {}
            finally:
                os.unlink(f.name)


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_config_passes(self):
        """Valid configuration should pass validation."""
        config = {
            "server": {"host": "localhost", "port": 5050, "debug": False},
            "logging": {"level": "INFO", "file": "logs/app.log"},
            "database": {"host": "localhost", "port": 5432, "name": "db", "user": "user", "password": "", "pool_size": 10, "pool_timeout": 30},
        }
        result = validate_config(config)
        assert result.valid
        assert len(result.errors) == 0

    def test_invalid_port_type(self):
        """Port as string should fail validation."""
        config = {"server": {"port": "abc"}}
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "port")
        assert "integer" in error.message

    def test_port_below_minimum(self):
        """Port below 1 should fail validation."""
        config = {"server": {"port": 0}}
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "port")
        assert "at least 1" in error.message

    def test_port_above_maximum(self):
        """Port above 65535 should fail validation."""
        config = {"server": {"port": 70000}}
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "port")
        assert "at most 65535" in error.message

    def test_invalid_boolean_type(self):
        """String for boolean should fail validation."""
        config = {"server": {"debug": "yes"}}
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "debug")
        assert "boolean" in error.message

    def test_invalid_string_type(self):
        """Integer for string should fail validation."""
        config = {"server": {"host": 123}}
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "host")
        assert "string" in error.message

    def test_float_validation(self):
        """Float fields should validate correctly."""
        config = {"file_watcher": {"polling_interval": 0.05}}  # Below minimum
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "polling_interval")
        assert "at least 0.1" in error.message

    def test_missing_section_passes(self):
        """Missing section should pass (uses defaults)."""
        config = {}
        result = validate_config(config)
        assert result.valid

    def test_none_value_passes_for_optional(self):
        """None value for optional field should pass."""
        config = {"database": {"password": None}}
        result = validate_config(config)
        # Password is optional so None should pass
        assert result.valid or not any(e.field == "password" for e in result.errors)


class TestSaveConfigFile:
    """Tests for save_config_file function."""

    def test_saves_config_atomically(self):
        """Should save config using atomic write."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {"server": {"port": 5050}}

            success, error = save_config_file(config, config_path)

            assert success
            assert error is None
            assert config_path.exists()

            with open(config_path) as f:
                saved = yaml.safe_load(f)
            assert saved["server"]["port"] == 5050

    def test_overwrites_existing_file(self):
        """Should overwrite existing config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"

            # Write initial config
            with open(config_path, "w") as f:
                yaml.dump({"server": {"port": 5000}}, f)

            # Overwrite with new config
            config = {"server": {"port": 5050}}
            success, error = save_config_file(config, config_path)

            assert success
            with open(config_path) as f:
                saved = yaml.safe_load(f)
            assert saved["server"]["port"] == 5050

    def test_creates_parent_directory(self):
        """Should handle existing parent directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "config.yaml"
            config = {"server": {"port": 5050}}

            success, error = save_config_file(config, config_path)
            assert success

    def test_returns_error_on_permission_denied(self):
        """Should return error on permission denied."""
        # Use a path that definitely doesn't exist and can't be written
        config_path = "/root/definitely_not_writable/config.yaml"
        config = {"server": {"port": 5050}}

        success, error = save_config_file(config, config_path)

        assert not success
        assert error is not None


class TestMergeWithDefaults:
    """Tests for merge_with_defaults function."""

    def test_fills_missing_sections(self):
        """Should fill in missing sections with defaults."""
        config = {}
        result = merge_with_defaults(config)

        assert "server" in result
        assert "database" in result
        assert "sse" in result

    def test_fills_missing_fields(self):
        """Should fill in missing fields with defaults."""
        config = {"server": {"port": 9000}}
        result = merge_with_defaults(config)

        assert result["server"]["port"] == 9000
        assert result["server"]["host"] == "127.0.0.1"  # Default
        assert result["server"]["debug"] is False  # Default

    def test_preserves_provided_values(self):
        """Should preserve provided values."""
        config = {"server": {"host": "0.0.0.0", "port": 8080, "debug": True}}
        result = merge_with_defaults(config)

        assert result["server"]["host"] == "0.0.0.0"
        assert result["server"]["port"] == 8080
        assert result["server"]["debug"] is True

    def test_handles_all_sections(self):
        """Should handle all schema sections."""
        config = {}
        result = merge_with_defaults(config)

        expected_sections = ["server", "logging", "database", "claude", "file_watcher", "event_system", "sse", "hooks"]
        for section in expected_sections:
            assert section in result


class TestPasswordSecurity:
    """Tests for password security in config editor."""

    def test_password_not_in_error_message(self):
        """Error messages should not contain password values."""
        config = {"database": {"password": "super_secret_password", "port": "invalid"}}
        result = validate_config(config)

        for error in result.errors:
            assert "super_secret_password" not in error.message.lower()

    @patch("claude_headspace.services.config_editor.logger")
    def test_password_not_logged_on_save_error(self, mock_logger):
        """Password should not be logged on save error."""
        # This tests that the error handling doesn't log config values
        config = {"database": {"password": "secret123"}}
        save_config_file(config, "/definitely/invalid/path")

        # Check that password wasn't in any log call
        for call in mock_logger.method_calls:
            for arg in call.args:
                if isinstance(arg, str):
                    assert "secret123" not in arg
