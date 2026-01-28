---
name: 'SOP 80: archive-and-commit'
description: 'Final wrap-up: archive OpenSpec change and commit to GitHub'
---

# SOP 80: archive-and-commit

**Goal:** Standardise the final wrap-up for a work unit: archive current OpenSpec change and commit to GitHub.

**Command name:** `SOP 80: archive-and-commit`

---

## Prompt

You are helping me wrap up a completed work unit in a Python/Flask project using OpenSpec.

You can run shell commands in the integrated terminal.

**Automation Principles:**

- Automatically run all **safe, read-only commands** (e.g., `openspec list`, `git status`, `git diff`) without asking for approval.
- Only require confirmation for **destructive operations** (archive, git add/commit, file deletions, push, PR creation).
- Combine related information gathering steps and present them together for efficiency.
- Minimize checkpoints to only critical decision points.

At each critical step:

- For safe commands: Run them automatically and include output in your response.
- For destructive operations: Show the exact command(s), clearly mark them as **destructive**, and ask for approval using `[y,n]` format.
- Include full terminal output in your reply.

If you cannot run a command yourself for any reason, clearly say so, then ask me to run it and paste the output.

---

## 0. Collect change name input

**IMPORTANT: DO NOT PROCEED without determining the change name.**

1. **Check if change name is provided or can be inferred:**

   🔍 **CONDITIONAL CHECK - YOU MUST EVALUATE THIS EXACTLY**

   **Step 0.1: Check if `{{Change_name}}` is provided:**
   
   **Condition to check:** Is `{{Change_name}}` empty, not provided, or appears as a placeholder (like "{{Change_name}}")?

   **IF `{{Change_name}}` is provided (not empty/placeholder):**
   - **YOU MUST output:** `✓ Step 0.1 complete - Change name provided: {{Change_name}}`
   - **YOU MUST proceed to Step 0.2** to verify it exists

   **ELSE IF `{{Change_name}}` is empty/placeholder:**
   - **YOU MUST attempt to infer** from available sources:
     - Current git branch name (extract feature branch pattern, e.g., `feature/sidebar-refactor` → `sidebar-refactor`)
     - OpenSpec changes directory (`openspec/changes/*/`)
     - Run `openspec list` to see recent changes

   **IF inference succeeds (change name found):**
   - **YOU MUST output:** `✓ Step 0.1 complete - Change name inferred: [inferred_name]`
   - Store as `{{Change_name}}`
   - **YOU MUST proceed to Step 0.2** to verify it exists

   **IF inference fails (change name cannot be determined):**

   🛑 **MANDATORY STOP - YOU MUST NOT PROCEED WITHOUT INPUT**

   **YOU MUST:**
   - Display the following message to the user:

     ```
     I could not determine the change name from the current context.

     Please provide the change name for archiving and committing.

     Example: `sidebar-refactor` or `inquiry-02-email`

     What is the change name?
     ```

   - **WAIT for user response in plain text**
   - **YOU MUST NOT proceed until the user provides a valid change name**
   - **YOU MUST end your message/turn after asking for the change name**

2. **Step 0.2: Verify the OpenSpec change exists:**

   - Check if `openspec/changes/{{Change_name}}/` directory exists
   - **IF directory doesn't exist:**
     - Check if the change was already archived (look in `openspec/changes/archive/`)
     - **IF found in archive:** Report that change was already archived
     - **IF not found anywhere:**
       - **YOU MUST output error:** `❌ OpenSpec change not found: {{Change_name}}`
       - **YOU MUST ask user for correct change name again**
       - **YOU MUST NOT proceed**
   - **IF directory exists:**
     - **YOU MUST output:** `✓ Step 0.2 complete - OpenSpec change verified`
     - **YOU MUST proceed to Step 0.3**

3. **Step 0.3: Automatically gather remaining context (run in parallel where possible):**

   **Automatically perform these in parallel or sequence:**

   - **Infer change description:**
     - Read `openspec/changes/{{Change_name}}/proposal.md` or `openspec/changes/{{Change_name}}/spec.md` if it exists.
     - Extract `{{change_desc}}` from the summary/description section.
     - If not found, use a placeholder: "Change description not found in OpenSpec".

   - **Gather state information (run in parallel if possible):**
     - Run `openspec list` and capture output.
     - Run `git status` and capture output.
     - Run `git branch --show-current` to get current branch name.

4. **Step 0.4: Automatically validate task completion (CRITICAL):**

   - Read `openspec/changes/{{Change_name}}/tasks.md` if it exists.
   - Parse all tasks in the file to identify:
     - Tasks marked as complete: `- [x]` or `- [X]`
     - Tasks marked as incomplete: `- [ ]`
   - **If all tasks are marked complete:**
     - Report: "✓ All tasks in tasks.md are marked as complete."
     - Proceed to Section 1.
   - **If any tasks are incomplete:**
     - For each incomplete task:
       1. Read the task description carefully.
       2. Search the codebase and git changes for evidence the task was actually completed.
       3. Check if the task is truly incomplete or just not marked as complete.
       4. Determine if the task can be safely marked as complete based on evidence.
     - **If all incomplete tasks can be marked complete:**
       - Present a summary of tasks that will be marked complete.
       - Ask for confirmation: "I found {{N}} incomplete task(s) that appear to be done. Should I mark them as complete in tasks.md? [y,n]"
       - If **y**: Update tasks.md to mark those tasks as complete, then proceed to Section 1.
       - If **n**: Proceed to Section 1 without changes (user will handle manually).
     - **If any incomplete tasks cannot be marked complete:**
       - **STOP and raise to user:**
         > **⚠️ BLOCKER: Incomplete tasks found**
         >
         > **Change:** `{{Change_name}}`
         >
         > **Incomplete tasks that cannot be marked complete:**
         >
         > - [List each task with description and reason why it cannot be marked complete]
         >
         > **Investigation results:**
         >
         > - [For each task, show what was checked and why it's not complete]
         >
         > **Action required:**
         >
         > Before proceeding with archive, please:
         >
         > 1. Complete the remaining tasks, OR
         > 2. Mark them as complete in `openspec/changes/{{Change_name}}/tasks.md` if they're actually done, OR
         > 3. Remove or defer them if they're no longer needed.
         >
         > **Cannot proceed with archive until all tasks are resolved.**
       - Do **not** proceed to Section 1 until the user confirms tasks are handled.

5. **Step 0.5: Prepare combined context summary:**

   - Change name: `{{Change_name}}`
   - Change description: `{{change_desc}}`
   - Current branch: `{{branch_name}}`
   - OpenSpec changes available: [list from openspec list]
   - Git status summary: [brief summary of tracked/untracked changes]
   - Task completion status: [summary from Step 0.4]

> Note: `{{id}}` comes from the command context. Do **not** ask me for it explicitly.

---

## 1. Combined checkpoint: Confirm change identity and archive command

**Automatically present all gathered information together:**

After automatically collecting context, present:

> **CHECKPOINT 1 of 3: Confirm change identity and archive command**
>
> **Context:**
>
> - Change name: `{{Change_name}}`
> - Change description: `{{change_desc}}`
> - Current branch: `{{branch_name}}`
>
> **OpenSpec Changes:**
>
> ```
> # Output of: openspec list
> [paste the actual output here]
> ```
>
> **Identified work unit to archive:**
>
> - [Show the matched line(s) from `openspec list`]
> - Proposed archive command: `openspec archive <identifier> --yes`
>
> **Git Status:**
>
> ```
> # Output of: git status
> [paste the actual output here]
> ```
>
> **Is this the correct work unit to archive, and should I proceed with the archive command? [y,n]**
>
> - If **n**, specify what needs correction (change name, work unit selection, etc.).
> - If **y**, proceed to run the archive command automatically.

1. Wait for my response. Do **not** proceed until I answer.

2. If I answer **n**, incorporate corrections and repeat the checkpoint.

3. If I answer **y**:

   - **Automatically run the archive command** in the terminal.
   - Include the terminal output verbatim.
   - **Automatically verify** by running `openspec list` again to confirm the change was archived.
   - Show both outputs and confirm the archive was successful.
   - If archive verification fails, stop and ask what to do next.
   - If successful, proceed to Section 2.

---

## 2. Analyze git status and warn about extra files (if any)

**Automatically analyze git status and warn about potentially unrelated files:**

1. **Automatically analyze** the `git status` output already collected (or re-run if needed):

   - Identify all tracked changes and untracked files.
   - **By default, ALL files will be included in the commit** (using `git add -A`).
   - Analyze and flag any files that appear potentially unrelated to this work unit:
     - Untracked files from other work units
     - Unrelated modifications not mentioned in the OpenSpec change
     - Leftover files from other work units
     - Build artifacts, logs, temp files (these should still be included if present)

2. **Prepare warning message (if extra files detected):**

   - If potentially unrelated files are detected, prepare a warning section to include in Section 3 (commit proposal).
   - The warning should list the files and briefly explain why they appear unrelated.
   - **Do NOT block or stop execution** - this is informational only.

3. **Always proceed to Section 3:**

   - Report: "✓ Ready to proceed with commit (all files will be included)."
   - Include any warnings about potentially unrelated files in the Section 3 checkpoint presentation.
   - Proceed directly to Section 3 (commit message).

---

## 3. Propose commit message and execute commit

1. **Automatically generate detailed commit message:**

   - **Summary line format:** `feat: {{id}} {{Change_name}} - {{change_desc}}`
   - **Detailed body format:** Include a comprehensive bulleted list of key features and changes
   - Generate detailed commit message by:
     1. Reading `openspec/changes/{{Change_name}}/proposal.md` or archived proposal to extract the "What Changes" section or detailed feature list
     2. Reviewing `git diff --stat` to understand actual file changes
     3. Extracting key implementation details from tasks.md completed items
     4. Creating a commit message with:
        - First line: Summary with change name and brief description
        - Blank line
        - Detailed bullet list covering:
          - New features/components added
          - Key functionality implemented
          - Technical details (e.g., gems added, database changes, API endpoints)
          - Integration points (e.g., filtering, navigation, links)
          - Performance optimizations (e.g., eager loading, caching)
          - UI/UX improvements
        - Use concise but informative bullet points (one sentence per bullet)
        - Focus on what was added/changed, not implementation details unless critical
   - Commit type patterns: Use appropriate prefix (feat, fix, refactor, chore, etc.)

2. **Present commit proposal with checkpoint:**

   > **CHECKPOINT 2 of 3: Commit message and execution**

   > **Note:** If you approve this commit, it will automatically be pushed to the remote repository. Push approval is tied to commit approval.
   >
   > **⚠️ WARNING: All files will be included in this commit** (using `git add -A`). The following files appear potentially unrelated to this work unit but will be committed:
   >
   > [If Section 2 identified extra files, list them here with brief explanation. If no extra files, omit this warning section.]
   >
   > **Proposed commit message:**
   >
   > ```
   > feat: {{id}} {{Change_name}} - {{change_desc}}
   >
   > [Detailed bullet list of key features and changes]
   > - Feature/change 1
   > - Feature/change 2
   > - Technical detail 1
   > - Integration detail 1
   > ```
   >
   > **Files to be committed:**
   >
   > ```
   > # Output of: git status --short
   > [paste output]
   > ```
   >
   > **Git commands to run:**
   >
   > ```bash
   > git add -A
   > git commit -m "feat: {{id}} {{Change_name}} - {{change_desc}}
   >
   > [Detailed bullet list]"
   > ```
   >
   > **Do you accept this commit message and want me to run these commands? [y,n]**
   >
   > - If **n**, please provide your edited commit message.
   > - If **y**, I'll proceed with the commit.

3. Wait for my response. Do **not** proceed until I answer.

4. If I answer **n**:

   - Use the edited commit message provided.
   - Show the updated commands and ask for confirmation again.
   - Wait for **y** before proceeding.

5. If I answer **y**:

   - Run `git add -A`.
   - Run `git commit -m "<commit-message>"` with the confirmed multi-line commit message.
     - For multi-line commit messages, use multiple `-m` flags or escape newlines appropriately
     - Format: `git commit -m "Summary line" -m "Body line 1" -m "Body line 2" ...` OR use a single `-m` with properly formatted multi-line string
   - Include full terminal output, especially the commit summary.
   - **Automatically verify** by running `git status` and `git log --oneline -1`.
   - Show both outputs and confirm the commit was successful.
   - If commit successful, **automatically proceed to push to remote** (Section 3.5) without additional approval, since commit approval and push are tied together.

---

## 3.5. Push to remote repository (automatic after commit approval)

**Note:** This section is automatically executed after commit approval in Section 3. Since commit approval and push are tied together, no separate approval is required for push.

1. **Automatically determine push command:**

   - Get current branch name: `{{branch_name}}` (already collected in Section 0).
   - Determine remote name (default to `origin` if not specified).
   - Push command: `git push origin {{branch_name}}`

2. **Automatically execute push:**

   - Run `git push origin {{branch_name}}`.
   - Include full terminal output.
   - **Automatically verify** by running `git status` to confirm branch is up to date.
   - Show the verification output and confirm the push was successful.
   - If push fails (e.g., due to authentication or remote issues), report the error and note that manual push may be required.
   - If push successful, proceed to Section 3.6 (PR creation).

---

## 3.6. Create pull request (optional)

**Note:** This section is only reached after a successful push to remote. The branch `{{branch_name}}` is now available on the remote repository.

1. **Automatically determine archived OpenSpec change path:**

   - After archiving, the change is moved to `openspec/changes/archive/YYYY-MM-DD-{{Change_name}}/`.
   - Determine the exact archive path by checking the archive directory or from the archive command output.
   - Store this as `{{archived_change_path}}` for the PR description.

2. **Automatically generate PR description:**

   - Title: `feat: {{id}} {{Change_name}} - {{change_desc}}`
   - Body template:

     ```
     ## Change: {{Change_name}}

     {{change_desc}}

     ## OpenSpec Reference

     This change corresponds to the archived OpenSpec work unit:
     - Path: `{{archived_change_path}}`
     - Proposal: `{{archived_change_path}}/proposal.md`
     ```

   - Base branch: `development`
   - Head branch: `{{branch_name}}`

3. **Present PR creation proposal (requires explicit approval):**

   > **CHECKPOINT 3 of 3: Create pull request**
   >
   > **PR Details:**
   >
   > - **Title:** `feat: {{id}} {{Change_name}} - {{change_desc}}`
   >
   > - **Base branch:** `development`
   >
   > - **Head branch:** `{{branch_name}}`
   >
   > - **Description:**
   >
   >   ```
   >   ## Change: {{Change_name}}
   >
   >   {{change_desc}}
   >
   >   ## OpenSpec Reference
   >
   >   This change corresponds to the archived OpenSpec work unit:
   >   - Path: `{{archived_change_path}}`
   >   - Proposal: `{{archived_change_path}}/proposal.md`
   >   ```
   >
   > **⚠️ Explicit approval required: Would you like me to create this pull request automatically? [y,n]**
   >
   > - If **n**, you can create the PR manually later.
   > - If **y**, I'll create the PR using GitHub CLI.

4. Wait for my response. Do **not** proceed until I answer.

5. If I answer **n**:

   - Note that PR creation was skipped and can be done manually.
   - Proceed to Section 4.

6. If I answer **y**:

   - Construct the PR body content:
     ```
     PR_BODY="## Change: {{Change_name}}
     ```

{{change_desc}}

## OpenSpec Reference

This change corresponds to the archived OpenSpec work unit:

- Path: {{archived_change_path}}
- Proposal: {{archived_change_path}}/proposal.md"
  ```
  - Run: `gh pr create --base development --head {{branch_name}} --title "feat: {{id}} {{Change_name}} - {{change_desc}}" --body "$PR_BODY"`
  - Include full terminal output.
  - **Automatically verify** by running `gh pr view --web` or `gh pr list --head {{branch_name}}` to confirm PR was created.
  - Extract and display the PR URL from the output.
  - If PR creation fails (e.g., due to authentication, network, or existing PR), report the error and note that manual PR creation may be required.
  - If successful, proceed to Section 4.
  ```

---

## 4. Final return payload

In your **final** response for this command (after everything is confirmed and completed), return a concise summary containing:

1. **Archive command**

   - The final `openspec archive` command that was executed (or identifier if provided manually).

2. **Git commit and push commands**

   - The final git commands that were executed, including:
     - The exact commit message used
     - The push command (if executed) or note if push was skipped

3. **Pull request information**

   - PR URL (if created automatically) or note if PR creation was skipped/not available
   - If PR was created, include the PR number and URL
   - If PR creation was skipped, note that manual PR creation is needed

4. **Verification status**

   - ✓ OpenSpec change archived
   - ✓ Commit created successfully
   - ✓ Push to remote completed (or skipped if user declined)
   - ✓ Pull request created (or skipped if user declined)
   - ✓ Working tree clean (or note any expected residual changes)

5. **Next steps checklist**

   If PR was created automatically:

   - Verify CI checks pass on the PR
   - Request review if needed
   - Merge into `development` when ready

   If PR was not created automatically:

   1. Push branch if not already pushed: `git push origin <branch-name>`
   2. Create PR from `<branch-name>` into `development`
   3. In the PR description, include:
      - The Change name `{{Change_name}}`
      - A brief summary based on `{{change_desc}}`
      - A link or reference to the archived OpenSpec work unit at `{{archived_change_path}}`
   4. Verify CI checks pass
   5. Request review if needed, then merge into `development` when ready

---

## 5. Style and formatting

- Keep responses tight and task-focused.
- Use explicit step numbers and headings so I can visually track progress.
- Use fenced code blocks for all commands.
- **Automatically run safe commands** without asking for approval.
- Only pause for confirmation on:
  - Destructive operations (archive, commit, PR creation)
  - Note: Push is automatically executed after commit approval (commit and push are tied together)
  - When information is ambiguous or unclear
- If potentially unrelated files are detected in `git status`, include them in the commit by default but clearly warn about them in the commit checkpoint.
- Present multiple pieces of information together in combined checkpoints to reduce back-and-forth.

---

## Optimizations applied

This optimized version:

- ✅ **Reduces checkpoints to 3** (archive confirmation, commit approval, PR creation - automatically includes all files with warning)
- ✅ **Automates safe command execution** (openspec list, git status run automatically)
- ✅ **Combines information gathering** (presents context, openspec, and git status together)
- ✅ **Auto-verifies operations** (automatically checks archive completion, commit success, push success, and PR creation)
- ✅ **Parallel command execution** where safe (openspec list and git status can run together)
- ✅ **Streamlines confirmations** (only asks for approval on destructive operations: archive, commit, and PR creation - includes all files by default with warnings)
- ✅ **Automates push** (automatically pushes to remote after commit approval - commit and push are tied together)
- ✅ **PR creation requires explicit approval** (PR creation still requires separate user confirmation)
- ✅ **Infers context automatically** (change name, description from OpenSpec when possible)
- ✅ **Validates task completion** (automatically checks all tasks in tasks.md are complete before archiving)

---

**SOP 80 complete.**
