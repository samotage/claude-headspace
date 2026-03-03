# PRD Remediation Plan — Epic 9 Cross-PRD Review Fixes

**Created:** 2026-03-03
**Author:** Robbo
**Source:** `docs/prds/channels/cross-prd-review-report.md` (15 findings)
**Status:** Executed (2026-03-03)

---

## Overview

The cross-PRD adversarial review found 15 issues across the 8 Epic 9 PRDs. This plan groups the fixes into 10 edits (some findings are resolved by the same edit). Each edit specifies the exact file, the section to change, and what the new text should say.

**All 8 PRD files are in:** `docs/prds/channels/`

**After all edits:** Re-run `70: review-prd-set` to confirm all criticals are resolved. Then run `30: prd-validate` on each PRD individually.

---

## Edit 1 — SSE Broadcast Ownership (Finding #1, CRITICAL)

**Decision:** ChannelService (S4) owns all SSE broadcasts. The delivery engine (S6) handles tmux delivery and notifications only — it does NOT broadcast SSE events independently. API routes (S5) do not broadcast.

### Edit 1a — S4: Add broadcast calls to ChannelService

**File:** `e9-s4-channel-service-cli-prd.md`

**Section 6.17 (Existing Services Used):** Replace the broadcaster bullet point:

> - **`src/claude_headspace/services/broadcaster.py`** — `broadcast()` for SSE events. ChannelService calls `broadcaster.broadcast("channel_message", ...)` after persisting a Message and `broadcaster.broadcast("channel_update", ...)` after state-changing operations (member join/leave, status transition, chair transfer, mute/unmute). SSE event schemas are defined in S5 Section 6.5.

**Section 6.3 (ChannelService Class Design):** Add after `_generate_context_briefing`:

```python
    # ── SSE Broadcasting ─────────────────────────────────────
    def _broadcast_message(self, message: Message, channel: Channel) -> None: ...
    def _broadcast_update(self, channel: Channel, update_type: str, detail: dict) -> None: ...
```

**Section 2.1 (In Scope):** Add bullet:

> - SSE broadcasting: `channel_message` events after message persistence, `channel_update` events after state changes (schemas defined in S5)

### Edit 1b — S5: Fix broadcast ownership description

**File:** `e9-s5-api-sse-endpoints-prd.md`

**Section 6.6:** Replace opening paragraph:

> The SSE broadcasts are triggered by ChannelService (S4) as post-commit side effects — not by the route handlers in this blueprint. ChannelService calls `broadcaster.broadcast()` after persisting Messages and after state-changing operations. The route handler's only responsibility is to parse the request, resolve the caller, call the service, and format the HTTP response.

### Edit 1c — S6: Remove SSE broadcast from delivery engine

**File:** `e9-s6-delivery-engine-prd.md`

**FR3 (Delivery per member type):** Update the table — remove SSE broadcast from delivery engine responsibilities:

| Member type | Delivery mechanism | Details |
|---|---|---|
| Agent (internal, online) | tmux `send_text()` | Envelope format. Per-pane lock. State safety check. |
| Agent (internal, offline) | Deferred | No active agent instance. Message persists in channel history. |
| Agent (remote/external) | No delivery action | SSE broadcast already handled by ChannelService (S4). |
| Person (internal — operator) | Notification only | macOS notification via NotificationService. SSE broadcast already handled by ChannelService (S4). |
| Person (external) | No delivery action | SSE broadcast already handled by ChannelService (S4). |

**Section 6.4 (Fan-Out Flow):** Update the flow diagram to remove `broadcaster.broadcast()` calls from the AGENT (remote/external), PERSON (internal), and PERSON (external) branches. Replace with comments: `# SSE already broadcast by ChannelService`.

**Section 2.1 (In Scope):** Remove the bullet about SSE events or change to: "SSE broadcasting is handled by ChannelService (S4) — delivery engine does not broadcast independently"

---

## Edit 2 — Canonical SSE Event Schema (Finding #2, CRITICAL)

**File:** `e9-s6-delivery-engine-prd.md`

**Section 6.13:** Replace the entire JSON schema block with:

> The `channel_message` SSE event uses the canonical schema defined in S5 Section 6.5. The delivery engine does not broadcast this event directly (see Edit 1c above) — ChannelService handles SSE broadcasting. This section is retained for reference only:
>
> See **e9-s5-api-sse-endpoints-prd.md Section 6.5** for the authoritative `channel_message` and `channel_update` event data schemas.

---

## Edit 3 — Operator Persona Runtime Accessor (Finding #3, CRITICAL)

**File:** `e9-s2-persona-type-system-prd.md`

**Section 4 (Functional Requirements):** Add after FR7:

> **FR8: Operator persona runtime accessor**
> The Persona model shall expose a `get_operator()` class method that returns the person/internal Persona record (the operator). Implementation:
> ```python
> @classmethod
> def get_operator(cls) -> "Persona | None":
>     """Return the operator's Persona (person/internal type), or None."""
>     return cls.query.join(PersonaType).filter(
>         PersonaType.type_key == "person",
>         PersonaType.subtype == "internal",
>     ).first()
> ```
> This method is used by S5 (API auth resolution) and S7 (dashboard channel cards) to map a Flask session to the operator's identity.

**Section 3.1 (Functional Success Criteria):** Add item 13:

> 13. `Persona.get_operator()` returns the operator Persona (Sam) with persona_type = person/internal

**File:** `e9-s5-api-sse-endpoints-prd.md`

**Section 6.3 (_resolve_caller):** Replace the `# Fallback: dashboard session (operator)` comment block with:

```python
    # Fallback: dashboard session (operator)
    from ..models import Persona
    operator = Persona.get_operator()
    if operator:
        return operator, None  # No agent for operator
    abort(401)
```

**File:** `e9-s7-dashboard-ui-prd.md`

**Section 6.15:** Update `get_channel_data_for_operator` to show how the operator persona is obtained:

```python
def get_channel_data_for_operator():
    """Fetch active channels with last message for dashboard cards."""
    from claude_headspace.models import Persona
    operator = Persona.get_operator()
    if not operator:
        return []
    # ... rest of function uses operator.id as persona_id ...
```

---

## Edit 4 — Notification Ownership to S6 (Finding #4, CRITICAL)

**File:** `e9-s6-delivery-engine-prd.md`

**Section 6.14:** Expand to include the full NotificationService extension (moving from S7):

> When a message is delivered to an operator (person/internal PersonaType), the delivery engine calls `NotificationService.send_channel_notification()`. This method is added to NotificationService by this sprint.
>
> **NotificationService extension (new method):**
> ```python
> def send_channel_notification(
>     self, channel_slug: str, channel_name: str,
>     persona_name: str, content_preview: str,
>     dashboard_url: str | None = None,
> ) -> bool:
> ```
> Per-channel rate limiting: one notification per channel per 30-second window (configurable via `config.yaml` `notifications.channel_rate_limit_seconds`). Uses a `_channel_rate_limit_tracker` dict keyed by channel slug, same locking pattern as existing `_rate_limit_tracker`.

**Section 6.1 (Files to Modify):** Add:

| File | Change |
|------|--------|
| `src/claude_headspace/services/notification_service.py` | Add `_channel_rate_limit_tracker` dict, `_is_channel_rate_limited()` method, and `send_channel_notification()` method. Per-channel rate limiting (30s window). |

**File:** `e9-s7-dashboard-ui-prd.md`

**Section 6.9:** Replace the entire backend section with:

> **Backend: per-channel rate limiting**
>
> NotificationService is extended with per-channel rate limiting by S6 (delivery engine sprint). This sprint (S7) does not modify NotificationService. The `send_channel_notification()` method is available for the dashboard to call if needed, but the primary notification path is server-side via S6's delivery engine.

**Section 6.1 (Files to Modify):** Remove `notification_service.py` from the table.

**Section 2.1 (In Scope):** Change the notification bullets to:

> - macOS notification integration: channel messages trigger notifications via S6's delivery engine (server-side, already implemented)
> - Notification suppression when operator is actively viewing the channel's chat panel (frontend focus flag — v1 uses 30-second rate limit as sufficient floor; active view suppression is v2)

**FR17-FR20:** Simplify. FR17: "Channel message notifications are handled server-side by S6's delivery engine. No frontend notification trigger needed." FR18: "Per-channel rate limiting is implemented in S6." FR19: "Active view suppression is deferred to v2 — the 30-second rate limit provides a sufficient floor." FR20: Keep as-is (notification content format).

---

## Edit 5 — Remove can_create_channel Duplicate (Finding #5, WARNING)

**File:** `e9-s4-channel-service-cli-prd.md`

**Section 6.9 (Capability Check):** Replace entirely:

> ### 6.9 Capability Check — `can_create_channel`
>
> Channel creation capability is checked via `persona.can_create_channel` — a property defined on the Persona model (S2, FR7). ChannelService does not reimplement this check. The `create_channel()` method calls `persona.can_create_channel` as a precondition:
>
> ```python
> if not creator_persona.can_create_channel:
>     raise NoCreationCapabilityError(
>         f"Error: Persona '{creator_persona.name}' does not have channel creation capability."
>     )
> ```

**FR12:** Update to:

> **FR12: Channel creation capability**
> `create_channel()` shall check `creator_persona.can_create_channel` (property from S2 FR7) before creating a channel. If `False`, raise `NoCreationCapabilityError`.

---

## Edit 6 — Message History Ordering (Finding #6, WARNING)

**File:** `e9-s5-api-sse-endpoints-prd.md`

**Section 6.8 (Cursor Pagination):** Replace the ordering paragraph:

> Messages are returned in chronological order (oldest first), matching the display order in the dashboard chat panel (S7) and CLI history (S4). The `before` parameter loads older messages: to paginate backward, pass the `sent_at` of the oldest message in the current page as `?before=`.

---

## Edit 7 — Fix `muted = false` Column Reference (Finding #7, WARNING)

**File:** `e9-s6-delivery-engine-prd.md`

**FR2:** Replace:

> The delivery engine shall iterate all ChannelMembership records for the message's channel where `status = 'active'`, excluding the membership record matching the sender's persona.

**Section 6.4 (Fan-Out Flow):** Replace the query line:

> ```
> +-- Query ChannelMembership WHERE channel_id=X AND status='active'
> |     AND persona_id != sender_persona_id
> ```

---

## Edit 8 — Agent-to-Membership Linking (Finding #8, WARNING)

**File:** `e9-s4-channel-service-cli-prd.md`

**Section 4 (Functional Requirements):** Add after FR13:

> **FR14: Agent-to-membership linking on agent registration**
> When the session correlator links a new agent to a persona (via `_create_or_update_agent()`), the system shall check for any ChannelMembership where `persona_id = agent.persona_id AND agent_id IS NULL AND status = 'active'` and update `agent_id` to the new agent's ID. This ensures agents spun up via `add_member` are linked to their channel membership when they register.

**Section 6.2 (Files to Modify):** Add:

| File | Change |
|------|--------|
| `src/claude_headspace/services/session_correlator.py` | After persona assignment, query and update ChannelMembership records with NULL agent_id for that persona. |

**Renumber existing FR14-FR15 to FR15-FR16.**

---

## Edit 9 — Caller Identity Resolution Contradiction (Finding #10, WARNING)

**File:** `e9-s4-channel-service-cli-prd.md`

**Section 6.5:** Remove the first code block (the one showing tmux-first order). Keep only the corrected prose and rewrite the code to match:

```python
def resolve_caller() -> Agent:
    """Resolve the calling agent via env var override or tmux pane detection.

    Strategy 1 (override): HEADSPACE_AGENT_ID env var — takes precedence when set.
    Strategy 2 (primary): tmux display-message pane detection.
    """
    # Strategy 1: env var override (takes precedence when set)
    agent_id_str = os.environ.get("HEADSPACE_AGENT_ID")
    if agent_id_str:
        try:
            agent_id = int(agent_id_str)
            agent = Agent.query.filter_by(id=agent_id, ended_at=None).first()
            if agent:
                return agent
        except ValueError:
            pass

    # Strategy 2: tmux pane detection
    try:
        result = subprocess.run(
            ["tmux", "display-message", "-p", "#{pane_id}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            pane_id = result.stdout.strip()
            if pane_id:
                agent = Agent.query.filter_by(
                    tmux_pane_id=pane_id, ended_at=None
                ).first()
                if agent:
                    return agent
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    raise CallerResolutionError(
        "Error: Cannot identify calling agent. "
        "Are you running in a Headspace-managed session?"
    )
```

Remove the paragraph that says "Implementation note: check HEADSPACE_AGENT_ID first if the intent is for testing/override..." and the "Corrected strategy order" section — the code now IS the corrected order.

---

## Edit 10 — Channel Archive Logic (Finding #11, WARNING)

**File:** `e9-s4-channel-service-cli-prd.md`

**Section 6.12 (Channel Status Transitions):** Change the `complete -> archived` row:

| From | To | Trigger | Service method |
|------|----|---------|----------------|
| `complete` | `archived` | Chair or operator calls `archive_channel()` | `archive_channel()` |

**Add FR after the new FR14 (agent-to-membership linking):**

> **FR15: Archive channel**
> `archive_channel(slug, persona)` shall validate the caller is the chair or operator, transition status to `archived`, set `archived_at`, and post a system message. Fail with a clear error if the caller is not the chair or operator, or if the channel is not in `complete` state.

**Section 6.3 (ChannelService Class Design):** Replace the `# ... archive_channel stub` with:

```python
    def archive_channel(self, slug: str, persona) -> Channel: ...
```

---

## Edit 11 — Minor/Info Fixes (Findings #12, #13, #14, #15)

### Finding #12 — SSE commonTypes shared resource note

**File:** `e9-s1-handoff-improvements-prd.md`

**Section 6.8 (Dashboard Rendering):** Add note:

> **Note:** S7 (Dashboard UI) also modifies `sse-client.js` `commonTypes` to add `channel_message` and `channel_update`. Building agents should check for prior modifications to the `commonTypes` array and append rather than replace.

**File:** `e9-s7-dashboard-ui-prd.md`

**Section 6.6 (SSE Event Handling):** Add note:

> **Note:** S1 (Handoff Improvements) also modifies `sse-client.js` `commonTypes` to add `synthetic_turn`. Building agents should check for prior modifications and append.

### Finding #13 — S7 scope statement (resolved by Edit 4)

No additional edit needed — Edit 4 removes the backend modification from S7, making the scope statement accurate.

### Finding #14 — Line number references in S6

**File:** `e9-s6-delivery-engine-prd.md`

**Section 6.15:** Remove "(lines 1543-1615 of hook_receiver.py)" — keep only the structural description of the insertion point.

### Finding #15 — Voice Chat PWA rendering consistency

**File:** `e9-s8-voice-bridge-channels-prd.md`

**Section 6.9 (Voice Chat PWA Channel Display):** Add note:

> **Visual consistency:** Channel message rendering in the Voice Chat PWA should follow the same conventions as S7's dashboard chat panel: operator messages in cyan, agent messages in green, system messages muted and centered. Reference S7 Section 6.7 for the rendering pattern.

---

## Execution Checklist

| # | Edit | PRDs Modified | Finding(s) |
|---|------|--------------|------------|
| 1 | SSE broadcast ownership | S4, S5, S6 | #1 (Critical) |
| 2 | Canonical SSE schema | S6 | #2 (Critical) |
| 3 | Operator persona accessor | S2, S5, S7 | #3 (Critical) |
| 4 | Notification ownership | S6, S7 | #4 (Critical) |
| 5 | Remove can_create_channel dup | S4 | #5 (Warning) |
| 6 | Message history ordering | S5 | #6 (Warning) |
| 7 | Fix muted column reference | S6 | #7 (Warning) |
| 8 | Agent-to-membership linking | S4 | #8 (Warning) |
| 9 | Caller identity contradiction | S4 | #10 (Warning) |
| 10 | Archive logic | S4 | #11 (Warning) |
| 11 | Minor/info fixes | S1, S6, S7, S8 | #12, #13, #14, #15 |

**PRD touch count:**
- S4: Edits 1a, 5, 8, 9, 10 (5 edits — heaviest)
- S6: Edits 1c, 2, 4, 7, 11 (5 edits)
- S5: Edits 1b, 3, 6 (3 edits)
- S7: Edits 3, 4, 11 (3 edits)
- S2: Edit 3 (1 edit)
- S1: Edit 11 (1 edit)
- S8: Edit 11 (1 edit)
- S3: No edits needed

**After execution:** Commit all changes, then re-run `70: review-prd-set` in a new session.
