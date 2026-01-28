---
name: '91: prd-checkpoint'
description: 'Handle checkpoint responses during orchestration flow'
---

# 91: PRD Checkpoint Response

**Command name:** `91: prd-checkpoint`

**Purpose:** Handle checkpoint responses during orchestration flow.

**Input:** `{{response}}` - User's checkpoint response

---

## Prompt

You are handling a checkpoint response in the PRD orchestration flow.

**Step 1: Check current state**

```bash
ruby orch/orchestrator.rb state show
```

**Read the checkpoint type:**

- `awaiting_proposal_approval` - User reviewed proposal
- `awaiting_test_review` - User reviewed test failures
- `awaiting_merge` - User completed PR merge

---

## Handle by Checkpoint Type

### awaiting_proposal_approval

**If approved:**
```bash
ruby orch/orchestrator.rb state clear-checkpoint
```
Continue to PREBUILD phase.

**If rejected:**
```
User chose to edit proposal. Stopping orchestration.
Re-run 20: prd-orchestrate when ready.
```

---

### awaiting_test_review

**If "fix manually":**
```
Stopping for manual fixes. Re-run 40: prd-test when ready.
```

**If "skip tests":**
```bash
ruby orch/orchestrator.rb state clear-checkpoint
ruby orch/orchestrator.rb state set --key tests_skipped --value true
```
Continue to FINALIZE phase with warning.

**If "abort":**
```bash
ruby orch/orchestrator.rb queue fail --prd-path "[prd_path]" --reason "User aborted after test failures"
ruby orch/orchestrator.rb state reset
```
STOP.

---

### awaiting_merge

**If "merged":**
```bash
ruby orch/orchestrator.rb state clear-checkpoint
```
Return to coordinator (Command 20) to spawn post-merge sub-agent.

**If "abort":**
```bash
ruby orch/orchestrator.rb queue fail --prd-path "[prd_path]" --reason "User aborted at merge"
ruby orch/orchestrator.rb state reset
```
STOP.

---

## Output

After handling checkpoint, show current status:

```bash
ruby orch/orchestrator.rb status
```

