"""E2E tests: edge cases and rapid sequences.

Verifies behaviour under unusual conditions like rapid
hook firing, double prompts, and session-end during input.
"""

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e


class TestEdgeCases:
    """Edge cases and rapid sequences."""

    def test_rapid_session_start_and_prompt(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Rapid session-start + user-prompt-submit ends in PROCESSING."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        # Fire prompt immediately after start
        hook_client.user_prompt_submit(prompt="Quick start")

        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        dashboard.capture("rapid_start_prompt")

    def test_double_prompt_creates_new_task(
        self, page, e2e_server, hook_client, dashboard
    ):
        """Second prompt while processing creates a new task."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        hook_client.user_prompt_submit(prompt="First command")
        dashboard.assert_agent_state(agent_id, "PROCESSING")

        # Second prompt while still processing
        hook_client.user_prompt_submit(prompt="Second command")
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        dashboard.assert_task_instruction_contains(agent_id, "Second command")
        dashboard.capture("double_prompt")

    def test_session_end_during_awaiting_input(
        self, page, e2e_server, hook_client, dashboard
    ):
        """session-end while AWAITING_INPUT removes the card."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)

        # Get to AWAITING_INPUT via notification (the canonical path)
        hook_client.user_prompt_submit(prompt="Do work")
        dashboard.assert_agent_state(agent_id, "PROCESSING")
        hook_client.notification()
        dashboard.assert_agent_state(agent_id, "AWAITING_INPUT", timeout=5000)

        # End session during AWAITING_INPUT
        hook_client.session_end()
        page.wait_for_timeout(500)
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")

        dashboard.assert_agent_card_gone(agent_id)
        dashboard.capture("end_during_awaiting")

    def test_session_end_while_idle(
        self, page, e2e_server, hook_client, dashboard
    ):
        """session-end on IDLE agent removes the card cleanly."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_id)
        dashboard.assert_agent_state(agent_id, "IDLE")

        hook_client.session_end()
        page.wait_for_timeout(500)
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")

        dashboard.assert_agent_card_gone(agent_id)
        dashboard.capture("end_while_idle")
