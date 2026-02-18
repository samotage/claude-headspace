"""E2E tests: multi-agent scenarios.

Verifies that multiple agents on different projects
maintain independent lifecycles on the dashboard.
"""

import shutil
import tempfile

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e


@pytest.fixture
def temp_project_dirs(e2e_app):
    """Create temporary directories and register as projects.

    Uses a location under HOME (not /var or /tmp) because the session
    correlator rejects paths under /tmp, /private/tmp, and /var.
    Projects must be pre-registered since auto-creation is disabled.
    """
    from pathlib import Path

    from claude_headspace.database import db
    from claude_headspace.models.project import Project, generate_slug

    base = Path.home() / ".claude-e2e-test"
    base.mkdir(exist_ok=True)
    dirs = []
    for name in ("project-alpha", "project-beta", "project-gamma", "project-delta"):
        d = tempfile.mkdtemp(prefix=f"{name}-", dir=str(base))
        dirs.append(d)

    # Register each directory as a project in the DB
    with e2e_app.app_context():
        for d in dirs:
            project_name = Path(d).name
            project = Project(
                name=project_name,
                slug=generate_slug(project_name),
                path=d,
            )
            db.session.add(project)
        db.session.commit()

    yield dirs

    for d in dirs:
        shutil.rmtree(d, ignore_errors=True)
    # Clean up base dir if empty
    try:
        base.rmdir()
    except OSError:
        pass


class TestMultiAgent:
    """Tests for multiple agents on different projects."""

    def test_two_agents_independent_states(
        self, page, e2e_server, make_hook_client, dashboard, temp_project_dirs
    ):
        """Two agents maintain independent state transitions."""
        # Use distinct working directories so they create separate projects
        client_a = make_hook_client(
            working_directory=temp_project_dirs[0]
        )
        client_b = make_hook_client(
            working_directory=temp_project_dirs[1]
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

        # Agent A stops → command completes (kanban creates condensed card + resets to IDLE)
        client_a.stop()
        dashboard.assert_task_completed(agent_a, timeout=3000)
        dashboard.assert_agent_state(agent_b, "PROCESSING")
        dashboard.assert_status_counts(input_needed=0, working=1, idle=1)
        dashboard.capture("multi_04_a_complete")

    def test_end_one_agent_preserves_other(
        self, page, e2e_server, make_hook_client, dashboard, temp_project_dirs
    ):
        """Ending one agent preserves the other's state."""
        client_a = make_hook_client(
            working_directory=temp_project_dirs[2]
        )
        client_b = make_hook_client(
            working_directory=temp_project_dirs[3]
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
