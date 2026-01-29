"""Flask application factory."""

import logging
import logging.config
import os
from pathlib import Path

from flask import Flask, render_template

from . import __version__
from .config import load_config, get_value
from .database import init_database


def setup_logging(config: dict, app_root: Path) -> None:
    """Configure structured logging to console and file."""
    log_level = get_value(config, "logging", "level", default="INFO")
    log_file = get_value(config, "logging", "file", default="logs/app.log")

    # Ensure logs directory exists
    log_path = app_root / log_file
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s - %(levelname)s - %(name)s - %(message)s",
                "datefmt": "%Y-%m-%dT%H:%M:%S%z",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "level": log_level,
                "formatter": "standard",
                "stream": "ext://sys.stdout",
            },
            "file": {
                "class": "logging.FileHandler",
                "level": log_level,
                "formatter": "standard",
                "filename": str(log_path),
                "mode": "a",
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"],
        },
    }

    logging.config.dictConfig(logging_config)


def create_app(config_path: str = "config.yaml") -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_path: Path to the YAML configuration file

    Returns:
        Configured Flask application instance
    """
    # Determine the application root directory
    app_root = Path(config_path).parent.absolute()
    if not app_root.exists():
        app_root = Path.cwd()

    # Load configuration
    config = load_config(config_path)

    # Create Flask app with correct template and static paths
    template_folder = app_root / "templates"
    static_folder = app_root / "static"

    app = Flask(
        __name__,
        template_folder=str(template_folder),
        static_folder=str(static_folder),
    )

    # Configure Flask
    app.config["DEBUG"] = get_value(config, "server", "debug", default=False)
    app.config["APP_CONFIG"] = config
    app.config["APP_VERSION"] = __version__

    # Setup logging
    setup_logging(config, app_root)
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Claude Headspace v{__version__}")

    # Initialize database (continues even if connection fails)
    db_connected = init_database(app, config)
    app.config["DATABASE_CONNECTED"] = db_connected

    # Register error handlers
    register_error_handlers(app)

    # Register blueprints
    register_blueprints(app)

    return app


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for 404 and 500 errors."""

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):
        # In production, don't expose error details
        if not app.debug:
            return render_template("errors/500.html"), 500
        # In debug mode, let Flask's default handler show details
        raise error


def register_blueprints(app: Flask) -> None:
    """Register application blueprints."""
    from .routes.config import config_bp
    from .routes.dashboard import dashboard_bp
    from .routes.focus import focus_bp
    from .routes.health import health_bp
    from .routes.help import help_bp
    from .routes.hooks import hooks_bp
    from .routes.logging import logging_bp
    from .routes.notifications import notifications_bp
    from .routes.objective import objective_bp
    from .routes.sessions import sessions_bp
    from .routes.waypoint import waypoint_bp

    app.register_blueprint(config_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(focus_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(hooks_bp)
    app.register_blueprint(logging_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(objective_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(waypoint_bp)
