"""tmux bridge service for sending input to Claude Code sessions via tmux send-keys.

Replaces the commander socket transport with tmux subprocess calls. Text is sent
via `send-keys -l` (literal) followed by a separate Enter keystroke, which tmux
delivers through its PTY layer at a level that Ink's onSubmit handler recognises
as genuine keyboard input.
"""

import logging
import re
import subprocess
import threading
import time
from enum import Enum
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_SUBPROCESS_TIMEOUT = 5  # seconds
DEFAULT_TEXT_ENTER_DELAY_MS = 120  # ms between text send and Enter
DEFAULT_CLEAR_DELAY_MS = 200  # ms after Escape before sending text
DEFAULT_SEQUENTIAL_SEND_DELAY_MS = 150  # ms between rapid sequential sends
DEFAULT_ENTER_VERIFY_DELAY_MS = 200  # ms between Enter and verification check
DEFAULT_MAX_ENTER_RETRIES = 3  # max Enter retry attempts after verification failure
DEFAULT_ENTER_VERIFY_LINES = 5  # pane lines to capture for Enter verification

# Per-pane send lock registry — prevents concurrent sends to the same pane
# from interleaving text and corrupting the prompt.
# Uses RLock so interrupt_and_send_text can call send_text without deadlocking.
_send_locks: dict[str, threading.RLock] = {}
_send_locks_meta_lock = threading.Lock()


def _get_send_lock(pane_id: str) -> threading.RLock:
    """Get or create a per-pane reentrant send lock."""
    with _send_locks_meta_lock:
        if pane_id not in _send_locks:
            _send_locks[pane_id] = threading.RLock()
        return _send_locks[pane_id]


def release_send_lock(pane_id: str) -> None:
    """Remove a pane's send lock when the agent is unregistered."""
    with _send_locks_meta_lock:
        _send_locks.pop(pane_id, None)


class TmuxBridgeErrorType(str, Enum):
    """Error types for tmux bridge operations."""

    PANE_NOT_FOUND = "pane_not_found"
    TMUX_NOT_INSTALLED = "tmux_not_installed"
    SUBPROCESS_FAILED = "subprocess_failed"
    NO_PANE_ID = "no_pane_id"
    TIMEOUT = "timeout"
    SEND_FAILED = "send_failed"  # Send completed but verification failed (reserved for wait_for_pattern use)
    UNKNOWN = "unknown"


class SendResult(NamedTuple):
    """Result of a send operation."""

    success: bool
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None
    latency_ms: int = 0


class HealthCheckLevel(str, Enum):
    """Level of health check to perform."""

    EXISTS = "exists"              # Pane found in list-panes (cheapest)
    COMMAND = "command"            # + current_command check (default)
    PROCESS_TREE = "process_tree"  # + ps tree walk (most expensive)


# Default process names to check for in health checks
DEFAULT_PROCESS_NAMES = ("claude", "node")


class HealthResult(NamedTuple):
    """Result of a health check operation."""

    available: bool
    running: bool = False
    pid: int | None = None
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None


class TtyResult(NamedTuple):
    """Result of a TTY lookup for a tmux pane's client."""

    success: bool
    tty: str | None = None
    session_name: str | None = None
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None


class PaneInfo(NamedTuple):
    """Metadata for a tmux pane."""

    pane_id: str
    session_name: str
    current_command: str
    working_directory: str


_PANE_ID_PATTERN = re.compile(r"^%\d+$")


def _validate_pane_id(pane_id: str | None) -> bool:
    """Validate that a pane ID matches tmux's %N format.

    Args:
        pane_id: The pane ID to validate

    Returns:
        True if valid (e.g. '%0', '%5', '%123'), False otherwise.
    """
    if not pane_id:
        return False
    return bool(_PANE_ID_PATTERN.match(pane_id))


class WaitResult(NamedTuple):
    """Result of a wait_for_pattern polling operation."""

    matched: bool
    content: str = ""
    elapsed_ms: int = 0
    error_type: TmuxBridgeErrorType | None = None
    error_message: str | None = None


def _classify_subprocess_error(error: subprocess.CalledProcessError) -> TmuxBridgeErrorType:
    """Classify a tmux subprocess error based on stderr content."""
    stderr = (error.stderr or b"").decode("utf-8", errors="replace").lower()
    if "can't find pane" in stderr or "no such" in stderr or "not found" in stderr:
        return TmuxBridgeErrorType.PANE_NOT_FOUND
    return TmuxBridgeErrorType.SUBPROCESS_FAILED


def _diagnostic_dump(pane_id: str, context: str) -> None:
    """Capture pane content and log at WARNING level for debugging.

    Called on timeouts and failure paths to aid post-mortem analysis.

    Args:
        pane_id: The tmux pane ID
        context: Description of why the dump was triggered
    """
    try:
        content = capture_pane(pane_id, lines=100)
        if content:
            truncated = content[:2000]
            if len(content) > 2000:
                truncated += "\n... [truncated]"
            logger.warning(
                f"Diagnostic dump ({context}) for pane {pane_id}:\n{truncated}"
            )
        else:
            logger.warning(
                f"Diagnostic dump ({context}) for pane {pane_id}: "
                f"capture returned empty"
            )
    except Exception as e:
        logger.warning(
            f"Diagnostic dump ({context}) for pane {pane_id} failed: {e}"
        )


def wait_for_pattern(
    pane_id: str,
    pattern: str,
    timeout_ms: int = 5000,
    poll_interval_ms: int = 200,
    capture_lines: int = 50,
    join_wrapped: bool = False,
) -> WaitResult:
    """Poll a tmux pane until a regex pattern matches captured content.

    Repeatedly captures pane content and searches for the pattern.
    Returns as soon as a match is found, or after timeout_ms.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        pattern: Regex pattern to search for (re.search)
        timeout_ms: Maximum time to wait in milliseconds
        poll_interval_ms: Delay between capture attempts in milliseconds
        capture_lines: Number of pane lines to capture per attempt
        join_wrapped: If True, join wrapped lines in capture (-J flag)

    Returns:
        WaitResult with match status, captured content, and timing
    """
    if not _validate_pane_id(pane_id):
        return WaitResult(
            matched=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    start_time = time.time()
    deadline = start_time + (timeout_ms / 1000.0)
    last_content = ""

    while True:
        content = capture_pane(
            pane_id, lines=capture_lines, join_wrapped=join_wrapped
        )
        last_content = content

        if content and re.search(pattern, content, re.MULTILINE):
            elapsed_ms = int((time.time() - start_time) * 1000)
            return WaitResult(
                matched=True,
                content=content,
                elapsed_ms=elapsed_ms,
            )

        now = time.time()
        if now >= deadline:
            elapsed_ms = int((now - start_time) * 1000)
            _diagnostic_dump(pane_id, f"wait_for_pattern timeout ({pattern!r})")
            return WaitResult(
                matched=False,
                content=last_content,
                elapsed_ms=elapsed_ms,
                error_type=TmuxBridgeErrorType.TIMEOUT,
                error_message=f"Pattern {pattern!r} not found after {timeout_ms}ms",
            )

        time.sleep(poll_interval_ms / 1000.0)


def _has_autocomplete_ghost(pane_content: str) -> bool:
    """Check if pane content shows autocomplete ghost text.

    Ghost text is rendered with dim/faint ANSI styling (SGR 2 or color 90).
    We check the last non-empty lines (the input area) for these indicators,
    but skip lines that are purely decorative (separator lines made of
    box-drawing characters, status bars, etc.) since Claude Code renders
    those with dim styling too — causing false positives that trigger
    unwanted Escape sends which clear user input.

    Args:
        pane_content: Pane content captured with escape sequences (-e flag)

    Returns:
        True if autocomplete ghost text is likely present
    """
    if not pane_content:
        return False

    # Check the last few non-empty lines for dim text indicators.
    # SGR 2 = dim/faint, SGR 90 = dark gray (bright black).
    # Claude Code renders autocomplete ghost suggestions with these styles.
    lines = [line for line in pane_content.split("\n") if line.strip()]
    if not lines:
        return False

    # Only check the last 2 lines (input area)
    for line in lines[-2:]:
        if "\x1b[2m" in line or "\x1b[90m" in line:
            # Strip ANSI escape sequences to examine the actual text content
            clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", line).strip()
            if not clean:
                continue
            # Skip lines that are purely decorative: box-drawing characters
            # (─│┌┐└┘├┤┬┴┼╭╮╰╯═║╔╗╚╝╠╣╦╩╬), dashes, dots, and whitespace.
            # These are Claude Code's separator/border lines rendered with
            # dim styling — NOT autocomplete ghost text.
            stripped = clean.replace(" ", "")
            if stripped and all(
                c in "─│┌┐└┘├┤┬┴┼╭╮╰╯═║╔╗╚╝╠╣╦╩╬-—·•…" for c in stripped
            ):
                continue
            # This line has dim/faint styling AND contains actual text
            # content — likely autocomplete ghost text.
            return True

    return False


def _extract_verification_snippet(text: str, max_len: int = 60) -> str | None:
    """Extract a verification snippet from the tail of sent text.

    Used by _verify_submission to check whether sent text is still visible
    in the pane (indicating Enter was not accepted) vs. cleared (Enter worked).

    Args:
        text: The sent text to extract a snippet from
        max_len: Maximum snippet length (truncated from end of last line)

    Returns:
        A snippet string (15-60 chars from the last non-empty line),
        or None if text is too short for reliable matching.
    """
    if not text or len(text) < 40:
        return None

    # Find the last non-empty line
    lines = [line for line in text.split("\n") if line.strip()]
    if not lines:
        return None

    last_line = lines[-1].strip()
    if len(last_line) < 15:
        return None

    # Truncate from the end to max_len
    return last_line[-max_len:]


def _pane_content_changed(before: str, after: str) -> bool:
    """Compare two pane captures to detect meaningful content change.

    Strips blank lines and whitespace from each line before comparison.
    Any difference in the non-empty lines indicates the agent has started
    processing (input cleared, tool output appeared, etc.).

    Args:
        before: Pane content captured before Enter
        after: Pane content captured after Enter

    Returns:
        True if the pane content has changed meaningfully
    """
    def _significant_lines(text: str) -> list[str]:
        return [line.strip() for line in text.strip().splitlines() if line.strip()]

    return _significant_lines(before) != _significant_lines(after)


def _verify_submission(
    pane_id: str,
    pre_submit_content: str,
    timeout: float,
    clear_delay_ms: int,
    verify_delay_ms: int = DEFAULT_ENTER_VERIFY_DELAY_MS,
    max_retries: int = DEFAULT_MAX_ENTER_RETRIES,
    sent_text: str = "",
) -> bool:
    """Verify that Enter was accepted by watching for pane content changes.

    For long text (40+ chars), uses text-presence verification: checks if a
    snippet of the sent text is still visible in the pane. If the snippet
    disappeared (input cleared), Enter worked. If still present, Enter failed.

    For short text (< 40 chars), falls back to content-change comparison
    with the pre-Enter baseline.

    Args:
        pane_id: The tmux pane ID
        pre_submit_content: Pane content captured before Enter was sent
        timeout: Subprocess timeout in seconds
        clear_delay_ms: Delay in ms after Escape before retrying Enter
        verify_delay_ms: Delay in ms before each verification check
        max_retries: Maximum number of Enter retries
        sent_text: The text that was sent (used for snippet extraction)

    Returns:
        True if submission was confirmed, False if all retries exhausted
    """
    snippet = _extract_verification_snippet(sent_text)
    use_snippet = snippet is not None

    for attempt in range(1, max_retries + 1):
        time.sleep(verify_delay_ms / 1000.0)
        post_content = capture_pane(
            pane_id, lines=DEFAULT_ENTER_VERIFY_LINES, timeout=timeout,
        )

        if use_snippet:
            # Text-presence check: snippet NOT in pane = Enter accepted
            if snippet not in post_content:
                logger.info(
                    f"Enter confirmed (text cleared) after {attempt} "
                    f"attempt(s) for pane {pane_id}"
                )
                return True
        else:
            # Content-change fallback for short text
            if _pane_content_changed(pre_submit_content, post_content):
                logger.info(
                    f"Enter confirmed after {attempt} attempt(s) for pane {pane_id}"
                )
                return True

        # Enter was lost — try to recover
        logger.debug(
            f"Pane {pane_id} unchanged after Enter "
            f"(attempt {attempt}/{max_retries})"
        )

        # Check for autocomplete ghost text that may have appeared
        ghost_content = capture_pane(
            pane_id, lines=3, include_escapes=True, timeout=timeout,
        )
        if _has_autocomplete_ghost(ghost_content):
            logger.debug(
                f"Ghost text detected during retry for pane {pane_id}, "
                f"dismissing with Escape"
            )
            try:
                subprocess.run(
                    ["tmux", "send-keys", "-t", pane_id, "Escape"],
                    check=True,
                    timeout=timeout,
                    capture_output=True,
                )
                time.sleep(clear_delay_ms / 1000.0)
            except Exception:
                pass

        # Retry Enter
        try:
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "Enter"],
                check=True,
                timeout=timeout,
                capture_output=True,
            )
        except Exception as e:
            logger.warning(f"Enter retry failed for pane {pane_id}: {e}")

    # All retries exhausted
    _diagnostic_dump(pane_id, "Enter verification failed after all retries")
    return False


def send_text(
    pane_id: str,
    text: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    text_enter_delay_ms: int = DEFAULT_TEXT_ENTER_DELAY_MS,
    clear_delay_ms: int = DEFAULT_CLEAR_DELAY_MS,
    verify_enter: bool = True,
    enter_verify_delay_ms: int = DEFAULT_ENTER_VERIFY_DELAY_MS,
    max_enter_retries: int = DEFAULT_MAX_ENTER_RETRIES,
    detect_ghost_text: bool = True,
    skip_verify_hint: bool = False,
) -> SendResult:
    """Send text followed by Enter to a Claude Code session's tmux pane.

    Simplified pipeline (max ~6 subprocess calls in typical case):
      1. Capture pane to check for ghost text (optional via detect_ghost_text)
      2. If ghost: Escape + delay
      3. send-keys -l <text>
      4. delay (text_enter_delay_ms)
      5. send-keys Enter
      6. If verify_enter and not skip_verify_hint: capture + compare, one retry

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        text: The text to send
        timeout: Subprocess timeout in seconds
        text_enter_delay_ms: Delay in ms between text send and Enter send
        clear_delay_ms: Delay in ms after Escape before sending text
        verify_enter: If True, verify Enter was accepted by watching for
            pane content changes. Overridden by skip_verify_hint.
        enter_verify_delay_ms: Delay in ms before each verification check
        max_enter_retries: Maximum number of Enter retries on verification failure
        detect_ghost_text: If False, skip all ghost text detection and Escape
            sends. Useful when callers know ghost text isn't relevant.
        skip_verify_hint: If True, skip the entire verification block even
            when verify_enter is True. Use when the pane is too volatile for
            content comparison (e.g. after an interrupt).

    Returns:
        SendResult with success status and optional error information
    """
    if not _validate_pane_id(pane_id):
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    with _get_send_lock(pane_id):
        start_time = time.time()

        # Strip trailing whitespace so the last byte through the PTY is
        # actual content, not junk that interferes with the deliberate Enter
        # we send after the delay.  Internal newlines and formatting are
        # preserved — send-keys -l passes them as literal characters.
        sanitised = text.rstrip()
        if sanitised != text:
            logger.debug(
                f"Sanitised text for pane {pane_id}: "
                f"original {len(text)} chars -> {len(sanitised)} chars"
            )

        try:
            # Step 1: Ghost text detection (configurable — skip when not relevant)
            if detect_ghost_text:
                pane_content = capture_pane(
                    pane_id, lines=3, include_escapes=True, timeout=timeout,
                )
                if _has_autocomplete_ghost(pane_content):
                    logger.debug(
                        f"Autocomplete ghost detected in pane {pane_id}, "
                        f"sending Escape to dismiss"
                    )
                    subprocess.run(
                        ["tmux", "send-keys", "-t", pane_id, "Escape"],
                        check=True,
                        timeout=timeout,
                        capture_output=True,
                    )
                    time.sleep(clear_delay_ms / 1000.0)

            # Step 2: Send literal text (does NOT interpret key names)
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "-l", sanitised],
                check=True,
                timeout=timeout,
                capture_output=True,
            )

            # Step 3: Adaptive delay between text and Enter
            # Scale delay with text length: +1ms per 10 chars beyond 200
            adaptive_delay_ms = text_enter_delay_ms + max(0, len(sanitised) - 200) // 10
            if adaptive_delay_ms != text_enter_delay_ms:
                logger.debug(
                    f"Adaptive delay for pane {pane_id}: "
                    f"{text_enter_delay_ms}ms -> {adaptive_delay_ms}ms "
                    f"(text length: {len(sanitised)})"
                )
            time.sleep(adaptive_delay_ms / 1000.0)

            # Step 3b: Post-typing ghost text dismissal
            # Text may have triggered NEW autocomplete suggestions after typing.
            # Dismiss them before sending Enter to prevent swallowing.
            if detect_ghost_text:
                post_type_content = capture_pane(
                    pane_id, lines=3, include_escapes=True, timeout=timeout,
                )
                if _has_autocomplete_ghost(post_type_content):
                    logger.debug(
                        f"Post-typing ghost text detected in pane {pane_id}, "
                        f"sending Escape to dismiss"
                    )
                    subprocess.run(
                        ["tmux", "send-keys", "-t", pane_id, "Escape"],
                        check=True,
                        timeout=timeout,
                        capture_output=True,
                    )
                    time.sleep(clear_delay_ms / 1000.0)

            # Step 4: Capture pre-Enter baseline for verification
            should_verify = verify_enter and not skip_verify_hint
            pre_enter_content = ""
            if should_verify:
                pre_enter_content = capture_pane(
                    pane_id, lines=DEFAULT_ENTER_VERIFY_LINES, timeout=timeout,
                )

            # Step 5: Send Enter as a key (triggers Ink's onSubmit)
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "Enter"],
                check=True,
                timeout=timeout,
                capture_output=True,
            )

            # Step 6: Verify Enter was accepted (one capture + compare,
            # retry on failure). Skipped when skip_verify_hint is set
            # because pane content is too volatile for comparison.
            #
            # IMPORTANT: Verification failure is NOT fatal. The retries
            # provide best-effort recovery for ghost-text swallowing, but
            # false negatives are common because Claude Code echoes user
            # text back into the conversation view — the snippet stays
            # visible in the pane even after Enter lands successfully.
            # Returning success=False here caused ~45% of voice commands
            # to 502 despite successful delivery.
            if should_verify:
                if not _verify_submission(
                    pane_id,
                    pre_enter_content,
                    timeout=timeout,
                    clear_delay_ms=clear_delay_ms,
                    verify_delay_ms=enter_verify_delay_ms,
                    max_retries=max_enter_retries,
                    sent_text=sanitised,
                ):
                    latency_ms = int((time.time() - start_time) * 1000)
                    logger.warning(
                        f"Enter verification inconclusive for pane {pane_id} "
                        f"after {max_enter_retries} retries ({latency_ms}ms) "
                        f"— proceeding as success (text was sent)"
                    )

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Sent text to tmux pane {pane_id} ({latency_ms}ms)")
            return SendResult(success=True, latency_ms=latency_ms)

        except FileNotFoundError:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning("tmux binary not found on PATH")
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
                error_message="tmux is not installed or not on PATH.",
                latency_ms=latency_ms,
            )

        except subprocess.CalledProcessError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_type = _classify_subprocess_error(e)
            stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
            logger.warning(f"tmux send-keys failed for pane {pane_id}: {stderr_text}")
            return SendResult(
                success=False,
                error_type=error_type,
                error_message=f"tmux send-keys failed: {stderr_text}" if stderr_text else "tmux send-keys failed",
                latency_ms=latency_ms,
            )

        except subprocess.TimeoutExpired:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"tmux send-keys timed out for pane {pane_id}")
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.TIMEOUT,
                error_message=f"tmux subprocess timed out after {timeout}s.",
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.exception(f"Unexpected error sending to tmux pane {pane_id}")
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.UNKNOWN,
                error_message=f"Unexpected error: {e}",
                latency_ms=latency_ms,
            )


def interrupt_and_send_text(
    pane_id: str,
    text: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    text_enter_delay_ms: int = DEFAULT_TEXT_ENTER_DELAY_MS,
    interrupt_settle_ms: int = 500,
    verify_enter: bool = True,
) -> SendResult:
    """Interrupt a processing Claude Code agent, then send text.

    Sends Escape to halt the current agent execution, waits for the
    agent to return to its input prompt, then sends the text as a new
    command via send_text().

    Used by voice_bridge.py for interrupting agents via voice commands.

    Note: The settle period (interrupt_settle_ms) uses a blocking
    time.sleep() which holds the Flask worker thread. This is not
    easily fixable without async, but callers can tune the value down
    to reduce blocking time at the risk of sending before the agent
    has returned to its prompt.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        text: The text to send after interrupting
        timeout: Subprocess timeout in seconds
        text_enter_delay_ms: Delay in ms between text send and Enter send
        interrupt_settle_ms: Delay in ms after Escape before sending text.
            Blocks the calling thread. Tune down to reduce latency at the
            risk of the agent not being ready for input yet.
        verify_enter: If True, attempt Enter verification in send_text.
            Note: skip_verify_hint=True is always passed to send_text after
            an interrupt since the pane is too volatile for content comparison.
    """
    if not _validate_pane_id(pane_id):
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    with _get_send_lock(pane_id):
        start_time = time.time()

        try:
            # Send Escape to interrupt the running agent
            subprocess.run(
                ["tmux", "send-keys", "-t", pane_id, "Escape"],
                check=True,
                timeout=timeout,
                capture_output=True,
            )
            logger.info(f"Sent Escape interrupt to tmux pane {pane_id}")

            # Wait for Claude Code to process the interrupt and return to prompt.
            # BLOCKING: holds the Flask worker thread for interrupt_settle_ms.
            # Callers can tune this value down to reduce latency.
            time.sleep(interrupt_settle_ms / 1000.0)

        except FileNotFoundError:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
                error_message="tmux is not installed or not on PATH.",
                latency_ms=latency_ms,
            )
        except subprocess.CalledProcessError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_type = _classify_subprocess_error(e)
            stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
            logger.warning(f"tmux Escape failed for pane {pane_id}: {stderr_text}")
            return SendResult(
                success=False,
                error_type=error_type,
                error_message=f"Interrupt failed: {stderr_text}" if stderr_text else "Interrupt failed",
                latency_ms=latency_ms,
            )
        except subprocess.TimeoutExpired:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.TIMEOUT,
                error_message=f"Interrupt timed out after {timeout}s.",
                latency_ms=latency_ms,
            )

        # Now send the actual text (RLock allows re-entrance).
        # skip_verify_hint=True: after an interrupt, the pane is too volatile
        # for content comparison — agent stop/cleanup output is still flowing.
        result = send_text(
            pane_id=pane_id,
            text=text,
            timeout=timeout,
            text_enter_delay_ms=text_enter_delay_ms,
            verify_enter=verify_enter,
            skip_verify_hint=True,
        )

        if result.success:
            total_latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Interrupt + send to tmux pane {pane_id} ({total_latency_ms}ms)")
            return SendResult(success=True, latency_ms=total_latency_ms)

        return result


def send_keys(
    pane_id: str,
    *keys: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    sequential_delay_ms: int = DEFAULT_SEQUENTIAL_SEND_DELAY_MS,
    verify_enter: bool = False,
    enter_verify_delay_ms: int = DEFAULT_ENTER_VERIFY_DELAY_MS,
    max_enter_retries: int = DEFAULT_MAX_ENTER_RETRIES,
    clear_delay_ms: int = DEFAULT_CLEAR_DELAY_MS,
) -> SendResult:
    """Send special keys to a tmux pane.

    Sends keys without the -l flag so tmux interprets key names
    (Enter, Escape, Up, Down, C-c, C-u, etc.).

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        *keys: Key names to send (e.g., "Enter", "Escape", "C-c")
        timeout: Subprocess timeout in seconds
        sequential_delay_ms: Delay in ms between sequential key sends
        verify_enter: If True, verify that Enter was accepted after sending
            all keys by watching for pane content changes. Default False.
        enter_verify_delay_ms: Delay in ms before each verification check
        max_enter_retries: Maximum number of Enter retries
        clear_delay_ms: Delay in ms after Escape before retrying Enter

    Returns:
        SendResult with success status
    """
    if not _validate_pane_id(pane_id):
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    with _get_send_lock(pane_id):
        start_time = time.time()

        try:
            # Capture baseline before keys if verification requested
            pre_keys_content = ""
            if verify_enter:
                pre_keys_content = capture_pane(
                    pane_id, lines=DEFAULT_ENTER_VERIFY_LINES, timeout=timeout,
                )

            for i, key in enumerate(keys):
                if i > 0:
                    time.sleep(sequential_delay_ms / 1000.0)
                subprocess.run(
                    ["tmux", "send-keys", "-t", pane_id, key],
                    check=True,
                    timeout=timeout,
                    capture_output=True,
                )

            # Verify Enter was accepted by watching for pane content change.
            # See send_text Step 6 comment — verification failure is NOT fatal.
            if verify_enter:
                if not _verify_submission(
                    pane_id,
                    pre_keys_content,
                    timeout=timeout,
                    clear_delay_ms=clear_delay_ms,
                    verify_delay_ms=enter_verify_delay_ms,
                    max_retries=max_enter_retries,
                ):
                    latency_ms = int((time.time() - start_time) * 1000)
                    logger.warning(
                        f"Enter verification inconclusive for pane {pane_id} "
                        f"after {max_enter_retries} retries ({latency_ms}ms) "
                        f"— proceeding as success (keys were sent)"
                    )

            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Sent keys {keys} to tmux pane {pane_id} ({latency_ms}ms)")
            return SendResult(success=True, latency_ms=latency_ms)

        except FileNotFoundError:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
                error_message="tmux is not installed or not on PATH.",
                latency_ms=latency_ms,
            )

        except subprocess.CalledProcessError as e:
            latency_ms = int((time.time() - start_time) * 1000)
            error_type = _classify_subprocess_error(e)
            stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
            return SendResult(
                success=False,
                error_type=error_type,
                error_message=f"tmux send-keys failed: {stderr_text}" if stderr_text else "tmux send-keys failed",
                latency_ms=latency_ms,
            )

        except subprocess.TimeoutExpired:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.TIMEOUT,
                error_message=f"tmux subprocess timed out after {timeout}s.",
                latency_ms=latency_ms,
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            return SendResult(
                success=False,
                error_type=TmuxBridgeErrorType.UNKNOWN,
                error_message=f"Unexpected error: {e}",
                latency_ms=latency_ms,
            )


def get_pane_pid(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> int | None:
    """Get the root PID of a tmux pane's process.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds

    Returns:
        The pane's PID as an int, or None if not found/error.
    """
    if not _validate_pane_id(pane_id):
        return None

    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id} #{pane_pid}"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0:
            return None

        for line in result.stdout.strip().splitlines():
            parts = line.split()
            if len(parts) == 2 and parts[0] == pane_id:
                try:
                    return int(parts[1])
                except ValueError:
                    return None
        return None

    except Exception:
        return None


def _is_process_in_tree(
    pane_pid: int,
    process_names: tuple[str, ...] = DEFAULT_PROCESS_NAMES,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> bool | None:
    """Check if any of the named processes are in a pane's process tree.

    Walks children and grandchildren of pane_pid using `ps -axo pid,ppid,comm`.

    Args:
        pane_pid: The root PID of the tmux pane
        process_names: Process names to search for (case-insensitive)
        timeout: Subprocess timeout in seconds

    Returns:
        True if found, False if not found, None on error.
    """
    try:
        ps_result = subprocess.run(
            ["ps", "-axo", "pid,ppid,comm"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if ps_result.returncode != 0:
            return None

        pane_pid_str = str(pane_pid)

        # Build parent→children map
        children: dict[str, list[tuple[str, str]]] = {}
        for line in ps_result.stdout.strip().split("\n")[1:]:  # skip header
            parts = line.split(None, 2)
            if len(parts) >= 3:
                pid, ppid, comm = parts[0], parts[1], parts[2]
                children.setdefault(ppid, []).append((pid, comm))

        # Check direct children
        for child_pid, child_comm in children.get(pane_pid_str, []):
            if any(name in child_comm.lower() for name in process_names):
                return True
            # Check grandchildren (bridge → claude)
            for _gc_pid, gc_comm in children.get(child_pid, []):
                if any(name in gc_comm.lower() for name in process_names):
                    return True

        return False

    except Exception:
        return None


def check_health(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    level: HealthCheckLevel = HealthCheckLevel.COMMAND,
    process_names: tuple[str, ...] = DEFAULT_PROCESS_NAMES,
) -> HealthResult:
    """Check whether a tmux pane exists and whether Claude Code is running in it.

    Three-level check controlled by the `level` parameter:
    - EXISTS: Only checks if the pane exists in `tmux list-panes` (cheapest).
    - COMMAND: Also checks if pane_current_command matches process_names (default).
    - PROCESS_TREE: Also walks the pane's process tree via `ps` (most expensive).

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds
        level: Depth of health check (EXISTS, COMMAND, or PROCESS_TREE)
        process_names: Process names to check for (default: ("claude", "node"))

    Returns:
        HealthResult with availability, running status, and optional PID
    """
    if not _validate_pane_id(pane_id):
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    try:
        # For EXISTS level, we only need pane_id in the output
        fmt = "#{pane_id} #{pane_current_command}" if level != HealthCheckLevel.EXISTS else "#{pane_id}"
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", fmt],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        output = result.stdout.decode("utf-8", errors="replace")

        for line in output.strip().splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) >= 1 and parts[0] == pane_id:
                # Pane exists
                if level == HealthCheckLevel.EXISTS:
                    return HealthResult(available=True, running=False)

                current_command = parts[1] if len(parts) >= 2 else ""
                running = any(
                    proc in current_command.lower()
                    for proc in process_names
                )

                if level == HealthCheckLevel.COMMAND:
                    return HealthResult(available=True, running=running)

                # PROCESS_TREE level: walk the process tree
                pane_pid = get_pane_pid(pane_id, timeout=timeout)
                if pane_pid is None:
                    # Fallback to COMMAND result if we can't get PID
                    return HealthResult(available=True, running=running, pid=None)

                tree_result = _is_process_in_tree(
                    pane_pid,
                    process_names=process_names,
                    timeout=timeout,
                )
                if tree_result is True:
                    return HealthResult(available=True, running=True, pid=pane_pid)
                elif tree_result is False:
                    return HealthResult(available=True, running=False, pid=pane_pid)
                else:
                    # Can't determine — fall back to command-level result
                    return HealthResult(available=True, running=running, pid=pane_pid)

        # Pane not found in list
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
            error_message=f"tmux pane {pane_id} not found.",
        )

    except FileNotFoundError:
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
        )

    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        # tmux may not be running (no server)
        if "no server running" in stderr_text.lower() or "no current" in stderr_text.lower():
            return HealthResult(
                available=False,
                error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
                error_message="tmux server is not running.",
            )
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.SUBPROCESS_FAILED,
            error_message=f"tmux list-panes failed: {stderr_text}",
        )

    except subprocess.TimeoutExpired:
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux health check timed out after {timeout}s.",
        )

    except Exception as e:
        logger.warning(f"Unexpected health check error for pane {pane_id}: {e}")
        return HealthResult(
            available=False,
            error_type=TmuxBridgeErrorType.UNKNOWN,
            error_message=f"Unexpected error: {e}",
        )


def capture_pane(
    pane_id: str,
    lines: int = 50,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    join_wrapped: bool = False,
    include_escapes: bool = False,
) -> str:
    """Capture the last N lines of a tmux pane's visible content.

    Args:
        pane_id: The tmux pane ID
        lines: Number of lines to capture from the end
        timeout: Subprocess timeout in seconds
        join_wrapped: If True, include -J flag to join wrapped lines
        include_escapes: If True, include ANSI escape sequences (-e flag)

    Returns:
        Captured text content (empty string on error)
    """
    if not _validate_pane_id(pane_id):
        return ""

    cmd = ["tmux", "capture-pane", "-t", pane_id, "-p", "-S", f"-{lines}"]
    if join_wrapped:
        cmd.append("-J")
    if include_escapes:
        cmd.append("-e")

    try:
        result = subprocess.run(
            cmd,
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        return result.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"capture-pane failed for {pane_id}: {e}")
        return ""


def parse_permission_options(pane_text: str) -> list[dict[str, str]] | None:
    """Parse numbered permission options from tmux pane content.

    Matches lines like:
      1. Yes
      ❯ 2. Yes, and don't ask again
        3. No

    Extracts the LAST group of sequential numbered options starting from 1,
    so earlier numbered lists in the terminal output don't interfere.

    Args:
        pane_text: Raw captured pane text (may contain ANSI escape codes)

    Returns:
        List of {"label": "..."} dicts if >= 2 sequential options found, else None
    """
    if not pane_text:
        return None

    # Strip ANSI escape codes
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", pane_text)

    # Match numbered option lines (with optional arrow indicator prefix).
    # Space after period is optional — tmux wrapping can compress "2. Yes" to "2.Yes"
    # when the cursor arrow (❯) on option 1 shifts alignment.
    pattern = r"^\s*(?:[❯›>]\s*)?(\d+)\.\s*(.+?)\s*$"
    matches = re.findall(pattern, clean, re.MULTILINE)

    if len(matches) < 2:
        return None

    # Find the LAST group of sequential options starting from 1.
    # Earlier numbered lists (agent output, etc.) should be ignored.
    best_group = None
    current_group = []
    for num_str, label in matches:
        num = int(num_str)
        if num == 1:
            # Start a new group
            current_group = [(num, label)]
        elif current_group and num == current_group[-1][0] + 1:
            # Continue the current group
            current_group.append((num, label))
        else:
            # Break in sequence — save current group if valid and reset
            if len(current_group) >= 2:
                best_group = current_group
            current_group = []
    # Check final group
    if len(current_group) >= 2:
        best_group = current_group

    if not best_group:
        return None

    return [{"label": label} for _num, label in best_group]


def parse_permission_context(pane_text: str) -> dict | None:
    """Parse the full permission dialog block from tmux pane content.

    Extracts the tool type header, command text, description, and options from
    a Claude Code permission dialog that looks like:

        Bash command

          curl -s http://localhost:5055/dashboard | sed -n '630,645p'
          Check state-bar HTML around line 634

        Do you want to proceed?
        ❯ 1. Yes
          2. No

    Args:
        pane_text: Raw captured pane text (may contain ANSI escape codes)

    Returns:
        Dict with "tool_type", "command", "description", "options" keys, or None
    """
    if not pane_text:
        return None

    # Strip ANSI escape codes
    clean = re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", pane_text)

    # Parse options first — if no options, this isn't a permission dialog
    options = parse_permission_options(pane_text)
    if not options:
        return None

    # Find the LAST "Do you want to proceed?" line (or similar prompt)
    prompt_pattern = r"^\s*(Do you want to (?:proceed|allow|continue)\??|Allow this .*\??)\s*$"
    prompt_matches = list(re.finditer(prompt_pattern, clean, re.MULTILINE | re.IGNORECASE))
    prompt_match = prompt_matches[-1] if prompt_matches else None

    # Find tool type header — a line like "Bash command", "Read file", etc.
    # Use the LAST match to handle panes with multiple tool outputs.
    tool_type = None
    command_text = None
    description = None

    # Look for known tool header patterns — find the LAST one
    header_pattern = r"^\s*((?:Bash|Read|Write|Edit|Glob|Grep|WebFetch|WebSearch|NotebookEdit)\s+\w*)\s*$"
    header_matches = list(re.finditer(header_pattern, clean, re.MULTILINE | re.IGNORECASE))
    header_match = header_matches[-1] if header_matches else None

    if header_match:
        tool_type = header_match.group(1).strip()
        header_end = header_match.end()

        # The command block is indented text between the header and the prompt
        if prompt_match and prompt_match.start() > header_end:
            block_text = clean[header_end:prompt_match.start()]
        else:
            # No prompt found after header — take text up to the first option line after header
            first_option_match = re.search(r"^\s*(?:[❯›>]\s*)?\d+\.\s*", clean[header_end:], re.MULTILINE)
            if first_option_match:
                block_text = clean[header_end:header_end + first_option_match.start()]
            else:
                block_text = ""

        # Parse the block: indented lines are command/description
        block_lines = [line.strip() for line in block_text.strip().splitlines() if line.strip()]

        if block_lines:
            # First non-empty line(s) are the command, last line may be description
            # Heuristic: if last line looks like a description (starts with uppercase,
            # no special command chars), treat it as description
            if len(block_lines) >= 2 and _looks_like_description(block_lines[-1]):
                command_text = "\n".join(block_lines[:-1])
                description = block_lines[-1]
            else:
                command_text = "\n".join(block_lines)

    # Require at least one structural signal that this is actually a
    # permission dialog, not just numbered agent output (e.g. "1. Fix bug,
    # 2. Add test, 3. Refactor").  A valid dialog has a tool header
    # ("Bash command", "Read file") and/or a confirmation prompt
    # ("Do you want to proceed?").
    if not header_match and not prompt_match:
        logger.debug("Rejecting numbered list — no dialog structure found (no header or prompt)")
        return None

    return {
        "tool_type": tool_type,
        "command": command_text,
        "description": description,
        "options": options,
    }


def _looks_like_description(line: str) -> bool:
    """Heuristic: check if a line looks like a human-readable description.

    Descriptions typically:
    - Start with an uppercase letter
    - Don't start with common command prefixes (/, -, $, etc.)
    - Don't contain shell operators (|, >, &&)
    """
    if not line:
        return False
    first_char = line[0]
    if first_char in ("/", "-", "$", ".", "~", "{", "[", "(", "'", '"', "`"):
        return False
    if any(op in line for op in ("|", "&&", ">>", "<<", "$(", "${")):
        return False
    # Starts with uppercase letter — likely description
    return first_char.isupper()


def capture_permission_options(
    pane_id: str,
    max_attempts: int = 10,
    retry_delay_ms: int = 200,
    capture_lines: int = 30,
) -> list[dict[str, str]] | None:
    """Capture tmux pane content and parse permission dialog options.

    Uses wait_for_pattern to poll for numbered option lines, handling
    the race condition where the hook fires before the dialog has fully
    rendered in the terminal.

    Args:
        pane_id: The tmux pane ID
        max_attempts: Number of capture+parse attempts (used to compute timeout)
        retry_delay_ms: Delay in ms between attempts (used as poll interval)
        capture_lines: Number of pane lines to capture

    Returns:
        List of {"label": "..."} dicts if options found, else None
    """
    # Use wait_for_pattern to detect numbered option lines
    timeout_ms = max_attempts * retry_delay_ms + retry_delay_ms
    wait = wait_for_pattern(
        pane_id,
        pattern=r"^\s*(?:[❯›>]\s*)?\d+\.\s*\S",
        timeout_ms=timeout_ms,
        poll_interval_ms=retry_delay_ms,
        capture_lines=capture_lines,
        join_wrapped=True,
    )

    if wait.matched:
        options = parse_permission_options(wait.content)
        if options is not None:
            logger.debug(
                f"Parsed {len(options)} permission options from pane {pane_id} "
                f"({wait.elapsed_ms}ms)"
            )
            return options

    logger.debug(f"No permission options found in pane {pane_id} after {timeout_ms}ms")
    return None


def capture_permission_context(
    pane_id: str,
    max_attempts: int = 10,
    retry_delay_ms: int = 200,
    capture_lines: int = 30,
) -> dict | None:
    """Capture tmux pane content and parse the full permission dialog context.

    Like capture_permission_options but returns the full context dict including
    the command text and description, not just the options list.

    Uses wait_for_pattern to poll for numbered option lines, handling
    the race condition where the hook fires before the dialog has fully
    rendered in the terminal.

    Args:
        pane_id: The tmux pane ID
        max_attempts: Number of capture+parse attempts (used to compute timeout)
        retry_delay_ms: Delay in ms between attempts (used as poll interval)
        capture_lines: Number of pane lines to capture

    Returns:
        Dict with "tool_type", "command", "description", "options" keys, or None
    """
    # Use wait_for_pattern to detect numbered option lines
    timeout_ms = max_attempts * retry_delay_ms + retry_delay_ms
    wait = wait_for_pattern(
        pane_id,
        pattern=r"^\s*(?:[❯›>]\s*)?\d+\.\s*\S",
        timeout_ms=timeout_ms,
        poll_interval_ms=retry_delay_ms,
        capture_lines=capture_lines,
        join_wrapped=True,
    )

    if wait.matched:
        context = parse_permission_context(wait.content)
        if context is not None:
            logger.debug(
                f"Parsed permission context from pane {pane_id} "
                f"({wait.elapsed_ms}ms): tool_type={context.get('tool_type')}"
            )
            return context

    logger.debug(f"No permission context found in pane {pane_id} after {timeout_ms}ms")
    return None


def kill_session(
    session_name: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    socket_path: str | None = None,
) -> SendResult:
    """Kill a tmux session by name.

    Args:
        session_name: The tmux session name to kill
        timeout: Subprocess timeout in seconds
        socket_path: Optional tmux socket path (-S flag) for socket isolation

    Returns:
        SendResult with success status
    """
    if not session_name:
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message="Empty session name",
        )

    start_time = time.time()
    cmd = ["tmux"]
    if socket_path:
        cmd.extend(["-S", socket_path])
    cmd.extend(["kill-session", "-t", session_name])

    try:
        subprocess.run(
            cmd,
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Killed tmux session '{session_name}' ({latency_ms}ms)")
        return SendResult(success=True, latency_ms=latency_ms)

    except FileNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
            latency_ms=latency_ms,
        )

    except subprocess.CalledProcessError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return SendResult(
            success=False,
            error_type=_classify_subprocess_error(e),
            error_message=f"tmux kill-session failed: {stderr_text}" if stderr_text else "tmux kill-session failed",
            latency_ms=latency_ms,
        )

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux kill-session timed out after {timeout}s.",
            latency_ms=latency_ms,
        )


def list_panes(
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
    socket_path: str | None = None,
) -> list[PaneInfo]:
    """List all tmux panes with metadata.

    Args:
        timeout: Subprocess timeout in seconds
        socket_path: Optional tmux socket path (-S flag) for socket isolation

    Returns:
        List of PaneInfo with pane_id, session_name, current_command, working_directory
    """
    try:
        cmd = ["tmux"]
        if socket_path:
            cmd.extend(["-S", socket_path])
        cmd.extend([
            "list-panes", "-a", "-F",
            "#{pane_id}\t#{session_name}\t#{pane_current_command}\t#{pane_current_path}",
        ])
        result = subprocess.run(
            cmd,
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        panes = []
        for line in result.stdout.decode("utf-8", errors="replace").strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 4:
                panes.append(PaneInfo(
                    pane_id=parts[0],
                    session_name=parts[1],
                    current_command=parts[2],
                    working_directory=parts[3],
                ))
        return panes

    except Exception as e:
        logger.warning(f"list-panes failed: {e}")
        return []


def get_pane_client_tty(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> TtyResult:
    """Resolve a tmux pane ID to the client TTY that owns it.

    Two-step lookup:
    1. Find which tmux session contains the pane via `tmux list-panes -a`
    2. Find the client TTY attached to that session via `tmux list-clients`

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds

    Returns:
        TtyResult with the client TTY path (e.g., /dev/ttys003)
    """
    if not _validate_pane_id(pane_id):
        return TtyResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    # Step 1: Find which session contains this pane
    try:
        result = subprocess.run(
            ["tmux", "list-panes", "-a", "-F", "#{pane_id} #{session_name}"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        output = result.stdout.decode("utf-8", errors="replace")
        session_name = None
        for line in output.strip().splitlines():
            parts = line.split(maxsplit=1)
            if len(parts) >= 2 and parts[0] == pane_id:
                session_name = parts[1]
                break

        if session_name is None:
            return TtyResult(
                success=False,
                error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
                error_message=f"tmux pane {pane_id} not found.",
            )

    except FileNotFoundError:
        return TtyResult(
            success=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
        )

    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return TtyResult(
            success=False,
            error_type=_classify_subprocess_error(e),
            error_message=f"tmux list-panes failed: {stderr_text}" if stderr_text else "tmux list-panes failed",
        )

    except subprocess.TimeoutExpired:
        return TtyResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux list-panes timed out after {timeout}s.",
        )

    # Step 2: Find client TTY for that session
    try:
        result = subprocess.run(
            ["tmux", "list-clients", "-t", session_name, "-F", "#{client_tty}"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        output = result.stdout.decode("utf-8", errors="replace").strip()
        if not output:
            return TtyResult(
                success=False,
                session_name=session_name,
                error_type=TmuxBridgeErrorType.PANE_NOT_FOUND,
                error_message=f"No client attached to tmux session '{session_name}'.",
            )

        # Take the first client TTY
        client_tty = output.splitlines()[0].strip()
        return TtyResult(
            success=True,
            tty=client_tty,
            session_name=session_name,
        )

    except subprocess.CalledProcessError as e:
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return TtyResult(
            success=False,
            session_name=session_name,
            error_type=_classify_subprocess_error(e),
            error_message=f"tmux list-clients failed: {stderr_text}" if stderr_text else "tmux list-clients failed",
        )

    except subprocess.TimeoutExpired:
        return TtyResult(
            success=False,
            session_name=session_name,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux list-clients timed out after {timeout}s.",
        )


def select_pane(
    pane_id: str,
    timeout: float = DEFAULT_SUBPROCESS_TIMEOUT,
) -> SendResult:
    """Select a tmux pane, switching to its window first.

    Runs `tmux select-window -t <pane_id>` then `tmux select-pane -t <pane_id>`.
    tmux resolves the %N pane ID to the correct window automatically.

    Args:
        pane_id: The tmux pane ID (format: %0, %5, etc.)
        timeout: Subprocess timeout in seconds

    Returns:
        SendResult with success status
    """
    if not _validate_pane_id(pane_id):
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.NO_PANE_ID,
            error_message=f"Invalid pane ID: {pane_id!r}",
        )

    start_time = time.time()

    try:
        subprocess.run(
            ["tmux", "select-window", "-t", pane_id],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        subprocess.run(
            ["tmux", "select-pane", "-t", pane_id],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        latency_ms = int((time.time() - start_time) * 1000)
        logger.info(f"Selected tmux pane {pane_id} ({latency_ms}ms)")
        return SendResult(success=True, latency_ms=latency_ms)

    except FileNotFoundError:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TMUX_NOT_INSTALLED,
            error_message="tmux is not installed or not on PATH.",
            latency_ms=latency_ms,
        )

    except subprocess.CalledProcessError as e:
        latency_ms = int((time.time() - start_time) * 1000)
        error_type = _classify_subprocess_error(e)
        stderr_text = (e.stderr or b"").decode("utf-8", errors="replace").strip()
        return SendResult(
            success=False,
            error_type=error_type,
            error_message=f"tmux select failed: {stderr_text}" if stderr_text else "tmux select failed",
            latency_ms=latency_ms,
        )

    except subprocess.TimeoutExpired:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.TIMEOUT,
            error_message=f"tmux select timed out after {timeout}s.",
            latency_ms=latency_ms,
        )

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        return SendResult(
            success=False,
            error_type=TmuxBridgeErrorType.UNKNOWN,
            error_message=f"Unexpected error: {e}",
            latency_ms=latency_ms,
        )
