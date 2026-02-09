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
    flatten_nested_sections,
    get_config_schema,
    load_config_file,
    merge_with_defaults,
    save_config_file,
    unflatten_nested_sections,
    validate_config,
)


class TestConfigSchema:
    """Tests for config schema definition."""

    def test_schema_has_all_sections(self):
        """Schema should have all expected sections."""
        section_names = [s.name for s in CONFIG_SCHEMA]
        expected = ["server", "logging", "database", "claude", "file_watcher", "event_system", "reaper", "sse", "hooks", "voice_bridge", "tmux_bridge", "dashboard", "archive", "commander", "notifications", "activity", "headspace", "openrouter"]
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

        expected_sections = ["server", "logging", "database", "claude", "file_watcher", "event_system", "sse", "hooks", "tmux_bridge", "dashboard", "archive", "commander"]
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


class TestFlattenUnflatten:
    """Tests for flatten_nested_sections and unflatten_nested_sections."""

    def test_flatten_nested_to_dot_notation(self):
        """Should convert nested dicts to dot-notation keys."""
        config = {
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1",
                "timeout": 30,
                "models": {
                    "turn": "haiku",
                    "task": "haiku",
                },
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 300,
                },
            }
        }
        result = flatten_nested_sections(config)

        assert result["openrouter"]["base_url"] == "https://openrouter.ai/api/v1"
        assert result["openrouter"]["timeout"] == 30
        assert result["openrouter"]["models.turn"] == "haiku"
        assert result["openrouter"]["models.task"] == "haiku"
        assert result["openrouter"]["cache.enabled"] is True
        assert result["openrouter"]["cache.ttl_seconds"] == 300
        # Nested dicts should be gone
        assert "models" not in result["openrouter"]
        assert "cache" not in result["openrouter"]

    def test_unflatten_dot_notation_to_nested(self):
        """Should convert dot-notation keys back to nested dicts."""
        config = {
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1",
                "timeout": 30,
                "models.turn": "haiku",
                "models.task": "haiku",
                "cache.enabled": True,
                "cache.ttl_seconds": 300,
            }
        }
        result = unflatten_nested_sections(config)

        assert result["openrouter"]["base_url"] == "https://openrouter.ai/api/v1"
        assert result["openrouter"]["timeout"] == 30
        assert result["openrouter"]["models"]["turn"] == "haiku"
        assert result["openrouter"]["models"]["task"] == "haiku"
        assert result["openrouter"]["cache"]["enabled"] is True
        assert result["openrouter"]["cache"]["ttl_seconds"] == 300

    def test_roundtrip_consistency(self):
        """Flatten then unflatten should produce the original structure."""
        original = {
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1",
                "timeout": 30,
                "models": {
                    "turn": "haiku",
                    "task": "haiku",
                    "project": "sonnet",
                    "objective": "sonnet",
                },
                "rate_limits": {
                    "calls_per_minute": 30,
                    "tokens_per_minute": 50000,
                },
                "cache": {
                    "enabled": True,
                    "ttl_seconds": 300,
                },
                "retry": {
                    "max_attempts": 3,
                },
            }
        }
        import copy
        expected = copy.deepcopy(original)

        flatten_nested_sections(original)
        unflatten_nested_sections(original)

        assert original == expected

    def test_flatten_no_openrouter_section(self):
        """Should handle missing openrouter section gracefully."""
        config = {"server": {"port": 5050}}
        result = flatten_nested_sections(config)
        assert result == {"server": {"port": 5050}}

    def test_unflatten_no_openrouter_section(self):
        """Should handle missing openrouter section gracefully."""
        config = {"server": {"port": 5050}}
        result = unflatten_nested_sections(config)
        assert result == {"server": {"port": 5050}}

    def test_flatten_modifies_in_place(self):
        """Flatten should modify the dict in place and return it."""
        config = {"openrouter": {"models": {"turn": "haiku"}}}
        result = flatten_nested_sections(config)
        assert result is config

    def test_unflatten_modifies_in_place(self):
        """Unflatten should modify the dict in place and return it."""
        config = {"openrouter": {"models.turn": "haiku"}}
        result = unflatten_nested_sections(config)
        assert result is config


class TestNewSchemaSections:
    """Tests for new CONFIG_SCHEMA sections (tmux_bridge, dashboard, archive)."""

    def test_tmux_bridge_section_exists(self):
        """Schema should have tmux_bridge section."""
        section = next((s for s in CONFIG_SCHEMA if s.name == "tmux_bridge"), None)
        assert section is not None
        assert section.title == "Tmux Bridge"

    def test_tmux_bridge_fields(self):
        """tmux_bridge section should have expected fields."""
        section = next(s for s in CONFIG_SCHEMA if s.name == "tmux_bridge")
        field_names = [f.name for f in section.fields]
        assert "health_check_interval" in field_names
        assert "subprocess_timeout" in field_names
        assert "text_enter_delay_ms" in field_names

    def test_dashboard_section_exists(self):
        """Schema should have dashboard section."""
        section = next((s for s in CONFIG_SCHEMA if s.name == "dashboard"), None)
        assert section is not None
        assert section.title == "Dashboard"

    def test_dashboard_fields(self):
        """dashboard section should have expected fields."""
        section = next(s for s in CONFIG_SCHEMA if s.name == "dashboard")
        field_names = [f.name for f in section.fields]
        assert "stale_processing_seconds" in field_names
        assert "active_timeout_minutes" in field_names

    def test_archive_section_exists(self):
        """Schema should have archive section."""
        section = next((s for s in CONFIG_SCHEMA if s.name == "archive"), None)
        assert section is not None
        assert section.title == "Archive"

    def test_archive_fields(self):
        """archive section should have expected fields including nested retention."""
        section = next(s for s in CONFIG_SCHEMA if s.name == "archive")
        field_names = [f.name for f in section.fields]
        assert "enabled" in field_names
        assert "retention.policy" in field_names
        assert "retention.keep_last_n" in field_names
        assert "retention.days" in field_names

    def test_new_openrouter_fields(self):
        """openrouter section should have retry and priority_scoring fields."""
        section = next(s for s in CONFIG_SCHEMA if s.name == "openrouter")
        field_names = [f.name for f in section.fields]
        assert "retry.base_delay_seconds" in field_names
        assert "retry.max_delay_seconds" in field_names
        assert "priority_scoring.debounce_seconds" in field_names

    def test_new_headspace_flow_detection_fields(self):
        """headspace section should have flow_detection fields."""
        section = next(s for s in CONFIG_SCHEMA if s.name == "headspace")
        field_names = [f.name for f in section.fields]
        assert "flow_detection.min_turn_rate" in field_names
        assert "flow_detection.max_frustration" in field_names
        assert "flow_detection.min_duration_minutes" in field_names

    def test_archive_in_nested_sections(self):
        """archive should be in NESTED_SECTIONS for flatten/unflatten."""
        from claude_headspace.services.config_editor import NESTED_SECTIONS
        assert "archive" in NESTED_SECTIONS


class TestHelpMetadata:
    """Tests for help_text and section_description metadata."""

    def test_all_sections_have_section_description(self):
        """Every section should have a non-empty section_description."""
        for section in CONFIG_SCHEMA:
            assert section.section_description, f"Section '{section.name}' missing section_description"

    def test_all_fields_have_help_text(self):
        """Every field should have a non-empty help_text."""
        for section in CONFIG_SCHEMA:
            for field in section.fields:
                assert field.help_text, f"Field '{section.name}.{field.name}' missing help_text"

    def test_get_config_schema_includes_help_text(self):
        """get_config_schema should include help_text in field dicts."""
        schema = get_config_schema()
        for section in schema:
            for field in section["fields"]:
                assert "help_text" in field

    def test_get_config_schema_includes_section_description(self):
        """get_config_schema should include section_description in section dicts."""
        schema = get_config_schema()
        for section in schema:
            assert "section_description" in section


class TestOpenrouterValidation:
    """Tests for openrouter section validation with dot-notation fields."""

    def test_valid_openrouter_config_passes(self):
        """Valid flattened openrouter config should pass validation."""
        config = {
            "openrouter": {
                "base_url": "https://openrouter.ai/api/v1",
                "timeout": 30,
                "models.turn": "anthropic/claude-3-haiku",
                "models.task": "anthropic/claude-3-haiku",
                "models.project": "anthropic/claude-3.5-sonnet",
                "models.objective": "anthropic/claude-3.5-sonnet",
                "rate_limits.calls_per_minute": 30,
                "rate_limits.tokens_per_minute": 50000,
                "cache.enabled": True,
                "cache.ttl_seconds": 300,
                "retry.max_attempts": 3,
            }
        }
        result = validate_config(config)
        assert result.valid

    def test_invalid_timeout_type(self):
        """Non-integer timeout should fail validation."""
        config = {"openrouter": {"timeout": "fast"}}
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "timeout" and e.section == "openrouter")
        assert "integer" in error.message

    def test_calls_per_minute_below_minimum(self):
        """calls_per_minute below 1 should fail validation."""
        config = {"openrouter": {"rate_limits.calls_per_minute": 0}}
        result = validate_config(config)
        assert not result.valid
        error = next(e for e in result.errors if e.field == "rate_limits.calls_per_minute")
        assert "at least 1" in error.message
