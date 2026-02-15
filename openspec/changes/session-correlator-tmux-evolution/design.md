## Context

The session correlator maps Claude Code hook events to Agent records via a cascade of strategies. A recent uncommitted fix added tmux_pane_id correlation (Strategy 2.75) to handle context compression. The strategy numbering has become messy (1, 2, 2.5, 2.75, 3, 4) through incremental additions.

Agents running in tmux sessions have a session name (e.g. `hs-claude-headspace-14100608`) created by the CLI launcher. This name is the key users need to `tmux attach -t <name>` — but it isn't stored anywhere on the Agent model. Users who start agents remotely via voice bridge currently have to SSH in and manually run `tmux ls` to find the session name before they can attach.

The dashboard already has iTerm2 focus infrastructure (`iterm_focus.py`, `/api/focus/<agent_id>`) that brings existing terminal windows to the foreground. The attach action is different: it creates a *new* iTerm2 tab and connects it to a tmux session, which may not currently have any iTerm client attached.

## Goals / Non-Goals

**Goals:**
- Clean up strategy numbering to sequential 1–6
- Persist tmux session name on Agent model for retrieval
- Provide one-click dashboard action to attach to an agent's tmux session via iTerm2
- Expose tmux_session in card state for frontend use

**Non-Goals:**
- Changing the correlation strategy logic or ordering (only renumbering)
- Supporting terminals other than iTerm2 (Terminal.app, Alacritty, etc.)
- Detaching existing tmux clients before attaching (tmux supports multiple clients)
- Auto-attaching on agent creation — this is an on-demand user action
- Supporting non-tmux agents for the attach action (they use the existing focus path)

## Decisions

### D1: Tmux session name capture via env var in launcher

**Decision:** Set `CLAUDE_HEADSPACE_TMUX_SESSION=<session_name>` as an environment variable in the launcher, alongside the existing `CLAUDE_HEADSPACE_SESSION_ID`. The hook script reads it from the environment and includes it in the JSON payload.

**Alternatives considered:**
- *Extract via `tmux display-message -p '#S'` in the hook script:* Works but adds a subprocess call to every hook invocation (~8 hooks per lifecycle). The env var approach is zero-cost at hook time.
- *Query tmux server from Flask on first hook:* Adds complexity and requires mapping pane ID to session name server-side. The launcher already knows the session name — passing it through is simpler.

**Rationale:** The launcher creates the tmux session and knows the name. Passing it as an env var follows the established pattern (`CLAUDE_HEADSPACE_SESSION_ID`). The hook script already reads env vars and forwards them. No new subprocess calls, no new server-side tmux queries.

### D2: Store tmux_session on Agent model (not on a separate table)

**Decision:** Add a nullable `String(128)` column `tmux_session` directly to the `agents` table via Alembic migration.

**Alternatives considered:**
- *Separate tmux_connections table:* Over-engineered for a simple nullable string. One agent has at most one tmux session.
- *Store on Project model:* Incorrect — different agents for the same project have different tmux sessions.

**Rationale:** Follows the existing pattern of `tmux_pane_id` and `iterm_pane_id` as nullable columns on Agent. One agent = one tmux session. Simple, queryable, no joins needed.

### D3: Backfill tmux_session via existing _backfill_tmux_pane pattern in hook_lifecycle_bridge

**Decision:** Extend the existing tmux pane backfill logic in `hook_lifecycle_bridge.py` to also set `agent.tmux_session` when the `tmux_session` field is present in the hook payload. This runs on every hook event that goes through session correlation, so the value is captured on the first hook from any session.

**Alternatives considered:**
- *Set only on session-start hook:* Misses agents created before this change (they'd never get backfilled). Setting on every hook is idempotent and catches agents retroactively.
- *New dedicated backfill function:* Unnecessary — the existing backfill runs on every hook and already sets `tmux_pane_id`. Adding `tmux_session` to the same function is natural.

### D4: New `/api/agents/<id>/attach` endpoint (not extending `/api/focus/<id>`)

**Decision:** Create a separate `POST /api/agents/<id>/attach` endpoint rather than adding attach logic to the existing focus endpoint.

**Alternatives considered:**
- *Extend `/api/focus/<id>` with a query param like `?action=attach`:* Conflates two distinct operations. Focus brings an existing window to the foreground; attach creates a new terminal connection. Different failure modes, different requirements (focus needs pane ID, attach needs session name).
- *Client-side only (no endpoint):* Not possible — AppleScript must run on the server (same machine as iTerm2), not in the browser.

**Rationale:** Focus and attach are semantically different. Focus finds an existing iTerm2 window/pane. Attach opens a new iTerm2 tab and runs `tmux attach -t`. Separate endpoints keep the API clear and error handling specific. The endpoint can live in the same `focus.py` blueprint.

### D5: AppleScript approach for tmux attach

**Decision:** New function `attach_tmux_session(session_name)` in `iterm_focus.py` that:
1. Checks if an iTerm2 tab already has the tmux session attached (by scanning session TTYs and matching against `tmux list-clients`)
2. If found, focuses that existing tab (reuse)
3. If not found, opens a new iTerm2 tab and runs `tmux attach -t <session_name>`

**Alternatives considered:**
- *Always open a new tab:* Creates duplicate tmux client connections. Users who click attach twice would get two tabs attached to the same session.
- *Use `tmux switch-client` instead of `tmux attach`:* Only works when the user is already in a tmux session. `attach` works from any terminal.

**Rationale:** Reusing an existing attached tab is the expected UX — users don't want duplicate connections. The check is cheap (one `tmux list-clients` call + iTerm2 session scan). The `tmux attach -t` fallback is the standard way to connect to a tmux session.

### D6: Strategy renumbering is code-only (no migration, no persisted data)

**Decision:** Renumber strategies 1–6 in code comments, docstrings, log messages, tests, and the `correlation_method` return values. No database changes needed — `correlation_method` is only used in log messages and the in-memory `CorrelationResult` NamedTuple, not persisted to the database.

**Alternatives considered:**
- *Keep old numbering:* Technical debt accumulates. The fractional numbering is confusing for debugging log analysis.

**Mapping:**
| Old | New | Strategy |
|-----|-----|----------|
| 1 | 1 | Memory cache |
| 2 | 2 | DB claude_session_id |
| 2.5 | 3 | Headspace session UUID |
| 2.75 | 4 | Tmux pane ID |
| 3 | 5 | Working directory |
| 4 | 6 | Create new agent |

## Risks / Trade-offs

**[Env var not set for non-launcher sessions]** → Agents started outside the CLI launcher (e.g. raw `claude` in a tmux pane) won't have `CLAUDE_HEADSPACE_TMUX_SESSION` set. The attach button simply won't appear for these agents (tmux_session will be NULL). The hook script could fall back to `tmux display-message -p '#S'` as a secondary capture, but this is a non-goal for v1 — the launcher is the standard entry point.

**[AppleScript permission requirements]** → The attach AppleScript needs the same Automation permissions as existing focus. No new permission grants needed since focus already requires iTerm2 Automation access.

**[Multiple tmux clients]** → Tmux supports multiple clients attached to the same session. If a user attaches from the dashboard while another client is already attached, both see the same content. This is expected tmux behaviour and not a problem.

**[Session name uniqueness]** → Tmux session names are unique system-wide (tmux enforces this). The launcher generates them with a random suffix (`hs-{project}-{hex8}`), so collisions are effectively impossible.

**[Stale tmux_session after tmux kill-session]** → If a tmux session is killed externally, `agent.tmux_session` becomes stale. The attach endpoint should verify the session exists (`tmux has-session -t <name>`) before attempting to attach, returning an appropriate error if not found.

## Migration Plan

1. Add `tmux_session` column to agents table (Alembic migration, nullable, no default)
2. Deploy code changes — existing agents get tmux_session populated on their next hook event
3. No backfill migration needed — the hook-based backfill handles it incrementally
4. Rollback: Drop the column. The attach feature degrades to "not available" (button hidden).

## Open Questions

None — the design is straightforward and builds on established patterns.
