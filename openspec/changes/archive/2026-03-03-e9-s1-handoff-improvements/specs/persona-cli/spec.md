## ADDED Requirements

### Requirement: CLI Handoff History Command

The system SHALL provide `flask persona handoffs <slug>` to list all handoff files for a persona, reading from the filesystem only.

#### Scenario: Basic listing

- **WHEN** `flask persona handoffs <slug>` is executed
- **THEN** the output SHALL show one line per handoff, newest first, with columns: timestamp, summary slug, agent ID

#### Scenario: Limit option

- **WHEN** `--limit N` is specified
- **THEN** only the N most recent handoffs SHALL be displayed

#### Scenario: Paths option

- **WHEN** `--paths` is specified
- **THEN** each line SHALL include the full absolute file path as an additional column

#### Scenario: Legacy filename format

- **WHEN** the handoff directory contains old-format files (`YYYYMMDDTHHmmss-NNNNNNNN.md`)
- **THEN** they SHALL appear in the listing with `(legacy)` in the summary column

#### Scenario: No handoffs found

- **WHEN** the persona has no handoff files
- **THEN** a message SHALL indicate no handoffs were found

#### Scenario: Invalid persona slug

- **WHEN** the persona slug does not exist
- **THEN** an error message SHALL be displayed
