# Channel Messaging Remediation Spec

**Author:** Robbo (architect)
**Date:** 4 March 2026
**Status:** Draft — awaiting operator approval
**Context:** Post-implementation audit of Epic 9 channel messaging. Operator tested channels on the dashboard and found: (1) messages sent to a channel were not received by any agent members, (2) no agent responses came back, (3) the interaction surface was built in the dashboard instead of the Voice Chat PWA as specified.

---

## Problem Statement

The channel messaging system has all the plumbing but the wiring is broken. The data model, service layer, API endpoints, SSE events, and delivery service all exist. But an end-to-end message flow — operator sends message → agent receives it → agent responds → response appears in channel — does not work.

Additionally, the spec (Workshop Section 1, UI/UX Context) is explicit that the **Voice Chat PWA is the primary participation interface** for channels. The implementation inverted this: the dashboard got a full chat panel, and the voice PWA got a read-only sidebar showing channel names and last-message previews.

The voice bridge route already implements channel command handlers (send, history, list, create, add member, complete) with semantic matching and context memory. The voice PWA frontend does not use any of them.

---

## Remediation Items

### P0: Message Delivery Pipeline (Critical — channels don't work without this)

**Symptom:** Operator sends messages via dashboard chat panel. Agent members (Robbo, Paula) are IDLE with active channel memberships. No messages arrive in their tmux panes. No responses come back.

**Investigation required before implementation:**

1. **Verify delivery trigger fires.** When `ChannelService.send_message()` commits a message, does `ChannelDeliveryService.deliver_message()` actually get called? The service is a post-commit side effect — confirm it's registered and executing.

2. **Verify operator persona resolution.** When the operator sends a message from the dashboard, the API must resolve the caller to a person/internal Persona (the operator persona). If the caller identity is NULL or unresolved, `send_message()` may reject the message or `deliver_message()` may skip fan-out because there's no valid sender.

3. **Verify agent_id on channel memberships.** When agents "join" a channel (system messages confirm "Robbo joined the channel", "Paula joined the channel"), does the ChannelMembership record have a non-NULL `agent_id` pointing to the actual running agent? If `agent_id` is NULL, the delivery service has no tmux target. This is the most likely failure point — the membership was created with persona reference but the agent linkage was never established.

4. **Verify tmux pane availability.** The delivery service checks `CommanderAvailability` before sending via tmux. If the availability check returns false (pane not found, or tmux session name mismatch), delivery silently fails.

5. **Verify envelope injection.** If all the above pass, confirm that `tmux_bridge.send_text()` actually works for the target agent's pane. The envelope format is `[#channel-slug] PersonaName (operator):\n{content}` — confirm it arrives in the tmux pane.

**Fix scope:**
- Trace the actual code path for operator-sends-message-to-channel
- Fix whatever is broken in the chain (likely agent_id linkage or delivery trigger)
- Add integration test: operator sends message → message appears in agent's tmux pane
- Add integration test: agent completes response → response posted as channel message

**Acceptance criteria:**
- Operator sends a message in a channel via dashboard or voice → message appears in all active agent members' tmux panes within 2 seconds
- Agent produces a COMPLETION turn while in a channel → completion text posted back as a channel message and visible to all members via SSE

---

### P1: Voice PWA as Primary Channel Interface

**Symptom:** Voice PWA shows channel sidebar (names + previews) but cannot send messages, view history, create channels, or add members. The spec says it's the primary interface.

**What already exists (backend):**
- Voice bridge route has full channel intent detection: send, history, list, create, add member, complete
- Semantic fuzzy matching for channel names (exact, substring, token overlap)
- Channel context memory ("this channel" resolves to last-referenced channel)
- Voice-formatted response envelope (`status_line`, `results`, `next_action`)

**What needs to be built (voice PWA frontend):**

#### 1a. Channel Chat View

When the user taps a channel in the voice sidebar, open a channel chat view (not the agent chat — a dedicated channel conversation view). This is the primary interaction surface.

**Requirements:**
- Message feed showing channel history (fetch from `GET /api/channels/<slug>/messages`)
- Real-time SSE updates for new messages (already wired — `channel_message` events arrive)
- Text input at the bottom for sending messages (`POST /api/channels/<slug>/messages`)
- Messages colour-coded by sender: operator messages distinct from agent messages, system messages muted
- Relative timestamps with absolute on hover/tap
- Load earlier messages on scroll-up (cursor pagination via `?before=<ISO>`)
- Channel name, type badge, and member count in the header
- Back button to return to voice sidebar

#### 1b. Voice Commands for Channels

The voice bridge route already handles these. The voice PWA needs to:
- Send voice transcriptions through the existing voice command endpoint
- Handle channel-type responses (the voice bridge returns voice-formatted envelopes)
- Update the channel chat view when voice commands send messages or fetch history

Supported voice patterns (already implemented in backend):
- "Send to [channel]: [message]"
- "What's happening in [channel]?"
- "List channels" / "My channels"
- "Create a [type] channel called [name]"
- "Create a [type] channel called [name] with [members]"
- "Add [persona] to [channel]"
- "Complete [channel]" / "Finish [channel]"

#### 1c. Channel Management in Voice Sidebar

Extend the existing voice sidebar channel list:
- Show member avatars/initials alongside channel name
- Unread indicator (new messages since last view — can be approximate, based on SSE events received while not viewing that channel)
- "Create Channel" button at the top of the channel list section
- Simple create form: name, type dropdown, optional members (persona autocomplete)

**Acceptance criteria:**
- Operator can open a channel in the voice PWA and see full message history
- Operator can send a message from the voice PWA and see it appear in real-time
- Operator can use voice commands to send messages, read history, and manage channels
- New channel messages trigger a visual indicator in the sidebar when the channel isn't the active view

---

### P2: Dashboard Demoted to Secondary Management

**Symptom:** Dashboard currently has a full chat panel that was built as the primary interaction surface. This needs to remain functional but be repositioned as a management/monitoring view, not the primary place you go to participate in channel conversations.

**What stays:**
- Channel cards at the top of the dashboard (real-time status, member list, last message preview) — this is specified and correct
- Channel management modal (create, complete, archive) — this is specified and correct
- Chat panel remains functional — operator can still send/view messages from the dashboard when convenient

**What changes:**
- No functional changes needed. The dashboard chat panel works. The remediation is that the voice PWA gets built as the primary surface (P1 above). Once P1 is delivered, the dashboard chat naturally becomes the secondary "I'm already looking at the dashboard" convenience surface.

**The only dashboard work item:** If P0 investigation reveals the dashboard chat's send function has a bug in operator persona resolution, fix it there too. The same fix applies to both surfaces since they share the API.

---

## Sequencing

```
P0 (delivery pipeline)  ──→  P1a (voice chat view)  ──→  P1b (voice commands)
                                                      ──→  P1c (voice sidebar mgmt)
```

P0 must be done first. Without working delivery, building the voice chat view gives the operator a second broken chat window. P1a is the highest-value voice item — it's the primary interaction surface. P1b and P1c can run in parallel after P1a.

P2 requires no implementation work. It's a natural consequence of P1 being delivered.

---

## Out of Scope

- Per-recipient delivery tracking / read receipts (v2)
- Message threading within channels (v2)
- External persona support (v2)
- Channel-specific rate limiting (no evidence of need)
- Agent-to-agent direct messaging outside channels (different feature)

---

## Testing Requirements

### P0 Tests
- **Integration test:** Create channel with operator + agent members → operator sends message → verify message record in DB → verify delivery service was called → verify tmux pane received envelope
- **Integration test:** Agent in channel produces COMPLETION turn → verify relay_agent_response fires → verify new Message record → verify SSE broadcast
- **Negative test:** Agent in PROCESSING state receives channel message → verify message is queued, not delivered → agent transitions to IDLE → verify queued message delivered

### P1 Tests
- **E2E (Playwright):** Voice PWA → tap channel → verify chat view loads with messages → type and send message → verify message appears in feed → verify SSE update arrives
- **E2E (Playwright):** Voice PWA → channel sidebar → verify unread indicator appears when new message arrives for non-active channel
- **Voice command test:** Transcription "send to workshop channel hello" → verify voice bridge routes to correct channel → verify message posted

---

## Notes for Implementation Team

- The voice bridge backend is **done**. Channel command handlers, fuzzy matching, context memory — all implemented. The voice PWA frontend is where the work is.
- The delivery service is **structurally complete** but untested end-to-end with a real operator persona. The bug is likely in the wiring, not the logic.
- Do not build a separate channel SSE stream. The existing `/api/events/stream` with `channel_message` and `channel_update` type filtering is the correct pattern and is already working for both dashboard and voice PWA.
- The voice PWA is a standalone HTML app (`/voice`), not a Jinja template. It has its own JS modules. Do not import dashboard JS files into it.
