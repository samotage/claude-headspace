## MODIFIED Requirements

### Requirement: Handoff Filename Format

The `generate_handoff_file_path()` method SHALL produce paths in the format:
`{project_root}/data/personas/{slug}/handoffs/{timestamp}_<insert-summary>_{agent-tag}.md`

Where:
- `{timestamp}` is ISO 8601: `YYYY-MM-DDTHH:MM:SS` (UTC)
- `<insert-summary>` is a literal placeholder string for the agent to replace
- `{agent-tag}` is `agent-id:{N}` where N is the agent's integer ID (no zero-padding)

#### Scenario: New handoff file path generation

- **WHEN** `generate_handoff_file_path()` is called for an agent with ID 1137 and persona slug "architect-robbo-3"
- **THEN** the path SHALL match the pattern `*/data/personas/architect-robbo-3/handoffs/YYYY-MM-DDTHH:MM:SS_<insert-summary>_agent-id:1137.md`

#### Scenario: Timestamp uses ISO 8601 with separators

- **WHEN** a handoff file path is generated
- **THEN** the timestamp portion SHALL use ISO 8601 with separators (hyphens in date, colons in time, T separator)

### Requirement: Handoff Instruction Filename Guidance

The `compose_handoff_instruction()` method SHALL include explicit instructions telling the departing agent to replace `<insert-summary>` with a kebab-case summary of their work (max 60 characters, no underscores, lowercase with hyphens).

#### Scenario: Instruction includes filename guidance

- **WHEN** `compose_handoff_instruction()` is called
- **THEN** the output SHALL contain instructions for replacing `<insert-summary>` with a kebab-case summary
- **AND** the existing handoff document requirements SHALL still be present
- **AND** operator context SHALL still be appended if provided

### Requirement: Polling Thread Glob Fallback

The `_poll_for_handoff_file()` method SHALL fall back to globbing for `{timestamp}_*_{agent_tag}.md` when the exact generated path does not exist.

#### Scenario: Exact path not found, glob matches

- **WHEN** the exact generated path does not exist
- **AND** a file matching `{timestamp}_*_{agent_tag}.md` exists and is non-empty
- **THEN** the polling thread SHALL use the matched file path and proceed with handoff completion

#### Scenario: Multiple glob matches

- **WHEN** the glob fallback matches multiple files
- **THEN** a warning SHALL be logged
- **AND** the first match (sorted) SHALL be used

### Requirement: Backward Compatibility with Legacy Filenames

The system SHALL accept mixed filename formats in the handoff directory. Old-format files (`YYYYMMDDTHHmmss-NNNNNNNN.md`) SHALL continue to work with the existing polling mechanism and appear in all listings.

#### Scenario: Legacy files coexist with new format

- **WHEN** the handoff directory contains both old-format and new-format files
- **THEN** all files SHALL appear in listings sorted by filename prefix
