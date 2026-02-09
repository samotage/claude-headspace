## Why

Claude Headspace currently requires users to be at their Mac to respond to agent questions. When agents block on input, idle time accumulates. The Voice Bridge Server provides backend API infrastructure for hands-free voice interaction from mobile devices on the same LAN — enabling agents to resume without the user touching their keyboard.

## What Changes

### Turn Model Enhancement
- Add `question_text` (TEXT) column to Turn for explicit question text storage
- Add `question_options` (JSONB) column to Turn for structured option data (labels, descriptions)
- Add `question_source_type` (VARCHAR) column to Turn: `ask_user_question`, `permission_request`, `free_text`
- Add `answered_by_turn_id` (FK to turns.id) column on ANSWER turns linking back to the QUESTION they resolve
- Alembic migration for new columns

### Voice Bridge API (new Flask blueprint)
- `POST /api/voice/command` — submit voice command to agent (FR4)
- `GET /api/voice/sessions` — list active agents with voice-friendly status (FR5)
- `GET /api/voice/agents/<agent_id>/output` — recent agent activity/output (FR6)
- `GET /api/voice/agents/<agent_id>/question` — full question context for AWAITING_INPUT agent (FR7)
- All responses use voice-friendly format: status line + key results + next action (FR8)
- `verbosity` query parameter: concise (default), normal, detailed (FR9)
- Voice-friendly error responses (FR10, FR16, FR17, FR18)

### Voice Output Formatting
- New `VoiceFormatter` service for LLM-powered voice output formatting
- Register prompt templates in PromptRegistry for voice formatting
- Verbosity levels: concise/normal/detailed (FR9)

### Question Passthrough
- Free-text questions (detected by intent_detector, no AskUserQuestion options) preserve full question text in Turn record (FR11)
- Question detail API distinguishes structured vs free-text questions (FR12)

### Authentication & Network
- Token-based auth middleware scoped to voice blueprint via `before_request` (FR13)
- Localhost bypass option (configurable) (FR13)
- Network binding config: `voice_bridge.network.bind_address` (localhost vs 0.0.0.0) (FR14)
- Access logging for all voice API requests (FR15)

### Configuration
- New `voice_bridge` section in config.yaml with: enabled, auth token, localhost_bypass, bind_address, rate_limit, verbosity default

## Impact

- Affected specs: turn-model, voice-bridge (new)
- Affected code:
  - `src/claude_headspace/models/turn.py` — new columns
  - `src/claude_headspace/routes/voice_bridge.py` — new blueprint (4 endpoints)
  - `src/claude_headspace/services/voice_formatter.py` — new service
  - `src/claude_headspace/services/voice_auth.py` — new auth middleware
  - `src/claude_headspace/services/prompt_registry.py` — new prompt templates
  - `src/claude_headspace/services/hook_receiver.py` — populate new Turn columns
  - `src/claude_headspace/app.py` — register blueprint + services
  - `src/claude_headspace/config.py` — voice_bridge config defaults
  - `config.yaml` — voice_bridge section
  - `run.py` — bind_address from config
  - `migrations/versions/` — new migration for Turn columns
- Related OpenSpec history:
  - e5-s1-input-bridge (2026-02-02)
  - e5-s4-tmux-bridge (2026-02-04)
  - e5-s8-cli-tmux-bridge (2026-02-06)
