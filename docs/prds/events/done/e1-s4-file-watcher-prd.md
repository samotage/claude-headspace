---
validation:
  status: valid
  validated_at: '2026-01-29T09:50:59+11:00'
---

# Product Requirements Document (PRD) — File Watcher

**Project:** Claude Headspace v3.1
**Scope:** Epic 1, Sprint 4 — File watcher for registered Claude Code sessions
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace monitors Claude Code sessions to provide real-time visibility into agent activity across projects. The file watcher subsystem is the polling/fallback mechanism that monitors jsonl files for registered sessions, providing turn detection and reconciliation alongside the primary hook-based event system (Sprint 13).

Only sessions explicitly registered via the `claude-headspace start` launcher script (Sprint 11) are monitored. The file watcher finds the appropriate jsonl file in `~/.claude/projects/`, parses it incrementally, and emits events for downstream processing by the Event System (Sprint 5) and State Machine (Sprint 6).

This sprint delivers the core file monitoring capability with Watchdog integration, JSONL parsing, project path decoding, git metadata extraction, and a session registration API. The file watcher operates in a hybrid model where hooks (Sprint 13) are primary and polling is secondary—when hooks are active, polling is reduced to 60-second reconciliation; when hooks are silent, polling resumes at 2-second intervals.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace uses a dual event source architecture:

1. **Claude Code Hooks (Sprint 13)** — Primary event source, instant (<100ms), confidence=1.0
2. **File Watcher Polling (Sprint 4)** — Secondary/fallback, 2-60 second intervals, provides reconciliation

The file watcher monitors `~/.claude/projects/` where Claude Code stores session jsonl files. Each session creates a folder named after the project path (with dashes replacing slashes) containing jsonl files for each session.

Sessions must be explicitly registered via the launcher script to be monitored. Unregistered Claude Code sessions are ignored—this allows users to have Claude Code sessions they don't want tracked.

### 1.2 Target User

Developers using Claude Code across multiple projects who want real-time visibility into registered agent sessions via the Claude Headspace dashboard.

### 1.3 Success Moment

A developer runs `claude-headspace start`, issues commands in Claude Code, and the file watcher detects each turn and emits events that flow through to the dashboard—even when hooks are unavailable.

---

## 2. Scope

### 2.1 In Scope

**Session Registration Mechanism:**
- Internal Python API to register sessions for monitoring
- Accept: session UUID, project path, working directory
- Store registered sessions (in-memory registry)
- Unregister sessions when ended or timed out

**File Monitoring (Registered Sessions Only):**
- Watch only jsonl files for sessions that have been registered
- Locate jsonl files in `~/.claude/projects/` based on working directory
- Start watching when session is registered
- Stop watching when session is unregistered or inactive

**Claude Code JSONL Parsing:**
- Parse Claude Code jsonl file format (one JSON object per line)
- Extract turn data: actor, text, timestamp
- Process only new content since last read (incremental parsing)
- Handle malformed lines gracefully (log and skip)

**Project Path Decoding:**
- Decode project path from folder name (`-Users-foo-bar` → `/Users/foo/bar`)
- Handle special characters in paths (spaces, unicode)

**Git Metadata Extraction:**
- Extract git metadata for registered projects: repository URL, current branch
- Cache git metadata during session lifetime
- Avoid repeated git calls on every event

**Turn Detection:**
- Detect new turns in monitored jsonl files
- Emit events for each new turn detected

**Event Emission:**
- Emit structured events for downstream processing:
  - `turn_detected` — new line parsed from jsonl
  - `session_ended` — session inactive or unregistered
- Events include context: project path, session UUID, turn data, timestamps

**Configuration:**
- Add `claude.projects_path` to config.yaml schema (default: `~/.claude/projects`)
- Configurable polling interval (default: 2 seconds)
- Configurable session inactivity timeout (default: 90 minutes)

**Hybrid Mode Awareness:**
- File watcher is the polling mechanism for the hybrid model
- Expose interface for Sprint 13 (Hooks) to adjust polling interval
- Support variable polling intervals (2s fallback, 60s when hooks active)

### 2.2 Out of Scope

- **Auto-discovery of all Claude Code sessions** — only registered sessions monitored
- **Launcher script implementation** — Sprint 11 implements `claude-headspace start`
- **Hook receiver endpoints** — Sprint 13 handles Claude Code hooks
- **Hybrid mode polling interval control logic** — Sprint 13 controls when to switch intervals
- **State machine logic** — Sprint 6 handles state transitions
- **Event persistence to database** — Sprint 5 writes events to Postgres
- **Intent detection** — Sprint 6 determines turn intent (command/question/etc.)
- **SSE broadcasting** — Sprint 7 pushes updates to browser
- **Agent/Command/Turn record creation** — Sprint 5 event handler creates records

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Register a session via internal API → watcher starts monitoring its jsonl file
2. Append content to monitored jsonl file → `turn_detected` event emitted with correct data
3. Unregister a session → watcher stops monitoring that file
4. Multiple registered sessions → all tracked independently without interference
5. Project path decoded correctly from folder name including edge cases:
   - Standard path: `-Users-samotage-dev-project` → `/Users/samotage/dev/project`
   - Path with spaces: `-Users-samotage-My-Documents-project` → `/Users/samotage/My Documents/project`
6. Git metadata extracted correctly for registered projects (repo URL, branch)
7. Malformed jsonl lines are logged but do not crash the watcher
8. Session inactive for >90 minutes → `session_ended` event emitted
9. Unregistered Claude Code sessions in `~/.claude/projects/` are completely ignored
10. Polling interval can be adjusted dynamically (for hybrid mode)

### 3.2 Non-Functional Success Criteria

1. File watcher does not block the main Flask application thread
2. Incremental parsing avoids re-reading entire jsonl files
3. Git metadata calls are cached to avoid performance impact
4. Watcher handles rapid file changes without event storms
5. Clean shutdown: watcher stops gracefully when application stops
6. Resource efficient: minimal CPU/memory when sessions are idle

---

## 4. Functional Requirements (FRs)

### FR1: Session Registration API

The system shall provide an internal Python API to register sessions for monitoring:
- `register_session(session_uuid, project_path, working_directory, iterm_pane_id=None)` — start monitoring
- `unregister_session(session_uuid)` — stop monitoring
- `get_registered_sessions()` — list all registered sessions
- `is_session_registered(session_uuid)` — check registration status

### FR2: Session Registry Storage

The system shall maintain an in-memory registry of registered sessions with:
- Session UUID
- Project path (decoded from working directory)
- Working directory (original path)
- iTerm pane ID (optional, for AppleScript focus)
- Registration timestamp
- Last activity timestamp
- jsonl file path (located after registration)

### FR3: JSONL File Locator

The system shall locate the jsonl file for a registered session:
- Search `~/.claude/projects/` for folder matching the working directory
- Folder name format: working directory with `/` replaced by `-` (e.g., `-Users-foo-project`)
- Find the most recent jsonl file in that folder
- Handle case where folder or file doesn't exist yet (wait for creation)

### FR4: Watchdog Integration

The system shall use Watchdog to monitor filesystem changes:
- Watch for modifications to registered sessions' jsonl files
- Watch for new files in registered sessions' project folders
- Watch for file deletions (session cleanup)
- Debounce rapid changes to prevent event storms

### FR5: JSONL Parser

The system shall parse Claude Code jsonl files:
- Read files line-by-line (one JSON object per line)
- Track file position to only process new lines since last read
- Extract turn data from each line:
  - Actor (user or assistant/agent)
  - Text content
  - Timestamp
- Handle malformed lines: log warning, skip line, continue processing

### FR6: Project Path Decoder

The system shall decode project paths from folder names:
- Replace leading `-` with `/`
- Replace subsequent `-` with `/` (standard case)
- Handle edge case: consecutive dashes may indicate special characters
- Validate decoded path exists on filesystem

### FR7: Git Metadata Extraction

The system shall extract git metadata for projects:
- Repository URL: `git remote get-url origin`
- Current branch: `git branch --show-current`
- Cache results during session lifetime
- Return None/empty for non-git directories (don't fail)

### FR8: Turn Detection and Event Emission

The system shall emit events when new turns are detected:
- Event type: `turn_detected`
- Event data includes:
  - Session UUID
  - Project path
  - Turn actor
  - Turn text
  - Turn timestamp
  - Source: `polling` (to distinguish from hook events)

### FR9: Session Inactivity Detection

The system shall detect inactive sessions:
- Track last activity timestamp per session
- Configurable inactivity timeout (default: 90 minutes)
- Emit `session_ended` event when timeout exceeded
- Automatically unregister inactive sessions

### FR10: Configuration Schema

The system shall extend config.yaml with file watcher settings:
```yaml
claude:
  projects_path: "~/.claude/projects"

file_watcher:
  polling_interval: 2  # seconds
  inactivity_timeout: 5400  # 90 minutes in seconds
  debounce_interval: 0.5  # seconds
```

### FR11: Polling Interval Control

The system shall support dynamic polling interval adjustment:
- Expose method to set polling interval at runtime
- Support switching between fallback mode (2s) and hooks-active mode (60s)
- Sprint 13 (Hooks) will call this to implement hybrid mode

### FR12: Graceful Lifecycle Management

The system shall integrate with Flask application lifecycle:
- Start watcher when application starts
- Stop watcher cleanly when application stops
- Handle registration/unregistration during runtime

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Threading Model

The file watcher shall run in a background thread or process:
- Must not block Flask request handling
- Must be thread-safe for registration/unregistration calls
- Must handle concurrent access to session registry

### NFR2: Incremental File Reading

The file watcher shall use incremental file reading:
- Track byte position per watched file
- Seek to last position before reading new content
- Only process new lines appended since last read

### NFR3: Debouncing

The file watcher shall debounce rapid file changes:
- Configurable debounce interval (default: 0.5 seconds)
- Coalesce rapid writes into single processing pass
- Prevent event storms from fast Claude Code output

### NFR4: Error Resilience

The file watcher shall handle errors gracefully:
- File not found: wait for creation, don't crash
- Permission errors: log and skip, don't crash
- Malformed JSON: log and skip line, continue processing
- Git command failures: return None, don't crash

### NFR5: Logging

The file watcher shall provide comprehensive logging:
- INFO: Session registered/unregistered, file watching started/stopped
- DEBUG: Turn detected, file change events
- WARNING: Malformed lines, missing files
- ERROR: Unexpected failures with stack traces

### NFR6: Resource Efficiency

The file watcher shall be resource efficient:
- Minimal CPU when no file changes occurring
- Minimal memory footprint for session registry
- Clean up resources for unregistered sessions

---

## 6. Technical Context

*Note: This section captures architectural decisions for implementation reference.*

### Technology Choices

- **File watching:** Watchdog library
- **Threading:** Python threading or concurrent.futures
- **JSON parsing:** Standard library json module
- **Git operations:** subprocess calls to git CLI

### File Structure

```
src/claude_headspace/
├── services/
│   ├── __init__.py
│   ├── file_watcher.py      # Main FileWatcher service
│   ├── jsonl_parser.py      # JSONL parsing logic
│   ├── session_registry.py  # Session registration storage
│   ├── project_decoder.py   # Path decoding logic
│   └── git_metadata.py      # Git metadata extraction
```

### Integration Points

- **Sprint 5 (Event System):** Receives emitted events
- **Sprint 11 (Launcher):** Calls registration API
- **Sprint 13 (Hooks):** Calls polling interval control, checks session registration

### Claude Code JSONL Format

Claude Code stores session data in jsonl files. Each line is a JSON object representing a conversation turn. The exact schema should be determined by examining actual Claude Code output files.

### Folder Name Encoding

Claude Code encodes project paths in folder names:
- `/Users/samotage/dev/project` → `-Users-samotage-dev-project`
- The leading slash becomes a leading dash
- Subsequent slashes become dashes

---

## 7. Dependencies

### Prerequisites

- Sprint 3 (Domain Models) complete — Event model defined (for event type taxonomy)
- `watchdog` library added to `pyproject.toml`

### Blocking

This sprint blocks:
- Sprint 5 (Event System) — needs events emitted by file watcher
- Sprint 6 (State Machine) — processes turn events
- Sprint 11 (Launcher Script) — uses registration API
- Sprint 13 (Hook Receiver) — uses registration check, polling interval control

---

## 8. Relationship to Hooks (Sprint 13)

The file watcher and hooks work together in a hybrid model:

| Aspect | File Watcher (Sprint 4) | Hooks (Sprint 13) |
|--------|------------------------|-------------------|
| Event source | jsonl file polling | HTTP POST from Claude Code |
| Latency | 2-60 seconds | <100ms |
| Confidence | Lower (parsing-based) | 1.0 (event-based) |
| Role | Fallback/reconciliation | Primary |
| Always runs | Yes | Only when hooks installed |

**Hybrid Mode Operation:**
1. Hooks active → File watcher polls every 60 seconds (reconciliation only)
2. Hooks silent >300 seconds → File watcher polls every 2 seconds (full monitoring)
3. Hooks resume → Back to 60-second polling

Sprint 13 will call the file watcher's polling interval control API to implement this switching.

---

## 9. Open Questions

*None — all questions resolved during workshop.*

---

## 10. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PRD Workshop | Initial PRD created |
