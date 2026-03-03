# Proposal: e9-s4-channel-service-cli

## Why

Channels exist as database tables (Sprint 3) but have no business logic or user-facing interface. Agents cannot create channels, send messages, or manage memberships. Without a centralised ChannelService, each future frontend (API, dashboard, voice bridge) would implement its own validation and state transitions — leading to inconsistency. This sprint creates the single service class that all channel operations flow through, plus the CLI layer that agents use to interact with channels from their terminal sessions.

## What Changes

- Create `ChannelService` class registered as `app.extensions["channel_service"]` — all channel business logic: CRUD, lifecycle transitions, membership management, message send/history, capability checks, SSE broadcasting
- Create `caller_identity.py` — shared caller identity resolution (env var override + tmux pane detection) for CLI and future API use
- Create `flask channel` CLI group — 10 subcommands: create, list, show, members, add, leave, complete, transfer-chair, mute, unmute
- Create `flask msg` CLI group — 2 subcommands: send, history (with conversational envelope and YAML output formats)
- Modify `app.py` — register ChannelService in extensions, register CLI command groups
- Modify `session_correlator.py` or `hook_receiver.py` — after persona assignment, link agent to pending ChannelMembership records (FR14) and deliver context briefings (FR14a)

## Impact

### Affected specs
- `channel-data-model` — existing spec (S3). This change builds business logic on top of those models. No model changes required.
- `session-correlator-persona` — existing spec. Modified to link agents to channel memberships on persona assignment.

### Affected code

**New files:**
- `src/claude_headspace/services/channel_service.py` — ChannelService class with all channel business logic, error hierarchy (7 exception subclasses)
- `src/claude_headspace/services/caller_identity.py` — Caller identity resolution utility (CallerResolutionError, resolve_caller function)
- `src/claude_headspace/cli/channel_cli.py` — `flask channel` CLI group (10 subcommands)
- `src/claude_headspace/cli/msg_cli.py` — `flask msg` CLI group (2 subcommands)

**Modified files:**
- `src/claude_headspace/app.py` — Import and register ChannelService, import and register channel_cli and msg_cli
- `src/claude_headspace/services/hook_receiver.py` — After persona assignment in process_session_start, query ChannelMembership records with NULL agent_id for that persona and update agent_id; deliver context briefings

### Breaking changes
None — this is additive. All new code, no existing behaviour modified.
