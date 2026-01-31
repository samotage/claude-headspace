# CLAUDE.md - Claude Headspace Project Guide

## Project Overview

Claude Headspace is a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects. It monitors terminal sessions and displays real-time session status with click-to-focus functionality and native macOS notifications.

**Purpose:**

- Track active Claude Code agents across projects
- Display agent status with AI-generated summaries
- Click-to-focus: bring iTerm2 windows to foreground from the dashboard
- Native macOS notifications when input is needed or tasks complete
- Real-time updates via Server-Sent Events (SSE)
- LLM-powered turn/task summarisation and cross-project priority scoring

## Architecture

Flask application factory (`app.py`) with:

- **Event-driven hooks:** Claude Code fires lifecycle hooks → Flask receives and processes state transitions
- **Persistence:** PostgreSQL via Flask-SQLAlchemy with Alembic migrations
- **Real-time broadcasting:** SSE pushes state changes, summaries, and scores to the dashboard
- **Intelligence layer:** OpenRouter inference service powers summarisation and priority scoring
- **File watcher fallback:** Monitors Claude Code `.jsonl` files when hooks are silent

```
┌──────────────────────────────────────────────────────────┐
│           Claude Code (Terminal Sessions)                 │
│   Hooks fire on lifecycle events ──────────┐             │
└────────────────────────────────────────────┼─────────────┘
                                              │
                                              ▼
┌──────────────────────────────────────────────────────────┐
│           Claude Headspace (Flask)                        │
│                                                          │
│  Hook Receiver → Lifecycle Bridge → Task State Machine   │
│                                                          │
│  Inference Service (OpenRouter)                          │
│    ├── Summarisation Service (turn/task summaries)       │
│    └── Priority Scoring Service (agent ranking 0-100)    │
│                                                          │
│  Broadcaster → SSE → Dashboard (real-time updates)       │
│  Event Writer → PostgreSQL (audit trail)                 │
└──────────────────────────────────────────────────────────┘
```

## Tech Stack

- **Python:** 3.10+
- **Framework:** Flask 3.0+ with blueprints
- **Database:** PostgreSQL via Flask-SQLAlchemy 3.1+ and Alembic (Flask-Migrate)
- **Build:** Hatchling (pyproject.toml)
- **Config:** PyYAML
- **LLM:** OpenRouter API (Claude Haiku for turns/tasks, Sonnet for project/objective)
- **Real-time:** Server-Sent Events (SSE)
- **Terminal:** iTerm2 (AppleScript-based focus)
- **Notifications:** terminal-notifier (macOS)
- **Testing:** pytest + factory-boy + pytest-cov

## Common Commands

```bash
python run.py                        # Start the server
./restart_server.sh                  # Restart running server
flask db upgrade                     # Run pending migrations
pytest                               # Run all tests (~960 tests)
pytest --cov=src                     # Tests with coverage report
pip install -e ".[dev]"              # Install with dev dependencies
```

## Directory Structure

```
claude_headspace/
├── run.py                           # Entry point
├── config.yaml                      # Server/DB/OpenRouter config
├── pyproject.toml                   # Build config & dependencies
├── restart_server.sh                # Server restart script
├── src/claude_headspace/
│   ├── app.py                       # Flask app factory
│   ├── config.py                    # Config loading
│   ├── database.py                  # SQLAlchemy init
│   ├── models/                      # Domain models
│   │   ├── agent.py                 # Agent (Claude Code session)
│   │   ├── project.py               # Project (monitored codebase)
│   │   ├── task.py                  # Task (unit of work, 5-state)
│   │   ├── turn.py                  # Turn (user/agent exchange)
│   │   ├── event.py                 # Event (audit trail)
│   │   ├── inference_call.py        # InferenceCall (LLM usage log)
│   │   └── objective.py             # Objective + ObjectiveHistory
│   ├── routes/                      # 15 Flask blueprints
│   │   ├── dashboard.py             # Main dashboard view
│   │   ├── hooks.py                 # Claude Code hook endpoints
│   │   ├── sse.py                   # SSE streaming
│   │   ├── sessions.py              # Session lifecycle
│   │   ├── inference.py             # Inference status/usage
│   │   ├── summarisation.py         # Turn/task summary API
│   │   ├── priority.py              # Priority scoring API
│   │   ├── objective.py             # Global objective CRUD
│   │   ├── waypoint.py              # Waypoint editor
│   │   ├── focus.py                 # iTerm2 focus control
│   │   ├── config.py                # Config viewer
│   │   ├── health.py                # Health check
│   │   ├── help.py                  # Help page
│   │   ├── logging.py               # Log viewer
│   │   └── notifications.py         # Notification settings
│   └── services/                    # Business logic
│       ├── hook_receiver.py         # Processes Claude Code hooks
│       ├── hook_lifecycle_bridge.py  # Hooks → state transitions
│       ├── task_lifecycle.py        # Task state management
│       ├── state_machine.py         # Transition validation
│       ├── inference_service.py     # LLM orchestration
│       ├── openrouter_client.py     # OpenRouter API client
│       ├── inference_cache.py       # Content-based caching
│       ├── inference_rate_limiter.py # Rate limiting
│       ├── summarisation_service.py  # Turn/task summaries
│       ├── priority_scoring.py      # Agent priority scoring
│       ├── broadcaster.py           # SSE distribution
│       ├── event_writer.py          # Async audit logging
│       ├── session_correlator.py    # Session → Agent mapping
│       ├── file_watcher.py          # .jsonl file monitoring
│       ├── intent_detector.py       # Turn intent classification
│       ├── notification_service.py  # macOS notifications
│       └── iterm_focus.py           # AppleScript iTerm2 control
├── tests/
│   ├── conftest.py                  # Root fixtures (app, client)
│   ├── test_app.py                  # App init tests
│   ├── test_database.py             # DB config tests
│   ├── test_models.py               # Model tests
│   ├── services/                    # Service unit tests (~27 files)
│   ├── routes/                      # Route tests (~15 files)
│   ├── integration/                 # Real PostgreSQL tests
│   │   ├── conftest.py              # DB lifecycle fixtures
│   │   ├── factories.py             # Factory Boy factories
│   │   ├── test_persistence_flow.py # End-to-end entity chains
│   │   ├── test_model_constraints.py # DB constraints & cascades
│   │   ├── test_factories.py        # Factory validation
│   │   └── test_*_persistence.py    # Feature persistence tests
│   └── cli/                         # CLI tests
├── migrations/versions/             # Alembic migration scripts
├── templates/                       # Jinja2 templates + partials
├── static/                          # CSS/JS assets
├── bin/                             # Scripts (hooks installer, etc.)
├── docs/                            # Architecture docs, PRDs, guides
├── orch/                            # PRD orchestration (Ruby)
└── .claude/                         # Claude Code settings & commands
```

## Configuration

Edit `config.yaml` to configure the application. Key sections:

```yaml
server:
  host: "0.0.0.0"
  port: 5055
  debug: true

database:
  host: localhost
  port: 5432
  name: claude_headspace
  user: samotage

openrouter:
  # Requires OPENROUTER_API_KEY env var (in .env)
  models:
    turn: "anthropic/claude-3-5-haiku-20241022"
    task: "anthropic/claude-3-5-haiku-20241022"
    project: "anthropic/claude-3-5-sonnet-20241022"
    objective: "anthropic/claude-3-5-sonnet-20241022"
  rate_limits:
    calls_per_minute: 30
    tokens_per_minute: 50000
  cache:
    enabled: true
    ttl_seconds: 300

file_watcher:
  polling_interval: 2           # Seconds (fallback mode)
  reconciliation_interval: 60   # Seconds (hooks-active mode)

hooks:
  enabled: true
```

## Claude Code Hooks (Event-Driven)

The monitor receives lifecycle events directly from Claude Code via hooks:

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
│              http://localhost:5055                           │
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

Ask Claude Code to install the hooks, or run `bin/install-hooks.sh`.

**Important:** Hook commands must use absolute paths (e.g., `/Users/yourname/.claude/hooks/...`).

See `docs/architecture/claude-code-hooks.md` for detailed documentation.

## Key Services

Services are registered in `app.extensions` and can be accessed via `app.extensions["service_name"]`.

### Hook & State Management

- **HookReceiver** (`hook_receiver.py`) — processes Claude Code lifecycle hooks (session-start, stop, user-prompt-submit, etc.), manages debounced AWAITING_INPUT state, in-memory display overrides
- **HookLifecycleBridge** (`hook_lifecycle_bridge.py`) — translates hook events into validated state machine transitions, creates USER/AGENT turns with proper intents
- **TaskLifecycle** (`task_lifecycle.py`) — manages task state transitions, processes turns, triggers async summarisation on completion
- **StateMachine** (`state_machine.py`) — pure stateless validation of `(from_state, actor, intent) → to_state` transitions

### Intelligence Layer

- **InferenceService** (`inference_service.py`) — orchestrates LLM calls via OpenRouter with content-based caching (5-min TTL), rate limiting (30 calls/min, 50k tokens/min), cost tracking, and model selection by level
- **SummarisationService** (`summarisation_service.py`) — generates AI summaries for turns (1-2 sentences) and tasks (2-3 sentences) asynchronously via thread pool
- **PriorityScoringService** (`priority_scoring.py`) — batch scores all active agents 0-100 based on objective/waypoint alignment, agent state, and recency; debounced (5 seconds)

### Infrastructure

- **Broadcaster** (`broadcaster.py`) — SSE event distribution with client filters (event_type, project_id, agent_id), queue-based delivery
- **EventWriter** (`event_writer.py`) — async audit logging to PostgreSQL (session events, state transitions, hook receipts)
- **SessionCorrelator** (`session_correlator.py`) — maps Claude Code sessions to Agent records by session_id, working_directory, or headspace_session_id
- **FileWatcher** (`file_watcher.py`) — monitors Claude Code `.jsonl` files as fallback when hooks are silent

## Data Models

| Model | Purpose | Key Fields |
|-------|---------|------------|
| **Project** | Monitored codebase | name, path, github_repo, current_branch |
| **Agent** | Claude Code session | session_uuid, claude_session_id, priority_score, priority_reason |
| **Task** | Unit of work (5-state lifecycle) | state, summary, started_at, completed_at |
| **Turn** | Individual exchange | actor (USER/AGENT), intent, text, summary |
| **Event** | Audit trail | event_type, payload, timestamps |
| **InferenceCall** | LLM call log | model, tokens, cost, latency, level |
| **Objective** | Global priority context | current_text, constraints |

**Task States:** `IDLE → COMMANDED → PROCESSING → AWAITING_INPUT → COMPLETE`

**Turn Actors:** `USER`, `AGENT`

**Turn Intents:** `COMMAND`, `ANSWER`, `QUESTION`, `COMPLETION`, `PROGRESS`

## API Endpoints

### Dashboard & Real-Time

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Main dashboard view |
| `/sse` | GET | SSE stream (filters: `?types=...&project_id=...&agent_id=...`) |

### Claude Code Hooks

| Route | Method | Description |
|-------|--------|-------------|
| `/hook/session-start` | POST | Claude Code session started |
| `/hook/session-end` | POST | Claude Code session ended |
| `/hook/stop` | POST | Claude finished turn (primary completion signal) |
| `/hook/notification` | POST | Claude Code notification |
| `/hook/user-prompt-submit` | POST | User submitted prompt |
| `/hook/status` | GET | Hook receiver status and activity |

### Intelligence Layer

| Route | Method | Description |
|-------|--------|-------------|
| `/api/inference/status` | GET | Inference service health and config |
| `/api/inference/usage` | GET | Usage statistics and cost breakdown |
| `/api/summarise/turn/<id>` | POST | Generate or retrieve turn summary |
| `/api/summarise/task/<id>` | POST | Generate or retrieve task summary |
| `/api/priority/score` | POST | Trigger batch priority scoring |
| `/api/priority/rankings` | GET | Get current priority rankings |

### Other Endpoints

| Route | Method | Description |
|-------|--------|-------------|
| `/api/sessions/...` | Various | Session lifecycle management |
| `/api/objective/...` | Various | Global objective CRUD |
| `/api/waypoint/...` | Various | Waypoint editor |
| `/api/focus/<agent_id>` | POST | iTerm2 focus control |
| `/api/config` | GET | Configuration viewer |
| `/health` | GET | Health check |

## Notes for AI Assistants

### Notifications

Notifications require `terminal-notifier` installed via Homebrew:

```bash
brew install terminal-notifier
```

Notifications can be enabled/disabled via:

- **Dashboard:** Toggle in settings panel

### Development Tips

- **Run tests often:** `pytest` runs ~960 tests, `pytest --cov=src` for coverage
- **Use run.py:** Recommended entry point — `python run.py`
- **Debug mode:** Set `debug: true` in config.yaml for Flask debug mode
- **Service injection:** Access services via `app.extensions["service_name"]`
- **State transitions:** Use `TaskStateMachine.transition()` for state changes
- **Migrations:** Run `flask db upgrade` after model changes
- **LLM features:** Set `OPENROUTER_API_KEY` in `.env` for inference/summarisation/priority
- The HTML template uses vanilla JS with no external dependencies

### Testing

#### Commands

```bash
pytest                                    # All tests (~960 tests)
pytest --cov=src                          # With coverage report
pytest tests/services/                    # Service unit tests
pytest tests/routes/                      # Route/endpoint tests
pytest tests/integration/                 # Integration tests (real PostgreSQL)
pytest -k "test_state_machine"            # Run tests matching pattern
pytest tests/integration/test_persistence_flow.py  # Specific file
```

#### Test Architecture (3-Tier)

- **Unit tests** (`tests/services/`) — mock dependencies, validate pure service logic in isolation
- **Route tests** (`tests/routes/`) — Flask test client with mocked services, validate HTTP contracts and response codes
- **Integration tests** (`tests/integration/`) — real PostgreSQL database, factory-boy data creation, verify actual persistence and constraints

#### Integration Testing Framework

Real PostgreSQL integration tests with automatic database lifecycle management.

**Prerequisites:**

- PostgreSQL running locally
- Database user with `CREATE DATABASE` privilege
- Dev dependencies installed: `pip install -e ".[dev]"`

**Database lifecycle (automatic):**

1. **Session start:** creates `claude_headspace_test` database (drops first if exists)
2. **Schema creation:** `db.metadata.create_all()` initialises all tables
3. **Per-test isolation:** each test wrapped in a transaction, rolled back after
4. **Session end:** drops the test database

**Test database URL** is resolved in order:

1. `TEST_DATABASE_URL` environment variable (if set)
2. Auto-constructed from `config.yaml` database settings with `_test` suffix

**Factory Boy factories** (`tests/integration/factories.py`):

| Factory | Model | Auto-creates Parent |
|---------|-------|---------------------|
| `ProjectFactory` | Project | — |
| `AgentFactory` | Agent | Project |
| `TaskFactory` | Task | Agent → Project |
| `TurnFactory` | Turn | Task → Agent → Project |
| `EventFactory` | Event | — (refs optional) |
| `ObjectiveFactory` | Objective | — |
| `ObjectiveHistoryFactory` | ObjectiveHistory | Objective |

**Key fixtures** (`tests/integration/conftest.py`):

| Fixture | Scope | Description |
|---------|-------|-------------|
| `test_database_url` | session | Test database connection URL |
| `test_db_engine` | session | Engine that manages create/drop of test DB |
| `TestSessionFactory` | session | `sessionmaker` bound to test engine |
| `db_session` | function | Per-test session with automatic rollback |

**Writing new integration tests:**

```python
import pytest
from sqlalchemy import select
from claude_headspace.models import Project, Agent
from .factories import ProjectFactory, AgentFactory

@pytest.fixture(autouse=True)
def _set_factory_session(db_session):
    ProjectFactory._meta.sqlalchemy_session = db_session
    AgentFactory._meta.sqlalchemy_session = db_session

class TestMyFeature:
    def test_something(self, db_session):
        project = ProjectFactory(name="my-project")
        db_session.flush()

        result = db_session.execute(
            select(Project).where(Project.id == project.id)
        ).scalar_one()
        assert result.name == "my-project"
```

See `docs/testing/integration-testing-guide.md` for the full guide.

#### Test Configuration

From `pyproject.toml`:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_functions = ["test_*"]
addopts = "-v"
```

Dev dependencies: `pip install -e ".[dev]"` (pytest, pytest-cov, factory-boy)

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
