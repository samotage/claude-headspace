# Bug: IntentDetector Missed Handoff Trigger

**Date:** 2 March 2026
**Reported by:** Sam (via Robbo session, Agent #1108)
**For:** Con — intent detection pipeline review

---

## What Happened

Sam issued a handoff request at the end of a workshop session. The IntentDetector did not trigger the handoff flow. Robbo did not receive the standard handoff prompt/template injection. The handoff document was written manually by following the predecessor's format.

## Operator's Exact Message

> Prepare handoff for the next Section in a new agent.

## Expected Behaviour

The IntentDetector should have classified this as a handoff trigger, which would have:
1. Triggered the HandoffExecutor flow
2. Injected the standard handoff prompt to guide the agent through structured handoff preparation
3. Ensured all required handoff elements were captured

## Actual Behaviour

No handoff flow triggered. No prompt injection. The agent (Robbo) received the message as a plain instruction and manually wrote a handoff document based on the predecessor's format.

## Analysis — Why It Likely Missed

The message contains several handoff-relevant signals:

| Signal | Present | Notes |
|--------|---------|-------|
| Word "handoff" | Yes | "Prepare **handoff**" — should be a strong keyword match |
| Intent to end session | Implied | "for the next... in a new agent" implies current agent is finishing |
| Delegation to successor | Yes | "new agent" explicitly references a successor |
| Section context | Yes | "next Section" references workshop continuity |

**Possible causes:**
- The IntentDetector's handoff patterns may not include "prepare handoff" as a trigger phrase
- The handoff detection may require specific phrasing (e.g., "hand off to", "do a handoff", "start handoff")
- The HandoffExecutor trigger may be gated on a different detection path than the IntentDetector (e.g., a separate keyword scanner or a specific hook event)
- The detection may expect "handoff" as a standalone intent, not embedded in a longer instruction

## Recommended Review

1. Check what patterns/phrases currently trigger the handoff flow
2. Verify "prepare handoff" and variations are covered
3. Consider whether the trigger should be keyword-based (any message containing "handoff") or intent-based (classified as a handoff request by the full pipeline)
4. Test with the exact message above to reproduce
