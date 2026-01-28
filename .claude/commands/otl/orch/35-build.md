---
name: '35: prd-build'
description: 'Sub-agent for BUILD phase - reads proposal-summary for context'
---

# 35: PRD Build

**Command name:** `35: prd-build`

**Purpose:** Fresh sub-agent for the BUILD phase. Reads the proposal-summary.md created by Command 30 for context, then implements all tasks. Spawned by Command 30 after proposal approval.

**This runs with fresh context to ensure reliable implementation.**

---

## Prompt

You are a fresh sub-agent handling the BUILD phase for a PRD. Your responsibility is to implement all tasks defined in tasks.md, using the proposal-summary.md as your primary context source. This ensures you have all necessary information without the accumulated context from proposal creation.

---

## Step 0: Initialize BUILD Context

**This command reads state from the queue/state files. No context is passed from the spawner.**

### Load state

```bash
ruby orch/orchestrator.rb state show
```

Read the YAML to get:
- `change_name` - The change being processed
- `prd_path` - The PRD file path
- `branch` - The feature branch
- `bulk_mode` - Processing mode (true = bulk, false = default)
- `phase` - Should be `proposal_complete`

**Verify phase is `proposal_complete`:**
- If phase is not `proposal_complete`, something is wrong
- Display error and STOP

### Get proposal_summary_path from queue

```bash
ruby orch/orchestrator.rb queue status
```

Look for the current PRD's `proposal_summary_path` field.

If `proposal_summary_path` is not set:
- Display error: "No proposal summary found. Run 30: prd-proposal first."
- STOP

Display:
```
═══════════════════════════════════════════
  BUILD PHASE STARTING
═══════════════════════════════════════════
Change: [change_name]
Branch: [branch]
Mode:   [Default Mode / Bulk Mode based on bulk_mode]

Loading context from proposal summary...
═══════════════════════════════════════════
```

---

## Step 1: Load Proposal Summary Context

**Read the proposal-summary.md file as your primary context source.**

```bash
cat openspec/changes/[change_name]/proposal-summary.md
```

**This file contains everything you need for BUILD:**

1. **Architecture Decisions** - Key choices already made
2. **Implementation Approach** - How to implement
3. **Files to Modify** - What files to change
4. **Acceptance Criteria** - Success metrics
5. **Constraints and Gotchas** - Things to watch out for
6. **Git Change History** - Related files, patterns, and history
7. **Q&A History** - Clarifications from proposal phase
8. **Dependencies** - Gems, APIs, migrations needed
9. **Testing Strategy** - What to test
10. **OpenSpec References** - Links to full proposal files

**Internalize this context before proceeding.**

---

## Step 2: Load Tasks

**Read the tasks.md file to get the implementation tasks.**

```bash
cat openspec/changes/[change_name]/tasks.md
```

Identify:
- Implementation tasks (Phase 2 section)
- Testing tasks (Phase 3 section)
- Final verification tasks (Phase 4 section)

---

## PHASE: BUILD

**Track usage for implementation phase:**

```bash
ruby orch/orchestrator.rb usage increment --phase implementation
```

```bash
ruby orch/orchestrator.rb build
```

**Read the YAML output to verify:**
- Tasks file exists and is valid
- No errors in the response

**DO NOT use the Skill tool for implementation - execute tasks directly to maintain flow.**

**Implementation Process:**

1. **Read tasks.md** to see implementation tasks:
   ```bash
   cat openspec/changes/[change_name]/tasks.md
   ```

2. **Work through tasks sequentially:**
   - Read proposal.md, design.md (if exists), and tasks.md to confirm scope
   - Implement each task one by one, keeping edits minimal and focused
   - Mark tasks complete in tasks.md as work is done (`[x]` instead of `[ ]`)
   - Reference openspec commands when additional context is needed

3. **Handle Dependencies:**
   - If Dependencies section lists gems to add, handle those first
   - If migrations are needed, create them (but DO NOT run without user approval)
   - Note any external API setup requirements

**Important context:**
- The proposal-summary.md provides architectural decisions
- Use the Files to Modify and Implementation Patterns sections to guide work
- Respect the Constraints and Gotchas from the summary

**After all implementation tasks are complete, continue to VERIFY BUILD COMPLETION below.**

---

## VERIFY BUILD COMPLETION

**Before spawning the test command, you MUST verify all implementation tasks are complete.**

**Step 1: Check current progress**

```bash
ruby orch/orchestrator.rb build
```

**Step 2: Read the YAML output and verify:**

Check these fields:
- `data.progress.implementation_completed` - number of completed tasks
- `data.progress.implementation_total` - total number of tasks  
- `data.progress.percentage` - completion percentage

**Step 3: Verify 100% completion**

**IF percentage is NOT 100%:**
- DO NOT proceed to spawn test command
- Review `data.tasks.implementation` to see which tasks remain incomplete (completed: false)
- Continue implementing the remaining tasks
- Mark tasks complete in tasks.md using [x] as you finish them
- Return to Step 1 to re-verify

**ONLY proceed when verification shows 100% completion.**

Display completion status to user:
```
BUILD PHASE VERIFICATION
------------------------
Implementation tasks: [completed] / [total] ([percentage]%)
Status: [COMPLETE ✓ / INCOMPLETE - X tasks remaining]
```

**IF percentage is 100%:**
- All implementation tasks are complete
- Proceed to spawn test command

---

## SPAWN TEST COMMAND

**CRITICAL: Do NOT stop here. You MUST spawn the TEST phase.**

**All implementation tasks verified complete. Spawning TEST phase.**

Display summary:
```
═══════════════════════════════════════════
  35: PRD-BUILD COMPLETE
═══════════════════════════════════════════

Change:     [change_name]
Branch:     [branch]
PRD:        [prd_path]

Phases Completed:
  ✓ PREPARE   - Git environment ready (Command 30)
  ✓ PROPOSAL  - OpenSpec created (Command 30)
  ✓ PREBUILD  - Snapshot committed (Command 30)
  ✓ SUMMARY   - Proposal summary created (Command 30)
  ✓ BUILD     - Implementation complete

Implementation: [completed]/[total] tasks (100%)

Spawning test command...
═══════════════════════════════════════════
```

**Update state to indicate build complete:**

```bash
ruby orch/orchestrator.rb state set --key phase --value build_complete
```

**MANDATORY: Spawn the test command using the Skill tool:**

```
Use Skill tool with: skill = "otl:orch:40-test"
```

This is NOT optional - you MUST use the Skill tool to invoke `40: prd-test`. The test command will read `change_name` and `bulk_mode` from state.

**If you do not have access to the Skill tool, then execute these commands directly:**

```bash
ruby orch/orchestrator.rb test
```

Then proceed to run tests and record results as described in Command 40.

---

## Error Handling

If any phase fails:

```bash
ruby orch/notifier.rb error --change-name "[change_name]" --message "[error description]" --phase "build" --resolution "[suggested fix]"
```

Then STOP. The pipeline will need to be manually restarted after fixing the issue.

---

## Quick Reference: Proposal Summary Sections

When implementing, refer to these proposal-summary.md sections:

| Need | Section to Check |
|------|------------------|
| How to structure code | Implementation Patterns |
| What files to modify | Files to Modify |
| Why decisions were made | Architecture Decisions, Q&A History |
| What to avoid | Constraints and Gotchas |
| What dependencies to add | Dependencies |
| What tests to write | Testing Strategy |
| Previous work on subsystem | Git Change History → OpenSpec History |

