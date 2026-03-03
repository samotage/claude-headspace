---
validation:
  status: pending
---

## Product Requirements Document (PRD) — Voice Bridge Channel Routing Extensions

**Project:** Claude Headspace v3.2
**Scope:** Epic 9, Sprint 8 — Voice bridge semantic picker extensions for channel routing
**Author:** Robbo (workshopped with Sam)
**Status:** Draft

---

## Executive Summary

The voice bridge is the operator's primary hands-free interface for managing agents. With channels arriving in Sprints 3-7, the voice bridge needs to route channel operations as naturally as it routes agent commands today. The operator should be able to say "send to the workshop channel: let's align on the persona spec" and have it land in the right channel — without switching to the dashboard or typing CLI commands.

This sprint extends the existing voice bridge with channel awareness. The semantic picker gains channel-name matching (same fuzzy algorithm as the existing agent picker). The existing `/api/voice/command` endpoint gains channel command routing — detecting channel-targeted utterances and delegating to `ChannelService`. Voice-formatted responses use the existing `{status_line, results, next_action}` envelope. The Voice Chat PWA sidebar gains a channel message display for real-time channel activity.

No new voice bridge endpoints are created. No auth or rate limiting changes. The existing Bearer token auth and sliding window rate limiter are sufficient. This sprint calls `ChannelService` (S4) — it does not implement channel infrastructure.

All design decisions are resolved in the Inter-Agent Communication Workshop, Section 2.3 (Voice Bridge Channel Routing) and Section 4.1 (Workshop Channel Setup — voice bridge primary path). See `docs/workshop/interagent-communication/sections/section-2-channel-operations.md` and `docs/workshop/interagent-communication/sections/section-4-group-workshop-use-case.md`.

---

## 1. Context & Purpose

### 1.1 Context

The voice bridge (`/api/voice/command`) currently handles three categories of input: agent commands (sent via tmux), handoff intent detection (routed to `HandoffExecutor`), and auto-targeting (finding the single agent awaiting input). All of these are agent-scoped — the voice bridge resolves a target agent and sends text to it.

Channels introduce a second routing dimension. When the operator says "send to the workshop channel: we need to discuss the persona alignment spec," the voice bridge needs to detect the channel intent, fuzzy-match "workshop" against active channel names, and route to `ChannelService.send_message()` — bypassing the agent-targeting path entirely.

The existing semantic picker (`_match_picker_option` in `voice_bridge.py`) handles option matching for structured pickers. Agent targeting uses explicit `agent_id` or auto-target single-agent resolution. Neither has fuzzy name matching on entities. Channel routing requires a proper entity-matching layer: tokenize the utterance, extract channel references, fuzzy-match against the active channel set.

The operator's preferred channel interaction is voice-first (Workshop Section 4.1, Decision 4.1). The dashboard and CLI are secondary. The voice bridge is where channels need to feel native.

### 1.2 Target User

The operator (Sam), who manages channels via voice while monitoring agents on the dashboard. The voice bridge is the operator's primary interface — it must handle channel operations without requiring the operator to switch to the CLI or dashboard.

### 1.3 Success Moment

Sam says: "Create a workshop channel called persona alignment with Robbo and Paula." The voice bridge creates the channel, adds both personas, and responds: "Created channel persona-alignment-workshop. Robbo joined. Paula's agent is spinning up." Ten seconds later: "Send to persona alignment: Let's discuss the persona alignment approach for the new org structure." The message lands in the channel and fans out to both agents via tmux. The entire setup took 30 seconds of voice — no typing, no dashboard, no CLI.

---

## 2. Scope

### 2.1 In Scope

- Extend existing semantic picker with channel-name fuzzy matching
- Fuzzy match on channel name and slug (same algorithm as existing agent picker patterns)
- Ambiguity handling: multiple channel matches return clarification prompt
- Voice command routing for channel operations via existing `/api/voice/command` endpoint:
  - "send to workshop channel: [content]" -> `ChannelService.send_message()`
  - "what's happening in the workshop?" -> GET channel messages, voice-formatted summary
  - "create a delegation channel for [task]" -> `ChannelService.create_channel()` with inferred type
  - "add Con to this channel" -> `ChannelService.add_member()` (requires current channel context)
  - "complete the persona alignment channel" -> `ChannelService.complete_channel()`
- Voice-formatted responses via existing `VoiceFormatter`: `{status_line, results, next_action}`
- Channel context tracking: "this channel" / "the channel" resolves to most recently referenced channel
- Voice Chat PWA (`/voice`) channel message display in sidebar

### 2.2 Out of Scope

- Channel data models (S3)
- ChannelService implementation (S4 — this sprint CALLS it)
- Channel API endpoints (S5)
- Delivery engine (S6)
- Dashboard UI for channels (S7)
- Voice bridge auth changes (existing Bearer token auth works)
- Voice bridge rate limiting changes (existing sliding window rate limiter sufficient)
- New voice bridge endpoints (uses existing `/api/voice/command`)
- Channel-specific SSE events in the voice bridge (uses existing `channel_message` and `channel_update` SSE types from S5)
- Voice bridge TTS/speech-to-text changes
- Channel file attachments via voice

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. The voice bridge routes "send to [channel-name]: [content]" to `ChannelService.send_message()` and returns a voice-formatted confirmation
2. The voice bridge routes "what's happening in [channel-name]?" to channel message retrieval and returns a voice-formatted summary of the last 10 messages
3. The voice bridge routes "create a [type] channel [called name] [with members]" to `ChannelService.create_channel()` and returns confirmation with member join status
4. The voice bridge routes "add [persona-name] to [channel-name/this channel]" to `ChannelService.add_member()` and returns confirmation
5. The voice bridge routes "complete [channel-name]" to `ChannelService.complete_channel()` and returns confirmation
6. Channel name matching is fuzzy: "the workshop" matches `workshop-persona-alignment-7`, "persona alignment" matches `workshop-persona-alignment-7`
7. When multiple channels match a fuzzy query, the voice bridge returns a clarification prompt listing the ambiguous matches
8. "this channel" and "the channel" resolve to the most recently referenced channel in the current voice session
9. The Voice Chat PWA sidebar displays channel messages from `channel_message` SSE events
10. Channel operations that fail (not a member, channel complete, no creation capability) return actionable voice-formatted error messages

### 3.2 Non-Functional Success Criteria

1. Channel command detection adds no perceptible latency to the `/api/voice/command` response path
2. The existing agent command path is unaffected — utterances that are not channel-targeted continue to route to agents
3. All existing voice bridge tests continue to pass
4. Channel name matching handles speech-to-text artifacts (missing articles, singular/plural variations, common misheard words)

---

## 4. Functional Requirements (FRs)

### Channel Intent Detection

**FR1: Channel command detection in voice_command()**
The existing `voice_command()` function in `voice_bridge.py` shall detect channel-targeted utterances before attempting agent resolution. Channel detection runs after handoff intent detection and before agent auto-targeting. If a channel intent is detected, the function routes to the appropriate `ChannelService` method and returns without entering the agent path.

**FR2: Channel command patterns**
The following voice patterns shall be recognised and routed:

| Pattern | Routes to | Example |
|---------|-----------|---------|
| "send to [channel]: [content]" | `ChannelService.send_message()` | "send to workshop channel: let's start" |
| "message [channel]: [content]" | `ChannelService.send_message()` | "message persona alignment: I disagree" |
| "tell [channel]: [content]" | `ChannelService.send_message()` | "tell the workshop: we need to pivot" |
| "what's happening in [channel]" | Channel message history retrieval | "what's happening in the workshop?" |
| "what's going on in [channel]" | Channel message history retrieval | "what's going on in persona alignment?" |
| "show [channel] messages" | Channel message history retrieval | "show workshop messages" |
| "create a [type] channel [name]" | `ChannelService.create_channel()` | "create a delegation channel for auth refactor" |
| "create [type] channel [name] with [members]" | `ChannelService.create_channel()` with members | "create a workshop channel called persona alignment with Robbo and Paula" |
| "add [persona] to [channel]" | `ChannelService.add_member()` | "add Con to the workshop" |
| "add [persona] to this channel" | `ChannelService.add_member()` (context) | "add Con to this channel" |
| "complete [channel]" | `ChannelService.complete_channel()` | "complete the persona alignment channel" |
| "finish [channel]" | `ChannelService.complete_channel()` | "finish the workshop" |

### Channel Name Matching

**FR3: Fuzzy channel name matching**
The channel matcher shall fuzzy-match the extracted channel reference against all active channels (status `pending` or `active`) visible to the operator. Matching shall be performed against both the channel `name` and `slug` fields.

**FR4: Matching algorithm**
The matching algorithm shall follow the same pattern as the existing agent auto-targeting — best effort with disambiguation:
1. Exact match on slug (highest priority)
2. Exact match on name (case-insensitive)
3. Substring match: channel name or slug contains the query
4. Token overlap: query tokens appear in channel name tokens (handles word reordering from speech-to-text)

**FR5: Ambiguity resolution**
If multiple channels match the fuzzy query, the voice bridge shall return a clarification prompt. No default selection on ambiguity.

**FR6: No-match handling**
If no channels match, the voice bridge shall return an error indicating no matching channel was found, with a suggestion to list available channels or use the exact channel name.

### Channel Context Tracking

**FR7: Session-scoped channel context**
The voice bridge shall maintain a per-session "current channel" reference. When a channel operation succeeds, the referenced channel becomes the current channel. Subsequent commands using "this channel" or "the channel" resolve to the current channel.

**FR8: Context storage**
Channel context is stored in the voice bridge's in-memory state (not persisted to DB). It resets when the voice session ends or the operator explicitly targets a different channel.

### Channel Type Inference

**FR9: Channel type inference from voice**
When the operator says "create a delegation channel for [task]," the channel type (`delegation`) is extracted from the utterance. If no type is specified, default to `workshop`. Supported type keywords: `workshop`, `delegation`, `review`, `standup`, `broadcast`.

### Voice-Formatted Responses

**FR10: Send message confirmation**
After successfully sending a channel message, the voice bridge shall return:
```json
{
  "voice": {
    "status_line": "Message sent to #persona-alignment-workshop.",
    "results": [],
    "next_action": "none"
  }
}
```

**FR11: Channel history summary**
When the operator asks what's happening in a channel, the voice bridge shall retrieve the last 10 messages and return a voice-formatted summary:
```json
{
  "voice": {
    "status_line": "Last 10 messages in #persona-alignment-workshop.",
    "results": [
      "Robbo: The persona type hierarchy resolves the identity question cleanly.",
      "Paula: I disagree with the approach to skill file injection.",
      "Sam: Paula raises a good point about timing."
    ],
    "next_action": "none"
  }
}
```

**FR12: Channel creation confirmation**
After creating a channel, the voice bridge shall return:
```json
{
  "voice": {
    "status_line": "Created channel #persona-alignment-workshop (workshop).",
    "results": ["Robbo joined.", "Paula — agent spinning up."],
    "next_action": "none"
  }
}
```

**FR13: Error responses**
Channel operation errors shall use the existing `VoiceFormatter.format_error()` pattern with actionable suggestions:

| Error | Voice Response |
|-------|---------------|
| Not a channel member | `status_line: "You're not a member of #channel-slug."`, `next_action: "Join the channel or ask the chair to add you."` |
| Channel complete/archived | `status_line: "Channel #channel-slug is complete."`, `next_action: "Create a new channel to continue."` |
| No creation capability | `status_line: "Cannot create channels."`, `next_action: "Ask an authorised persona to create the channel."` |
| Ambiguous match | `status_line: "Multiple channels match 'workshop'."`, `results: ["#persona-alignment-workshop", "#api-design-workshop"]`, `next_action: "Say the full channel name."` |
| No match | `status_line: "No channel found matching 'foobar'."`, `next_action: "Check channel names or say 'list channels'."` |

### Persona Name Matching for Member Addition

**FR14: Persona name matching**
When the operator says "add Con to this channel," the voice bridge shall fuzzy-match "Con" against active persona names and slugs. Same algorithm as channel name matching: exact, substring, token overlap. Ambiguous persona matches return a clarification prompt.

### Voice Chat PWA Channel Display

**FR15: Channel messages in sidebar**
The Voice Chat PWA (`/voice`) shall display channel messages from `channel_message` SSE events. Channel messages appear in a dedicated section of the sidebar (below the agent list) or as a separate tab/view, showing: channel name, sender persona name, message preview, and timestamp.

**FR16: Channel message tap-through**
Tapping a channel message in the sidebar shall navigate to a channel detail view showing the full message history in conversational envelope format, consistent with the existing agent chat view.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1: No new endpoints**
All channel routing happens within the existing `/api/voice/command` endpoint. No new Flask routes are added. The channel detection is a routing layer inside `voice_command()`, not a separate endpoint.

**NFR2: Existing agent path unaffected**
Utterances that do not match channel patterns continue through the existing agent resolution path (explicit `agent_id`, auto-target, handoff detection). Channel detection must not produce false positives on agent-targeted commands.

**NFR3: Latency**
Channel name matching (fuzzy match against active channels) shall complete in under 10ms. The `ChannelService` call latency is outside this sprint's control.

**NFR4: Ordering of detection stages**
The detection pipeline in `voice_command()` shall be ordered: (1) handoff intent detection, (2) channel intent detection, (3) agent resolution. This ensures handoff intents are never accidentally captured by channel patterns.

**NFR5: Speech-to-text robustness**
Channel name matching shall tolerate common speech-to-text artifacts: missing/added articles ("the workshop" vs "workshop"), singular/plural variations ("channels" vs "channel"), filler words ("um", "like"), and common homophone errors.

**NFR6: Service registration**
No new service is registered. Channel routing logic is added to the existing `voice_bridge.py` route module, calling `ChannelService` via `app.extensions["channel_service"]`.

---

## 6. Technical Context

### 6.1 Files to Modify

| File | Change |
|------|--------|
| `src/claude_headspace/routes/voice_bridge.py` | Add channel intent detection and routing in `voice_command()`. New helper functions: `_detect_channel_intent()`, `_match_channel()`, `_match_persona_for_channel()`. Add `VoiceFormatter` calls for channel responses. |
| `src/claude_headspace/services/voice_formatter.py` | Add `format_channel_message_sent()`, `format_channel_history()`, `format_channel_created()`, `format_channel_completed()` methods following the existing `{status_line, results, next_action}` pattern. |
| `static/voice/voice-sidebar.js` | Add channel section rendering below agent list. Handle `channel_message` SSE events for real-time updates. |
| `static/voice/voice-sse-handler.js` | Add `handleChannelMessage()` and `handleChannelUpdate()` SSE event handlers. Wire to `VoiceAPI.onChannelMessage()` and `VoiceAPI.onChannelUpdate()` callbacks. |
| `static/voice/voice-api.js` | Add SSE event type subscriptions for `channel_message` and `channel_update`. Add callback registration methods. |
| `static/voice/voice-state.js` | Add `channels` array and `currentChannelSlug` for channel context tracking. |

### 6.2 New Files

None. All changes are modifications to existing files.

### 6.3 Channel Intent Detection Pipeline

The channel intent detection is a new stage inserted into the existing `voice_command()` function, between handoff detection and agent resolution. It uses regex pattern matching — no LLM call needed for channel routing.

```python
# In voice_command(), after handoff intent detection:

def _detect_channel_intent(text: str) -> dict | None:
    """Detect if a voice utterance targets a channel operation.

    Returns a dict with:
      - action: "send" | "history" | "create" | "add_member" | "complete"
      - channel_ref: extracted channel name/reference (may be "this channel")
      - content: message content (for send action)
      - channel_type: inferred type (for create action)
      - member_ref: persona name reference (for add_member action)
      - member_refs: list of persona name references (for create with members)
    Returns None if the utterance is not channel-targeted.
    """
```

Pattern matching hierarchy (checked in order):

```python
import re

# 1. Send to channel
_SEND_PATTERNS = [
    re.compile(r"(?:send|message|tell)\s+(?:to\s+)?(?:the\s+)?(.+?)(?:\s+channel)?:\s*(.+)", re.I),
    re.compile(r"(?:send|message|tell)\s+(?:to\s+)?(?:the\s+)?(.+?)\s+channel\s*:\s*(.+)", re.I),
]

# 2. Channel history
_HISTORY_PATTERNS = [
    re.compile(r"what(?:'s|s)\s+(?:happening|going on)\s+in\s+(?:the\s+)?(.+?)(?:\s+channel)?\s*\??", re.I),
    re.compile(r"show\s+(?:the\s+)?(.+?)(?:\s+channel)?\s+messages", re.I),
    re.compile(r"(?:channel\s+)?history\s+(?:for\s+)?(?:the\s+)?(.+?)(?:\s+channel)?", re.I),
]

# 3. Create channel (with optional members)
_CREATE_PATTERNS = [
    re.compile(
        r"create\s+(?:a\s+)?(\w+)\s+channel\s+(?:called\s+|named\s+)?(.+?)"
        r"(?:\s+with\s+(.+))?$",
        re.I,
    ),
    re.compile(
        r"create\s+(?:a\s+)?channel\s+(?:called\s+|named\s+)?(.+?)"
        r"(?:\s+(?:as|type)\s+(\w+))?"
        r"(?:\s+with\s+(.+))?$",
        re.I,
    ),
]

# 4. Add member
_ADD_MEMBER_PATTERNS = [
    re.compile(r"add\s+(\w+)\s+to\s+(?:the\s+)?(.+?)(?:\s+channel)?$", re.I),
    re.compile(r"add\s+(\w+)\s+to\s+this\s+channel$", re.I),
]

# 5. Complete channel
_COMPLETE_PATTERNS = [
    re.compile(r"(?:complete|finish|close|end)\s+(?:the\s+)?(.+?)(?:\s+channel)?$", re.I),
]
```

**Key design decision:** Channel intent detection uses regex only — no LLM fallback. Channel commands have distinctive structural patterns ("send to X:", "what's happening in X", "create a X channel") that regex handles reliably. This keeps the detection path fast (sub-millisecond) and deterministic.

### 6.4 Channel Name Matching Algorithm

The fuzzy matcher operates against all channels where the operator is a member (or all visible channels for the operator persona).

```python
def _match_channel(channel_ref: str, channels: list) -> dict:
    """Fuzzy match a channel reference against active channels.

    Args:
        channel_ref: The extracted channel name from voice input
        channels: List of Channel objects (status pending or active)

    Returns:
        {"match": Channel, "confidence": float} for single match
        {"ambiguous": [Channel, ...]} for multiple matches
        {"no_match": True} for no matches
    """
    ref = channel_ref.strip().lower()
    # Strip common articles and noise words
    ref = re.sub(r"^(the|a|an)\s+", "", ref)
    ref = ref.rstrip("?!.")

    candidates = []
    for ch in channels:
        name_lower = ch.name.lower()
        slug_lower = ch.slug.lower()

        # 1. Exact slug match
        if ref == slug_lower:
            return {"match": ch, "confidence": 1.0}

        # 2. Exact name match
        if ref == name_lower:
            return {"match": ch, "confidence": 1.0}

        # 3. Slug contains ref or ref contains slug
        if ref in slug_lower or slug_lower in ref:
            candidates.append((ch, 0.8))
            continue

        # 4. Name contains ref or ref contains name
        if ref in name_lower or name_lower in ref:
            candidates.append((ch, 0.8))
            continue

        # 5. Token overlap: query tokens appear in channel name tokens
        ref_tokens = set(ref.split())
        name_tokens = set(name_lower.replace("-", " ").split())
        slug_tokens = set(slug_lower.replace("-", " ").split())
        all_tokens = name_tokens | slug_tokens

        overlap = ref_tokens & all_tokens
        if overlap and len(overlap) >= len(ref_tokens) * 0.5:
            score = len(overlap) / max(len(ref_tokens), len(all_tokens))
            candidates.append((ch, score))

    if not candidates:
        return {"no_match": True}

    # Sort by score descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    # If top candidate is significantly better, return it
    if len(candidates) == 1:
        return {"match": candidates[0][0], "confidence": candidates[0][1]}

    if candidates[0][1] - candidates[1][1] > 0.2:
        return {"match": candidates[0][0], "confidence": candidates[0][1]}

    # Ambiguous — return top matches
    ambiguous = [c[0] for c in candidates if c[1] >= candidates[0][1] - 0.1]
    return {"ambiguous": ambiguous}
```

The same algorithm (exact -> substring -> token overlap) is used for persona name matching in `_match_persona_for_channel()`.

### 6.5 Channel Context Tracking

Voice sessions need a "current channel" so the operator can say "this channel" in follow-up commands. This is per-request state, stored in a module-level dict keyed by auth token (or `"localhost"` for localhost bypass).

```python
# Module-level channel context cache
# Key: auth identifier (token or "localhost"), Value: channel slug
_channel_context: dict[str, str] = {}

def _set_channel_context(auth_id: str, channel_slug: str) -> None:
    """Set the current channel context for this voice session."""
    _channel_context[auth_id] = channel_slug

def _get_channel_context(auth_id: str) -> str | None:
    """Get the current channel context for this voice session."""
    return _channel_context.get(auth_id)

def _resolve_channel_ref(channel_ref: str, auth_id: str) -> str:
    """Resolve 'this channel' / 'the channel' to actual channel slug."""
    if channel_ref.strip().lower() in ("this channel", "the channel", "this", "current channel"):
        ctx = _get_channel_context(auth_id)
        if ctx:
            return ctx
        raise ValueError("No current channel context. Specify the channel name.")
    return channel_ref
```

Context is updated whenever a channel operation succeeds. The context cache has no TTL — it resets naturally when the server restarts. This is acceptable because voice sessions are ephemeral.

### 6.6 Channel Type Inference

The channel type is inferred from the voice utterance using keyword matching:

```python
_CHANNEL_TYPE_KEYWORDS = {
    "workshop": "workshop",
    "delegation": "delegation",
    "delegate": "delegation",
    "review": "review",
    "standup": "standup",
    "stand up": "standup",
    "broadcast": "broadcast",
    "announce": "broadcast",
    "announcement": "broadcast",
}

def _infer_channel_type(text: str) -> str:
    """Infer channel type from voice text. Default: workshop."""
    text_lower = text.lower()
    for keyword, channel_type in _CHANNEL_TYPE_KEYWORDS.items():
        if keyword in text_lower:
            return channel_type
    return "workshop"
```

### 6.7 Integration with voice_command()

The channel detection stage is inserted into the existing `voice_command()` function. The modification point is after handoff intent detection (line ~376) and before agent resolution (line ~330):

```python
@voice_bridge_bp.route("/api/voice/command", methods=["POST"])
def voice_command():
    # ... existing code: parse text, agent_id, file_path ...

    # ── Handoff intent detection (existing) ──
    from ..services.intent_detector import detect_handoff_intent
    is_handoff, handoff_context = detect_handoff_intent(text)
    if is_handoff:
        # ... existing handoff routing ...

    # ── Channel intent detection (NEW) ──
    channel_intent = _detect_channel_intent(text)
    if channel_intent:
        return _handle_channel_intent(channel_intent, text, formatter)

    # ── Agent resolution (existing) ──
    if agent_id:
        agent = db.session.get(Agent, agent_id)
        # ... rest of existing agent path ...
```

The `_handle_channel_intent()` function dispatches to the appropriate `ChannelService` method:

```python
def _handle_channel_intent(intent: dict, text: str, formatter) -> tuple:
    """Route a channel-targeted voice command to ChannelService."""
    channel_service = current_app.extensions.get("channel_service")
    if not channel_service:
        return _voice_error("Channels not available.", "Channel service not configured.", 503)

    action = intent["action"]
    auth_id = _get_auth_id()

    if action == "send":
        return _handle_channel_send(intent, channel_service, formatter, auth_id)
    elif action == "history":
        return _handle_channel_history(intent, channel_service, formatter, auth_id)
    elif action == "create":
        return _handle_channel_create(intent, channel_service, formatter, auth_id)
    elif action == "add_member":
        return _handle_channel_add_member(intent, channel_service, formatter, auth_id)
    elif action == "complete":
        return _handle_channel_complete(intent, channel_service, formatter, auth_id)
    else:
        return _voice_error("Unknown channel action.", "Try 'send to [channel]: [message]'.", 400)
```

### 6.8 VoiceFormatter Channel Methods

New methods added to `VoiceFormatter` following the existing pattern:

```python
def format_channel_message_sent(self, channel_slug: str) -> dict:
    """Format channel message send confirmation."""
    return {
        "status_line": f"Message sent to #{channel_slug}.",
        "results": [],
        "next_action": "none",
    }

def format_channel_history(self, channel_slug: str, messages: list[dict],
                           verbosity: str | None = None) -> dict:
    """Format channel message history for voice consumption."""
    v = verbosity or self.default_verbosity
    if not messages:
        return {
            "status_line": f"No messages in #{channel_slug}.",
            "results": [],
            "next_action": "none",
        }
    results = []
    for msg in messages:
        persona = msg.get("persona_name", "Unknown")
        content = msg.get("content", "")
        if v == "concise":
            # Truncate to first 80 chars
            preview = content[:80] + ("..." if len(content) > 80 else "")
            results.append(f"{persona}: {preview}")
        else:
            results.append(f"{persona}: {content}")
    return {
        "status_line": f"Last {len(messages)} messages in #{channel_slug}.",
        "results": results,
        "next_action": "none",
    }

def format_channel_created(self, channel_slug: str, channel_type: str,
                           member_results: list[str]) -> dict:
    """Format channel creation confirmation."""
    return {
        "status_line": f"Created channel #{channel_slug} ({channel_type}).",
        "results": member_results,
        "next_action": "none",
    }

def format_channel_completed(self, channel_slug: str) -> dict:
    """Format channel completion confirmation."""
    return {
        "status_line": f"Channel #{channel_slug} completed.",
        "results": [],
        "next_action": "none",
    }

def format_channel_member_added(self, persona_name: str,
                                channel_slug: str, spinning_up: bool = False) -> dict:
    """Format member addition confirmation."""
    suffix = " (agent spinning up)" if spinning_up else ""
    return {
        "status_line": f"{persona_name} added to #{channel_slug}{suffix}.",
        "results": [],
        "next_action": "none",
    }
```

### 6.9 Voice Chat PWA Channel Display

The Voice Chat PWA sidebar (`voice-sidebar.js`) gains a channels section below the agent list. This section renders when `channel_message` or `channel_update` SSE events arrive.

**Data flow:**
1. `VoiceAPI.connectSSE()` subscribes to `channel_message` and `channel_update` event types
2. `VoiceSSEHandler.handleChannelMessage()` receives the event and updates `VoiceState.channels`
3. `VoiceSidebar.renderChannelList()` renders channel entries below agent cards

**Channel sidebar entry format:**
```html
<div class="channel-card" data-channel-slug="persona-alignment-workshop">
  <div class="channel-header">
    <span class="channel-name">#persona-alignment-workshop</span>
    <span class="channel-status active">active</span>
  </div>
  <div class="channel-preview">
    <span class="channel-sender">Robbo:</span>
    <span class="channel-content-preview">The persona type hierarchy resolves...</span>
  </div>
  <div class="channel-ago">2m ago</div>
</div>
```

Tapping a channel card navigates to a channel detail view. This view reuses the existing chat message rendering (`VoiceChatRenderer.createBubbleEl()`) adapted for channel messages — each message rendered as a bubble with persona attribution in the envelope format.

**Visual consistency:** Channel message rendering in the Voice Chat PWA should follow the same conventions as S7's dashboard chat panel: operator messages in cyan, agent messages in green, system messages muted and centered. Reference S7 Section 6.7 for the rendering pattern.

### 6.10 Member Extraction from Voice Create Commands

When the operator says "create a workshop channel called persona alignment with Robbo and Paula," the member list is extracted from the "with [members]" suffix:

```python
def _extract_member_refs(members_text: str) -> list[str]:
    """Extract persona name references from 'with X and Y' / 'with X, Y, Z'."""
    if not members_text:
        return []
    # Normalize: split on "and", ",", "&"
    parts = re.split(r"\s+and\s+|,\s*|&\s*", members_text.strip())
    return [p.strip() for p in parts if p.strip()]
```

Each extracted name is then fuzzy-matched against active personas using `_match_persona_for_channel()`. Failed matches return an error listing unresolved names.

### 6.11 Design Decisions (All Resolved — Workshop Sections 2.3 and 4.1)

| Decision | Resolution | Source |
|----------|-----------|--------|
| Voice command routing | Extend existing `/api/voice/command` endpoint, no new endpoints | 2.3 |
| Channel name matching | Fuzzy match on name + slug, same algorithm as agent picker | 2.3 |
| Ambiguity handling | Return clarification prompt listing matches | 2.3 |
| Voice response format | Existing `{status_line, results, next_action}` envelope via `VoiceFormatter` | 2.3 |
| Primary operator interface | Voice bridge is the primary channel interface; dashboard and CLI are secondary | 4.1 |
| Channel creation via voice | Single utterance creates channel with type, name, and members | 4.1 |
| Channel type inference | Keyword matching with `workshop` default | 4.1 |
| Auth for channel operations | Existing Bearer token auth, no changes | 2.3 |
| Rate limiting | Existing voice bridge rate limiter, no channel-specific limits | 2.3 |
| Detection pipeline order | Handoff -> Channel -> Agent (channel detection before agent resolution) | New (derived from 2.3 architecture) |
| Context tracking | In-memory per-session "current channel" for "this channel" references | New (derived from 4.1 conversational flow) |

### 6.12 Existing Services Used (DO NOT recreate)

- **`src/claude_headspace/routes/voice_bridge.py`** — Contains `voice_command()`, `_voice_error()`, `_get_voice_formatter()`, `_get_voice_auth()`. Modify in place to add channel detection stage.
- **`src/claude_headspace/services/voice_formatter.py`** — Contains `format_sessions()`, `format_command_result()`, `format_question()`, `format_output()`, `format_error()`. Add new `format_channel_*` methods.
- **`src/claude_headspace/services/voice_auth.py`** — Token auth and rate limiting. No changes needed.
- **`ChannelService`** (from S4) — Called via `app.extensions["channel_service"]`. Provides `create_channel()`, `send_message()`, `add_member()`, `complete_channel()`, `get_messages()`. This sprint calls it; it does not implement it.
- **`src/claude_headspace/services/broadcaster.py`** — Broadcasts `channel_message` and `channel_update` SSE events (defined in S5). Voice Chat PWA subscribes to these existing events.

### 6.13 Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Channel intent false positives on agent commands | Low | Medium | Detection pipeline checks channel patterns first with structural markers ("send to X:"), falling through to agent path only if no channel match. Patterns require distinctive syntax (colon separator, question mark, "create ... channel") unlikely to appear in agent commands. |
| Speech-to-text garbles channel names | Medium | Low | Fuzzy matching with token overlap handles most variations. Worst case: operator retries with explicit name or falls back to dashboard. |
| "this channel" context lost between requests | Low | Low | In-memory context per auth token persists across requests within same server lifetime. Server restart clears context — acceptable for ephemeral voice sessions. |
| ChannelService not available (S4 not deployed) | Certain (during dev) | None | Graceful 503 error: "Channels not available." No crash, no side effects. |
| Ambiguous channel matches frustrate operator | Medium | Low | Clarification prompt lists exact channel names — operator repeats with specific name. Max 2-3 active channels in typical use makes ambiguity rare. |

---

## 7. Dependencies

| Dependency | Sprint | What It Provides |
|------------|--------|------------------|
| ChannelService | E9-S4 | Service layer this sprint calls — create, send, add_member, complete, get_messages |
| Channel data model | E9-S3 | Channel, ChannelMembership, Message models queried for fuzzy matching |
| Channel SSE events | E9-S5 | `channel_message` and `channel_update` SSE event types consumed by Voice Chat PWA |
| Voice bridge infrastructure | Existing | `/api/voice/command` endpoint, VoiceFormatter, VoiceAuth, Bearer token auth |
| Voice Chat PWA | Existing | `/voice` page, VoiceSidebar, VoiceSSEHandler, VoiceAPI, VoiceState modules |
| Persona system | E8-S5 (done) | Persona name/slug lookup for `_match_persona_for_channel()` |

**Critical dependency:** S4 (ChannelService) must be deployed before this sprint is functional. However, the code can be built and tested in isolation with mocked `ChannelService` calls.

---

## Document History

| Version | Date       | Author | Changes |
|---------|------------|--------|---------|
| 1.0     | 2026-03-03 | Robbo  | Initial PRD from Epic 9 Workshop (Sections 2.3, 4.1) |
