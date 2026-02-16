"""Readable Playwright assertions for voice app state.

Provides a high-level API for asserting voice chat DOM state,
wrapping Playwright's expect() with domain-specific methods.
Modeled on DashboardAssertions.
"""

from pathlib import Path

from playwright.sync_api import Page, expect


class VoiceAssertions:
    """Readable Playwright assertions for voice app state."""

    def __init__(self, page: Page, screenshot_dir: Path):
        self.page = page
        self.screenshot_dir = screenshot_dir
        self._step = 0

    def navigate_to_voice(self, base_url: str):
        """Go to /voice, inject localStorage credentials, reload."""
        self.page.goto(f"{base_url}/voice")
        self.page.evaluate(
            """(baseUrl) => {
            localStorage.setItem('voice_settings', JSON.stringify({
                serverUrl: baseUrl, token: 'test', theme: 'dark', fontSize: 15
            }));
        }""",
            base_url,
        )
        self.page.reload()
        self.page.wait_for_load_state("domcontentloaded")

    def assert_on_agents_screen(self, timeout: int = 10000):
        """Verify sidebar visible, setup screen absent."""
        expect(self.page.locator("#sidebar")).to_be_visible(timeout=timeout)
        expect(self.page.locator("#screen-setup.active")).to_have_count(
            0, timeout=timeout
        )

    def assert_setup_screen_visible(self, timeout: int = 10000):
        """Verify setup screen is active."""
        expect(self.page.locator("#screen-setup.active")).to_be_visible(timeout=timeout)

    def assert_agent_card_visible(self, agent_id: int, timeout: int = 10000):
        """Wait for .agent-card[data-agent-id="N"]."""
        expect(
            self.page.locator(f'.agent-card[data-agent-id="{agent_id}"]')
        ).to_be_visible(timeout=timeout)

    def select_agent(self, agent_id: int, timeout: int = 10000):
        """Click card, wait for #screen-chat.active."""
        card = self.page.locator(f'.agent-card[data-agent-id="{agent_id}"]')
        card.click()
        expect(self.page.locator("#screen-chat.active")).to_be_visible(timeout=timeout)

    def assert_chat_screen_active(self, timeout: int = 10000):
        """#screen-chat has .active."""
        expect(self.page.locator("#screen-chat.active")).to_be_visible(timeout=timeout)

    def assert_bubble_exists(self, turn_id, timeout: int = 10000):
        """Wait for [data-turn-id="N"]."""
        expect(
            self.page.locator(f'[data-turn-id="{turn_id}"]')
        ).to_be_visible(timeout=timeout)

    def send_chat_message(self, text: str):
        """Fill #chat-text-input, submit form."""
        self.page.fill("#chat-text-input", text)
        self.page.click("#chat-send-btn")

    def assert_typing_indicator_visible(self, timeout: int = 10000):
        """Typing indicator is displayed."""
        expect(self.page.locator("#chat-typing")).to_be_visible(timeout=timeout)

    def assert_typing_indicator_hidden(self, timeout: int = 10000):
        """Typing indicator is hidden."""
        expect(self.page.locator("#chat-typing")).to_be_hidden(timeout=timeout)

    def assert_state_pill(self, text: str, timeout: int = 10000):
        """#chat-state-pill content."""
        expect(self.page.locator("#chat-state-pill")).to_contain_text(
            text, timeout=timeout
        )

    def assert_connection_indicator(self, state: str, timeout: int = 10000):
        """#connection-status has the expected class."""
        expect(self.page.locator("#connection-status")).to_have_class(
            f"connection-dot {state}", timeout=timeout
        )

    def assert_ended_banner_visible(self, timeout: int = 10000):
        """Ended banner is displayed."""
        expect(self.page.locator("#chat-ended-banner")).to_be_visible(timeout=timeout)

    def assert_ended_banner_hidden(self, timeout: int = 10000):
        """Ended banner is hidden."""
        expect(self.page.locator("#chat-ended-banner")).to_be_hidden(timeout=timeout)

    def assert_empty_agent_state(self, timeout: int = 10000):
        """No active agents message visible."""
        expect(self.page.locator("#agent-list .empty-state")).to_be_visible(
            timeout=timeout
        )

    def assert_project_group_visible(self, project_name: str, timeout: int = 10000):
        """Project group header with name visible."""
        expect(
            self.page.locator(f".project-group-name:has-text('{project_name}')")
        ).to_be_visible(timeout=timeout)

    def assert_settings_panel_open(self, timeout: int = 10000):
        """Settings panel is open."""
        expect(self.page.locator("#settings-panel.open")).to_be_visible(
            timeout=timeout
        )

    def assert_settings_panel_closed(self, timeout: int = 5000):
        """Settings panel is closed."""
        expect(self.page.locator("#settings-panel.open")).to_have_count(
            0, timeout=timeout
        )

    def assert_project_picker_open(self, timeout: int = 10000):
        """Project picker is open."""
        expect(self.page.locator("#project-picker.open")).to_be_visible(
            timeout=timeout
        )

    def assert_project_picker_closed(self, timeout: int = 5000):
        """Project picker is closed."""
        expect(self.page.locator("#project-picker.open")).to_have_count(
            0, timeout=timeout
        )

    def get_agent_card_state(self, agent_id: int) -> str:
        """Read the state class from an agent card."""
        card = self.page.locator(f'.agent-card[data-agent-id="{agent_id}"]')
        classes = card.get_attribute("class") or ""
        for cls in classes.split():
            if cls.startswith("state-"):
                return cls.replace("state-", "")
        return ""

    def capture(self, name: str):
        """Save a screenshot with step numbering."""
        self._step += 1
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        path = self.screenshot_dir / f"{self._step:02d}_{name}.png"
        self.page.screenshot(path=str(path))
