---
name: 'SOP 30: prebuild-snapshot'
description: 'Automated git safety checkpoint for pre-build spec/docs snapshot'
---

# SOP 30: prebuild-snapshot

**Goal:** Automated git safety checkpoint for a pre-build spec/docs snapshot with minimal manual intervention.

**Command name:** `SOP 30: prebuild-snapshot`

---

**Prompt:**

You are an automated git safety checker ensuring only spec/docs are committed in a pre-build snapshot for a Python/Flask project.

You can run shell and git commands yourself. Automate routine steps; only pause for critical safety decisions.

---

## Step 1 – Auto-detect context and inspect git state

**Your first response** after this command is invoked should immediately:

1. **Auto-detect change name** from the current branch:

   - Run: `git branch --show-current`
   - Extract change name from branch (e.g., `feature/settings-controller-endpoint` → `settings-controller-endpoint`)
   - If branch doesn't match `feature/*` pattern, check for OpenSpec files or ask for clarification
   - Display: `Change: {{change_name}}` (derived from branch: `{{branch_name}}`)

2. **Automatically inspect git state** by running:

   ```bash
   git status --short
   git diff --name-only
   git diff --cached --name-only
   ```

3. **Auto-categorize files** using these patterns:

   **Spec/Docs files (safe to commit):**

   - `openspec/**`
   - `docs/**`
   - `*.md`
   - `*.spec.yml`, `*.spec.yaml`
   - `.claude/commands/**/*.md` (SOP documentation)
   - `.claude/rules/**` (documentation/rules)

   **App code files (must NOT be in this commit):**

   - `lib/**` (except `lib/**/*.md`)
   - `static/**`
   - `templates/**`
   - `bin/**`
   - `*.py` (Python source files)
   - `*.js`, `*.css` (frontend assets)
   - `test_*.py`, `*_test.py` (test files are app code)
   - `requirements.txt`, `*.lock`
   - `config.yaml` (runtime configuration)

4. **Generate a clear status report:**
   - Current branch
   - Change name (auto-detected)
   - List of spec/docs files (grouped by type)
   - List of app code files (if any)
   - Working tree status

---

## Step 2 – Automated safety check and decision

**If any app code files are detected:**

1. Immediately report: `❌ NOT SAFE – app code changes detected`
2. List all app code files clearly
3. **Stop automation** and offer options:

   - Option A: Reset app code changes with `git restore <files>`
   - Option B: Stage only spec/docs files explicitly (skip app files)
   - Option C: Abort this snapshot (user handles app code separately)

4. **Wait for explicit instruction** before proceeding. Do not auto-commit.

**If ONLY spec/docs files are detected:**

1. Confirm: `✅ SAFE TO COMMIT SPEC-ONLY – {{count}} spec/docs files detected`
2. Provide a concise summary: file types and counts (e.g., "2 OpenSpec files, 1 markdown doc")
3. **Proceed to Step 2.5** for OpenSpec planning task validation

---

## Step 2.5 – OpenSpec Planning Task Completion Validation

**Before proceeding with the snapshot, validate that all OpenSpec PLANNING tasks are complete. Only planning tasks (proposal creation, validation, approval) are checked. Implementation, testing, and validation tasks are expected to be incomplete at this stage.**

1. **Check for OpenSpec change directory:**

   - Look for `openspec/changes/{{change_name}}/` directory
   - If directory doesn't exist:
     - Check if change name needs adjustment (e.g., kebab-case conversion, removing prefixes)
     - Try alternative change names (e.g., if branch is `feature/sidebar-menu`, try `sidebar-menu-improvement` if OpenSpec files reference it)
     - List available OpenSpec changes: `ls openspec/changes/` to suggest matches
     - If multiple candidates exist, ask user to confirm which change applies

2. **Read and identify planning tasks in tasks.md:**

   - Read `openspec/changes/{{change_name}}/tasks.md` if it exists
   - Parse task sections and checkboxes in the file
   - **Identify PLANNING tasks only** using these criteria:

     **Planning task sections** (include tasks from these sections):

     - Section headers containing: "Planning", "Phase 1", "Proposal", "OpenSpec Proposal"
     - Section headers matching patterns: `##.*Phase.*1`, `##.*[Pp]lanning`, `##.*[Pp]roposal`

     **Planning task keywords** (include tasks matching these patterns):

     - Tasks mentioning: "Create OpenSpec proposal", "Create proposal files", "proposal.md", "tasks.md"
     - Tasks mentioning: "Validate proposal", "openspec validate"
     - Tasks mentioning: "Review and get approval", "get approval", "approval"
     - Tasks mentioning: "OpenSpec" in context of proposal creation/validation

     **Exclude these sections** (skip tasks from these sections entirely):

     - Sections titled: "Implementation", "Testing", "Validation", "Phase 2", "Phase 3", "Database", "Model", "Controller", "Routes", "View", etc.
     - Any section clearly related to implementation, testing, or validation work

3. **Generate planning task completion report:**

   - Count total planning tasks found
   - Count completed planning tasks (`[x]`)
   - Count incomplete planning tasks (`[ ]`)
   - Calculate completion percentage for planning tasks only
   - Note: Implementation/testing/validation tasks are intentionally ignored

4. **Decision logic:**

   **If tasks.md exists and PLANNING tasks are found:**

   **If planning tasks are incomplete:**

   - Report: `⚠️ INCOMPLETE PLANNING TASKS DETECTED – Cannot proceed with snapshot`
   - Display incomplete planning tasks clearly:
     ```
     Incomplete Planning Tasks ({{incomplete_planning_count}} of {{total_planning_count}}):
     - [ ] Task description here
     - [ ] Another incomplete planning task
     ```
   - **Stop automation** and raise to user:

     ```
     ❌ BLOCKER: OpenSpec proposal has incomplete PLANNING tasks.

     All PLANNING tasks in openspec/changes/{{change_name}}/tasks.md must be marked complete ([x])
     before creating a pre-build snapshot. Implementation, testing, and validation tasks are
     expected to be incomplete at this stage.

     Please:
     1. Review openspec/changes/{{change_name}}/tasks.md
     2. Complete any remaining PLANNING tasks or mark them as complete if already done
     3. Re-run SOP 30 after planning tasks are complete
     ```

   - **Wait for explicit user instruction** before proceeding

   **If all planning tasks are complete:**

   - Report: `✅ ALL PLANNING TASKS COMPLETE – {{completed_planning_count}}/{{total_planning_count}} planning tasks verified`
   - Display summary:

     ```
     Planning Task Completion Status:
     - Total planning tasks: {{total_planning_count}}
     - Completed: {{completed_planning_count}} ✅
     - Incomplete: 0 ✅
     - Completion: 100%

     Note: Implementation/testing/validation tasks are intentionally not checked at this stage.
     ```

   - **Proceed automatically to Step 3**

   **If tasks.md exists but NO planning tasks are found:**

   - Report: `ℹ️ No planning tasks found in tasks.md for {{change_name}}`
   - Display summary:
     ```
     Task File Analysis:
     - tasks.md exists: Yes
     - Planning sections found: 0
     - Planning tasks found: 0
     - Implementation/testing/validation sections found: {{count}} (expected to be incomplete)
     ```
   - Note: `No planning tasks detected. Planning appears to be complete or not tracked in tasks.md. Proceeding with snapshot.`
   - **Proceed automatically to Step 3** (no planning tasks to validate = planning is considered complete)

   **If tasks.md does not exist:**

   - Report: `ℹ️ No tasks.md found for {{change_name}}`
   - Check if this is expected (e.g., documentation-only change, planning completed elsewhere)
   - Ask user: `No tasks.md found. Is this expected? Proceed with snapshot? [y,n]`
   - If 'y': Proceed to Step 3
   - If 'n': Stop and wait for clarification

   **If OpenSpec change directory does not exist:**

   - Report: `ℹ️ No OpenSpec change directory found for {{change_name}}`
   - This may be expected for non-OpenSpec changes
   - **Proceed automatically to Step 3** (no blocker)

5. **Error handling:**
   - **File read errors**: Report error, suggest checking file permissions or path
   - **Malformed tasks.md**: Report parsing issues, show problematic lines
   - **Ambiguous task format**: Default to treating as incomplete if checkbox format unclear
   - **Unclear section boundaries**: If task appears to be in multiple sections, default to including it if it matches planning keywords

**If working tree is clean:**

1. Report: `ℹ️ Working tree is clean – no changes to snapshot`
2. Check if there's already a spec snapshot commit on this branch
3. If snapshot exists, show the last commit: `git log --oneline -1 --grep="pre-build snapshot"`
4. Ask if user wants to proceed anyway or if snapshot is already complete

---

## Step 3 – Automated staging and commit (with single checkpoint)

**If spec-only files are detected:**

1. **Auto-stage all spec/docs files** using explicit file paths:

   ```bash
   git add <file1> <file2> <file3>
   ```

   - Use actual file paths from git status, not patterns
   - Verify staged files with: `git status --short`

2. **Show commit plan** in a concise format:

   ```
   Committing {{count}} spec/docs files for: {{change_name}}

   Files:
   - openspec/proposal.md
   - openspec/specs/landing-page/spec.md
   - ...

   Commit message: "chore(spec): {{change_name}} pre-build snapshot"
   ```

3. **Single checkpoint** – Ask once:

   > `Create spec snapshot commit now? [y,n] (or 'a' for auto-commit without asking)`

4. **If user answers 'y' or 'a':**

   - Run: `git commit -m "chore(spec): {{change_name}} pre-build snapshot"`
   - Show commit output
   - **Automatically proceed to push** (Step 4)

5. **If user answers 'n':**
   - Show what would have been committed
   - Stop and wait for instruction

---

## Step 4 – Automated push and verification

**After successful commit:**

1. **Automatically push** to remote (no separate checkpoint):

   ```bash
   git push -u origin HEAD
   ```

   - Show push output
   - Confirm upstream is set

2. **Automatically verify** working tree:

   ```bash
   git status
   git log --oneline -1
   ```

3. **Generate completion report:**

   ```
   ✅ CHECKPOINT COMPLETE

   Change: {{change_name}}
   Commit: <short-hash> "chore(spec): {{change_name}} pre-build snapshot"
   Branch: {{branch_name}} (pushed to origin)
   Status: Working tree clean

   Pre-build spec/docs snapshot complete. Safe to proceed with implementation.
   ```

**If push fails:**

- Show error details
- Offer to retry or check remote state
- Do not proceed to verification until push succeeds

---

## Step 5 – Optional: Post-snapshot status

After successful completion, optionally run:

```bash
git log --oneline --graph -5
git diff HEAD~1 --stat
```

Show a brief visual confirmation of the snapshot commit in the git history.

---

## Automation rules

- **Auto-detect** change name from branch name (pattern: `feature/<change-name>`)
- **Auto-inspect** git state immediately without asking
- **Auto-categorize** files using explicit patterns
- **Auto-validate** OpenSpec PLANNING task completion before proceeding (implementation/testing/validation tasks are intentionally ignored)
- **Auto-stage** spec/docs files when safe
- **Auto-push** after successful commit
- **Auto-verify** working tree after push
- **Single checkpoint** before committing (user can skip with 'a' for auto-commit)
- **Never auto-commit** if app code is present
- **Never auto-commit** if OpenSpec PLANNING tasks are incomplete (raises blocker to user)
- **Never auto-reset** or modify files without explicit instruction

---

## Error handling

- **Branch detection fails**: Ask for change name manually, suggest format
- **Git commands fail**: Show error, stop automation, wait for resolution
- **Push conflicts**: Show conflict details, suggest `git pull --rebase`, wait
- **File categorization unclear**: Default to unsafe (ask user), show ambiguous files
- **No changes detected**: Report clean state, confirm if user expected changes
- **OpenSpec PLANNING tasks incomplete**: Block snapshot creation, list incomplete planning tasks only, wait for user resolution (implementation/testing/validation tasks are expected to be incomplete)
- **tasks.md read errors**: Report file access issues, suggest checking permissions/path
- **tasks.md parsing errors**: Show malformed lines, suggest format fixes

---

**SOP 30 complete.**
