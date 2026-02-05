"""Config API routes for editing configuration."""

import logging
import os
import subprocess
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from ..services.config_editor import (
    flatten_nested_sections,
    get_config_schema,
    load_config_file,
    merge_with_defaults,
    save_config_file,
    unflatten_nested_sections,
    validate_config,
)

logger = logging.getLogger(__name__)

config_bp = Blueprint("config", __name__)


@config_bp.route("/config")
def config_page():
    """Render the configuration editing page."""
    # Load current config from file (not env vars)
    config = load_config_file()
    # Flatten nested openrouter keys for the flat section[field] editor
    flatten_nested_sections(config)
    config = merge_with_defaults(config)

    # Get schema for form generation
    schema = get_config_schema()

    # Check if inference service is available (API key configured)
    inference_available = current_app.extensions.get("inference_service") is not None

    # Provide status_counts for header partial (defaults for non-dashboard pages)
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}

    return render_template(
        "config.html",
        config=config,
        schema=schema,
        inference_available=inference_available,
        status_counts=status_counts,
    )


@config_bp.route("/api/config", methods=["GET"])
def get_config():
    """
    Get current configuration as JSON.

    Returns file values only, excludes environment variable overrides.

    Returns:
        200: Configuration JSON
    """
    try:
        # Load from file only (no env vars)
        config = load_config_file()
        # Flatten nested openrouter keys for the flat section[field] editor
        flatten_nested_sections(config)
        config = merge_with_defaults(config)

        # Get schema for field metadata
        schema = get_config_schema()

        return jsonify({
            "status": "ok",
            "config": config,
            "schema": schema,
        }), 200

    except Exception as e:
        logger.exception(f"Error loading config: {e}")
        return jsonify({
            "status": "error",
            "message": "Failed to load configuration",
        }), 500


@config_bp.route("/api/config", methods=["POST"])
def save_config():
    """
    Save configuration to config.yaml.

    Validates all fields before saving. Performs atomic write.
    Password values are never logged.

    Expected payload:
    {
        "server": {...},
        "logging": {...},
        ...
    }

    Returns:
        200: Configuration saved successfully
        400: Validation errors
        500: Save failed
    """
    if request.headers.get("X-Confirm-Destructive") != "true":
        return jsonify({
            "status": "error",
            "message": "Config write requires X-Confirm-Destructive header",
        }), 403

    if not request.is_json:
        return jsonify({
            "status": "error",
            "message": "Content-Type must be application/json",
        }), 400

    config = request.get_json(silent=True)
    if config is None:
        return jsonify({
            "status": "error",
            "message": "Invalid JSON payload",
        }), 400

    # Validate configuration
    result = validate_config(config)

    if not result.valid:
        # Return structured validation errors
        errors = [
            {
                "section": e.section,
                "field": e.field,
                "message": e.message,
            }
            for e in result.errors
        ]
        return jsonify({
            "status": "error",
            "message": "Validation failed",
            "errors": errors,
        }), 400

    # Merge with defaults to ensure complete config
    config = merge_with_defaults(config)

    # Unflatten dot-notation openrouter keys back to nested dicts for YAML
    unflatten_nested_sections(config)

    # Preserve non-schema sections and fields from the original file
    original = load_config_file()
    # Preserve top-level sections not in CONFIG_SCHEMA (e.g. dashboard, reaper)
    schema_sections = {s["name"] for s in get_config_schema()}
    for key, value in original.items():
        if key not in schema_sections:
            config[key] = value
    # Deep-merge nested sections to preserve non-schema sub-keys
    for nested_section in ["openrouter", "headspace"]:
        original_nested = original.get(nested_section, {})
        config_nested = config.get(nested_section, {})
        for key, value in original_nested.items():
            if isinstance(value, dict) and key in config_nested and isinstance(config_nested[key], dict):
                for subkey, subvalue in value.items():
                    if subkey not in config_nested[key]:
                        config_nested[key][subkey] = subvalue
            elif key not in config_nested:
                config_nested[key] = value

    # Save configuration atomically
    success, error_message = save_config_file(config)

    if success:
        logger.info("Configuration saved successfully")
        return jsonify({
            "status": "ok",
            "message": "Configuration saved",
            "requires_restart": True,
        }), 200
    else:
        return jsonify({
            "status": "error",
            "message": error_message or "Failed to save configuration",
        }), 500


@config_bp.route("/api/config/restart", methods=["POST"])
def restart_server():
    """
    Restart the server by launching restart_server.sh.

    The script is launched detached so it survives the parent process dying.

    Returns:
        200: Restart initiated
        500: Script not found or launch failed
    """
    if request.headers.get("X-Confirm-Destructive") != "true":
        return jsonify({
            "status": "error",
            "message": "Server restart requires X-Confirm-Destructive header",
        }), 403

    app_root = Path(current_app.config.get("APP_ROOT", "."))
    script = app_root / "restart_server.sh"

    if not script.is_file():
        logger.error("restart_server.sh not found at %s", script)
        return jsonify({
            "status": "error",
            "message": "restart_server.sh not found",
        }), 500

    try:
        # Strip Werkzeug reloader env vars so the new server starts fresh.
        # The request handler runs inside Werkzeug's reloader child which sets
        # WERKZEUG_RUN_MAIN and WERKZEUG_SERVER_FD.  If these leak into the
        # new python3 process it skips the reloader and tries to reuse a dead
        # file descriptor, crashing on startup.
        clean_env = {
            k: v for k, v in os.environ.items()
            if not k.startswith("WERKZEUG_")
        }
        subprocess.Popen(
            [str(script)],
            cwd=str(app_root),
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=clean_env,
        )
        logger.info("Server restart initiated via restart_server.sh")
        return jsonify({
            "status": "ok",
            "message": "Restart initiated",
        }), 200
    except OSError as e:
        logger.exception("Failed to launch restart_server.sh: %s", e)
        return jsonify({
            "status": "error",
            "message": f"Failed to launch restart script: {e}",
        }), 500
