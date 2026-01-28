---
name: commit-pr-to-main
description: Commit changes and create a PR to main while keeping branch-specific files separate.
category: Git
tags: [git, commit, pr, main]
---

# /commit-pr-to-main Command

**Goal:** Commit current changes and create a PR to merge into main, while excluding branch-specific files that should stay only on the current feature branch.

---

## Overview

This command handles the common workflow of:
1. Working on a feature branch with branch-specific files (e.g., design docs, feature outlines)
2. Making improvements that should go to main (e.g., bug fixes, enhancements)
3. Creating a clean PR with only the main-worthy changes
4. Keeping all changes on the current branch

---

## 0. Pre-flight Checks (Automatic)

Run in parallel:

1. **Check branch:** `git branch --show-current`
   - IF on `main`: STOP - "Already on main. This command is for feature branches."
   - Store current branch name for later

2. **Check for changes:** `git status --short`
   - IF no changes (staged or unstaged): STOP - "No changes to commit."

3. **Check remote:** `git remote -v`
   - IF no remote: STOP - "No remote configured. Cannot create PR."

4. **Check main exists:** `git branch -a | grep -E '(^|\s)main$|origin/main'`
   - IF no main branch: Check for `master` and use that instead

---

## 1. Analyze and Categorize Changes

**Gather change information:**

```bash
git status --short
git diff --stat
git diff --name-only
git diff --cached --name-only
```

**Identify branch-specific files** by checking:

1. Files matching patterns in `.claude/branch-local-patterns` (if exists):
   ```
   # Example .claude/branch-local-patterns
   docs/voice-bridge*
   **/FEATURE_OUTLINE.md
   .claude/rules/*-branch-*
   ```

2. Common branch-specific patterns (auto-detected):
   - Files containing the branch name (e.g., `voice-bridge` files on `voice-bridge` branch)
   - Files in `docs/` that match the branch name pattern
   - Files named `*OUTLINE*`, `*DESIGN*`, `*SPEC*` that reference the branch feature

3. Files that exist ONLY on this branch (not on main):
   ```bash
   git diff --name-only main...HEAD --diff-filter=A
   ```

**Categorize all changed files into:**
- **Main-worthy:** Bug fixes, enhancements, general improvements
- **Branch-specific:** Feature docs, branch-only configs, design files

---

## 2. User Confirmation (Single Checkpoint)

Present categorized files using AskUserQuestion:

**Show:**
- Current branch name
- List of main-worthy changes (to be included in PR)
- List of branch-specific changes (to be excluded from PR)
- Proposed commit message (AI-generated from diff analysis)

**Options:**
1. **Proceed** - Accept categorization and continue
2. **Modify selection** - Let user specify which files to include/exclude
3. **Cancel** - Abort operation

If user selects "Modify selection":
- List all changed files
- Ask user to specify which to EXCLUDE from PR (comma-separated numbers or patterns)

---

## 3. Commit to Current Branch

Stage and commit ALL changes to the current branch first:

```bash
git add -A
git commit -m "commit_message

Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
```

Store the commit hash for reference.

---

## 4. Create PR Branch and Cherry-Pick

1. **Stash any uncommitted changes** (shouldn't be any after step 3)

2. **Fetch and update main:**
   ```bash
   git fetch origin main
   ```

3. **Create PR branch from main:**
   ```bash
   git checkout main
   git pull origin main
   git checkout -b pr/[descriptive-name]-to-main
   ```

4. **Apply main-worthy changes only:**

   Option A - If all changes are main-worthy:
   ```bash
   git cherry-pick [commit-hash]
   ```

   Option B - If only some files should go to main:
   ```bash
   git checkout [original-branch] -- [file1] [file2] ...
   git commit -m "commit_message

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
   ```

5. **Push PR branch:**
   ```bash
   git push -u origin pr/[descriptive-name]-to-main
   ```

---

## 5. Create Pull Request

Use GitHub CLI to create PR:

```bash
gh pr create \
  --title "type: description" \
  --body "## Summary
- Bullet points of changes

## Test plan
- [ ] Test items

Generated with [Claude Code](https://claude.com/claude-code)"
```

Store the PR URL.

---

## 6. Return to Original Branch

```bash
git checkout [original-branch]
```

Verify:
- Back on original branch
- All changes (including branch-specific) are intact
- Working tree is clean

---

## 7. Final Summary

Report:
- Committed to `[original-branch]`: `[commit-hash]`
- PR created: `[PR-URL]`
- PR branch: `pr/[name]-to-main`
- Current branch: `[original-branch]` (all changes intact)
- Branch-specific files excluded: `[list]`

---

## Error Handling

1. **Merge conflicts during cherry-pick:**
   - Abort cherry-pick
   - Report conflict
   - Suggest manual resolution
   - Return to original branch

2. **PR creation fails:**
   - Report error
   - Provide manual PR link
   - Keep PR branch for manual creation

3. **Push fails:**
   - Check if branch exists remotely
   - Suggest force push if appropriate
   - Report error details

---

## Configuration

**Optional `.claude/branch-local-patterns` file:**

Create this file to define patterns for branch-specific files that should never go to main PRs:

```
# Files matching these patterns are excluded from PRs to main
docs/feature-*
**/DESIGN.md
**/OUTLINE.md
.claude/rules/*-feature-*
```

If this file doesn't exist, the command will auto-detect based on branch name matching and common patterns.

---

## Example Workflow

```
# On voice-bridge branch with:
# - monitor.py changes (enhancement - should go to main)
# - docs/voice-bridge-outline.md (branch-specific - stay on branch)

/commit-pr-to-main

# Claude analyzes and shows:
# Main-worthy: monitor.py
# Branch-specific: docs/voice-bridge-outline.md
# Proposed: "feat: Add input detection patterns"

# User confirms, Claude:
# 1. Commits all to voice-bridge
# 2. Creates pr/input-detection-to-main from main
# 3. Cherry-picks only monitor.py changes
# 4. Creates PR
# 5. Returns to voice-bridge with everything intact
```
