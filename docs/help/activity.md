# Activity Monitoring

The activity page shows real-time and historical metrics about your Claude Code usage.

## Accessing Activity

Navigate to **>activity** in the header.

## Overall Metrics

The top section shows system-wide metrics for the selected time window:

- **Turns** - Total number of turns (user + agent exchanges)
- **Turn Rate** - Average turns per hour
- **Avg Turn Time** - Average time between a user prompt and the agent's response
- **Active Agents** - Number of agents active during the period
- **Frustration** - Count of turns with elevated frustration scores

## Frustration State Widget

Three indicators show frustration levels at different time scales:

- **Immediate** (10-turn rolling average) - Most recent interaction pattern
- **Short-term** (30-minute rolling average) - Recent session trend
- **Session** (3-hour rolling average) - Overall session health

Each indicator is colour-coded:
- **Green** - Frustration below yellow threshold (default: 4)
- **Yellow** - Moderate frustration (between yellow and red thresholds)
- **Red** - High frustration (above red threshold, default: 7)

## Time Windows

Use the **Day / Week / Month** buttons to change the aggregation window:

- **Day** - Last 24 hours, hourly granularity
- **Week** - Last 7 days, hourly granularity
- **Month** - Last 30 days, daily granularity

Use the **< >** arrows to navigate to earlier or later periods.

## Activity Chart

A time-series bar chart shows turn counts over time. The chart adjusts its granularity based on the selected window.

## Per-Project and Per-Agent Metrics

Below the overall metrics, the page breaks down activity by project and by individual agent within each project.

## Data Source

Activity metrics are computed by a background aggregator that runs every 5 minutes. Metrics are stored as hourly buckets in the database at three scopes: agent, project, and system-wide.
