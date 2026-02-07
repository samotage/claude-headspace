# Claude Code Hooks Architecture

## Overview

Claude Headspace uses Claude Code's lifecycle hooks to receive real-time events from terminal sessions. Hooks fire HTTP POST requests to the Flask server, enabling instant state tracking with <100ms latency and 100% accuracy (vs inference from terminal scraping).

## Hook Events

8 lifecycle hooks fire from Claude Code to `http://localhost:5055/hook/*`:

| Hook Event | Endpoint | When It Fires | Effect |
|------------|----------|---------------|--------|
| `SessionStart` | `/hook/session-start` | Claude Code session begins | Create/link agent via SessionCorrelator, set IDLE |
| `SessionEnd` | `/hook/session-end` | Session closes | Complete active task, mark agent ended |
| `Stop` | `/hook/stop` | Agent turn completes | Create AGENT turn, detect intent (COMPLETION/END_OF_TASK/QUESTION), transition state |
| `Notification` | `/hook/notification` | Various (elicitation, permission, idle) | Timestamp update, may trigger AWAITING_INPUT |
| `UserPromptSubmit` | `/hook/user-prompt-submit` | User sends a message | Create task (if needed), USER turn with COMMAND intent, transition IDLE→COMMANDED→PROCESSING |
| `PreToolUse` | `/hook/pre-tool-use` | Before tool execution | For AskUserQuestion/ExitPlanMode: transition PROCESSING→AWAITING_INPUT |
| `PostToolUse` | `/hook/post-tool-use` | After tool execution | Transition AWAITING_INPUT→PROCESSING, update timestamp |
| `PermissionRequest` | `/hook/permission-request` | Permission prompt shown | Transition to AWAITING_INPUT, trigger notification |

## Task State Machine (5-State)

```
                                ┌─────────────────────────────────┐
                                │           user answers           │
                                ▼                                 │
┌──────────┐    user command   ┌───────────┐                      │
│          │ ─────────────────▶│           │                      │
│   IDLE   │                   │ COMMANDED │                      │
│          │◀─┐                │           │                      │
└──────────┘  │                └─────┬─────┘                      │
              │                      │                            │
              │                      │ agent starts processing    │
              │                      ▼                            │
              │                ┌────────────┐                     │
              │                │            │◀────────────────┐   │
              │                │ PROCESSING │                 │   │
              │                │            │─────────┐       │   │
              │                └─────┬──────┘         │       │   │
              │                      │                │       │   │
              │     agent completes  │                │       │   │
              │     or end_of_task   │                │       │   │
              │                      ▼                │       │   │
              │                ┌──────────┐           │       │   │
              │                │          │   agent   │       │   │
              │                │ COMPLETE │   asks    │       │   │
              │                │          │  question │       │   │
              │                └────┬─────┘   (pre-   │       │   │
              │                     │        tool-use)│       │   │
              │                     │                 ▼       │   │
              │  task complete      │          ┌────────────┐ │   │
              └─────────────────────┘          │  AWAITING  │ │   │
                                               │   INPUT    │─┘   │
                                               │            │     │
                                               └──────┬─────┘     │
                                                      │ (post-    │
                                                      │ tool-use) │
                                                      └───────────┘
```

### Valid Transitions

| From State | Actor | Intent | To State |
|------------|-------|--------|----------|
| IDLE | USER | COMMAND | COMMANDED |
| COMMANDED | AGENT | PROGRESS | PROCESSING |
| COMMANDED | AGENT | QUESTION | AWAITING_INPUT |
| COMMANDED | AGENT | COMPLETION | COMPLETE |
| COMMANDED | AGENT | END_OF_TASK | COMPLETE |
| PROCESSING | AGENT | PROGRESS | PROCESSING |
| PROCESSING | AGENT | QUESTION | AWAITING_INPUT |
| PROCESSING | AGENT | COMPLETION | COMPLETE |
| PROCESSING | AGENT | END_OF_TASK | COMPLETE |
| PROCESSING | USER | ANSWER | PROCESSING |
| AWAITING_INPUT | USER | ANSWER | PROCESSING |
| AWAITING_INPUT | AGENT | COMPLETION | COMPLETE |
| AWAITING_INPUT | AGENT | END_OF_TASK | COMPLETE |

The state machine is implemented in `src/claude_headspace/services/state_machine.py` as a pure stateless function: `validate_transition(from_state, actor, intent) -> TransitionResult`.

## AWAITING_INPUT via Pre/Post Tool Use

The `pre-tool-use` and `post-tool-use` hooks enable tracking of PROCESSING↔AWAITING_INPUT cycles:

1. **pre-tool-use** fires before tool execution. When the tool is `AskUserQuestion`, `ExitPlanMode`, or `EnterPlanMode`, the system transitions from PROCESSING → AWAITING_INPUT
2. The user sees the question/permission prompt and responds
3. **post-tool-use** fires after the tool completes, transitioning AWAITING_INPUT → PROCESSING

This provides accurate tracking of when agents are blocked waiting for user input vs actively working.

## Event Flow

```
┌─────────────────────────────────────────────────────────────┐
│              Claude Code (Terminal Session)                   │
│                                                              │
│  Hooks fire on lifecycle events ──────────────────┐         │
└──────────────────────────────────────────────────┼─────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Claude Headspace (Flask)                         │
│              http://localhost:5055                            │
│                                                              │
│  POST /hook/session-start      → Agent created, IDLE         │
│  POST /hook/user-prompt-submit → IDLE → COMMANDED → PROCESSING│
│  POST /hook/pre-tool-use       → PROCESSING → AWAITING_INPUT │
│  POST /hook/post-tool-use      → AWAITING_INPUT → PROCESSING │
│  POST /hook/stop               → Detect intent, transition   │
│  POST /hook/notification       → Timestamp/state update      │
│  POST /hook/permission-request → AWAITING_INPUT + notify     │
│  POST /hook/session-end        → Agent marked ended          │
└─────────────────────────────────────────────────────────────┘
```

## Processing Pipeline

When a hook event arrives, it flows through:

1. **HookReceiver** (`hook_receiver.py`) — receives the HTTP POST, extracts session data
2. **SessionCorrelator** (`session_correlator.py`) — maps the Claude Code session to an Agent record via 5-strategy cascade: memory cache, DB lookup, headspace UUID, working directory, or new agent creation
3. **HookLifecycleBridge** (`hook_lifecycle_bridge.py`) — translates hook events into task lifecycle actions
4. **TaskLifecycleManager** (`task_lifecycle.py`) — manages task creation, turn processing, state transitions
5. **IntentDetector** (`intent_detector.py`) — determines turn intent (COMMAND, QUESTION, COMPLETION, etc.)
6. **StateMachine** (`state_machine.py`) — validates the proposed transition
7. **Broadcaster** (`broadcaster.py`) — pushes SSE events to the dashboard
8. **NotificationService** — sends macOS notifications when agents need input

## Installation

Run `bin/install-hooks.sh` to configure Claude Code hooks. This:

1. Copies `bin/notify-headspace.sh` to `~/.claude/hooks/`
2. Backs up `~/.claude/settings.json` before modification
3. Merges hook configuration into `~/.claude/settings.json` using `jq`

Hook commands use absolute paths (required by Claude Code).

### Verification

```bash
# Test a hook endpoint
curl -X POST http://localhost:5055/hook/session-start \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "cwd": "/tmp", "timestamp": 1234567890}'

# Check hook status
curl http://localhost:5055/hook/status
```

### Uninstall

```bash
bin/install-hooks.sh --uninstall
```
