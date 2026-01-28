---
name: commit-push
description: Fast commit and push with smart auto-commit for low-risk changes.
category: Git
tags: [git, commit, push]
---

# /commit-push Command

**Goal:** Quick, friction-free git commit and push. Auto-commits low-risk changes (docs, style, chore) without approval. Single approval checkpoint for meaningful changes (feat, fix, refactor).

---

## Automation Principles

- **Auto-commit low-risk changes** (`docs:`, `style:`, `chore:`, formatting-only) without approval
- **Single approval checkpoint** for meaningful changes (`feat:`, `fix:`, `refactor:`)
- **Push automatically** after commit (no separate push approval)
- **Use AI to analyze actual code changes** from `git diff`, not just file paths
- **Minimize checkpoints** - gather all info upfront, one approval if needed

---

## 0. Pre-flight Checks (Automatic)

Run these automatically in parallel:

1. **Check branch:** `git branch --show-current`
   - IF detached HEAD: STOP - "Not on a branch. Please checkout a branch first."

2. **Check changes:** `git status --short`
   - IF no changes: STOP - "No changes to commit. Working tree clean."

3. **Check remote:** `git remote -v`
   - IF no remote: Warn but continue (skip push later)

---

## 1. Analyze Changes and Determine Auto-Commit Eligibility

**Automatically gather context and analyze:**

1. Run in parallel:
   - `git status --short`
   - `git diff --stat`
   - `git diff` (actual content) - Analyze for commit type and description

2. **Analyze actual code changes** (not just file paths):
   - What actually changed in the code
   - Commit type based on code changes
   - Meaningful description from actual code modifications

**Commit Type Detection:**

- **`feat:`** - New functionality, features, significant additions
- **`fix:`** - Bug fixes, error corrections
- **`refactor:`** - Code restructuring without behavior change
- **`docs:`** - Documentation changes only
- **`style:`** - Formatting, whitespace, non-functional
- **`chore:`** - Build config, dependencies, tooling
- **`test:`** - Test additions/modifications
- **`perf:`** - Performance improvements

**Generate commit message:**
- Extract what the code actually does/changes
- Use concise, action-oriented language
- Include body if 3+ files changed OR 50+ lines changed OR multiple distinct changes
- Use bullet points for key changes (one sentence each)

**Determine auto-commit eligibility:**

AUTO-COMMIT (skip approval) if:
- Commit type is `docs:`, `style:`, or `chore:` AND not on protected branch
- Commit type is `refactor:` AND only affecting low-risk files (commands, tooling, docs)
- Formatting-only changes
- AND not on protected branch (`main`, `master`, `production`, `development`)

REQUIRE APPROVAL if:
- Commit type is `feat:`, `fix:`, `perf:`
- Commit type is `refactor:` affecting application code (`app/`, `lib/`)
- On protected branch
- High-impact changes (database migrations, API changes)

---

## 2. Auto-Commit Path (No Approval)

If auto-commit eligible:

1. Stage and commit automatically:
   ```bash
   git add -A
   git commit -m "type: description"
   ```

2. Push automatically (skip if no remote):
   ```bash
   git push origin branch_name
   ```

3. Verify and report:
   - Show commit hash with `git log --oneline -1`
   - Confirm clean working tree with `git status`

4. Final summary:
   - Auto-committed: `type: description` (hash)
   - Pushed to origin/branch_name
   - Working tree clean

**END - No user interaction needed**

---

## 3. Approval Path (Single Checkpoint)

If approval required, use AskUserQuestion with:

- Branch name
- Changes summary (git status)
- Diff stats
- Proposed commit message
- Options: Accept / Edit message

**On accept:** Stage, commit, push automatically, show summary

**On edit:** Ask for new message, then proceed

---

## 4. Final Summary

Concise summary:
- Commit: `type: description` (hash)
- Push: Pushed to origin/branch_name (or skipped/failed)
- Status: Working tree clean

---

## Error Handling

1. **Detached HEAD:** Stop, suggest checking out branch
2. **No changes:** Stop, report clean tree
3. **No remote:** Continue, skip push
4. **Push fails:** Report error, suggest manual push
5. **Message generation fails:** Use fallback `chore: update files`, allow edit

---

## Co-Author

Always include co-author in commits:
```
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```
