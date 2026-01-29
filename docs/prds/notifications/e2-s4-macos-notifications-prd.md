---
validation:
  status: valid
  validated_at: '2026-01-29T16:49:23+11:00'
---

## Product Requirements Document (PRD) — macOS Notifications

**Project:** Claude Headspace v3.1
**Scope:** Epic 2, Sprint 4 — Native macOS system notifications for agent state changes
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace monitors multiple Claude Code agents across projects, displaying their status on a web dashboard. However, users cannot watch the dashboard continuously while working on other tasks. When an agent completes a task or needs user input, the user may not notice, leading to idle agents and lost productivity.

This PRD defines the macOS Notifications subsystem, which sends native system notifications when agents reach important states. Notifications appear as standard macOS banners, integrate with the system notification center, and support click-to-navigate functionality that brings users directly to the relevant agent on the dashboard.

The notification system integrates with the existing hook receiver infrastructure from Epic 1, which provides instant, high-confidence state detection. Preferences are stored in `config.yaml` and editable via the dashboard settings panel, allowing users to control which events trigger notifications and whether sounds are enabled.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace's value proposition is keeping users informed about their agent fleet without constant manual checking. The Epic 1 dashboard provides a visual overview with real-time SSE updates, but this requires the user to have the dashboard visible. Users frequently work in other applications (IDE, browser, terminal) and miss important state changes.

The hook receiver from Epic 1 Sprint 13 reliably captures agent lifecycle events with 100% confidence and sub-100ms latency. This provides the foundation for proactive notifications that reach users regardless of which application has focus.

### 1.2 Target User

Power users managing 2-5 concurrent Claude Code agents across multiple projects. These users multitask between the dashboard, IDE, and other applications. They need to know immediately when an agent requires attention without manually checking the dashboard.

### 1.3 Success Moment

The user is working in VS Code when a macOS notification banner appears: "Agent ready for input - claude_headspace". They click the notification, their browser comes to focus with the dashboard open, and the relevant agent card is highlighted. They provide input and return to VS Code, confident they'll be notified when the agent completes.

---

## 2. Scope

### 2.1 In Scope

- macOS system notifications triggered by agent state changes
- Notification on `task_complete` event (agent finished processing)
- Notification on `awaiting_input` event (agent needs user response)
- Notification preferences stored in `config.yaml`
- Global enable/disable toggle for notifications
- Per-event-type toggles (task_complete, awaiting_input)
- Sound enable/disable preference
- Rate limiting to prevent notification spam (configurable cooldown per agent)
- Click-to-action: focus browser dashboard and highlight relevant agent
- Detection of terminal-notifier installation status
- Setup guidance when terminal-notifier is not installed
- Preferences API endpoints (GET/PUT `/api/notifications/preferences`)
- Preferences UI in settings panel

### 2.2 Out of Scope

- Native NSUserNotification API (using terminal-notifier for simplicity)
- Push notifications to mobile devices
- Slack/Discord/webhook integrations (future epic)
- Notifications for other events (session_start, session_end)
- Custom notification sounds (default macOS sound or silent only)
- Notification grouping or aggregation
- Do Not Disturb integration (respects macOS DND automatically via terminal-notifier)
- Click-to-focus iTerm directly (focus dashboard with highlight instead)
- Notification history or log in UI
- Windows or Linux notification support

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. When an agent's task completes, a macOS notification banner appears
2. When an agent enters `awaiting_input` state, a macOS notification appears
3. Clicking a notification opens the dashboard in the default browser with the agent highlighted
4. Users can toggle notifications on/off globally via the preferences UI
5. Users can toggle notifications per event type (task_complete, awaiting_input)
6. Users can toggle notification sounds on/off
7. Rate limiting prevents more than one notification per agent within the cooldown period
8. If terminal-notifier is not installed, the preferences UI shows installation instructions
9. Preferences persist across application restarts (stored in config.yaml)
10. Preferences are accessible via REST API

### 3.2 Non-Functional Success Criteria

1. **NFR1 - Latency:** Notifications appear within 500ms of the state change event
2. **NFR2 - Compatibility:** Works on macOS 12 (Monterey), 13 (Ventura), 14 (Sonoma), 15 (Sequoia)
3. **NFR3 - Graceful Degradation:** If terminal-notifier is unavailable, the system continues operating without notifications (no crashes or errors)
4. **NFR4 - Resource Usage:** Notification service adds negligible CPU/memory overhead

---

## 4. Functional Requirements (FRs)

**FR1: Task Complete Notification**
The system sends a macOS notification when an agent's task transitions to the `complete` state. The notification includes the agent name and project context.

**FR2: Awaiting Input Notification**
The system sends a macOS notification when an agent transitions to the `awaiting_input` state. The notification clearly indicates user action is required.

**FR3: Global Enable/Disable**
Users can enable or disable all notifications globally via a single toggle in preferences. When disabled, no notifications are sent regardless of per-event settings.

**FR4: Per-Event-Type Toggle**
Users can enable or disable notifications for specific event types independently:
- `task_complete`: enabled/disabled
- `awaiting_input`: enabled/disabled

**FR5: Sound Toggle**
Users can enable or disable notification sounds. When enabled, notifications use the default macOS notification sound. When disabled, notifications appear silently.

**FR6: Click-to-Navigate**
Clicking a notification opens the Claude Headspace dashboard in the user's default browser. The URL includes a query parameter that triggers the dashboard to scroll to and visually highlight the relevant agent card.

**FR7: Rate Limiting**
The system rate-limits notifications per agent to prevent spam during rapid state changes. The cooldown period is configurable (default: 5 seconds). During cooldown, state changes for that agent do not trigger notifications.

**FR8: Availability Detection**
The system detects whether notification capability is available (terminal-notifier installed) at startup and on-demand. The availability status is exposed via the preferences API.

**FR9: Setup Guidance**
When notification capability is unavailable, the preferences UI displays clear setup instructions including the installation command (`brew install terminal-notifier`).

**FR10: Preferences API**
The system provides REST API endpoints for notification preferences:
- `GET /api/notifications/preferences` - Retrieve current preferences and availability status
- `PUT /api/notifications/preferences` - Update notification preferences

**FR11: Preferences UI**
The dashboard settings panel includes a notifications section with:
- Global enable/disable toggle
- Per-event-type toggles
- Sound toggle
- Installation status indicator
- Setup instructions (when unavailable)

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Notification Latency**
Notifications must appear within 500ms of the triggering state change event. This ensures users perceive notifications as real-time.

**NFR2: macOS Compatibility**
The notification system must work on macOS versions 12 (Monterey) through 15 (Sequoia). terminal-notifier provides this compatibility.

**NFR3: Graceful Degradation**
If terminal-notifier is not installed or fails to execute, the system must:
- Continue operating without crashing
- Log a warning (not error) on first failure
- Not retry failed notifications repeatedly
- Indicate unavailability in the preferences UI

**NFR4: Resource Efficiency**
The notification service must not add significant resource overhead:
- No background polling for notification state
- Event-driven activation only
- Subprocess spawned only when sending notification

---

## 6. UI Overview

### 6.1 Preferences Panel - Notifications Section

The existing settings panel (from E2-S1 Config UI) includes a "Notifications" section:

```
Notifications
─────────────────────────────────────────
[Toggle] Enable notifications           [ON/OFF]

When enabled:
  [Toggle] Task complete                 [ON/OFF]
  [Toggle] Awaiting input                [ON/OFF]
  [Toggle] Play sound                    [ON/OFF]

Rate limit: [5] seconds per agent

─────────────────────────────────────────
Status: ✓ terminal-notifier installed
        Ready to send notifications
```

**When terminal-notifier is not installed:**

```
Notifications
─────────────────────────────────────────
⚠ Notifications unavailable

terminal-notifier is required for macOS notifications.

Install with Homebrew:
  brew install terminal-notifier

[Refresh Status]
─────────────────────────────────────────
```

### 6.2 Agent Card Highlight

When navigating from a notification click, the target agent card receives a temporary visual highlight:
- Brief animation or glow effect
- Card scrolled into view if not visible
- Highlight fades after 2-3 seconds

---

## 7. Technical Context (For Implementers)

This section provides implementation guidance but is not part of the requirements.

### 7.1 Recommended Approach

- **Notification tool:** `terminal-notifier` via Homebrew
- **Invocation:** Python `subprocess.run()` with timeout
- **Click action:** Open URL `http://localhost:5050/?highlight=<agent_id>`

### 7.2 Integration Points

- **Event source:** Hook receiver service (`src/services/hook_receiver.py`)
- **State transitions:** Subscribe to `process_stop()` and state changes to `awaiting_input`
- **Config:** Add `notifications` section to `config.yaml` defaults and loaders

### 7.3 Suggested Config Schema

```yaml
notifications:
  enabled: true
  sound: true
  events:
    task_complete: true
    awaiting_input: true
  rate_limit_seconds: 5
```

### 7.4 terminal-notifier Command

```bash
terminal-notifier \
  -title "Claude Headspace" \
  -subtitle "Agent: <agent_name>" \
  -message "<event description>" \
  -sound default \
  -open "http://localhost:5050/?highlight=<agent_id>"
```

---

## 8. Risks & Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| terminal-notifier not installed | Medium | Detection + setup guidance in UI |
| Notification spam during rapid changes | Medium | Rate limiting per agent |
| Click action fails to open browser | Low | URL scheme is standard; fallback to manual navigation |
| macOS notification permissions denied | Low | terminal-notifier handles permissions; system prompts user |

---

## 9. Dependencies

- **Epic 1 Complete:** Hook receiver, SSE system, dashboard, agent state machine
- **E2-S1 Config UI:** Settings panel for preferences UI integration
- **External:** terminal-notifier (Homebrew package)

---

## 10. Acceptance Tests

### Test 1: Task Complete Notification
1. Enable notifications in preferences
2. Start a Claude Code agent with hooks configured
3. Submit a prompt and wait for completion
4. **Expected:** macOS notification appears with task complete message

### Test 2: Awaiting Input Notification
1. Enable notifications in preferences
2. Start a Claude Code agent
3. Submit a prompt that causes agent to ask a question
4. **Expected:** macOS notification appears indicating input needed

### Test 3: Click-to-Navigate
1. Receive a notification
2. Click the notification banner
3. **Expected:** Browser opens dashboard, agent card is highlighted

### Test 4: Rate Limiting
1. Set rate limit to 5 seconds
2. Trigger multiple completions for same agent within 3 seconds
3. **Expected:** Only first notification appears; subsequent ones suppressed

### Test 5: Preferences Persistence
1. Disable `task_complete` notifications in UI
2. Restart the application
3. **Expected:** `task_complete` remains disabled after restart

### Test 6: Missing terminal-notifier
1. Ensure terminal-notifier is not installed
2. Open preferences panel
3. **Expected:** Setup instructions displayed with brew command

---

**End of PRD**
