"""File watcher service for monitoring Claude Code session files.

Provides two modes of operation:
1. Legacy session file monitoring via Watchdog + polling
2. Content pipeline: transcript monitoring, regex question detection,
   and timeout-gated inference for AWAITING_INPUT detection
"""

import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable, Optional
from uuid import UUID

from watchdog.events import FileModifiedEvent, FileSystemEventHandler
from watchdog.observers import Observer

from .git_metadata import GitMetadata
from .jsonl_parser import JSONLParser
from .project_decoder import encode_project_path, locate_jsonl_file
from .prompt_registry import build_prompt
from .session_registry import RegisteredSession, SessionRegistry

logger = logging.getLogger(__name__)

# Default timeout before triggering inference for stalled agent output
DEFAULT_AWAITING_INPUT_TIMEOUT = 10  # seconds


class FileWatcher:
    """
    Service for watching Claude Code session jsonl files.

    Monitors registered sessions' jsonl files and emits events when
    new turns are detected. Also monitors transcript files for content
    pipeline processing (question detection and inference classification).
    """

    def __init__(
        self,
        projects_path: str = "~/.claude/projects",
        polling_interval: float = 2.0,
        inactivity_timeout: int = 5400,
        debounce_interval: float = 0.5,
        awaiting_input_timeout: float = DEFAULT_AWAITING_INPUT_TIMEOUT,
    ) -> None:
        """
        Initialize the file watcher.

        Args:
            projects_path: Path to Claude Code projects directory
            polling_interval: Polling interval in seconds (fallback mode)
            inactivity_timeout: Session inactivity timeout in seconds
            debounce_interval: Debounce interval for rapid file changes
            awaiting_input_timeout: Seconds before inference check on stalled transcript
        """
        self._projects_path = os.path.expanduser(projects_path)
        self._polling_interval = polling_interval
        self._inactivity_timeout = inactivity_timeout
        self._debounce_interval = debounce_interval
        self._awaiting_input_timeout = awaiting_input_timeout

        self._registry = SessionRegistry()
        self._git_metadata = GitMetadata()
        self._parsers: dict[UUID, JSONLParser] = {}

        self._observer: Optional[Observer] = None
        self._polling_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._running = False

        # Event callbacks
        self._on_turn_detected: Optional[Callable[[dict], None]] = None
        self._on_session_ended: Optional[Callable[[dict], None]] = None
        self._on_question_detected: Optional[Callable[[dict], None]] = None

        # Debouncing state
        self._pending_files: dict[str, float] = {}
        self._debounce_lock = threading.Lock()

        # Content pipeline: transcript monitoring
        self._transcript_positions: dict[int, int] = {}  # agent_id -> file byte position
        self._pending_inference_timers: dict[int, threading.Timer] = {}  # agent_id -> timer
        self._timer_lock = threading.Lock()

    @property
    def registry(self) -> SessionRegistry:
        """Get the session registry."""
        return self._registry

    @property
    def git_metadata(self) -> GitMetadata:
        """Get the git metadata service."""
        return self._git_metadata

    def set_on_turn_detected(self, callback: Callable[[dict], None]) -> None:
        """Set callback for turn_detected events."""
        self._on_turn_detected = callback

    def set_on_session_ended(self, callback: Callable[[dict], None]) -> None:
        """Set callback for session_ended events."""
        self._on_session_ended = callback

    def set_on_question_detected(self, callback: Callable[[dict], None]) -> None:
        """Set callback for question_detected events from content pipeline."""
        self._on_question_detected = callback

    def start(self) -> None:
        """Start the file watcher background threads."""
        if self._running:
            logger.warning("File watcher already running")
            return

        self._stop_event.clear()
        self._running = True

        # Start Watchdog observer
        self._observer = Observer()
        self._observer.start()
        logger.info("Watchdog observer started")

        # Start polling thread for inactivity checks and fallback polling
        self._polling_thread = threading.Thread(
            target=self._polling_loop, daemon=True, name="FileWatcher-Polling"
        )
        self._polling_thread.start()
        logger.info("Polling thread started")

    def stop(self) -> None:
        """Stop the file watcher gracefully."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        # Stop Watchdog observer
        if self._observer:
            self._observer.stop()
            self._observer.join(timeout=5)
            self._observer = None
            logger.info("Watchdog observer stopped")

        # Wait for polling thread
        if self._polling_thread and self._polling_thread.is_alive():
            self._polling_thread.join(timeout=5)
            self._polling_thread = None
            logger.info("Polling thread stopped")

        # Clear parsers
        self._parsers.clear()

    def register_session(
        self,
        session_uuid: UUID,
        project_path: str,
        working_directory: str,
        iterm_pane_id: Optional[str] = None,
    ) -> RegisteredSession:
        """
        Register a session and start watching its jsonl file.

        Args:
            session_uuid: Unique identifier for the session
            project_path: Decoded project path
            working_directory: Original working directory
            iterm_pane_id: Optional iTerm pane ID

        Returns:
            The registered session
        """
        session = self._registry.register_session(
            session_uuid=session_uuid,
            project_path=project_path,
            working_directory=working_directory,
            iterm_pane_id=iterm_pane_id,
        )

        # Locate and set jsonl file path
        jsonl_path = locate_jsonl_file(working_directory, self._projects_path)
        if jsonl_path:
            self._registry.update_jsonl_path(session_uuid, jsonl_path)
            self._setup_file_watch(session_uuid, jsonl_path)

        logger.info(f"Session registered: {session_uuid} for {project_path}")
        return session

    def unregister_session(self, session_uuid: UUID) -> bool:
        """
        Unregister a session and stop watching.

        Args:
            session_uuid: UUID of the session to unregister

        Returns:
            True if session was unregistered
        """
        # Remove parser
        self._parsers.pop(session_uuid, None)

        result = self._registry.unregister_session(session_uuid)
        if result:
            logger.info(f"Session unregistered: {session_uuid}")
        return result

    def get_registered_sessions(self) -> list[RegisteredSession]:
        """Get all registered sessions."""
        return self._registry.get_registered_sessions()

    def is_session_registered(self, session_uuid: UUID) -> bool:
        """Check if a session is registered."""
        return self._registry.is_session_registered(session_uuid)

    def set_polling_interval(self, seconds: float) -> None:
        """
        Adjust polling interval at runtime.

        Used by hybrid mode to switch between fallback (2s) and
        hooks-active (60s) intervals.

        Args:
            seconds: New polling interval in seconds
        """
        self._polling_interval = seconds
        logger.info(f"Polling interval set to {seconds} seconds")

    def _setup_file_watch(self, session_uuid: UUID, jsonl_path: str) -> None:
        """Set up Watchdog watch for a jsonl file."""
        if not self._observer or not os.path.exists(jsonl_path):
            return

        # Create parser for this file
        parser = JSONLParser(jsonl_path)
        # Read existing content to set position at end
        parser.read_new_lines()
        self._parsers[session_uuid] = parser

        # Set up Watchdog handler for the directory
        directory = os.path.dirname(jsonl_path)
        handler = _SessionFileHandler(
            session_uuid=session_uuid,
            jsonl_path=jsonl_path,
            file_watcher=self,
        )
        self._observer.schedule(handler, directory, recursive=False)

    def _polling_loop(self) -> None:
        """Background polling loop for inactivity checks and fallback polling."""
        while not self._stop_event.is_set():
            try:
                # Check for inactive sessions
                self._check_inactive_sessions()

                # Process any debounced file changes
                self._process_debounced_changes()

                # Fallback polling for sessions without Watchdog events
                self._poll_all_sessions()

            except Exception as e:
                logger.error(f"Error in polling loop: {e}")

            # Wait for next poll
            self._stop_event.wait(self._polling_interval)

    def _check_inactive_sessions(self) -> None:
        """Check for and handle inactive sessions."""
        inactive = self._registry.get_inactive_sessions(self._inactivity_timeout)
        for session in inactive:
            self._emit_session_ended(session, reason="timeout")
            self._registry.unregister_session(session.session_uuid)
            self._parsers.pop(session.session_uuid, None)
            logger.info(f"Session timed out: {session.session_uuid}")

    def _poll_all_sessions(self) -> None:
        """Poll all registered sessions for new content."""
        for session in self._registry.get_registered_sessions():
            self._process_session_file(session.session_uuid)

    def _process_session_file(self, session_uuid: UUID) -> None:
        """Process new content in a session's jsonl file."""
        parser = self._parsers.get(session_uuid)
        if not parser:
            return

        session = self._registry.get_session(session_uuid)
        if not session:
            return

        turns = parser.read_new_lines()
        for turn in turns:
            self._registry.update_last_activity(session_uuid)
            self._emit_turn_detected(session, turn)

    def _process_debounced_changes(self) -> None:
        """Process file changes that have passed the debounce window."""
        now = time.time()
        to_process = []

        with self._debounce_lock:
            for path, timestamp in list(self._pending_files.items()):
                if now - timestamp >= self._debounce_interval:
                    to_process.append(path)
                    del self._pending_files[path]

        for path in to_process:
            self._handle_file_change(path)

    def _schedule_debounced_change(self, path: str) -> None:
        """Schedule a file change for debounced processing."""
        with self._debounce_lock:
            self._pending_files[path] = time.time()

    def _handle_file_change(self, path: str) -> None:
        """Handle a file change event (after debouncing)."""
        # Find session for this file
        for session_uuid, parser in self._parsers.items():
            if parser.file_path == path:
                self._process_session_file(session_uuid)
                break

    # --- Content Pipeline Methods ---

    def register_transcript(self, agent_id: int, transcript_path: str) -> None:
        """
        Register a transcript file for content pipeline monitoring.

        Args:
            agent_id: The agent ID to associate with this transcript
            transcript_path: Absolute path to the .jsonl transcript file
        """
        if not transcript_path or not os.path.exists(transcript_path):
            logger.debug(
                f"Transcript not registered for agent_id={agent_id}: "
                f"path={'missing' if not transcript_path else 'not found'}"
            )
            return

        # Set initial position to end of file (don't process existing content)
        try:
            file_size = os.path.getsize(transcript_path)
            self._transcript_positions[agent_id] = file_size
            logger.info(
                f"Transcript registered for agent_id={agent_id}: "
                f"{transcript_path} (position={file_size})"
            )
        except OSError as e:
            logger.warning(f"Error registering transcript for agent_id={agent_id}: {e}")

    def unregister_transcript(self, agent_id: int) -> None:
        """Unregister a transcript from content pipeline monitoring."""
        self._transcript_positions.pop(agent_id, None)
        self.cancel_inference_timer(agent_id)

    def check_transcript_for_questions(
        self,
        agent_id: int,
        transcript_path: str,
    ) -> bool:
        """
        Check a transcript file for new agent content and detect questions.

        Uses incremental reading from last known position. If new agent
        content is detected, runs regex-based question detection immediately.

        Args:
            agent_id: The agent ID
            transcript_path: Path to the transcript file

        Returns:
            True if a question was detected (regex), False otherwise
        """
        from .transcript_reader import read_new_entries_from_position

        position = self._transcript_positions.get(agent_id, 0)
        entries, new_position = read_new_entries_from_position(
            transcript_path, position
        )
        self._transcript_positions[agent_id] = new_position

        if not entries:
            return False

        # Look for new assistant content
        agent_entries = [
            e for e in entries
            if e.role == "assistant" and e.content
        ]

        if not agent_entries:
            return False

        # Check the latest agent content for question patterns
        latest_content = agent_entries[-1].content
        if not latest_content:
            return False

        from .intent_detector import detect_agent_intent
        from ..models.turn import TurnIntent

        intent_result = detect_agent_intent(latest_content)
        if intent_result.intent == TurnIntent.QUESTION:
            logger.info(
                f"Content pipeline: regex detected question for agent_id={agent_id}, "
                f"pattern={intent_result.matched_pattern}"
            )
            self._emit_question_detected(agent_id, latest_content, "regex")
            return True

        # No question detected by regex — start timeout timer for inference
        self._start_inference_timer(agent_id, latest_content)
        return False

    def cancel_inference_timer(self, agent_id: int) -> None:
        """
        Cancel any pending inference timer for an agent.

        Called when PostToolUse or Stop events arrive, indicating the agent
        is still active (no need for inference classification).

        Args:
            agent_id: The agent ID whose timer to cancel
        """
        with self._timer_lock:
            timer = self._pending_inference_timers.pop(agent_id, None)
            if timer:
                timer.cancel()
                logger.debug(f"Inference timer cancelled for agent_id={agent_id}")

    def _start_inference_timer(self, agent_id: int, content: str) -> None:
        """Start a timeout timer for inference-based question classification."""
        # Cancel any existing timer first
        self.cancel_inference_timer(agent_id)

        with self._timer_lock:
            timer = threading.Timer(
                self._awaiting_input_timeout,
                self._on_inference_timeout,
                args=(agent_id, content),
            )
            timer.daemon = True
            timer.start()
            self._pending_inference_timers[agent_id] = timer
            logger.debug(
                f"Inference timer started for agent_id={agent_id}, "
                f"timeout={self._awaiting_input_timeout}s"
            )

    def _on_inference_timeout(self, agent_id: int, content: str) -> None:
        """Called when inference timeout expires — classify content via LLM."""
        with self._timer_lock:
            self._pending_inference_timers.pop(agent_id, None)

        logger.info(
            f"Content pipeline: inference timeout for agent_id={agent_id}, "
            f"sending to inference"
        )

        try:
            from flask import current_app
            inference_service = current_app.extensions.get("inference_service")
            if not inference_service:
                logger.debug("No inference service available for question classification")
                return

            is_question = self._classify_question_via_inference(
                inference_service, content
            )
            if is_question:
                logger.info(
                    f"Content pipeline: inference classified as question "
                    f"for agent_id={agent_id}"
                )
                self._emit_question_detected(agent_id, content, "inference")
        except RuntimeError:
            logger.debug("No Flask app context for inference classification")
        except Exception as e:
            logger.warning(f"Inference classification failed for agent_id={agent_id}: {e}")

    @staticmethod
    def _classify_question_via_inference(inference_service: Any, content: str) -> bool:
        """
        Use inference service to classify if content is a question needing user input.

        Args:
            inference_service: The inference service instance
            content: The agent output text to classify

        Returns:
            True if the content is classified as a question needing user input
        """
        prompt = build_prompt("question_classification", content=content[:2000])

        try:
            result = inference_service.infer(
                level="turn",
                purpose="question_classification",
                input_text=prompt,
            )
            if result and result.text:
                answer = result.text.strip().lower()
                return answer.startswith("yes")
        except Exception as e:
            logger.warning(f"Inference question classification error: {e}")

        return False

    def _emit_question_detected(
        self, agent_id: int, content: str, source: str
    ) -> None:
        """Emit a question_detected event from the content pipeline."""
        event = {
            "event_type": "question_detected",
            "agent_id": agent_id,
            "content": content[:500],  # Truncate for the event
            "source": source,  # "regex" or "inference"
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self._on_question_detected:
            try:
                self._on_question_detected(event)
            except Exception as e:
                logger.error(f"Error in question_detected callback: {e}")

    # --- Legacy Event Emission Methods ---

    def _emit_turn_detected(self, session: RegisteredSession, turn: Any) -> None:
        """Emit a turn_detected event."""
        event = {
            "event_type": "turn_detected",
            "session_uuid": str(session.session_uuid),
            "project_path": session.project_path,
            "actor": turn.actor,
            "text": turn.text,
            "timestamp": turn.timestamp.isoformat(),
            "source": "polling",
        }

        if self._on_turn_detected:
            try:
                self._on_turn_detected(event)
            except Exception as e:
                logger.error(f"Error in turn_detected callback: {e}")

    def _emit_session_ended(
        self, session: RegisteredSession, reason: str
    ) -> None:
        """Emit a session_ended event."""
        event = {
            "event_type": "session_ended",
            "session_uuid": str(session.session_uuid),
            "project_path": session.project_path,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if self._on_session_ended:
            try:
                self._on_session_ended(event)
            except Exception as e:
                logger.error(f"Error in session_ended callback: {e}")


class _SessionFileHandler(FileSystemEventHandler):
    """Watchdog event handler for session jsonl files."""

    def __init__(
        self, session_uuid: UUID, jsonl_path: str, file_watcher: FileWatcher
    ) -> None:
        super().__init__()
        self._session_uuid = session_uuid
        self._jsonl_path = jsonl_path
        self._file_watcher = file_watcher

    def on_modified(self, event: FileModifiedEvent) -> None:
        """Handle file modification event."""
        if event.is_directory:
            return

        if event.src_path == self._jsonl_path:
            # Schedule debounced processing
            self._file_watcher._schedule_debounced_change(event.src_path)


def init_file_watcher(app: Any, config: dict) -> FileWatcher:
    """
    Initialize and register FileWatcher with Flask app.

    Args:
        app: Flask application instance
        config: Application configuration dictionary

    Returns:
        Initialized FileWatcher instance
    """
    from ..config import get_claude_projects_path, get_file_watcher_config

    projects_path = get_claude_projects_path(config)
    fw_config = get_file_watcher_config(config)

    watcher = FileWatcher(
        projects_path=projects_path,
        polling_interval=fw_config["polling_interval"],
        inactivity_timeout=fw_config["inactivity_timeout"],
        debounce_interval=fw_config["debounce_interval"],
        awaiting_input_timeout=fw_config.get(
            "awaiting_input_timeout", DEFAULT_AWAITING_INPUT_TIMEOUT
        ),
    )

    app.extensions["file_watcher"] = watcher

    # Start watcher when app starts
    @app.before_request
    def start_watcher_once():
        if not watcher._running:
            watcher.start()

    # Register cleanup on app teardown
    @app.teardown_appcontext
    def stop_watcher(exception=None):
        pass  # Watcher stops on app shutdown via atexit

    import atexit
    atexit.register(watcher.stop)

    return watcher
