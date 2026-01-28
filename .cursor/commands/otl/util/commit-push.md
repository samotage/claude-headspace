---
name: commit-push
description: Fast commit and push. Always auto-commits and pushes; no approval checkpoint.
category: Git
tags: [git, commit, push]
---

# /commit-push Command

**Goal:** Quick, friction-free git commit and push. Always stage, commit, and push in one go. No approval step—if you need to undo, use `git revert` or `git reset`.

---

## Automation Principles

- **Always auto-commit and push** — no approval checkpoint, no "Accept / Edit message"
- **Use AI to analyze actual code changes** from `git diff`, not just file paths
- **Generate a good commit message** from the diff; include co-author

---

## 0. Pre-flight Checks (Automatic)

Run in parallel:

1. **Check branch:** `git branch --show-current`
   - IF detached HEAD: STOP — "Not on a branch. Please checkout a branch first."

2. **Check changes:** `git status --short`
   - IF no changes: STOP — "No changes to commit. Working tree clean."

3. **Check remote:** `git remote -v`
   - IF no remote: Warn but continue (skip push later)

---

## 1. Analyze Changes and Generate Commit Message

1. Run in parallel: `git status --short`, `git diff --stat`, `git diff` (full content).

2. **Analyze the diff** (not just paths):
   - What actually changed
   - Commit type from the changes
   - Short, action-oriented description

**Commit types:** `feat:`, `fix:`, `refactor:`, `docs:`, `style:`, `chore:`, `test:`, `perf:`

**Message format:**
- Subject: `type: description` (concise)
- Body (if 3+ files OR 50+ lines OR multiple distinct changes): bullet points for key changes
- Always append co-author (see below)

**Fallback:** If message generation fails, use `chore: update files` and proceed.

---

## 2. Commit and Push

1. Stage and commit:
   ```bash
   git add -A
   git commit -m "type: description

   - bullet 1
   - bullet 2

   Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>"
   ```
   (Omit body bullets when not needed; always include co-author.)

2. Push (skip if no remote):
   ```bash
   git push origin $(git branch --show-current)
   ```

3. Verify: `git log --oneline -1`, `git status`

4. **Final summary:** Commit hash, push result, working tree clean.

---

## 3. Error Handling

1. **Detached HEAD:** Stop, suggest checking out a branch.
2. **No changes:** Stop, report clean tree.
3. **No remote:** Commit only, skip push, say so in summary.
4. **Push fails:** Report error, suggest `git push` manually.
5. **Message generation fails:** Use `chore: update files` and continue.

---

## Co-Author

Every commit must include:
```
Co-Authored-By: Claude Opus 4.5 <noreply@anthropic.com>
```
