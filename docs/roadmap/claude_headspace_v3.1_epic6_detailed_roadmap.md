# Epic 6 Detailed Roadmap: Voice Bridge & Agent Chat

**Project:** Claude Headspace v3.1  
**Epic:** Epic 6 — Voice Bridge & Agent Chat  
**Author:** PM Agent (John)  
**Status:** Roadmap — Baseline for PRD Generation  
**Date:** 2026-02-11

---

## Executive Summary

This document serves as the **high-level roadmap and baseline** for Epic 6 implementation. It breaks Epic 6 into 3 initial sprints (1 sprint = 1 PRD = 1 OpenSpec change), identifies subsystems that require OpenSpec PRDs, and provides the foundation for generating detailed Product Requirements Documents for each subsystem. This roadmap is designed to grow as new ideas emerge — additional sprints will be appended as they are scoped and workshopped.

**Epic 6 Goal:** Enable hands-free voice interaction with Claude Code agents from mobile devices and transform the agent chat into a rich, lifetime conversation view with real-time intermediate message capture.

**Epic 6 Value Proposition:**

- **Voice Bridge Server** — Voice-friendly API layer, enhanced question data model, token-based LAN authentication, and LLM-powered concise output formatting for listening rather than reading
- **Voice Bridge Mobile Client** — PWA for iPhone/iPad with speech-to-text input, text-to-speech output, audio cues, real-time SSE updates, and hands-free agent interaction
- **Agent Chat History** — Agent-lifetime conversation spanning all tasks, real-time intermediate message capture, iMessage-style timestamps, smart message grouping, paginated scroll, and universal chat links across the dashboard

**The Differentiator:** Epic 6 breaks Claude Headspace free from the desk. Until now, interacting with agents required being at the Mac — seeing a question on the dashboard and typing a response. The Voice Bridge enables the user to monitor and command agents from anywhere in the house (or yard, or bike ride) via their iPhone, hearing concise spoken summaries and answering questions by voice. The Agent Chat History transforms fragmented task-scoped views into a continuous iMessage-like conversation, making agent interactions feel natural and persistent. Together, these features make Claude Headspace a truly ambient development companion.

**Success Criteria:**

- Ask "what needs my attention?" from iPhone → hear concise spoken summary of agent statuses
- Speak an answer to an agent's question → agent resumes without touching the Mac
- Audio cue plays when an agent needs input → user aware without looking at screen
- PWA installable on iPhone via "Add to Home Screen" → standalone mode
- Open agent chat → see full conversation across all tasks, not just current task
- Agent intermediate messages appear in real-time as the agent works (within 5 seconds)
- Scroll up in chat → older messages load seamlessly
- Chat accessible from dashboard cards, project pages, and activity views
- Ended agents retain readable chat history

**Architectural Foundation:** Builds on Epic 5's tmux bridge (E5-S4), input bridge (E5-S1), CLI tmux alignment (E5-S8), full command/output capture (E5-S9), and dashboard restructure (E5-S6). Leverages Epic 3's inference service and summarisation. Extends Epic 4's project controls and activity monitoring.

**Dependency:** Epic 5 must be complete before Epic 6 begins (tmux bridge, input bridge, full output capture, and CLI launcher must exist).

---

## Epic 6 Story Mapping

| Story ID | Story Name                                             | Subsystem               | PRD Directory | Sprint | Priority |
| -------- | ------------------------------------------------------ | ----------------------- | ------------- | ------ | -------- |
| E6-S1    | Voice-friendly server API with auth and question model | `voice-bridge-server`   | bridge/       | 1      | P1       |
| E6-S2    | PWA mobile client for hands-free voice interaction     | `voice-bridge-client`   | bridge/       | 2      | P1       |
| E6-S3    | Agent-lifetime chat with real-time intermediate msgs   | `agent-chat-history`    | bridge/       | 3      | P1       |

---

## Sprint Breakdown

### Sprint 1: Voice Bridge Server (E6-S1)

**Goal:** Server-side API, enhanced data model, LLM-powered voice output formatting, and token-based LAN authentication for voice-driven interaction with Claude Code agents.

**Duration:** 1-2 weeks  
**Dependencies:** Epic 5 complete (tmux bridge, input bridge, full output capture, CLI launcher)

**Deliverables:**

**Turn Model Enhancement:**

- Question turns (intent=QUESTION) store structured question detail: question text, list of options (labels + descriptions), question source type (ask_user_question, permission_request, free_text)
- Answer turns (intent=ANSWER) store a reference to the question turn they resolve (question-answer pairing)
- Question detail and answer linkage exposed in turn-related API responses
- Alembic migration for new Turn columns/foreign key

**Voice Command API:**

- Voice command endpoint: accepts text command + optional target agent identifier
- Auto-targeting: if no target specified and exactly one agent awaiting input, route to that agent automatically
- Session listing endpoint: all active agents with project name, state, input-needed flag, task summary, time since last activity (structured for voice, no HTML)
- Output retrieval endpoint: recent agent activity (last N commands + outputs, concise text)
- Question detail endpoint: full question context for AWAITING_INPUT agents (question text, options, source type, agent/project context)
- Non-structured question passthrough: full question text returned when no AskUserQuestion options exist

**Voice Output Formatting:**

- Voice-friendly response format: status line (1 sentence) + key results (1-3 bullets) + next action (0-2 bullets)
- Verbosity parameter: concise (default), normal, detailed
- LLM-powered formatting via existing InferenceService with caching
- Error responses formatted for voice: short phrase + one suggestion, no stack traces or status codes

**Authentication & Network:**

- Token-based authentication middleware on all voice bridge endpoints
- Configurable localhost bypass (optional, for development)
- Network binding configurable: localhost-only (default) or LAN-accessible (0.0.0.0)
- Voice bridge configuration section in config.yaml (token, network bind, rate limits, verbosity)
- Rate limiting: configurable, default 60 requests/minute per token
- Access logging: timestamp, source IP, endpoint, target agent, auth status, response latency

**Subsystem Requiring PRD:**

1. `voice-bridge-server` — Turn model enhancement, voice API endpoints, voice output formatting, authentication middleware, network configuration

**PRD Location:** `docs/prds/bridge/done/e6-s1-voice-bridge-server-prd.md`

**Stories:**

- E6-S1: Voice-friendly server API with auth and question model

**Technical Decisions Made:**

- Separate Flask blueprint for voice bridge endpoints — **decided**
- Token-based auth (not OAuth or session-based) — **decided** (single-user system, LAN-only)
- Voice output formatting via existing InferenceService — **decided** (reuse caching + rate limiting)
- Turn model foreign key for question-answer linking — **decided**
- Question source types: ask_user_question, permission_request, free_text — **decided**
- No WebSocket support (SSE sufficient for server-to-client push) — **decided**

**Data Model Changes:**

```python
class Turn(Base):
    ...
    # Question detail (for intent=QUESTION turns)
    question_text: Mapped[str | None]          # The question text
    question_options: Mapped[dict | None]       # JSONB: list of options with labels/descriptions
    question_source_type: Mapped[str | None]    # ask_user_question, permission_request, free_text

    # Answer linkage (for intent=ANSWER turns)
    answers_turn_id: Mapped[UUID | None]        # FK to the question Turn this answer resolves
```

**API Endpoints:**

| Endpoint                             | Method | Description                                            |
| ------------------------------------ | ------ | ------------------------------------------------------ |
| `/api/voice/command`                 | POST   | Submit voice command to agent (auto-target or explicit) |
| `/api/voice/sessions`               | GET    | List active agents with voice-friendly status           |
| `/api/voice/agents/<id>/output`     | GET    | Recent agent output (concise text)                      |
| `/api/voice/agents/<id>/question`   | GET    | Full question context for AWAITING_INPUT agent          |

**API Response Example (Session Listing, Concise Verbosity):**

```
Status: You have 3 agents running. One needs your input.
- claude-headspace: awaiting input — asking about test approach
- raglue: processing — running integration tests
- ot-monitor: idle since 5 minutes ago
Action needed: Respond to claude-headspace.
```

**Risks:**

- Token security on LAN (mitigated: single-user system, LAN-only scope)
- LLM latency for voice formatting (mitigated: caching, concise mode as default)
- Turn model migration affecting existing data (mitigated: nullable new columns, non-breaking)

**Acceptance Criteria:**

- [ ] Voice command via API delivered to correct agent; agent resumes processing
- [ ] Question turns store full question context (text, options, type)
- [ ] Answer turns linked to question turn they resolve
- [ ] Non-structured agent questions return full question text via API
- [ ] Voice output summaries follow concise format: status + key results + next action
- [ ] All voice API endpoints accessible from another LAN device with valid token
- [ ] Invalid/missing tokens rejected with appropriate error
- [ ] Requests to non-AWAITING_INPUT agents return helpful voice-friendly error
- [ ] API response latency (excluding LLM) under 500ms
- [ ] Voice output formatting (with LLM) completes within 2 seconds

---

### Sprint 2: Voice Bridge Mobile Client (E6-S2)

**Goal:** Progressive Web App for iPhone/iPad enabling hands-free voice interaction with Claude Code agents — speech input, spoken output, audio cues, and real-time status updates.

**Duration:** 2-3 weeks  
**Dependencies:** E6-S1 complete (voice bridge server API, authentication, voice-friendly responses)

**Deliverables:**

**Speech Input:**

- Active listening mode: speech captured and converted to text via browser Web Speech API
- Automatic end-of-utterance detection with configurable silence timeout (default 800ms, range 600-1200ms)
- Optional spoken "done word" (configurable: "send", "over", "done") to finalise input immediately
- Debounce mechanism: speech resuming within silence timeout window resets the timeout
- Text input fallback for quiet environments or precise technical input

**Speech Output:**

- Text-to-speech for all voice-friendly API responses (toggleable)
- Audio cues (earcons) for key events: ready, sent, agent needs input, error
- TTS reads responses in voice-friendly format: status → key results → next action, with pauses between sections
- Audio cues play regardless of TTS toggle

**Agent Interaction:**

- Agent list view: project name, state (colour-coded), input-needed indicator, current task summary
- Real-time updates via SSE connection
- Target agent by tapping list or speaking project name
- Auto-targeting when exactly one agent awaiting input
- Structured question options displayed as tappable buttons (select by tap or by speaking option number/label)
- Free-text questions: full question text displayed, respond by speaking or typing

**Real-Time Updates:**

- SSE connection to server for live status changes
- AWAITING_INPUT transition triggers "needs input" audio cue and list update
- Auto-reconnect with exponential backoff; periodic polling fallback

**Authentication & Configuration:**

- First-launch setup: server URL + authentication token (stored in localStorage)
- Settings screen: silence timeout, done-word selector, TTS toggle, audio cues toggle, verbosity level

**PWA Requirements:**

- Web app manifest for "Add to Home Screen" installation (standalone mode, icons, theme colours)
- Service worker for app shell caching (HTML, CSS, JS — offline launch, API calls still require network)
- Total bundle under 100KB uncompressed

**Subsystem Requiring PRD:**

2. `voice-bridge-client` — PWA client, speech I/O, agent list, question presentation, SSE, settings

**PRD Location:** `docs/prds/bridge/done/e6-s2-voice-bridge-client-prd.md`

**Stories:**

- E6-S2: PWA mobile client for hands-free voice interaction

**Technical Decisions Made:**

- Vanilla HTML/CSS/JS (no framework) — **decided** (matches existing frontend, minimises bundle)
- Browser-native Web Speech API (no external STT/TTS service) — **decided**
- PWA via service worker (not native app) — **decided** (v1 scope)
- Optimised for mobile Safari on iOS 16+ — **decided**
- Client state in localStorage only — **decided**
- No wake-word detection in v1 (extension point only) — **decided**

**UI Screens:**

```
HOME / AGENT LIST
┌──────────────────────────────────────┐
│  Claude Headspace                    │
│                                      │
│  ┌──────────────────────────────┐   │
│  │ ● claude-headspace           │   │
│  │   awaiting input             │   │
│  │   "Which test approach?"     │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │ ○ raglue                     │   │
│  │   processing                 │   │
│  │   Running integration tests  │   │
│  └──────────────────────────────┘   │
│                                      │
│  ┌──────────────────────────────┐   │
│  │ ○ ot-monitor                 │   │
│  │   idle · 5 min ago           │   │
│  └──────────────────────────────┘   │
│                                      │
│         [🎤 Microphone]              │
│                                      │
│  [Settings]                          │
└──────────────────────────────────────┘

LISTENING / COMMAND MODE
┌──────────────────────────────────────┐
│                                      │
│         ((🎤))                        │
│      Listening...                    │
│                                      │
│  "Use integration tests for the     │
│   login module"                      │
│                                      │
│  → claude-headspace                  │
│                                      │
│  Hint: say "send" to finalise       │
│                                      │
│         [Cancel]                     │
└──────────────────────────────────────┘

QUESTION / RESPONSE MODE
┌──────────────────────────────────────┐
│  < Back                              │
│                                      │
│  claude-headspace                    │
│  "Which testing approach?"           │
│                                      │
│  ┌──────────────────────────────┐   │
│  │ 1. Unit tests only           │   │
│  │    faster but less coverage  │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ 2. Integration tests         │   │
│  │    slower but more thorough  │   │
│  └──────────────────────────────┘   │
│  ┌──────────────────────────────┐   │
│  │ 3. Both                      │   │
│  │    comprehensive but longest │   │
│  └──────────────────────────────┘   │
│                                      │
│  Or speak/type your answer:          │
│  ┌─────────────────────────┐ [🎤]  │
│  │                         │        │
│  └─────────────────────────┘        │
└──────────────────────────────────────┘
```

**Risks:**

- iOS Safari Web Speech API limitations (mitigated: text fallback always available)
- End-of-utterance detection in noisy environments (mitigated: configurable silence timeout + done word)
- PWA install experience on iOS may be confusing (mitigated: clear onboarding instructions)
- SSE connection stability on mobile (mitigated: auto-reconnect + polling fallback)

**Acceptance Criteria:**

- [ ] User can speak a command on iPhone → delivered to correct agent → agent resumes
- [ ] User hears agent status summaries read aloud without looking at screen
- [ ] Structured questions presented with selectable options; free-text shows full question
- [ ] End-of-utterance detection finalises after configurable silence period
- [ ] Spoken "done word" immediately finalises input
- [ ] Audio cues play for state transitions (needs input, sent, error)
- [ ] PWA installable via "Add to Home Screen" → standalone mode
- [ ] Real-time status updates via SSE without manual refresh
- [ ] Speech recognition starts within 1 second of activating listening mode
- [ ] End-to-end latency (speech finalisation to agent receipt) under 3 seconds on LAN
- [ ] PWA loads and is interactive within 2 seconds on iPhone
- [ ] Works on iOS Safari 16+

---

### Sprint 3: Agent Chat History (E6-S3)

**Goal:** Transform the chat into an agent-lifetime conversation view with real-time intermediate message capture, iMessage-style display, paginated scroll, and universal chat links.

**Duration:** 1-2 weeks  
**Dependencies:** E6-S1 and E6-S2 complete (voice bridge server and client provide the chat foundation)

**Deliverables:**

**Real-Time Intermediate Message Capture:**

- Agent text output between tool calls captured as PROGRESS turns linked to current task
- Incremental transcript reading from last known position (no re-reading)
- Deduplication between intermediate PROGRESS turns and final COMPLETION turn from stop hook
- Empty/whitespace-only text blocks filtered out

**Agent-Lifetime Conversation View:**

- Chat transcript endpoint returns turns across all tasks for a given agent, ordered chronologically
- Each turn includes task identifier for client-side task boundary detection
- Task boundary separators with task instruction text and state
- Full history from agent's first task through current task, with real-time updates

**Pagination:**

- Cursor-based pagination (turn ID, not offset-based) for consistent results with concurrent writes
- Client requests most recent N turns (default 50), requests older turns via cursor
- Scroll-to-top triggers next page load; new messages prepended without disrupting scroll position
- Loading indicator at top; "all loaded" indicator when no more pages

**Timestamps (iMessage-Style):**

- Timestamps on first message and after 5+ minute gaps
- Today: time-only (e.g., "2:30 PM")
- Yesterday: "Yesterday 2:30 PM"
- This week: day-of-week with time (e.g., "Monday 2:30 PM")
- Older: month/day with time (e.g., "Feb 3, 2:30 PM")

**Smart Message Grouping:**

- Consecutive agent messages within 2 seconds grouped into single bubble (line-break separated)
- Intent change always breaks a group (PROGRESS → QUESTION, PROGRESS → COMPLETION)
- User messages (COMMAND, ANSWER) never grouped — each is its own bubble

**Task Separators:**

- Subtle visual separator at task boundaries (centered text with horizontal rules)
- Shows task instruction for the new task
- Unobtrusive — does not dominate conversation flow

**Chat Links Everywhere:**

- Dashboard agent cards: chat link (existing, unchanged)
- Project show page: chat icon/link for each agent (active and ended)
- Activity page: chat link where agents are individually referenced
- Ended agent chat: read-only mode (full history, no input bar, "Agent ended" indicator)

**Subsystem Requiring PRD:**

3. `agent-chat-history` — Agent-lifetime transcript API, intermediate message capture, pagination, iMessage timestamps, smart grouping, universal chat links

**PRD Location:** `docs/prds/bridge/done/e6-s3-agent-chat-history-prd.md`

**Stories:**

- E6-S3: Agent-lifetime chat with real-time intermediate messages

**Technical Decisions Made:**

- No Turn model schema changes needed (PROGRESS intent already exists) — **decided**
- Smart message grouping performed client-side — **decided** (avoids server-side complexity)
- Cursor-based pagination (turn ID) not offset-based — **decided** (consistent with concurrent writes)
- New messages appended to DOM without full re-render — **decided** (preserves scroll position)
- Transcript reading uses existing incremental position-based approach — **decided**

**Chat UI Layout:**

```
┌──────────────────────────────────────┐
│  < Back            claude-headspace  │
├──────────────────────────────────────┤
│                                      │
│           Mon 2:30 PM                │
│  ── Fix the login bug ──────────    │
│                                      │
│  Fix the login bug in the auth   ◀  │
│  module. Users are getting 401       │
│  errors on valid tokens.             │
│                                      │
│  ▶  Let me explore the current       │
│     implementation...                │
│                                      │
│  ▶  I'll check the token            │
│     validation logic and the         │
│     middleware chain.                │
│                                      │
│  ▶  Found the issue. The JWT        │
│     expiry check was using UTC       │
│     but tokens had local time.       │
│     Fixed and tests passing.         │
│                                      │
│           2:45 PM                    │
│  ── Add integration tests ────────  │
│                                      │
│  Now add integration tests for   ◀  │
│  the auth module.                    │
│                                      │
│  ▶  Which testing approach should   │
│     we use?                          │
│     [1: Unit only] [2: Integration] │
│     [3: Both]                        │
│                                      │
│  Use integration tests            ◀  │
│                                      │
│  ▶  Running integration tests...    │
│  ▶  ···                              │
│                                      │
├──────────────────────────────────────┤
│  ┌─────────────────────────┐ [🎤]  │
│  │ Type a message...       │ [Send] │
│  └─────────────────────────┘        │
└──────────────────────────────────────┘
```

**Risks:**

- Large conversation histories affecting load performance (mitigated: cursor-based pagination, 50-turn default page)
- Intermediate message capture adding latency to hook processing (mitigated: async capture, <50ms requirement)
- Deduplication between PROGRESS and COMPLETION turns (mitigated: text comparison, position tracking)
- Smart grouping edge cases with rapid intent changes (mitigated: intent change always breaks group)

**Acceptance Criteria:**

- [ ] Chat shows complete conversation across all tasks, not just current task
- [ ] Intermediate agent text messages appear within 5 seconds of agent producing them
- [ ] Scrolling up loads older messages without page reload
- [ ] Task transitions visible as subtle separators with task instruction
- [ ] Rapid consecutive agent messages (within 2 seconds) grouped into single bubble
- [ ] Chat accessible for ended agents from project show page and activity page
- [ ] Timestamps follow iMessage conventions
- [ ] Loading initial 50 turns completes within 500ms
- [ ] Loading older page on scroll-up completes within 500ms
- [ ] PROGRESS turn capture adds no more than 50ms to hook response
- [ ] Agent with 500+ turns renders without performance degradation

---

## Sprint Dependencies & Sequencing

```
E6-S1 (Voice Bridge Server)
   │
   └──▶ E6-S2 (Voice Bridge Client)
           │
           └──▶ E6-S3 (Agent Chat History)
```

**Critical Path:** E6-S1 → E6-S2 → E6-S3 (strictly sequential)

**Rationale:**

- E6-S2 (Client) consumes E6-S1 (Server) APIs — cannot build client without server
- E6-S3 (Chat History) extends the chat screen introduced in E6-S2 — requires the client foundation
- No parallelisation opportunities within the initial 3 sprints (each builds on the previous)

---

## Cross-Epic Dependencies

```
Epic 5 (Voice Bridge & Project Enhancement)
   │
   ├── E5-S1 (Input Bridge) ──────────────────────┐
   ├── E5-S4 (tmux Bridge) ───────────────────────┤
   ├── E5-S8 (CLI tmux Alignment) ────────────────┤
   └── E5-S9 (Full Command/Output Capture) ───────┤
                                                    │
                                                    ▼
                                              Epic 6 (Voice Bridge & Agent Chat)
                                                    │
                                                    ├── E6-S1 (Server)
                                                    ├── E6-S2 (Client)
                                                    └── E6-S3 (Chat History)
```

Epic 3's InferenceService and PromptRegistry are also leveraged by E6-S1 for voice output formatting.

---

## Acceptance Test Cases

### Test Case 1: Voice Command Delivery

**Setup:** Server running on LAN, one agent in AWAITING_INPUT state, iPhone on same network with PWA installed.

**Success:**

- ✅ Open PWA on iPhone → agent list shows with status
- ✅ Tap microphone → listening mode activates within 1 second
- ✅ Speak answer → transcription appears in real-time
- ✅ Silence timeout or "done word" finalises → command sent
- ✅ Confirmation tone plays → agent resumes processing
- ✅ Agent card updates to PROCESSING state via SSE
- ✅ Total latency from speech to agent receipt under 3 seconds

### Test Case 2: Hands-Free Monitoring

**Setup:** Multiple agents running, one transitions to AWAITING_INPUT while user is away from Mac.

**Success:**

- ✅ "Needs input" audio cue plays on iPhone
- ✅ Agent list updates in real-time
- ✅ User says "what needs my attention?" → hears concise spoken summary
- ✅ User says "what's the question?" → hears full question read aloud
- ✅ Structured options read as numbered list
- ✅ User speaks option number → answer sent to correct agent

### Test Case 3: Authentication & Security

**Setup:** Server bound to 0.0.0.0, token configured in config.yaml.

**Success:**

- ✅ Request with valid token → 200 response
- ✅ Request with invalid token → 401 response
- ✅ Request with no token → 401 response
- ✅ Localhost request without token (if bypass enabled) → 200 response
- ✅ Access log captures all requests with IP, endpoint, auth status, latency
- ✅ Rate limiting enforced (60 req/min default)

### Test Case 4: Agent Chat History

**Setup:** Agent has completed 2 tasks and is working on a 3rd, 80+ turns total.

**Success:**

- ✅ Open chat → sees most recent 50 turns (current task + some from previous)
- ✅ Scroll up → older messages load, scroll position preserved
- ✅ Task separators visible between task boundaries
- ✅ Intermediate agent messages appear in real-time as agent works
- ✅ Rapid agent messages grouped into single bubble
- ✅ Timestamps follow iMessage conventions
- ✅ After agent ends → chat still accessible from project page (read-only)

### Test Case 5: End-to-End Epic 6 Flow

**Setup:** Fresh Epic 6 deployment with Epics 1-5 complete. Two agents running.

**Success:**

- ✅ Start agents via `claude-headspace start --bridge`
- ✅ Open PWA on iPhone → authenticate with token
- ✅ See both agents in list with real-time status
- ✅ Agent asks question → "needs input" audio cue on iPhone
- ✅ Speak answer → agent resumes → confirmation tone
- ✅ Open chat on iPhone → see full agent conversation with intermediate messages
- ✅ Open chat on dashboard → same history, task separators, pagination
- ✅ Agent ends → chat remains accessible (read-only) from project page
- ✅ TTS reads status summaries and question details aloud
- ✅ Everything works hands-free without looking at the screen

---

## Recommended PRD Generation Order

Generate OpenSpec PRDs in implementation order:

### Phase 1: Voice Bridge Server (Week 1-2) — DONE

1. **voice-bridge-server** (`docs/prds/bridge/done/e6-s1-voice-bridge-server-prd.md`) — Turn model enhancement, voice API, voice output formatting, authentication, network config

**Rationale:** Foundational server infrastructure that the client depends on. Can be fully tested with curl/httpie before any client exists.

---

### Phase 2: Voice Bridge Client (Week 3-5) — DONE

2. **voice-bridge-client** (`docs/prds/bridge/done/e6-s2-voice-bridge-client-prd.md`) — PWA, speech I/O, agent list, question presentation, SSE, settings

**Rationale:** Consumes the server APIs from Phase 1. Introduces the chat screen that Phase 3 extends.

---

### Phase 3: Agent Chat History (Week 5-7) — DONE

3. **agent-chat-history** (`docs/prds/bridge/done/e6-s3-agent-chat-history-prd.md`) — Agent-lifetime transcript, intermediate messages, pagination, timestamps, chat links

**Rationale:** Extends the chat foundation from Phase 2 with rich history and real-time intermediate capture.

---

## Future Sprints (Planned / Under Consideration)

Epic 6 is designed to grow. The following ideas are candidates for future sprints as they are scoped and workshopped. This section will be updated as new PRDs are created.

### Voice Interactivity (Candidate)

Full conversational voice interaction with agents — integrating a speech-to-text/text-to-speech model for natural voice chat beyond the current push-to-talk approach. This may repurpose or retire the `screen-listening` and `screen-question` views currently unused in the voice client (see `docs/todo/TODO.md`).

**Status:** Idea — requires scoping and PRD workshop

### Wake-Word Detection (Candidate)

"Hey Claude" or custom wake-word to activate listening without tapping the microphone button. Enables fully ambient hands-free monitoring.

**Status:** Idea — extension point exists in E6-S2, requires scoping

### Cross-Agent Conversation View (Candidate)

Unified timeline view showing interleaved conversations across multiple agents on the same project, enabling the user to see how parallel agents' work relates.

**Status:** Idea — requires scoping and PRD workshop

### Voice Notifications (Candidate)

Proactive voice announcements via TTS when significant events occur — task completions, high-frustration alerts, flow state milestones — without requiring the user to check the app.

**Status:** Idea — requires scoping and PRD workshop

### Chat Search (Candidate)

Full-text search within agent chat history, enabling the user to find specific exchanges, decisions, or errors across the entire conversation.

**Status:** Idea — requires scoping and PRD workshop

---

## Document History

| Version | Date       | Author          | Changes                                         |
| ------- | ---------- | --------------- | ----------------------------------------------- |
| 1.0     | 2026-02-11 | PM Agent (John) | Initial detailed roadmap for Epic 6 (3 sprints) |

---

**End of Epic 6 Detailed Roadmap**
