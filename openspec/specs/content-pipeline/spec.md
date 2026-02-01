# content-pipeline Specification

## Purpose
TBD - created by archiving change e3-s6-content-pipeline. Update Purpose after archive.
## Requirements
### Requirement: Hook-Driven Input-Needed Detection

The system SHALL receive Notification hook events with `notification_type` of `elicitation_dialog`, `permission_prompt`, or `idle_prompt` and transition the associated agent's task to AWAITING_INPUT state within 100ms of hook receipt.

#### Scenario: AskUserQuestion triggers input-needed state

- **WHEN** a Notification hook fires with `notification_type: elicitation_dialog`
- **THEN** the associated agent's active task transitions to AWAITING_INPUT
- **AND** the `message` and `title` from the Notification payload are stored as turn context

#### Scenario: Permission dialog triggers input-needed state

- **WHEN** a Notification hook fires with `notification_type: permission_prompt`
- **THEN** the associated agent's active task transitions to AWAITING_INPUT
- **AND** the `message` and `title` from the Notification payload are stored as turn context

#### Scenario: Idle prompt triggers input-needed state

- **WHEN** a Notification hook fires with `notification_type: idle_prompt`
- **THEN** the associated agent's active task transitions to AWAITING_INPUT

---

### Requirement: PostToolUse Resumption Signal

The system SHALL receive PostToolUse hook events and, when the associated agent's task is in AWAITING_INPUT state, transition it back to PROCESSING state.

#### Scenario: User answers question and agent resumes

- **WHEN** a PostToolUse hook event is received
- **AND** the agent's current task is in AWAITING_INPUT state
- **THEN** the task transitions to PROCESSING state

#### Scenario: PostToolUse when not awaiting input

- **WHEN** a PostToolUse hook event is received
- **AND** the agent's current task is NOT in AWAITING_INPUT state
- **THEN** no state transition occurs
- **AND** the event is logged for audit purposes

#### Scenario: PreToolUse is not used as resumption signal

- **WHEN** PreToolUse events are considered
- **THEN** they SHALL NOT be used as resumption signals
- **BECAUSE** PreToolUse fires before input-needed states, not after

---

### Requirement: Transcript Path Capture

The system SHALL capture `transcript_path` from hook event payloads and persist it on the Agent model.

#### Scenario: SessionStart provides transcript path

- **WHEN** a SessionStart hook fires with `transcript_path` in the payload
- **THEN** the `transcript_path` is stored on the Agent record

#### Scenario: Transcript path available on subsequent hooks

- **WHEN** any hook fires with `transcript_path` and the Agent's `transcript_path` is null
- **THEN** the `transcript_path` is backfilled on the Agent record

---

### Requirement: Agent Response Text Capture

On receiving a Stop hook event, the system SHALL read the agent's transcript `.jsonl` file and extract the agent's last response text to populate the AGENT/COMPLETION turn.

#### Scenario: Successful transcript content extraction

- **WHEN** a Stop hook event is received
- **AND** the agent has a valid `transcript_path`
- **THEN** the system reads the transcript `.jsonl` file
- **AND** extracts the agent's last response text
- **AND** populates the AGENT/COMPLETION turn's `text` field (truncated to configurable max)

#### Scenario: Missing transcript file

- **WHEN** a Stop hook event is received
- **AND** the transcript file does not exist or is unreadable
- **THEN** the turn's `text` field remains empty
- **AND** a warning is logged

#### Scenario: Transcript read performance

- **WHEN** the transcript file is read on Stop hook
- **THEN** the read MUST complete within 500ms for typical transcript sizes

---

### Requirement: File Watcher Content Pipeline

The file watcher SHALL monitor registered transcript files for new entries and process them through a content pipeline that includes regex-based question detection and timeout-gated inference.

#### Scenario: Regex detects obvious question pattern

- **WHEN** new agent output is detected in the transcript
- **AND** regex matches a question pattern (e.g., ends with "?", contains "would you like", "should I")
- **THEN** the system transitions the agent's task to AWAITING_INPUT
- **AND** no inference call is made

#### Scenario: Ambiguous output triggers inference after timeout

- **WHEN** new agent output is detected in the transcript
- **AND** regex does not match a question pattern
- **AND** no PostToolUse or Stop hook arrives within `awaiting_input_timeout` seconds
- **THEN** the system sends the output to inference for question classification

#### Scenario: Inference classifies output as question

- **WHEN** inference classifies agent output as a question
- **THEN** the system transitions the agent's task to AWAITING_INPUT

#### Scenario: Activity cancels timeout timer

- **WHEN** a PostToolUse or Stop hook event arrives for an agent
- **AND** an `awaiting_input_timeout` timer is active for that agent
- **THEN** the timer is cancelled
- **AND** no inference call is made

---

### Requirement: Configuration

The `awaiting_input_timeout` value SHALL be configurable in `config.yaml` under the `file_watcher` section.

#### Scenario: Default configuration

- **WHEN** `awaiting_input_timeout` is not specified in `config.yaml`
- **THEN** the default value of 10 seconds is used

#### Scenario: Custom configuration

- **WHEN** `awaiting_input_timeout` is set to N seconds in `config.yaml`
- **THEN** the file watcher uses N seconds as the timeout before triggering inference

---

### Requirement: Intelligence Integration

Captured agent turn text SHALL be passed through the existing summarisation and priority scoring services.

#### Scenario: Turn summaries from real content

- **WHEN** an AGENT/COMPLETION turn has non-empty text
- **THEN** the summarisation service generates a summary from the actual content
- **AND** the summary reflects what the agent actually did

#### Scenario: Priority scoring with real context

- **WHEN** task summaries are generated from real content
- **THEN** priority scoring rankings incorporate actual task context
- **AND** "recommended next" rankings are meaningful

---

### Requirement: Hook Installer Update

The hook installer SHALL configure new Notification matchers and PostToolUse hooks.

#### Scenario: Notification matchers installed

- **WHEN** `bin/install-hooks.sh` is run
- **THEN** Notification hooks with matchers for `elicitation_dialog`, `permission_prompt`, and `idle_prompt` are configured

#### Scenario: PostToolUse hooks installed

- **WHEN** `bin/install-hooks.sh` is run
- **THEN** PostToolUse hooks are configured to send events to the Headspace server

#### Scenario: All hooks use async mode

- **WHEN** hook commands are configured
- **THEN** they use `async: true` where they do not need to control Claude Code behavior
- **AND** all hooks complete within 1 second

---

