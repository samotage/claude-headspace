"""Flask application factory."""

import logging
import logging.config
import os
import time
from pathlib import Path

from flask import Flask, render_template

from . import __version__
from .config import load_config, get_value, get_database_url, get_notifications_config
from .database import db, init_database


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
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["APP_CONFIG"] = config
    app.config["APP_VERSION"] = __version__

    # Setup logging
    setup_logging(config, app_root)
    logger = logging.getLogger(__name__)
    logger.info(f"Starting Claude Headspace v{__version__}")

    # Initialize database (continues even if connection fails)
    db_connected = init_database(app, config)
    app.config["DATABASE_CONNECTED"] = db_connected

    # Initialize event writer for audit logging (only if database connected)
    if db_connected:
        from .services.event_writer import create_event_writer
        try:
            db_url = get_database_url(config)
            event_writer = create_event_writer(db_url, config)
            app.extensions["event_writer"] = event_writer
            logger.info("Event writer initialized for audit logging")
        except Exception as e:
            logger.warning(f"Event writer initialization failed (non-fatal): {e}")
            app.extensions["event_writer"] = None
    else:
        app.extensions["event_writer"] = None
        logger.debug("Event writer disabled (no database connection)")

    # Initialize broadcaster for SSE
    from .services.broadcaster import init_broadcaster, shutdown_broadcaster
    broadcaster = init_broadcaster(config)
    app.extensions["broadcaster"] = broadcaster
    logger.info("SSE broadcaster initialized")

    # Initialize git metadata service
    from .services.git_metadata import GitMetadata
    git_metadata = GitMetadata()
    app.extensions["git_metadata"] = git_metadata
    logger.info("Git metadata service initialized")

    # Initialize inference service
    from .services.inference_service import InferenceService
    inference_service = InferenceService(
        config=config,
        database_url=get_database_url(config) if db_connected else None,
    )
    app.extensions["inference_service"] = inference_service
    if inference_service.is_available:
        logger.info("Inference service initialized (OpenRouter configured)")
    else:
        logger.warning("Inference service initialized in degraded mode (no API key)")

    # Initialize summarisation service
    from .services.summarisation_service import SummarisationService
    summarisation_service = SummarisationService(
        inference_service=inference_service,
        config=config,
    )
    app.extensions["summarisation_service"] = summarisation_service
    logger.info("Summarisation service initialized")

    # Initialize headspace monitor
    from .services.headspace_monitor import HeadspaceMonitor
    headspace_monitor = HeadspaceMonitor(app=app, config=config)
    app.extensions["headspace_monitor"] = headspace_monitor
    logger.info("Headspace monitor initialized (enabled=%s)", headspace_monitor.enabled)

    # Initialize priority scoring service
    from .services.priority_scoring import PriorityScoringService
    priority_scoring_service = PriorityScoringService(
        inference_service=inference_service,
        app=app,
        config=config,
    )
    app.extensions["priority_scoring_service"] = priority_scoring_service
    logger.info("Priority scoring service initialized")

    # Initialize notification service from config
    from .services.notification_service import (
        NotificationPreferences, configure_notification_service, get_notification_service,
    )
    notif_config = get_notifications_config(config)
    # Derive dashboard_url from server config if not explicitly set in notifications
    server_host = get_value(config, "server", "host", default="127.0.0.1")
    server_port = get_value(config, "server", "port", default=5055)
    # Use 127.0.0.1 for browser access when host is 0.0.0.0
    browser_host = "127.0.0.1" if server_host == "0.0.0.0" else server_host
    dashboard_url = notif_config.get("dashboard_url") or f"http://{browser_host}:{server_port}"
    configure_notification_service(NotificationPreferences(
        enabled=notif_config.get("enabled", True),
        sound=notif_config.get("sound", True),
        events=notif_config.get("events", {"task_complete": True, "awaiting_input": True}),
        rate_limit_seconds=notif_config.get("rate_limit_seconds", 5),
        dashboard_url=dashboard_url,
    ))
    notification_service = get_notification_service()
    app.extensions["notification_service"] = notification_service
    # Eagerly check terminal-notifier availability for startup diagnostics
    notification_service.is_available()
    logger.info(f"Notification service initialized (dashboard_url={dashboard_url})")

    # Initialize archive service
    from .services.archive_service import ArchiveService
    archive_service = ArchiveService(config=config)
    app.extensions["archive_service"] = archive_service
    logger.info("Archive service initialized")

    # Initialize progress summary service
    from .services.progress_summary import ProgressSummaryService
    progress_summary_service = ProgressSummaryService(
        inference_service=inference_service,
        app=app,
        archive_service=archive_service,
    )
    app.extensions["progress_summary_service"] = progress_summary_service
    logger.info("Progress summary service initialized")

    # Initialize brain reboot service
    from .services.brain_reboot import BrainRebootService
    brain_reboot_service = BrainRebootService(
        app=app,
        archive_service=archive_service,
    )
    app.extensions["brain_reboot_service"] = brain_reboot_service
    logger.info("Brain reboot service initialized")

    # Initialize staleness service
    from .services.staleness import StalenessService
    staleness_service = StalenessService(app=app)
    app.extensions["staleness_service"] = staleness_service
    logger.info("Staleness service initialized")

    # Initialize file watcher (only in non-testing environments)
    if not app.config.get("TESTING"):
        from .services.file_watcher import init_file_watcher
        init_file_watcher(app, config)
        logger.info("File watcher initialized")

    # Initialize agent reaper (only in non-testing environments)
    if not app.config.get("TESTING"):
        from .services.agent_reaper import AgentReaper
        reaper = AgentReaper(app=app, config=config)
        reaper.start()
        app.extensions["agent_reaper"] = reaper

    # Initialize activity aggregator (only in non-testing environments)
    if not app.config.get("TESTING"):
        from .services.activity_aggregator import ActivityAggregator
        aggregator = ActivityAggregator(app=app, config=config)
        aggregator.start()
        app.extensions["activity_aggregator"] = aggregator

    # Register shutdown cleanup
    import atexit

    @atexit.register
    def cleanup():
        # Wrap in try-except as logging may be shut down during atexit
        try:
            shutdown_broadcaster()
            if "agent_reaper" in app.extensions:
                app.extensions["agent_reaper"].stop()
            if "activity_aggregator" in app.extensions:
                app.extensions["activity_aggregator"].stop()
            if "file_watcher" in app.extensions:
                app.extensions["file_watcher"].stop()
            # Stop event writer to close database connections
            event_writer = app.extensions.get("event_writer")
            if event_writer:
                event_writer.stop()
        except Exception:
            pass  # Ignore errors during shutdown

    # Register context processor for cache busting
    @app.context_processor
    def inject_cache_bust():
        return {"cache_bust": int(time.time())}

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
    from .routes.activity import activity_bp
    from .routes.archive import archive_bp
    from .routes.brain_reboot import brain_reboot_bp
    from .routes.config import config_bp
    from .routes.dashboard import dashboard_bp
    from .routes.focus import focus_bp
    from .routes.headspace import headspace_bp
    from .routes.health import health_bp
    from .routes.help import help_bp
    from .routes.hooks import hooks_bp
    from .routes.inference import inference_bp
    from .routes.logging import logging_bp
    from .routes.notifications import notifications_bp
    from .routes.objective import objective_bp
    from .routes.priority import priority_bp
    from .routes.progress_summary import progress_summary_bp
    from .routes.projects import projects_bp
    from .routes.sessions import sessions_bp
    from .routes.sse import sse_bp
    from .routes.summarisation import summarisation_bp
    from .routes.waypoint import waypoint_bp

    app.register_blueprint(activity_bp)
    app.register_blueprint(archive_bp)
    app.register_blueprint(brain_reboot_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(focus_bp)
    app.register_blueprint(headspace_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(help_bp)
    app.register_blueprint(hooks_bp)
    app.register_blueprint(inference_bp)
    app.register_blueprint(logging_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(objective_bp)
    app.register_blueprint(priority_bp)
    app.register_blueprint(progress_summary_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(sse_bp)
    app.register_blueprint(summarisation_bp)
    app.register_blueprint(waypoint_bp)
