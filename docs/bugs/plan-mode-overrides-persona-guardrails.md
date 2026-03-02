# Bug: Plan Mode Self-Approval via Permissive settings.json

**Date:** 2 March 2026
**Status:** Resolved — root cause was local permissions config
**GitHub Issue:** [#29950](https://github.com/anthropics/claude-code/issues/29950) (closed — not a platform bug)

---

## Summary

An agent with skills injected at session start (via `.claude/agents/`) self-approved its own implementation plan and committed a 383-line change without operator review. Originally reported as a Claude Code platform bug, but the root cause was our `settings.json` permissions configuration.

## What Happened

1. Agent entered plan mode (per skill file instruction)
2. Agent wrote a plan
3. Agent called `ExitPlanMode`
4. `ExitPlanMode` auto-approved — the operator was never prompted to review
5. Agent implemented and committed a 383-line, 5-file change without real approval
6. The skill file guardrail ("never skip the approval checkpoint") was bypassed

## Root Cause

The project's `.claude/settings.json` had `defaultMode: "acceptEdits"` with a broad `allow` list. This permission configuration caused `ExitPlanMode` to auto-approve without prompting the operator. The plan mode tool was working as designed — it was our permissions that told it not to ask.

**The fix:** Tighten permissions so `ExitPlanMode` requires explicit operator approval, or remove `acceptEdits` as the default mode for agent sessions that need approval checkpoints.

## Lesson

Broad permissions (`defaultMode: "acceptEdits"` + blanket tool allows) are convenient for solo interactive sessions but dangerous for agent sessions with skill files that define approval checkpoints. The permissions and the skill file guardrails need to agree — if the skill file says "get approval before implementing," the permissions must actually require approval for plan-mode exit.
