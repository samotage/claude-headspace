# Headspace Monitoring

Headspace is a monitoring layer that tracks your frustration levels and flow state across all Claude Code sessions.

## How It Works

Every time you send a prompt (USER turn), the LLM analyses it for frustration on a 0-10 scale. These scores are aggregated into rolling averages at three time windows:

- **10-turn** - Rolling average over the last 10 user turns
- **30-minute** - Rolling average over the last 30 minutes
- **3-hour** - Rolling average over the session (configurable window)

## Traffic Light Alerts

Based on the rolling averages, the system raises traffic-light alerts:

- **Green** - Frustration is below the yellow threshold (default: 4). All good.
- **Yellow** - Moderate frustration detected. A yellow indicator appears in the header.
- **Red** - High frustration detected (default: 7). A red banner appears at the top of the dashboard with a dismiss option.

The thresholds are configurable in `config.yaml` under `headspace.thresholds`.

## Header Indicator

The header shows a small coloured dot next to **HEADSPACE**:

- Green dot: everything is fine
- Yellow dot: moderate frustration
- Red dot: high frustration, alert banner shown

## Alert Banner

When frustration reaches the red threshold, a banner appears at the top of the dashboard:

- Shows the current frustration state
- Click **"I'm fine"** to suppress alerts for 1 hour
- Alerts respect a cooldown period (default: 10 minutes) to avoid nagging

## Flow State Detection

The system also detects positive "flow state" based on:

- Turn rate above a minimum threshold (default: 6 turns/hour)
- Frustration below a maximum (default: 3)
- Sustained for a minimum duration (default: 15 minutes)

When flow is detected, a brief green toast appears: "Flow state detected."

## Suppressing Alerts

If you're intentionally working on something frustrating and don't want interruptions:

1. Click **"I'm fine"** on the alert banner
2. Alerts are suppressed for 1 hour
3. Monitoring continues in the background; data is still recorded

## Configuration

```yaml
headspace:
  enabled: true
  thresholds:
    yellow: 4
    red: 7
  session_rolling_window_minutes: 180
  alert_cooldown_minutes: 10
  snapshot_retention_days: 7
  flow_detection:
    min_turn_rate: 6
    max_frustration: 3
    min_duration_minutes: 15
```

Set `headspace.enabled: false` to disable the entire monitoring layer.

## Viewing History

The activity page shows frustration trends over time. The headspace API (`/api/headspace/history`) provides historical snapshot data for analysis.
