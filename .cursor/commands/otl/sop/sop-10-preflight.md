---
name: 'SOP 10: preflight'
description: 'Ensure on development, up to date, and in sane git state'
---

# SOP 10: preflight

**Goal:** Ensure we are on `development`, up to date, and in a sane git state before starting any change.

**Behaviour / prompt skeleton:**

```md
Command name: SOP 10: preflight

Prompt:
You are a preflight assistant for a Python project. Automate all safe operations.

1. **Check current state** (run automatically):

   - `git branch --show-current`
   - `git status`

2. From those outputs, tell me:
   - Whether I am on `development`.
   - Whether the working tree is clean.
3. If I am NOT on `development` or the tree is dirty, propose the safest options:

   - If there are uncommitted changes, offer explicit choices:
     - Commit them (and suggest a commit message), OR
     - Stash them with `git stash -u`, OR
     - Abort and handle them manually.
   - CHECKPOINT 2 of 3 – Branch correction
     - Provide the exact commands (in a fenced block) for the chosen path, for example:
       - `git stash -u`
       - `git checkout development`
     - Show the commands you plan to run and ask for explicit permission: `Shall I run these commands now? [y,n]`
     - If yes, proceed to run these commands automatically using the terminal. If no, stop and await further instructions.

4. **Switch to development** (if needed):

   - If not on `development`, automatically run `git checkout development`
   - Only ask for permission if checkout fails

5. **Update from origin** (run automatically):

   - `git pull --rebase origin development`
   - If conflicts occur, stop and report them

6. **Verify final state** (run automatically):

   - `git branch --show-current`
   - `git status`
   - `git log --oneline -1` (to show latest commit)

7. **Report** (concise):
   - ✅ Branch: `development`
   - ✅ Status: clean and up to date
   - ⚠️ Warnings: [any issues]
   - **Next:** Use `SOP 20: start-work-unit` with {{change_name}} and {{change_desc}}

**Automation rules:**

- Run all commands automatically unless they require user decision
- Only prompt when: stashing fails, checkout fails, or merge conflicts occur
- Use clear, concise output
- Show commands as you run them
```

---

**SOP 10 complete.**
