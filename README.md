# Claude Headspace

**AI-powered Claude Code session monitoring dashboard -- the only tool with frustration detection, flow state tracking, and agent priority scoring.**

Monitor and manage all your Claude Code agents from a single web dashboard. See what each agent is working on, who needs input, which sessions are stuck -- and respond to agents directly via tmux, without switching terminal tabs or just click on the agent to open their iTerm2 directly. Spec-driven, production-grade software with 85+ test files and full observability.

![Python](https://img.shields.io/badge/python-3.10+-blue)
![Flask](https://img.shields.io/badge/flask-3.0+-green)
![License](https://img.shields.io/badge/license-MIT-brightgreen)
![macOS](https://img.shields.io/badge/platform-macOS-lightgrey)


## Quick Start

### One-Command Setup (via Claude Code)

```bash
git clone https://github.com/samotage/claude-headspace.git
cd claude-headspace
```

Then paste this into a Claude Code session:

```
Read the setup instructions at docs/application/claude_code_setup_prompt.md and run them.
```

Claude Code will automatically install hooks, create the database, set up the CLI, and verify everything. You approve each step. [View the full setup prompt](docs/application/claude_code_setup_prompt.md) to see exactly what it does.

### Manual Setup

<details>
<summary>Manual installation steps</summary>

#### Prerequisites

- Python 3.10+
- PostgreSQL (running)
- Node.js (for Tailwind CSS)
- macOS (for iTerm2 focus + notifications)
- tmux (for responding to agents from the dashboard)
- jq (`brew install jq`)
- An [OpenRouter API key](https://openrouter.ai/) (for AI features)

#### Install

```bash
git clone https://github.com/samotage/claude-headspace.git
cd claude-headspace

# Python dependencies
pip install -e ".[dev]"

# Node dependencies (Tailwind CSS)
npm install

# Database
createdb claude_headspace
flask db upgrade

# Configure
cp .env.example .env
# Edit .env and set OPENROUTER_API_KEY
```

#### Install Claude Code Hooks

```bash
bin/install-hooks.sh
```

This configures `~/.claude/settings.json` so every Claude Code session sends lifecycle events to the dashboard.

#### Symlink the CLI

```bash
chmod +x bin/claude-headspace
ln -sf "$(pwd)/bin/claude-headspace" ~/bin/claude-headspace
```

</details>

### Run

```bash
python run.py
# Dashboard available at http://localhost:5055
```

### Launch a Monitored Session

```bash
claude-headspace start              # Session with tmux bridge (default)
claude-headspace start --no-bridge  # Without tmux bridge
```

### Build CSS (development)

```bash
npx tailwindcss -i static/css/src/input.css -o static/css/main.css --watch
```

## Why Claude Headspace?

If you run multiple Claude Code sessions across projects, you know the pain: dozens of terminal tabs, constant context-switching, no idea which agent is stuck waiting for input, and no way to tell if an agent has been spinning its wheels in frustration for 20 minutes.

Claude Headspace solves this with:

- **One dashboard, all agents** -- every active Claude Code session displayed as a card with real-time status
- **AI-generated summaries** -- LLM-powered turn and task summaries so you know what each agent is doing without reading transcripts
- **Frustration detection** -- each user turn scored 0-10 for frustration, with rolling averages and traffic-light alerts (green/yellow/red)
- **Flow state tracking** -- detects when you're in flow and suppresses non-critical interruptions
- **Priority scoring** -- agents ranked 0-100 based on objective alignment, state, and recency
- **Click-to-focus** -- bring any iTerm2 terminal to the foreground from the dashboard
- **Respond from dashboard** -- send text responses to Claude Code sessions via tmux
- **macOS notifications** -- native alerts when agents need input or complete tasks

## How It Works

Claude Headspace is **event-driven**, not polling-based. It uses [Claude Code hooks](https://docs.anthropic.com/en/docs/claude-code/hooks) to receive lifecycle events directly from your terminal sessions:

```
Claude Code (Terminal)              Claude Headspace (Dashboard)
  |                                        |
  |-- session-start ------------------->   | Agent created
  |-- user-prompt-submit -------------->   | State -> COMMANDED
  |-- pre-tool-use / post-tool-use ---->   | Tool tracking
  |-- stop ---------------------------->   | Turn complete, summarise
  |-- permission-request -------------->   | Needs input alert
  |-- notification -------------------->   | Timestamp update
  |-- session-end --------------------->   | Agent deactivated
```

Events arrive in <100ms (vs 2-second polling). State transitions are 100% accurate (vs inference from terminal scraping).

## Features

### Multi-Agent Session Monitoring
- Track unlimited concurrent Claude Code sessions across projects
- 5-state command lifecycle: `IDLE -> COMMANDED -> PROCESSING -> AWAITING_INPUT -> COMPLETE`
- Real-time state updates via Server-Sent Events (SSE)
- Session correlation maps Claude Code sessions to agent records automatically

### AI-Powered Intelligence Layer
- **Turn summarisation** -- 1-2 sentence summaries of each user/agent exchange (Claude Haiku)
- **Command summarisation** -- 2-3 sentence completion summaries (Claude Haiku)
- **Frustration scoring** -- 0-10 score on every user turn, persisted and tracked over time
- **Priority scoring** -- batch score all active agents 0-100 based on objective/waypoint alignment
- **Progress summaries** -- project-level analysis from git commit history (Claude Sonnet)
- **Project descriptions** -- auto-generated from codebase analysis
- Content-based caching, rate limiting, and cost tracking for all LLM calls

### Headspace Monitor
- Rolling frustration averages (10-turn and 30-minute windows)
- Traffic-light alerting: green (all good), yellow (elevated frustration), red (intervention needed)
- Flow state detection with alert suppression
- Headspace snapshots persisted for historical analysis

### Brain Reboot
- Generate waypoint + progress summary snapshots for project context resets
- Export brain reboot documents to project filesystem
- Archive history with timestamped versions

### Dashboard Controls
- **iTerm2 focus switching** -- click any agent card to bring its terminal pane to the foreground
- **Tmux bridge** -- respond to agents directly from the dashboard via tmux send-keys
- **Agent dismiss** -- mark agents as ended from the dashboard
- **Inference pause** -- per-project controls to pause/resume LLM inference
- **Objective system** -- set global priority context that influences agent scoring

### Project Management
- Per-project settings, metadata detection, and waypoint editing
- Git metadata extraction (repo URL, current branch)
- Activity metrics with hourly aggregation at agent, project, and system-wide scope
- Archive history for waypoints and artifacts

### Notifications
- Native macOS notifications via terminal-notifier
- Alerts when agents need input (permission requests)
- Alerts on task completion
- Per-agent rate limiting to prevent notification spam

## Architecture

```
+------------------------------------------------------------+
|           Claude Code (Terminal Sessions)                    |
|   8 lifecycle hooks fire on events ---------------+         |
+---------------------------------------------------+---------+
                                                    |
                                                    v
+------------------------------------------------------------+
|           Claude Headspace (Flask)                           |
|                                                             |
|  Hook Receiver -> Session Correlator -> Command Lifecycle   |
|  Intent Detector -> State Machine (5-state)                 |
|                                                             |
|  Inference Service (OpenRouter / Claude Haiku + Sonnet)     |
|    +-- Turn & Command Summarisation                         |
|    +-- Frustration Detection (0-10 scoring)                 |
|    +-- Priority Scoring (0-100 agent ranking)               |
|    +-- Progress Summary (project-level analysis)            |
|    +-- Brain Reboot (waypoint + progress export)            |
|                                                             |
|  Headspace Monitor (frustration / flow / traffic-light)     |
|  Tmux Bridge (respond to agents via tmux send-keys)         |
|  Activity Aggregator (hourly metrics)                       |
|  Agent Reaper (cleanup inactive agents)                     |
|                                                             |
|  Broadcaster -> SSE -> Dashboard (real-time)                |
|  Event Writer -> PostgreSQL (audit trail)                   |
+------------------------------------------------------------+
```

## How It Compares

| Feature | Claude Headspace | claudecodeui | sniffly | claude-code-monitor | agent-deck |
|---------|:---:|:---:|:---:|:---:|:---:|
| Multi-session Kanban board | Yes | No | No | Yes | Yes |
| AI-powered summaries | Yes | No | No | No | No |
| Frustration detection | **Unique** | No | No | No | No |
| Flow state tracking | **Unique** | No | No | No | No |
| Priority scoring | **Unique** | No | No | No | No |
| Respond to agents | Yes (tmux) | No | No | No | No |
| Headspace monitoring | **Unique** | No | No | No | No |
| Brain reboot export | **Unique** | No | No | No | No |
| Event-driven hooks | Yes (8 hooks, <100ms) | No | No | No | No |
| Activity metrics | Yes (hourly) | No | Yes | No | No |
| Click-to-focus terminal | Yes (iTerm2) | No | No | Yes | No |
| macOS notifications | Yes (rate-limited) | No | No | Yes | No |
| PostgreSQL persistence | Yes (full audit trail) | No | No | No | No |

## Engineering Quality

Claude Headspace is spec-driven, production-grade software -- not a weekend prototype or vibe-coded experiment.

- **210+ commits** with structured PRD-driven development and [OpenSpec](openspec/) change management
- **85+ test files** across 4 tiers: unit, route, integration (real PostgreSQL), and E2E (Playwright browser tests)
- **24 database migrations** via Alembic with full schema evolution
- **40 service modules** with dependency injection via Flask extensions
- **34 OpenSpec specifications** tracking every feature from proposal to implementation
- **Full configuration system** with YAML config, environment overrides, and a config editor UI
- **Comprehensive logging** with audit trail, inference call tracking, and event history
- **Background services** -- agent reaper, activity aggregator, tmux health checker run in separate threads
- **Content-based LLM caching** with rate limiting and cost tracking across all inference calls

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.10+, Flask 3.0+ |
| Database | PostgreSQL via SQLAlchemy + Alembic |
| Real-time | Server-Sent Events (SSE) |
| LLM | OpenRouter API (Claude Haiku for turns, Sonnet for projects) |
| Frontend | Vanilla JS + Tailwind CSS 3.0 |
| Terminal | iTerm2 integration via AppleScript + tmux bridge |
| Notifications | terminal-notifier (macOS native) |
| Testing | pytest + factory-boy + Playwright (E2E) |

## Configuration

Edit `config.yaml` to configure:

- **Server** -- host, port, debug mode
- **Database** -- PostgreSQL connection, pool settings
- **OpenRouter** -- model selection, rate limits, caching
- **Headspace** -- frustration thresholds (yellow at 4, red at 7)
- **Reaper** -- inactive agent cleanup interval
- **Tmux bridge** -- health check interval, subprocess timeout
- **Notifications** -- enable/disable, sound, rate limiting
- **SSE** -- heartbeat interval, max connections

## API

Claude Headspace exposes a full REST API:

| Endpoint | Description |
|----------|-------------|
| `GET /` | Dashboard |
| `GET /api/events/stream` | SSE event stream |
| `POST /hook/*` | Claude Code hook endpoints (8 hooks) |
| `POST /api/summarise/turn/<id>` | Generate turn summary |
| `POST /api/summarise/command/<id>` | Generate task summary |
| `POST /api/priority/score` | Trigger priority scoring |
| `GET /api/priority/rankings` | Current agent rankings |
| `POST /api/respond/<agent_id>` | Send response to agent via tmux |
| `POST /api/focus/<agent_id>` | iTerm2 focus control |
| `GET /api/headspace/current` | Current headspace state |
| `GET /api/metrics/*` | Activity metrics |

See the full API reference in [CLAUDE.md](CLAUDE.md#api-endpoints).

## License

MIT
