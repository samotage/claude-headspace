---
validation:
  status: valid
  validated_at: '2026-03-03T14:22:25+11:00'
---

## Product Requirements Document (PRD) — Handoff Continuity Improvements

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 1 — Handoff filename reform, startup detection, synthetic injection, and handoff history CLI
**Author:** Robbo (workshopped with Sam)
**Status:** Draft

---

## Executive Summary

The handoff system (Epic 8, Sprint 14) works but has three gaps that the operator identified during production use: handoff filenames are opaque (you can't tell what a handoff is about without opening it), new agents have no awareness of prior handoffs for their persona, and the operator has no control over whether an agent rehydrates from a predecessor's context.

This sprint addresses all three gaps. The handoff filename format changes from `{YYYYMMDDTHHmmss}-{agent-8digit}.md` to `{timestamp}_{summary-slug}_{agent-id:NNN}.md`, making the directory listing itself a scannable index. A startup detection mechanism scans the persona's handoff directory when a new agent is created and surfaces the most recent handoffs as synthetic dashboard turns. The operator then decides whether to tell the agent to read a specific handoff — rehydration is gated, not automatic.

This is Sprint 1 of Epic 9 (Inter-Agent Communication) but is fully independent of the channel infrastructure in Sprints 2–8. It ships standalone, improving the existing persona handoff pipeline with no new database tables or models.

All design decisions are resolved in the Inter-Agent Communication Workshop, Section 0A (7 decisions: 0A.1–0A.7). See `docs/workshop/interagent-communication/sections/section-0a-handoff-continuity.md`.

---

## 1. Context & Purpose

### 1.1 Context

The current handoff system generates filenames like `20260302T233900-00001137.md` — timestamps and zero-padded agent IDs. A directory listing of `data/personas/architect-robbo-3/handoffs/` tells you nothing about what each handoff covers. The operator must open each file to understand its content.

When a new agent starts for a persona, it has no awareness of prior handoffs unless it was specifically created by the HandoffExecutor (which sets `previous_agent_id` and auto-injects context). Manually started agents — the operator fires up a new Robbo session — start blind. There is no way to know that Robbo's predecessor left work behind without manually inspecting the filesystem.

The current system also auto-injects handoff context without operator input. The operator has no say in whether the agent should continue from a handoff or start fresh. This consumes context window whether or not the prior work is still relevant.

The existing `HandoffExecutor` service (`src/claude_headspace/services/handoff_executor.py`) contains all the methods that need modification: `generate_handoff_file_path()`, `compose_handoff_instruction()`, and the background polling thread `_poll_for_handoff_file()`.

### 1.2 Target User

The operator (Sam), who manages persona-backed agents and needs to quickly understand what prior agents were working on, decide whether a new agent should continue from a predecessor's context, and browse handoff history without opening individual files.

### 1.3 Success Moment

A new Robbo agent starts. The operator glances at the dashboard and sees three recent handoffs listed — including summaries like "epic9-workshop-restructure" and "org-workshop-section1" — right on the agent's card. The operator clicks one, copies the path, and pastes it into a message telling Robbo to pick up where the predecessor left off. The whole interaction takes 10 seconds, not 2 minutes of filesystem browsing.

---

## 2. Scope

### 2.1 In Scope

- New handoff filename format: `{timestamp}_{summary-slug}_{agent-id:NNN}.md`
- Updated `generate_handoff_file_path()` with `<insert-summary>` placeholder
- Updated `compose_handoff_instruction()` with filename format instructions for the departing agent
- Updated polling thread with glob fallback for summary-variable filenames
- New `HandoffDetectionService` — scans persona handoff directory on agent creation
- New `synthetic_turn` SSE event type for dashboard-only informational turns
- Dashboard rendering of synthetic turns with handoff file listing and copyable paths
- New `flask org persona handoffs` CLI command for on-demand handoff history

### 2.2 Out of Scope

- Channel data model, ChannelService, or any channel infrastructure (E9-S2 through E9-S8)
- PersonaType table or operator Persona creation (E9-S2)
- Changes to the Handoff DB model schema (no new columns — the filename IS the summary)
- Handoff file cleanup or lifecycle management
- Automated handoff quality scoring
- "Rehydrate" button on the dashboard (v2 convenience — copy-paste is sufficient for v1)
- `--detail` flag on CLI that reads file content (v2 — scannable filenames make this unnecessary)
- Changes to the existing auto-injection flow for HandoffExecutor-created successors (that path continues to work as-is; this sprint adds the startup detection path alongside it)

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. New handoff files are created with the format `{YYYY-MM-DDTHH:MM:SS}_{summary-slug}_{agent-id:NNN}.md`
2. The `<insert-summary>` placeholder in the generated path is communicated to the departing agent via the handoff instruction
3. The departing agent receives explicit instructions to replace the placeholder with a kebab-case summary (max 60 chars, no underscores)
4. The polling thread detects handoff files even when the agent's chosen summary differs from any expected value (glob fallback)
5. When a new agent is created and assigned a persona, the system scans `data/personas/{slug}/handoffs/` for existing handoff documents
6. The most recent 3 handoffs are surfaced as a `synthetic_turn` SSE event on the dashboard
7. Synthetic turns render as visually distinct bubbles (system-generated indicator) before the agent's first real turn
8. Each listed handoff filename is a copyable file path
9. The operator can run `flask org persona handoffs <slug>` to list all handoffs for a persona, newest first
10. The CLI supports `--limit N` to show only the most recent N handoffs
11. The CLI supports `--paths` to include full absolute file paths in the output
12. Legacy handoff files (old format) continue to appear in listings and are not broken by the format change

### 3.2 Non-Functional Success Criteria

1. Startup detection adds no perceptible delay to agent creation — filesystem scan of a small directory is sub-millisecond
2. Synthetic turns are dashboard-only — the agent never receives them via tmux or any other delivery mechanism
3. The existing HandoffExecutor auto-injection flow for `previous_agent_id`-linked successors is unaffected
4. All existing handoff tests continue to pass

---

## 4. Functional Requirements (FRs)

### Filename Format

**FR1: New filename format**
The `generate_handoff_file_path()` method shall produce paths in the format:
`{project_root}/data/personas/{slug}/handoffs/{timestamp}_<insert-summary>_{agent-tag}.md`

Where:
- `{timestamp}` is ISO 8601: `YYYY-MM-DDTHH:MM:SS` (UTC)
- `<insert-summary>` is a literal placeholder string for the agent to replace
- `{agent-tag}` is `agent-id:{N}` where N is the agent's integer ID (no zero-padding)

**FR2: Handoff instruction includes filename guidance**
The `compose_handoff_instruction()` method shall include explicit instructions telling the departing agent to replace `<insert-summary>` with a kebab-case summary of their work. The instruction shall specify: max 60 characters, no underscores (reserved as section separator), lowercase with hyphens.

Example instruction addition:
```
IMPORTANT — Replace `<insert-summary>` in the filename with a kebab-case
summary of your work (max 60 characters, no underscores). Example:
  2026-03-02T23:39:00_epic9-workshop-restructure_agent-id:1137.md
```

### Polling Fallback

**FR3: Glob fallback for polling thread**
The `_poll_for_handoff_file()` method shall, if the exact generated path does not exist after the first poll cycle, fall back to globbing for `{timestamp}_*_{agent-tag}.md` in the handoff directory. The timestamp and agent-tag portions are software-generated and deterministic — only the summary portion varies.

The glob fallback shall match exactly one file. If multiple files match (should not happen — timestamp + agent-tag is unique), log a warning and use the first match.

### Startup Detection

**FR4: Handoff detection on agent creation**
When a new agent is created and assigned a persona (via SessionCorrelator), the system shall scan `data/personas/{slug}/handoffs/` for existing `.md` files.

**FR5: Detection result**
If handoff files exist, the system shall sort them by filename (timestamp prefix gives chronological order) and select the most recent 3. If fewer than 3 exist, return all of them.

**FR6: Detection edge cases**
- No handoff directory → skip, no synthetic turn
- Empty directory → skip, no synthetic turn
- Agent created by HandoffExecutor (`previous_agent_id` set) → still show the listing. The operator may want a different handoff than the automatic predecessor's. The synthetic listing is informational; the operator decides.
- No staleness threshold. Old handoffs still appear. The operator reads timestamps and decides relevance.

### Synthetic Injection

**FR7: `synthetic_turn` SSE event type**
The system shall emit a new SSE event type `synthetic_turn` via the existing broadcaster. The event data shall include:
```json
{
  "agent_id": 1234,
  "persona_slug": "architect-robbo-3",
  "turns": [{
    "type": "handoff_listing",
    "filenames": ["2026-03-02T23:39:00_epic9-workshop-restructure_agent-id:1137.md", ...],
    "file_paths": ["/abs/path/to/file.md", ...]
  }]
}
```

**FR8: Dashboard rendering**
Synthetic turns shall render as visually distinct bubbles on the agent's dashboard card/panel. Visual indicators: muted background or dashed border, "SYSTEM" label. They appear before the agent's first real turn.

**FR9: Copyable file paths**
Each handoff entry in the synthetic turn shall be a clickable/copyable element. Clicking copies the full absolute file path to the clipboard.

**FR10: Agent isolation**
Synthetic turns are NOT delivered to the agent via tmux, hook response, or any other mechanism. They are dashboard-only SSE events for operator consumption.

### Operator Rehydration

**FR11: Manual rehydration flow**
The operator's rehydration path is: see synthetic turn listing → read filenames (timestamps + summaries) → click to copy a file path → paste into a message to the agent with context (e.g., "Read the handoff at `{path}` and continue where they left off"). No automated rehydration. No standardised instruction format — the operator types naturally.

### On-Demand Handoff History

**FR12: CLI command**
The system shall provide `flask org persona handoffs <slug>` to list all handoff files for a persona. Output: one line per handoff, newest first, showing timestamp, summary slug, and agent ID.

**FR13: CLI output format**
Plain text, columnar, designed for terminal scanning:
```
2026-03-02T23:39:00  epic9-workshop-restructure           agent-id:1137
2026-03-02T19:28:59  epic9-section1-audit                 agent-id:1122
2026-03-02T04:58:10  org-workshop-section1                agent-id:1117
```

**FR14: CLI options**
- `--limit N` — show only the most recent N handoffs
- `--paths` — include the full absolute file path as an additional column (for copy-paste into rehydration instructions)

**FR15: Data source**
The CLI reads the filesystem only (`data/personas/{slug}/handoffs/*.md`). No DB query. The directory listing is the source of truth.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: Backward compatibility with legacy filenames**
The system shall accept mixed filename formats in the handoff directory. Old-format files (`YYYYMMDDTHHmmss-NNNNNNNN.md`) still sort by timestamp prefix and appear in listings. No migration of existing files.

**NFR2: No new database tables or columns**
This sprint adds no schema changes. The filename IS the summary. The existing `Handoff.file_path` column carries the new-format path. No new summary column.

**NFR3: Existing auto-injection unaffected**
The existing flow where HandoffExecutor creates a successor and auto-injects the handoff prompt continues to work. Startup detection runs alongside it — not instead of it. A successor created by HandoffExecutor will see both the auto-injection (via tmux) AND the synthetic turn listing (via SSE) on the dashboard.

**NFR4: Service registration**
`HandoffDetectionService` shall be registered as `app.extensions["handoff_detection_service"]` following the existing service registration pattern.

---

## 6. Technical Context

### 6.1 Files to Modify

| File | Change |
|------|--------|
| `src/claude_headspace/services/handoff_executor.py` | Modify `generate_handoff_file_path()`: new format with `<insert-summary>` placeholder. Modify `compose_handoff_instruction()`: add filename format guidance. Modify `_poll_for_handoff_file()`: add glob fallback. |
| `src/claude_headspace/services/broadcaster.py` | No code change — `broadcast()` already accepts arbitrary event types. `synthetic_turn` is just a new type string. |
| `src/claude_headspace/services/session_correlator.py` | After persona assignment, call `HandoffDetectionService.detect_and_emit()`. **Note:** S4 also modifies session_correlator.py after persona assignment to update ChannelMembership `agent_id`. Both modifications target the same logical point — append sequentially. |
| `src/claude_headspace/app.py` | Register `HandoffDetectionService` as `app.extensions["handoff_detection_service"]` during app factory setup (per NFR4). |

### 6.2 New Files

| File | Purpose |
|------|---------|
| `src/claude_headspace/services/handoff_detection.py` | `HandoffDetectionService` — scans persona handoff directory, emits `synthetic_turn` SSE event. |
| `src/claude_headspace/cli/org_cli.py` (or extend existing CLI) | `flask org persona handoffs` command. Note: current CLI uses `flask persona` (see 6.5). |
| Dashboard JS (new module or extension) | Render `synthetic_turn` SSE events as system bubbles. |

### 6.3 Current `generate_handoff_file_path()` Implementation

The current method (lines 104–122 of `handoff_executor.py`) generates:
```python
timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
agent_suffix = str(agent.id).zfill(8)
# Result: {project_root}/data/personas/{slug}/handoffs/{timestamp}-{agent_suffix}.md
```

The new implementation shall produce:
```python
timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
agent_tag = f"agent-id:{agent.id}"
# Result: {project_root}/data/personas/{slug}/handoffs/{timestamp}_<insert-summary>_{agent_tag}.md
```

Key changes:
- Timestamp format: `YYYYMMDDTHHmmss` → `YYYY-MM-DDTHH:MM:SS` (ISO 8601 with separators)
- Separator: hyphen → underscore (three sections cleanly split on underscores)
- Agent identifier: zero-padded 8-digit ID → `agent-id:{N}` (human-readable, no padding)
- New `<insert-summary>` placeholder section between timestamp and agent-tag

### 6.4 Polling Thread Glob Fallback

The current polling thread (lines 283–352) checks `os.path.exists(file_path)` for the exact generated path. With the placeholder, the agent produces a path where `<insert-summary>` is replaced with their chosen summary.

The glob fallback pattern is: `{timestamp}_*_{agent_tag}.md`

```python
import glob

# Primary check — exact path (unlikely to match due to placeholder)
if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
    ...

# Fallback — glob for files matching timestamp and agent-tag
dir_path = Path(file_path).parent
pattern = f"{timestamp}_*_{agent_tag}.md"
matches = sorted(dir_path.glob(pattern))
if matches and matches[0].stat().st_size > 0:
    file_path = str(matches[0])  # Use the actual path the agent wrote
    ...
```

The timestamp and agent-tag are deterministic (software-generated). Only the summary varies. This glob is scoped to one agent's handoff — it cannot accidentally match another agent's file.

### 6.5 CLI Namespace Note

The workshop specifies `flask org persona handoffs` (Organisation Workshop Section 1.3 defined `flask org` as the unified entry point). The current codebase uses `flask persona` (not yet restructured under `flask org`).

Implementation should use whichever namespace is current at build time. If `flask org` exists, nest under it. If not, add to the existing `flask persona` group as `flask persona handoffs`. The command name and behaviour are the same either way.

### 6.6 `HandoffDetectionService` Design

Lightweight service — no background thread, no DB queries. Called synchronously during agent creation.

```python
class HandoffDetectionService:
    def __init__(self, app):
        self.app = app

    def detect_and_emit(self, agent: Agent) -> None:
        """Scan persona handoff dir and emit synthetic_turn SSE if handoffs exist."""
        if not agent.persona:
            return
        handoff_dir = self._handoff_dir(agent.persona.slug)
        if not handoff_dir.exists():
            return
        files = sorted(handoff_dir.glob("*.md"), reverse=True)[:3]
        if not files:
            return
        # Emit synthetic_turn SSE
        broadcaster.broadcast("synthetic_turn", {
            "agent_id": agent.id,
            "persona_slug": agent.persona.slug,
            "turns": [{
                "type": "handoff_listing",
                "filenames": [f.name for f in files],
                "file_paths": [str(f) for f in files],
            }],
        })
```

### 6.7 Filename Parsing for CLI Display

The CLI command parses filenames to extract timestamp, summary, and agent-id for columnar display. Both old and new formats are handled:

| Format | Parsing |
|--------|---------|
| New: `2026-03-02T23:39:00_epic9-workshop-restructure_agent-id:1137.md` | Split on `_` → 3 sections: timestamp, summary, agent-tag |
| Legacy: `20260302T233900-00001137.md` | Split on `-` → timestamp (compact), agent ID (zero-padded). Summary column shows `(legacy)`. |

### 6.8 Dashboard Rendering

The `synthetic_turn` SSE event is handled by dashboard JS. A new handler (or extension of the existing turn rendering) creates a visually distinct bubble:

- Muted background colour (e.g., `bg-slate-100` or dashed border)
- "SYSTEM" label or gear icon
- Each handoff entry as a row: filename displayed, click-to-copy on the file path
- Positioned before the agent's first real turn in the card/panel

This is frontend JS work — no Jinja template change needed. The SSE event arrives on the existing `/api/events/stream` endpoint, type-filtered by the dashboard.

**Note:** S7 (Dashboard UI) also modifies `sse-client.js` `commonTypes` to add `channel_message` and `channel_update`. Building agents should check for prior modifications to the `commonTypes` array and append rather than replace.

### 6.9 Design Decisions (All Resolved — Workshop Section 0A)

| Decision | Resolution | Source |
|----------|-----------|--------|
| Filename format | `{timestamp}_{summary}_{agent-id:NNN}.md` — underscore separators, no braces | 0A.1 |
| Startup detection trigger | After persona assignment in SessionCorrelator | 0A.2 |
| Most recent N handoffs | 3 (hardcoded, not configurable) | 0A.2 |
| Synthetic injection mechanism | Dashboard-only SSE (`synthetic_turn` event type). Agent never sees it. | 0A.3 |
| Rehydration flow | Manual: operator copies path, pastes into message to agent | 0A.4 |
| Handoff history access | CLI (`flask org persona handoffs`), API, dashboard | 0A.5 |
| Instruction template changes | `<insert-summary>` placeholder + kebab-case instructions | 0A.6 |
| Polling fallback | Glob `{timestamp}_*_{agent_tag}.md` if exact path not found | 0A.6 |
| CLI namespace | Under `flask org persona` (or `flask persona` if org CLI not yet restructured) | 0A.7 |
| CLI output format | Plain text, columnar, one line per handoff | 0A.7 |
| Data source | Filesystem only — no DB query for listings | 0A.5, 0A.7 |
| Legacy compatibility | Mixed formats accepted, no migration | 0A.1 |

### 6.10 Existing Services Used (DO NOT recreate)

- **`src/claude_headspace/services/handoff_executor.py`** — Contains `generate_handoff_file_path()`, `compose_handoff_instruction()`, and `_poll_for_handoff_file()`. Modify in place.
- **`src/claude_headspace/services/broadcaster.py`** — `broadcast()` method accepts any event type string. No changes needed to broadcaster code.
- **`src/claude_headspace/services/session_correlator.py`** — Agent creation and persona assignment. Add call to `HandoffDetectionService.detect_and_emit()` after persona is assigned.
- **`src/claude_headspace/services/persona_assets.py`** — Already has persona directory path resolution. May be useful for handoff dir path construction.

### 6.11 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Agents fail to replace the `<insert-summary>` placeholder | Medium | Low | Polling glob fallback matches regardless of summary content. Worst case: filename has literal `<insert-summary>` in it — ugly but functional. |
| Agents insert underscores in the summary (breaking the 3-section split) | Low | Low | CLI parser handles gracefully — if more than 2 underscores, treat everything between first and last underscore as the summary. |
| Large handoff directories slow startup detection | Very Low | Low | Filesystem glob of a single directory is sub-millisecond even with hundreds of files. No DB query, no file content reading. |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|------------|--------|------------------|
| HandoffExecutor service | E8-S14 (done) | Existing handoff pipeline — methods to modify |
| Persona filesystem assets | E8-S5 (done) | `data/personas/{slug}/` directory convention |
| Session correlator persona assignment | E8-S8 (done) | Trigger point for startup detection |
| SSE broadcaster | E1-S7 (done) | Event broadcast infrastructure |
| Tmux bridge | E5-S4 (done) | Existing delivery mechanism (unmodified) |

No unresolved dependencies. All prerequisites are shipped.

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-03 | Robbo  | Initial PRD from Epic 9 Workshop (Section 0A) |
| 1.1     | 2026-03-03 | Robbo  | v2 cross-PRD remediation: added S4 cross-reference for session_correlator.py shared modification (Finding #7) |
| 1.2     | 2026-03-03 | Robbo  | v3 cross-PRD remediation: added `app.py` to Files to Modify for HandoffDetectionService registration (Finding #5) |
