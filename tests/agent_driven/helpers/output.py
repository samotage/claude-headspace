"""Structured test output helper for agent-driven integration tests.

Provides step-by-step progress reporting with scenario name, step progress,
pass/fail status per assertion, and elapsed time. Output uses print() so it
does not interfere with pytest's own capture mechanism (visible with -s flag).

Plain function only -- no classes, decorators, or metaclasses (constraint C6).

Usage:
    from tests.agent_driven.helpers.output import scenario_header, scenario_footer, step

    def test_my_scenario(...):
        start = scenario_header("My Scenario")

        with step("Navigate to voice chat", num=1, total=5):
            va.navigate_to_voice(e2e_server)

        with step("Send command", num=2, total=5):
            va.send_chat_message("hello")

        scenario_footer("My Scenario", start)
"""

import time
from contextlib import contextmanager


def scenario_header(scenario_name: str) -> float:
    """Print scenario header and return the start time.

    Args:
        scenario_name: Human-readable scenario name.

    Returns:
        Start time (time.monotonic()) for elapsed calculation.
    """
    start = time.monotonic()
    print(f"\n{'=' * 60}")
    print(f"  SCENARIO: {scenario_name}")
    print(f"{'=' * 60}")
    return start


def scenario_footer(scenario_name: str, start_time: float) -> None:
    """Print scenario footer with elapsed time.

    Args:
        scenario_name: Human-readable scenario name.
        start_time: Value returned by scenario_header().
    """
    elapsed = time.monotonic() - start_time
    print(f"\n{'=' * 60}")
    print(f"  SCENARIO COMPLETE: {scenario_name}")
    print(f"  Elapsed: {elapsed:.1f}s")
    print(f"{'=' * 60}\n")


@contextmanager
def step(description: str, num: int = 0, total: int = 0):
    """Context manager that wraps a test step with progress and timing output.

    Prints step start, then on successful exit prints PASS with timing.
    On exception, prints FAIL with the error before re-raising.

    Args:
        description: What this step does (e.g. "Navigate to voice chat").
        num: Current step number (1-based). 0 to omit numbering.
        total: Total steps in the scenario. 0 to omit numbering.

    Usage:
        with step("Send command", num=1, total=5):
            va.send_chat_message("hello")
    """
    if num and total:
        prefix = f"  [{num}/{total}]"
    elif num:
        prefix = f"  [{num}]"
    else:
        prefix = "  [*]"

    print(f"{prefix} {description}...", flush=True)
    step_start = time.monotonic()

    try:
        yield
    except Exception as exc:
        elapsed = time.monotonic() - step_start
        print(f"{prefix} FAIL ({elapsed:.1f}s): {exc}")
        raise
    else:
        elapsed = time.monotonic() - step_start
        print(f"{prefix} PASS ({elapsed:.1f}s)")
