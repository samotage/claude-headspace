# CLAUDE.md - Claude Headspace Project Guide

## Project Overview

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors terminal sessions and displays real-time session status with click-to-focus functionality and native macOS notifications.

**Purpose:**

- Track active Claude Code agents across projects
- Display agent status
- Click-to-focus: bring iTerm2 windows to foreground from the dashboard
- Native macOS notifications when input is needed or tasks complete
- Real-time updates via Server-Sent Events (SSE)

## Architecture

- TBD

## Tech Stack

- **Python:** 3.10+
- **Framework:** Flask with blueprints
- **Config:** PyYAML with migration
- **Terminal:** iTerm2
- **Notifications:** terminal-notifier
- **LLM:** OpenRouter API

## Common Commands

## Directory Structure

```
claude_headspace/
├── .env                 # Environment variables (gitignored)
├── .env.example         # Environment template
├── requirements.txt     # Python dependencies
├── bin/
│   └── claude-headspace # Session wrapper script
├── orch/                # PRD orchestration
├── docs/                # Documentation
├── .claude/             # Claude Code settings
├── CLAUDE.md            # This file
└── README.md            # User documentation
```

## Configuration

Edit `config.yaml` to configure monitored projects:

## Terminal Backend Integration

Terminal backends enable bidirectional control of Claude Code sessions:

- **Send text/commands** to sessions via the API
- **Capture full output** watch/tail output from the claude code master jsonl files
- Enable **voice bridge** and **remote control** features

### Available Backends

### Configuration

Set the default backend in `config.yaml`:

Or use command-line flags:

````bash
claude-monitor start             # Use configured for iTerm2


### Session Control API for Claude Code Hooks

Send text to a session:
```bash
curl -X POST http://localhost:5050/api/send/<session_id> \
  -H "Content-Type: application/json" \
  -d '{"text": "Hello, Claude!", "enter": true}'
````

Capture session output:

```bash
curl http://localhost:5050/api/output/<session_id>?lines=100
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

**Important:** Hook commands must use absolute paths (e.g., `/Users/yourname/.claude/hooks/...`).

See `docs/architecture/claude-code-hooks.md` for detailed documentation.

### Legacy Architecture (lib/)

2. **PID/TTY Matching:** Match process to terminal session
3. **3-State Model:** processing/input_needed/idle
4. **iTerm2:** AppleScript-based focus

## Key Services (New Architecture)

- TBD

### Key Methods

- TBD

### Legacy Functions (lib/)

- TBD

## API Endpoints

- TBD

### New Architecture Routes

- TBD

### Claude Code Hook Routes

| Route                      | Method | Description                                      |
| -------------------------- | ------ | ------------------------------------------------ |
| `/hook/session-start`      | POST   | Claude Code session started                      |
| `/hook/session-end`        | POST   | Claude Code session ended                        |
| `/hook/stop`               | POST   | Claude finished turn (primary completion signal) |
| `/hook/notification`       | POST   | Claude Code notification                         |
| `/hook/user-prompt-submit` | POST   | User submitted prompt                            |
| `/hook/status`             | GET    | Hook receiver status and activity                |

## Notes for AI Assistants

### Notifications

Notifications require `terminal-notifier` installed via Homebrew:

```bash
brew install terminal-notifier
```

Notifications can be enabled/disabled via:

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
