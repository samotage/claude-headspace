# Claude Headspace v3.1 Roadmap Documentation

**Date:** 2026-01-28  
**Author:** PM Agent (John)

---

## Overview

This directory contains the complete roadmap documentation for Claude Headspace v3.1, structured to drive PRD generation and OpenSpec-based implementation via the orchestration engine.

## Documents

### 1. Overarching Roadmap

**File:** `claude_headspace_v3.1_overarching_roadmap.md`

**Purpose:** High-level epic planning across 4 epics (23 total sprints)

**Contents:**

- Epic goals, dependencies, and sequencing
- Tech stack and architecture decisions
- Claude Code hooks architecture overview
- Risks and mitigation strategies
- Success metrics per epic
- PRD generation order

**Use this for:**

- Understanding the full project scope
- Epic-level planning and dependencies
- Architecture and technical decisions
- Sequencing PRD generation

---

### 2. Epic 1 Detailed Roadmap

**File:** `claude_headspace_v3.1_epic1_detailed_roadmap.md`

**Purpose:** Sprint-by-sprint breakdown of Epic 1 with subsystem-level detail

**Contents:**

- 11 sprints with full specifications
- 13 subsystems requiring OpenSpec PRDs
- Each sprint includes:
  - Goal, duration, dependencies
  - Deliverables (comprehensive list)
  - Technical decisions required
  - Risks & mitigation
  - Acceptance criteria
- Subsystem specs with:
  - OpenSpec IDs
  - File paths
  - Data model changes
  - Dependencies
  - Acceptance tests
- Sprint dependency diagram
- PRD generation order with phasing

**Use this for:**

- Generating detailed PRDs for each sprint
- Understanding subsystem requirements
- Implementation planning
- OpenSpec proposal creation

---

## Roadmap Structure

### Epic Breakdown

| Epic       | Name                                 | Sprints | Duration    | Priority      |
| ---------- | ------------------------------------ | ------- | ----------- | ------------- |
| **Epic 1** | Core Foundation + Event-Driven Hooks | 11      | 11-13 weeks | P0 (blocking) |
| **Epic 2** | UI Polish & Documentation            | 4       | 3-4 weeks   | P1            |
| **Epic 3** | Intelligence Layer                   | 5       | 5-7 weeks   | P1            |
| **Epic 4** | Data Management & Wellness           | 4       | 3-4 weeks   | P2            |
| **Epic 5** | Voice Bridge & Project Enhancement   | 9       | 8-10 weeks  | P1            |
| **Epic 6** | Voice Bridge & Agent Chat            | 3+      | 5-7 weeks+  | P1            |

**Total:** 36+ sprints, ~35-45 weeks (Epic 6 is extensible)

### Critical Path

```
Epic 1 (Foundation) → Epic 3 (Intelligence) → Epic 4 (Data Mgmt) → Epic 5 (Bridge & Projects) → Epic 6 (Voice & Chat)
                   ↘
                    Epic 2 (UI Polish) [parallel with Epic 3]
```

---

## Epic 1 Sprint Overview

| Sprint | Name                            | Duration  | Subsystem                       |
| ------ | ------------------------------- | --------- | ------------------------------- |
| 1      | Project Bootstrap               | 1 week    | flask-bootstrap, database-setup |
| 2      | Domain Models & Database Schema | 1-2 weeks | domain-models                   |
| 3      | File Watcher & Event System     | 1-2 weeks | file-watcher, event-system      |
| 4      | Task/Turn State Machine         | 1 week    | state-machine                   |
| 5      | SSE & Real-time Updates         | 1 week    | sse-system                      |
| 6      | Dashboard UI                    | 2 weeks   | dashboard-ui                    |
| 7      | Objective Tab                   | 1 week    | objective-tab                   |
| 8      | Logging Tab                     | 1 week    | logging-tab                     |
| 9      | Launcher Script                 | 1 week    | launcher-script                 |
| 10     | AppleScript Integration         | 1 week    | applescript-integration         |
| 11     | Claude Code Hooks Integration   | 1-2 weeks | hook-receiver                   |

**Total:** 11 sprints, 11-13 weeks

---

### 6. Epic 6 Detailed Roadmap

**File:** `claude_headspace_v3.1_epic6_detailed_roadmap.md`

**Purpose:** Sprint-by-sprint breakdown of Epic 6 with subsystem-level detail

**Contents:**

- 3 initial sprints (extensible — new sprints appended as scoped)
- 3 subsystems requiring OpenSpec PRDs
- Each sprint includes:
  - Goal, duration, dependencies
  - Deliverables (comprehensive list)
  - Technical decisions
  - UI wireframes
  - Risks & mitigation
  - Acceptance criteria
- Sprint dependency diagram
- Cross-epic dependencies
- Acceptance test cases
- Future sprint candidates
- PRD generation order

**Use this for:**

- Generating detailed PRDs for each sprint
- Understanding voice bridge and chat history requirements
- Implementation planning
- OpenSpec proposal creation

---

## Key Architecture Decisions

### 1. Event-Driven from Day One

Logs are events. Events drive the application.

- All state updates triggered by events (not polling loops)
- Event log provides audit trail
- Enables dual event sources (hooks + polling)

### 2. 5-State Task Model

```
idle → commanded → processing → awaiting_input/complete → idle
```

- More granular than 3-state (idle/working/waiting)
- Aligns with turn intents
- Enables better prioritisation

### 3. Dual Event Sources with Hybrid Mode

**Primary:** Claude Code hooks (instant, confidence=1.0, <100ms latency)
**Secondary:** Terminal polling (fallback, adaptive interval)

**Hybrid Mode:**

- Hooks active: 60-second polling (reconciliation)
- Hooks silent >300s: 2-second polling (full monitoring)
- Hooks resume: back to 60-second polling

**Benefits:**

- Instant updates when hooks installed
- Graceful degradation when hooks unavailable
- Safety net catches missed events

### 4. Session Correlation

Claude `$CLAUDE_SESSION_ID` ≠ terminal pane ID

**Solution:** Match via working directory (`$CLAUDE_WORKING_DIRECTORY`)

### 5. Turn-Level Granularity

Track every user/agent exchange (not just task-level):

- Foundation for Epic 3 turn summarisation
- Enables fine-grained audit trail
- Better understanding of agent behavior

---

## Claude Code Hooks Architecture

**See:** `docs/architecture/claude-code-hooks.md` for full details

### Hook Events

| Hook Event         | When It Fires               | State Transition       | Confidence |
| ------------------ | --------------------------- | ---------------------- | ---------- |
| `SessionStart`     | Claude Code session begins  | Create agent, set IDLE | 1.0        |
| `UserPromptSubmit` | User sends a message        | IDLE → PROCESSING      | 1.0        |
| `Stop`             | Agent turn completes        | PROCESSING → IDLE      | 1.0        |
| `Notification`     | Various (idle_prompt, etc.) | Timestamp update only  | -          |
| `SessionEnd`       | Session closes              | Mark agent inactive    | 1.0        |

### Components

1. **HookReceiver Service** (`src/services/hook_receiver.py`)
2. **Hook API Routes** (`src/routes/hooks.py`)
3. **Hook Script** (`bin/notify-headspace.sh`)
4. **Installation Script** (`bin/install-hooks.sh`)
5. **Settings Template** (`docs/claude-code-hooks-settings.json`)

### User Setup

```bash
# From claude_headspace directory
./bin/install-hooks.sh
```

Or manually:

1. Copy `bin/notify-headspace.sh` to `~/.claude/hooks/`
2. Make executable: `chmod +x ~/.claude/hooks/notify-headspace.sh`
3. Merge `docs/claude-code-hooks-settings.json` into `~/.claude/settings.json`

**Important:** Use absolute paths (not ~ or $HOME) in `settings.json`.

---

## PRD Generation Order

Follow this order for OpenSpec PRD generation:

### Phase 1: Foundation (Weeks 1-2)

1. flask-bootstrap
2. database-setup

### Phase 2: Data Model (Weeks 3-4)

3. domain-models

### Phase 3: Event System (Weeks 5-6)

4. file-watcher
5. event-system

### Phase 4: State Machine (Week 7)

6. state-machine

### Phase 5: Real-time UI (Weeks 8-10)

7. sse-system
8. dashboard-ui

### Phase 6: User Features (Weeks 11-12)

9. objective-tab
10. logging-tab

### Phase 7: Integration (Weeks 13-15)

11. launcher-script
12. applescript-integration
13. hook-receiver

---

## Success Metrics

### Epic 1 Acceptance Test

Launch 2-3 iTerm2 sessions with Claude Code, issue commands in each:

- ✅ Dashboard reflects correct Task/Turn states in real-time
- ✅ Agent cards clickable, focus correct iTerm window
- ✅ Hook events update agent state instantly (<100ms)
- ✅ Terminal polling provides fallback when hooks unavailable
- ✅ Can set objective and view history
- ✅ Event log viewable with filtering

### Key Metrics

| Metric                         | Target            |
| ------------------------------ | ----------------- |
| State update latency (hooks)   | <100ms            |
| State update latency (polling) | <2 seconds        |
| Hook confidence                | 100%              |
| Polling confidence             | 30-90%            |
| Dashboard refresh rate         | Real-time via SSE |
| iTerm focus latency            | <500ms            |
| Session correlation accuracy   | >95%              |

---

## Next Steps

1. **Review roadmaps** — Validate epic/sprint structure and dependencies
2. **Generate Sprint 1 PRD** — Start with flask-bootstrap subsystem
3. **Create OpenSpec proposal** — From Sprint 1 PRD
4. **Execute via orchestration** — Use orchestration engine to build
5. **Iterate** — Continue through remaining 22 sprints

---

## Related Documentation

- **Conceptual Overview:** `docs/conceptual/claude_headspace_v3.1_conceptual_overview.md`
- **Epic 1 Guidance:** `docs/conceptual/claude_headspace_v3.1_epic1_guidance.md`
- **Hooks Architecture:** `docs/architecture/claude-code-hooks.md`
- **Project Guide:** `CLAUDE.md`

---

## Document History

| Version | Date       | Author          | Changes                                              |
| ------- | ---------- | --------------- | ---------------------------------------------------- |
| 1.0     | 2026-01-28 | PM Agent (John) | Initial roadmap documentation with hooks integration |
| 1.1     | 2026-02-11 | PM Agent (John) | Added Epic 5, Epic 6 entries and updated totals      |

---

**End of Roadmap README**
