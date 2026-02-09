"""Configuration loader with YAML and environment variable support."""

import os
from pathlib import Path
from typing import Any

import yaml


# Default configuration values
DEFAULTS = {
    "server": {
        "host": "0.0.0.0",
        "port": 5055,
        "debug": False,
    },
    "logging": {
        "level": "INFO",
        "file": "logs/app.log",
    },
    "database": {
        "host": "localhost",
        "port": 5432,
        "name": "claude_headspace",
        "user": "postgres",
        "password": "",
        "pool_size": 10,
        "pool_timeout": 30,
    },
    "claude": {
        "projects_path": "~/.claude/projects",
    },
    "file_watcher": {
        "polling_interval": 2,
        "reconciliation_interval": 60,
        "inactivity_timeout": 5400,
        "debounce_interval": 0.5,
        "awaiting_input_timeout": 10,
    },
    "event_system": {
        "write_retry_attempts": 3,
        "write_retry_delay_ms": 100,
        "max_restarts_per_minute": 5,
        "shutdown_timeout_seconds": 2,
    },
    "sse": {
        "heartbeat_interval_seconds": 30,
        "max_connections": 100,
        "connection_timeout_seconds": 60,
        "retry_after_seconds": 5,
    },
    "hooks": {
        "enabled": True,
        "polling_interval_with_hooks": 60,
        "fallback_timeout": 300,
    },
    "notifications": {
        "enabled": True,
        "sound": True,
        "events": {
            "task_complete": True,
            "awaiting_input": True,
        },
        "rate_limit_seconds": 5,
        "dashboard_url": "http://localhost:5055",
    },
    "activity": {
        "enabled": True,
        "interval_seconds": 300,
        "retention_days": 3000,
    },
    "commander": {
        "health_check_interval": 30,
        "socket_timeout": 2,
        "socket_path_prefix": "/tmp/claudec-",
    },
    "tmux_bridge": {
        "health_check_interval": 30,
        "subprocess_timeout": 5,
        "text_enter_delay_ms": 100,
        "sequential_delay_ms": 150,
        "select_other_delay_ms": 500,
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "timeout": 30,
        "models": {
            "turn": "anthropic/claude-haiku-4.5",
            "task": "anthropic/claude-haiku-4.5",
            "project": "anthropic/claude-3.5-sonnet",
            "objective": "anthropic/claude-3.5-sonnet",
        },
        "rate_limits": {
            "calls_per_minute": 30,
            "tokens_per_minute": 50000,
        },
        "cache": {
            "enabled": True,
            "ttl_seconds": 300,
        },
        "priority_scoring": {
            "debounce_seconds": 5.0,
        },
        "retry": {
            "max_attempts": 3,
            "base_delay_seconds": 1.0,
            "max_delay_seconds": 30.0,
        },
        "pricing": {
            "anthropic/claude-3-haiku": {
                "input_per_million": 0.25,
                "output_per_million": 1.25,
            },
            "anthropic/claude-3.5-sonnet": {
                "input_per_million": 3.0,
                "output_per_million": 15.0,
            },
        },
    },
    "progress_summary": {
        "default_scope": "since_last",
        "last_n_count": 50,
        "time_based_days": 7,
        "max_commits": 200,
    },
    "brain_reboot": {
        "staleness_threshold_days": 7,
        "aging_threshold_days": 4,
        "export_filename": "brain_reboot.md",
    },
    "dashboard": {
        "stale_processing_seconds": 600,
        "active_timeout_minutes": 5,
    },
    "reaper": {
        "enabled": True,
        "interval_seconds": 60,
        "inactivity_timeout_seconds": 300,
        "grace_period_seconds": 300,
    },
    "archive": {
        "enabled": True,
        "retention": {
            "policy": "keep_all",
            "keep_last_n": 10,
            "days": 90,
        },
    },
    "voice_bridge": {
        "enabled": False,
        "auth": {
            "token": "",
            "localhost_bypass": True,
        },
        "network": {
            "bind_address": "127.0.0.1",
        },
        "rate_limit": {
            "requests_per_minute": 60,
        },
        "default_verbosity": "concise",
        "auto_target": False,
    },
}

# Environment variable mappings
# Maps env var name to (config_section, config_key, type_converter)
ENV_MAPPINGS = {
    "FLASK_SERVER_HOST": ("server", "host", str),
    "FLASK_SERVER_PORT": ("server", "port", int),
    "FLASK_DEBUG": ("server", "debug", lambda x: x.lower() in ("true", "1", "yes")),
    "FLASK_LOG_LEVEL": ("logging", "level", str),
    "DATABASE_HOST": ("database", "host", str),
    "DATABASE_PORT": ("database", "port", int),
    "DATABASE_NAME": ("database", "name", str),
    "DATABASE_USER": ("database", "user", str),
    "DATABASE_PASSWORD": ("database", "password", str),
    "DATABASE_POOL_SIZE": ("database", "pool_size", int),
    "DATABASE_POOL_TIMEOUT": ("database", "pool_timeout", int),
    "CLAUDE_PROJECTS_PATH": ("claude", "projects_path", str),
    "FILE_WATCHER_POLLING_INTERVAL": ("file_watcher", "polling_interval", float),
    "FILE_WATCHER_INACTIVITY_TIMEOUT": ("file_watcher", "inactivity_timeout", int),
    "FILE_WATCHER_DEBOUNCE_INTERVAL": ("file_watcher", "debounce_interval", float),
    "EVENT_SYSTEM_WRITE_RETRY_ATTEMPTS": ("event_system", "write_retry_attempts", int),
    "EVENT_SYSTEM_WRITE_RETRY_DELAY_MS": ("event_system", "write_retry_delay_ms", int),
    "EVENT_SYSTEM_MAX_RESTARTS_PER_MINUTE": ("event_system", "max_restarts_per_minute", int),
    "EVENT_SYSTEM_SHUTDOWN_TIMEOUT_SECONDS": ("event_system", "shutdown_timeout_seconds", int),
    "SSE_HEARTBEAT_INTERVAL_SECONDS": ("sse", "heartbeat_interval_seconds", int),
    "SSE_MAX_CONNECTIONS": ("sse", "max_connections", int),
    "SSE_CONNECTION_TIMEOUT_SECONDS": ("sse", "connection_timeout_seconds", int),
    "SSE_RETRY_AFTER_SECONDS": ("sse", "retry_after_seconds", int),
    "HOOKS_ENABLED": ("hooks", "enabled", lambda x: x.lower() in ("true", "1", "yes")),
    "HOOKS_POLLING_INTERVAL_WITH_HOOKS": ("hooks", "polling_interval_with_hooks", int),
    "HOOKS_FALLBACK_TIMEOUT": ("hooks", "fallback_timeout", int),
    "NOTIFICATIONS_ENABLED": ("notifications", "enabled", lambda x: x.lower() in ("true", "1", "yes")),
    "NOTIFICATIONS_SOUND": ("notifications", "sound", lambda x: x.lower() in ("true", "1", "yes")),
    "NOTIFICATIONS_RATE_LIMIT_SECONDS": ("notifications", "rate_limit_seconds", int),
    "OPENROUTER_BASE_URL": ("openrouter", "base_url", str),
    "OPENROUTER_TIMEOUT": ("openrouter", "timeout", int),
    "OPENROUTER_CALLS_PER_MINUTE": ("openrouter", "calls_per_minute", int),
    "OPENROUTER_TOKENS_PER_MINUTE": ("openrouter", "tokens_per_minute", int),
    "DASHBOARD_STALE_PROCESSING_SECONDS": ("dashboard", "stale_processing_seconds", int),
    "DASHBOARD_ACTIVE_TIMEOUT_MINUTES": ("dashboard", "active_timeout_minutes", int),
}


def deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dictionaries, with override taking precedence."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_yaml_config(config_path: Path) -> dict:
    """Load configuration from YAML file."""
    if not config_path.exists():
        return {}

    with open(config_path, "r") as f:
        content = yaml.safe_load(f)
        return content if content else {}


def apply_env_overrides(config: dict) -> dict:
    """Apply environment variable overrides to configuration."""
    result = config.copy()

    for env_var, (section, key, converter) in ENV_MAPPINGS.items():
        value = os.environ.get(env_var)
        if value is not None:
            if section not in result:
                result[section] = {}
            result[section][key] = converter(value)

    return result


def load_config(config_path: str | Path = "config.yaml") -> dict:
    """Load config: env vars > config.yaml > DEFAULTS."""
    if isinstance(config_path, str):
        config_path = Path(config_path)

    # Start with defaults
    config = DEFAULTS.copy()

    # Merge YAML config
    yaml_config = load_yaml_config(config_path)
    config = deep_merge(config, yaml_config)

    # Apply environment overrides
    config = apply_env_overrides(config)

    return config


def get_value(config: dict, *keys: str, default: Any = None) -> Any:
    """Get a nested configuration value by key path."""
    result = config
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    return result


def _extract_db_name(url: str) -> str:
    """Extract the database name from a PostgreSQL URL, stripping query params."""
    # URL format: postgresql://user[:password]@host:port/dbname[?params]
    if "/" not in url:
        return ""
    name = url.rsplit("/", 1)[-1]
    # Strip query parameters
    if "?" in name:
        name = name.split("?", 1)[0]
    return name


def get_database_url(config: dict) -> str:
    """Build database URL. DATABASE_URL env var takes precedence over config fields."""
    # DATABASE_URL takes precedence
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        _guard_production_db(database_url, config)
        return database_url

    # Build URL from individual config fields
    db = config.get("database", {})
    host = db.get("host", "localhost")
    port = db.get("port", 5432)
    name = db.get("name", "claude_headspace")
    user = db.get("user", "postgres")
    password = db.get("password", "")

    if password:
        url = f"postgresql://{user}:{password}@{host}:{port}/{name}"
    else:
        url = f"postgresql://{user}@{host}:{port}/{name}"

    _guard_production_db(url, config)
    return url


def _guard_production_db(database_url: str, config: dict) -> None:
    """Raise RuntimeError if tests are trying to connect to a non-test database.

    Convention: test databases MUST have a name ending with '_test'.
    This mirrors the Rails convention and prevents any test from accidentally
    connecting to development or production databases.
    """
    import sys
    if "_pytest" not in sys.modules and "pytest" not in sys.modules:
        return  # Not running under pytest — allow anything

    db_name = _extract_db_name(database_url)
    if not db_name:
        return  # Can't determine name — allow (may be in-memory or custom)

    if not db_name.endswith("_test"):
        raise RuntimeError(
            f"SAFETY GUARD: Refusing to connect to database '{db_name}' "
            f"during test run. Test databases MUST have names ending with "
            f"'_test' (e.g. '{db_name}_test'). Set the DATABASE_URL "
            f"environment variable to a test database URL."
        )


def mask_database_url(url: str) -> str:
    """Mask the password in a database URL for safe logging."""
    import re
    # Match postgresql://user:password@host pattern
    return re.sub(r"(postgresql://[^:]+:)[^@]+(@)", r"\1***\2", url)


def get_claude_projects_path(config: dict) -> str:
    """Get the expanded path to Claude Code projects directory."""
    path = get_value(config, "claude", "projects_path", default="~/.claude/projects")
    return os.path.expanduser(path)


def get_file_watcher_config(config: dict) -> dict:
    """Get file watcher configuration with defaults."""
    return {
        "polling_interval": get_value(
            config, "file_watcher", "polling_interval", default=2
        ),
        "reconciliation_interval": get_value(
            config, "file_watcher", "reconciliation_interval", default=60
        ),
        "inactivity_timeout": get_value(
            config, "file_watcher", "inactivity_timeout", default=5400
        ),
        "debounce_interval": get_value(
            config, "file_watcher", "debounce_interval", default=0.5
        ),
        "awaiting_input_timeout": get_value(
            config, "file_watcher", "awaiting_input_timeout", default=10
        ),
    }


def get_notifications_config(config: dict) -> dict:
    """Get notifications configuration with defaults."""
    events = config.get("notifications", {}).get("events", {})
    return {
        "enabled": get_value(
            config, "notifications", "enabled", default=True
        ),
        "sound": get_value(
            config, "notifications", "sound", default=True
        ),
        "events": {
            "task_complete": events.get("task_complete", True),
            "awaiting_input": events.get("awaiting_input", True),
        },
        "rate_limit_seconds": get_value(
            config, "notifications", "rate_limit_seconds", default=5
        ),
        "dashboard_url": get_value(
            config, "notifications", "dashboard_url", default="http://localhost:5055"
        ),
    }
