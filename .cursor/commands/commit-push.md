---
name: /commit-push
id: commit-push
category: Git
description: Fast commit and push with smart auto-commit for low-risk changes.
---

# /commit-push Command

**Goal:** Quick, friction-free git commit and push. Auto-commits low-risk changes (docs, style, chore) without approval. Single approval checkpoint for meaningful changes (feat, fix, refactor).

**Command name:** `/commit-push`

---

## Prompt

You are helping me commit and push changes to GitHub quickly and efficiently.

**Automation Principles:**

- **Auto-commit low-risk changes** (`docs:`, `style:`, `chore:`, formatting-only) without approval
- **Single approval checkpoint** for meaningful changes (`feat:`, `fix:`, `refactor:`)
- **Push automatically** after commit (no separate push approval)
- **Use AI to analyze actual code changes** from `git diff`, not just file paths
- **Minimize checkpoints** - gather all info upfront, one approval if needed

---

## 0. Pre-flight Checks (Automatic)

**Run these automatically in parallel:**

1. **Check branch:**

   - `git branch --show-current` → `{{branch_name}}`
   - **IF detached HEAD:** STOP - "❌ Not on a branch. Please checkout a branch first."

2. **Check changes:**

   - `git status --short` → `{{git_status}}`
   - **IF no changes:** STOP - "✓ No changes to commit. Working tree clean."

3. **Check remote:**
   - `git remote -v` → `{{has_remote}}`, `{{remote_name}}` (default: `origin`)
   - **IF no remote:** Warn but continue (skip push later)

**Proceed to Section 1**

---

## 1. Analyze Changes and Determine Auto-Commit Eligibility

**Automatically gather context and analyze:**

1. **Run in parallel:**

   - `git status --short` → `{{git_status}}`
   - `git diff --stat` → `{{git_diff_stat}}`
   - `git diff` (actual content) → Analyze for commit type and description

2. **Use AI to analyze actual code changes:**

   Read the `git diff` output and analyze:

   - **What actually changed** in the code (not just file paths)
   - **Commit type** based on code changes, not just patterns
   - **Meaningful description** from actual code modifications

   **Commit Type Detection (prioritize actual code analysis):**

   - **`feat:`** - New functionality, features, significant additions

     - New methods/functions with business logic
     - New models, services with functionality
     - New routes, endpoints, features

   - **`fix:`** - Bug fixes, error corrections

     - Error handling changes
     - Validation fixes
     - Bug correction logic

   - **`refactor:`** - Code restructuring without behavior change

     - Method extraction, code organization
     - Moving code between files
     - Renaming without functional changes

   - **`docs:`** - Documentation changes only

     - Markdown files, README updates
     - Comments in code
     - Documentation files

   - **`style:`** - Formatting, whitespace, non-functional

     - Only whitespace/formatting changes
     - Linter auto-fixes (Ruff, Black)
     - No logic changes

   - **`chore:`** - Build config, dependencies, tooling

     - requirements.txt, pyproject.toml changes
     - Config files, CI configs
     - Tooling updates

   - **`test:`** - Test additions/modifications

     - Test files, pytest files
     - Fixture updates

   - **`perf:`** - Performance improvements
     - Caching additions
     - Query optimizations
     - Performance fixes

3. **Generate commit message:**

   **Based on actual code analysis:**

   - Extract what the code actually does/changes
   - Use concise, action-oriented language
   - Focus on user-visible impact when possible

   **Body inclusion:**

   - Include body if 3+ files changed OR 50+ lines changed OR multiple distinct changes
   - Use bullet points for key changes (one sentence each)

4. **Determine auto-commit eligibility:**

   **AUTO-COMMIT (skip approval) if ANY of these conditions:**

   - Commit type is `docs:`, `style:`, or `chore:` AND not on protected branch
   - Commit type is `refactor:` AND only affecting low-risk files:
     - Command definitions (`.cursor/commands/**`)
     - Tooling files (scripts, config files)
     - Documentation/workflow files
     - No application code changes (`src/`, `lib/` with business logic)
   - Formatting-only changes (whitespace, style)
   - AND not on protected branch (`main`, `master`, `production`)

   **REQUIRE APPROVAL if:**

   - Commit type is `feat:`, `perf:` OR
   - Commit type is `refactor:` affecting application code (`src/`, `lib/` with logic) OR
   - On protected branch OR
   - High-impact changes detected (database migrations, API changes, breaking changes)

   Store decision as `{{auto_commit}}` (true/false)

---

## 2. Auto-Commit Path (No Approval)

**IF `{{auto_commit}}` is `true`:**

1. **Stage and commit automatically:**
   ```bash
   git add -A
   git commit -m "{{commit_type}}: {{commit_description}}" {{-m flags for body if present}}
   ```
2. **Push automatically:**

   ```bash
   git push {{remote_name}} {{branch_name}}
   ```

   (Skip if `{{has_remote}}` is false)

3. **Verify and report:**
   - `git log --oneline -1` → Show commit hash
   - `git status` → Confirm clean working tree
4. **Final summary:**
   - ✓ Auto-committed: `{{commit_type}}: {{commit_description}}` ({{commit_hash}})
   - ✓ Pushed to `{{remote_name}}/{{branch_name}}` (or skipped if no remote)
   - ✓ Working tree clean

**END - No user interaction needed**

---

## 3. Approval Path (Single Checkpoint)

**IF `{{auto_commit}}` is `false`:**

1. **Present single checkpoint with all info:**

   > **Commit and Push**
   >
   > **Branch:** `{{branch_name}}`
   >
   > **Changes:**
   >
   > ```
   > {{git_status}}
   > ```
   >
   > **Summary:** {{git_diff_stat}}
   >
   > **Commit message:**
   >
   > ```
   > {{commit_type}}: {{commit_description}}
   >
   > {{commit_body}}
   > ```
   >
   > **This will:** Stage all changes, commit, and push to `{{remote_name}}/{{branch_name}}`
   >
   > **Accept? [y,n]**
   >
   > - **y** = Proceed with commit and push
   > - **n** = Edit message (just provide the new message)

2. **Wait for response:**

   **IF `y`:**

   - Stage: `git add -A`
   - Commit: `git commit -m "..."` (with proper -m flags)
   - Push: `git push {{remote_name}} {{branch_name}}` (automatic after commit)
   - Verify: `git log --oneline -1` and `git status`
   - Show summary

   **IF `n`:**

   - Ask: "What should the commit message be?" (can provide full message or just changes)
   - Update `{{commit_type}}`, `{{commit_description}}`, `{{commit_body}}`
   - Show updated message and ask again: "Accept? [y,n]"
   - On `y`, proceed with commit and push

---

## 4. Final Summary (Both Paths)

**Concise summary:**

- ✓ Commit: `{{commit_type}}: {{commit_description}}` ({{commit_hash}})
- ✓ Push: Pushed to `{{remote_name}}/{{branch_name}}` (or skipped/failed)
- ✓ Status: Working tree clean (or note remaining changes)

**If push failed:**

- Report error
- Suggest: `git push {{remote_name}} {{branch_name}}`

---

## Error Handling

1. **Detached HEAD:** Stop, suggest checking out branch
2. **No changes:** Stop, report clean tree
3. **No remote:** Continue, skip push (commit still created)
4. **Push fails:** Report error, suggest manual push (commit was successful)
5. **Message generation fails:** Use fallback `chore: update files`, allow edit

---

## Key Improvements

- ✅ **Auto-commits low-risk changes** - No approval needed for docs/style/chore
- ✅ **Single approval checkpoint** - One [y,n] for meaningful changes
- ✅ **Auto-push** - Push happens automatically after commit (no separate approval)
- ✅ **AI-powered analysis** - Reads actual `git diff` content, not just file paths
- ✅ **Streamlined flow** - All info gathered upfront, minimal back-and-forth
- ✅ **Quick edits** - Easy message override with simple response

---

**/commit-push command complete.**
