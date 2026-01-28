---
name: "50: prd-finalize"
description: "Sub-agent for FINALIZE phase - commit, PR creation, and merge checkpoint"
---

# 50: PRD Finalize

**Command name:** `50: prd-finalize`

**Purpose:** Sub-agent for FINALIZE phase. Spawned by the coordinator (Command 20) after tests pass. Handles committing changes, creating the PR, and waiting for merge confirmation.

**This can also be run standalone to complete a PRD build independently.**

---

## Prompt

You are a fresh sub-agent handling the FINALIZE phase for a PRD build. Your responsibility is to commit all changes, create a pull request, and wait for merge confirmation.

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

---

## PHASE: FINALIZE

**Track usage for PR creation phase:**

```bash
ruby orch/orchestrator.rb usage increment --phase pr_creation
```

### Step 1: Archive OpenSpec Change

**DO NOT use the Skill tool for archive - execute commands directly to maintain flow.**

**1.1 Verify the change exists:**

```bash
openspec list
```

Confirm `[change_name]` appears in the list.

**1.2 Archive the change:**

```bash
openspec archive [change_name] --yes
```

**1.3 Verify archive completed:**

```bash
openspec list
```

Confirm `[change_name]` no longer appears in active changes.

**After archive is verified complete, continue immediately with Step 2.**

---

### Step 2: Move PRD to Done Directory

**Get the PRD path from state:**

```bash
ruby orch/orchestrator.rb state get --key prd_path
```

**If prd_path exists and is NOT already in a `done/` directory:**

```bash
# Create done directory if needed
mkdir -p [prd_directory]/done

# Move PRD file
git mv [prd_path] [prd_directory]/done/[prd_filename]
```

Example:
- From: `docs/prds/inquiry-system/inquiry-02-email-prd.md`
- To: `docs/prds/inquiry-system/done/inquiry-02-email-prd.md`

**If PRD is already in done/ or prd_path is not set, skip this step.**

---

### Step 3: Commit All Changes

**Stage and commit all changes:**

```bash
git add -A
git commit -m "feat([change_name]): implementation complete"
```

**Verify working tree is clean:**

```bash
git status --porcelain
```

If files remain uncommitted, stage and commit again.

**Important Notes:**
- The commit will include ALL uncommitted changes in the repository, not just changes related to this PRD
- This is intentional to handle cases where work on the next change has already begun

---

### Step 4: Push and Create PR

```bash
git push -u origin HEAD
gh pr create --title "feat([change_name]): implementation" --body "## Summary

Implementation for [change_name]

## PRD Reference

[prd_path]

## Changes

See OpenSpec: openspec/changes/[change_name]/

## Testing

- [ ] All tests passing
- [ ] Manual verification complete" --base development
gh pr view --web
```

---

## CRITICAL: Mandatory Merge Checkpoint

**⚠️  This checkpoint ALWAYS stops in both Default and Bulk modes.**

Unlike proposal review (Command 30) and human testing review (Command 40) which can be
auto-approved in bulk_mode, the PR merge checkpoint requires explicit human confirmation
in ALL modes because:

- **Safety gate:** Prevents auto-merging of broken or incomplete PRs
- **Code review enforcement:** Ensures the PR was reviewed before merge
- **Quality control:** Human must verify the PR is actually ready to merge
- **No rollback:** After merge, changes are in development branch - no undo

This follows the ERROR checkpoint pattern from Command 30. It cannot and should not
be bypassed by bulk_mode automation.

---

### Step 5: Notify and Merge Checkpoint

```bash
ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "PR created and ready for merge" --checkpoint "awaiting_merge" --action "Review and merge the PR, then continue"
```

**MANDATORY CHECKPOINT: Use AskUserQuestion**

**NOTE: This is an ERROR checkpoint - it ALWAYS stops in both Default and Bulk modes.**

- Question: "PR opened in browser. After merging, select continue."
- Options:
  - "Merged - continue to post-merge cleanup"
  - "Abort - stop processing this PRD"

**No auto-approval is permitted - user must manually select an option.**

**If "Merged":**

- Update state to indicate merge complete
- Proceed to return to coordinator

**If "Abort":**

```bash
ruby orch/orchestrator.rb queue fail --prd-path "[prd_path]" --reason "User aborted at merge"
```

- STOP and return to coordinator with abort status

---

## SPAWN NEXT COMMAND

**CRITICAL: Do NOT stop here. You MUST spawn the POST-MERGE command.**

**PR merged. Spawning POST-MERGE cleanup.**

Display summary:

```
═══════════════════════════════════════════
  50: PRD-FINALIZE COMPLETE
═══════════════════════════════════════════

Change:     [change_name]
Branch:     [branch]
PR:         [PR URL or number]
Status:     ✓ Merged

Finalize Steps:
  ✓ OpenSpec archived
  ✓ PRD moved to done/
  ✓ All changes committed (with polling)
  ✓ PR created
  ✓ PR merged

Spawning post-merge command...
═══════════════════════════════════════════
```

**Update state to indicate finalize complete:**

```bash
ruby orch/orchestrator.rb state set --key phase --value finalize_complete
```

**MANDATORY: Spawn the post-merge command using the Skill tool:**

```
Use Skill tool with: skill = "otl:orch:60-post-merge"
```

This is NOT optional - you MUST use the Skill tool to invoke `60: prd-post-merge`. The post-merge command will read `change_name` from state, perform cleanup, and check for more PRDs.

**If you do not have access to the Skill tool, then execute these commands directly:**

```bash
ruby orch/orchestrator.rb finalize --post-merge
```

Then proceed with development branch checkout and queue continuation as described in Command 60.

---

## Running Standalone

This command can also be run independently (not from orchestration):

1. Ensure you're on the correct feature branch
2. Ensure all changes are ready to commit
3. Run `50: prd-finalize` with the change name
4. This command will handle the commit → PR → merge cycle
5. After merge, manually run `60: prd-post-merge` for cleanup

**Standalone usage:**

```
Command: 50: prd-finalize
Input: change_name (optional - uses state if not provided)
```

This is useful for:

- Completing a build that was done manually
- Recovering from interrupted orchestration
- Finalizing work done outside the normal flow

---

## Error Handling

The finalize command includes comprehensive error handling:

**Possible errors:**

1. **git_add_failed** - `git add -A` command failed
   - Check git repository state
   - Verify file permissions
   - Check disk space

2. **git_staging_timeout** - Could not stage all files after 5 attempts
   - Some files may be locked or inaccessible
   - Check for file permission issues
   - Review which files remain unstaged in error output

3. **pre_commit_verification_failed** - Files remain unstaged after polling loop
   - Indicates files that cannot be staged
   - Check .gitignore or .cursorignore for conflicts
   - Verify file permissions

4. **git_commit_failed** - `git commit` command failed
   - Check commit message format
   - Verify repository state
   - Check for git hooks that may be failing

5. **post_commit_verification_failed** - Working tree not clean after commit
   - Indicates files that weren't included in commit
   - Should not occur with polling approach
   - Investigate filesystem or git issues

**On any error:**

```bash
ruby orch/notifier.rb error --change-name "[change_name]" --message "[error]" --phase "finalize" --resolution "[fix suggestion]"
```

STOP. The pipeline will need to be manually restarted after fixing the issue.

**Error output includes:**
- Exact step that failed
- Command output
- List of affected files
- Suggested resolution
