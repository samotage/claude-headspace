---
name: "40: prd-test"
description: "Sub-agent for TEST phase with Ralph loop and human review"
---

# 40: PRD Test

**Command name:** `40: prd-test`

**Purpose:** Fresh sub-agent for TEST phase. Spawned by the coordinator (Command 20) after BUILD completes. Handles test execution, Ralph loop auto-retry, and human review checkpoint.

**This runs with fresh context to ensure reliable test execution.**

---

## Prompt

You are a fresh sub-agent handling the TEST phase for a PRD build. Your responsibility is to run the test suite, handle failures with the Ralph loop (auto-retry up to 2 times), and conduct human review before finalizing.

---

## Step 0: Load State

**This command reads all context from state. No context needs to be passed from the spawner.**

```bash
ruby orch/orchestrator.rb state show
```

Read the YAML to get:

- `change_name` - The change being processed
- `prd_path` - The PRD file path
- `branch` - The feature branch
- `bulk_mode` - Processing mode (true = bulk, false = default)

If `bulk_mode` is not set, default to `bulk_mode = false` (Default Mode).

---

## PHASE: TEST

**Track usage for testing phase:**

```bash
ruby orch/orchestrator.rb usage increment --phase testing
```

```bash
ruby orch/orchestrator.rb test
```

**Read the YAML output for test scope and Ralph loop status.**

**Run the tests:**

Use the suggested commands from `data.suggested_commands` or:

```bash
pytest -v
```

**Record results:**

```bash
ruby orch/orchestrator.rb test record --passed [N] --total [N] --failures '[{"file":"spec/...", "line":42, "error":"..."}]'
```

**Read the response:**

---

### If `outcome: all_passed` - HUMAN REVIEW CHECKPOINT

All tests passed. Before returning to coordinator, present the human review checkpoint.

**Display review summary:**

1. Show tasks completed from tasks.md:

```bash
cat openspec/changes/[change_name]/tasks.md
```

2. Show files changed:

```bash
git status --short
```

3. Provide instructions for manual testing of functionality

**IF bulk_mode is TRUE:**

- Send Slack notification:
  ```bash
  ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Tests passed - ready for human review" --checkpoint "awaiting_human_review" --action "Auto-approved in bulk mode"
  ```
- Display message to user:

  ```
  🤖 BULK MODE: Auto-approved awaiting_human_review

  **Completed Tasks:**
  [List from tasks.md]

  **Files Changed:**
  [git status output]

  All tests passed. Returning to coordinator...
  ```

- Auto-select the "Approved - continue" option
- Proceed to return to coordinator

**IF bulk_mode is FALSE (default mode):**

- Send notification:

  ```bash
  ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Tests passed - ready for human review" --checkpoint "awaiting_human_review" --action "Review built work and verify functionality before finalizing"
  ```

- **CHECKPOINT: Use AskUserQuestion**

  - Question: "Tests passed. Please review the built work:

    **Completed Tasks:**
    [List from tasks.md]

    **Files Changed:**
    [git status output]

    **Manual Testing:**
    Please verify functionality in the browser.

    How would you like to proceed?"

  - Options:
    - "Approved - continue to finalize"
    - "Needs fixes - I'll provide feedback for you to address"
    - "Stop - I'll fix manually and re-run"
    - "Skip issues - proceed anyway (with warning)"

- **Based on response:**
  - **Approved**: Proceed to return to coordinator
  - **Needs fixes**:
    - Receive feedback from user
    - Make the requested changes
    - Re-run tests
    - Return to this checkpoint (record results again)
  - **Stop**: STOP here. User will make manual changes and re-run `40: prd-test`
  - **Skip issues**: Add warning note, proceed to return to coordinator with caution

---

### If `outcome: retry`

- This is Ralph loop attempt [N] of 2
- Analyze the failures
- Attempt to fix the issues
- Re-run tests
- Record results again
- Repeat until pass or exhausted

---

### If `outcome: human_intervention`

- Ralph loop exhausted (2 attempts failed)

**IF bulk_mode is TRUE:**

- Send Slack notification:
  ```bash
  ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Tests failed after 2 retry attempts" --checkpoint "awaiting_test_review" --action "Auto-selected: Skip tests and proceed (bulk mode)"
  ```
- Display message to user:

  ```
  🤖 BULK MODE: Auto-approved awaiting_test_review

  ⚠️ WARNING: Tests failed after Ralph loop (2 attempts)
  Auto-selecting "Skip tests - proceed to finalize anyway"

  Test failures will be included in PR for manual review.
  Returning to coordinator...
  ```

- Auto-select the "Skip tests - proceed" option
- Set warning flag and proceed to return to coordinator

**IF bulk_mode is FALSE (default mode):**

- Send notification:

  ```bash
  ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Tests failed after 2 retry attempts" --checkpoint "awaiting_test_review" --action "Review failures and choose: fix manually, skip tests, or abort"
  ```

- **CHECKPOINT: Use AskUserQuestion**

  - Question: "Tests failed after Ralph loop. How to proceed?"
  - Options:
    - "I'll fix manually - then re-run this command"
    - "Skip tests - proceed to finalize anyway"
    - "Abort - stop processing this PRD"

- **Based on response:**
  - Fix manually: STOP, user will re-run `40: prd-test`
  - Skip tests: Set warning flag and proceed to return to coordinator
  - Abort: Mark as failed and STOP

---

## SPAWN NEXT COMMAND

**CRITICAL: Do NOT stop here. You MUST spawn the VALIDATE phase.**

**Tests handled. Spawning VALIDATE phase for spec compliance check.**

Display summary:

```
═══════════════════════════════════════════
  40: PRD-TEST COMPLETE
═══════════════════════════════════════════

Change:     [change_name]
Branch:     [branch]

Test Results:
  Passed:   [N]
  Failed:   [N]
  Total:    [N]
  Status:   [PASSED ✓ / SKIPPED ⚠️]

Human Review: [Approved / Skipped with warning]

Spawning validate command...
═══════════════════════════════════════════
```

**Update state to indicate test complete:**

```bash
ruby orch/orchestrator.rb state set --key phase --value test_complete
```

**MANDATORY: Spawn the validate command using the Skill tool:**

```
Use Skill tool with: skill = "otl:orch:45-validate-build"
```

This is NOT optional - you MUST use the Skill tool to invoke `45: prd-validate-build`. Command 45 will:
- Read `change_name` from state
- Validate implementation against all spec artifacts (PRD, proposal.md, design.md, tasks.md, specs/*.md)
- Generate compliance-report.md
- Handle retry loop if validation fails (up to 2 attempts)
- Then spawn Command 50 for finalize

**If you do not have access to the Skill tool, then execute these commands directly:**

```bash
ruby orch/orchestrator.rb validate
```

Then proceed with spec compliance validation as described in Command 45.

---

## Error Handling

On any error:

```bash
ruby orch/notifier.rb error --change-name "[change_name]" --message "[error]" --phase "test" --resolution "[fix suggestion]"
```

STOP. The pipeline will need to be manually restarted after fixing the issue.
