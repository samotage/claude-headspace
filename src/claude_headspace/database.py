"""Database setup and utilities using Flask-SQLAlchemy."""

import logging
from typing import Tuple

from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import text

from .config import get_database_url, get_value, mask_database_url

logger = logging.getLogger(__name__)

# SQLAlchemy instance - imported by models and app
db = SQLAlchemy()

# Flask-Migrate instance
migrate = Migrate()


def init_database(app: Flask, config: dict) -> bool:
    """
    Initialize database connection and Flask-Migrate.

    Args:
        app: Flask application instance
        config: Application configuration dictionary

    Returns:
        True if database connection successful, False otherwise
    """
    # Build database URL
    database_url = get_database_url(config)
    masked_url = mask_database_url(database_url)

    # Configure SQLAlchemy
    app.config["SQLALCHEMY_DATABASE_URI"] = database_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    # Configure connection pooling
    db_config = config.get("database", {})
    pool_size = get_value(config, "database", "pool_size", default=10)
    pool_timeout = get_value(config, "database", "pool_timeout", default=30)

    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_size": pool_size,
        "pool_timeout": pool_timeout,
        "pool_recycle": 3600,  # Recycle connections after 1 hour
        "pool_pre_ping": True,  # Verify connections before use
        "connect_args": {
            "connect_timeout": 5,  # 5 second connection timeout
        },
    }

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # Verify database connection
    connected = verify_connection(app)

    if connected:
        logger.info(f"Database connected to {masked_url}")
    else:
        logger.error(f"Database connection failed: {masked_url}")

    return connected


def verify_connection(app: Flask) -> bool:
    """
    Verify database connectivity by executing a simple query.

    Args:
        app: Flask application instance

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with app.app_context():
            db.session.execute(text("SELECT 1"))
            db.session.commit()
        return True
    except Exception as e:
        logger.error(f"Database connection verification failed: {e}")
        return False


def check_database_health() -> Tuple[bool, str | None]:
    """
    Check database connectivity for health checks.

    Returns:
        Tuple of (is_connected, error_message)
        - (True, None) if connected
        - (False, error_string) if disconnected
    """
    try:
        db.session.execute(text("SELECT 1"))
        db.session.commit()
        return True, None
    except Exception as e:
        # Don't expose full error details, just the type and brief message
        error_msg = f"{type(e).__name__}: {str(e)[:100]}"
        return False, error_msg
