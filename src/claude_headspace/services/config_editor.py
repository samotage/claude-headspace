"""Config editor service for validation and persistence."""

import logging
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class FieldSchema:
    """Schema definition for a config field."""

    name: str
    field_type: str  # "string", "integer", "float", "boolean", "password"
    description: str
    required: bool = False
    min_value: int | float | None = None
    max_value: int | float | None = None
    default: Any = None


@dataclass
class SectionSchema:
    """Schema definition for a config section."""

    name: str
    title: str
    fields: list[FieldSchema]


@dataclass
class ValidationError:
    """Validation error for a config field."""

    section: str
    field: str
    message: str


@dataclass
class ValidationResult:
    """Result of config validation."""

    valid: bool
    errors: list[ValidationError]


# Config schema definition
CONFIG_SCHEMA = [
    SectionSchema(
        name="server",
        title="Server",
        fields=[
            FieldSchema("host", "string", "Server bind address", default="127.0.0.1"),
            FieldSchema("port", "integer", "Server port number", min_value=1, max_value=65535, default=5050),
            FieldSchema("debug", "boolean", "Enable debug mode", default=False),
        ],
    ),
    SectionSchema(
        name="logging",
        title="Logging",
        fields=[
            FieldSchema("level", "string", "Log level (DEBUG, INFO, WARNING, ERROR)", default="INFO"),
            FieldSchema("file", "string", "Log file path", default="logs/app.log"),
        ],
    ),
    SectionSchema(
        name="database",
        title="Database",
        fields=[
            FieldSchema("host", "string", "Database host", default="localhost"),
            FieldSchema("port", "integer", "Database port", min_value=1, max_value=65535, default=5432),
            FieldSchema("name", "string", "Database name", default="claude_headspace"),
            FieldSchema("user", "string", "Database user", default="postgres"),
            FieldSchema("password", "password", "Database password", default=""),
            FieldSchema("pool_size", "integer", "Connection pool size", min_value=1, max_value=100, default=10),
            FieldSchema("pool_timeout", "integer", "Pool timeout in seconds", min_value=1, max_value=300, default=30),
        ],
    ),
    SectionSchema(
        name="claude",
        title="Claude",
        fields=[
            FieldSchema("projects_path", "string", "Path to Claude projects directory", default="~/.claude/projects"),
        ],
    ),
    SectionSchema(
        name="file_watcher",
        title="File Watcher",
        fields=[
            FieldSchema("polling_interval", "float", "Polling interval in seconds", min_value=0.1, max_value=60, default=2),
            FieldSchema("reconciliation_interval", "integer", "Reconciliation interval in seconds", min_value=10, max_value=600, default=60),
            FieldSchema("inactivity_timeout", "integer", "Inactivity timeout in seconds", min_value=60, max_value=86400, default=5400),
            FieldSchema("debounce_interval", "float", "Debounce interval in seconds", min_value=0.1, max_value=10, default=0.5),
        ],
    ),
    SectionSchema(
        name="event_system",
        title="Event System",
        fields=[
            FieldSchema("write_retry_attempts", "integer", "Write retry attempts", min_value=1, max_value=10, default=3),
            FieldSchema("write_retry_delay_ms", "integer", "Write retry delay in milliseconds", min_value=10, max_value=5000, default=100),
            FieldSchema("max_restarts_per_minute", "integer", "Max restarts per minute", min_value=1, max_value=60, default=5),
            FieldSchema("shutdown_timeout_seconds", "integer", "Shutdown timeout in seconds", min_value=1, max_value=60, default=2),
        ],
    ),
    SectionSchema(
        name="sse",
        title="SSE",
        fields=[
            FieldSchema("heartbeat_interval_seconds", "integer", "Heartbeat interval in seconds", min_value=1, max_value=300, default=30),
            FieldSchema("max_connections", "integer", "Maximum SSE connections", min_value=1, max_value=1000, default=100),
            FieldSchema("connection_timeout_seconds", "integer", "Connection timeout in seconds", min_value=10, max_value=600, default=60),
            FieldSchema("retry_after_seconds", "integer", "Retry after seconds", min_value=1, max_value=60, default=5),
        ],
    ),
    SectionSchema(
        name="hooks",
        title="Hooks",
        fields=[
            FieldSchema("enabled", "boolean", "Enable hook receiver", default=True),
            FieldSchema("polling_interval_with_hooks", "integer", "Polling interval when hooks active (seconds)", min_value=10, max_value=600, default=60),
            FieldSchema("fallback_timeout", "integer", "Fallback timeout in seconds", min_value=60, max_value=3600, default=300),
        ],
    ),
    SectionSchema(
        name="commander",
        title="Commander (Input Bridge)",
        fields=[
            FieldSchema("health_check_interval", "integer", "Seconds between socket availability checks", min_value=1, max_value=3600, default=30),
            FieldSchema("socket_timeout", "integer", "Socket operation timeout in seconds", min_value=1, max_value=30, default=2),
            FieldSchema("socket_path_prefix", "string", "Socket path prefix (must match claudec convention)", default="/tmp/claudec-"),
        ],
    ),
    SectionSchema(
        name="notifications",
        title="Notifications",
        fields=[
            FieldSchema("enabled", "boolean", "Enable macOS notifications (requires terminal-notifier)", default=True),
            FieldSchema("sound", "boolean", "Play sound with notifications", default=True),
            FieldSchema("rate_limit_seconds", "integer", "Minimum seconds between notifications per agent", min_value=0, max_value=60, default=5),
        ],
    ),
    SectionSchema(
        name="activity",
        title="Activity Metrics",
        fields=[
            FieldSchema("enabled", "boolean", "Enable activity metrics aggregation", default=True),
            FieldSchema("interval_seconds", "integer", "Seconds between aggregation passes", min_value=10, max_value=3600, default=300),
            FieldSchema("retention_days", "integer", "Days to retain metric records before pruning", min_value=1, max_value=365, default=30),
        ],
    ),
    SectionSchema(
        name="openrouter",
        title="Inference",
        fields=[
            FieldSchema("base_url", "string", "OpenRouter API base URL",
                         default="https://openrouter.ai/api/v1"),
            FieldSchema("timeout", "integer", "Request timeout (seconds)",
                         min_value=1, max_value=300, default=30),
            FieldSchema("models.turn", "string", "Model for turn summaries",
                         default="anthropic/claude-3-haiku"),
            FieldSchema("models.task", "string", "Model for task summaries",
                         default="anthropic/claude-3-haiku"),
            FieldSchema("models.project", "string", "Model for project analysis",
                         default="anthropic/claude-3.5-sonnet"),
            FieldSchema("models.objective", "string", "Model for priority scoring",
                         default="anthropic/claude-3.5-sonnet"),
            FieldSchema("rate_limits.calls_per_minute", "integer", "Max API calls per minute",
                         min_value=1, max_value=1000, default=30),
            FieldSchema("rate_limits.tokens_per_minute", "integer", "Max tokens per minute",
                         min_value=1, max_value=1000000, default=50000),
            FieldSchema("cache.enabled", "boolean", "Enable inference result caching",
                         default=True),
            FieldSchema("cache.ttl_seconds", "integer", "Cache TTL (seconds)",
                         min_value=1, max_value=3600, default=300),
            FieldSchema("retry.max_attempts", "integer", "Max retry attempts",
                         min_value=1, max_value=10, default=3),
        ],
    ),
]


def get_config_schema() -> list[dict]:
    """
    Get the config schema as a serializable list.

    Returns:
        List of section dictionaries with field information
    """
    result = []
    for section in CONFIG_SCHEMA:
        section_dict = {
            "name": section.name,
            "title": section.title,
            "fields": [],
        }
        for field in section.fields:
            field_dict = {
                "name": field.name,
                "type": field.field_type,
                "description": field.description,
                "required": field.required,
                "default": field.default,
            }
            if field.min_value is not None:
                field_dict["min"] = field.min_value
            if field.max_value is not None:
                field_dict["max"] = field.max_value
            section_dict["fields"].append(field_dict)
        result.append(section_dict)
    return result


def load_config_file(config_path: str | Path = "config.yaml") -> dict:
    """
    Load configuration from YAML file only (no env vars).

    Args:
        config_path: Path to config file

    Returns:
        Configuration dictionary from file
    """
    path = Path(config_path)
    if not path.exists():
        return {}

    with open(path, "r") as f:
        content = yaml.safe_load(f)
        return content if content else {}


def validate_config(config: dict) -> ValidationResult:
    """
    Validate configuration against schema.

    Args:
        config: Configuration dictionary to validate

    Returns:
        ValidationResult with validation status and errors
    """
    errors = []

    for section in CONFIG_SCHEMA:
        section_data = config.get(section.name, {})

        for field in section.fields:
            value = section_data.get(field.name)

            # Check required fields
            if field.required and value is None:
                errors.append(ValidationError(
                    section=section.name,
                    field=field.name,
                    message=f"{field.name} is required",
                ))
                continue

            # Skip validation if value is None and not required
            if value is None:
                continue

            # Type validation
            if field.field_type in ("string", "password"):
                if not isinstance(value, str):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be a string",
                    ))

            elif field.field_type == "integer":
                if not isinstance(value, int) or isinstance(value, bool):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be an integer",
                    ))
                else:
                    # Range validation
                    if field.min_value is not None and value < field.min_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at least {field.min_value}",
                        ))
                    if field.max_value is not None and value > field.max_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at most {field.max_value}",
                        ))

            elif field.field_type == "float":
                if not isinstance(value, (int, float)) or isinstance(value, bool):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be a number",
                    ))
                else:
                    # Range validation
                    if field.min_value is not None and value < field.min_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at least {field.min_value}",
                        ))
                    if field.max_value is not None and value > field.max_value:
                        errors.append(ValidationError(
                            section=section.name,
                            field=field.name,
                            message=f"{field.name} must be at most {field.max_value}",
                        ))

            elif field.field_type == "boolean":
                if not isinstance(value, bool):
                    errors.append(ValidationError(
                        section=section.name,
                        field=field.name,
                        message=f"{field.name} must be a boolean",
                    ))

    return ValidationResult(
        valid=len(errors) == 0,
        errors=errors,
    )


def save_config_file(
    config: dict,
    config_path: str | Path = "config.yaml",
) -> tuple[bool, str | None]:
    """
    Save configuration to YAML file atomically.

    Writes to a temp file first, then renames to prevent corruption.
    Password values are never logged in error messages.

    Args:
        config: Configuration dictionary to save
        config_path: Path to config file

    Returns:
        Tuple of (success, error_message)
    """
    path = Path(config_path)

    try:
        # Write to temporary file first
        fd, temp_path = tempfile.mkstemp(
            suffix=".yaml",
            prefix="config_",
            dir=path.parent,
        )

        try:
            with os.fdopen(fd, "w") as f:
                yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)

            # Atomic rename
            os.replace(temp_path, path)

            # Log success without sensitive data
            logger.info(f"Configuration saved to {path}")
            return True, None

        except Exception as e:
            # Clean up temp file on error
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

    except PermissionError:
        error_msg = f"Permission denied writing to {path}"
        logger.error(error_msg)
        return False, error_msg

    except Exception as e:
        # Never log config values (may contain password)
        error_msg = f"Failed to save configuration: {type(e).__name__}"
        logger.error(error_msg)
        return False, error_msg


def flatten_openrouter(config: dict) -> dict:
    """
    Flatten nested openrouter config keys into dot-notation.

    Converts e.g. config['openrouter']['models']['turn'] to
    config['openrouter']['models.turn'] so the flat section[field]
    editor can handle it.

    Args:
        config: Configuration dictionary (modified in-place and returned)

    Returns:
        The config dict with openrouter section flattened
    """
    section = config.get("openrouter")
    if not isinstance(section, dict):
        return config

    flat = {}
    for key, value in list(section.items()):
        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                flat[f"{key}.{subkey}"] = subvalue
        else:
            flat[key] = value

    config["openrouter"] = flat
    return config


def unflatten_openrouter(config: dict) -> dict:
    """
    Unflatten dot-notation openrouter keys back to nested dicts.

    Converts e.g. config['openrouter']['models.turn'] to
    config['openrouter']['models']['turn'] for YAML serialisation.

    Args:
        config: Configuration dictionary (modified in-place and returned)

    Returns:
        The config dict with openrouter section unflattened
    """
    section = config.get("openrouter")
    if not isinstance(section, dict):
        return config

    nested = {}
    for key, value in section.items():
        if "." in key:
            parent, child = key.split(".", 1)
            if parent not in nested:
                nested[parent] = {}
            nested[parent][child] = value
        else:
            nested[key] = value

    config["openrouter"] = nested
    return config


def merge_with_defaults(config: dict) -> dict:
    """
    Merge provided config with defaults for any missing values.

    Args:
        config: Partial configuration dictionary

    Returns:
        Configuration with defaults filled in
    """
    result = {}

    for section in CONFIG_SCHEMA:
        section_data = config.get(section.name, {})
        result[section.name] = {}

        for field in section.fields:
            if field.name in section_data:
                result[section.name][field.name] = section_data[field.name]
            elif field.default is not None:
                result[section.name][field.name] = field.default

    return result
