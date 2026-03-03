# Cross-PRD Review Report

**Epic/Subsystem:** Epic 9 — Inter-Agent Communication (Channels)
**PRDs Reviewed:** 8
**Review Date:** 2026-03-03
**Reviewer:** Adversarial Cross-PRD Review (70: review-prd-set) — Robbo

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 4 |
| 🟡 Warning | 7 |
| 🔵 Info | 4 |
| **Total Findings** | **15** |

**Overall Assessment:** The individual PRDs are well-structured and thorough — each one in isolation reads cleanly. But the seams between them are where it falls apart. There is a three-way contradiction about who broadcasts SSE events (S4, S5, and S6 all have different stories), the `channel_message` SSE event schema is defined differently in two PRDs, and critical runtime plumbing (operator persona identity resolution, agent-to-membership linking) falls through the cracks — nobody owns it. These need resolution before orchestration picks them up, or building agents will stall at integration points.

---

## PRDs Under Review

| # | PRD | Sprint | FRs | Est. Tasks |
|---|-----|--------|-----|------------|
| 1 | e9-s1-handoff-improvements-prd.md | S1 | 15 | ~12 |
| 2 | e9-s2-persona-type-system-prd.md | S2 | 7 | ~8 |
| 3 | e9-s3-channel-data-model-prd.md | S3 | 12 | ~10 |
| 4 | e9-s4-channel-service-cli-prd.md | S4 | 16 | ~25 |
| 5 | e9-s5-api-sse-endpoints-prd.md | S5 | 18 | ~18 |
| 6 | e9-s6-delivery-engine-prd.md | S6 | 15 | ~20 |
| 7 | e9-s7-dashboard-ui-prd.md | S7 | 20 | ~22 |
| 8 | e9-s8-voice-bridge-channels-prd.md | S8 | 16 | ~16 |

---

## Findings

### Finding 1: SSE Broadcast Ownership — Three-Way Contradiction

- **Severity:** 🔴 Critical
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s4, e9-s5, e9-s6
- **Detail:**

  Three PRDs tell three different stories about who broadcasts `channel_message` and `channel_update` SSE events:

  - **S4** (Section 6.17, Existing Services Used): *"broadcaster... Not called directly by ChannelService in this sprint (SSE broadcasting is S5), but the service should be designed to allow S5 to add broadcast calls as post-commit hooks."* — S4 doesn't broadcast.

  - **S5** (Section 6.6): *"The SSE broadcasts are triggered by ChannelService (S4), not by the route handlers."* — S5 says S4 broadcasts. But S4 was told not to. And S5's Files to Modify (6.11) does NOT list `channel_service.py`.

  - **S6** (FR3, Section 6.4): The delivery engine broadcasts `channel_message` SSE events for operators and remote agents as part of fan-out delivery.

  Net result: S4 doesn't broadcast. S5 says S4 should but doesn't modify S4 to add it. S5 doesn't broadcast from routes either. S6 broadcasts as part of delivery. **Nobody adds the broadcast calls to ChannelService**, yet S5 architecturally asserts the service should be the broadcast origin for all frontends.

- **Impact:** Building agents for S5 and S6 will conflict. If S6's delivery broadcast is the only broadcast that fires, then the `channel_message` SSE events only reach the dashboard when messages are delivered by the delivery engine — but the delivery engine excludes the sender. The sender's own message would never appear in their own chat panel via SSE (they'd rely on optimistic rendering only, with no SSE confirmation). If S5 adds its own broadcasts in routes, the operator gets duplicate events (one from the route, one from S6 delivery).

- **Recommendation:** Decide on ONE ownership model and propagate it to all three PRDs:
  - **Option A (Recommended):** ChannelService (S4) broadcasts `channel_message` and `channel_update` for ALL consumers (including the sender) as a post-commit side effect. S6's delivery engine handles tmux/notification delivery but does NOT independently broadcast SSE — it relies on the service's broadcast. S5 routes do not broadcast. Update S4 to add broadcast calls, update S5 section 6.6 to match, update S6 to remove SSE broadcast from delivery.
  - **Option B:** S6 delivery engine is the sole SSE broadcast origin. S4 and S5 do not broadcast. The delivery engine must include the sender in SSE broadcast (even though it excludes the sender from tmux delivery). Update S4, S5, and S6 accordingly.

---

### Finding 2: `channel_message` SSE Event Schema Mismatch

- **Severity:** 🔴 Critical
- **Dimension:** 4. Terminology Consistency
- **PRDs Involved:** e9-s5, e9-s6
- **Detail:**

  The `channel_message` SSE event is defined with different schemas in two PRDs:

  **S5** (Section 6.5):
  ```json
  {
    "channel_slug": "...",
    "message_id": 42,
    "persona_slug": "architect-robbo-3",
    "persona_name": "Robbo",
    "content_preview": "...",
    "message_type": "message",
    "sent_at": "2026-03-03T10:23:45Z"
  }
  ```

  **S6** (Section 6.13):
  ```json
  {
    "channel_id": 42,
    "channel_slug": "architecture-review",
    "message_id": 789,
    "persona_id": 15,
    "persona_name": "Robbo",
    "agent_id": 1053,
    "text": "Message content...",
    "message_type": "message",
    "timestamp": "2026-03-03T12:00:00Z"
  }
  ```

  Key differences:
  - S5 uses `content_preview`, S6 uses `text`
  - S5 uses `sent_at`, S6 uses `timestamp`
  - S5 includes `persona_slug`, S6 includes `persona_id` and `agent_id` instead
  - S6 includes `channel_id` (integer), S5 does not

  S7 (Section 6.6) references S5's schema. If S6 broadcasts with a different schema, S7's dashboard JS won't parse events correctly.

- **Impact:** S7's dashboard JS handlers expect S5's field names. If S6 emits events with S6's field names, channel cards and the chat panel will fail silently (fields will be `undefined`). This is the kind of bug that passes unit tests but breaks the live app.

- **Recommendation:** Canonise ONE schema in S5 (the SSE definition sprint) and mandate that all emitters (S4, S6, or whoever broadcasts — see Finding 1) use that exact schema. Remove the conflicting schema definition from S6 section 6.13 and replace with a reference: "Uses the `channel_message` SSE event schema defined in S5 Section 6.5."

---

### Finding 3: Operator Persona Identity Resolution — Nobody Builds It

- **Severity:** 🔴 Critical
- **Dimension:** 6. Gap Detection (Inter-PRD)
- **PRDs Involved:** e9-s2, e9-s5, e9-s7
- **Detail:**

  Multiple sprints need to resolve "the operator" to a Persona record at runtime:

  - **S5** (Section 6.3, `_resolve_caller()`): For dashboard session cookie auth, needs to resolve the Flask session to the operator's persona. The code shows `# Fallback: dashboard session (operator) ... Dashboard session represents the operator — resolve to operator persona ...` with no implementation.

  - **S7** (Section 6.15): The dashboard route handler needs `operator_persona_id` to query the operator's channel memberships for rendering channel cards. `get_channel_data_for_operator(operator_persona_id)` — but where does `operator_persona_id` come from?

  **S2** creates the operator Persona in a migration (FR6) with name "Sam", role "operator", persona_type = person/internal. But S2 provides no service method, no helper function, and no query pattern for looking up this persona at runtime. The migration creates the record; nobody provides the runtime accessor.

  The Flask session does not contain a `persona_id`. There is no documented mapping from "authenticated dashboard user" to "the operator Persona record." This is infrastructure that both S5 and S7 assume exists but neither creates.

- **Impact:** S5's API routes and S7's dashboard will both fail to identify the operator. Without operator identity, the operator cannot send messages, view channels, or have channel cards rendered. This blocks the entire operator-facing channel experience.

- **Recommendation:** Add an explicit FR to either S2 or S4:
  - A service method or model class method: `Persona.get_operator()` → returns the person/internal Persona, or `None`.
  - Implementation: `Persona.query.join(PersonaType).filter(PersonaType.type_key == "person", PersonaType.subtype == "internal").first()` (or query by role name "operator").
  - S5 and S7 both reference this method for operator identity resolution.
  - Consider also storing `operator_persona_id` in config or as an app-level constant for fast lookup.

---

### Finding 4: Notification Integration — Dual Ownership

- **Severity:** 🔴 Critical
- **Dimension:** 1. Scope Overlap
- **PRDs Involved:** e9-s6, e9-s7
- **Detail:**

  Both S6 and S7 claim to implement per-channel notification rate limiting for operator channel messages:

  - **S6** (Section 6.14): *"When a message is delivered to an operator (person/internal PersonaType), the delivery engine calls NotificationService for macOS notification. Per Decision 3.4, per-channel rate limiting applies: one notification per channel per 30-second window. The rate limiting is implemented inside the delivery engine (not in NotificationService itself)."*

  - **S7** (Section 6.9): Extends `NotificationService` with a new `_channel_rate_limit_tracker` dict, a `_is_channel_rate_limited()` method, and a `send_channel_notification()` method. Rate limiting is implemented INSIDE NotificationService.

  These are contradictory implementations of the same feature. S6 puts rate limiting in the delivery engine. S7 puts it in NotificationService. Both claim ownership.

  Additionally, S7 says (scope, 2.1): "This sprint produces no new backend services, models, or API endpoints." But Section 6.9 modifies `NotificationService` — a backend service. This contradicts S7's own scope statement.

- **Impact:** If both sprints implement rate limiting, there will be double rate limiting (delivery engine checks AND NotificationService checks) or conflicting implementations. If only one is built, the other's tests will fail.

- **Recommendation:** Assign notification ownership to ONE sprint. Recommended: S6 owns operator delivery (it already handles all per-member-type delivery). S6 should extend NotificationService with `send_channel_notification()` (S7's design is cleaner here). S7 then calls the existing method — no backend changes needed in S7, matching S7's own scope claim.

---

### Finding 5: `can_create_channel` — Dual Implementation

- **Severity:** 🟡 Warning
- **Dimension:** 1. Scope Overlap
- **PRDs Involved:** e9-s2, e9-s4
- **Detail:**

  Both S2 and S4 define `can_create_channel` with identical logic:

  - **S2** FR7: A `@property` on the Persona model. Returns `True` for internal personas, `False` for external.

  - **S4** Section 6.9: A method on ChannelService with the same logic: check `persona.persona_type.subtype != "external"`, return `True` for internal. S4 FR12 describes it as a "service-layer method."

  Two implementations of the same check means they can drift. S4's service method essentially duplicates S2's model property.

- **Impact:** If one is updated without the other, authorization checks become inconsistent. A persona might pass the model check but fail the service check, or vice versa. Building agents may be confused about which to call.

- **Recommendation:** Keep ONE implementation. S2's model property is the right location (capability is an intrinsic property of the persona, not a service concern). Remove the service-level `can_create_channel` from S4 section 6.9 and have S4's `create_channel()` call `persona.can_create_channel` (the property from S2). Update S4 FR12 to say: "Channel creation capability is checked via `persona.can_create_channel` property (defined in S2). ChannelService does not reimplement this check."

---

### Finding 6: Message History Ordering Contradiction

- **Severity:** 🟡 Warning
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s4, e9-s5, e9-s7
- **Detail:**

  - **S4** FR11: *"Return messages ordered by `sent_at` ascending"* (oldest first).
  - **S5** Section 6.8: *"Messages are returned in reverse chronological order (newest first)."*
  - **S7** FR7: *"Messages in chronological order, newest at the bottom."* (This implies oldest first when reading top-to-bottom — matches S4.)

  The service (S4) and UI (S7) want chronological (oldest first). The API (S5) specifies reverse chronological (newest first). If the API returns newest first and the chat panel renders top-to-bottom, the frontend must reverse the array. This isn't fatal but is an unnecessary impedance mismatch.

- **Impact:** If S7's building agent calls the API expecting oldest-first (matching S4) but gets newest-first (per S5), the chat feed renders backward. S5's cursor pagination design (`?before=` as primary cursor) also implies newest-first semantics.

- **Recommendation:** Align on ONE ordering. The API should return chronological (oldest first) for chat-feed consumption, since both primary consumers (dashboard chat panel in S7, CLI history in S4) display oldest-first. S5 Section 6.8 should say "chronological order (oldest first)" and `?before=` loads _older_ messages. The `before` cursor still works — it just means "messages older than this timestamp, in chronological order."

---

### Finding 7: `muted = false` References Non-Existent Column

- **Severity:** 🟡 Warning
- **Dimension:** 4. Terminology Consistency
- **PRDs Involved:** e9-s3, e9-s6
- **Detail:**

  S3 defines `ChannelMembership.status` as a `String(16)` column with values `"active"`, `"left"`, `"muted"`. There is no boolean `muted` column.

  S6 FR2 says: *"The delivery engine shall iterate all ChannelMembership records for the message's channel where `muted = false`."*

  `muted = false` implies a boolean column. The correct filter is `status != 'muted'` (and probably `status = 'active'` to also exclude `left` members).

- **Impact:** A building agent implementing S6 FR2 literally would write `filter_by(muted=False)`, which would fail with an `AttributeError` — there is no `muted` attribute on ChannelMembership.

- **Recommendation:** Update S6 FR2 to: *"where `status = 'active'` (excluding muted and left members)"*. Grep S6 for any other `muted` boolean references and fix them to use the status column.

---

### Finding 8: Agent-to-Membership Linking — Unowned Gap

- **Severity:** 🟡 Warning
- **Dimension:** 6. Gap Detection (Inter-PRD)
- **PRDs Involved:** e9-s4, e9-s6
- **Detail:**

  S4 Section 6.13 (`_spin_up_agent_for_persona`): When a persona is added to a channel and has no running agent, the membership is created with `agent_id=NULL`. The comment says: *"When the agent starts and registers via the session-start hook, the session correlator links it to the persona, and a separate mechanism (outside this sprint's scope) updates the channel membership's agent_id."*

  No sprint claims ownership of this "separate mechanism." The session correlator (existing code) links agents to personas but knows nothing about channel memberships. When a new agent spins up and registers, nobody updates `ChannelMembership.agent_id` from NULL to the new agent's ID.

- **Impact:** Agents spun up via `add_member` will have `agent_id=NULL` in their membership record indefinitely. The delivery engine (S6) uses `agent_id` to look up tmux pane targets for delivery. With `agent_id=NULL`, the member appears "offline" to the delivery engine and never receives tmux delivery — even though they have an active agent.

- **Recommendation:** Add an FR to S4 (or S6): When the session correlator's `_create_or_update_agent()` links a new agent to a persona, check for any ChannelMembership where `persona_id = agent.persona_id AND agent_id IS NULL AND status = 'active'` and set `agent_id = agent.id`. This is a small addition to `session_correlator.py` — one query, one update. Assign it to S4 since it's service-layer plumbing.

---

### Finding 9: `send_message()` Parameter Name Mismatch

- **Severity:** 🟡 Warning
- **Dimension:** 4. Terminology Consistency
- **PRDs Involved:** e9-s4, e9-s6
- **Detail:**

  S4 FR10 defines `send_message()` with this signature:
  ```python
  send_message(slug, content, persona, agent=None, message_type='message',
               attachment_path=None, source_turn_id=None, source_command_id=None)
  ```

  S6 Section 6.5 calls it with different parameter names:
  ```python
  ChannelService.send_message(
      channel_id=membership.channel_id,
      persona_id=agent.persona_id,
      agent_id=agent.id,
      text=stripped_text,
      source_turn_id=turn.id,
      ...
  )
  ```

  Differences:
  - S4 uses `slug` (string), S6 uses `channel_id` (integer)
  - S4 uses `content` (string), S6 uses `text` (string)
  - S4 uses `persona` (object), S6 uses `persona_id` (integer)
  - S4 uses `agent` (object), S6 uses `agent_id` (integer)

- **Impact:** S6's calling code won't match S4's method signature. The building agent for S6 will either need to rewrite the call or modify S4's interface.

- **Recommendation:** Standardise. S4's signature is the contract. Update S6 Section 6.5 to call with S4's parameter names and types — look up Channel by slug (or add an internal `_send_message_by_id` helper if slug lookup is wasteful for internal callers). Or, add an overloaded version that accepts IDs for internal service-to-service calls.

---

### Finding 10: Caller Identity Resolution — Internal Contradiction in S4

- **Severity:** 🟡 Warning
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s4
- **Detail:**

  S4 Section 6.5 contradicts itself about caller identity resolution order:

  The code example shows **tmux first**, env var second:
  ```python
  # Strategy 1: tmux pane detection
  ...
  # Strategy 2: env var override
  ```

  Then the prose below the code says: *"The env var takes precedence when set (per workshop Decision 2.2: 'Takes precedence when set')."* It then provides a "corrected strategy order" that puts env var first:
  1. If `HEADSPACE_AGENT_ID` is set, use it (explicit override takes precedence).
  2. Otherwise, detect tmux pane.

  The code and the prose specify opposite orders.

- **Impact:** The building agent will implement whichever version they read last. If they follow the code, env var overrides don't work in testing. If they follow the prose, tmux detection is bypassed when the env var is accidentally set.

- **Recommendation:** Remove the code example that shows the wrong order. Keep only the corrected order (env var first if set, tmux fallback). The code block should match the prose.

---

### Finding 11: Channel Archive Logic — Nobody Implements It

- **Severity:** 🟡 Warning
- **Dimension:** 6. Gap Detection (Inter-PRD)
- **PRDs Involved:** e9-s4, e9-s7
- **Detail:**

  S4 Section 6.12 defines the channel lifecycle transition `complete -> archived` as: *"`archive_channel()` method stub"*. S4 does not implement archive logic — it's a stub.

  S7 FR16 says the management tab provides an "Archive" action button that is *"available when status is `complete`"*. S7 Section 6.10 shows the archive API call as `PATCH /api/channels/<slug>`.

  But no sprint implements the actual archive transition logic. S4 stubs it. S5 defines the PATCH endpoint but for description/intent updates (FR4), not archival. S7 expects to call an archive action.

- **Impact:** The dashboard's archive button will call an endpoint that doesn't perform archival. The operator clicks "Archive" and nothing happens (or gets a 400 error).

- **Recommendation:** Either add archive logic to S4's ChannelService (remove the stub, implement the method), or explicitly defer it: remove the archive button from S7 FR16 and add a comment in S4 that archive is a v2 feature. Don't ship a button that calls a stub.

---

### Finding 12: SSE `commonTypes` Modification by Multiple Sprints

- **Severity:** 🔵 Info
- **Dimension:** 10. Shared Resource Contention
- **PRDs Involved:** e9-s1, e9-s7
- **Detail:**

  S1 adds a `synthetic_turn` SSE event type that the dashboard JS must handle. S1 Section 6.8 says this needs a new handler in dashboard JS.

  S7 Section 6.6 modifies `static/js/sse-client.js` to add `channel_message` and `channel_update` to the `commonTypes` array.

  Both sprints modify the same JS file. If S1 is built first and also adds `synthetic_turn` to `commonTypes`, S7's building agent will encounter a merge conflict on that array.

- **Impact:** Minor merge conflict. Both additions are additive (appending to an array) so the resolution is trivial, but building agents may not handle it gracefully.

- **Recommendation:** Note in both PRDs that `sse-client.js` `commonTypes` is a shared resource. The additions are non-conflicting but building agents should check for prior modifications to the array.

---

### Finding 13: S7 Scope Statement Contradicts Backend Changes

- **Severity:** 🔵 Info
- **Dimension:** 2. Boundary Conflicts
- **PRDs Involved:** e9-s7
- **Detail:**

  S7 scope says: *"This sprint produces no new backend services, models, or API endpoints."*

  S7 Section 6.9 modifies `NotificationService` (adding `_channel_rate_limit_tracker`, `_is_channel_rate_limited()`, and `send_channel_notification()` methods). This IS a backend service modification.

  S7 Section 6.1 also lists `notification_service.py` in Files to Modify.

- **Impact:** The scope statement misleads the building agent about the sprint's boundary. A building agent reading only the scope might skip the notification backend work.

- **Recommendation:** Update S7 scope to say: "This sprint produces no new backend services or models. One existing backend service (NotificationService) is extended with per-channel rate limiting." — OR — move notification backend work to S6 (see Finding 4).

---

### Finding 14: Line Number References in S6 Will Be Stale

- **Severity:** 🔵 Info
- **Dimension:** 7. Sequencing Feasibility
- **PRDs Involved:** e9-s6
- **Detail:**

  S6 references specific line numbers in existing files:
  - *"lines 1543-1615 of hook_receiver.py"* (Section 6.15)

  By the time S6 is built, S1 and potentially S4 will have modified `session_correlator.py` and potentially `hook_receiver.py`, shifting line numbers. The building agent for S6 will look for code at the wrong lines.

- **Impact:** Minor confusion for the building agent. The code structure is well-described enough to find the insertion points regardless of line shifts.

- **Recommendation:** Replace line number references with structural references: "After the two-commit pattern in `process_stop()`, before `_trigger_priority_scoring()`." The S6 PRD already provides structural descriptions alongside line numbers — consider removing the line numbers entirely.

---

### Finding 15: Voice Chat PWA Changes in S8 May Belong in S7

- **Severity:** 🔵 Info
- **Dimension:** 8. Scope Creep Signals
- **PRDs Involved:** e9-s7, e9-s8
- **Detail:**

  S8 FR15-FR16 add channel message display to the Voice Chat PWA sidebar (`/voice`). This is frontend UI work that renders channel data — conceptually similar to S7's dashboard channel UI work.

  S7 handles all dashboard channel UI but explicitly lists "Voice Chat PWA channel integration" as out of scope (Section 2.2). S8 picks it up. This split is intentional but creates a situation where two sprints modify different parts of the frontend for the same user need (seeing channel messages).

- **Impact:** Low. The Voice Chat PWA (`/voice`) is a separate static HTML app from the dashboard, so there's no file-level conflict. But the building agents for S7 and S8 might not be aware of each other's rendering patterns, leading to visual inconsistency.

- **Recommendation:** This is a reasonable scope split — just ensure both PRDs reference the same SSE event schema (Finding 2 applies here too). Consider adding a note in S8 to follow S7's visual conventions for channel message rendering.

---

## Remediation Plan

### e9-s4-channel-service-cli-prd.md

1. **Add SSE broadcast calls to ChannelService** — `send_message()` and all state-changing methods should call `broadcaster.broadcast()` as post-commit side effects. Reference Finding #1.
2. **Remove service-level `can_create_channel` duplicate** — Section 6.9 ChannelService method should call `persona.can_create_channel` (S2's property), not reimplement. Reference Finding #5.
3. **Fix caller identity code example** — Remove the tmux-first code block in Section 6.5, keep only the corrected env-var-first order. Reference Finding #10.
4. **Add agent-to-membership linking FR** — When session correlator links a new agent to a persona, update any ChannelMembership with `persona_id = agent.persona_id AND agent_id IS NULL AND status = 'active'`. Reference Finding #8.
5. **Implement archive logic or remove stub** — Either implement `archive_channel()` properly or explicitly defer and document. Reference Finding #11.

### e9-s5-api-sse-endpoints-prd.md

1. **Update SSE broadcast ownership description** — Section 6.6 should say broadcasts come from ChannelService (modified in S4 per Finding #1 remediation), not just assert it. Reference Finding #1.
2. **Align message history ordering** — Section 6.8 should specify chronological order (oldest first), matching S4 and S7 expectations. Reference Finding #6.

### e9-s6-delivery-engine-prd.md

1. **Remove SSE broadcast from delivery engine** — If Finding #1 is resolved with Option A, delivery engine does tmux + notification, not SSE. Reference Finding #1.
2. **Remove conflicting SSE event schema** — Section 6.13 should reference S5's canonical schema, not define its own. Reference Finding #2.
3. **Fix `muted = false` to `status = 'active'`** — FR2 and anywhere else that references a boolean `muted` column. Reference Finding #7.
4. **Fix `send_message()` call parameters** — Section 6.5 should use S4's parameter names (slug, content, persona, agent). Reference Finding #9.
5. **Replace line number references with structural descriptions** — Section 6.15. Reference Finding #14.
6. **Own notification integration** — Move per-channel rate limiting implementation here (extend NotificationService). Reference Finding #4.

### e9-s7-dashboard-ui-prd.md

1. **Remove notification backend work** — Section 6.9 backend modifications move to S6 (Finding #4 remediation). S7 only calls the method. Reference Finding #4.
2. **Fix scope statement** — Update Section 2.1 to reflect actual backend touch (or remove it per above). Reference Finding #13.

### e9-s2-persona-type-system-prd.md

1. **Add operator persona runtime accessor** — New FR: `Persona.get_operator()` class method that returns the person/internal Persona. Reference Finding #3.

### Cross-PRD Actions

1. **Canonise `channel_message` SSE event schema** — Define it exactly ONCE in S5 Section 6.5. All other PRDs reference S5's definition. Remove conflicting definitions from S6 Section 6.13. Reference Findings #1, #2.
2. **Resolve SSE broadcast ownership** — Pick ONE model (recommended: ChannelService broadcasts, delivery engine does tmux/notification). Propagate to S4, S5, S6. Reference Finding #1.
3. **Add `synthetic_turn` to SSE shared resource note** — Both S1 and S7 modify `sse-client.js` `commonTypes`. Add cross-reference notes. Reference Finding #12.
4. **Verify S7 and S8 use same rendering conventions** — Channel message display consistency across dashboard and Voice Chat PWA. Reference Finding #15.

---

## Dimensions Reviewed

| Dimension | Status | Findings |
|-----------|--------|----------|
| 1. Scope Overlap | ⚠ Issues Found | 2 (#4, #5) |
| 2. Boundary Conflicts | ⚠ Issues Found | 1 (#13) |
| 3. Dependency Alignment | ✓ Clear | 0 |
| 4. Terminology Consistency | ⚠ Issues Found | 3 (#2, #7, #9) |
| 5. Contradictory Requirements | ⚠ Issues Found | 3 (#1, #6, #10) |
| 6. Gap Detection | ⚠ Issues Found | 3 (#3, #8, #11) |
| 7. Sequencing Feasibility | ⚠ Issues Found | 1 (#14) |
| 8. Scope Creep Signals | ⚠ Issues Found | 1 (#15) |
| 9. Success Criteria Conflicts | ✓ Clear | 0 |
| 10. Shared Resource Contention | ⚠ Issues Found | 1 (#12) |

---

## Next Steps

- Address all 4 critical findings before proceeding to orchestration
- Re-run `70: review-prd-set` after remediation to verify fixes
- When all critical findings are resolved: proceed to `10: queue-add` for orchestration
- Individual PRD validation (`30: prd-validate`) should be run after remediation
