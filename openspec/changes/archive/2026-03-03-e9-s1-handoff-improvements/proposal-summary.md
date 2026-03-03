# Proposal Summary: e9-s1-handoff-improvements

## Architecture Decisions

1. **Filename format uses underscore separators**: Three sections (`{timestamp}_{summary}_{agent-tag}`) split cleanly on underscores, enabling reliable parsing while keeping hyphens available within the summary slug. (Workshop Decision 0A.1)

2. **Detection is synchronous, not background**: `HandoffDetectionService` runs during agent creation (no background thread, no DB queries). A filesystem glob of a small directory is sub-millisecond. (Workshop Decision 0A.2)

3. **Dashboard-only SSE injection**: Synthetic turns use a new `synthetic_turn` SSE event type. The agent never sees these turns — they are strictly for operator consumption on the dashboard. No tmux delivery, no hook response. (Workshop Decision 0A.3)

4. **Manual rehydration (operator-gated)**: No automated rehydration. The operator sees the listing, copies a path, and tells the agent what to do. This preserves operator control over context window usage. (Workshop Decision 0A.4)

5. **Filesystem-only data source for listings**: Both the detection service and CLI command read the filesystem directly. No DB queries for handoff listings. The directory listing is the source of truth. (Workshop Decisions 0A.5, 0A.7)

6. **No schema changes**: The filename IS the summary. The existing `Handoff.file_path` column carries the new-format path. No new tables, no new columns. (PRD NFR2)

## Implementation Approach

The implementation is organised into four streams that can be built largely in sequence:

1. **HandoffExecutor modifications** (FR1-FR3): Modify three existing methods in `handoff_executor.py` — filename generation, instruction composition, and polling with glob fallback. These are surgical changes to an existing, well-tested service.

2. **HandoffDetectionService** (FR4-FR6): New lightweight service — ~30 lines of Python. Scans persona handoff directory, emits SSE event. Registered in `app.py`, called from `session_correlator.py` after persona assignment.

3. **Dashboard rendering** (FR7-FR9): Add `synthetic_turn` to SSE client `commonTypes`, create a JS handler that renders handoff listings as system bubbles with click-to-copy functionality.

4. **CLI command** (FR12-FR15): Add `handoffs` subcommand to existing `persona_cli` group. Parses both old and new filename formats for columnar display.

## Files to Modify (organised by type)

### Python Services (backend)
- `src/claude_headspace/services/handoff_executor.py` — Modify `generate_handoff_file_path()`, `compose_handoff_instruction()`, `_poll_for_handoff_file()`
- `src/claude_headspace/services/session_correlator.py` — Add `HandoffDetectionService.detect_and_emit()` call after persona assignment
- `src/claude_headspace/app.py` — Register `HandoffDetectionService` as `app.extensions["handoff_detection_service"]`

### New Python Files
- `src/claude_headspace/services/handoff_detection.py` — `HandoffDetectionService` class

### CLI
- `src/claude_headspace/cli/persona_cli.py` — Add `handoffs` command with `--limit` and `--paths` options

### JavaScript (frontend)
- `static/js/sse-client.js` — Add `synthetic_turn` to `commonTypes` array
- `static/js/` — New or extended JS module for synthetic turn rendering (handler + click-to-copy)

### No Changes Needed
- `src/claude_headspace/services/broadcaster.py` — Already accepts arbitrary event type strings
- `src/claude_headspace/services/persona_assets.py` — No changes, but may be referenced for handoff dir path construction
- Database models / migrations — No schema changes

## Acceptance Criteria

1. New handoff files use format `{YYYY-MM-DDTHH:MM:SS}_{summary-slug}_{agent-id:NNN}.md`
2. Departing agent receives explicit kebab-case summary instructions in handoff instruction
3. Polling thread detects handoff files via glob fallback when summary differs from placeholder
4. New persona-backed agents see synthetic turn with up to 3 recent handoff filenames on dashboard
5. Synthetic turns are visually distinct (muted background, "SYSTEM" label) with copyable file paths
6. `flask persona handoffs <slug>` lists handoffs with `--limit N` and `--paths` options
7. Legacy handoff filenames continue to work throughout the system
8. No database schema changes
9. Existing auto-injection flow for HandoffExecutor-created successors is unaffected
10. All existing handoff tests pass

## Constraints and Gotchas

- **Colon in filename**: The `agent-id:1137` portion contains a colon. On macOS/Linux this is fine. Windows would have issues but this is a macOS-only project.
- **Agent may not replace placeholder**: If the agent writes the file with literal `<insert-summary>` in the filename, the glob fallback still matches. Ugly but functional.
- **Underscore in agent summary**: If the agent puts underscores in their summary, the CLI parser must handle gracefully — treat everything between first and last underscore as the summary section.
- **S4 cross-reference**: Sprint 4 (Channel Service) also modifies `session_correlator.py` at the same logical point (after persona assignment). Both modifications should append sequentially.
- **S7 cross-reference**: Sprint 7 (Dashboard UI) also modifies `sse-client.js` `commonTypes` to add `channel_message` and `channel_update`. Building agents should check for prior modifications and append rather than replace.

## Git Change History

- Recent commits are all workshop/documentation for Epic 9 interagent communication
- No prior code changes to handoff_executor.py in recent history
- No prior openspec changes for this subsystem
- The handoff system was built in Epic 8, Sprint 14 and has been stable

## Q&A History

No clarifications were needed. The PRD has all 7 design decisions resolved in Workshop Section 0A (decisions 0A.1 through 0A.7).

## Dependencies

- **HandoffExecutor service** (E8-S14, done) — Existing handoff pipeline with methods to modify
- **Persona filesystem assets** (E8-S5, done) — `data/personas/{slug}/` directory convention
- **Session correlator persona assignment** (E8-S8, done) — Trigger point for startup detection
- **SSE broadcaster** (E1-S7, done) — Event broadcast infrastructure
- **Tmux bridge** (E5-S4, done) — Existing delivery mechanism (unmodified)

No unresolved dependencies. No new package dependencies needed.

## Testing Strategy

1. **Unit tests for handoff_executor.py modifications**: Test new filename format, instruction content, and glob fallback logic
2. **Unit tests for HandoffDetectionService**: Test directory scanning, file sorting, edge cases (no dir, empty dir, no persona), SSE emission
3. **Unit tests for CLI command**: Test filename parsing (both formats), columnar output, `--limit` and `--paths` options
4. **Regression**: Run all existing handoff tests to verify backward compatibility
5. **Manual verification**: Create a handoff, verify new filename format on disk; start a persona-backed agent, verify synthetic turn appears on dashboard; run CLI command with sample data

## OpenSpec References

- **Proposal**: `openspec/changes/e9-s1-handoff-improvements/proposal.md`
- **Tasks**: `openspec/changes/e9-s1-handoff-improvements/tasks.md`
- **Specs**:
  - `openspec/changes/e9-s1-handoff-improvements/specs/handoff-execution/spec.md`
  - `openspec/changes/e9-s1-handoff-improvements/specs/handoff-detection/spec.md`
  - `openspec/changes/e9-s1-handoff-improvements/specs/dashboard/spec.md`
  - `openspec/changes/e9-s1-handoff-improvements/specs/persona-cli/spec.md`
