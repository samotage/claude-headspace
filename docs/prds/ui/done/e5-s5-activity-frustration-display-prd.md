---
validation:
  status: valid
  validated_at: '2026-02-04T11:28:44+11:00'
---

## Product Requirements Document (PRD) — Multi-Window Frustration Display for Activity Page

**Project:** Claude Headspace
**Scope:** Activity page frustration metrics — average-based display + rolling-window frustration state widget
**Author:** Sam (PRD Workshop)
**Status:** Draft

---

## Executive Summary

The activity page currently displays frustration as a summed total per hourly bucket (e.g., "60 Frustration"), which correlates with turn volume rather than frustration intensity. A calm 50-turn session at score 1 shows "50" — appearing worse than 5 genuinely angry turns at score 8 showing "40." Users cannot distinguish between high-volume/low-frustration sessions and genuinely frustrating ones.

This PRD addresses the problem with two complementary changes: (1) fix all existing frustration displays on the activity page to show average frustration per scored turn instead of sum, and (2) add a "Frustration State" widget showing three rolling-window averages (immediate, short-term, session) for at-a-glance current frustration state.

All underlying data already exists in the system. The ActivityMetric model stores both `total_frustration` and `frustration_turn_count`, and the HeadspaceSnapshot model stores `frustration_rolling_10` and `frustration_rolling_30min`. The only new data requirement is a 3-hour rolling window average on HeadspaceSnapshot.

---

## 1. Context & Purpose

### 1.1 Context

The activity page provides hourly metrics at overall, project, and agent scope levels. Frustration is currently displayed as a raw sum — the total of all frustration scores within a time period. This makes frustration appear proportional to turn volume: busy sessions look "more frustrated" regardless of actual frustration intensity. The chart's frustration line overlay tracks turn bars almost exactly, providing no additional insight.

Meanwhile, the headspace monitor already computes rolling frustration averages (10-turn and 30-minute windows) for traffic-light alerting, but this real-time frustration state is not visible on the activity page.

### 1.2 Target User

Users monitoring Claude Code sessions across multiple projects who need to:
- Quickly identify which sessions are genuinely struggling vs. simply active
- See current frustration state at a glance without navigating to headspace-specific views
- Trust that the displayed frustration metric reflects intensity, not volume

### 1.3 Success Moment

A user glances at the activity page and immediately sees that one project has an average frustration of 7.2 (red) despite only 8 turns, while another project with 45 turns shows a calm 1.8 (green). The frustration state widget shows the immediate window spiking to 6.5 (yellow) while the session window remains at 3.1 (green), indicating a recent rough patch in an otherwise smooth session.

---

## 2. Scope

### 2.1 In Scope

- Activity page metric cards display average frustration per scored turn (0-10 scale) instead of raw sum, at overall, project, and agent levels
- Activity page chart frustration line overlay uses average frustration per bucket instead of sum, with a fixed 0-10 right Y-axis
- Threshold-based coloring (green < 4, yellow 4-7, red > 7) applied to all displayed frustration averages
- Buckets/periods with no scored turns display a dash (—) in cards and a gap in the chart line
- New "Frustration State" widget on the activity page showing three rolling-window averages:
  - Immediate (~last 10 USER turns)
  - Short-term (last 30 minutes)
  - Session (last 3 hours, duration configurable)
- Each rolling window in the widget displays a numeric average (0-10) with threshold-based coloring
- Hover tooltips on widget indicators showing frustration threshold boundaries for context
- Widget updates in real-time via SSE (existing headspace events)
- Widget hidden when headspace monitoring is disabled
- New `frustration_rolling_3hr` field on HeadspaceSnapshot model, computed by HeadspaceMonitor
- 3-hour rolling window duration configurable via `config.yaml → headspace`
- Configuration UI section for frustration metric settings (thresholds and rolling window durations)
- All frustration thresholds and rolling window durations read from config — no hardcoded values

### 2.2 Out of Scope

- Dashboard agent cards — no changes to frustration display on the main dashboard
- Headspace alert system — state transitions, flow detection, alert cooldown remain unchanged
- ActivityMetric model and activity aggregator — no schema or aggregation logic changes (average computed at display time from existing fields)
- Per-agent or per-project headspace rolling averages — rolling windows remain global (system-wide)
- Headspace history API — no changes to `/api/headspace/history`
- Notification system — no changes
- Any pages other than the activity page (`/activity`)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Activity page metric cards show frustration as a decimal average (0-10 scale) instead of an integer sum, at all scope levels (overall, project, agent)
2. Frustration metric card values are colored green when average < 4, yellow when 4-7, red when > 7
3. Metric cards display "—" when no scored turns exist in the selected period
4. Chart frustration line shows per-bucket average (0-10) with a fixed right Y-axis scaled 0-10
5. Chart frustration line has gaps (no drawn segment) for buckets with no scored turns
6. Chart frustration line is visually decoupled from turn volume bars — a high-turn/low-frustration hour shows high bars but a low frustration line
7. Frustration state widget displays three numeric averages with threshold-based coloring
8. Widget values update in real-time when new headspace SSE events arrive
9. Widget is not visible when headspace monitoring is disabled
10. Hover tooltips on widget values show the threshold boundaries (green < 4, yellow 4-7, red > 7)
11. All threshold values and rolling window durations are sourced from configuration, not hardcoded
12. Configuration UI includes a section for editing frustration thresholds and the 3-hour rolling window duration

### 3.2 Non-Functional Success Criteria

1. The 3-hour rolling window computation does not add noticeable latency to the headspace recalculation cycle
2. Existing headspace monitor tests continue to pass

---

## 4. Functional Requirements (FRs)

### Average-Based Frustration Display

**FR1:** Activity page overall metric cards display frustration as an average per scored turn (total_frustration ÷ frustration_turn_count) on a 0-10 scale, rounded to one decimal place.

**FR2:** Activity page project-level metric cards display frustration as an average per scored turn, matching the same format as overall cards.

**FR3:** Activity page agent-level rows display frustration as an average per scored turn, matching the same format as overall and project cards.

**FR4:** All displayed frustration averages are colored based on configurable thresholds: green below the yellow threshold, yellow between yellow and red thresholds, red at or above the red threshold.

**FR5:** When a period or bucket contains no scored turns (frustration_turn_count is zero or null), the frustration metric displays "—" (em dash) with no threshold coloring applied.

### Chart Frustration Line

**FR6:** The Turn Activity chart's frustration line overlay displays average frustration per bucket (total_frustration ÷ frustration_turn_count) instead of the raw frustration sum.

**FR7:** The chart's right Y-axis (frustration scale) is fixed at 0-10, matching the frustration score scale.

**FR8:** For hourly buckets with no scored turns, the chart frustration line has a gap — no line segment is drawn to or from that bucket.

**FR9:** The chart frustration line applies threshold-based coloring to the line or data points, using the same configurable thresholds as the metric cards.

### Frustration State Widget

**FR10:** The activity page includes a "Frustration State" widget positioned near the overall metrics section, displaying three rolling-window frustration averages: immediate (last N turns), short-term (last M minutes), and session (last P minutes).

**FR11:** Each rolling-window value in the widget is displayed as a numeric average on a 0-10 scale, rounded to one decimal place, with a label identifying the window (e.g., "Immediate," "Short-term," "Session").

**FR12:** Each rolling-window value is colored based on the same configurable thresholds used for metric cards (green/yellow/red).

**FR13:** When a rolling-window value is unavailable (null — no scored turns in that window), the widget displays "—" with no threshold coloring.

**FR14:** Hovering over any rolling-window indicator in the widget shows a tooltip displaying the threshold boundaries (e.g., "Green: < 4 | Yellow: 4-7 | Red: > 7").

**FR15:** The frustration state widget updates in real-time via SSE when new headspace state events are broadcast.

**FR16:** The frustration state widget is hidden (not rendered) when headspace monitoring is disabled.

### 3-Hour Rolling Window

**FR17:** HeadspaceSnapshot records include a session-level rolling frustration average computed over a configurable time window (default: 3 hours / 180 minutes).

**FR18:** The session-level rolling window duration is configurable via `config.yaml` under the headspace section.

**FR19:** The `/api/headspace/current` endpoint includes the session-level rolling frustration average in its response.

### Configuration

**FR20:** All frustration thresholds (yellow, red) and rolling window durations are read from configuration at runtime — no hardcoded threshold or duration values exist in the codebase.

**FR21:** The configuration UI includes a section for frustration settings, allowing users to view and edit frustration thresholds and the session rolling window duration.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The session-level rolling window query performs comparably to the existing 30-minute rolling window query — the wider time range should not cause perceptible delay in the headspace recalculation cycle.

**NFR2:** The frustration state widget SSE handling reuses existing headspace event infrastructure and does not create additional SSE connections.

---

## 6. UI Overview

### Metric Cards (Modified)

The existing frustration metric cards at overall, project, and agent levels change from displaying a raw integer sum (e.g., "60") to displaying a decimal average (e.g., "3.8"). The number is colored green, yellow, or red based on thresholds. When no frustration data exists, the card shows "—" in neutral styling.

### Turn Activity Chart (Modified)

The chart's green frustration line overlay changes from plotting raw sums (right Y-axis 0-25+) to plotting per-bucket averages (right Y-axis fixed 0-10). The line is decoupled from turn volume — bars can be tall while the frustration line stays low. Buckets with no scored turns create gaps in the line rather than plotting zero. The line or data points use threshold-based coloring.

### Frustration State Widget (New)

A compact horizontal widget positioned near the top of the activity page, adjacent to or below the overall metrics section. Contains three labeled numeric indicators arranged horizontally:

- **Immediate** — rolling average of last ~10 scored USER turns
- **Short-term** — rolling average of last 30 minutes
- **Session** — rolling average of last 3 hours (configurable)

Each indicator shows a numeric value (e.g., "3.2") with a colored background matching the threshold state (green/yellow/red). Hovering over any indicator reveals a tooltip showing the threshold boundaries. When headspace is disabled, the entire widget is hidden. When a window has no data, it shows "—" in neutral styling.

### Configuration UI (Modified)

The configuration page gains a frustration settings section showing:
- Yellow threshold value
- Red threshold value
- Session rolling window duration (minutes)

These are editable and persist to `config.yaml` under the headspace section.
