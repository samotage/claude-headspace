## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### Filename Format Reform (FR1, FR2)

- [x] 2.1 Modify `generate_handoff_file_path()` in `handoff_executor.py`: change timestamp format to ISO 8601 (`YYYY-MM-DDTHH:MM:SS`), use underscore separators, add `<insert-summary>` placeholder, change agent tag to `agent-id:{N}`
- [x] 2.2 Modify `compose_handoff_instruction()` in `handoff_executor.py`: add explicit instructions for departing agent to replace `<insert-summary>` with kebab-case summary (max 60 chars, no underscores, lowercase with hyphens)

### Polling Fallback (FR3)

- [x] 2.3 Modify `_poll_for_handoff_file()` in `handoff_executor.py`: add glob fallback pattern `{timestamp}_*_{agent_tag}.md` after exact path check fails; log warning if multiple matches; use first match

### Startup Detection Service (FR4, FR5, FR6, NFR4)

- [x] 2.4 Create `src/claude_headspace/services/handoff_detection.py` with `HandoffDetectionService` class: `detect_and_emit()` method scans `data/personas/{slug}/handoffs/` for `.md` files, sorts by filename (reverse), takes top 3, emits `synthetic_turn` SSE event
- [x] 2.5 Register `HandoffDetectionService` in `app.py` as `app.extensions["handoff_detection_service"]`
- [x] 2.6 Modify `session_correlator.py`: after persona assignment in `_create_agent_for_session()` or relevant correlation path, call `HandoffDetectionService.detect_and_emit(agent)`

### Synthetic Turn SSE (FR7, FR8, FR9, FR10)

- [x] 2.7 Add `synthetic_turn` to `commonTypes` array in `static/js/sse-client.js`
- [x] 2.8 Create dashboard JS handler for `synthetic_turn` events: render visually distinct bubbles (muted background, dashed border, "SYSTEM" label), display handoff filenames with click-to-copy file paths, position before first real turn

### CLI Command (FR12, FR13, FR14, FR15)

- [x] 2.9 Add `handoffs` command to `persona_cli` in `src/claude_headspace/cli/persona_cli.py`: parse both new and legacy filename formats, output columnar format (timestamp, summary, agent-id), support `--limit N` and `--paths` options, sort newest first, filesystem-only data source

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for `generate_handoff_file_path()` new format: verify ISO 8601 timestamp, underscore separators, `<insert-summary>` placeholder, `agent-id:{N}` tag
- [x] 3.2 Unit tests for `compose_handoff_instruction()`: verify kebab-case instructions are included in output
- [x] 3.3 Unit tests for polling glob fallback: verify fallback triggers when exact path not found, verify matches on glob pattern, verify warning logged for multiple matches
- [x] 3.4 Unit tests for `HandoffDetectionService.detect_and_emit()`: verify scans correct directory, returns top 3 files sorted reverse, handles missing dir / empty dir / no persona gracefully, emits `synthetic_turn` SSE event
- [x] 3.5 Unit tests for CLI `persona handoffs` command: verify both filename formats are parsed, verify columnar output, verify `--limit` and `--paths` options, verify newest-first sorting
- [x] 3.6 Verify all existing handoff tests still pass (NFR backward compatibility)

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification: new handoff filename format in filesystem
- [ ] 4.4 Manual verification: synthetic turn appears on dashboard for persona-backed agent
- [ ] 4.5 Manual verification: CLI `flask persona handoffs` works with both old and new filename formats
