"""Config API routes for editing configuration."""

import logging

from flask import Blueprint, current_app, jsonify, render_template, request

from ..services.config_editor import (
    get_config_schema,
    load_config_file,
    merge_with_defaults,
    save_config_file,
    validate_config,
)

logger = logging.getLogger(__name__)

config_bp = Blueprint("config", __name__)


@config_bp.route("/config")
def config_page():
    """Render the configuration editing page."""
    # Load current config from file (not env vars)
    config = load_config_file()
    config = merge_with_defaults(config)

    # Get schema for form generation
    schema = get_config_schema()

    # Provide status_counts for header partial (defaults for non-dashboard pages)
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}

    return render_template(
        "config.html",
        config=config,
        schema=schema,
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
