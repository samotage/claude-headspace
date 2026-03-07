"""Send pipeline — text delivery, ghost text handling, Enter verification."""

import logging
import os
import subprocess
import tempfile
import threading
import time

from .read import _has_autocomplete_ghost, capture_pane
from .types import (
    DEFAULT_CLEAR_DELAY_MS,
    DEFAULT_ENTER_VERIFY_DELAY_MS,
    DEFAULT_ENTER_VERIFY_LINES,
    DEFAULT_MAX_ENTER_RETRIES,
    DEFAULT_SEQUENTIAL_SEND_DELAY_MS,
    DEFAULT_SUBPROCESS_TIMEOUT,
    DEFAULT_TEXT_ENTER_DELAY_MS,
    SEND_KEYS_LITERAL_MAX,
    SendResult,
    TmuxBridgeErrorType,
    _classify_subprocess_error,
    _validate_pane_id,
)
from .read import _diagnostic_dump

logger = logging.getLogger(__name__)

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
            pane_id,
            lines=DEFAULT_ENTER_VERIFY_LINES,
            timeout=timeout,
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
            f"Pane {pane_id} unchanged after Enter (attempt {attempt}/{max_retries})"
        )

        # Check for autocomplete ghost text that may have appeared
        ghost_content = capture_pane(
            pane_id,
            lines=3,
            include_escapes=True,
            timeout=timeout,
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


def _send_literal_text(
    pane_id: str,
    text: str,
    timeout: float,
) -> None:
    """Send literal text to a tmux pane, choosing the best transport.

    For short text (<= SEND_KEYS_LITERAL_MAX bytes), uses ``send-keys -l``.
    For longer text, writes to a temp file and uses ``load-buffer`` +
    ``paste-buffer`` to bypass the send-keys argument length limit.

    Args:
        pane_id: The tmux pane ID
        text: The literal text to send (no trailing Enter)
        timeout: Subprocess timeout in seconds

    Raises:
        subprocess.CalledProcessError: If any tmux command fails
        FileNotFoundError: If tmux binary not found
        subprocess.TimeoutExpired: If any tmux command times out
    """
    if len(text.encode("utf-8")) <= SEND_KEYS_LITERAL_MAX:
        subprocess.run(
            ["tmux", "send-keys", "-t", pane_id, "-l", text],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
        return

    # Large text: write to a temp file, load into a named tmux buffer,
    # then paste that buffer into the target pane.
    logger.debug(
        f"Text exceeds send-keys limit ({len(text)} chars / "
        f"{len(text.encode('utf-8'))} bytes), "
        f"using load-buffer for pane {pane_id}"
    )
    buffer_name = f"inject-{pane_id.replace('%', '')}"
    fd, tmppath = tempfile.mkstemp(prefix="tmux_inject_", suffix=".txt")
    try:
        os.write(fd, text.encode("utf-8"))
        os.close(fd)

        subprocess.run(
            ["tmux", "load-buffer", "-b", buffer_name, tmppath],
            check=True,
            timeout=timeout,
            capture_output=True,
        )

        subprocess.run(
            ["tmux", "paste-buffer", "-t", pane_id, "-b", buffer_name, "-d"],
            check=True,
            timeout=timeout,
            capture_output=True,
        )
    finally:
        try:
            os.unlink(tmppath)
        except OSError:
            pass


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
                    pane_id,
                    lines=3,
                    include_escapes=True,
                    timeout=timeout,
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
            # Uses load-buffer + paste-buffer for large payloads to avoid
            # the tmux send-keys argument length limit.
            _send_literal_text(pane_id, sanitised, timeout)

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
                    pane_id,
                    lines=3,
                    include_escapes=True,
                    timeout=timeout,
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
                    pane_id,
                    lines=DEFAULT_ENTER_VERIFY_LINES,
                    timeout=timeout,
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
                error_message=f"tmux send-keys failed: {stderr_text}"
                if stderr_text
                else "tmux send-keys failed",
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
                error_message=f"Interrupt failed: {stderr_text}"
                if stderr_text
                else "Interrupt failed",
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
            logger.info(
                f"Interrupt + send to tmux pane {pane_id} ({total_latency_ms}ms)"
            )
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
                    pane_id,
                    lines=DEFAULT_ENTER_VERIFY_LINES,
                    timeout=timeout,
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
                error_message=f"tmux send-keys failed: {stderr_text}"
                if stderr_text
                else "tmux send-keys failed",
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
