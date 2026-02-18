# Claude Headspace v3.1: Overarching Roadmap

**Project:** Claude Headspace v3.1  
**Author:** PM Agent (John)  
**Status:** Roadmap — Epic Planning Baseline  
**Date:** 2026-01-28

---

## Executive Summary

This document defines the **complete implementation roadmap** for Claude Headspace v3.1 across 4 epics. It serves as the baseline for epic sequencing, dependency management, and PRD generation for the orchestration engine.

**Project Goal:** Build a Kanban-style web dashboard for tracking Claude Code sessions across multiple projects, with real-time state monitoring, iTerm2 integration, macOS notifications, and LLM-powered summarisation and prioritisation.

**Differentiation:**

- **Event-driven architecture** from day one (not polling-first)
- **5-state command model** (idle → commanded → processing → awaiting_input/complete)
- **Dual event sources with hybrid mode:** Claude Code hooks (instant, confidence=1.0) + terminal polling (fallback, adaptive interval)
- **Turn-level granularity:** Track every user/agent exchange, not just command-level
- **Brain reboot system:** Git-based project summaries for context restoration
- **Cross-project prioritisation:** AI-driven priority scoring aligned to global objective

**Reference:** See `docs/architecture/claude-code-hooks.md` for detailed hooks architecture.

**Success Criteria:**

- Launch 2-3 iTerm2 sessions, issue commands, watch dashboard reflect states in real-time
- Click agent cards to focus iTerm windows
- Receive macOS notifications when commands complete or need input
- Set objectives, see AI-prioritised agent recommendations
- Generate brain_reboot artifacts from git history

---

## Epic Breakdown

| Epic       | Name                                 | Sprints | Duration    | Goal                                                                                      |
| ---------- | ------------------------------------ | ------- | ----------- | ----------------------------------------------------------------------------------------- |
| **Epic 1** | Core Foundation + Event-Driven Hooks | 11      | 11-13 weeks | Event-driven architecture, state machine, dashboard, hooks integration                    |
| **Epic 2** | UI Polish & Documentation            | 4       | 3-4 weeks   | Config UI, waypoint editing, help system, macOS notifications                             |
| **Epic 3** | Intelligence Layer                   | 5       | 5-7 weeks   | Turn/command summarisation, priority scoring, git-based summaries, brain reboot              |
| **Epic 4** | Data Management & Wellness           | 4       | 3-4 weeks   | Artifact archiving, project controls, activity monitoring, headspace/frustration tracking |

**Total:** 24 sprints, ~22-28 weeks

---

## Epic 1: Core Foundation + Event-Driven Hooks

**Goal:** Establish the foundational event-driven architecture and prove the Command/Turn state machine works with a functional dashboard. Integrate Claude Code hooks for instant, high-confidence state updates.

**Duration:** 11-13 weeks  
**Sprints:** 11  
**Priority:** P0 (blocking all other epics)

### Key Features

- Python/Flask application with Postgres database
- Event-driven architecture (Claude Code jsonl + hooks)
- 5-state command model with turn-level tracking
- Dashboard with Kanban layout, real-time SSE updates
- Objective setting and history tracking
- Event log viewing with filtering
- Launcher script for monitored Claude Code sessions
- AppleScript integration for iTerm2 focus
- **Claude Code hooks integration** for instant state updates

### Acceptance Test

Launch 2-3 iTerm2 sessions with Claude Code, issue commands in each:

- ✅ Dashboard reflects correct Command/Turn states in real-time
- ✅ Agent cards clickable, focus correct iTerm window
- ✅ Hook events update agent state instantly (<100ms)
- ✅ Terminal polling provides fallback when hooks unavailable

### Deliverables

- Flask application with Postgres
- Domain models: Objective, Project, Agent, Command, Turn, Event
- File watcher for `~/.claude/projects/` jsonl files
- Hook receiver endpoints for Claude Code lifecycle events
- Command state machine with turn intent mapping
- SSE endpoint with HTMX frontend
- Dashboard UI with Tailwind CSS
- Objective tab for setting current headspace
- Logging tab for event filtering
- Launcher script (`claude-headspace start`)
- AppleScript iTerm2 focus integration

### Dependencies

- None (foundational epic)

### Out of Scope (Future Epics)

- LLM-based summarisation/prioritisation
- Brain reboot/waypoint/progress_summary generation
- Config UI tab
- Help/documentation system
- macOS system notifications

---

## Epic 2: UI Polish & Documentation

**Goal:** Polish the user experience with configuration UI, waypoint editing, help system, and native macOS notifications.

**Duration:** 3-4 weeks  
**Sprints:** 4  
**Priority:** P1 (enhances usability, not blocking core features)

### Key Features

- Config UI tab for editing settings
- Waypoint editing UI (per project)
- Help/documentation system (searchable)
- macOS system notifications (command complete, input needed)

### Acceptance Test

- ✅ Edit config.yaml via web UI, changes persist
- ✅ Edit waypoint.md via web UI for each project
- ✅ Search help documentation, find relevant topics
- ✅ Receive macOS notification banner when command completes

### Deliverables

- Config tab with form for editing config.yaml
- Waypoint editor (Markdown editing, per project)
- Help system with search (markdown-based docs)
- macOS notification integration (terminal-notifier or NSUserNotification)
- Notification preferences (enable/disable per event type)

### Dependencies

- **Epic 1 complete** (dashboard, projects, agents exist)

---

## Epic 3: Intelligence Layer

**Goal:** Add LLM-powered summarisation and prioritisation at turn, task, and project levels. Generate brain_reboot artifacts from git history.

**Duration:** 5-7 weeks  
**Sprints:** 5  
**Priority:** P1 (adds intelligence, not blocking core functionality)

### Key Features

- Turn-level summarisation (Haiku) for dashboard display
- Command-level summarisation (Haiku) on completion
- AI-driven cross-project priority scoring (Sonnet)
- Project-level progress_summary generation from git (Sonnet)
- Brain reboot generation (progress_summary + waypoint)

### Acceptance Test

- ✅ Agent turns show AI-generated summaries in dashboard
- ✅ Completed tasks have AI summaries
- ✅ Dashboard shows AI-ranked priority scores per agent
- ✅ Project progress_summary generated from git commits
- ✅ Brain reboot combines progress_summary + waypoint for context restoration

### Deliverables

- OpenRouter API integration
- Inference service with model selection (Haiku, Sonnet)
- Turn summarisation service
- Command summarisation service
- Priority scoring service (cross-project ranking)
- Git analyzer service (commit history → progress narrative)
- Progress summary generator
- Brain reboot generator
- InferenceCall logging (track API usage, input/output)

### Dependencies

- **Epic 1 complete** (Command/Turn models, git integration)

---

## Epic 4: Data Management & Wellness

**Goal:** Add data lifecycle management, project controls, activity monitoring, and developer wellness tracking (headspace/frustration monitoring).

**Duration:** 3-4 weeks  
**Sprints:** 4  
**Priority:** P2 (polish, scaling, and wellness — not blocking MVP)

### Key Features

- **Artifact archiving:** Waypoint, brain_reboot, and progress_summary archived when new versions created
- **Project controls:** Pause/resume inference calls per project (cost/noise control)
- **Activity monitoring:** Turn metrics (rate, avg time), rollups to project/overall, time-series visualization
- **Headspace monitoring:** Frustration tracking, flow state detection, traffic light indicator, gentle playful alerts

### Acceptance Test

- ✅ Create new waypoint → previous version archived with timestamp
- ✅ Create new progress_summary → previous version archived
- ✅ Pause project → inference calls stop, other activity continues
- ✅ Activity metrics show turn rate/avg time per agent, project, overall
- ✅ Frustration indicator (traffic light) visible at top of dashboard
- ✅ High frustration triggers gentle alert ("Think of your cortisol")
- ✅ Flow state detected and displayed ("You've been in the zone for 45 minutes")

### Deliverables

- **Archive System (E4-S1):**
  - Archive waypoint.md when new version created
  - Archive brain_reboot.md when new version created
  - Archive progress_summary.md when new version created
  - Timestamped archive files in `archive/` subdirectory

- **Project Controls (E4-S2):**
  - Pause/resume inference toggle per project
  - Project settings UI
  - Pause state persisted to database

- **Activity Monitoring (E4-S3):**
  - Turn rate per agent (turns/hour)
  - Average turn time per agent
  - Rollups to project level and overall level
  - Time-series data for productivity patterns
  - Monitoring/metrics API endpoint

- **Headspace Monitoring (E4-S4):**
  - Frustration score extraction (enhance turn summarisation inference)
  - Rolling frustration average (last 10 turns, last 30 minutes)
  - Traffic light indicator (green/yellow/red) at top of dashboard
  - Threshold detection (absolute, sustained, rising trend, time-based)
  - Gentle playful alerts ("Who owns this, you or the robots?")
  - Flow state detection (high throughput + low frustration)
  - Positive signals ("You've been in the zone for 45 minutes")
  - Configurable on/off in settings

### Dependencies

- **Epic 3 complete** (turn summarisation, progress summaries exist)

---

## Epic Dependencies & Sequencing

```
Epic 1 (Foundation)
   │
   ├──▶ Epic 2 (UI Polish) ─────────────┐
   │                                    │
   └──▶ Epic 3 (Intelligence) ──────────┤
                   │                    │
                   └──▶ Epic 4 (Data Mgmt)
```

**Critical Path:** Epic 1 → Epic 3 → Epic 4  
**Parallel Track:** Epic 2 can run in parallel with Epic 3

**Rationale:**

- Epic 2 (UI) is mostly independent of Epic 3 (Intelligence)
- Epic 4 depends on Epic 3 because it archives intelligence artifacts
- Epic 1 blocks everything (foundational)

---

## Sprint Count by Epic

| Epic      | Core Sprints | Optional/Parallel | Total  |
| --------- | ------------ | ----------------- | ------ |
| Epic 1    | 10 (S1-S10)  | 1 (S11 hooks)     | 11     |
| Epic 2    | 4            | 0                 | 4      |
| Epic 3    | 5            | 0                 | 5      |
| Epic 4    | 4            | 0                 | 4      |
| **Total** | **23**       | **1**             | **24** |

---

## Technical Foundation Decisions

### Tech Stack

| Component         | Choice       | Notes                       |
| ----------------- | ------------ | --------------------------- |
| Language          | Python 3.10+ | Fresh start, no v2 code     |
| Web Framework     | Flask        | Lightweight, proven         |
| Database          | Postgres     | Local install, not Docker   |
| CSS               | Tailwind     | Model knows it well         |
| Interactivity     | HTMX         | Proven for SSE              |
| Real-time         | SSE          | Server-Sent Events          |
| File Watching     | watchdog     | Watch `~/.claude/projects/` |
| macOS Integration | AppleScript  | iTerm focus, notifications  |
| Config            | YAML         | `config.yaml` file          |
| LLM               | OpenRouter   | Multi-model access          |

### Architecture Principles

**1. Event-Driven Design**

Logs are events. Events drive the application.

```
Claude Code jsonl + hooks
        │
        ▼
    [Event]
        │
        ├──▶ Writes to Postgres (event log)
        ├──▶ Updates Command state
        ├──▶ Updates Turn records
        ├──▶ Triggers SSE push to UI
        └──▶ Triggers notifications (Epic 2)
```

**2. Data Storage Separation**

```
Application Domain (Postgres)          LLM Domain (text files)
──────────────────────────────        ─────────────────────────
Event log                              config.yaml
Command records                           waypoint.md (in target project)
Turn records                           progress_summary.md (in target project)
Objective + history                    brain_reboot outputs
Agent/Session state
InferenceCall logs
```

**3. Auto-Discovery**

Minimal configuration. Discover everything from filesystem:

```
~/.claude/projects/
├── -Users-samotage-dev-otagelabs-claude-headspace/
│   └── {session-uuid}.jsonl
├── -Users-samotage-dev-otagelabs-raglue/
│   └── {session-uuid}.jsonl
└── ...
```

- Folder name = project path (dashes replace slashes)
- jsonl files = session logs (one per Claude Code session)
- Project metadata derived from git

**4. Dual Event Sources with Hybrid Mode**

- **Primary:** Claude Code hooks (instant, confidence=1.0, <100ms latency)
- **Secondary:** Terminal polling via jsonl files (fallback, confidence=0.3-0.9)
- **Hybrid Mode:**
  - Hooks active → 60-second polling (reconciliation only)
  - Hooks silent >300s → 2-second polling (full monitoring)
  - Hooks resume → back to 60-second polling

**Session Correlation:**

- Claude `$CLAUDE_SESSION_ID` ≠ terminal pane ID
- Match sessions via working directory (`$CLAUDE_WORKING_DIRECTORY`)
- Cache correlations for performance

**Hook Events:**

- `SessionStart` → Create agent, IDLE
- `UserPromptSubmit` → IDLE → PROCESSING
- `Stop` → PROCESSING → IDLE (primary completion signal)
- `Notification` → Timestamp update only
- `SessionEnd` → Mark agent inactive

**5. State Machine First**

5-state command model drives all behavior:

```
idle → commanded → processing → awaiting_input/complete → idle
```

Turn intents trigger state transitions (from hooks or polling).

---

## Claude Code Hooks Architecture (Epic 1, Sprint 11)

### Overview

Claude Code supports lifecycle hooks that fire on significant events, enabling instant state detection with 100% confidence (vs polling with 0-2s latency and 30-90% inference confidence).

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

### Hook Events and State Mapping

| Hook Event         | When It Fires               | State Transition       | Confidence |
| ------------------ | --------------------------- | ---------------------- | ---------- |
| `SessionStart`     | Claude Code session begins  | Create agent, set IDLE | 1.0        |
| `UserPromptSubmit` | User sends a message        | IDLE → PROCESSING      | 1.0        |
| `Stop`             | Agent turn completes        | PROCESSING → IDLE      | 1.0        |
| `Notification`     | Various (idle_prompt, etc.) | Timestamp update only  | -          |
| `SessionEnd`       | Session closes              | Mark agent inactive    | 1.0        |

### Hybrid Mode

The implementation uses a hybrid approach for reliability:

1. **Events are primary** - Process hook events immediately with confidence 1.0
2. **Polling is secondary** - Reduced to once every 60 seconds for reconciliation
3. **Fallback mechanism** - If hooks go silent >300s, revert to 2-second polling
4. **Safety net** - Polling catches any missed transitions

**Polling Interval Logic:**

- Hooks active: 60 seconds (reconciliation only)
- Hooks silent >300s: 2 seconds (full monitoring)
- Hooks resume: back to 60 seconds

### Session Correlation

Claude `$CLAUDE_SESSION_ID` differs from terminal pane ID. Correlation uses working directory matching:

```python
def correlate_session(claude_session_id, cwd):
    # 1. Check cache
    if claude_session_id in cache:
        return cache[claude_session_id]

    # 2. Match by working directory
    for agent in agents:
        if agent.cwd == cwd:
            cache[claude_session_id] = agent
            return agent

    # 3. Create new agent
    agent = create_agent(cwd=cwd)
    cache[claude_session_id] = agent
    return agent
```

### Components

**1. HookReceiver Service** (`src/services/hook_receiver.py`):

- Process incoming hook events
- Correlate Claude session IDs to agents
- Apply state transitions with confidence=1.0
- Emit SSE events for real-time dashboard updates

**2. Hook Notification Script** (`bin/notify-headspace.sh`):

- Bash script that POSTs to hook endpoints
- Uses Claude env vars: `$CLAUDE_SESSION_ID`, `$CLAUDE_WORKING_DIRECTORY`
- Timeout: 1s connect, 2s max time
- Silent failures (exit 0 always, don't block Claude Code)

**3. Installation Script** (`bin/install-hooks.sh`):

- Copies `notify-headspace.sh` to `~/.claude/hooks/`
- Merges hook configuration into `~/.claude/settings.json`
- Sets executable permissions
- Validates absolute paths (not ~ or $HOME)

**4. Claude Code Settings Template** (`docs/claude-code-hooks-settings.json`):

- JSON configuration for all 5 hook events
- Absolute paths required
- Merged into user's `~/.claude/settings.json`

### Benefits vs Polling

| Aspect                 | Polling                  | Hooks                 |
| ---------------------- | ------------------------ | --------------------- |
| **Latency**            | 0-2 seconds              | <100ms                |
| **Confidence**         | 30-90% (inference)       | 100% (event-based)    |
| **Resource Usage**     | High (constant scraping) | Low (event-driven)    |
| **Missed Transitions** | Possible (between polls) | Never                 |
| **Setup Required**     | None                     | One-time installation |

### User Setup

1. Run installation script: `./bin/install-hooks.sh`
2. Or manually:
   - Copy `bin/notify-headspace.sh` to `~/.claude/hooks/`
   - Make executable: `chmod +x ~/.claude/hooks/notify-headspace.sh`
   - Merge `docs/claude-code-hooks-settings.json` into `~/.claude/settings.json`

**Important:** Use absolute paths (not ~ or $HOME) in `settings.json`.

### Verification

- Start Claude Code → `session-start` event received
- Send prompt → `user-prompt-submit` event received
- Wait for response → `stop` event received
- Exit Claude → `session-end` event received
- Dashboard shows "Hooks: enabled" badge
- State transitions <100ms latency

---

## Risks & Mitigation

### Risk 1: Postgres Setup Complexity

**Risk:** Users may not have Postgres installed or configured correctly.

**Impact:** Medium (blocks Epic 1 start)

**Mitigation:**

- Provide clear setup instructions in README
- Consider SQLite fallback for simpler local development
- Docker Compose option for one-command setup

---

### Risk 2: Claude Code Hook Adoption

**Risk:** Users may not install hooks, breaking instant event detection.

**Impact:** Medium (degrades to polling-only mode)

**Mitigation:**

- Make hooks optional with graceful degradation
- Polling fallback works without hooks
- Provide clear installation instructions and benefits

---

### Risk 3: iTerm2 AppleScript Permissions

**Risk:** macOS privacy controls may block AppleScript automation.

**Impact:** Medium (breaks click-to-focus)

**Mitigation:**

- Clear permission instructions in setup docs
- Detect permission failures and show actionable error
- Provide manual focus fallback (show session path)

---

### Risk 4: OpenRouter API Costs

**Risk:** High inference volume (turn-level summarisation) may be expensive.

**Impact:** Medium (affects Epic 3 adoption)

**Mitigation:**

- Use fast/cheap models (Haiku) for turn/command summaries
- Use Sonnet only for project/objective-level inference
- Add inference call throttling (max calls per hour)
- Make summarisation optional (enable/disable per project)

---

### Risk 5: Epic 1 Scope Creep

**Risk:** Epic 1 has 11 sprints; temptation to add "just one more feature."

**Impact:** High (delays entire roadmap)

**Mitigation:**

- Strictly enforce Epic 1 scope (see "Out of Scope" section)
- Defer all LLM features to Epic 3
- Defer all UI polish to Epic 2
- Use PRD-driven process to maintain discipline

---

## Success Metrics

### Epic 1 Success Metrics

- ✅ Application starts and connects to Postgres
- ✅ Auto-discovers projects from `~/.claude/projects/`
- ✅ Watches jsonl files, logs events to database
- ✅ Command/Turn state machine works correctly
- ✅ Dashboard shows real-time updates via SSE
- ✅ Click agent card → iTerm window focuses
- ✅ Hook events trigger instant state updates
- ✅ Can set objective and view history

### Epic 2 Success Metrics

- ✅ Edit config via web UI
- ✅ Edit waypoint per project
- ✅ Search help documentation
- ✅ Receive macOS notifications

### Epic 3 Success Metrics

- ✅ Turns show AI summaries in dashboard
- ✅ Commands have completion summaries
- ✅ Cross-project priority scores displayed
- ✅ Progress summaries generated from git
- ✅ Brain reboot available for stale projects

### Epic 4 Success Metrics

- ✅ Artifact archiving works (waypoint, brain_reboot, progress_summary)
- ✅ Pause/resume inference per project works
- ✅ Activity metrics displayed (turn rate, avg time, rollups)
- ✅ Frustration traffic light visible and responsive
- ✅ Gentle alerts trigger on elevated frustration
- ✅ Flow state detected and celebrated
- ✅ Time-series productivity patterns viewable

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in this order to maintain logical dependencies:

### Phase 1: Epic 1 Foundation (Weeks 1-6)

1. Sprint 1: Project Bootstrap
2. Sprint 2: Domain Models & Database Schema
3. Sprint 3: File Watcher & Event System
4. Sprint 4: Command/Turn State Machine
5. Sprint 5: SSE & Real-time Updates
6. Sprint 6: Dashboard UI

**Checkpoint:** Core event system and UI functional

---

### Phase 2: Epic 1 Features (Weeks 7-11)

7. Sprint 7: Objective Tab
8. Sprint 8: Logging Tab
9. Sprint 9: Launcher Script
10. Sprint 10: AppleScript Integration
11. Sprint 11: Claude Code Hooks Integration

**Checkpoint:** Epic 1 acceptance test passes

---

### Phase 3: Epic 2 Polish (Weeks 12-15)

12. Sprint 12: Config UI Tab
13. Sprint 13: Waypoint Editing UI
14. Sprint 14: Help/Documentation System
15. Sprint 15: macOS Notifications

**Checkpoint:** UI polished, notifications working

---

### Phase 4: Epic 3 Intelligence (Weeks 16-22)

16. Sprint 16: OpenRouter Integration & Inference Service
17. Sprint 17: Turn/Command Summarisation
18. Sprint 18: Priority Scoring Service
19. Sprint 19: Git Analyzer & Progress Summary Generation
20. Sprint 20: Brain Reboot Generation

**Checkpoint:** AI features working, brain reboot available

---

### Phase 5: Epic 4 Data Management & Wellness (Weeks 23-28)

21. Sprint 21: Archive System (waypoint, brain_reboot, progress_summary)
22. Sprint 22: Project Controls (pause/resume inference)
23. Sprint 23: Activity Monitoring (turn metrics, rollups, time-series)
24. Sprint 24: Headspace Monitoring (frustration tracking, flow state, traffic light alerts)

**Checkpoint:** Production-ready, wellness-aware, productivity insights available

---

## Document History

| Version | Date       | Author          | Changes                                                                                                                                  |
| ------- | ---------- | --------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| 1.0     | 2026-01-28 | PM Agent (John) | Initial overarching roadmap for 4 epics                                                                                                  |
| 1.1     | 2026-01-30 | PM Agent (John) | Updated Epic 4: expanded to 4 sprints, added headspace/frustration monitoring, activity metrics, renamed to "Data Management & Wellness" |

---

**End of Overarching Roadmap**
