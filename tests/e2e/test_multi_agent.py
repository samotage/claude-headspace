"""E2E tests: multi-agent scenarios.

Verifies that multiple agents on different projects
maintain independent lifecycles on the dashboard.
"""

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e


class TestMultiAgent:
    """Tests for multiple agents on different projects."""

    def test_two_agents_independent_states(
        self, page, e2e_server, make_hook_client, dashboard
    ):
        """Two agents maintain independent state transitions."""
        # Use distinct working directories so they create separate projects
        client_a = make_hook_client(
            working_directory="/Users/samotage/dev/e2e-test/project-alpha"
        )
        client_b = make_hook_client(
            working_directory="/Users/samotage/dev/e2e-test/project-beta"
        )

        # Start both agents
        result_a = client_a.session_start()
        agent_a = result_a["agent_id"]

        result_b = client_b.session_start()
        agent_b = result_b["agent_id"]

        # Reload to pick up both agents
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()
        dashboard.assert_agent_card_exists(agent_a)
        dashboard.assert_agent_card_exists(agent_b)
        dashboard.capture("multi_01_both_idle")

        # Agent A starts processing
        client_a.user_prompt_submit(prompt="Work on feature A")
        dashboard.assert_agent_state(agent_a, "PROCESSING")
        dashboard.assert_agent_state(agent_b, "IDLE")
        dashboard.assert_status_counts(input_needed=0, working=1, idle=1)
        dashboard.capture("multi_02_a_processing")

        # Agent B starts processing
        client_b.user_prompt_submit(prompt="Work on feature B")
        dashboard.assert_agent_state(agent_a, "PROCESSING")
        dashboard.assert_agent_state(agent_b, "PROCESSING")
        dashboard.assert_status_counts(input_needed=0, working=2, idle=0)
        dashboard.capture("multi_03_both_processing")

        # Agent A stops → immediate COMPLETE
        client_a.stop()
        dashboard.assert_agent_state(agent_a, "COMPLETE", timeout=3000)
        dashboard.assert_agent_state(agent_b, "PROCESSING")
        dashboard.assert_status_counts(input_needed=0, working=1, idle=1)
        dashboard.capture("multi_04_a_complete")

    def test_end_one_agent_preserves_other(
        self, page, e2e_server, make_hook_client, dashboard
    ):
        """Ending one agent preserves the other's state."""
        client_a = make_hook_client(
            working_directory="/Users/samotage/dev/e2e-test/project-gamma"
        )
        client_b = make_hook_client(
            working_directory="/Users/samotage/dev/e2e-test/project-delta"
        )

        # Start both, both processing
        result_a = client_a.session_start()
        agent_a = result_a["agent_id"]
        result_b = client_b.session_start()
        agent_b = result_b["agent_id"]

        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()

        client_a.user_prompt_submit(prompt="Work A")
        client_b.user_prompt_submit(prompt="Work B")
        dashboard.assert_agent_state(agent_a, "PROCESSING")
        dashboard.assert_agent_state(agent_b, "PROCESSING")

        # End agent A
        client_a.session_end()
        page.wait_for_timeout(500)
        page.goto(e2e_server)
        page.wait_for_load_state("domcontentloaded")
        dashboard.assert_sse_connected()

        # Agent A gone, agent B still present
        dashboard.assert_agent_card_gone(agent_a)
        dashboard.assert_agent_card_exists(agent_b)
        dashboard.capture("multi_end_one_preserves_other")
