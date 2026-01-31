"""Readable Playwright assertions for dashboard state.

Provides a high-level API for asserting dashboard DOM state,
wrapping Playwright's expect() with domain-specific methods.
"""

from pathlib import Path

from playwright.sync_api import Page, expect


class DashboardAssertions:
    """Readable Playwright assertions for dashboard state."""

    def __init__(self, page: Page, screenshot_dir: Path):
        self.page = page
        self.screenshot_dir = screenshot_dir
        self._step = 0

    def assert_agent_state(self, agent_id: int, state: str, timeout: int = 10000):
        """Wait for agent card data-state attribute to match."""
        locator = self.page.locator(f'article[data-agent-id="{agent_id}"]')
        expect(locator).to_have_attribute("data-state", state, timeout=timeout)

    def assert_state_label(self, agent_id: int, text: str, timeout: int = 10000):
        """Wait for .state-label text content to match."""
        locator = self.page.locator(
            f'article[data-agent-id="{agent_id}"] .state-label'
        )
        expect(locator).to_contain_text(text, timeout=timeout)

    def assert_task_summary_contains(
        self, agent_id: int, text: str, timeout: int = 10000
    ):
        """Wait for .task-summary to contain text."""
        locator = self.page.locator(
            f'article[data-agent-id="{agent_id}"] .task-summary'
        )
        expect(locator).to_contain_text(text, timeout=timeout)

    def assert_status_counts(
        self,
        input_needed: int,
        working: int,
        idle: int,
        timeout: int = 10000,
    ):
        """Wait for header status count badges to match."""
        expect(
            self.page.locator("#status-input-needed .status-count")
        ).to_have_text(f"[{input_needed}]", timeout=timeout)
        expect(
            self.page.locator("#status-working .status-count")
        ).to_have_text(f"[{working}]", timeout=timeout)
        expect(
            self.page.locator("#status-idle .status-count")
        ).to_have_text(f"[{idle}]", timeout=timeout)

    def assert_sse_connected(self, timeout: int = 10000):
        """Wait for SSE connection indicator to show connected."""
        expect(
            self.page.locator("#connection-indicator .connection-text")
        ).to_have_text("SSE live", timeout=timeout)

    def assert_agent_card_exists(self, agent_id: int, timeout: int = 10000):
        """Wait for agent card to appear in DOM."""
        expect(
            self.page.locator(f'article[data-agent-id="{agent_id}"]')
        ).to_be_visible(timeout=timeout)

    def assert_agent_card_gone(self, agent_id: int, timeout: int = 15000):
        """Wait for agent card to disappear (after page reload)."""
        expect(
            self.page.locator(f'article[data-agent-id="{agent_id}"]')
        ).to_have_count(0, timeout=timeout)

    def capture(self, name: str):
        """Save a screenshot with step numbering."""
        self._step += 1
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshot_dir / f"{self._step:02d}_{name}.png"
        self.page.screenshot(path=str(path))
