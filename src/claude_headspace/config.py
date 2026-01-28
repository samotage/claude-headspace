"""Configuration loader with YAML and environment variable support."""

import os
from pathlib import Path
from typing import Any

import yaml


# Default configuration values
DEFAULTS = {
    "server": {
        "host": "127.0.0.1",
        "port": 5050,
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
    """
    Load configuration with the following precedence (highest to lowest):
    1. Environment variables
    2. config.yaml values
    3. Default values

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Merged configuration dictionary
    """
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
    """
    Get a nested configuration value.

    Args:
        config: Configuration dictionary
        keys: Sequence of keys to traverse
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    result = config
    for key in keys:
        if isinstance(result, dict) and key in result:
            result = result[key]
        else:
            return default
    return result


def get_database_url(config: dict) -> str:
    """
    Build the database URL from configuration.

    DATABASE_URL environment variable takes precedence over individual config fields.

    Args:
        config: Configuration dictionary

    Returns:
        PostgreSQL connection URL
    """
    # DATABASE_URL takes precedence
    database_url = os.environ.get("DATABASE_URL")
    if database_url:
        return database_url

    # Build URL from individual config fields
    db = config.get("database", {})
    host = db.get("host", "localhost")
    port = db.get("port", 5432)
    name = db.get("name", "claude_headspace")
    user = db.get("user", "postgres")
    password = db.get("password", "")

    if password:
        return f"postgresql://{user}:{password}@{host}:{port}/{name}"
    return f"postgresql://{user}@{host}:{port}/{name}"


def mask_database_url(url: str) -> str:
    """
    Mask the password in a database URL for safe logging.

    Args:
        url: Database URL that may contain a password

    Returns:
        URL with password replaced by ***
    """
    import re
    # Match postgresql://user:password@host pattern
    return re.sub(r"(postgresql://[^:]+:)[^@]+(@)", r"\1***\2", url)
