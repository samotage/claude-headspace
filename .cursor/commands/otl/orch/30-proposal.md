---
name: '30: prd-proposal'
description: 'Sub-agent for PREPARE → PROPOSAL → PREBUILD → Create Summary phases'
---

# 30: PRD Proposal

**Command name:** `30: prd-proposal`

**Purpose:** Fresh sub-agent for PREPARE → PROPOSAL → PREBUILD phases. Creates OpenSpec proposal files and generates a proposal-summary.md for handoff to the BUILD phase. Spawned by the coordinator (Command 20) for each PRD.

**This runs with fresh context to ensure reliable proposal generation.**

---

## Prompt

You are a fresh sub-agent handling the PROPOSAL phases for a PRD. Your responsibility is to take a PRD through proposal creation: prepare the git environment, create the OpenSpec proposal, snapshot it, and generate a comprehensive proposal summary for the BUILD phase.

---

## Step 0: Initialize PRD Processing

**This command self-initializes from the queue. No context needs to be passed from the spawner.**

### Check for pending PRDs

```bash
ruby orch/orchestrator.rb queue next
```

**IF `queue_empty: true`:**

Display:
```
═══════════════════════════════════════════
  NO PRDs TO PROCESS
═══════════════════════════════════════════
Queue is empty. Nothing to build.
═══════════════════════════════════════════
```

STOP here. Pipeline complete.

---

**IF next PRD exists:**

Extract `prd_path` from the YAML response.

### Start PRD processing

```bash
ruby orch/orchestrator.rb queue start --prd-path "[prd_path]"
```

This command:
- Initializes state with `prd_path`, `change_name`, `branch`
- Marks the queue item as `in_progress`

### Load state including bulk_mode

```bash
ruby orch/orchestrator.rb state show
```

Read the YAML to get:
- `change_name` - The change being processed
- `prd_path` - The PRD file path
- `branch` - The feature branch
- `bulk_mode` - Processing mode (true = bulk, false = default)

If `bulk_mode` is not set, default to `bulk_mode = false` (Default Mode).

Display:
```
═══════════════════════════════════════════
  PROCESSING PRD
═══════════════════════════════════════════
PRD:  [prd_path]
Mode: [Default Mode / Bulk Mode based on bulk_mode]
═══════════════════════════════════════════
```

---

## PHASE: PREPARE

**Track usage for branch setup phase:**

```bash
ruby orch/orchestrator.rb usage increment --phase branch_setup
```

```bash
ruby orch/orchestrator.rb prepare --prd-path "[prd_path]"
```

**Read the YAML output.**

### Handle Errors (Always Stop)

**If `status` == `error`:**

These are critical errors that ALWAYS stop processing in both Default and Bulk modes:

- **openspec_not_empty** - Active OpenSpec changes detected
  - Display the list of active changes to user
  - Instruct user to run `openspec list` to see details
  - Instruct user to either:
    - Complete current work and merge/archive, OR
    - Run `openspec archive <change-id> --yes` if change is no longer needed
  - Run: `ruby orch/orchestrator.rb queue fail --prd-path "[prd_path]" --reason "OpenSpec not empty"`
  - STOP and return to coordinator

- **prd_not_found** - PRD file doesn't exist
  - Display error to user
  - Run: `ruby orch/orchestrator.rb queue fail --prd-path "[prd_path]" --reason "PRD file not found"`
  - STOP and return to coordinator

- **validation_regression** or **mixed_validation_content_changes** - PRD validation issues
  - Display error details to user
  - Slack notification already sent by Ruby command
  - Run: `ruby orch/orchestrator.rb queue fail --prd-path "[prd_path]" --reason "Validation error"`
  - STOP and return to coordinator

### Handle Checkpoints (Mode-Dependent)

**If `checkpoints` array is present and not empty:**

**FOR EACH checkpoint in the checkpoints array:**

**1. Identify checkpoint type:**
   - `dirty_tree_confirmation` - Working tree has uncommitted changes
   - `branch_confirmation` - Not on development branch
   - `branch_exists_confirmation` - Feature branch already exists
   - `validation_commit_approval` - PRD validation status changed to 'valid'

**2. Handle based on bulk_mode:**

**IF bulk_mode is TRUE (Bulk Mode):**

- Display auto-approval message:
  ```
  🤖 BULK MODE: Auto-approved [checkpoint_type]

  [Brief description of what was auto-approved based on checkpoint type]

  Continuing...
  ```

- Auto-select the "proceed/yes/use_existing" option (based on checkpoint type):
  - `dirty_tree_confirmation` → select "yes_proceed"
  - `branch_confirmation` → select "yes_proceed"
  - `branch_exists_confirmation` → select "use_existing"
  - `validation_commit_approval` → select "yes_commit"

- Continue to next step WITHOUT using AskUserQuestion

**IF bulk_mode is FALSE (Default Mode):**

- **CHECKPOINT: Use AskUserQuestion**
- Present the checkpoint question and options from the YAML to the user
- Wait for user response
- Handle response:
  - If user selects "abort/no_abort" options:
    - Run: `ruby orch/orchestrator.rb queue fail --prd-path "[prd_path]" --reason "User aborted"`
    - STOP and return to coordinator
  - If user selects "proceed/yes" options:
    - Continue to next step
  - If user selects "yes_commit" for validation:
    - Ruby command will execute the commit
    - Continue to next step

### Handle Warnings

**If `warnings` array is present:**
- Display warnings to user for visibility
- Continue processing (warnings are informational)

### Execute Next Steps

**Execute the `next_steps` commands from the YAML output in order:**

- Run git commands as instructed (git pull, git checkout, etc.)
- Continue to PROPOSAL phase

---

## PHASE: PROPOSAL

**Track usage for OpenSpec generation phase:**

```bash
ruby orch/orchestrator.rb usage increment --phase openspec_generation
```

```bash
ruby orch/orchestrator.rb proposal
```

**Read the YAML output.**

The output now includes `data.git_context` with historical information about:
- Related files in the codebase
- Recent commits (last 12 months)
- OpenSpec change history
- Implementation patterns

**Use this git context throughout the PROPOSAL phase to:**
1. Inform gap detection (Step 1)
2. Enhance conflict checking (Step 2)
3. Write accurate Impact sections in proposal.md (Step 4)
4. Create realistic tasks following established patterns in tasks.md (Step 4)

**IMPORTANT: Store the `git_context` data - you will need it for the proposal-summary.md.**

---

### STEP 1: Gap Check (Automated from Ruby Output)

Review the YAML output for:

- `data.gaps` - List of detected gaps in the PRD
- `data.git_context` - Historical context about this subsystem **[NEW]**
- `warnings` - Includes high-severity gaps
- `checkpoints` - May include `clarification_needed` if gaps detected

**If `checkpoints` contains `clarification_needed`:**
- Display the gaps to the user
- Reference git_context to inform your questions
- Proceed to Conflict Check below

---

### STEP 2: Conflict Check (Agent Evaluation Enhanced with Git Context)

**BEFORE creating any OpenSpec files, YOU MUST evaluate the PRD for conflicts:**

**Use `data.git_context` to inform this evaluation:**

1. **Contradictory Requirements**
   - Are there requirements that cannot both be satisfied?
   - Do any requirements conflict with each other?

2. **Scope Conflicts**
   - Do any "Out of Scope" items overlap with stated requirements?
   - Check `git_context.related_files` - are we trying to modify frozen/stable areas?

3. **Tech-Requirement Mismatch**
   - Does the Technical Implementation section align with Requirements?
   - Check `git_context.patterns_detected` - does this follow established patterns?
   - Check `git_context.openspec_history` - are we contradicting recent changes?

4. **Active Development Conflicts**
   - Check `git_context.recent_commits` - is someone actively working here?
   - Are there recent changes that might conflict?

5. **Other Inconsistencies**
   - Are there any ambiguities that require assumptions?
   - Is anything unclear that could lead to incorrect implementation?

---

### STEP 3: Clarification Checkpoint (If Needed)

**NOTE: This is an ERROR checkpoint - it ALWAYS stops in both Default and Bulk modes.**

**IF you identified ANY gaps, conflicts, or questions from Steps 1-2:**

```bash
ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Clarification needed before proposal creation" --checkpoint "awaiting_clarification" --action "Answer questions or update PRD before proceeding"
```

**CHECKPOINT: Use AskUserQuestion**

- Question: "I need clarification on the following before creating the OpenSpec proposal:

  [LIST YOUR SPECIFIC QUESTIONS HERE - be precise about what needs clarification]"

- Options:
  - "Here are answers - continue" (user provides answers in response)
  - "I'll update the PRD - stop" (user will update PRD and re-run)

**DO NOT proceed to create files until clarifications are resolved.**

**Track any Q&A for the proposal-summary.md:**
- Questions asked and answers received
- Decisions made based on clarifications
- Alternatives considered and rejected

**IF the PRD is sufficiently clear and consistent (no gaps or conflicts):**
- Skip the clarification checkpoint
- Proceed directly to Step 4

---

### STEP 4: Create OpenSpec Files

**Only proceed here after clarification is resolved (or not needed).**

**IMPORTANT: After completing this step, you MUST continue to PHASE: PREBUILD. Do not stop after validation passes.**

**DO NOT use the Skill tool for proposal creation - execute commands directly to maintain flow.**

**4.1 Create the OpenSpec change directory:**

```bash
mkdir -p openspec/changes/[change_name]
```

**4.2 Create the three required files:**

Create these files using the Write tool:

1. **`openspec/changes/[change_name]/proposal.md`** - Impact section:
   - List affected files from `git_context.related_files`
   - Reference recent changes from `git_context.openspec_history`
   - Follow the standard proposal template

2. **`openspec/changes/[change_name]/tasks.md`** - Implementation tasks:
   - Follow structure from `git_context.patterns_detected.typical_structure`
   - Reference similar tasks from `git_context.recent_commits`
   - Use the standard task checklist format

3. **`openspec/changes/[change_name]/spec.md`** - Delta specifications:
   - Check `git_context.openspec_history` for existing requirements
   - Ensure consistency with previous changes to this subsystem

**4.3 Validate the proposal:**

```bash
openspec validate [change_name] --strict
```

**After validation passes, continue immediately to PHASE: PREBUILD below.**

---

## PHASE: PREBUILD

```bash
ruby orch/orchestrator.rb prebuild
```

**Execute the commit commands from `next_steps`:**

```bash
git add openspec/changes/[change_name]/
git commit -m "chore(spec): [change_name] pre-build snapshot"
git push -u origin HEAD
```

---

## PHASE: CREATE PROPOSAL SUMMARY

**Create the proposal-summary.md file as a handoff document for the BUILD phase.**

This file captures all context needed for BUILD without requiring the full PROPOSAL context.

### Create the file: `openspec/changes/[change_name]/proposal-summary.md`

```markdown
# Proposal Summary: [change_name]

## Architecture Decisions
- [Key architectural choices made during proposal]
- [Patterns selected based on git_context]

## Implementation Approach
- [Chosen approach and rationale]
- [Why this approach vs alternatives]

## Files to Modify
- [List of key files/components from proposal.md Impact section]
- [Organized by type: models, controllers, services, etc.]

## Acceptance Criteria
- [Condensed from PRD requirements]
- [Key success metrics]

## Constraints and Gotchas
- [Critical things BUILD must know]
- [Edge cases identified during proposal]
- [Technical debt or workarounds needed]

## Git Change History

### Related Files
[From git_context.related_files - categorized by type]
- Models: [list]
- Controllers: [list]
- Services: [list]
- Policies: [list]
- Views: [list]
- Specs: [list]

### OpenSpec History
[From git_context.openspec_history]
- [Previous changes to this subsystem with dates]

### Implementation Patterns
[From git_context.patterns_detected]
- [Detected structure: e.g., model → service → controller → policy → views]

## Q&A History
- [Key clarifications made during PROPOSAL phase]
- [Decisions made in response to questions]
- [Alternatives considered and rejected]

## Dependencies
- [Required gems/packages to add]
- [External services/APIs involved]
- [Database migrations needed]

## Testing Strategy
- [What needs tests]
- [Test scenarios to cover]
- [From PRD Testing Requirements section]

## OpenSpec References
- proposal.md: openspec/changes/[change_name]/proposal.md
- tasks.md: openspec/changes/[change_name]/tasks.md
- spec.md: openspec/changes/[change_name]/specs/spec.md
```

### Update queue with proposal_summary_path

```bash
ruby orch/orchestrator.rb queue update-field --prd-path "[prd_path]" --field proposal_summary_path --value "openspec/changes/[change_name]/proposal-summary.md"
```

### Commit the proposal summary

```bash
git add openspec/changes/[change_name]/proposal-summary.md
git commit -m "chore(spec): [change_name] proposal summary for BUILD handoff"
git push
```

---

## PHASE: PROPOSAL REVIEW CHECKPOINT

**IF bulk_mode is TRUE:**

- Send Slack notification:
  ```bash
  ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Proposal ready for review" --checkpoint "awaiting_proposal_approval" --action "Auto-approved in bulk mode"
  ```
- Display message to user:
  ```
  🤖 BULK MODE: Auto-approved awaiting_proposal_approval
  OpenSpec proposal files have been created and validated.
  Proposal summary created for BUILD handoff.
  Spawning BUILD phase...
  ```
- Auto-select the "Approved - continue" option
- Proceed to SPAWN BUILD without waiting for user input

**IF bulk_mode is FALSE (default mode):**

- Send notification for review:
  ```bash
  ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Proposal ready for review" --checkpoint "awaiting_proposal_approval" --action "Review OpenSpec files and approve to continue"
  ```

- **CHECKPOINT: Use AskUserQuestion**
  - Question: "OpenSpec proposal created. Review and approve?"
  - Options: "Approved - continue", "Need edits - stop"

- **If user approves, continue. If not, STOP and return to coordinator.**

---

## SPAWN BUILD COMMAND

**Proposal complete. Spawning BUILD phase with fresh context.**

Display summary:
```
═══════════════════════════════════════════
  30: PRD-PROPOSAL COMPLETE
═══════════════════════════════════════════

Change:     [change_name]
Branch:     [branch]
PRD:        [prd_path]

Phases Completed:
  ✓ PREPARE   - Git environment ready
  ✓ PROPOSAL  - OpenSpec created
  ✓ PREBUILD  - Snapshot committed
  ✓ SUMMARY   - Proposal summary created

Proposal Summary: openspec/changes/[change_name]/proposal-summary.md

Spawning build command with fresh context...
═══════════════════════════════════════════
```

**Update state to indicate proposal complete:**

```bash
ruby orch/orchestrator.rb state set --key phase --value proposal_complete
```

**Run command:** `35: prd-build`

Command 35 will read `change_name`, `bulk_mode`, and `proposal_summary_path` from state/queue.

---

## Error Handling

If any phase fails:

```bash
ruby orch/notifier.rb error --change-name "[change_name]" --message "[error description]" --phase "[current phase]" --resolution "[suggested fix]"
```

Then STOP. The pipeline will need to be manually restarted after fixing the issue.

