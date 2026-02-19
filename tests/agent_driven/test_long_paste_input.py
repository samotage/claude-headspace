"""Agent-driven integration test: long text paste via Ctrl+V.

Verifies that pasting a large block of text into the voice chat message
box via Ctrl+V, then pressing Enter (or clicking send), results in the
command being delivered to the agent and executed.  This exercises:

- Browser clipboard paste into the textarea
- Voice bridge handling of long text
- tmux send_text with verify_enter=True for large payloads
- No command backflush (duplicate user bubble)

Every layer is real. Nothing is mocked.
"""

import sys
import time
from pathlib import Path

import pytest
from playwright.sync_api import expect

from tests.e2e.helpers.voice_assertions import VoiceAssertions

SCREENSHOT_DIR = Path(__file__).parent / "screenshots"
RESPONSE_TIMEOUT = 90_000  # ms — extra generous for long text processing

# The blog post to paste — realistic long-form content
BLOG_POST = """\
Summarise this blog post:

---

Building With AI Agents: Why the Filesystem Is the Interface
AI agents work best when you meet them where they already are — the filesystem. \
Here's why otageLabs chose markdown files over a CMS, and what it means for how we build and publish.

Sam Sabey
|
ai
engineering
workflow
There's a moment in every project where you choose between the tool that looks right \
and the tool that works right. For content publishing, that choice usually lands on a \
CMS — something with an admin panel, a database, a WYSIWYG editor. The whole stack.

We went a different direction.

The problem with traditional publishing
A CMS adds operational overhead that scales with complexity, not with value. You get \
database migrations, admin authentication, content tables, editor maintenance. Every \
layer is another thing that can break, another thing that needs updating, another thing \
between you and the words on the page.

For a solo engineering practice, that overhead isn't justified. But there's a deeper \
issue: AI agents can't use admin panels.

Meeting agents where they are
Claude Code — the AI agent I use daily — is exceptional at working with files. It reads \
them, writes them, understands their structure. Ask it to create a blog post, and it can \
write a markdown file with valid frontmatter in seconds. No API integration. No browser \
automation. No authentication flow.

The filesystem is the interface.

content/blog/2026-02-10-building-with-ai-agents.md
That's it. One file. Frontmatter for metadata, markdown for content. Commit and deploy. \
The post is live.

What this looks like in practice
Every blog post is a markdown file in content/blog/. The naming convention — \
YYYY-MM-DD-slug.md — gives you chronological ordering for free. The frontmatter handles \
everything else:

title — what appears on the page
slug — the URL path
date — when it was published
tags — for categorisation
summary — for the index page and SEO
published — the on/off switch
Set published: true, push to main, and the build system does the rest. Static generation \
means zero runtime overhead. No database queries. No API calls. Just HTML.

The builder's choice
This isn't the sophisticated choice. It's the practical one. The same principle that \
drives every decision at otageLabs: build what works, not what impresses.

A markdown file in a git repository is version-controlled, diffable, portable, and works \
with every tool in the development chain. It's the kind of unsexy infrastructure that \
quietly makes everything else easier.

The best tool is the one that disappears into the workflow.

That's what we're building here. Not a publishing platform. A publishing workflow — one \
that humans and AI agents share equally."""


@pytest.mark.agent_driven
def test_long_paste_ctrl_v(claude_session, page, e2e_server, e2e_app):
    """Paste a long blog post via Ctrl+V and verify the agent processes it.

    This test reproduces a real-world failure mode where:
    1. User pastes long text into the voice chat message box
    2. The text arrives in the tmux terminal
    3. But Enter is never pressed — the command sits in the input

    The fix (verify_enter=True) ensures Enter is retried if autocomplete
    or other input handling swallows the first keystroke.

    Flow:
    1. Write blog post to browser clipboard
    2. Focus textarea, press Meta+V (macOS) to paste
    3. Verify text appears in textarea
    4. Press Enter to submit
    5. Wait for agent response
    6. Verify agent summarised the blog post
    7. Verify no command backflush (exactly 1 user bubble)
    """
    agent_id = claude_session["agent_id"]

    # --- Setup voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("paste_01_chat_ready")

    # --- Write text to clipboard ---
    page.evaluate("text => navigator.clipboard.writeText(text)", BLOG_POST)

    # --- Focus textarea and paste via keyboard shortcut ---
    textarea = page.locator("#chat-text-input")
    textarea.focus()

    # Use Meta+v on macOS, Control+v on Linux/Windows
    paste_key = "Meta+v" if sys.platform == "darwin" else "Control+v"
    page.keyboard.press(paste_key)

    # Verify text appeared in the textarea
    expect(textarea).not_to_be_empty(timeout=3_000)
    pasted_value = textarea.input_value()
    assert "filesystem" in pasted_value.lower(), (
        f"Paste failed — expected blog post text in textarea, got: {pasted_value[:100]!r}"
    )
    va.capture("paste_02_text_pasted")

    # --- Submit via Enter key ---
    page.keyboard.press("Enter")
    va.capture("paste_03_enter_pressed")

    # --- Verify optimistic user bubble rendered ---
    user_bubbles = page.locator(".chat-bubble.user")
    expect(user_bubbles.first).to_be_visible(timeout=5_000)
    va.capture("paste_04_user_bubble_visible")

    # --- Wait for agent response ---
    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("paste_05_response_visible")

    # --- Verify the response is a summary (not an error) ---
    response_text = agent_bubbles.first.inner_text().lower()
    # The agent should reference concepts from the blog post
    assert any(keyword in response_text for keyword in [
        "filesystem", "markdown", "cms", "blog", "agent", "publish",
        "otagelabs", "frontmatter", "infrastructure",
    ]), (
        f"Agent response doesn't appear to summarise the blog post: "
        f"{response_text[:200]!r}"
    )
    va.capture("paste_06_response_verified")

    # --- Backflush check: wait for delayed SSE events ---
    time.sleep(5)
    va.capture("paste_07_after_settle")

    # Exactly 1 user bubble — no backflush
    user_count = user_bubbles.count()
    assert user_count == 1, (
        f"BACKFLUSH DETECTED: Expected 1 user bubble, got {user_count}. "
        f"Texts: {[user_bubbles.nth(i).inner_text()[:80] for i in range(user_count)]}"
    )

    va.capture("paste_08_complete")


@pytest.mark.agent_driven
def test_long_paste_send_button(claude_session, page, e2e_server, e2e_app):
    """Paste via Ctrl+V and submit via Send button (not Enter).

    Same as test_long_paste_ctrl_v but uses the Send button instead of
    Enter key, verifying both submission paths work with long pasted text.

    Flow:
    1. Write blog post to clipboard
    2. Focus textarea, paste via Ctrl+V
    3. Click the Send button
    4. Wait for agent response
    5. Verify no backflush
    """
    agent_id = claude_session["agent_id"]

    # --- Setup voice chat ---
    va = VoiceAssertions(page, SCREENSHOT_DIR)
    va.navigate_to_voice(e2e_server)
    va.assert_agent_card_visible(agent_id, timeout=15_000)
    va.select_agent(agent_id)
    va.assert_chat_screen_active()
    va.capture("sendbtn_01_chat_ready")

    # --- Paste via clipboard ---
    page.evaluate("text => navigator.clipboard.writeText(text)", BLOG_POST)
    textarea = page.locator("#chat-text-input")
    textarea.focus()

    paste_key = "Meta+v" if sys.platform == "darwin" else "Control+v"
    page.keyboard.press(paste_key)

    expect(textarea).not_to_be_empty(timeout=3_000)
    va.capture("sendbtn_02_text_pasted")

    # --- Submit via Send button ---
    page.click("#chat-send-btn")
    va.capture("sendbtn_03_send_clicked")

    # --- Verify optimistic user bubble ---
    user_bubbles = page.locator(".chat-bubble.user")
    expect(user_bubbles.first).to_be_visible(timeout=5_000)

    # --- Wait for agent response ---
    agent_bubbles = page.locator(".chat-bubble.agent[data-turn-id]")
    expect(agent_bubbles.first).to_be_visible(timeout=RESPONSE_TIMEOUT)
    va.capture("sendbtn_04_response_visible")

    # --- Verify the response is about the blog post ---
    response_text = agent_bubbles.first.inner_text().lower()
    assert any(keyword in response_text for keyword in [
        "filesystem", "markdown", "cms", "blog", "agent", "publish",
        "otagelabs", "frontmatter", "infrastructure",
    ]), (
        f"Agent response doesn't appear to summarise the blog post: "
        f"{response_text[:200]!r}"
    )

    # --- Backflush check ---
    time.sleep(5)
    va.capture("sendbtn_05_after_settle")

    user_count = user_bubbles.count()
    assert user_count == 1, (
        f"BACKFLUSH DETECTED: Expected 1 user bubble, got {user_count}. "
        f"Texts: {[user_bubbles.nth(i).inner_text()[:80] for i in range(user_count)]}"
    )

    va.capture("sendbtn_06_complete")
