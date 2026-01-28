---
name: "60: prd-post-merge"
description: "Sub-agent for POST-MERGE cleanup, archive, and queue advancement"
---

# 60: PRD Post-Merge

**Command name:** `60: prd-post-merge`

**Purpose:** Fresh sub-agent for POST-MERGE cleanup. Spawned by the coordinator (Command 20) after PR is merged. Handles checkout to development, pulling latest changes, and queue advancement. OpenSpec archival and PRD move to done/ are handled by Command 50 (finalize) before the PR is created.

**This runs with fresh context to ensure clean state for next PRD processing.**

---

## Prompt

You are a fresh sub-agent handling the POST-MERGE phase for a PRD build. Your responsibility is to clean up after a successful merge: switch back to development, pull latest changes, mark the PRD as complete, and either spawn the next PRD processing or complete the pipeline. Note: OpenSpec archival and PRD move to done/ are already completed by Command 50 (finalize) before the PR is created.

---

## Step 0: Load State

**This command reads all context from state. No context needs to be passed from the spawner.**

```bash
ruby orch/orchestrator.rb state show
```

Read the YAML to get:

- `change_name` - The change being processed
- `prd_path` - The PRD file path
- `branch` - The feature branch (now merged)

---

## PHASE: POST-MERGE

**Track usage for cleanup/merge phase:**

```bash
ruby orch/orchestrator.rb usage increment --phase cleanup_merge
```

### Step 1: Checkout development branch

```bash
git checkout development
```

**If checkout fails (uncommitted changes, etc.):**

- Display error to user
- STOP and return to coordinator with error status

---

### Step 2: Pull latest changes

```bash
git pull --rebase origin development
```

**If pull fails (conflicts, etc.):**

- Display error to user
- STOP and return to coordinator with error status

---

### Step 3: Verify OpenSpec was archived (already done in Command 50)

**Note:** OpenSpec archival was already completed in Command 50 (finalize phase) before the PR was created. This step just verifies it was successful.

```bash
openspec list
```

**Verify** that `[change_name]` does not appear in active changes list.

**If the change still appears:**
- This indicates Command 50 may have had an issue
- Warn the user
- Continue with post-merge (do not re-archive)

---

### Step 4: Mark PRD complete and advance queue

```bash
ruby orch/orchestrator.rb queue complete --prd-path "[prd_path]"
```

This will:

- Mark the current PRD as `completed`
- Record completion timestamp
- Advance the queue position

---

### Step 5: Update state and reset for next PRD

**Update state to indicate post-merge complete:**

```bash
ruby orch/orchestrator.rb state set --key phase --value post_merge_complete
```

**Reset state for next PRD (preserves bulk_mode):**

```bash
ruby orch/orchestrator.rb state reset
```

This clears the PRD-specific state while preserving session settings like `bulk_mode`.

---

### Step 6: Check for next PRD and spawn or complete

```bash
ruby orch/orchestrator.rb queue next
```

**Read the YAML response.**

---

## IF Next PRD Exists

Display:

```
═══════════════════════════════════════════
  60: PRD-POST-MERGE COMPLETE
═══════════════════════════════════════════

Completed: [change_name]
PRD:       [prd_path]
Status:    ✓ Completed

Post-Merge Steps:
  ✓ Checked out development branch
  ✓ Pulled latest changes
  ✓ Verified OpenSpec archive (done in Command 50)
  ✓ Marked PRD complete in queue

Next PRD in queue detected.
Continuing to next PRD...
═══════════════════════════════════════════
```

**Run command:** `30: prd-proposal`

Command 30 will discover and process the next pending PRD from the queue.

---

## IF Queue Empty

### Step 7: Generate Usage Report

**Output the PRD workflow usage report:**

```bash
ruby orch/orchestrator.rb usage complete --format table
```

This generates a detailed breakdown of Claude Code API message usage per phase. The report is also logged to `orch/log/orchestration_usage.log` for historical tracking.

---

### Step 8: Cleanup - Archive queue and delete state

```bash
ruby orch/orchestrator.rb queue archive
```

This archives the queue file to `z_queue_processed_YYYY-MM-DD-HHMM.yaml`.

```bash
ruby orch/orchestrator.rb state delete
```

This deletes the state file completely (will be recreated fresh on next run).

```bash
ruby orch/orchestrator.rb usage delete
```

This deletes the usage tracking file (will be recreated fresh on next run).

---

### Step 9: Send completion notification and display summary

```bash
ruby orch/notifier.rb complete --change-name "[change_name]" --message "All PRDs in queue processed successfully"
```

```bash
ruby orch/orchestrator.rb status
```

Display the usage report from Step 7, followed by the completion summary:

```
═══════════════════════════════════════════
  ✅ ORCHESTRATION COMPLETE
═══════════════════════════════════════════

Final PRD Completed: [change_name]

Queue Summary:
  Completed: [N] PRDs
  Failed:    [N] PRDs
  Skipped:   [N] PRDs

All PRDs in the queue have been processed.

Cleanup:
  ✓ Usage report generated (logged to orch/log/orchestration_usage.log)
  ✓ Queue archived to z_queue_processed_[timestamp].yaml
  ✓ State file deleted
  ✓ Usage tracking file deleted

Ready for next orchestration run.

Thank you for using the PRD orchestration system.
═══════════════════════════════════════════
```

STOP here. Pipeline complete.

---

## Error Handling

On any error:

```bash
ruby orch/notifier.rb error --change-name "[change_name]" --message "[error]" --phase "post-merge" --resolution "[fix suggestion]"
```

STOP. The pipeline will need to be manually restarted after fixing the issue.

---

## Manual Usage

This command can also be run manually after a PR has been merged:

1. Ensure the PR for the change has been merged
2. Run `60: prd-post-merge` with the change name
3. The command will clean up, advance the queue, and either spawn Command 30 for the next PRD or complete the pipeline

This is useful for:

- Recovering from interrupted orchestration
- Manually completing a build that was finalized outside orchestration
