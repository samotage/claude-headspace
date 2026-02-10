"""E2E tests: stop hook and notification hook behaviour.

Verifies that the stop hook immediately completes the task (no debounce),
and that the notification hook is the signal for AWAITING_INPUT.

Note: The stop-hook debounce mechanism was deprecated. Stop now
transitions immediately to COMPLETE. AWAITING_INPUT is reached only
via the notification hook.
"""

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e


class TestStopAndNotificationBehaviour:
    """Tests for stop (immediate COMPLETE) and notification (AWAITING_INPUT)."""

    def test_stop_immediately_completes_task(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Stop hook immediately transitions task to COMPLETE (no debounce)."""
        # Setup: session-start -> user-prompt-submit -> PROCESSING
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="Do something")
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # Fire stop — should immediately complete the task
        hook_client.stop()
        dashboard.assert_task_completed(agent_id, timeout=3000)
        dashboard.assert_status_counts(input_needed=0, working=0, idle=1)
        dashboard.capture("stop_immediate_complete")

    def test_notification_triggers_awaiting_input(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Notification hook transitions PROCESSING task to AWAITING_INPUT."""
        # Setup: session-start -> user-prompt-submit -> PROCESSING
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="Do something")
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # Fire notification — should transition to AWAITING_INPUT
        hook_client.notification()
        dashboard.assert_agent_state(agent_id, "AWAITING_INPUT", timeout=3000)
        dashboard.assert_status_counts(input_needed=1, working=0, idle=0)
        dashboard.capture("notification_awaiting_input")

    def test_stop_without_prior_processing_is_harmless(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Stop on IDLE agent is a no-op."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)
        dashboard.assert_agent_state(agent_id, "IDLE")

        # Fire stop on IDLE — should remain IDLE
        hook_client.stop()

        # Brief wait then verify still IDLE
        page.wait_for_timeout(500)
        dashboard.assert_agent_state(agent_id, "IDLE")
        dashboard.capture("stop_on_idle_harmless")
