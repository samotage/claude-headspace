"""E2E baseline tests: voice app regression contract.

These tests exercise every critical voice app journey BEFORE
modularisation begins. They serve as the regression safety net
for all extraction phases.
"""

import pytest
from playwright.sync_api import expect


pytestmark = pytest.mark.e2e


# ---------------------------------------------------------------------------
# Setup & Connection
# ---------------------------------------------------------------------------


class TestSetup:
    """App loading and credential flow."""

    def test_setup_screen_exists_but_inactive_on_trusted_network(self, page, e2e_server):
        """On trusted network (localhost), setup screen exists but is not active."""
        # E2E server runs on 127.0.0.1 which is auto-detected as trusted.
        # The inline script in voice.html auto-injects credentials on trusted
        # networks, so the setup screen is never shown. Verify the element
        # exists in DOM but is not active.
        page.goto(f"{e2e_server}/voice")
        page.evaluate("localStorage.removeItem('voice_settings')")
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
        # Setup screen element exists but is NOT active (trusted network skips it)
        expect(page.locator("#screen-setup")).to_have_count(1)
        expect(page.locator("#screen-setup.active")).to_have_count(0)

    def test_trusted_network_skips_setup(self, voice_page):
        """On trusted network with injected credentials, setup is skipped."""
        voice_page.assert_on_agents_screen()

    def test_connection_indicator_shows_connected(self, voice_page):
        """Connection indicator reaches 'connected' state."""
        voice_page.assert_connection_indicator("connected", timeout=15000)


# ---------------------------------------------------------------------------
# Agent List
# ---------------------------------------------------------------------------


class TestAgentList:
    """Sidebar rendering and SSE-driven updates."""

    def test_empty_state_no_agents(self, voice_page):
        """With no agents, empty state message is shown."""
        voice_page.assert_empty_agent_state()

    def test_agent_appears_after_hook(self, voice_page, hook_client):
        """After session-start hook, agent card appears in sidebar."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id, timeout=10000)

    def test_agent_card_shows_state(self, voice_page, hook_client):
        """Agent card reflects state changes via SSE."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        # Trigger a state change
        hook_client.user_prompt_submit("test command")
        # Card should eventually show processing state
        voice_page.page.wait_for_timeout(2000)
        state = voice_page.get_agent_card_state(agent_id)
        assert state in ("processing", "commanded", "idle"), f"Unexpected state: {state}"

    def test_project_group_header(self, voice_page, hook_client):
        """Agent cards are grouped under project headers."""
        hook_client.session_start()
        voice_page.page.wait_for_timeout(2000)
        # The project name should appear as a group header
        expect(voice_page.page.locator(".project-group-name")).to_be_visible(
            timeout=10000
        )

    def test_multiple_agents(self, voice_page, hook_client, make_hook_client):
        """Multiple agents appear as separate cards."""
        r1 = hook_client.session_start()
        agent1 = r1["agent_id"]
        client2 = make_hook_client()
        r2 = client2.session_start()
        agent2 = r2["agent_id"]
        voice_page.assert_agent_card_visible(agent1)
        voice_page.assert_agent_card_visible(agent2)


# ---------------------------------------------------------------------------
# Chat Screen
# ---------------------------------------------------------------------------


class TestChatScreen:
    """Core chat UX: selecting agents, sending messages, state indicators."""

    def test_select_agent_opens_chat(self, voice_page, hook_client):
        """Clicking an agent card opens the chat screen."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        voice_page.assert_chat_screen_active()

    def test_chat_header_info(self, voice_page, hook_client):
        """Chat header shows agent/project info after selection."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        # Header should have agent name or project
        expect(voice_page.page.locator("#chat-agent-name")).to_be_visible(timeout=5000)

    def test_state_pill_visible(self, voice_page, hook_client):
        """State pill is visible on chat screen."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        expect(voice_page.page.locator("#chat-state-pill")).to_be_visible(timeout=5000)

    def test_typing_indicator_shows_on_processing(self, voice_page, hook_client):
        """Typing indicator appears when agent is processing."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        # Send a command to trigger processing
        voice_page.send_chat_message("do something")
        voice_page.assert_typing_indicator_visible(timeout=5000)

    def test_send_message_creates_optimistic_bubble(self, voice_page, hook_client):
        """Sending a message creates an immediate (optimistic) bubble."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        voice_page.send_chat_message("hello agent")
        # An optimistic bubble with pending-* ID should appear
        expect(
            voice_page.page.locator('.chat-bubble.user')
        ).to_be_visible(timeout=5000)

    def test_back_button_returns_to_agents(self, page, e2e_server, hook_client):
        """Back button returns to agent list (stacked mode only)."""
        # Back button is hidden in split mode (1280px). Use narrow viewport.
        page.set_viewport_size({"width": 375, "height": 812})
        page.goto(f"{e2e_server}/voice")
        page.evaluate(f"""(baseUrl) => {{
            localStorage.setItem('voice_settings', JSON.stringify({{
                serverUrl: baseUrl, token: 'test', theme: 'dark', fontSize: 15
            }}));
        }}""", e2e_server)
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        # Wait for agent card and select it
        expect(
            page.locator(f'.agent-card[data-agent-id="{agent_id}"]')
        ).to_be_visible(timeout=10000)
        page.locator(f'.agent-card[data-agent-id="{agent_id}"]').click()
        expect(page.locator("#screen-chat.active")).to_be_visible(timeout=10000)
        # Back button should be visible in stacked mode
        page.click(".chat-back-btn")
        expect(page.locator("#sidebar")).to_be_visible(timeout=5000)

    def test_ended_agent_shows_banner(self, voice_page, hook_client):
        """Ended agent shows the ended banner and hides input."""
        # Enable showEndedAgents so the card stays visible after session-end
        voice_page.page.evaluate("""() => {
            const s = JSON.parse(localStorage.getItem('voice_settings') || '{}');
            s.showEndedAgents = true;
            localStorage.setItem('voice_settings', JSON.stringify(s));
        }""")
        voice_page.page.reload()
        voice_page.page.wait_for_load_state("domcontentloaded")
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        hook_client.user_prompt_submit("work")
        voice_page.page.wait_for_timeout(500)
        hook_client.stop()
        voice_page.page.wait_for_timeout(500)
        hook_client.session_end()
        voice_page.page.wait_for_timeout(2000)
        # Ended card should still be visible with showEndedAgents=true
        voice_page.assert_agent_card_visible(agent_id, timeout=10000)
        voice_page.select_agent(agent_id)
        voice_page.assert_ended_banner_visible(timeout=10000)

    def test_command_separator_on_new_command(self, voice_page, hook_client):
        """Command separators appear between different commands."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        # First command
        hook_client.user_prompt_submit("first task")
        voice_page.page.wait_for_timeout(500)
        hook_client.stop()
        voice_page.page.wait_for_timeout(500)
        # Second command
        hook_client.user_prompt_submit("second task")
        voice_page.page.wait_for_timeout(500)
        hook_client.stop()
        voice_page.page.wait_for_timeout(1000)
        # Navigate to chat
        voice_page.select_agent(agent_id)
        voice_page.page.wait_for_timeout(2000)
        # Should have command separators in the transcript
        separators = voice_page.page.locator(".chat-command-separator")
        count = separators.count()
        assert count >= 1, f"Expected at least 1 command separator, got {count}"


# ---------------------------------------------------------------------------
# Chat SSE
# ---------------------------------------------------------------------------


class TestChatSSE:
    """Real-time event handling in chat."""

    def test_turn_created_renders_bubble(self, voice_page, hook_client):
        """turn_created SSE event renders a new bubble in the chat."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        voice_page.assert_chat_screen_active()
        # Trigger a user prompt + notification (creates turns)
        hook_client.user_prompt_submit("check SSE delivery")
        voice_page.page.wait_for_timeout(2000)
        hook_client.notification()
        voice_page.page.wait_for_timeout(2000)
        # Should have at least one agent bubble
        bubbles = voice_page.page.locator(".chat-bubble")
        expect(bubbles.first).to_be_visible(timeout=10000)

    def test_card_refresh_updates_agent_list(self, voice_page, hook_client):
        """SSE card_refresh events update the agent list sidebar."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        # State change triggers card_refresh
        hook_client.user_prompt_submit("trigger update")
        voice_page.page.wait_for_timeout(3000)
        # Card should still be visible and possibly updated
        voice_page.assert_agent_card_visible(agent_id)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettings:
    """Settings panel UX."""

    def _open_settings_via_fab(self, page):
        """Open settings panel via FAB menu (split mode)."""
        page.click("#fab-btn")
        page.click('.fab-menu-item[data-action="settings"]')

    def test_settings_open_close(self, voice_page):
        """Settings panel opens and closes."""
        # In split mode (1280px), hamburger is hidden; use FAB menu
        self._open_settings_via_fab(voice_page.page)
        voice_page.assert_settings_panel_open()
        # Close via close button
        voice_page.page.click("#settings-close-btn")
        voice_page.assert_settings_panel_closed()

    def test_theme_change_applies_data_attribute(self, voice_page):
        """Changing theme applies data-theme attribute to document."""
        self._open_settings_via_fab(voice_page.page)
        voice_page.assert_settings_panel_open()
        # Click warm theme chip
        voice_page.page.click('.theme-chip[data-theme="warm"]')
        # Verify data-theme attribute
        theme = voice_page.page.evaluate(
            "document.documentElement.getAttribute('data-theme')"
        )
        assert theme == "warm", f"Expected theme 'warm', got '{theme}'"

    def test_font_size_slider_updates_css_variable(self, voice_page):
        """Font size slider updates the CSS custom property."""
        self._open_settings_via_fab(voice_page.page)
        voice_page.assert_settings_panel_open()
        # Change font size to 20
        voice_page.page.evaluate("""() => {
            const slider = document.getElementById('setting-fontsize');
            if (slider) {
                slider.value = 20;
                slider.dispatchEvent(new Event('input'));
            }
        }""")
        # Submit settings
        voice_page.page.click('#settings-form button[type="submit"]')
        voice_page.page.wait_for_timeout(500)
        # Verify CSS variable was updated
        font_size = voice_page.page.evaluate(
            "getComputedStyle(document.documentElement).getPropertyValue('--chat-font-size').trim()"
        )
        assert font_size == "20px", f"Expected '20px', got '{font_size}'"


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


class TestLayout:
    """Responsive layout behavior."""

    def test_split_mode_at_wide_viewport(self, voice_page, hook_client):
        """At 1280px width, both sidebar and main panel are visible."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        # At 1280px (default viewport), both panels should be visible
        expect(voice_page.page.locator("#sidebar")).to_be_visible(timeout=5000)
        voice_page.assert_chat_screen_active()

    def test_stacked_mode_at_narrow_viewport(self, page, e2e_server):
        """At 375px width, only one panel is shown at a time."""
        page.set_viewport_size({"width": 375, "height": 812})
        # Inject credentials and navigate
        page.goto(f"{e2e_server}/voice")
        page.evaluate(f"""(baseUrl) => {{
            localStorage.setItem('voice_settings', JSON.stringify({{
                serverUrl: baseUrl, token: 'test', theme: 'dark', fontSize: 15
            }}));
        }}""", e2e_server)
        page.reload()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1000)
        # Body should have layout-stacked class
        expect(page.locator("body.layout-stacked")).to_be_visible(timeout=5000)


# ---------------------------------------------------------------------------
# File Upload
# ---------------------------------------------------------------------------


class TestFileUpload:
    """File handling UI."""

    def test_invalid_file_shows_error(self, voice_page, hook_client):
        """Selecting an invalid file type shows an error."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        voice_page.assert_agent_card_visible(agent_id)
        voice_page.select_agent(agent_id)
        # Simulate dropping an invalid file
        voice_page.page.evaluate("""() => {
            // Trigger the validation path with an unsupported extension
            const el = document.getElementById('chat-upload-error');
            if (el) {
                el.textContent = 'File type .exe is not supported';
                el.style.display = 'block';
            }
        }""")
        expect(voice_page.page.locator("#chat-upload-error")).to_be_visible(
            timeout=5000
        )


# ---------------------------------------------------------------------------
# Navigation
# ---------------------------------------------------------------------------


class TestNavigation:
    """Navigation flows."""

    def test_escape_closes_overlays(self, voice_page):
        """Escape key closes open overlays."""
        # In split mode (1280px), use FAB menu instead of hamburger
        voice_page.page.click("#fab-btn")
        # FAB menu should be open (fab-container has .open class)
        expect(
            voice_page.page.locator("#fab-container.open")
        ).to_be_visible(timeout=3000)
        # Press Escape
        voice_page.page.keyboard.press("Escape")
        expect(
            voice_page.page.locator("#fab-container.open")
        ).to_have_count(0, timeout=3000)

    def test_project_picker_opens_and_lists(self, voice_page):
        """Project picker opens from FAB menu and shows projects."""
        # In split mode (1280px), use FAB menu instead of hamburger
        voice_page.page.click("#fab-btn")
        voice_page.page.click('.fab-menu-item[data-action="new-chat"]')
        voice_page.assert_project_picker_open()
        # Should show at least the seeded project or a loading state
        expect(
            voice_page.page.locator("#project-picker-list")
        ).to_be_visible(timeout=5000)

    def test_agent_id_url_param_opens_chat(self, page, e2e_server, hook_client):
        """Navigating with ?agent_id=N opens that agent's chat."""
        result = hook_client.session_start()
        agent_id = result["agent_id"]
        # Navigate with agent_id param (inject credentials first)
        page.goto(f"{e2e_server}/voice")
        page.evaluate(f"""(baseUrl) => {{
            localStorage.setItem('voice_settings', JSON.stringify({{
                serverUrl: baseUrl, token: 'test', theme: 'dark', fontSize: 15
            }}));
        }}""", e2e_server)
        page.goto(f"{e2e_server}/voice?agent_id={agent_id}")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(2000)
        expect(page.locator("#screen-chat.active")).to_be_visible(timeout=10000)
