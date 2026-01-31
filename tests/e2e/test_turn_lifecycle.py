"""E2E tests: single-agent turn lifecycle (happy path).

Verifies the full session lifecycle via the dashboard:
session-start → command → processing → awaiting input → answer → session-end
"""

import time

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e


class TestSingleAgentTurnLifecycle:
    """Full lifecycle: session start through session end."""

    def test_session_start_creates_agent_card(
        self, page, e2e_server, hook_client, dashboard
    ):
        """session-start hook creates an IDLE agent card on the dashboard."""
        # Fire session-start
        result = hook_client.session_start()
        agent_id = result["agent_id"]

        # session_created SSE event triggers page reload
        page.wait_for_load_state("domcontentloaded")
        # Wait a moment for the reload to complete
        page.wait_for_timeout(500)
        # Re-navigate after reload to ensure we're on the fresh page
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()

        dashboard.assert_agent_card_exists(agent_id)
        dashboard.assert_agent_state(agent_id, "IDLE")
        dashboard.assert_status_counts(input_needed=0, working=0, idle=1)
        dashboard.capture("session_started")

    def test_user_prompt_creates_processing_state(
        self, page, e2e_server, hook_client, dashboard
    ):
        """user-prompt-submit transitions agent to PROCESSING via SSE."""
        # Setup: start session
        result = hook_client.session_start()
        agent_id = result["agent_id"]

        # Navigate to pick up the new agent card
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        # Fire user-prompt-submit
        hook_client.user_prompt_submit(prompt="Fix the login bug")

        # SSE updates state without reload
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        dashboard.assert_task_summary_contains(agent_id, "Fix the login bug")
        dashboard.assert_status_counts(input_needed=0, working=1, idle=0)
        dashboard.capture("processing")

    def test_stop_debounce_to_awaiting_input(
        self, page, e2e_server, hook_client, dashboard
    ):
        """stop hook triggers debounced transition to AWAITING_INPUT."""
        # Setup: session-start → user-prompt-submit → PROCESSING
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="Test debounce")
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # Fire stop hook - starts debounce timer (0.5s in test mode)
        hook_client.stop()

        # Wait for debounce to fire
        dashboard.assert_agent_state(agent_id, "AWAITING_INPUT", timeout=5000)
        dashboard.assert_status_counts(input_needed=1, working=0, idle=0)
        dashboard.capture("awaiting_input")

    def test_answer_returns_to_processing(
        self, page, e2e_server, hook_client, dashboard
    ):
        """user-prompt-submit from AWAITING_INPUT returns to PROCESSING."""
        # Setup: get to AWAITING_INPUT
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="Initial command")
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        hook_client.stop()
        dashboard.assert_agent_state(agent_id, "AWAITING_INPUT", timeout=5000)

        # Fire answer
        hook_client.user_prompt_submit(prompt="Yes, proceed")
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        dashboard.assert_task_summary_contains(agent_id, "Yes, proceed")
        dashboard.capture("answer_processing")

    def test_session_end_removes_card(
        self, page, e2e_server, hook_client, dashboard
    ):
        """session-end removes the agent card from the dashboard."""
        # Setup: start session and process
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="Some work")
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # End session - triggers page reload
        hook_client.session_end()
        page.wait_for_timeout(500)
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")

        dashboard.assert_agent_card_gone(agent_id)
        dashboard.capture("session_ended")

    def test_full_lifecycle_sequence(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Comprehensive: full lifecycle with screenshots at each step."""
        # 1. Session start
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)
        dashboard.assert_agent_state(agent_id, "IDLE")
        dashboard.capture("lifecycle_01_idle")

        # 2. User command → PROCESSING
        hook_client.user_prompt_submit(prompt="Implement the feature")
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        dashboard.capture("lifecycle_02_processing")

        # 3. Stop → debounce → AWAITING_INPUT
        hook_client.stop()
        dashboard.assert_agent_state(agent_id, "AWAITING_INPUT", timeout=5000)
        dashboard.capture("lifecycle_03_awaiting")

        # 4. Answer → PROCESSING again
        hook_client.user_prompt_submit(prompt="Yes, looks good")
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        dashboard.capture("lifecycle_04_processing_again")

        # 5. Session end → card removed
        hook_client.session_end()
        page.wait_for_timeout(500)
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_agent_card_gone(agent_id)
        dashboard.capture("lifecycle_05_ended")
