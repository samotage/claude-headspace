#!/usr/bin/env python3
"""Background watcher process for Claude Headspace event system.

This process runs independently of the Flask web server and:
1. Runs the file watcher to detect new turns in Claude Code sessions
2. Writes detected events to Postgres via the EventWriter
3. Handles graceful shutdown on SIGTERM/SIGINT
"""

import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

from claude_headspace.config import (
    get_claude_projects_path,
    get_database_url,
    get_event_system_config,
    get_file_watcher_config,
    load_config,
)
from claude_headspace.services.event_writer import create_event_writer
from claude_headspace.services.file_watcher import FileWatcher
from claude_headspace.services.process_monitor import (
    DEFAULT_PID_FILE,
    remove_pid_file,
    write_pid_file,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)


class WatcherProcess:
    """Main watcher process controller."""

    def __init__(self, config: dict) -> None:
        """
        Initialize the watcher process.

        Args:
            config: Application configuration dictionary
        """
        self._config = config
        self._running = False
        self._shutdown_timeout = config.get("event_system", {}).get(
            "shutdown_timeout_seconds", 2
        )

        # Initialize components
        self._file_watcher: FileWatcher | None = None
        self._event_writer: Any = None  # Avoid circular import issues

    def start(self) -> None:
        """Start the watcher process."""
        logger.info("Starting watcher process...")

        # Write PID file
        write_pid_file()

        # Initialize file watcher
        projects_path = get_claude_projects_path(self._config)
        fw_config = get_file_watcher_config(self._config)

        self._file_watcher = FileWatcher(
            projects_path=projects_path,
            polling_interval=fw_config["polling_interval"],
            inactivity_timeout=fw_config["inactivity_timeout"],
            debounce_interval=fw_config["debounce_interval"],
        )

        # Initialize event writer
        database_url = get_database_url(self._config)
        self._event_writer = create_event_writer(
            database_url=database_url,
            config=self._config,
        )

        # Wire up callbacks
        self._file_watcher.set_on_turn_detected(self._handle_turn_detected)
        self._file_watcher.set_on_session_ended(self._handle_session_ended)

        # Start file watcher
        self._file_watcher.start()

        self._running = True
        logger.info("Watcher process started successfully")

    def _handle_turn_detected(self, event: dict) -> None:
        """Handle turn_detected events from file watcher."""
        if not self._event_writer:
            return

        payload = {
            "session_uuid": event.get("session_uuid"),
            "actor": event.get("actor"),
            "text": event.get("text", "")[:1000],  # Truncate long text
            "source": event.get("source", "polling"),
            "turn_timestamp": event.get("timestamp"),
        }

        result = self._event_writer.write_event(
            event_type="turn_detected",
            payload=payload,
        )

        if not result.success:
            logger.error(f"Failed to write turn_detected event: {result.error}")

    def _handle_session_ended(self, event: dict) -> None:
        """Handle session_ended events from file watcher."""
        if not self._event_writer:
            return

        payload = {
            "session_uuid": event.get("session_uuid"),
            "reason": event.get("reason", "unknown"),
        }

        result = self._event_writer.write_event(
            event_type="session_ended",
            payload=payload,
        )

        if not result.success:
            logger.error(f"Failed to write session_ended event: {result.error}")

    def stop(self) -> None:
        """Stop the watcher process gracefully."""
        if not self._running:
            return

        logger.info("Stopping watcher process...")
        self._running = False

        # Stop file watcher
        if self._file_watcher:
            self._file_watcher.stop()
            self._file_watcher = None

        # Stop event writer
        if self._event_writer:
            self._event_writer.stop()
            self._event_writer = None

        # Remove PID file
        remove_pid_file()

        logger.info("Watcher process stopped")

    def run(self) -> None:
        """Run the watcher process main loop."""
        self.start()

        try:
            while self._running:
                time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def main() -> int:
    """Main entry point for the watcher process."""
    logger.info("=" * 50)
    logger.info("Claude Headspace Watcher Process Starting")
    logger.info(f"PID: {os.getpid()}")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 50)

    # Load configuration
    config_path = project_root / "config.yaml"
    config = load_config(str(config_path))

    # Create watcher process
    watcher = WatcherProcess(config)

    # Set up signal handlers
    def signal_handler(signum: int, frame: Any) -> None:
        sig_name = signal.Signals(signum).name
        logger.info(f"Received {sig_name}, initiating shutdown...")
        watcher.stop()

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    # Run the watcher
    try:
        watcher.run()
        return 0
    except Exception as e:
        logger.error(f"Watcher process failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
