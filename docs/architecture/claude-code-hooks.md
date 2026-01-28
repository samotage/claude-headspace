# Claude Code Hooks Integration

## Overview

This document describes the integration of Claude Code lifecycle hooks into the Claude Monitor project for real-time turn monitoring.

## Problem Statement

The core monitoring challenge is knowing:
1. When a Claude Code session has **started its turn** (user submitted a prompt)
2. When it has **completed its turn** (Claude finished working)
3. Whether it **requires user response** (blocking progress)

### Current Approach: Polling + Inference

The existing architecture uses a 2-second polling loop:

```
Terminal Output → 2s Poll → Content Capture → Regex/LLM → Inferred State
                           (uncertain, delayed, resource-intensive)
```

**Limitations:**
- 0-2 second latency for state detection
- 30-90% confidence (inference-based)
- Resource-intensive (constant terminal scraping)
- Can miss fast state transitions between polls

### New Approach: Event-Driven Hooks

Claude Code supports lifecycle hooks that fire on significant events:

```
Claude Code → Hook Event → HTTP POST → Direct State Transition
                        (certain, instant, lightweight)
```

**Benefits:**
- <100ms latency
- 100% confidence (event-based, not inferred)
- Minimal resources (only fires on actual events)
- Never misses transitions

## Architecture

### Event Flow

```
┌─────────────────────────────────────────────────────────────┐
│              Claude Code (Terminal Session)                  │
│                                                              │
│  Hooks fire on lifecycle events ──────────────────┐         │
└──────────────────────────────────────────────────┼─────────┘
                                                    │
                                                    ▼
┌─────────────────────────────────────────────────────────────┐
│              Claude Monitor (Flask)                          │
│              http://localhost:5050                           │
│                                                              │
│  POST /hook/session-start      → Agent created, IDLE        │
│  POST /hook/user-prompt-submit → Transition to PROCESSING   │
│  POST /hook/stop               → Transition to IDLE         │
│  POST /hook/notification       → Timestamp update           │
│  POST /hook/session-end        → Agent marked inactive      │
└─────────────────────────────────────────────────────────────┘
```

### Hook Events

| Hook Event | When It Fires | State Transition |
|------------|---------------|------------------|
| `SessionStart` | Claude Code session begins | Create agent, set IDLE |
| `UserPromptSubmit` | User sends a message | IDLE → PROCESSING |
| `Stop` | Agent turn completes | PROCESSING → IDLE |
| `Notification` | Various (idle_prompt, etc.) | Timestamp update only |
| `SessionEnd` | Session closes | Mark agent inactive |

### State Machine Mapping

```
                    ┌─────────────────────────────────────┐
                    │                                     │
                    ▼                                     │
┌─────────┐  SessionStart  ┌─────────┐  UserPromptSubmit  │
│ UNKNOWN │ ─────────────► │  IDLE   │ ─────────────────► │
└─────────┘                └─────────┘                    │
                                ▲                         │
                                │                         │
                              Stop                        │
                                │                         │
                           ┌─────────────┐                │
                           │ PROCESSING  │ ◄──────────────┘
                           └─────────────┘
                                │
                           SessionEnd
                                │
                                ▼
                           ┌─────────┐
                           │  ENDED  │
                           └─────────┘
```

### Hybrid Mode

The implementation uses a hybrid approach for reliability:

1. **Events are primary** - Process hook events immediately with confidence 1.0
2. **Polling is secondary** - Reduced to once every 60 seconds for reconciliation
3. **Fallback mechanism** - If hooks go silent, revert to 2-second polling
4. **Safety net** - Catch any missed transitions

## Implementation Plan

### Phase 1: Foundation (Parallel - No Dependencies)

| Task | Description | Files |
|------|-------------|-------|
| #1 | Create HookReceiver service | `src/services/hook_receiver.py` |
| #3 | Add HookConfig to AppConfig | `src/models/config.py` |
| #4 | Add session correlation to AgentStore | `src/services/agent_store.py` |
| #7 | Create hook notification script | `bin/notify-monitor.sh` |
| #12 | Update CLAUDE.md documentation | `CLAUDE.md` |

### Phase 2: API & Integration (Sequential)

| Task | Blocked By | Description |
|------|------------|-------------|
| #2 | #1 | Create hooks API routes blueprint |
| #5 | #1, #3, #4 | Integrate HookReceiver with GoverningAgent |
| #6 | #1, #2 | Register hooks blueprint in Flask app |
| #8 | #7 | Create Claude Code settings.json template |

### Phase 3: Testing & UI

| Task | Blocked By | Description |
|------|------------|-------------|
| #9 | #2, #5 | Add hook status to dashboard UI |
| #10 | #1 | Write tests for HookReceiver service |
| #11 | #2, #6 | Write tests for hooks API routes |

### Phase 4: Deployment

| Task | Blocked By | Description |
|------|------------|-------------|
| #13 | #7, #8 | Create install-hooks.sh setup script |
| #14 | #6, #9, #13 | End-to-end integration test |

### Dependency Graph

```
Phase 1 (Parallel)          Phase 2              Phase 3           Phase 4
──────────────────          ───────              ───────           ───────

   ┌──────┐
   │ #1   │──────┬──────────► #2 ────┬──────────► #11
   │ Hook │      │                   │
   │Recvr │      └──────────► #6 ────┘
   └──┬───┘                   ▲
      │                       │
      ├──────────────────────►│
      │                       │
   ┌──┴───┐                   │
   │ #3   │──────┐            │
   │Config│      │            │
   └──────┘      ▼            │
              ┌──────┐        │
   ┌──────┐   │ #5   │────────┴───────► #9 ──────┐
   │ #4   │──►│Govern│                           │
   │Store │   │Agent │                           ▼
   └──────┘   └──────┘                        ┌──────┐
                                              │ #14  │
   ┌──────┐                                   │ E2E  │
   │ #7   │──────────► #8 ────────► #13 ─────►│ Test │
   │Script│                                   └──────┘
   └──────┘

   ┌──────┐
   │ #12  │ (Documentation - can run anytime)
   │ Docs │
   └──────┘
```

## Component Details

### 1. HookReceiver Service (`src/services/hook_receiver.py`)

Core service that processes incoming Claude Code hook events.

**Key methods:**
- `process_event(event_type, session_id, cwd, timestamp)` - Main entry point
- `correlate_session(claude_session_id, cwd)` - Match to existing agent
- `map_event_to_state(event_type, current_state)` - State mapping logic

**Event processing logic:**
```python
def process_event(self, event_type: str, session_id: str, cwd: str, timestamp: int):
    # 1. Correlate Claude Code session to agent
    agent = self.correlate_session(session_id, cwd)

    # 2. Map event to state transition
    new_state = self.map_event_to_state(event_type, agent.current_state)

    # 3. Apply transition with confidence=1.0
    if new_state:
        self.governing_agent.apply_state_transition(agent, new_state, confidence=1.0)

    # 4. Emit SSE event
    self.event_bus.emit("hook_event", {...})
```

### 2. API Routes (`src/routes/hooks.py`)

Flask blueprint with endpoints for receiving hook events.

**Endpoints:**
```
POST /hook/session-start
POST /hook/session-end
POST /hook/stop
POST /hook/notification
POST /hook/user-prompt-submit
GET  /hook/status
```

**Request body schema:**
```json
{
  "session_id": "string",
  "event": "string",
  "cwd": "string (optional)",
  "timestamp": "int (unix epoch)"
}
```

**Response:**
```json
{
  "status": "ok",
  "agent_id": "string (if correlated)",
  "state": "string (new state if transitioned)"
}
```

### 3. Configuration (`src/models/config.py`)

```python
class HookConfig(BaseModel):
    enabled: bool = True
    port: int | None = None  # None = use main Flask port
    fallback_polling: bool = True
    polling_interval_with_hooks: int = 60  # seconds
    session_timeout: int = 300  # seconds
```

### 4. Session Correlation

Claude Code's `$CLAUDE_SESSION_ID` differs from WezTerm's pane ID. Correlation uses working directory matching:

```python
def correlate_session(self, claude_session_id: str, cwd: str) -> Agent:
    # 1. Check if we've seen this session before
    if claude_session_id in self._claude_session_map:
        return self._claude_session_map[claude_session_id]

    # 2. Find agent by matching working directory
    for agent in self.agents.values():
        if agent.cwd == cwd:
            self._claude_session_map[claude_session_id] = agent
            return agent

    # 3. Create new agent if no match
    agent = self.create_agent(cwd=cwd)
    self._claude_session_map[claude_session_id] = agent
    return agent
```

## User Setup

### Hook Script (`~/.claude/hooks/notify-monitor.sh`)

```bash
#!/bin/bash

MONITOR_URL="${CLAUDE_MONITOR_URL:-http://localhost:5050}"
EVENT_TYPE="${1:-unknown}"
SESSION_ID="${CLAUDE_SESSION_ID:-unknown}"
CWD="${CLAUDE_WORKING_DIRECTORY:-$(pwd)}"
TIMESTAMP=$(date +%s)

curl -s --connect-timeout 1 --max-time 2 \
  -X POST "${MONITOR_URL}/hook/${EVENT_TYPE}" \
  -H "Content-Type: application/json" \
  -d "{\"session_id\":\"$SESSION_ID\",\"event\":\"$EVENT_TYPE\",\"cwd\":\"$CWD\",\"timestamp\":$TIMESTAMP}" \
  2>/dev/null || true

exit 0
```

### Claude Code Settings (`~/.claude/settings.json`)

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": null,
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/notify-monitor.sh session-start" }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": null,
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/notify-monitor.sh session-end" }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": null,
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/notify-monitor.sh stop" }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": null,
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/notify-monitor.sh notification" }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": null,
        "hooks": [
          { "type": "command", "command": "~/.claude/hooks/notify-monitor.sh user-prompt-submit" }
        ]
      }
    ]
  }
}
```

### Installation

```bash
# From the claude_monitor directory
./bin/install-hooks.sh
```

Or manually:
```bash
mkdir -p ~/.claude/hooks
cp bin/notify-monitor.sh ~/.claude/hooks/
chmod +x ~/.claude/hooks/notify-monitor.sh
# Merge docs/claude-code-hooks-settings.json into ~/.claude/settings.json
```

## Verification

### Checklist

- [ ] `~/.claude/settings.json` contains hook configuration
- [ ] `~/.claude/hooks/notify-monitor.sh` exists and is executable
- [ ] Monitor is running (`python run.py`)
- [ ] Start Claude Code and verify `session-start` event received
- [ ] Send a prompt and verify `user-prompt-submit` event received
- [ ] Wait for response and verify `stop` event received
- [ ] Exit Claude and verify `session-end` event received

### Testing Endpoints

```bash
# Test hook endpoint
curl -X POST http://localhost:5050/hook/session-start \
  -H "Content-Type: application/json" \
  -d '{"session_id": "test-123", "cwd": "/tmp", "timestamp": 1234567890}'

# Check hook status
curl http://localhost:5050/hook/status
```

## Feasibility Assessment

| Aspect | Rating | Notes |
|--------|--------|-------|
| Technical complexity | **Low-Medium** | Existing infrastructure covers 80% |
| Integration risk | **Low** | Additive change, doesn't break existing |
| Reliability improvement | **High** | From inference to certainty |
| Performance improvement | **High** | Eliminate polling overhead |
| User setup burden | **Medium** | One-time global config |
| Maintenance burden | **Low** | Hooks are stable Claude Code API |

## Summary

- **14 total implementation tasks**
- **5 tasks can start immediately** (Phase 1)
- **Core path:** #1 → #2 → #6 → #14 (minimum viable implementation)
- **New files:** 4 (hook_receiver.py, hooks.py, notify-monitor.sh, settings template)
- **Modified files:** 5 (config.py, agent_store.py, governing_agent.py, app.py, CLAUDE.md)

The implementation directly solves the core monitoring problem by providing instant, certain knowledge of Claude Code turn lifecycle events.
