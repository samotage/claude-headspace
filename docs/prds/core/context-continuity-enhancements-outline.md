# Context Continuity Enhancements — PRD Workshop Outline

**Author:** Hawk (Technical Analyst)
**Date:** 2026-03-04
**Purpose:** Input material for Robbo + Hawk PRD workshop
**Status:** Outline — not yet a PRD

---

## Background

Comparative evaluation of four ecosystem approaches to session continuity (claude-mem, Continuous-Claude-v3, beads, SuperClaude) against our existing handoff and persona system. Full evaluation transcript available from Hawk's session 2026-03-03/04.

Our handoff system is architecturally ahead of the ecosystem on persona modelling, state management, and observability. Three operational gaps were identified where specific mechanisms from external projects would strengthen our existing design.

---

## Enhancement 1: Pre-Compact Auto-Snapshot

### The Problem

When Claude Code compacts context mid-session, structured state is lost silently. The agent continues working but with degraded context. If a handoff happens later, the handoff document is written from the post-compaction context — missing earlier decisions, rationale, and progress.

There is currently no PreCompact hook handler in the codebase.

### What We'd Build

A PreCompact hook handler that automatically generates a lightweight state snapshot before compaction occurs. Not a full handoff — the agent keeps working — but a safety net that preserves structured state.

### Inspiration

Continuous-Claude-v3's `pre-compact-continuity.mjs` parses the JSONL transcript and auto-generates a YAML handoff before compaction. Their format is ~400 tokens with fixed fields (goal, now, done_this_session, blockers, decisions, files modified).

### What We Already Have

- `TranscriptReconciler` and `JSONLParser` for parsing agent transcripts
- `HookReceiver` already processes 8 hook event types (PreCompact is not one of them but Claude Code emits it)
- `Command` model with state, instruction, completion_summary
- `Turn` model with actor, intent, text, summary
- `SummarisationService` for LLM-powered compression
- `BrainRebootService` which generates waypoint + progress exports (heavier-weight version of what this would do)

### Key Design Questions for Workshop

1. **Snapshot scope:** What goes into the snapshot? Options:
   - Minimal: current command state + last N turn summaries + files modified (cheap, no inference)
   - Medium: the above + LLM-generated progress summary (one inference call)
   - Full: brain-reboot-lite (existing BrainRebootService, trimmed down)

2. **Storage:** Where does the snapshot live?
   - New model (e.g., `CompactionSnapshot`) in PostgreSQL
   - Append to the persona's experience file
   - Write to disk alongside handoff documents (different subdirectory)
   - Ephemeral — inject back into the agent's session via tmux as `additionalContext` (CC-v3's approach)

3. **Injection on compaction:** Should the snapshot be re-injected into the agent's session after compaction?
   - CC-v3 does this via `additionalContext` in the hook response
   - We'd do it via tmux send-keys (our existing injection path)
   - Risk: if the snapshot is large, we're burning fresh context budget on history

4. **Relationship to handoff:** If a handoff happens later in the same session, should the handoff document reference or include the compaction snapshot? This would give the successor access to pre-compaction context the outgoing agent has forgotten.

5. **Multiple compactions:** A long session might compact several times. Accumulate snapshots? Overwrite? Chain them?

### Existing Infrastructure to Leverage

| Component | How It Helps |
|-----------|-------------|
| `HookReceiver` | Add PreCompact handler alongside existing 8 handlers |
| `JSONLParser` / `TranscriptReconciler` | Parse transcript for recent activity |
| `SummarisationService` | Optional LLM compression of snapshot content |
| `CardState` / `Broadcaster` | Broadcast snapshot event to dashboard (visual indicator that compaction occurred) |
| `Command` + `Turn` models | Query recent state without parsing files |

### Effort Estimate

- Hook handler + minimal snapshot (no inference): **small** — wiring and a DB query
- Medium snapshot with inference: **medium** — add inference call, decide storage
- Re-injection into session: **medium** — tmux injection path exists, but needs format design

---

## Enhancement 2: Progressive Handoff Injection

### The Problem

When a successor agent starts, the full handoff document is injected into its session via tmux. As persona chains get longer and handoff documents get richer (decisions, rationale, operator notes, file lists, prior handoff references), this consumes an increasing share of the successor's context budget before it does any work.

The current injection is all-or-nothing: the entire handoff document plus the full skill.md plus experience.md goes in at session start.

### What We'd Build

A two-tier injection model:
- **Tier 1 (always injected):** Compact summary — who you are, what you're continuing, current task, key blockers, immediate next step. Target: 300-500 tokens.
- **Tier 2 (available on demand):** Full handoff document, prior handoff chain, detailed decisions. The successor is told the file path and reads it if needed.

### Inspiration

claude-mem's progressive disclosure: inject a compact index (~50-100 tokens per observation) into every session, with MCP tools available to fetch full details on demand. Claude reads titles to know what it knows, then retrieves specifics only when relevant.

### What We Already Have

- `HandoffExecutor.compose_injection_prompt()` — already composes the injection text
- `HandoffExecutor.deliver_injection_prompt()` — sends via tmux after skill injection
- Handoff documents on disk at `data/personas/{slug}/handoffs/`
- `SkillInjector` handles skill + experience injection (separate from handoff injection)

### Key Design Questions for Workshop

1. **What goes in Tier 1?** The compact summary needs to be useful enough that the successor can start working without reading the full document. Candidates:
   - Current task / next step (from handoff's "Next Steps" section)
   - Key blockers
   - Most recently modified files
   - One-sentence progress summary
   - Pointer to the full handoff file path

2. **Who generates the Tier 1 summary?** Options:
   - The outgoing agent writes it as a required section in the handoff document (structured format)
   - The system generates it from the handoff document via inference (adds latency at successor startup)
   - The system extracts it mechanically from the handoff document's sections (fragile if format varies)

3. **Should Tier 1 format be standardised?** If we define required fields (like CC-v3's `goal:` / `now:` / `test:` YAML), we can extract them reliably. Trade-off: constrains the agent's writing freedom vs enables mechanical extraction.

4. **Chain depth:** When a persona has 3+ predecessors, should the Tier 1 summary include anything from earlier handoffs, or just the immediate predecessor? Recursive summarisation risks growing the injection over time.

5. **Experience file interaction:** The experience.md is also injected at startup. Should accumulated handoff insights migrate into experience.md over time (long-term persona memory) rather than being re-injected from the handoff chain each time?

### Existing Infrastructure to Leverage

| Component | How It Helps |
|-----------|-------------|
| `HandoffExecutor.compose_injection_prompt()` | Modify to generate Tier 1 compact version |
| `HandoffExecutor.deliver_injection_prompt()` | Already the injection path — just change what's injected |
| Handoff documents on disk | Tier 2 is "read this file" — already how agents access documents |
| `SummarisationService` | Could generate Tier 1 from full handoff if we go the inference route |

### Effort Estimate

- Structured Tier 1 with outgoing agent writing it: **small-medium** — modify handoff instruction template + injection prompt
- System-generated Tier 1 via inference: **medium** — add inference call at successor startup, handle latency
- Chain summarisation for deep persona lineages: **medium-large** — recursive summarisation design

---

## Enhancement 3 (Conditional): Context-Aware Handoff Gate

### Status Note

The dashboard already shows a "Handoff" button when context usage hits the `handoff_threshold` (80%, configurable). The `ContextPoller` tracks usage. The UI wiring is complete. What's missing is proactive/automatic behaviour at the hook level.

**This may already be in scope for existing designs.** Before workshopping, verify whether this was specced in a prior PRD or architecture decision and simply not yet implemented. If it was, this section becomes a build task, not a new PRD.

### The Problem

Context exhaustion is currently a passive event. The dashboard shows a button; the operator has to notice it and click it. If nobody is watching the dashboard (overnight runs, deep focus sessions), the agent hits context limits, compacts repeatedly, and degrades without intervention.

### What We'd Build

A policy layer in the hook receiver that responds to context threshold crossings:

- **At warning threshold (e.g., 75%):** Broadcast an SSE alert to the dashboard. Optional: inject a gentle reminder into the agent's session via tmux ("Context at 75%. Consider wrapping up or requesting a handoff.")
- **At handoff threshold (e.g., 85%):** Auto-trigger handoff via `HandoffExecutor.trigger_handoff()` with `reason="context_limit"`. The agent writes its handoff document, successor is created, and work continues with fresh context.
- **At critical threshold (e.g., 95%):** If no handoff has been triggered, force one. This is the safety net.

### Inspiration

CC-v3's stop hook returns `{"decision": "block"}` at 85% context, preventing the agent from continuing until it creates a handoff. Their approach is blunt (block entirely) — ours could be smoother (auto-trigger the handoff flow the agent already knows how to do).

### What We Already Have

- `ContextPoller` — background thread polling context usage, persists to `Agent.context_percent_used`
- `handoff_threshold` config (80%) — used by `card_state.py` for `handoff_eligible` flag
- `HandoffExecutor.trigger_handoff()` — the full handoff flow, ready to call
- Dashboard "Handoff" button — already wired for `reason="context_limit"`
- `TmuxBridge` — can inject advisory messages into agent sessions

### Key Design Questions for Workshop

1. **Auto-trigger vs advisory:** Should crossing 85% automatically trigger a handoff, or just send an advisory to the agent and notify the dashboard? Auto-trigger is more reliable but removes operator choice. Advisory is gentler but depends on someone acting.

2. **Threshold configuration:** Should this be per-persona, per-project, or global? Some personas (researchers) may burn context faster and need lower thresholds. Some projects may want manual-only handoffs.

3. **Interaction with existing handoff button:** If the dashboard button triggers a manual handoff at 80%, and the auto-gate triggers at 85%, what happens if both fire? The idempotency guards in `HandoffExecutor` should handle this, but worth verifying.

4. **Overnight/unattended operation:** The strongest case for auto-trigger is unattended runs. If personas run overnight, nobody is watching the dashboard. Auto-handoff at a threshold keeps work flowing. This may change the design preference.

5. **Cooldown after compaction:** If context drops after compaction (e.g., from 90% to 60%), should the thresholds reset? Or should we track "this agent has already compacted N times" as an escalating signal?

### Effort Estimate

- Advisory-only (tmux message + SSE alert at threshold): **small**
- Auto-trigger handoff at threshold: **small-medium** — call existing `trigger_handoff()` from ContextPoller
- Configurable per-persona/project thresholds: **medium** — config schema changes, UI for setting them

---

## Dependencies and Ordering

```
Enhancement 1 (Pre-Compact Snapshot) — independent, can be built first
Enhancement 2 (Progressive Injection) — independent, can be built in parallel
Enhancement 3 (Context Gate)          — depends on existing handoff working well;
                                        verify prior design coverage first
```

Enhancements 1 and 2 reinforce each other: if compaction snapshots exist (E1), the progressive injection (E2) can reference them as part of the Tier 1 compact summary for successors.

Enhancement 3 is the most operationally impactful for unattended runs but may already be partially designed. Recommend checking existing PRDs/architecture docs before workshopping.

---

## Ecosystem Sources

| Source | Stars | What we're borrowing | What we're not borrowing |
|--------|-------|---------------------|------------------------|
| **parcadei/Continuous-Claude-v3** | 3.6k | Pre-compact transcript parsing, stop hook gating concept | YAML format (we keep rich markdown), 32 agent prompt files, PostgreSQL+pgvector memory system, subprocess overhead |
| **thedotmack/claude-mem** | 32k | Progressive disclosure injection model | Observer subprocess (2x API cost), SQLite storage, project-only scoping, no persona awareness |
| **steveyegge/beads** | 18k | Nothing directly — but the "structured over unstructured" principle informs Tier 1 design | Dolt dependency, manual-only capture, all-or-nothing memory injection |
| **SuperClaude-Org/SuperClaude_Framework** | 21k | Nothing | Prompt templates marketed as "cognitive personas" |

---

## Next Steps

1. Robbo reviews this outline for architectural fit
2. Workshop PRD covering Enhancements 1 and 2 (confirmed new work)
3. Verify Enhancement 3 against existing design docs — workshop only if not already specced
4. Hawk available for technical review of the PRD and implementation verification
