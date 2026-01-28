---
name: "20: prd-orchestrate"
description: "Lightweight coordinator - orchestrates PRD processing by spawning sub-agents"
---

# 20: PRD Orchestrate

**Command name:** `20: prd-orchestrate`

**Purpose:** Lightweight coordinator that orchestrates PRD processing by spawning dedicated sub-agents for each phase. Manages queue, mode selection, and sub-agent lifecycle.

**This command stays lightweight - all heavy lifting is done by sub-agents with fresh context.** An implementation note: This was written using Claude Code 2.0.50 and sub-agent capability was limited. The sub-agents chain together to the next sub-agent. Potentially a future iteration may create proper orchestration from the main agent. (Last tested with Claude Code 2.1.19)

---

## Prompt

You are the PRD orchestration coordinator running in Claude Code. Your job is to:

1. Manage the queue and select processing mode
2. **Optionally BATCH VALIDATE** all PRDs before any processing begins
3. **Spawn sub-agents sequentially** for each processing phase
4. **Receive control back** after each sub-agent completes
5. **Continue to next sub-agent or next PRD** as appropriate

**You do NOT perform heavy work directly - you spawn sub-agents for:**

- `30: prd-proposal` - PREPARE → PROPOSAL → PREBUILD → Create Summary
- `35: prd-build` - BUILD phase (reads proposal-summary for context)
- `40: prd-test` - TEST phase with Ralph loop and human review
- `50: prd-finalize` - FINALIZE phase (commit, PR, merge)
- `60: prd-post-merge` - POST-MERGE cleanup and queue advancement

---

## Check Queue

```bash
ruby orch/orchestrator.rb queue next
```

**If queue is empty:**

```
✅ Queue empty - no PRDs to process
```

STOP here.

---

## Prerequisites Check

Before processing begins, Command 30 (prd-build) will verify:

- ✅ PRD file exists
- ✅ **OpenSpec is empty** (no active changes)
- ✅ Git working tree is clean (or user acknowledges)
- ✅ On development branch (or user acknowledges)

If OpenSpec has active changes, processing will stop immediately with an error. Complete or archive any pending OpenSpec changes before starting a new PRD build.

---

## SELECT PROCESSING MODE

**CHECKPOINT: Use AskUserQuestion**

- Question: "Select processing mode for this queue run:

  **Default Mode**: Stop at each checkpoint for human review and approval

  - Proposal approval checkpoints
  - Human review checkpoints after tests pass
  - Test failure review (after Ralph loop exhausted)

  **Bulk Mode**: Auto-approve review checkpoints and continue processing

  - Automatically approves proposal reviews
  - Automatically approves human reviews
  - Automatically continues after Ralph loop test fixes
  - Still STOPS for critical errors:
    - PRD gaps/conflicts (clarification needed)
    - Git issues (dirty tree, wrong branch)
    - Validation failures
  - Sends Slack notifications at each auto-approved checkpoint

  Note: Bulk mode is designed for unattended batch processing of trusted PRDs."

- Options:
  - "Default Mode - stop at all checkpoints"
  - "Bulk Mode - auto-approve reviews, stop only for errors"

**Store the user's selection in a variable `bulk_mode`:**

- If user selects "Default Mode", set `bulk_mode = false`
- If user selects "Bulk Mode", set `bulk_mode = true`

**Display confirmation:**

```
Mode selected: [Default/Bulk Mode]
```

---

## PHASE: BATCH VALIDATE (Optional - User Choice)

This phase is optional. The system will display all pending PRDs and ask if you want to validate them before processing.

**Step 1: Get and display all pending PRDs with validation status**

```bash
ruby orch/orchestrator.rb queue list
```

Parse the YAML output. Collect all items with `status: pending`.

**For each PRD, read validation status:**

```bash
ruby orch/prd_validator.rb status --prd-path [prd_path]
ruby orch/prd_validator.rb metadata --prd-path [prd_path]
```

Display them to the user in a table format:

```
## Pending PRDs in Queue

| # | PRD | Validation Status |
|---|-----|-------------------|
| 1 | beta-signups-06-prd.md | ✓ Valid (Jan 2, 2026) |
| 2 | campaign-visits-4-prd.md | ⊗ Unvalidated (needs validation) |
| 3 | google-analytics-prd.md | ✗ Invalid (3 errors) |

Total: 3 PRDs in queue
Validation Status: 1 valid, 1 invalid, 1 unvalidated
```

**Status Badge Format:**

- `✓ Valid (Jan 2, 2026)` - PRD passed validation (show validated_at date)
- `✗ Invalid (3 errors)` - PRD failed validation (show error count)
- `⊗ Unvalidated (needs validation)` - PRD not yet validated

---

**Step 2: Check validation status and proceed accordingly**

Based on the validation status summary:

**If all PRDs are already valid:**

Skip the validation question and proceed directly to the main processing loop:

```
✅ All PRDs validated - proceeding to processing
```

Continue to "STORE BULK MODE AND SPAWN COMMAND 30" section.

---

**If some PRDs need validation (invalid or unvalidated):**

**CHECKPOINT: Use AskUserQuestion**

- Question: "Review the validation status above. [X] PRD(s) need validation.

  Validation checks for format compliance, gaps, conflicts, scope issues, and ambiguities. This is a token-intensive process (~20K tokens per PRD).

  How would you like to proceed?"

- Options:
  - "Validate unvalidated/invalid PRDs only" - Proceed to Step 3 (skip already valid PRDs)
  - "Re-validate all PRDs" - Proceed to Step 3 (validate all regardless of status)
  - "Skip validation" - Display warning and skip to main processing loop
  - "Remove invalid PRDs from queue" - Remove PRDs with invalid/unvalidated status and proceed

**IF user chooses "Skip validation":**

Display warning:

```
⚠️ Skipping validation. Proceeding with assumption that all PRDs are valid and ready for implementation.
If any PRD has issues, the build phase may fail or produce incorrect implementations.
```

Skip to main processing loop.

**IF user chooses "Remove invalid PRDs from queue":**

```bash
# For each PRD with invalid/unvalidated status:
ruby orch/orchestrator.rb queue skip --prd-path [prd_path] --reason "Not validated"
```

Then proceed with remaining valid PRDs.

**IF user chooses validation (any option):**

Continue to Step 3 below.

---

**Step 3: Validate PRDs (conditionally)**

For each pending PRD (in queue order):

**Check current validation status:**

```bash
ruby orch/prd_validator.rb status --prd-path [prd_path]
```

**If user chose "Validate unvalidated/invalid PRDs only" and status is 'valid':**

```
Skipping validation for [prd_path] - already validated ✓
```

Continue to next PRD.

**Otherwise, validate the PRD:**

```
Validating PRD [n] of [total]: [prd_path]
```

**Spawn sub-agent validation:**

**Command:** `30: prd-validate`  
**Input:** Provide the `[prd_path]` when invoking the command

Parse the `validation_result` YAML output from the sub-agent.

**IF status is PASS:**

- PRD frontmatter will be updated to 'valid' by the validation command
- Record the result
- Continue to the next PRD in the validation list

**IF status is FAIL or BLOCKED:**

- PRD frontmatter will be updated to 'invalid' by the validation command
- Display the validation issues to the user
- **CHECKPOINT: Use AskUserQuestion**

  - Question: "PRD validation failed for: [prd_path]

    [Display issues from validation_result]

    How would you like to proceed?"

  - Options:
    - "Remediate now" - Run `10: prd-workshop [prd_path]`, then re-validate this PRD
    - "Skip this PRD" - Remove from queue, continue validating others
    - "Abort" - Stop entirely, fix PRDs manually before re-running

**IF user chooses "Remediate now":**

- **Spawn sub-agent:** Command `10: prd-workshop` with the `[prd_path]` as input
- After workshop completes, re-run validation for this PRD
- Continue from validation step

**IF user chooses "Skip this PRD":**

```bash
ruby orch/orchestrator.rb queue skip --prd-path "[prd_path]" --reason "Skipped during validation"
```

- Continue to next PRD in validation list

**IF user chooses "Abort":**

- STOP here. User will fix PRDs manually and re-run.

---

After all PRDs have been validated, display a summary:

```
## Validation Complete

| PRD | Status |
|-----|--------|
| [prd_1] | PASS |
| [prd_2] | PASS |

All [n] PRDs passed validation. Proceeding to processing.
```

---

## STORE BULK MODE AND SPAWN COMMAND 30

**Store bulk_mode in state for subsequent commands:**

```bash
ruby orch/orchestrator.rb state set --key bulk_mode --value [true/false]
```

**Initialize usage tracking for this workflow:**

```bash
ruby orch/orchestrator.rb usage start --prd-path "[first_prd_path]"
```

This starts tracking Claude Code API message usage for the entire workflow. Phase counters will be incremented by each sub-agent.

Display kickoff summary:

```
═══════════════════════════════════════════
  ORCHESTRATION STARTED
═══════════════════════════════════════════
Mode: [Default/Bulk Mode]
═══════════════════════════════════════════

Spawning proposal command...
```

**Run command:** `30: prd-proposal`

Command 30 will:

1. Discover the first pending PRD from the queue
2. Initialize state and mark it as in_progress
3. Process through PREPARE → PROPOSAL → PREBUILD → Create Summary
4. Spawn `35: prd-build` with fresh context for implementation
5. Automatically chain to subsequent commands (35 → 40 → 50 → 60)
6. Loop back to process additional PRDs until queue is empty

---

## Architecture Summary

```
20: prd-orchestrate (ONE-TIME KICKOFF)
│
├── Mode Selection (bulk_mode)
├── Batch Validation (optional)
└── Spawn → 30: prd-proposal

Processing Loop (automatic chaining):
30: prd-proposal → 35: prd-build → 40: prd-test → 50: prd-finalize → 60: prd-post-merge
       │                │                                                     │
       │                └── Reads proposal-summary.md                         ├── If more PRDs → 30: prd-proposal
       └── Creates proposal-summary.md                                        └── If queue empty → COMPLETE
```

Each command in the chain:

- Reads state from `state.yaml` (including `bulk_mode`)
- Performs its phase work
- Spawns the next command in the chain
- Command 30 self-initializes from the queue (discovers next pending PRD)
- Command 35 reads proposal-summary.md for BUILD context (fresh context handoff)
