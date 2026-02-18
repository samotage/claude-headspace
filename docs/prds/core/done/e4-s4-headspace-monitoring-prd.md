---
validation:
  status: valid
  validated_at: '2026-02-02T18:05:03+11:00'
---

## Product Requirements Document (PRD) — Headspace Monitoring

**Project:** Claude Headspace v3.1
**Scope:** E4-S4 — Frustration tracking, flow state detection, traffic light indicator, gentle wellness alerts
**Author:** PM Agent (John) / PRD Workshop
**Status:** Draft
**Epic:** 4 — Data Management & Wellness
**Sprint:** 4

---

## Executive Summary

Claude Headspace monitors AI agents — but the most important variable in any coding session is the human. When frustration builds silently during long sessions with Claude Code, it degrades effectiveness without the developer being consciously aware. Headspace Monitoring addresses this by extracting a frustration score from each user turn (piggybacking on the existing turn summarisation LLM call), calculating rolling averages, and presenting a traffic light indicator at the top of the dashboard.

When frustration is sustained or spikes, the system displays gentle, playful alerts — body-focused messages like "Think of your cortisol" — that reframe frustration as a physiological signal rather than a personal failing. The alerts are dismissable, with an "I'm fine" button that suppresses them for one hour.

On the positive side, the system detects flow state — periods of high turn throughput with low frustration — and provides encouraging reinforcement messages. This transforms Claude Headspace from a developer productivity tool into a developer wellness tool, recognizing that self-awareness is the first step to sustainable work with AI agents.

---

## 1. Context & Purpose

### 1.1 Context

The turn summarisation infrastructure (E3-S2) already calls the LLM for every user turn to generate a concise summary. Adding frustration score extraction to this same call is nearly free — same prompt, same inference call, extended output. The activity metrics infrastructure provides turn rate data that can inform flow state detection.

The existing dashboard header and SSE broadcasting system provide natural integration points for a traffic light indicator and real-time alert delivery.

### 1.2 Target User

The sole user of Claude Headspace: the developer managing multiple Claude Code sessions across projects. This person works long hours with AI agents and may not notice when frustration is affecting their decision-making and communication quality.

### 1.3 Success Moment

The user has been debugging a stubborn issue for 20 minutes. Their messages are getting terse, they've repeated the same request three times. The traffic light shifts from green to yellow, then to red. A gentle banner appears: "Your future self called. They said chill." The user laughs, takes a breath, grabs water, and comes back with a clearer prompt that solves the problem in one turn.

Alternatively: the user has been in productive flow for 45 minutes — low frustration, steady turn rate. A quiet message appears: "You've been in the zone for 45 minutes. Nice!" They smile and keep going.

---

## 2. Scope

### 2.1 In Scope

- Frustration score extraction from user turns (0-10 scale) via enhanced turn summarisation prompt
- Frustration score persisted on the Turn model (user turns only; agent turns get null)
- Rolling frustration calculations: last 10 user turns average, last 30 minutes average
- Traffic light indicator at top of dashboard (green/yellow/red) with progressive prominence
- Threshold detection for alerts: absolute spike, sustained yellow, sustained red, rising trend, time-based
- Gentle playful alert system: dismissable banner with randomized body-focused messages
- "I'm fine" button that suppresses alerts for 1 hour
- Alert cooldown (configurable, default 10 minutes between alerts)
- Flow state detection based on turn rate and frustration thresholds
- Positive reinforcement messages for sustained flow state (periodic, every 15 minutes)
- HeadspaceSnapshot model for persisting headspace state over time
- HeadspaceMonitor service: orchestrates calculation, detection, alerting, and snapshot creation
- API endpoints: GET `/api/headspace/current`, GET `/api/headspace/history`
- SSE events for real-time traffic light updates and alert delivery
- Database migration for Turn.frustration_score column and HeadspaceSnapshot table
- Configuration in config.yaml: enable/disable, thresholds, cooldown, flow detection params, messages
- Snapshot retention policy (configurable, default 7 days)

### 2.2 Out of Scope

- Per-project frustration tracking (this is a global indicator across all active sessions)
- Machine learning or custom sentiment model training (uses existing LLM infrastructure)
- macOS system notifications for frustration alerts (dashboard-only for this sprint)
- Historical trend visualization or charting UI (API provides data; visualization deferred)
- Agent turn frustration scoring (only user turns are analysed)
- UI for authoring custom alert messages (configured via config.yaml)
- Audio or sound-based alerts
- Integration with external wellness tools or APIs

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. User turns have a frustration score (0-10) extracted and stored, within the same latency as current turn summarisation
2. Traffic light indicator is visible at the top of the dashboard, reflecting current frustration state
3. Traffic light is subtle when green (calm), visible when yellow (moderate frustration), and prominent when red (high frustration)
4. A gentle alert banner appears when frustration thresholds are breached (sustained yellow, sustained red, absolute spike, rising trend, time-based)
5. Alert messages are playful and body-focused — never preachy, judgmental, or dismissive
6. Alerts are dismissable; an "I'm fine" button suppresses alerts for 1 hour
7. Alerts re-trigger if frustration continues after cooldown expires and suppression period ends
8. Flow state is detected when turn rate is high and frustration is low for a sustained period
9. A positive reinforcement message appears periodically during sustained flow state
10. Headspace monitoring can be enabled or disabled via config.yaml
11. Thresholds for yellow/red states are configurable
12. GET `/api/headspace/current` returns current frustration level, traffic light state, flow state status, and alert status
13. GET `/api/headspace/history` returns time-series of headspace snapshots within a configurable retention window

### 3.2 Non-Functional Success Criteria

1. Frustration extraction must not add perceptible latency to turn summarisation (same LLM call, JSON output parsed server-side)
2. If frustration extraction fails (malformed LLM response), the turn summary must still be saved normally with null frustration_score — graceful degradation
3. Headspace calculations must not block the main request/response cycle (async or deferred computation)
4. Traffic light indicator must update in real-time via SSE (no page refresh required)
5. Alert cooldown and suppression state must be maintained server-side (not lost on page refresh)

---

## 4. Functional Requirements (FRs)

### Frustration Score Extraction

**FR1:** The system must extract a frustration score (integer, 0-10) from each user turn by enhancing the existing turn summarisation prompt to return both a summary and a frustration score.

**FR2:** The frustration score must be stored on the Turn model as a nullable integer field. Only user turns (actor=USER) receive a frustration score; agent turns have null.

**FR3:** The enhanced prompt must instruct the LLM to analyse the user's emotional state based on: tone and language intensity, punctuation patterns (!!!, ???, CAPS), repetition of previous requests, explicit frustration signals ("again", "still not working"), and patience indicators (clear instructions, positive framing).

**FR4:** The frustration scale must be interpreted as: 0-3 calm/patient/constructive, 4-6 showing some frustration, 7-10 clearly frustrated.

**FR5:** If the LLM response cannot be parsed as the expected format, the system must fall back to treating the response as a plain text summary with null frustration_score. Existing turn summarisation functionality must not be disrupted.

### Rolling Frustration Calculation

**FR6:** The system must calculate a rolling average frustration score over the last 10 user turns (across all active projects/agents). If fewer than 10 scored user turns exist, the average must be calculated over whatever scored turns are available (minimum 1).

**FR7:** The system must calculate a rolling average frustration score over the last 30 minutes of user turns. If no scored user turns exist in the last 30 minutes, the 30-minute rolling average must be reported as null (not zero).

**FR8:** Rolling calculations must be triggered after each new user turn is processed with a frustration score.

### Traffic Light Indicator

**FR9:** The dashboard must display a traffic light indicator at the top of the page that reflects the current frustration state: green (0-3), yellow (4-6), or red (7-10). When no frustration data exists yet (no scored user turns), the indicator must default to green with minimal prominence (same as calm state).

**FR10:** The traffic light state must be determined by the higher of the two rolling averages (10-turn and 30-minute). If one average is null (e.g., no turns in the last 30 minutes), the state must be determined by the non-null average alone.

**FR11:** The indicator must be subtle when green (small dot or minimal element), visually prominent when yellow, and highly prominent when red (larger element, attention-drawing styling).

**FR12:** The traffic light must update in real-time via SSE events when the state changes.

### Threshold Detection & Alerts

**FR13:** The system must detect the following alert trigger conditions:

| Trigger | Condition | Action |
|---------|-----------|--------|
| Absolute spike | Single user turn frustration score >= 8 | Immediate alert |
| Sustained yellow | Rolling average >= 5 for 5+ minutes | Alert |
| Sustained red | Rolling average >= 7 for 2+ minutes | Alert |
| Rising trend | Frustration increased by +3 points over last 5 user turns | Alert |
| Time-based | Rolling average >= 4 for 30+ minutes | Alert |

**FR14:** When an alert triggers, the system must display a dismissable banner on the dashboard with a randomly selected gentle alert message.

**FR15:** The default set of gentle alert messages must include at minimum:
- "Think of your cortisol."
- "Your body's gonna hate you for this."
- "If you keep getting frustrated, you're going to pay for it later."
- "Who owns this, you or the robots?"
- "The robots don't care if you're upset. But your body does."
- "Time for a glass of water?"
- "Your future self called. They said chill."
- "Frustration is feedback. What's it telling you?"

**FR16:** Alert messages must be gentle, playful, and body-focused in tone. They must never be preachy, instructional, judgmental, or dismissive.

**FR17:** The alert banner must include a dismiss button and an "I'm fine" button.

**FR18:** Dismissing an alert closes the banner. The "I'm fine" button closes the banner and suppresses all alerts for 1 hour.

**FR19:** A cooldown period (configurable, default 10 minutes) must elapse between consecutive alerts. During cooldown, no new alerts fire even if thresholds are breached.

**FR20:** Alert delivery must use SSE so the banner appears without page refresh.

### Flow State Detection

**FR21:** The system must detect flow state when all of the following conditions are met for a sustained period:
- Turn rate exceeds a configurable minimum (default: 6 turns per hour)
- Rolling frustration average is below a configurable maximum (default: 3)
- The conditions have been sustained for a configurable minimum duration (default: 15 minutes)

**FR22:** Turn rate must be calculated directly from Turn timestamps (count of user turns in the last hour), without requiring E4-S3 Activity Monitoring infrastructure.

**FR23:** When flow state is detected, the system must display a positive reinforcement message on the dashboard.

**FR24:** The default set of flow state messages must include at minimum:
- "You've been in the zone for {minutes} minutes. Nice!"
- "Flow state detected. Keep riding it."
- "Productive streak: {minutes} minutes and counting."
- "{turns} turns, low frustration. You're cooking."

**FR25:** Flow state messages must appear periodically (every 15 minutes of sustained flow) rather than only once on entry.

### Headspace State Persistence

**FR26:** The system must persist headspace snapshots to the database, recording: timestamp, rolling averages (10-turn and 30-minute), traffic light state, turn rate, flow state flag, flow duration, last alert timestamp, and daily alert count.

**FR27:** Snapshots must be created after each headspace recalculation (i.e., after each user turn with a frustration score).

**FR28:** Snapshot retention must be configurable (default: 7 days). Snapshots older than the retention period must be pruned automatically. Pruning must occur opportunistically during snapshot creation (delete expired snapshots when writing a new one) to avoid requiring a separate scheduled job.

### API Endpoints

**FR29:** GET `/api/headspace/current` must return the most recent headspace state including: current frustration rolling averages, traffic light state (green/yellow/red), flow state flag, flow duration, alert suppression status, and timestamp.

**FR30:** GET `/api/headspace/history` must return a time-series of headspace snapshots, supporting optional query parameters for time range filtering (e.g., `?since=<ISO timestamp>`, `?limit=N`).

### Configuration

**FR31:** Headspace monitoring must be configurable via a `headspace` section in config.yaml with the following settings:
- `enabled` (boolean, default: true)
- `thresholds.yellow` (integer, default: 4)
- `thresholds.red` (integer, default: 7)
- `alert_cooldown_minutes` (integer, default: 10)
- `flow_detection.min_turn_rate` (integer, default: 6 turns per hour)
- `flow_detection.max_frustration` (integer, default: 3)
- `flow_detection.min_duration_minutes` (integer, default: 15)
- `snapshot_retention_days` (integer, default: 7)
- `messages.gentle_alerts` (list of strings)
- `messages.flow_messages` (list of strings, supporting `{minutes}` and `{turns}` placeholders)

**FR32:** When headspace monitoring is disabled in config, no frustration scores are extracted, no traffic light is shown, no alerts fire, and no snapshots are created. Turn summarisation continues normally without the frustration extraction enhancement.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Frustration extraction must add no more than 10% additional latency to the existing turn summarisation call (same LLM call with slightly extended prompt).

**NFR2:** Headspace recalculation (rolling averages, threshold checks, flow detection) must complete within 100ms.

**NFR3:** HeadspaceSnapshot table must have appropriate indexes on `timestamp` for efficient time-range queries.

**NFR4:** The system must handle concurrent user turns from multiple agents without race conditions in rolling calculations.

**NFR5:** The alert and suppression state must be maintained in memory (server-side) so that page refreshes do not lose context. Server restart resets suppression state (acceptable for MVP).

---

## 6. UI Overview

### Traffic Light Indicator

Positioned at the top of the dashboard, in or near the existing stats bar. The indicator is always visible when headspace monitoring is enabled:

- **Green (0-3):** Subtle green dot or small circle. Minimal visual weight — doesn't distract during calm sessions.
- **Yellow (4-6):** Visible yellow indicator. Larger, noticeable but not alarming. Pulsing or glowing effect optional.
- **Red (7-10):** Prominent red warning. Larger element, attention-drawing. Clear visual signal that something needs attention.

Transitions between states should use smooth CSS transitions (not jarring jumps).

### Alert Banner

A full-width or near-full-width banner that appears below the header when an alert triggers:

- Displays the randomly selected gentle alert message in a warm, readable font
- Includes a dismiss (X) button on the right
- Includes an "I'm fine" button (suppresses for 1 hour)
- Banner appears with a slide-down animation and disappears with slide-up
- Banner styling: warm/neutral background, not aggressive red (the traffic light handles urgency signaling)

### Flow State Message

A positive, subtle notification that appears when flow state is detected:

- Less prominent than alert banners — this is encouragement, not a warning
- Could be a toast-style notification or a subtle banner in green/blue tones
- Displays the flow message with actual values interpolated ({minutes}, {turns})
- Auto-dismisses after a few seconds or on click

---

## 7. Technical Context (Builder Guidance)

This section provides implementation guidance. These are not requirements — the builder may choose different approaches as long as the functional requirements are met.

### Enhanced Turn Summary Prompt

The existing turn summarisation prompt should be extended to request JSON output including both summary and frustration score:

```
Summarise this user turn in 1-2 concise sentences.

Also analyse the user's emotional state and rate their apparent frustration level 0-10:
- 0-3: Calm, patient, constructive
- 4-6: Showing some frustration (repetition, mild exasperation)
- 7-10: Clearly frustrated (caps, punctuation, harsh language, repeated complaints)

Consider:
- Tone and language intensity
- Punctuation patterns (!!!, ???, CAPS)
- Repetition of previous requests
- Explicit frustration signals ("again", "still not working", "why won't you")
- Patience indicators (clear instructions, positive framing)

Turn: {turn.text}

Return JSON:
{
  "summary": "...",
  "frustration_score": N
}
```

### Data Model Guidance

```python
# Add to Turn model
class Turn(Base):
    ...
    frustration_score: Mapped[int | None]  # 0-10, user turns only

# New model
class HeadspaceSnapshot(Base):
    __tablename__ = "headspace_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    timestamp: Mapped[datetime] = mapped_column(default=func.now())
    frustration_rolling_10: Mapped[float]  # Last 10 user turns average
    frustration_rolling_30min: Mapped[float]  # Last 30 min average
    state: Mapped[str]  # green, yellow, red
    turn_rate_per_hour: Mapped[float]
    is_flow_state: Mapped[bool]
    flow_duration_minutes: Mapped[int | None]
    last_alert_at: Mapped[datetime | None]
    alert_count_today: Mapped[int] = mapped_column(default=0)
```

### Default Alert Messages

```python
GENTLE_ALERTS = [
    "Think of your cortisol.",
    "Your body's gonna hate you for this.",
    "If you keep getting frustrated, you're going to pay for it later.",
    "Who owns this, you or the robots?",
    "The robots don't care if you're upset. But your body does.",
    "Time for a glass of water?",
    "Your future self called. They said chill.",
    "Frustration is feedback. What's it telling you?",
    "Step back. The code will still be here in 5 minutes.",
    "Your shoulders are probably up by your ears right now.",
    "Deep breath. Seriously.",
    "You're arguing with a machine. The machine doesn't mind.",
]

FLOW_MESSAGES = [
    "You've been in the zone for {minutes} minutes. Nice!",
    "Flow state detected. Keep riding it.",
    "Productive streak: {minutes} minutes and counting.",
    "{turns} turns, low frustration. You're cooking.",
]
```

### Config.yaml Addition

```yaml
headspace:
  enabled: true
  thresholds:
    yellow: 4
    red: 7
  alert_cooldown_minutes: 10
  snapshot_retention_days: 7
  flow_detection:
    min_turn_rate: 6        # turns per hour
    max_frustration: 3      # frustration score ceiling
    min_duration_minutes: 15
  messages:
    gentle_alerts:
      - "Think of your cortisol."
      - "Your body's gonna hate you for this."
      - "If you keep getting frustrated, you're going to pay for it later."
      - "Who owns this, you or the robots?"
      - "The robots don't care if you're upset. But your body does."
      - "Time for a glass of water?"
      - "Your future self called. They said chill."
      - "Frustration is feedback. What's it telling you?"
      - "Step back. The code will still be here in 5 minutes."
      - "Your shoulders are probably up by your ears right now."
      - "Deep breath. Seriously."
      - "You're arguing with a machine. The machine doesn't mind."
    flow_messages:
      - "You've been in the zone for {minutes} minutes. Nice!"
      - "Flow state detected. Keep riding it."
      - "Productive streak: {minutes} minutes and counting."
      - "{turns} turns, low frustration. You're cooking."
```

### Integration Points

- **E3-S2 Turn Summarisation:** Enhances the existing turn summarisation prompt (same LLM call, extended output format)
- **E4-S2 Project Controls:** Respects inference_paused — when paused, no frustration scores extracted
- **E4-S3 Activity Monitoring (soft dependency):** Flow detection calculates turn rate independently from Turn timestamps; does not require ActivityMetric model
- **Epic 1 SSE:** Uses existing broadcaster for real-time headspace_update and headspace_alert events
- **Dashboard Header:** Traffic light indicator positioned in the stats bar area

### SSE Event Types

- `headspace_update` — Sent when traffic light state changes. Payload: `{state, frustration_rolling_10, frustration_rolling_30min, is_flow_state, flow_duration_minutes}`
- `headspace_alert` — Sent when an alert triggers. Payload: `{message, alert_type, dismissable: true}`
- `headspace_flow` — Sent when flow state message should display. Payload: `{message, minutes, turns}`

---

## 8. Dependencies

| Dependency | Type | Notes |
|-----------|------|-------|
| E3-S2 Turn/Command Summarisation | Hard | Frustration extraction extends the existing turn summarisation prompt and service |
| E4-S2 Project Controls | Soft | Should respect inference_paused when extracting frustration scores |
| E4-S3 Activity Monitoring | Soft | Flow detection calculates turn rate independently; does not require E4-S3 infrastructure |
| Epic 1 SSE/Broadcaster | Hard | Required for real-time traffic light and alert delivery |

---

## 9. Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Frustration detection inaccuracy (false positives/negatives) | Medium | Conservative default thresholds; "I'm fine" dismiss with 1-hour suppression; configurable thresholds |
| Alerts becoming annoying rather than helpful | Medium | 10-minute cooldown; "I'm fine" suppression; playful non-judgmental tone; configurable messages |
| Users disabling the feature entirely | Low | Gentle tone, easy dismiss, positive flow reinforcement creates balanced experience |
| Privacy concerns about emotional analysis | Low | All data local (no external transmission); user controls enable/disable; transparent about what's analysed |
| LLM returning malformed JSON breaking turn summarisation | High | Graceful fallback: if JSON parse fails, treat response as plain text summary with null frustration_score |
| Alert fatigue from too-frequent notifications | Medium | Cooldown period, daily alert limit tracking, escalation-only logic (don't alert on every yellow turn) |

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-02 | PRD Workshop | Initial PRD generated from E4-S4 roadmap specification |
