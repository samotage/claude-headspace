"""Agent-driven integration test fixtures.

Launches a real Claude Code session in a tmux pane with hooks pointing
to a test Flask server. Provides a ready gate (waits for session-start
hook) and conditional teardown (cleanup on success, preserve on failure).
"""

import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

# Re-export session-scoped E2E fixtures so pytest discovers them.
from tests.e2e.conftest import (  # noqa: F401
    e2e_test_db,
    e2e_app,
    e2e_server,
    browser_context_args,
)

PROJECT_ROOT = Path(__file__).parent.parent.parent

# Generous timeouts for real Claude Code sessions
READY_GATE_TIMEOUT = 45  # seconds to wait for session-start hook
RESPONSE_TIMEOUT = 60000  # ms — Playwright timeout for agent response


# ---------------------------------------------------------------------------
# Session-scoped: cleanup stale test tmux sessions from previous runs
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def cleanup_stale_test_sessions():
    """Kill any headspace-test-* tmux sessions left over from previous runs.

    When a test fails, its tmux session is preserved for debugging. But if
    that session is still alive when the next test run starts, its hooks
    create rogue Agents that contaminate the ready gate.
    """
    result = subprocess.run(
        ["tmux", "list-sessions", "-F", "#{session_name}"],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        for name in result.stdout.strip().split("\n"):
            if name.startswith("headspace-test-"):
                subprocess.run(
                    ["tmux", "kill-session", "-t", name],
                    capture_output=True,
                )
    yield


# ---------------------------------------------------------------------------
# pytest hook: capture test outcome for conditional teardown
# ---------------------------------------------------------------------------

@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# ---------------------------------------------------------------------------
# claude_session fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def claude_session(e2e_app, e2e_server, request):
    """Launch a real Claude Code CLI in a tmux pane, wait for session-start hook.

    Yields:
        dict with keys: agent_id (int), session_name (str)

    On success: kills tmux session (DB cleanup handled by clean_db fixture).
    On failure: preserves tmux session and DB state for investigation.
    """
    session_name = f"headspace-test-{uuid4().hex[:8]}"

    # Record the highest existing Agent ID so the ready gate only accepts
    # agents created AFTER this fixture launches its tmux session. Without
    # this, hooks from a lingering failed-test tmux session can create a
    # rogue Agent that the ready gate picks up instead of the real one.
    from claude_headspace.database import db
    from claude_headspace.models.agent import Agent

    with e2e_app.app_context():
        max_agent_id = db.session.query(db.func.max(Agent.id)).scalar() or 0

    # Create tmux session with hooks pointing to the test server
    subprocess.run(
        [
            "tmux", "new-session", "-d",
            "-s", session_name,
            "-c", str(PROJECT_ROOT),
            "-x", "200", "-y", "50",
            "-e", f"CLAUDE_HEADSPACE_URL={e2e_server}",
            "-e", f"CLAUDE_HEADSPACE_TMUX_SESSION={session_name}",
        ],
        check=True,
        timeout=10,
    )

    # Wait for the shell inside the tmux pane to finish loading its profile.
    # Without this delay, send-keys can arrive before the shell is ready,
    # causing the command to be lost or garbled.
    time.sleep(3)

    # Launch Claude CLI inside the tmux pane.
    # - unset CLAUDECODE: allows launch inside a parent Claude Code session
    # - --model haiku: cost control
    subprocess.run(
        [
            "tmux", "send-keys", "-t", session_name,
            "unset CLAUDECODE && claude --model haiku",
            "Enter",
        ],
        check=True,
        timeout=5,
    )

    # Ready gate: poll DB for an Agent created AFTER max_agent_id
    agent_id = None
    deadline = time.time() + READY_GATE_TIMEOUT
    with e2e_app.app_context():
        while time.time() < deadline:
            agent = (
                db.session.query(Agent)
                .filter(Agent.ended_at.is_(None))
                .filter(Agent.id > max_agent_id)
                .order_by(Agent.id.desc())
                .first()
            )
            if agent:
                agent_id = agent.id
                break
            db.session.expire_all()
            time.sleep(1)

    if agent_id is None:
        # Capture pane content for diagnostics before killing
        pane_capture = subprocess.run(
            ["tmux", "capture-pane", "-t", session_name, "-p", "-S", "-50"],
            capture_output=True,
            text=True,
        )
        pane_content = pane_capture.stdout if pane_capture.returncode == 0 else "(capture failed)"

        # Kill the tmux session — ready gate failed
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
        )
        pytest.fail(
            f"Ready gate timeout: no Agent registered within {READY_GATE_TIMEOUT}s "
            f"(tmux session: {session_name})\n"
            f"--- tmux pane content ---\n{pane_content}"
        )

    yield {"agent_id": agent_id, "session_name": session_name}

    # --- Conditional teardown ---
    failed = (
        hasattr(request.node, "rep_call")
        and request.node.rep_call.failed
    )

    if failed:
        print(f"\n⚠️  Test FAILED — preserving tmux session: {session_name}")
        print(f"    Inspect: tmux attach-session -t {session_name}")
    else:
        # Kill the tmux session. DB cleanup is handled by the
        # clean_db autouse fixture (from e2e/conftest.py) which
        # truncates tables and re-seeds the Project atomically.
        subprocess.run(
            ["tmux", "kill-session", "-t", session_name],
            capture_output=True,
        )
