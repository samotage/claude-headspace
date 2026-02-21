# skill-file-injection Specification

## Purpose
Injects persona skill and experience content into newly registered persona-backed agents as their first user message via tmux bridge, enabling agents to operate in character.

## ADDED Requirements

### Requirement: Skill file injection for persona-backed agents

When an agent is registered with a `persona_id` and a `tmux_pane_id`, the system SHALL read the persona's `skill.md` and `experience.md` from disk, compose a priming message, and deliver it to the agent's tmux pane via `send_text()`.

#### Scenario: Successful injection with both files
- **WHEN** an agent is registered with `persona_id` set, `tmux_pane_id` set, and both `skill.md` and `experience.md` exist on disk
- **THEN** a priming message containing both skill and experience content is sent to the agent's tmux pane, and an INFO log records the successful injection with agent ID and persona slug

#### Scenario: Injection with skill.md only (experience.md missing)
- **WHEN** an agent is registered with `persona_id` set, `skill.md` exists, but `experience.md` does not exist
- **THEN** a priming message containing only skill content is sent, and a DEBUG log notes the missing experience file

#### Scenario: Missing skill.md skips injection
- **WHEN** an agent is registered with `persona_id` set, but `skill.md` does not exist on disk
- **THEN** no priming message is sent, a WARNING log records the missing skill file, and the agent starts without persona priming

### Requirement: Backward compatibility for non-persona agents

Agents without a `persona_id` SHALL receive no injection. The existing anonymous agent startup flow is completely unaffected.

#### Scenario: Agent without persona
- **WHEN** an agent is registered without a `persona_id`
- **THEN** no injection occurs, no skill file reads are attempted, and no additional logs are generated

### Requirement: Injection idempotency

The system SHALL track whether injection has been performed for each agent session. Duplicate triggers (e.g., duplicate session-start hooks) SHALL be no-ops.

#### Scenario: Duplicate trigger
- **WHEN** injection is triggered for an agent that has already received injection in the current session
- **THEN** the duplicate is silently skipped (DEBUG log), and no second priming message is sent

### Requirement: Health check before injection

Before sending the priming message, the system SHALL verify the agent's tmux pane is healthy via `check_health()` at COMMAND level minimum. If unhealthy, injection is skipped with a warning.

#### Scenario: Unhealthy tmux pane
- **WHEN** the tmux pane health check returns unhealthy (pane missing or no Claude Code process)
- **THEN** injection is skipped, a WARNING log records the health check failure, and the agent starts without priming

### Requirement: Fault isolation

Injection failures SHALL NOT block agent registration, crash the server, or affect other agents. All exceptions during injection are caught and logged.

#### Scenario: Send failure
- **WHEN** `tmux_bridge.send_text()` raises an exception during priming delivery
- **THEN** the exception is logged at ERROR level, the agent continues to operate normally without priming, and other agents are unaffected

### Requirement: Injection logging

Every injection attempt SHALL be logged with: agent ID, persona slug, and outcome (success, skipped, failed) with reason for skip/failure.

#### Scenario: Successful injection logged
- **WHEN** priming is successfully delivered to agent 42 with persona slug "developer-con-1"
- **THEN** an INFO log contains the agent ID 42, persona slug "developer-con-1", and outcome "success"
