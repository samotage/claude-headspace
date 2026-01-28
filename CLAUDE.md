<!-- OPENSPEC:START -->
# OpenSpec Instructions

These instructions are for AI assistants working in this project.

Always open `@/openspec/AGENTS.md` when the request:
- Mentions planning or proposals (words like proposal, spec, change, plan)
- Introduces new capabilities, breaking changes, architecture shifts, or big performance/security work
- Sounds ambiguous and you need the authoritative spec before coding

Use `@/openspec/AGENTS.md` to learn:
- How to create and apply change proposals
- Spec format and conventions
- Project structure and guidelines

Keep this managed block so 'openspec update' can refresh the instructions.

<!-- OPENSPEC:END -->

# CLAUDE.md - Claude Headspace Project Guide

## Project Overview

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors terminal sessions and displays real-time session status with click-to-focus functionality and native macOS notifications.

**Purpose:**
- Track active Claude Code agents across projects
- Display agent status using a 5-state model (idle/commanded/processing/awaiting_input/complete)
- Click-to-focus: bring WezTerm windows to foreground from the dashboard
- Native macOS notifications when input is needed or tasks complete
- Real-time updates via Server-Sent Events (SSE)

## Architecture

The project has two architectures:

1. **New Architecture (src/)** - Recommended
   - Pydantic models with validation
   - 5-state task model
   - Service injection and proper testing
   - WezTerm-first with Lua hooks
   - 450+ tests, 70%+ coverage

2. **Legacy Architecture (lib/)** - Deprecated
   - Single-file Flask app
   - 3-state model (processing/input_needed/idle)
   - iTerm/tmux focus

## Tech Stack

- **Python:** 3.10+
- **Framework:** Flask with blueprints
- **Models:** Pydantic v2
- **Config:** PyYAML with migration
- **Terminal:** WezTerm (recommended) or tmux
- **Notifications:** terminal-notifier
- **LLM:** OpenRouter API

## Common Commands

```bash
# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the application (NEW - recommended)
python run.py
# Or: python -m src.app
# Dashboard available at http://localhost:5050

# Run legacy mode (deprecated)
python monitor.py
# Or with new architecture: USE_NEW_ARCH=1 python monitor.py

# Restart the server
./restart_server.sh

# Run tests
pytest
pytest --cov=src  # With coverage

# Start a monitored Claude session (in your project directory)
claude-monitor start --wezterm  # WezTerm (recommended)
claude-monitor start --tmux     # tmux (legacy)
```

## Directory Structure

```
claude_headspace/
├── run.py               # NEW: Entry point (recommended)
├── monitor.py           # LEGACY: All-in-one Flask app (deprecated)
├── config.py            # LEGACY: Config module (deprecated)
├── config.yaml.example  # Configuration template
├── config.yaml          # User configuration (gitignored)
├── .env                 # Environment variables (gitignored)
├── .env.example         # Environment template
├── requirements.txt     # Python dependencies
│
├── src/                 # NEW: Main application code
│   ├── __init__.py
│   ├── app.py           # Flask application factory
│   ├── models/          # Pydantic domain models
│   │   ├── __init__.py
│   │   ├── agent.py     # Agent model
│   │   ├── task.py      # Task model with 5-state machine
│   │   ├── project.py   # Project model
│   │   ├── headspace.py # Headspace model
│   │   └── config.py    # AppConfig model
│   ├── services/        # Business logic services
│   │   ├── __init__.py
│   │   ├── agent_store.py      # Single source of truth
│   │   ├── state_interpreter.py # LLM state detection
│   │   ├── inference_service.py # OpenRouter API
│   │   ├── governing_agent.py   # Main orchestrator
│   │   ├── hook_receiver.py     # Claude Code lifecycle hooks
│   │   ├── priority_service.py  # Cross-project priorities
│   │   ├── notification_service.py
│   │   ├── event_bus.py        # SSE broadcasting
│   │   ├── config_service.py   # Config with migration
│   │   └── git_analyzer.py     # Git history analysis
│   ├── backends/        # Terminal backends
│   │   ├── __init__.py
│   │   ├── base.py      # Abstract interface
│   │   ├── wezterm.py   # WezTerm backend (recommended)
│   │   └── tmux.py      # tmux backend
│   └── routes/          # Flask blueprints
│       ├── __init__.py
│       ├── agents.py    # /api/agents endpoints
│       ├── tasks.py     # /api/tasks endpoints
│       ├── config.py    # /api/config endpoints
│       ├── events.py    # /api/events SSE endpoint
│       └── hooks.py     # /hook/* Claude Code hooks
│
├── tests/               # Test suite (mirrors src/)
│   ├── conftest.py      # Shared fixtures
│   ├── models/
│   ├── services/
│   ├── backends/
│   └── routes/
│
├── lib/                 # LEGACY: Deprecated modules
│   └── ...              # See lib/__init__.py for migration guide
│
├── static/              # Frontend assets
│   ├── css/
│   │   └── kanban.css   # Dashboard styles (5-state support)
│   └── js/
│       ├── api.js       # API client
│       ├── kanban.js    # Dashboard logic
│       ├── sse.js       # SSE client
│       └── utils.js     # Utilities (5-state support)
├── templates/
│   └── index.html       # Dashboard template
│
├── data/                # Application data
│   ├── agents.json      # Agent persistence
│   ├── tasks.json       # Task persistence
│   └── projects/        # Project YAML files
│
├── bin/
│   └── claude-monitor   # Session wrapper script
├── orch/                # PRD orchestration
├── docs/                # Documentation
├── .claude/             # Claude Code settings
├── CLAUDE.md            # This file
└── README.md            # User documentation
```

## Configuration

Edit `config.yaml` to configure monitored projects:

```yaml
projects:
  - name: "project_name"
    path: "/absolute/path/to/project"
    # tmux: false           # Disable tmux to use iTerm mode (optional)

scan_interval: 2          # Refresh interval in seconds (default)
```

## Terminal Backend Integration

Terminal backends enable bidirectional control of Claude Code sessions:
- **Send text/commands** to sessions via the API
- **Capture full output** beyond iTerm's 5000 char limit
- Enable **voice bridge** and **remote control** features

### Available Backends

| Backend | Read | Write | Notes |
|---------|------|-------|-------|
| tmux | ✅ | ✅ | Default, requires `brew install tmux` |
| WezTerm | ✅ | ✅ | Cross-platform, full scrollback, requires `brew install --cask wezterm` |

### Configuration

Set the default backend in `config.yaml`:
```yaml
terminal_backend: "tmux"    # or "wezterm"
```

Or use command-line flags:
```bash
claude-monitor start             # Use configured default
claude-monitor start --tmux      # Force tmux
claude-monitor start --wezterm   # Force WezTerm
```

### WezTerm-specific settings

```yaml
wezterm:
  workspace: "claude-monitor"  # Workspace for grouping sessions
  full_scrollback: true        # Enable full scrollback capture
```

### Session Control API

Send text to a session:
```bash
curl -X POST http://localhost:5050/api/send/<session_id> \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, Claude!", "enter": true}'
```

Capture session output:
```bash
curl http://localhost:5050/api/output/<session_id>?lines=100
```

## How It Works

### New Architecture (src/)

1. **GoverningAgent:** Main orchestrator that coordinates all services
2. **AgentStore:** Single source of truth for all agents, tasks, and projects
3. **Terminal Backends:** WezTerm or tmux capture terminal output
4. **StateInterpreter:** LLM-based state detection with regex fast-path
5. **5-State Model:** Tasks transition through idle → commanded → processing → awaiting_input/complete
6. **EventBus:** Real-time SSE broadcasting to dashboard
7. **NotificationService:** macOS notifications on state changes

### 5-State Task Model

```
         ┌─────────────────────────────────────┐
         │                                     │
         ▼                                     │
     ┌───────┐  user_command  ┌───────────┐   │
     │ idle  │──────────────▶│ commanded │   │
     └───────┘                └─────┬─────┘   │
         ▲                          │         │
         │                   agent_started    │
         │                          │         │
         │                          ▼         │
         │                   ┌────────────┐   │
         │   task_completed  │ processing │───┘
         │◀──────────────────┴─────┬──────┘
         │                         │
         │                  needs_input
         │                         │
         │                         ▼
         │                 ┌───────────────┐
         │  input_provided │awaiting_input │
         └◀────────────────┴───────────────┘
```

### Claude Code Hooks (Event-Driven)

The monitor can receive lifecycle events directly from Claude Code via hooks:

```
┌─────────────────────────────────────────────────────────────┐
│              Claude Code (Terminal Session)                  │
│                                                              │
│  Hooks fire on lifecycle events ──────────────────┐         │
└──────────────────────────────────────────────────┼─────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Claude Headspace (Flask)                        │
│              http://localhost:5050                           │
│                                                              │
│  POST /hook/session-start      → Agent created, IDLE        │
│  POST /hook/user-prompt-submit → Transition to PROCESSING   │
│  POST /hook/stop               → Transition to IDLE         │
│  POST /hook/notification       → Timestamp update           │
│  POST /hook/session-end        → Agent marked inactive      │
└─────────────────────────────────────────────────────────────┘
```

**Benefits over polling:**
- Instant state updates (<100ms vs 2-second polling)
- 100% confidence (event-based vs inference)
- Reduced resource usage (no constant terminal scraping)

**Setup:**

Ask Claude Code to install the hooks:
> "Install the Claude Headspace hooks. Copy `bin/notify-headspace.sh` to `~/.claude/hooks/` and merge `docs/claude-code-hooks-settings.json` into `~/.claude/settings.json`. Use absolute paths (not ~ or $HOME)."

**Important:** Hook commands must use absolute paths (e.g., `/Users/yourname/.claude/hooks/...`).

See `docs/architecture/claude-code-hooks.md` for detailed documentation.

### Legacy Architecture (lib/)

1. **State Files:** `.claude-monitor-*.json` files in project directories
2. **PID/TTY Matching:** Match process to terminal session
3. **3-State Model:** processing/input_needed/idle
4. **iTerm/tmux:** AppleScript-based focus

## Key Services (New Architecture)

| Service | Purpose |
|---------|---------|
| `AgentStore` | Single source of truth for agents, tasks, projects |
| `GoverningAgent` | Main orchestrator, coordinates scan loop |
| `StateInterpreter` | LLM-based state detection with regex fast-path |
| `InferenceService` | OpenRouter API integration |
| `PriorityService` | Cross-project priority ranking |
| `NotificationService` | macOS notifications via terminal-notifier |
| `EventBus` | SSE event broadcasting |
| `ConfigService` | Config loading with legacy migration |
| `GitAnalyzer` | Git history analysis for narratives |
| `HookReceiver` | Claude Code lifecycle hooks for event-driven state detection |

### Key Methods

| Method | Service | Purpose |
|--------|---------|---------|
| `scan_once()` | GoverningAgent | Run one scan cycle across all terminals |
| `interpret_state()` | StateInterpreter | Detect task state from terminal output |
| `transition()` | TaskStateMachine | Apply state transition with validation |
| `emit()` | EventBus | Broadcast SSE event to all clients |
| `notify()` | NotificationService | Send macOS notification |
| `get_current_task()` | AgentStore | Get agent's current task |
| `compute_priorities()` | PriorityService | Rank agents by priority |

### Legacy Functions (lib/)

| Function | Purpose |
|----------|---------|
| `scan_sessions()` | Scan tmux sessions for Claude Code |
| `parse_activity_state()` | 3-state detection from terminal |
| `focus_iterm_window_by_pid()` | Focus iTerm window |
| `call_openrouter()` | Legacy OpenRouter API call |

## API Endpoints

### New Architecture Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main Kanban dashboard |
| `/api/agents` | GET | List all agents |
| `/api/agents/<id>` | GET | Get agent by ID |
| `/api/agents/<id>/task` | GET | Get agent's current task |
| `/api/agents/<id>/task/transition` | POST | Trigger task state transition |
| `/api/tasks` | GET | List all tasks |
| `/api/tasks/<id>` | GET | Get task by ID |
| `/api/events` | GET | SSE event stream |
| `/api/config` | GET/POST | Read/write configuration |
| `/api/priorities` | GET | Get AI-ranked agent priorities |

### Claude Code Hook Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/hook/session-start` | POST | Claude Code session started |
| `/hook/session-end` | POST | Claude Code session ended |
| `/hook/stop` | POST | Claude finished turn (primary completion signal) |
| `/hook/notification` | POST | Claude Code notification |
| `/hook/user-prompt-submit` | POST | User submitted prompt |
| `/hook/status` | GET | Hook receiver status and activity |

### Legacy Routes (still supported)

| Route | Method | Description |
|-------|--------|-------------|
| `/api/sessions` | GET | JSON list of sessions (maps to agents) |
| `/api/focus/<pid>` | POST | Focus window by PID (deprecated) |
| `/api/focus/session/<name>` | POST | Focus window by session name |
| `/api/send/<session_id>` | POST | Send text to session |
| `/api/output/<session_id>` | GET | Capture session output |
| `/api/notifications` | GET/POST | Notification enable/disable |
| `/api/notifications/test` | POST | Send test notification |
| `/api/headspace` | GET/POST | Get/set current headspace |
| `/api/headspace/history` | GET | Get headspace history |

## Notes for AI Assistants

### New Architecture (src/)

- **Service injection:** All services are injected via Flask's `app.extensions`
- **Pydantic models:** Use `model_dump(mode="json")` for serialization
- **5-state model:** Tasks use commanded/processing/awaiting_input/complete/idle
- **Single source of truth:** AgentStore persists to `data/agents.json` and `data/tasks.json`
- **Tests:** 450+ tests in `tests/` directory, run with `pytest`
- **Coverage:** 70%+ enforced

### Legacy Architecture (lib/)

- **Single-file application:** All code is in `monitor.py` including HTML/CSS/JS template
- **3-state model:** processing/input_needed/idle
- **State files:** Created by `claude-monitor start` wrapper
- **iTerm focus:** Uses AppleScript for window management

### Common to Both

- **macOS-only:** AppleScript/terminal-notifier requires macOS
- **API Keys:** OpenRouter API key should be in `.env` file, not config.yaml
- **Port:** Flask runs on port 5050 (not default 5000)

### Notifications

Notifications require `terminal-notifier` installed via Homebrew:
```bash
brew install terminal-notifier
```

Notifications can be enabled/disabled via:
- **API:** `POST /api/notifications` with `{"enabled": true/false}`
- **Dashboard:** Toggle in settings panel

### Development Tips

- **Run tests often:** `pytest` runs 450+ tests, `pytest --cov=src` for coverage
- **Use run.py:** Recommended entry point for the new architecture
- **Debug mode:** Set `debug: true` in config.yaml for Flask debug mode
- **Service injection:** Access services via `app.extensions["service_name"]`
- **State transitions:** Use `TaskStateMachine.transition()` for state changes
- The HTML template uses vanilla JS with no external dependencies

### Testing

```bash
pytest                           # Run all tests
pytest --cov=src                 # With coverage report
pytest tests/services/           # Run specific test directory
pytest -k "test_agent"           # Run tests matching pattern
```

### AppleScript (Legacy)

Test AppleScript commands manually before modifying:
```bash
osascript -e 'tell application "iTerm" to get name of windows'
```

If permissions errors occur, check System Preferences → Privacy & Security → Automation.

### Auto-Restart Server

When making changes that require a server restart, **use the restart script**:
```bash
./restart_server.sh
```

The script handles everything: kills old process, activates venv, starts new one, verifies it's running.

## PRD Orchestration System

This project includes a PRD-driven development orchestration system for managing feature development through a structured pipeline.

### Orchestration Overview

The system uses Ruby scripts (`orch/`) with Claude Code commands (`.claude/commands/otl/`) to automate:

1. **PRD Workshop** - Create and validate PRDs
2. **Queue Management** - Batch processing of multiple PRDs
3. **Proposal Generation** - Create OpenSpec change proposals from PRDs
4. **Build Phase** - Implement changes with AI assistance
5. **Test Phase** - Run pytest with auto-retry (Ralph loop)
6. **Validation** - Verify implementation matches spec
7. **Finalize** - Commit, create PR, and merge

### Git Workflow

```
development (base) → feature/change-name → PR → development
```

- Feature branches are created FROM `development`
- PRs target `development` branch
- `main` is the stable/release branch

### Key Commands

```bash
# PRD Management
/10: prd-workshop      # Create/remediate PRDs
/20: prd-list          # List pending PRDs
/30: prd-validate      # Quality gate validation

# Orchestration (from development branch)
/10: queue-add         # Add PRDs to queue
/20: prd-orchestrate   # Start queue processing

# Ruby CLI (direct access)
ruby orch/orchestrator.rb status      # Show current state
ruby orch/orchestrator.rb queue list  # List queue items
ruby orch/prd_validator.rb list-all   # List PRDs with validation status
```

### Orchestration Directories

```
orch/
├── orchestrator.rb      # Main orchestration dispatcher
├── state_manager.rb     # State persistence
├── queue_manager.rb     # Queue operations
├── prd_validator.rb     # PRD validation
├── config.yaml          # Orchestration config
├── commands/            # Ruby command implementations
├── working/             # State/queue files (gitignored)
└── log/                 # Log files (gitignored)

.claude/commands/otl/
├── prds/                # PRD management commands
└── orch/                # Orchestration commands
```

### PRD Location

PRDs are stored in `docs/prds/{subsystem}/`:

```
docs/prds/
├── dashboard/
│   ├── voice-bridge-prd.md
│   └── done/            # Completed PRDs
└── notifications/
    └── slack-integration-prd.md
```

### Running the Orchestration

1. Create a PRD in `docs/prds/{subsystem}/`
2. Run `/10: prd-workshop` to validate
3. Switch to `development` branch
4. Run `/10: queue-add` to add to queue
5. Run `/20: prd-orchestrate` to start processing

See `.claude/commands/otl/README.md` for detailed documentation.
