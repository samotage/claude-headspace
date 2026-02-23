"""Flask application factory."""

import logging
import logging.config
import os
import threading
import time
from pathlib import Path

from flask import Flask, render_template, request, jsonify

from . import __version__
from .config import load_config, get_value, get_database_url, get_notifications_config
from .database import db, init_database


def setup_logging(config: dict, app_root: Path) -> None:
    """Configure structured logging to console and file."""
    log_level = get_value(config, "logging", "level", default="INFO")
    log_file = get_value(config, "logging", "file", default="logs/app.log")
    max_bytes = get_value(config, "logging", "max_bytes", default=10_000_000)  # 10MB
    backup_count = get_value(config, "logging", "backup_count", default=5)

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
                "class": "logging.handlers.RotatingFileHandler",
                "level": log_level,
                "formatter": "standard",
                "filename": str(log_path),
                "maxBytes": max_bytes,
                "backupCount": backup_count,
            },
        },
        "root": {
            "level": log_level,
            "handlers": ["console", "file"],
        },
    }

    logging.config.dictConfig(logging_config)


def create_app(config_path: str = "config.yaml", testing: bool = False) -> Flask:
    """
    Create and configure the Flask application.

    Args:
        config_path: Path to the YAML configuration file
        testing: If True, skip background services and orphan cleanup.
            Must be passed by test fixtures BEFORE creation so safety
            gates work during initialization (not after).

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

    # TESTING must be set before any safety-gated code runs.
    # Setting it after create_app() returns is too late — background services
    # and cleanup_orphaned_sessions() will have already executed.
    if testing:
        app.config["TESTING"] = True

    # Configure Flask
    app.config["DEBUG"] = get_value(config, "server", "debug", default=False)
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 0
    app.config["APP_CONFIG"] = config
    app.config["APP_VERSION"] = __version__
    app.config["APP_ROOT"] = str(app_root)

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

    # Initialize headspace monitor (requires database for snapshot persistence)
    if db_connected:
        from .services.headspace_monitor import HeadspaceMonitor
        headspace_monitor = HeadspaceMonitor(app=app, config=config)
        app.extensions["headspace_monitor"] = headspace_monitor
        logger.info("Headspace monitor initialized (enabled=%s)", headspace_monitor.enabled)
    else:
        app.extensions["headspace_monitor"] = None
        logger.debug("Headspace monitor disabled (no database connection)")

    # Initialize priority scoring service (requires database for agent queries)
    if db_connected:
        from .services.priority_scoring import PriorityScoringService
        priority_scoring_service = PriorityScoringService(
            inference_service=inference_service,
            app=app,
            config=config,
        )
        app.extensions["priority_scoring_service"] = priority_scoring_service
        logger.info("Priority scoring service initialized")
    else:
        app.extensions["priority_scoring_service"] = None
        logger.debug("Priority scoring service disabled (no database connection)")

    # Initialize notification service from config
    from .services.notification_service import (
        NotificationPreferences, configure_notification_service, get_notification_service,
    )
    notif_config = get_notifications_config(config)
    # Derive dashboard_url: prefer application_url (Tailscale hostname for browsers/notifications),
    # then fall back to notifications config, then construct from server host/port
    server_host = get_value(config, "server", "host", default="127.0.0.1")
    server_port = get_value(config, "server", "port", default=5055)
    browser_host = "127.0.0.1" if server_host == "0.0.0.0" else server_host
    dashboard_url = (
        get_value(config, "server", "application_url", default=None)
        or notif_config.get("dashboard_url")
        or f"https://{browser_host}:{server_port}"
    )
    configure_notification_service(NotificationPreferences(
        enabled=notif_config.get("enabled", True),
        sound=notif_config.get("sound", True),
        events=notif_config.get("events", {"command_complete": True, "awaiting_input": True}),
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

    # Initialize staleness service (requires database for command queries)
    if db_connected:
        from .services.staleness import StalenessService
        staleness_service = StalenessService(app=app)
        app.extensions["staleness_service"] = staleness_service
        logger.info("Staleness service initialized")
    else:
        app.extensions["staleness_service"] = None
        logger.debug("Staleness service disabled (no database connection)")

    # Initialize file watcher — fallback monitoring mechanism.
    # The file watcher polls .jsonl and transcript files to catch events
    # that hooks miss. Disabled by default since hooks are the primary path.
    # Enable via file_watcher.enabled in config.yaml or the /config dashboard.
    fw_enabled = get_value(config, "file_watcher", "enabled", default=False)
    if not app.config.get("TESTING") and fw_enabled:
        from .services.file_watcher import init_file_watcher
        init_file_watcher(app, config)
        logger.info("File watcher initialized (fallback monitoring enabled)")
    elif not app.config.get("TESTING"):
        logger.info("File watcher disabled (hooks are the primary event path)")

    # Clean up orphaned tmux sessions on startup (only in non-testing environments)
    if not app.config.get("TESTING") and db_connected:
        try:
            from .services.agent_lifecycle import cleanup_orphaned_sessions
            with app.app_context():
                killed = cleanup_orphaned_sessions()
                if killed:
                    logger.info(f"Startup: cleaned up {killed} orphaned tmux session(s)")
        except Exception as e:
            logger.warning(f"Startup orphan cleanup failed (non-fatal): {e}")

    # Initialize agent reaper (only in non-testing environments, requires database)
    if not app.config.get("TESTING") and db_connected:
        from .services.agent_reaper import AgentReaper
        reaper = AgentReaper(app=app, config=config)
        reaper.start()
        app.extensions["agent_reaper"] = reaper

    # Initialize context poller (only in non-testing environments, requires database)
    if not app.config.get("TESTING") and db_connected:
        from .services.context_poller import ContextPoller
        context_poller = ContextPoller(app=app, config=config)
        context_poller.start()
        app.extensions["context_poller"] = context_poller

    # Initialize activity aggregator (only in non-testing environments, requires database)
    if not app.config.get("TESTING") and db_connected:
        from .services.activity_aggregator import ActivityAggregator
        aggregator = ActivityAggregator(app=app, config=config)
        aggregator.start()
        app.extensions["activity_aggregator"] = aggregator

    # Register tmux bridge module (stateless, no init needed)
    from .services import tmux_bridge
    app.extensions["tmux_bridge"] = tmux_bridge

    # Initialize handoff executor (requires tmux bridge and database)
    from .services.handoff_executor import HandoffExecutor
    handoff_executor = HandoffExecutor(app=app)
    app.extensions["handoff_executor"] = handoff_executor
    logger.info("Handoff executor initialized")

    # Initialize file upload service
    from .services.file_upload import FileUploadService
    file_upload_service = FileUploadService(config=config, app_root=str(app_root))
    app.extensions["file_upload"] = file_upload_service
    if not app.config.get("TESTING"):
        file_upload_service.startup_sweep()
    logger.info("File upload service initialized (dir=%s)", file_upload_service.upload_dir)

    # Initialize voice bridge services
    vb_enabled = get_value(config, "voice_bridge", "enabled", default=False)
    if vb_enabled:
        from .services.voice_auth import VoiceAuth
        voice_auth = VoiceAuth(config=config)
        app.extensions["voice_auth"] = voice_auth
        logger.info("Voice auth service initialized")

        from .services.voice_formatter import VoiceFormatter
        voice_formatter = VoiceFormatter(
            config=config,
            inference_service=inference_service,
        )
        app.extensions["voice_formatter"] = voice_formatter
        logger.info("Voice formatter service initialized")
    else:
        app.extensions["voice_auth"] = None
        app.extensions["voice_formatter"] = None

    # Initialize commander availability tracker (uses tmux_bridge internally)
    from .services.commander_availability import CommanderAvailability
    commander_availability = CommanderAvailability(app=app, config=config)
    app.extensions["commander_availability"] = commander_availability
    if not app.config.get("TESTING"):
        commander_availability.start()
    logger.info("Commander availability service initialized")

    # Initialize tmux watchdog (near-real-time turn gap detection)
    from .services.tmux_watchdog import TmuxWatchdog
    tmux_watchdog = TmuxWatchdog(app=app, config=config)
    app.extensions["tmux_watchdog"] = tmux_watchdog
    if not app.config.get("TESTING"):
        tmux_watchdog.start()
    logger.info("Tmux watchdog service initialized")

    # Background thread health monitor
    _thread_health_stop = threading.Event()

    def _get_background_thread_status():
        """Get the alive status of all background threads."""
        status = {}
        for name in ("agent_reaper", "activity_aggregator", "file_watcher", "commander_availability", "context_poller", "tmux_watchdog"):
            svc = app.extensions.get(name)
            if svc is None:
                status[name] = "disabled"
            elif hasattr(svc, "_thread") and isinstance(svc._thread, threading.Thread):
                status[name] = "alive" if svc._thread.is_alive() else "dead"
            elif hasattr(svc, "thread") and isinstance(svc.thread, threading.Thread):
                status[name] = "alive" if svc.thread.is_alive() else "dead"
            elif hasattr(svc, "_observer") and isinstance(svc._observer, threading.Thread):
                status[name] = "alive" if svc._observer.is_alive() else "dead"
            else:
                status[name] = "unknown"
        return status

    app.extensions["_get_background_thread_status"] = _get_background_thread_status

    def _thread_health_loop():
        while not _thread_health_stop.wait(60):
            status = _get_background_thread_status()
            dead = [k for k, v in status.items() if v == "dead"]
            if dead:
                logger.warning(f"Background threads dead: {', '.join(dead)}")

    if not app.config.get("TESTING"):
        health_thread = threading.Thread(target=_thread_health_loop, daemon=True, name="thread-health")
        health_thread.start()

    # Register shutdown cleanup
    import atexit

    @atexit.register
    def cleanup():
        # Wrap in try-except as logging may be shut down during atexit
        try:
            _thread_health_stop.set()
            shutdown_broadcaster()
            if "agent_reaper" in app.extensions:
                app.extensions["agent_reaper"].stop()
            if "activity_aggregator" in app.extensions:
                app.extensions["activity_aggregator"].stop()
            if "file_watcher" in app.extensions:
                app.extensions["file_watcher"].stop()
            if "commander_availability" in app.extensions:
                app.extensions["commander_availability"].stop()
            if "tmux_watchdog" in app.extensions:
                app.extensions["tmux_watchdog"].stop()
            if "context_poller" in app.extensions:
                app.extensions["context_poller"].stop()
            # Stop event writer to close database connections
            event_writer = app.extensions.get("event_writer")
            if event_writer:
                event_writer.stop()
            # Dispose inference service engine
            inference_svc = app.extensions.get("inference_service")
            if inference_svc:
                inference_svc.stop()
        except Exception as e:
            logger.warning(f"Error during shutdown cleanup: {e}")

    # Compute cache bust once at startup (not per-render)
    app.config["CACHE_BUST"] = int(time.time())

    # CSRF protection — use a secure secret key in non-debug mode
    from itsdangerous import URLSafeTimedSerializer
    secret_key = app.config.get("SECRET_KEY")
    if not secret_key:
        if app.config["DEBUG"]:
            secret_key = "dev-secret-key"
        else:
            secret_key = os.urandom(32).hex()
            logger.warning("No SECRET_KEY configured — using a generated key (will not persist across restarts)")
    app.config["SECRET_KEY"] = secret_key
    csrf_serializer = URLSafeTimedSerializer(secret_key)

    @app.context_processor
    def inject_template_globals():
        token = csrf_serializer.dumps("csrf-token", salt="csrf-salt")
        return {
            "cache_bust": app.config["CACHE_BUST"],
            "csrf_token": token,
        }

    # CSRF exempt paths (hooks, SSE, and voice bridge API)
    _CSRF_EXEMPT_PREFIXES = ("/hook/", "/api/events/stream", "/api/sessions", "/api/voice/", "/api/agents", "/api/focus/", "/api/respond/", "/api/personas/")

    @app.before_request
    def verify_csrf_token():
        if app.config.get("TESTING"):
            return None
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return None
        # Exempt hook endpoints and SSE
        for prefix in _CSRF_EXEMPT_PREFIXES:
            if request.path.startswith(prefix):
                return None
        token = request.headers.get("X-CSRF-Token")
        if not token:
            return jsonify({"error": "Missing CSRF token"}), 403
        try:
            csrf_serializer.loads(token, salt="csrf-salt", max_age=86400 * 7)
        except Exception:
            return jsonify({"error": "Invalid or expired CSRF token"}), 403
        return None

    # Register error handlers
    register_error_handlers(app)

    # Register blueprints
    register_blueprints(app)

    # Register CLI command groups
    register_cli_commands(app)

    return app


def register_error_handlers(app: Flask) -> None:
    """Register error handlers for 404 and 500 errors."""

    @app.errorhandler(404)
    def not_found_error(error):
        return render_template(
            "errors/404.html",
            status_counts={"input_needed": 0, "working": 0, "idle": 0},
        ), 404

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
    from .routes.agents import agents_bp
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
    from .routes.personas import personas_bp
    from .routes.priority import priority_bp
    from .routes.progress_summary import progress_summary_bp
    from .routes.projects import projects_bp
    from .routes.respond import respond_bp
    from .routes.sessions import sessions_bp
    from .routes.sse import sse_bp
    from .routes.summarisation import summarisation_bp
    from .routes.voice_bridge import voice_bridge_bp
    from .routes.waypoint import waypoint_bp

    app.register_blueprint(activity_bp)
    app.register_blueprint(agents_bp)
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
    app.register_blueprint(personas_bp)
    app.register_blueprint(priority_bp)
    app.register_blueprint(progress_summary_bp)
    app.register_blueprint(projects_bp)
    app.register_blueprint(respond_bp)
    app.register_blueprint(sessions_bp)
    app.register_blueprint(sse_bp)
    app.register_blueprint(summarisation_bp)
    app.register_blueprint(voice_bridge_bp)
    app.register_blueprint(waypoint_bp)


def register_cli_commands(app: Flask) -> None:
    """Register Flask CLI command groups."""
    from .cli.persona_cli import persona_cli

    app.cli.add_command(persona_cli)
