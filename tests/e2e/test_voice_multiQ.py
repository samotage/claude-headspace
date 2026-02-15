#!/usr/bin/env python3
"""
Playwright E2E test: Multi-tab AskUserQuestion in Voice Chat

Tests that a multi-question AskUserQuestion tool call renders
correctly in the voice chat with tabbed sections and option buttons.

Usage: python tests/e2e/test_voice_multiQ.py
"""

import json
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

BASE_URL = "https://smac.griffin-blenny.ts.net:5055"
VOICE_URL = f"{BASE_URL}/voice"
PROJECT_NAME = "Claude Headspace"

# Timeouts (ms)
AGENT_APPEAR_TIMEOUT = 45_000
QUESTION_RENDER_TIMEOUT = 120_000
STEP_PAUSE = 1.5  # seconds

SCREENSHOTS = Path(__file__).parent / "screenshots"
SCREENSHOTS.mkdir(exist_ok=True)


class Colors:
    INFO = "\033[36m"
    WARN = "\033[33m"
    ERR = "\033[31m"
    OK = "\033[32m"
    DBG = "\033[90m"
    RESET = "\033[0m"


def log(level, msg):
    colors = {"info": Colors.INFO, "warn": Colors.WARN, "err": Colors.ERR, "ok": Colors.OK, "dbg": Colors.DBG}
    c = colors.get(level, "")
    tag = level.upper().center(4)
    print(f"{c}[{tag}]{Colors.RESET} {msg}", flush=True)


MUTATION_OBSERVER_JS = """
() => {
    const chatContainer = document.getElementById('chat-messages');
    if (!chatContainer) {
        console.log('[MQ-TRACE] WARNING: chat-messages container not found');
        return false;
    }
    const observer = new MutationObserver(mutations => {
        for (const m of mutations) {
            for (const node of m.addedNodes) {
                if (node.nodeType !== 1) continue;
                const mqEl = node.querySelector ? node.querySelector('.bubble-multi-question') : null;
                if (mqEl) {
                    const sections = mqEl.querySelectorAll('.bubble-question-section');
                    console.log(`[MQ-TRACE] Multi-question bubble rendered! Sections: ${sections.length}`);
                    sections.forEach((sec, i) => {
                        const header = sec.querySelector('.bubble-question-header');
                        const opts = sec.querySelectorAll('.bubble-option-btn');
                        console.log(`[MQ-TRACE]   Section ${i}: header="${header?.textContent}", options=${opts.length}`);
                    });
                }
                const sqEl = node.querySelector ? node.querySelector('.bubble-options') : null;
                if (sqEl && !mqEl) {
                    const opts = sqEl.querySelectorAll('.bubble-option-btn');
                    console.log(`[MQ-TRACE] Single-question bubble rendered! Options: ${opts.length}`);
                    opts.forEach((opt, i) => {
                        console.log(`[MQ-TRACE]   Opt ${i}: "${opt.textContent.trim().substring(0, 80)}"`);
                    });
                }
            }
        }
    });
    observer.observe(chatContainer, { childList: true, subtree: true });
    console.log('[MQ-TRACE] MutationObserver attached to chat-messages');
    return true;
}
"""

# Also instrument the SSE turn_created handler
SSE_INSTRUMENT_JS = """
() => {
    // Monkey-patch the SSE onmessage to log turn_created events
    if (window._mqTraceInstalled) return;
    window._mqTraceInstalled = true;

    // Intercept VoiceApp internals via the SSE event source
    // We'll watch for custom events on the document
    const origAddEventListener = EventSource.prototype.addEventListener;
    EventSource.prototype.addEventListener = function(type, handler, ...rest) {
        if (type === 'message') {
            const wrappedHandler = function(event) {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'turn_created' || data.type === 'card_refresh') {
                        console.log(`[SSE] ${data.type}: intent=${data.intent || 'n/a'}, hasToolInput=${!!data.tool_input}, hasQuestions=${!!(data.tool_input && data.tool_input.questions)}`);
                        if (data.tool_input && data.tool_input.questions) {
                            console.log(`[SSE] questions count: ${data.tool_input.questions.length}`);
                            data.tool_input.questions.forEach((q, i) => {
                                console.log(`[SSE]   Q${i}: header="${q.header}", question="${(q.question || '').substring(0, 60)}", opts=${(q.options || []).length}`);
                            });
                        }
                    }
                } catch(e) {}
                return handler.call(this, event);
            };
            return origAddEventListener.call(this, type, wrappedHandler, ...rest);
        }
        return origAddEventListener.call(this, type, handler, ...rest);
    };
    console.log('[MQ-TRACE] SSE instrumentation installed');
}
"""


PROMPT = """I want to perform a Tmux AskUserQuestion tool response test, To test the interaction of the voice chat with the agent using the systems send keys algorithms.

I want you to figure out what the current system time is on the computer.

Before responding I want you to use the Ask User Question tool with a two tab panel that:
First panel: to ask me what format I would like the time in
Second panel: to ask me how you should describe the time of the day

Then When you have the answer, I want you to print out to the terminal the responses I've chosen.

Wait one second.

and then output the time in the selected format with the chosen descriptive format"""


def run_test(attempt: int = 1):
    log("info", f"{'='*60}")
    log("info", f"  ATTEMPT {attempt}: Multi-Question Voice Chat Test")
    log("info", f"{'='*60}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            ignore_https_errors=True,
            viewport={"width": 430, "height": 932},
        )
        page = context.new_page()

        # Capture console logs
        console_messages = []
        def on_console(msg):
            text = msg.text
            console_messages.append(text)
            if any(text.startswith(pf) for pf in ("[MQ-TRACE]", "[SSE]", "[VOICE]")):
                log("dbg", f"BROWSER: {text}")

        page.on("console", on_console)
        page.on("pageerror", lambda err: log("err", f"PAGE ERROR: {err.message}"))

        try:
            return _execute_test(page, attempt, console_messages)
        except Exception as e:
            log("err", f"Test failed with exception: {e}")
            page.screenshot(path=str(SCREENSHOTS / f"mq_attempt{attempt}_exception.png"))
            return False, str(e)
        finally:
            browser.close()


def _execute_test(page, attempt, console_messages):
    prefix = f"mq_a{attempt}"

    # ──── Step 1: Navigate to voice chat ────
    log("info", f"Navigating to {VOICE_URL}...")
    page.goto(VOICE_URL, wait_until="domcontentloaded", timeout=30_000)

    # Install SSE instrumentation BEFORE anything else
    page.evaluate(SSE_INSTRUMENT_JS)

    time.sleep(STEP_PAUSE)
    page.screenshot(path=str(SCREENSHOTS / f"{prefix}_01_loaded.png"))
    log("ok", "Voice chat loaded")

    # ──── Step 2: Install mutation observer ────
    log("info", "Installing instrumentation...")
    result = page.evaluate(MUTATION_OBSERVER_JS)
    log("info", f"MutationObserver installed: {result}")

    # ──── Step 3: Create new agent ────
    log("info", f'Creating new agent for project "{PROJECT_NAME}"...')
    time.sleep(STEP_PAUSE)

    # In stacked/mobile mode, look for hamburger menu
    agent_created = False

    # Try hamburger -> New Chat
    hamburger = page.locator("#hamburger-btn")
    if hamburger.is_visible(timeout=3000):
        log("info", "Found hamburger menu (stacked mode)")
        hamburger.click()
        time.sleep(0.5)
        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_02a_hamburger_open.png"))

        new_chat = page.locator('.hamburger-item[data-action="new-chat"]')
        if new_chat.is_visible(timeout=3000):
            new_chat.click()
            log("ok", 'Clicked "New Chat"')
            time.sleep(STEP_PAUSE)
            agent_created = True

    # Try FAB button
    if not agent_created:
        fab = page.locator("#fab-btn")
        if fab.is_visible(timeout=3000):
            log("info", "Found FAB button")
            fab.click()
            time.sleep(STEP_PAUSE)
            agent_created = True

    if not agent_created:
        log("warn", "No hamburger or FAB found, trying API fallback...")

    page.screenshot(path=str(SCREENSHOTS / f"{prefix}_02_after_new_chat.png"))

    # ──── Step 4: Select project from picker ────
    log("info", f'Looking for project "{PROJECT_NAME}" in picker...')

    # Wait for project picker to appear
    picker = page.locator("#project-picker.open, .project-picker.open")
    try:
        picker.wait_for(state="visible", timeout=5000)
        log("ok", "Project picker is open")
    except Exception:
        log("warn", "Project picker did not open, taking screenshot...")

    time.sleep(1)
    page.screenshot(path=str(SCREENSHOTS / f"{prefix}_03_picker.png"))

    # Use data-project-name attribute (set on .project-picker-row elements)
    project_found = False
    row = page.locator(f'.project-picker-row[data-project-name="{PROJECT_NAME}"]').first
    try:
        if row.is_visible(timeout=3000):
            row.click()
            log("ok", f'Selected project via data-project-name="{PROJECT_NAME}"')
            project_found = True
    except Exception:
        pass

    if not project_found:
        # Fallback: try text-based match
        log("warn", "Exact attribute match failed, trying text search...")
        try:
            text_el = page.locator(".project-picker-row").filter(has_text=PROJECT_NAME).first
            if text_el.is_visible(timeout=3000):
                text_el.click()
                log("ok", "Selected project via text filter")
                project_found = True
        except Exception:
            pass

    if not project_found:
        # Close the picker first if it's blocking
        log("warn", "Closing project picker and using direct API...")
        try:
            backdrop = page.locator("#project-picker-backdrop")
            if backdrop.is_visible(timeout=1000):
                backdrop.click()
                time.sleep(0.5)
        except Exception:
            pass

        resp = page.evaluate("""
            async (pName) => {
                const r = await fetch('/api/voice/agents/create', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ project_name: pName })
                });
                return { status: r.status, body: await r.json() };
            }
        """, PROJECT_NAME)
        log("info", f"API create response: {json.dumps(resp, indent=2)}")

    # Ensure project picker is closed before proceeding
    try:
        backdrop = page.locator("#project-picker-backdrop.open")
        if backdrop.is_visible(timeout=1000):
            backdrop.click()
            time.sleep(0.5)
            log("info", "Closed project picker backdrop")
    except Exception:
        pass

    time.sleep(STEP_PAUSE)
    page.screenshot(path=str(SCREENSHOTS / f"{prefix}_04_agent_starting.png"))

    # ──── Step 5: Wait for agent to appear ────
    # In stacked/mobile mode, after project selection the app auto-selects the
    # new agent and switches to chat view. So we wait for the chat input to appear
    # rather than looking for agent cards in the (now hidden) sidebar.
    log("info", "Waiting for agent to boot and chat view to activate...")

    chat_ready = False
    try:
        # Wait for the chat input to become visible (means agent was auto-selected)
        page.locator("#chat-text-input").wait_for(state="visible", timeout=AGENT_APPEAR_TIMEOUT)
        chat_ready = True
        log("ok", "Chat view is active (agent was auto-selected)")
    except Exception:
        log("warn", "Chat input not visible after timeout")

    if not chat_ready:
        # Check current screen state
        screen_state = page.evaluate("""
            () => {
                const active = document.querySelector('.screen.active');
                return {
                    activeScreen: active ? active.id : 'none',
                    hasChatInput: !!document.getElementById('chat-input'),
                    agentCards: document.querySelectorAll('.agent-card').length,
                    pendingCards: document.querySelectorAll('.agent-card-pending').length,
                };
            }
        """)
        log("dbg", f"Screen state: {json.dumps(screen_state)}")
        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_05_screen_debug.png"))

        # Try to find and click an agent card (may need to navigate to agents view)
        agent_card = page.locator(".agent-card:not(.agent-card-pending)").last
        if agent_card.is_visible(timeout=5000):
            agent_card.click()
            time.sleep(1)
            log("ok", "Clicked agent card")
        else:
            log("err", "Cannot find chat input or visible agent cards")
            return False, "Agent did not boot or UI did not navigate to chat"

    page.screenshot(path=str(SCREENSHOTS / f"{prefix}_05_agent_selected.png"))

    # Re-install mutation observer for the chat view
    page.evaluate(MUTATION_OBSERVER_JS)

    # ──── Step 6: Enter the prompt ────
    log("info", "Entering prompt into chat input...")

    # Wait for chat input to be ready
    chat_input = page.locator("#chat-text-input").first
    try:
        chat_input.wait_for(state="visible", timeout=10_000)
    except Exception:
        # Maybe the chat view isn't showing - need to navigate to it
        log("warn", "Chat input not visible, checking screen state...")
        screen_state = page.evaluate("document.querySelector('.screen.active')?.id || 'unknown'")
        log("dbg", f"Active screen: {screen_state}")
        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_06_no_chat_input.png"))

        # Try clicking the agent card again to enter chat mode
        page.locator(".agent-card").last.click()
        time.sleep(1)
        chat_input = page.locator("#chat-text-input").first
        chat_input.wait_for(state="visible", timeout=10_000)

    chat_input.fill(PROMPT)
    time.sleep(0.5)

    # Send the prompt
    send_btn = page.locator("#chat-send-btn")
    if send_btn.is_visible(timeout=2000):
        send_btn.click()
        log("ok", "Sent prompt via send button")
    else:
        chat_input.press("Enter")
        log("ok", "Sent prompt via Enter key")

    time.sleep(1)
    page.screenshot(path=str(SCREENSHOTS / f"{prefix}_06_prompt_sent.png"))

    # ──── Step 7: Wait for the question bubble ────
    log("info", f"Waiting up to {QUESTION_RENDER_TIMEOUT // 1000}s for question bubble...")

    multi_q_sel = ".bubble-multi-question"
    single_q_sel = ".bubble-options"

    try:
        page.locator(f"{multi_q_sel}, {single_q_sel}").first.wait_for(
            state="visible", timeout=QUESTION_RENDER_TIMEOUT
        )
    except Exception as e:
        log("err", f"Timeout waiting for question: {e}")
        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_07_timeout.png"))

        # Diagnostic dump
        chat_state = page.evaluate("""
            () => {
                const container = document.getElementById('chat-messages');
                if (!container) return 'no container';
                const bubbles = container.querySelectorAll('.chat-bubble');
                return Array.from(bubbles).map(b => ({
                    turnId: b.getAttribute('data-turn-id'),
                    classes: b.className,
                    text: b.textContent.substring(0, 200),
                    hasMultiQ: !!b.querySelector('.bubble-multi-question'),
                    hasSingleQ: !!b.querySelector('.bubble-options'),
                    hasAnyBtn: !!b.querySelector('.bubble-option-btn'),
                }));
            }
        """)
        log("err", f"Chat state: {json.dumps(chat_state, indent=2)}")

        # Also dump relevant console messages
        mq_logs = [m for m in console_messages if "[MQ-TRACE]" in m or "[SSE]" in m]
        log("err", f"Trace logs ({len(mq_logs)}): {json.dumps(mq_logs, indent=2)}")

        return False, "Timeout waiting for question bubble"

    # ──── Step 8: Analyze what rendered ────
    is_multi = page.locator(multi_q_sel).is_visible()
    is_single = page.locator(single_q_sel).is_visible()

    page.screenshot(path=str(SCREENSHOTS / f"{prefix}_07_question_visible.png"))

    if is_multi:
        log("ok", "*** MULTI-QUESTION BUBBLE RENDERED! ***")

        section_count = page.locator(".bubble-question-section").count()
        log("info", f"Found {section_count} question sections")

        for i in range(section_count):
            sec = page.locator(".bubble-question-section").nth(i)
            header = sec.locator(".bubble-question-header").text_content()
            opt_count = sec.locator(".bubble-option-btn").count()
            log("info", f'  Section {i}: "{header}" — {opt_count} options')

        # ──── Step 9: Select options ────
        log("info", "Selecting first option in each section...")

        for i in range(section_count):
            sec = page.locator(".bubble-question-section").nth(i)
            first_opt = sec.locator(".bubble-option-btn").first
            first_opt.click()
            label = first_opt.text_content().strip()[:60]
            log("ok", f'  Selected "{label}" in section {i}')
            time.sleep(0.3)

        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_08_options_selected.png"))

        # ──── Step 10: Submit ────
        submit_btn = page.locator(".bubble-multi-submit")
        is_enabled = submit_btn.is_enabled()
        log("info", f"Submit All enabled: {is_enabled}")

        if is_enabled:
            submit_btn.click()
            log("ok", 'Clicked "Submit All"')
        else:
            log("err", "Submit All is disabled!")
            return False, "Submit All button disabled"

        time.sleep(2)
        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_09_submitted.png"))

        # ──── Step 11: Wait for agent response ────
        log("info", "Waiting 30s for agent to respond with the time...")
        time.sleep(30)
        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_10_final.png"))

        log("ok", "=== TEST PASSED ===")
        return True, "Multi-question rendered and submitted successfully"

    elif is_single:
        log("err", "*** SINGLE-QUESTION BUBBLE RENDERED (NOT MULTI!) ***")

        # Dump diagnostic info
        diag = page.evaluate("""
            () => {
                const bubble = document.querySelector('.bubble-options');
                if (!bubble) return { error: 'no bubble' };
                const parent = bubble.closest('.chat-bubble');
                const opts = bubble.querySelectorAll('.bubble-option-btn');
                return {
                    turnId: parent?.getAttribute('data-turn-id'),
                    optionCount: opts.length,
                    optionLabels: Array.from(opts).map(o => o.textContent.trim().substring(0, 80)),
                    parentClasses: parent?.className,
                    bubbleInnerHTML: bubble.innerHTML.substring(0, 1000),
                };
            }
        """)
        log("err", f"Diagnostic: {json.dumps(diag, indent=2)}")

        # Also dump SSE trace logs
        mq_logs = [m for m in console_messages if "[MQ-TRACE]" in m or "[SSE]" in m]
        log("err", f"Trace logs ({len(mq_logs)}):")
        for m in mq_logs:
            log("dbg", f"  {m}")

        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_07_FAIL_single_q.png"))
        return False, "Single-question rendered instead of multi-question"

    else:
        log("err", "Question appeared but neither multi nor single selector matched")
        page.screenshot(path=str(SCREENSHOTS / f"{prefix}_07_FAIL_unknown.png"))
        return False, "Unknown question format"


def main():
    max_attempts = 3
    for attempt in range(1, max_attempts + 1):
        success, detail = run_test(attempt)
        log("info", f"Attempt {attempt} result: {'PASS' if success else 'FAIL'} — {detail}")

        if success:
            log("ok", f"Test passed on attempt {attempt}!")
            return 0

        if attempt < max_attempts:
            log("warn", f"Retrying in 5 seconds (attempt {attempt + 1}/{max_attempts})...")
            time.sleep(5)

    log("err", f"All {max_attempts} attempts failed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
