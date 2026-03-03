# Cross-PRD Review Report (v2 — Post-Remediation)

**Epic/Subsystem:** Epic 9 — Inter-Agent Communication (Channels)
**PRDs Reviewed:** 8
**Review Date:** 2026-03-03
**Reviewer:** Adversarial Cross-PRD Review (70: review-prd-set) — Robbo
**Context:** Post-remediation re-review. The first review (v1) found 15 findings (4 critical, 7 warning, 4 info). 11 edits were applied. This review verifies those fixes and hunts for residual or newly introduced issues.

---

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | 2 |
| 🟡 Warning | 7 |
| 🔵 Info | 3 |
| **Total Findings** | **12** |

**Overall Assessment:** The four original critical findings (SSE broadcast ownership, canonical SSE schema, operator persona accessor, notification ownership) are architecturally resolved — the correct ownership model is now consistently described across the cohort. However, the remediation edits were surgical: they updated the targeted sections but left stale text in adjacent sections of the same PRDs. The result is internal contradictions within S4 (caller identity ordering described three different ways in the same document) and S7 (notification suppression simultaneously deferred to v2 and specified as a success criterion). These are cleanup issues, not architectural disagreements — but they will confuse building agents if not fixed before orchestration.

---

## PRDs Under Review

| # | PRD | Sprint | FRs | Est. Tasks |
|---|-----|--------|-----|------------|
| 1 | e9-s1-handoff-improvements-prd.md | S1 | 15 | ~12 |
| 2 | e9-s2-persona-type-system-prd.md | S2 | 8 | ~9 |
| 3 | e9-s3-channel-data-model-prd.md | S3 | 12 | ~10 |
| 4 | e9-s4-channel-service-cli-prd.md | S4 | 18 | ~28 |
| 5 | e9-s5-api-sse-endpoints-prd.md | S5 | 18 | ~18 |
| 6 | e9-s6-delivery-engine-prd.md | S6 | 15 | ~20 |
| 7 | e9-s7-dashboard-ui-prd.md | S7 | 20 | ~22 |
| 8 | e9-s8-voice-bridge-channels-prd.md | S8 | 16 | ~16 |

---

## v1 Finding Resolution Status

| v1 Finding | Severity | Status |
|-----------|----------|--------|
| #1 SSE Broadcast Ownership | 🔴 Critical | ✅ Architecturally resolved. Residual: S4 Out of Scope still contradicts (new Finding #1) |
| #2 Canonical SSE Event Schema | 🔴 Critical | ✅ Fully resolved |
| #3 Operator Persona Runtime Accessor | 🔴 Critical | ✅ Fully resolved |
| #4 Notification Ownership to S6 | 🔴 Critical | ✅ Architecturally resolved. Residual: S7 NFR5 stale (new Finding #4) |
| #5 can_create_channel Duplicate | 🟡 Warning | ✅ Fully resolved |
| #6 Message History Ordering | 🟡 Warning | ✅ Fully resolved |
| #7 muted=false Column Reference | 🟡 Warning | ✅ Fully resolved |
| #8 Agent-to-Membership Linking | 🟡 Warning | ✅ FR14 added. Residual: Section 6.13 stale (new Finding #6) |
| #9 Caller Identity Resolution Contradiction | 🟡 Warning | ⚠️ Section 6.5 fixed, but FR18 and Section 2.1 not updated (new Finding #2) |
| #10 Caller Identity Resolution (duplicate of #9) | 🟡 Warning | ⚠️ Same residual as #9 |
| #11 Channel Archive Logic | 🟡 Warning | ✅ FR15 + Section 6.12 added. New gap: no API endpoint (new Finding #5) |
| #12 SSE commonTypes Shared Resource | 🔵 Info | ✅ Fully resolved |
| #13 Hardcoded Line Numbers in S6 | 🔵 Info | ✅ Fully resolved |
| #14 Voice Chat Visual Consistency | 🔵 Info | ✅ Fully resolved |
| #15 S2 FR count in report table | 🔵 Info | ✅ N/A (report artifact) |

---

## Findings

### Finding 1: S4 In Scope / Out of Scope Contradiction on SSE Broadcasting

- **Severity:** 🔴 Critical
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s4-channel-service-cli-prd.md
- **Detail:** The v1 remediation (Edit 1a) added SSE broadcasting to S4's In Scope (Section 2.1) and added `_broadcast_message()` / `_broadcast_update()` methods to the class design (Section 6.3). However, S4 Section 2.2 (Out of Scope) still contains:

  > `- SSE event broadcasting for channels (S5)`

  This directly contradicts Section 2.1 which now says:

  > `- SSE broadcasting: channel_message events after message persistence, channel_update events after state changes (schemas defined in S5)`

  A building agent reading the Out of Scope section will skip implementing SSE broadcasts. A building agent reading In Scope + Section 6.3 + Section 6.17 will implement them. Same document, opposite instructions.

- **Impact:** Building agent may omit SSE broadcasts from ChannelService, breaking the entire real-time update pipeline for the dashboard (S7) and voice bridge (S8). This was the #1 critical finding in v1 and the remediation partially reintroduced the confusion by not cleaning up the Out of Scope bullet.

- **Recommendation:** In S4 Section 2.2, remove the bullet `- SSE event broadcasting for channels (S5)` entirely. Optionally replace with `- SSE event schema definitions (S5 — ChannelService broadcasts events, S5 defines the schemas)` to clarify the boundary.

---

### Finding 2: S4 Caller Identity Resolution — Three Conflicting Descriptions in Same Document

- **Severity:** 🔴 Critical
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s4-channel-service-cli-prd.md
- **Detail:** The v1 remediation (Edit 9) fixed Section 6.5 to make env var the override (Strategy 1) and tmux the fallback (Strategy 2). But two other locations in the same PRD still describe the opposite ordering:

  **Section 2.1 (In Scope):**
  > `Caller identity resolution: tmux pane detection with HEADSPACE_AGENT_ID env var fallback`

  **FR18:**
  > `1. Primary: tmux display-message -p '#{pane_id}' -> look up Agent by tmux_pane_id`
  > `2. Fallback: HEADSPACE_AGENT_ID env var -> look up Agent by ID`

  **Section 6.5 (code block):**
  > `Strategy 1 (override): HEADSPACE_AGENT_ID env var — takes precedence when set.`
  > `Strategy 2 (primary): tmux display-message pane detection.`

  Three locations, two contradictory orderings. The code in Section 6.5 (env var first) is the intended resolution per the v1 remediation. FR18 and Section 2.1 still say tmux first.

- **Impact:** Building agent follows FR18 (the normative requirement) and implements tmux-first ordering, ignoring the code example in 6.5. The env var override — needed for testing, CI, and non-tmux environments — becomes a dead-code fallback that only fires when tmux detection fails, instead of the intended take-precedence override.

- **Recommendation:** Update FR18 to match Section 6.5:
  > `1. Override: HEADSPACE_AGENT_ID env var — takes precedence when set`
  > `2. Primary: tmux display-message -p '#{pane_id}' -> look up Agent by tmux_pane_id`

  Update Section 2.1 to: `Caller identity resolution: HEADSPACE_AGENT_ID env var override with tmux pane detection fallback`

---

### Finding 3: S7 Notification Suppression — FR19 Defers to v2 While SC19 and Code Require It

- **Severity:** 🟡 Warning
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s7-dashboard-ui-prd.md
- **Detail:** Three sections of S7 give contradictory guidance on whether active-view notification suppression is implemented:

  **FR19:** `"Active view suppression is deferred to v2 — the 30-second rate limit provides a sufficient floor."`

  **Success Criteria 3.1 #19:** `"Notifications are suppressed for the channel currently open in the chat panel"`

  **Section 6.5 (code example):**
  ```javascript
  if (!window.ChannelChat || !window.ChannelChat.isActivelyViewing(data.channel_slug)) {
      triggerChannelNotification(data);
  }
  ```

  FR19 explicitly defers suppression. SC #19 requires it. Section 6.5 implements it. The building agent cannot satisfy all three.

- **Impact:** Building agent likely follows the FR (normative requirement) and skips suppression implementation. The SC then fails during validation. Or the building agent implements suppression per the code example, contradicting the FR's "deferred to v2" statement.

- **Recommendation:** Choose one position. If suppression is deferred: remove SC #19 and remove the `isActivelyViewing` check from Section 6.5. If suppression is v1: update FR19 to describe the implementation. Given the code is already sketched in 6.5 and the 30-second rate limit may still cause notification spam for active conversations, **recommend implementing it in v1** — update FR19.

---

### Finding 4: S7 NFR5 Still Claims NotificationService Modification (Belongs to S6)

- **Severity:** 🟡 Warning
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s7-dashboard-ui-prd.md
- **Detail:** The v1 remediation (Edit 4) moved notification ownership to S6 and updated S7's Section 6.9 and FR17-FR19. However, S7 NFR5 was not updated:

  **S7 NFR5:** `"No new backend routes... The only backend change is extending NotificationService with per-channel rate limiting."`

  **S7 Section 6.9:** `"NotificationService is extended with per-channel rate limiting by S6 (delivery engine sprint). This sprint (S7) does not modify NotificationService."`

  NFR5 says S7 extends NotificationService. Section 6.9 says S7 does NOT modify NotificationService.

- **Impact:** Building agent for S7 may attempt to modify NotificationService (duplicating S6's work), or correctly skip it but then wonder why NFR5 references it.

- **Recommendation:** Update S7 NFR5 to: `"No new backend routes or services. All backend channel logic (including notification rate limiting) is handled by S4-S6. This sprint is frontend-only: Jinja2 templates, vanilla JavaScript, and Tailwind CSS."`

---

### Finding 5: No Archive API Endpoint — S4 Method Exists, S5 Has No Endpoint, S7 References Nonexistent Path

- **Severity:** 🟡 Warning
- **Dimension:** 6. Gap Detection (Inter-PRD)
- **PRDs Involved:** e9-s4, e9-s5, e9-s7
- **Detail:** The v1 remediation (Edit 10) added `archive_channel()` to S4 (FR15 + Section 6.3 + Section 6.12). The service method exists. But no API endpoint exposes it:

  **S5 Endpoint Table (Section 6.2):** Has 13 endpoints. None is `/api/channels/<slug>/archive`. The closest is `PATCH /api/channels/<slug>` (FR4) which handles `{description?, intent_override?}` only.

  **S7 FR16:** `"Archive — calls PATCH /api/channels/<slug> with archive data (available when status is complete)"` — but S5's PATCH endpoint does not accept archive transitions.

  **S4 FR15:** `archive_channel(slug, persona)` exists as a service method but is unreachable via HTTP.

  The dashboard (S7) cannot trigger archive because no API endpoint maps to S4's `archive_channel()`.

- **Impact:** The archive feature is half-built: service method exists (S4), CLI could call it directly, but the dashboard (S7) and any HTTP consumer has no way to trigger it. Building agent for S7 will either invent an endpoint (scope creep) or leave archive non-functional in the UI.

- **Recommendation:** Add a `POST /api/channels/<slug>/archive` endpoint to S5's endpoint table (Section 6.2) and add a corresponding FR. Chair or operator only. Delegates to `ChannelService.archive_channel()`. Returns 200. Update S7 FR16 to reference the new endpoint instead of PATCH.

---

### Finding 6: S4 Section 6.13 Contradicts FR14 on Agent-Membership Linking Scope

- **Severity:** 🟡 Warning
- **Dimension:** 5. Contradictory Requirements
- **PRDs Involved:** e9-s4-channel-service-cli-prd.md
- **Detail:** The v1 remediation (Edit 8) added FR14 (agent-to-membership linking) to S4's scope. FR14 says:

  > `When the session correlator links a new agent to a persona, the system shall check for any ChannelMembership where persona_id = agent.persona_id AND agent_id IS NULL AND status = 'active' and update agent_id to the new agent's ID.`

  But Section 6.13 (Agent Spin-Up on Member Add) still contains the original text:

  > `"a separate mechanism (outside this sprint's scope) updates the channel membership's agent_id."`

  FR14 IS that mechanism, and it IS in this sprint's scope. The section directly contradicts the FR that was added by remediation.

- **Impact:** Building agent reads Section 6.13, sees "outside this sprint's scope," and does not implement the agent-to-membership linking. FR14 goes unbuilt. The channel membership agent_id stays NULL forever — agents join channels but never get delivery because the membership isn't linked to their agent instance.

- **Recommendation:** Update S4 Section 6.13's final paragraph to: `"The membership record is created with agent_id=NULL. When the agent starts and registers via the session-start hook, the session correlator links it to the persona and updates the ChannelMembership's agent_id (see FR14)."`

---

### Finding 7: session_correlator.py Modified by S1 and S4 at Same Insertion Point

- **Severity:** 🟡 Warning
- **Dimension:** 10. Shared Resource Contention
- **PRDs Involved:** e9-s1-handoff-improvements-prd.md, e9-s4-channel-service-cli-prd.md
- **Detail:** Both S1 and S4 add code to `session_correlator.py` at the same logical point — after persona assignment during agent creation:

  **S1 Section 6.1:** `"session_correlator.py — After persona assignment, call HandoffDetectionService.detect_and_emit()."`

  **S4 Section 6.2:** `"session_correlator.py — After persona assignment, query and update ChannelMembership records with NULL agent_id for that persona."`

  Neither PRD cross-references the other's modification to this file. If built sequentially (S1 first, then S4), the second building agent may not be aware of the first's changes and could inadvertently break the insertion. If built out of sequence, merge conflicts are likely.

- **Impact:** Merge conflict in session_correlator.py during orchestration. Or worse: one sprint's modification silently overrides the other's.

- **Recommendation:** Add a note to both PRDs acknowledging the shared modification:
  - S1 Section 6.1: `"Note: S4 also modifies session_correlator.py after persona assignment to update ChannelMembership agent_id. Both modifications target the same logical point — append sequentially."`
  - S4 Section 6.2: `"Note: S1 also modifies session_correlator.py after persona assignment to call HandoffDetectionService.detect_and_emit(). Both modifications target the same logical point — append sequentially."`

---

### Finding 8: S7 Dashboard Route File Missing from Files to Modify

- **Severity:** 🟡 Warning
- **Dimension:** 6. Gap Detection (Inter-PRD)
- **PRDs Involved:** e9-s7-dashboard-ui-prd.md
- **Detail:** S7 Section 6.15 defines a Python function `get_channel_data_for_operator()` that must be added to the dashboard route handler to provide the `channel_data` template context variable. However, Section 6.1 (Files to Modify) does not list the dashboard route file. It lists only:

  - `templates/dashboard.html`
  - `static/js/sse-client.js`
  - `static/js/dashboard-sse.js`
  - `static/css/src/input.css`

  The dashboard route handler (likely `src/claude_headspace/routes/dashboard.py` or equivalent) is a Python file that needs modification to compute and pass `channel_data` to the template. Without it in the files-to-modify list, the building agent may render the template with `{% if channel_data %}` but never provide the variable — resulting in channel cards never appearing.

- **Impact:** Channel cards section never renders on the dashboard because the route handler doesn't provide the context variable. The building agent implements all the frontend code but the server never passes the data.

- **Recommendation:** Add the dashboard route file to S7 Section 6.1 (Files to Modify):
  > `| src/claude_headspace/routes/dashboard.py | Add get_channel_data_for_operator() function. Call it in the dashboard route handler and pass result as channel_data template context variable. |`

---

### Finding 9: S8 Voice Bridge Operator Persona Resolution Not Specified

- **Severity:** 🟡 Warning
- **Dimension:** 6. Gap Detection (Inter-PRD)
- **PRDs Involved:** e9-s8-voice-bridge-channels-prd.md
- **Detail:** S8 routes channel commands through the existing `voice_command()` function, which calls `ChannelService` methods. These methods require a `persona` argument (e.g., `create_channel(creator_persona, ...)`, `send_message(slug, content, persona, ...)`). But S8 never specifies how the operator's Persona is resolved within the voice bridge.

  The existing voice bridge uses Bearer token auth or localhost bypass — both designed for agent-scoped operations. The operator has no agent, so there's no `token -> agent_id -> persona` chain. S5 solves this for the API with `Persona.get_operator()` (Section 6.3). S7 solves it for the dashboard with the same method (Section 6.15). But S8 never references `Persona.get_operator()` or any equivalent resolution.

  S8 Section 6.7 shows `_handle_channel_intent()` dispatching to service methods, but the `persona` argument is not shown being resolved.

- **Impact:** Building agent implements channel routing in the voice bridge but cannot call ChannelService methods because they have no persona to pass. The agent either invents a resolution mechanism (scope creep, inconsistency risk) or the channel voice commands crash at runtime.

- **Recommendation:** Add persona resolution to S8 Section 6.7 or a new Section 6.x. Reference `Persona.get_operator()` from S2 FR8:
  > `"Before calling any ChannelService method, the voice bridge resolves the operator's Persona via Persona.get_operator() (S2 FR8). If no operator persona exists, return a 503 voice error: 'Operator identity not configured.'"`

---

### Finding 10: S7 Success Criteria 17-19 Describe S6's Responsibilities, Not S7's

- **Severity:** 🔵 Info
- **Dimension:** 9. Success Criteria Conflicts
- **PRDs Involved:** e9-s7-dashboard-ui-prd.md
- **Detail:** S7's Success Criteria 3.1 items 17-19 describe notification behavior that is implemented by S6, not S7:

  - SC17: `"Channel messages trigger macOS notifications via NotificationService when the operator is not actively viewing the channel"` — this is S6's delivery engine responsibility.
  - SC18: `"Per-channel notification rate limiting enforces one notification per channel per 30-second window"` — this is S6's NotificationService extension.
  - SC19: `"Notifications are suppressed for the channel currently open in the chat panel"` — this is either deferred to v2 (per FR19) or a frontend concern.

  S7's corresponding FRs (FR17-FR19) correctly say these are handled by S6 or deferred. But the success criteria still describe them as if S7 is being validated against them. A building agent completing S7 cannot verify SC17 or SC18 because they depend on S6 being operational.

- **Impact:** Validation confusion. S7's `30: prd-validate` run may flag these as unverifiable success criteria.

- **Recommendation:** Rephrase SC17-19 to describe what S7 is actually responsible for. For example:
  - SC17: `"The channel cards and chat panel correctly display messages received via channel_message SSE events"`
  - SC18: `"N/A — per-channel rate limiting is validated in S6"`
  - SC19: (Remove if deferred, or specify the frontend focus flag behavior if implementing)

---

### Finding 11: S2 FR7 "property (or method)" Ambiguity

- **Severity:** 🔵 Info
- **Dimension:** 4. Terminology Consistency
- **PRDs Involved:** e9-s2-persona-type-system-prd.md, e9-s4-channel-service-cli-prd.md
- **Detail:** S2 FR7 describes `can_create_channel` as a "property (or method)":

  > `"The Persona model shall expose a can_create_channel property (or method)"`

  S4 FR12 references it as a property:

  > `"check creator_persona.can_create_channel (property from S2 FR7)"`

  S2 Section 6.2 implements it as a `@property`:

  > `@property def can_create_channel(self) -> bool:`

  The "or method" alternative in the FR text is harmless — the code example resolves it. But a pedantic building agent could implement it as a method (`can_create_channel()` with parentheses) which would break S4's property-style access (`persona.can_create_channel` without parentheses).

- **Impact:** Very low risk — the code example in Section 6.2 is unambiguous. But the FR text could be cleaner.

- **Recommendation:** Change S2 FR7 from "property (or method)" to just "property" to match the implementation in Section 6.2 and the consumer in S4 FR12.

---

### Finding 12: Operator Persona Hardcoded as "Sam" in Migration

- **Severity:** 🔵 Info
- **Dimension:** 4. Terminology Consistency
- **PRDs Involved:** e9-s2-persona-type-system-prd.md
- **Detail:** S2 FR6 hardcodes the operator persona as name "Sam" in the Alembic migration (Section 6.4 Step 7). Multiple PRDs reference "the operator (Sam)" throughout. This is correct for the current deployment (single operator, Sam) but creates a coupling between the migration and the operator's name.

  If the operator name ever changes or a second operator is added, the migration's hardcoded "Sam" persona cannot be updated (migrations are immutable once run). A future operator would require a new migration.

- **Impact:** None for v1 — there is exactly one operator. Worth noting for awareness.

- **Recommendation:** No change required. This is an acceptable v1 trade-off. Document in S2 that the operator persona is a one-time seed and any future operator changes require a new migration.

---

## Remediation Plan

Recommended fixes grouped by PRD, in suggested order of remediation:

### e9-s4-channel-service-cli-prd.md (3 fixes)

1. **Section 2.2 (Out of Scope):** Remove the bullet `- SSE event broadcasting for channels (S5)`. Optionally replace with `- SSE event schema definitions (S5 — ChannelService broadcasts events, S5 defines the schemas)`. — References Finding #1
2. **FR18 + Section 2.1:** Update to match Section 6.5 ordering: env var override first, tmux detection second. — References Finding #2
3. **Section 6.13:** Replace "a separate mechanism (outside this sprint's scope)" with "the session correlator links it and updates the ChannelMembership's agent_id (see FR14)." — References Finding #6

### e9-s7-dashboard-ui-prd.md (4 fixes)

1. **FR19:** Either remove "deferred to v2" and describe the suppression implementation, or keep deferral and remove SC #19 + the isActivelyViewing code from Section 6.5. — References Finding #3
2. **NFR5:** Replace notification backend claim with "This sprint is frontend-only." — References Finding #4
3. **Section 6.1 (Files to Modify):** Add the dashboard route file (dashboard.py or equivalent). — References Finding #8
4. **SC17-19:** Rephrase to describe S7's actual frontend responsibilities. — References Finding #10

### e9-s5-api-sse-endpoints-prd.md (1 fix)

1. **Section 6.2 + new FR:** Add `POST /api/channels/<slug>/archive` endpoint. Chair or operator only. Delegates to `ChannelService.archive_channel()`. Returns 200. — References Finding #5

### e9-s8-voice-bridge-channels-prd.md (1 fix)

1. **Section 6.7 or new section:** Add operator persona resolution via `Persona.get_operator()` before any ChannelService call. — References Finding #9

### Cross-PRD Actions

1. **session_correlator.py shared modification:** Add cross-reference notes to both S1 Section 6.1 and S4 Section 6.2 acknowledging the shared insertion point. — References Finding #7
2. **S2 FR7:** Change "property (or method)" to "property". — References Finding #11

---

## Dimensions Reviewed

| Dimension | Status | Findings |
|-----------|--------|----------|
| 1. Scope Overlap | ✓ Clear | 0 |
| 2. Boundary Conflicts | ✓ Clear | 0 |
| 3. Dependency Alignment | ✓ Clear | 0 |
| 4. Terminology Consistency | ⚠ Issues Found | 2 (#11, #12) |
| 5. Contradictory Requirements | ⚠ Issues Found | 5 (#1, #2, #3, #4, #6) |
| 6. Gap Detection | ⚠ Issues Found | 3 (#5, #8, #9) |
| 7. Sequencing Feasibility | ✓ Clear | 0 |
| 8. Scope Creep Signals | ✓ Clear | 0 |
| 9. Success Criteria Conflicts | ⚠ Issues Found | 1 (#10) |
| 10. Shared Resource Contention | ⚠ Issues Found | 1 (#7) |

---

## Comparison with v1 Review

| Metric | v1 Review | v2 Review (this) |
|--------|-----------|-------------------|
| Total findings | 15 | 12 |
| 🔴 Critical | 4 | 2 |
| 🟡 Warning | 7 | 7 |
| 🔵 Info | 4 | 3 |
| Architectural issues | 4 (SSE ownership, schema, operator accessor, notification ownership) | 0 |
| Stale text from incomplete remediation | 0 | 5 (#1, #2, #4, #6, + partial #3) |
| New gaps found on deeper review | 0 | 4 (#5, #7, #8, #9) |

**Key improvement:** All four original critical architectural disagreements are resolved. The cohort now tells a consistent story about SSE broadcast ownership (S4), notification ownership (S6), operator identity (S2 FR8), and agent-to-membership linking (S4 FR14). The remaining issues are text cleanup (stale contradictions) and coverage gaps (missing archive endpoint, missing file-to-modify, missing persona resolution).

---

## Next Steps

- Address 2 critical findings (#1, #2) — stale text that directly contradicts the intended architecture
- Address warning findings — particularly #5 (archive endpoint gap) and #9 (voice bridge persona resolution)
- Re-run `70: review-prd-set` after remediation to target zero criticals
- When all criticals are resolved: run `30: prd-validate` on each PRD individually, then proceed to `10: queue-add` for orchestration
