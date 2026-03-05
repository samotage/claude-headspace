# Channels Functional Review — Consolidated Report

**Date:** 5 March 2026
**Review Lead:** Robbo (Architect)
**Review Team:** Mark (Data Layer), Verner (API/Integration/QA), Shorty (Services — partial)
**Requested By:** Sam (Operator)
**Channel:** #workshop-channels-functional-review-14

---

## Executive Summary

A full end-to-end functional review of the Epic 9 (Inter-Agent Communication) implementation, tracing decisions from the conceptual architecture through the workshop corpus, Epic 9 roadmap, 8 sprint PRDs, and into the codebase.

**Overall Assessment:** The channels feature is **substantially complete** across all 8 sprints. Every workshop decision has a corresponding implementation. The data model is clean. The service layer is comprehensive (~2,000 lines). The API, CLI, dashboard UI, and voice bridge are all functional. The architecture is sound.

**However, three critical issues require attention before the feature can be considered production-ready:**

1. **Completion relay pipeline is broken** — Agent responses don't flow back into channels (live bug, confirmed during this review session)
2. **Zero end-to-end test coverage** — ~1,825 tests exist but are entirely mock-based; the integrated pipeline has never been verified
3. **Handoff doesn't update channel membership** — Successor agents are silently excluded from channel conversations

---

## 1. Scope & Methodology

### Source Documents Reviewed

| Document | Location | Purpose |
|----------|----------|---------|
| Agent Teams Functional Outline | `docs/conceptual/headspace-agent-teams-functional-outline.md` | Original vision (Feb 15, 2026) |
| Workshop Corpus (9 files) | `docs/workshop/interagent-communication/` | 26 decisions across Sections 0-4 |
| Epic 9 Roadmap | `docs/roadmap/epic-9_inter-agent-communication.md` | 8-sprint breakdown with dependencies |
| Sprint 1-8 PRDs | `docs/prds/channels/done/e9-s1..s8-*.md` | Sprint-level specifications |
| Cross-PRD Review Reports | `docs/prds/channels/cross-prd-review-report*.md` | Pre-build review findings |
| PRD Remediation Plan | `docs/prds/channels/prd-remediation-plan.md` | Issue resolution tracking |

### Implementation Files Reviewed

- **Models:** `channel.py`, `channel_membership.py`, `message.py`, `persona_type.py`
- **Services:** `channel_service.py` (~1,425 lines), `channel_delivery.py` (~554 lines), `caller_identity.py`, `handoff_detection.py`, `handoff_executor.py`
- **Routes:** `channels_api.py` (~647 lines), `voice_bridge.py` (channel extensions), `dashboard.py`
- **CLI:** `channel_cli.py`, `persona_cli.py` (handoffs command)
- **Frontend:** `channel-chat.js`, `channel-cards.js`, `channel-management.js`, `member-autocomplete.js`
- **Templates:** `_channel_cards.html`, `_channel_chat_panel.html`, `_channel_management.html`
- **Voice PWA:** `voice-sidebar.js`, `voice-channel-chat.js`, `voice-sse-handler.js`, `voice-api.js`
- **Migration:** `c5f6f4b1893b_add_channel_tables.py`

### Review Assignments

| Reviewer | Lane | Status |
|----------|------|--------|
| **Robbo** | Cross-cutting architectural lineage, Sprint 7/8, consolidated report | Complete |
| **Mark** | Data layer (S2/S3), Workshop Section 1, live bug diagnosis | Complete |
| **Verner** | API (S5), Sprint 1 (Handoff), Workshop Sections 0A/4, test coverage | Complete |
| **Shorty** | Services (S4/S6), Workshop Sections 0/2/3 | **Incomplete** — partial findings only |

---

## 2. Conceptual Architecture Lineage

The original Agent Teams vision (Feb 15) laid out a v1-v5 roadmap. Epic 9 is **not explicitly in that roadmap** — it emerged from the workshop process when inter-agent communication was identified as a prerequisite before the team model could operate as envisioned.

### What Epic 9 Addresses

| Conceptual Item | Status | Epic 9 Sprint |
|-----------------|--------|---------------|
| Workshop mode as first-class concept (§4.1) | Addressed — workshop channel type | S3-S7 |
| Cross-persona collaboration (§8.3, v4) | Pulled forward — channels enable direct agent communication | S3-S8 |
| Handoff pipeline improvements (§6) | Partially addressed — filename reform + startup detection | S1 |
| Persona system (§5) | Prerequisite complete (Epic 8) | — |

### What Remains Deferred

| Conceptual Item | Original Version | Status |
|-----------------|-----------------|--------|
| PM Automation / Gavin (§4.2) | v3 | Not addressed |
| QA Integration / Verner (§4.4) | v1-v2 | Not addressed |
| Ops & Auto-Remediation / Leon (§4.6) | v5 | Not addressed |
| Autonomous Teams (§4, v4) | v4 | Not addressed |
| Skill File Evolution (§7) | v2 | Not addressed |
| Context Handoff auto-trigger (§6, Open Q1) | v2 | Still an open design question |
| Decision extraction from channel history | — | Explicitly deferred (Workshop 4.3) |
| Delivery priority for chair | — | Deferred to v2 (Workshop 1.4) |
| Unread/delivery tracking | — | Deferred to v2 |

### Open Questions from Conceptual Doc (§11)

| # | Question | Resolution |
|---|----------|------------|
| 1 | Handoff trigger mechanism | **Still open** — S1 improved the pipeline, not the trigger |
| 2 | Skill file format | Resolved — markdown |
| 3 | Persona count per pool | Resolved pragmatically |
| 4 | PM layer scope | Deferred |
| 5 | Skill file scope | Resolved — project-level via `otl_support/data/` |
| 6 | Experience persistence pruning | Partially resolved — append-only with manual curation |

---

## 3. Workshop Decision Traceability

All 26 workshop decisions across Sections 0-4 have corresponding implementations.

### Section 0: Infrastructure Audit (4 decisions)

| Decision | Subject | Implementation Status |
|----------|---------|----------------------|
| 0.1 | 7 communication paths, per-pane locks | Confirmed in tmux bridge |
| 0.2 | Completion-only relay rule | Implemented in `channel_delivery.py` |
| 0.3 | Safe delivery states, envelope format | Implemented — `[#slug] Name (agent:ID):\n{content}` |
| 0.4 | Two-layer channel behavioral primer | Channel types with intent_override field |

### Section 0A: Handoff Continuity (7 decisions)

| Decision | Subject | Implementation Status |
|----------|---------|----------------------|
| 0A.1 | Filename format `{ts}_{summary}_{agent-id:N}` | Implemented in `handoff_executor.py` |
| 0A.2 | Startup detection after persona assignment | Implemented in `handoff_detection.py` |
| 0A.3 | Synthetic injection (dashboard-only SSE) | **Deviated** — persistent Turn records instead (improvement) |
| 0A.4 | Manual rehydration (operator copies path) | Supported via Turn text field |
| 0A.5 | Three access paths (CLI, API, Dashboard) | CLI implemented; API and Dashboard paths **not confirmed** |
| 0A.6 | `<insert-summary>` placeholder + glob fallback | Both implemented |
| 0A.7 | CLI namespace | `flask persona handoffs` (not `flask org persona`) |

### Section 1: Channel Data Model (5 decisions)

| Decision | Subject | Implementation Status |
|----------|---------|----------------------|
| 1.1 | Channel table (12 columns), PersonaType, slug pattern | Implemented at 100% fidelity |
| 1.2 | Message table (10+ columns), immutability, bidirectional links | Implemented |
| 1.3 | MessageType enum (4 types) | Implemented |
| 1.4 | Membership model, mutable agent_id, partial unique index | Implemented — but **agent_id not updated on handoff** (Finding 10) |
| 1.5 | Relationship to existing models, no new Event types | Implemented |

### Section 2: Channel Operations (3 decisions)

| Decision | Subject | Implementation Status |
|----------|---------|----------------------|
| 2.1 | 4-state lifecycle, creation paths, context briefing | Implemented in ChannelService |
| 2.2 | CLI interface (`flask channel`, `flask msg`) | Implemented |
| 2.3 | API endpoints, dual auth, SSE event types | Implemented (16 endpoints vs 14 specified) |

### Section 3: Message Delivery (4 decisions)

| Decision | Subject | Implementation Status |
|----------|---------|----------------------|
| 3.1 | Async per-member fan-out, per-pane locks | Implemented in ChannelDeliveryService |
| 3.2 | Completion-only relay via hook pipeline | Implemented — but **single integration point, no fallback** (Finding 9) |
| 3.3 | Safe-state delivery, in-memory queue, FIFO drain | Implemented |
| 3.4 | Operator delivery via SSE, notifications with rate limiting | Implemented |

### Section 4: Group Workshop Use Case (3 decisions)

| Decision | Subject | Implementation Status |
|----------|---------|----------------------|
| 4.1 | Channel setup via voice, agent spin-up on member add | Implemented in voice bridge |
| 4.2 | Multi-agent conversation flow, concurrent delivery | Implemented — but **relay broken in practice** (Finding 8) |
| 4.3 | Explicit completion, archival, no automated decision extraction | Implemented |

---

## 4. Sprint Implementation Status

| Sprint | Scope | Fidelity | Key Findings |
|--------|-------|----------|--------------|
| S1 | Handoff Improvements | 95% | Design deviation (persistent Turns vs synthetic_turn SSE — improvement). CLI namespace differs from PRD. API/Dashboard handoff history paths unconfirmed. |
| S2 | PersonaType System | 100% | Clean implementation, all 4 quadrant rows seeded. |
| S3 | Channel Data Model | 100% | All tables, enums, constraints, indexes match spec exactly. |
| S4 | ChannelService + CLI | ~95% | ~1,425 lines. Agent-to-membership linking (FR14) needs verification. SSE scope contradiction in PRD text. |
| S5 | API + SSE Endpoints | ~92% | 16 endpoints (2 unspecified additions). SSE payload naming differs from PRD. Deactivated persona edge case. |
| S6 | Delivery Engine | ~90% | Core logic sound. Single integration point (hook receiver). No reconciler fallback. Stale agent_id after handoff breaks relay. |
| S7 | Dashboard UI | 95% | Several enhancements beyond spec (kebab menu, info panel, member management, optimistic dedup). Chat bubble alignment bug reported. |
| S8 | Voice Bridge | 100% | All FRs implemented. Fuzzy matching, context tracking, PWA integration complete. No dedicated test coverage. |

---

## 5. Consolidated Findings

### Critical (3)

| # | Finding | Category | Reference | Detail |
|---|---------|----------|-----------|--------|
| **F8** | Completion relay pipeline broken | Gap | Workshop 3.2, S6 PRD | Agent completion responses don't flow back into channels. Live bug confirmed during this review session. Stop hooks not firing for some agents; transcript reconciler creates Turns but has no channel awareness. |
| **F9** | Single integration point for relay | Gap | S6 PRD §6.7 | `relay_agent_response()` is only called from `hook_receiver.process_stop()`. The transcript reconciler path (which is the actual path being exercised) has zero channel awareness. Any agent whose stop hooks don't fire is silently excluded from conversations. |
| **F10** | Handoff doesn't update channel membership | Gap | Workshop 1.4, S3 PRD, S4 FR14 | `ChannelMembership.agent_id` is designed as a "mutable delivery target" but neither HandoffExecutor nor SessionCorrelator updates it when a successor agent registers. Membership row goes stale, delivery engine can't find the successor, relay silently returns False. |

### Major (4)

| # | Finding | Category | Reference | Detail |
|---|---------|----------|-----------|--------|
| **V5** | Zero end-to-end test coverage | Gap | All sprints | ~1,825 tests across 9 files, all mock-based. No integration test exercises the full pipeline: message send → DB write → SSE broadcast → dashboard render. Same failure mode as voice chat ordering incident (commit `74a8892`). |
| **F3** | S4 PRD SSE scope contradiction | Drift | Cross-PRD Review v2 #1 | Section 2.1 says SSE broadcasting IN scope; Section 2.2 says OUT of scope. Code is correct (ChannelService owns broadcasts). PRD text unresolved from incomplete remediation. |
| **F4** | S4 PRD caller identity contradiction | Drift | Cross-PRD Review v2 #2 | Three conflicting descriptions of env var vs tmux precedence. Code correctly uses env var first. PRD text unresolved. |
| **V4** | Deactivated persona via stale token | Gap | S5 PRD FR16-17 | Bearer token maps to agent → agent resolves → persona might be deactivated/deleted. No guard clause in `_resolve_caller()`. |

### Minor (10)

| # | Finding | Category | Reference | Detail |
|---|---------|----------|-----------|--------|
| **F1** | Conceptual roadmap doesn't include Epic 9 | Unspecified | Conceptual §10 | Epic 9 inserts between v1 and v2. Roadmap doc should be updated. |
| **F2** | Handoff trigger mechanism still open | Gap | Conceptual §11.1 | S1 improved the pipeline but auto-triggering on context threshold is unresolved. |
| **F6** | S8 voice bridge has no dedicated tests | Gap | S8 PRD NFRs | Channel intent detection, fuzzy matching, context tracking — all untested. |
| **F7** | S1 synthetic injection design deviation undocumented | Drift | S1 PRD FR7-10 | Persistent Turns instead of `synthetic_turn` SSE. Better approach, but PRD still describes original. |
| **V1** | 16 endpoints vs 14 in S5 PRD | Drift | S5 PRD FR1-13 | `join` and `available-members` endpoints added during implementation. PRD update needed. |
| **V2** | SSE payload/naming mismatch | Drift | S5 PRD FR14-15 | `content_preview` vs `content`, `member_joined` vs `member_added`, etc. Client coded against PRD schema would break. |
| **V6** | Two S5 error codes untested at route level | Gap | S5 error codes table | `agent_already_in_channel` (409) and `content_too_long` (413). |
| **V7** | Message pagination edge cases untested | Gap | S5 PRD cursor pagination | Combined `since`+`before`, limit cap at 200, inverted range. |
| **V9** | CLI namespace differs from PRD | Drift | S1 PRD FR12 | `flask persona handoffs` vs `flask org persona handoffs`. PRD anticipated this. |
| **V10** | Workshop 0A.5 partially fulfilled | Gap | Workshop 0A.5 | CLI handoff history implemented. API endpoint (`GET /api/personas/<slug>/handoffs`) and dashboard section **confirmed unimplemented** (Mark verified). |
| **V11** | Handoff turns may lack visual distinction | Gap | S1 PRD FR8 | Standard AGENT/PROGRESS turns may render identically to normal turns. Visual verification needed. |
| **V12** | Polling glob multiple-match edge case | Concern | S1 PRD FR3 | Warning logged but edge case not tested. |

---

## 6. Reported Bugs (Live During Review)

| Bug | Reported By | Root Cause | Status |
|-----|------------|------------|--------|
| Agent completion messages not appearing in channel chat | Sam | Stop hooks not firing → reconciler creates Turns without channel awareness → relay never called. Compounded by stale agent_id on membership after handoff. | Diagnosed (Findings 8/9/10) |
| Chat bubble alignment (all messages right-aligned) | Sam | Frontend rendering bug in channel chat view. Not a spec gap — standard chat convention places other speakers' messages on the left. | Reported, not yet investigated |
| Operator messages from mobile not reaching channel | Sam (via Verner) | API submission path (`POST /api/channels/<slug>/messages`) failing from iPhone. Different pipeline from Bug 2 (hooks/reconciler). May be caused by SSE flood preventing POST completion. | Reported, not yet investigated |
| Excessive SSE events causing mobile screen instability | Sam (via Verner) | iPhone screen "flipping madly" on channel view. Possible broadcast loop, redundant events, or rapid reconnection cycling on mobile. May be related to Bug 3. | Reported, not yet investigated |

---

## 7. Recommended Remediations

### Priority 1 — Fix the Relay Pipeline (Findings 8, 9, 10)

Three related fixes that together restore the core group chat loop:

1. **Diagnose why stop hooks aren't firing** for channel member agents. This is the root cause — if hooks fire correctly, the existing relay path works.

2. **Add channel relay to transcript reconciler** as defense in depth. When the reconciler creates a COMPLETION/END_OF_COMMAND Turn for an agent with a channel membership, call `relay_agent_response()`. Same conditions, second integration point. The delivery engine shouldn't depend on *how* the Turn was detected — only *that* it was detected with the right intent.

3. **Wire handoff into channel membership update.** When `SessionCorrelator` assigns a persona to a new agent, update any `ChannelMembership` rows for that persona with the new `agent_id`. This is S4 PRD FR14 — verify whether it's implemented.

### Priority 2 — End-to-End Test Coverage (Finding V5)

Write at minimum one integration test that exercises the full pipeline:
- Create a channel with members
- Send a message via API
- Verify DB persistence
- Verify SSE broadcast fires with correct payload
- Verify delivery service fans out to members

This is the project's known Achilles heel (voice chat ordering incident). Mock-based tests prove layers; integration tests prove the feature.

### Priority 3 — PRD Text Cleanup (Findings F3, F4, V1, V2, F7, V9)

Six PRD text issues from incomplete remediation or implementation-time drift. The code is correct in all cases — the PRDs need to catch up:
- S4: Resolve SSE scope contradiction (Section 2.1 vs 2.2)
- S4: Resolve caller identity precedence (three conflicting descriptions)
- S5: Add `join` and `available-members` endpoints
- S5: Align SSE payload schema to actual implementation
- S1: Document persistent Turns approach (replacing `synthetic_turn`)
- S1: Update CLI namespace

### Priority 4 — Test Coverage for Voice Bridge Channels (Finding F6)

Sprint 8 channel intent detection has no dedicated tests. Add tests for:
- All 6 channel intent patterns
- Fuzzy channel name matching (exact, substring, token overlap, ambiguous, no match)
- Channel context tracking ("this channel" resolution)
- Error cases (missing context, service unavailable)

### Priority 5 — Minor Gaps (Findings V4, V10, V11, F1, F2)

- Add guard clause for deactivated persona in `_resolve_caller()`
- Confirm/implement API endpoint for handoff history (`GET /api/personas/<slug>/handoffs`)
- Verify dashboard visual distinction for handoff turns
- Update conceptual roadmap to include Epic 9
- Track handoff trigger mechanism as a v2 design item

---

## 8. Architectural Assessment

### What Went Well

- **Workshop-first approach worked.** 26 decisions resolved before any code was written. The implementation closely follows the workshop design with minimal drift.
- **Data model is clean.** Three tables, two enums, correct constraints, partial unique index for one-agent-one-channel. Mark's review found 100% fidelity.
- **Service layer is comprehensive.** ChannelService at ~1,425 lines is a proper domain service with error hierarchy, lifecycle management, and SSE broadcasting.
- **Multi-frontend architecture is sound.** Single service, four frontends (CLI, API, dashboard, voice). All call the same ChannelService methods. This was a good design call.
- **Implementation exceeded spec in useful ways.** Dashboard UI added kebab menu, info panel, member autocomplete, optimistic dedup — all genuine UX improvements.

### What Needs Attention

- **Single integration point for relay is fragile.** The completion relay depends entirely on the hook receiver. The transcript reconciler — a legitimate fallback path — has no channel awareness. Defense in depth is needed.
- **Mock-heavy test strategy masks integration failures.** This is a project-wide pattern, not channels-specific. But channels is the most integration-dependent feature yet built — it spans hooks, services, SSE, tmux, and frontend JS. Mock-only testing is insufficient for this kind of cross-cutting feature.
- **PRD maintenance lag.** Cross-PRD review found 15 issues, remediation fixed most, but two critical text contradictions remain. Implementation-time additions (2 extra endpoints, SSE schema changes) weren't back-propagated to PRDs. If PRDs are reference docs, they need a maintenance pass.

### Architectural Debt

- Handoff trigger mechanism (conceptual §6, Open Q1) is still unresolved and will become pressing as context windows fill during real team operations.
- Channel behavioral primer (Workshop 0.4) — the two-layer architecture (base primer + channel intent) is modelled in the data but the actual primer injection into agents at channel join is not yet implemented.

---

## 9. Review Gaps

**Shorty's services review (S4/S6) was delivered informally** — scattered observations rather than a structured report. Extractable findings:

- **S4 service architecture verified:** Error hierarchy, advisory locks, and post-commit pattern confirmed sound
- **Caller identity deviation (security):** `HEADSPACE_AGENT_ID` env var deliberately removed as spoofable; code uses tmux-only resolution; S4 PRD still describes the two-strategy cascade — PRD update needed
- **Relay queries by agent_id:** Stale membership after handoff causes silent relay failure (confirmed by Mark as part of Finding 10)
- **In-memory queue risk:** Delivery queue lost on server restart; messages persist in DB but queued-but-undelivered messages are lost
- **One-message-per-drain latency:** In busy channels, agents receive one queued message per state transition; could cause delivery lag in high-traffic workshops

**Not independently verified** (no structured review delivered):
- ChannelService method-by-method comparison against S4 PRD functional requirements
- CLI command coverage against S4 PRD specification
- Feedback loop prevention (three mechanisms per Workshop 3.2)
- COMMAND COMPLETE stripping logic verification

---

## 10. Architectural Direction (Per Sam)

**Stop hooks are unreliable — that's upstream (Claude Code), outside our control.** The fix strategy is NOT to make hooks reliable. Instead:

1. **Promote the transcript reconciler + IntentDetector as the primary channel relay path.** When the reconciler creates a Turn with COMPLETION/END_OF_COMMAND intent for a channel member, call `relay_agent_response()`. Mark verified the interface is compatible — no hook-specific context assumed.

2. **Advance the IntentDetector** to handle cases where agents don't produce a clean COMMAND COMPLETE footer. Agents may stop mid-thought, await input, or produce substantive responses without the explicit signal. The IntentDetector needs to recognise "composed response that should relay" without depending on the footer.

3. **Treat hooks as best-effort bonus.** The existing hook → relay path stays, but the reconciler path becomes the reliable backbone.

This reframes Priority 1: we're not "fixing hooks and adding a fallback" — we're promoting the reconciler to primary path.

### Verification Criteria (Verner)

**Critical 1 — Relay Pipeline:**
- Integration test: agent completes turn via reconciler path → message appears in channel
- Integration test: agent completes turn via hook path → same result
- Both paths produce identical channel messages

**Critical 2 — End-to-End Coverage:**
- At minimum one test exercising: message sent to channel → delivery to agent via tmux → agent responds → response captured → relayed back to channel → SSE broadcast → correct payload shape

**Critical 3 — Handoff Membership:**
- Test: agent hands off → successor registers → membership agent_id updated → delivery works for successor

---

## 11. Conclusion

Epic 9 is architecturally sound and substantially complete. The workshop-first approach produced clean specifications, and the implementation follows them with high fidelity. The three critical findings (relay pipeline, test coverage, handoff-membership linkage) are integration-level issues — the individual components are correct, but the seams between them have gaps. Fixing the relay pipeline and adding integration tests would bring this feature to production-ready status.

---

*Review conducted in #workshop-channels-functional-review-14 on 5 March 2026.*
*Consolidated by Robbo (Architect) from findings by Mark, Verner, Shorty (partial), and Robbo.*
