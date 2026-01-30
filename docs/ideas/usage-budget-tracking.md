# Idea: Claude Subscription Usage Budget Tracking

**Status:** Research Complete - Awaiting Implementation Path
**Date:** 2026-01-23
**Workshop Session:** PRD Workshop (incomplete - pivoted to idea capture)

---

## Intent

Track Claude AI subscription usage (session and weekly limits) to enable better budget management and avoid running out at critical moments during work sessions.

### Core Problem

Running out of Claude turns/budget mid-task causes:
- Loss of mental context (expensive cognitive cost)
- Disruption to flow state and headspace
- Uncertainty about whether to pace usage or go full-tilt

### Desired Outcome

- Know how much "budget" remains in current session window
- Forecast whether current pace will exhaust budget before reset
- Receive guidance on optimal session management
- Visualize usage patterns over time

---

## Key Research Findings

### 1. Usage is Token-Based, Not Turn-Based

**Initial assumption:** Usage limits are based on turn counts (request/response pairs).

**Reality:** Limits are calculated based on **tokens consumed**, which includes:
- Input tokens (your messages + full conversation context)
- Output tokens (Claude's responses)
- Context accumulation - each turn in a long session costs more than the same turn early in a session

**Implication:** Turn counting from JSONL logs is only a rough proxy for actual consumption.

### 2. Context Accumulation Effect

Each API call includes the full conversation history. This means:
- Early session turns: Small context → low token cost
- Late session turns: Large context → high token cost (for equivalent work)

**Insight:** Shorter, more frequent sessions may be more token-efficient than long grinding sessions. Starting fresh resets context cost to baseline while persistent context (CLAUDE.md, project files) is preserved on disk.

### 3. Subscription Allocations (Approximate)

Per 5-hour session window:
- Pro: ~44,000 tokens
- Max 5x: ~88,000 tokens
- Max 20x: ~220,000 tokens

Weekly limits also apply (added August 2025).

### 4. Model Selection Impact

Opus 4.5 consumes allocation ~1.7x faster than Sonnet. Heavy Opus use exhausts limits faster.

### 5. No Public API for Usage Data

- **API users** get rate-limit headers (`anthropic-ratelimit-tokens-remaining`, etc.)
- **Subscription users** (Pro/Max) have no equivalent programmatic access
- Usage visible only via:
  - `/status` command within Claude Code
  - Web dashboard at Settings > Usage on claude.ai

---

## Existing Infrastructure (What We Have)

The monitor already captures:

1. **JSONL Session Logs** - Full conversation history at `~/.claude/projects/<project>/<session>.jsonl`
2. **Log Parsing** - `lib/summarization.py` extracts files, commands, errors, timestamps
3. **Session Sync** - Background thread monitors active sessions
4. **Turn Data Available** - JSONL contains `type: "user"` and `type: "assistant"` entries (countable)

**Gap:** We can count turns and estimate tokens from message content, but cannot get authoritative usage data from Anthropic.

---

## Future Implementation Options

### Option A: Turn/Token Estimation (Available Now)

- Count turns from JSONL logs
- Estimate tokens from message character counts
- Track session "depth" (how far into context accumulation)
- Provide rough pacing guidance

**Pros:** Implementable immediately
**Cons:** Approximate, may not match actual consumption

### Option B: Parse `/status` Command Output (Hacky)

- Periodically run `/status` in Claude Code terminal
- Parse the output for actual usage numbers
- Requires terminal integration

**Pros:** Real data from Anthropic
**Cons:** Brittle, depends on output format stability

### Option C: Tmux Integration (Future)

When tmux integration is implemented, the monitor could:
- Send `/status` command directly to Claude Code sessions
- Capture and parse the response
- Track authoritative usage data over time

**Pros:** Real data, automated collection
**Cons:** Requires tmux integration milestone first

### Option D: Wait for Anthropic API

Monitor Anthropic's API development for subscription usage endpoints.

**Pros:** Official, reliable
**Cons:** May never happen, timeline unknown

---

## Recommended Path Forward

1. **Short-term:** Implement session depth/age tracking as efficiency indicator
   - Track turns per session
   - Recommend fresh sessions when context is bloated
   - Leverage existing briefing system for efficient restarts

2. **Medium-term:** After tmux integration, implement Option C
   - Periodic `/status` polling
   - Historical usage tracking
   - Forecasting based on actual data

3. **Long-term:** Integrate Anthropic API if/when available

---

## Related Features

- **Brain Reboot Briefing** - Already exists, helps efficient session starts
- **Session Summarization** - Already captures session activity
- **Headspace Management** - Core app purpose, usage tracking aligns with this

---

## Sources

- [About Claude's Pro Plan Usage | Claude Help Center](https://support.claude.com/en/articles/8324991-about-claude-s-pro-plan-usage)
- [Using Claude Code with your Pro or Max plan | Claude Help Center](https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan)
- [Claude Code Rate Limits | Portkey](https://portkey.ai/blog/claude-code-limits/)
- [Rate limits - Claude Docs](https://platform.claude.com/docs/en/api/rate-limits)
