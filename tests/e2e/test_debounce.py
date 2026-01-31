"""E2E tests: debounce timing for stop hook.

Verifies the debounce mechanism that delays AWAITING_INPUT
after a stop hook, and how notification/prompt cancels it.
"""

import time

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e


class TestDebounce:
    """Tests for the stop hook debounce mechanism."""

    def test_notification_overrides_stop_debounce(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Notification immediately triggers AWAITING_INPUT, overriding stop debounce."""
        # Setup: session-start → user-prompt-submit → PROCESSING
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("networkidle")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="Do something")
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # Fire stop (starts 0.5s debounce)
        hook_client.stop()
        # Wait briefly, then fire notification before debounce expires
        time.sleep(0.2)
        hook_client.notification()

        # Notification should immediately set AWAITING_INPUT
        dashboard.assert_agent_state(agent_id, "AWAITING_INPUT", timeout=3000)
        dashboard.capture("notification_override")

    def test_mid_turn_stop_cancelled_by_prompt(
        self, page, e2e_server, hook_client, dashboard
    ):
        """user-prompt-submit cancels pending stop debounce."""
        # Setup: session-start → user-prompt-submit → PROCESSING
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("networkidle")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="Start work")
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # Fire stop (starts debounce)
        hook_client.stop()
        time.sleep(0.2)

        # Fire another prompt - cancels the debounce
        hook_client.user_prompt_submit(prompt="Continue working")

        # Should still be PROCESSING (debounce was cancelled)
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # Wait longer than debounce period to confirm it never fires
        time.sleep(1.0)
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        dashboard.capture("mid_turn_stop_cancelled")

    def test_stop_without_prior_processing_is_harmless(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Stop on IDLE agent is a no-op."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("networkidle")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)
        dashboard.assert_agent_state(agent_id, "IDLE")

        # Fire stop on IDLE - should be harmless
        hook_client.stop()

        # Wait longer than debounce
        time.sleep(1.0)
        dashboard.assert_agent_state(agent_id, "IDLE")
        dashboard.capture("stop_on_idle_harmless")
