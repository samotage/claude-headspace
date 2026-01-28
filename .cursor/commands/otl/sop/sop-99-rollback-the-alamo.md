---
name: 'SOP 99: rollback-the-alamo'
description: 'Safely roll back feature branch to last good commit'
---

# SOP 99: rollback-the-alamo

**Goal:** Safely roll back a feature branch to the last good commit when a change has gone wrong.

**Command name:** `SOP 99: rollback-the-alamo`

**Prompt:**

You help me safely roll back a feature branch to the last good commit when a change has gone FUBAR.

---

## Step 1: Collect inputs before doing anything else

Your first response after this command is run must only ask me for the required input:

> Please provide the change name for this rollback, for example `settings-controller-endpoint`.

Specifically ask for:

- **Change name** (`{{change_name}}`)

Then wait for my reply.

Once I provide the change name:

1. Try to infer `{{change_desc}}` from the OpenSpec change with the same name:

   - Check if `openspec/changes/{{change_name}}/proposal.md` or `openspec/changes/{{change_name}}/spec.md` exists.
   - If found, read it and extract a one line description of the change.
   - If not found, set `{{change_desc}}` to `Change description not found in OpenSpec`.

2. Reply with a single short context line, for example:

> Context: `settings-controller-endpoint` - "Add filtering to settings index action"

After that, continue with the rest of the steps below.

---

## Step 2: CHECKPOINT 1 - Inspect recent history

**Automatically run these commands** using the terminal and display the output:

1. Run `git log --oneline -n 10` to show recent commit history.
2. Run `git status` to show current working tree state.

Display both outputs in fenced code blocks with clear labels, then proceed directly to Step 3.

**You must run these commands yourself using the terminal tools. Do not ask the user to run them or paste output.**

---

## Step 3: Identify candidate last good commit

Using the `git log` output and any OpenSpec context:

1. Help me identify a candidate last good commit:

   - Prefer the pre build spec snapshot commit for this change if it exists.
   - Otherwise use the last commit where the feature was known good and tests passed.

2. Clearly explain why you chose this commit and what will happen if we reset to it.

---

## Step 4: Explain destructive effects

Before suggesting any destructive commands:

1. Explain that `git reset --hard <hash>` discards all uncommitted changes in the working tree.
2. Explain that `git clean -fd` deletes untracked files and directories.
3. Confirm that I really want to proceed with a hard reset at the chosen commit.

If I do not explicitly confirm, ask what I would like to do instead and pause.

---

## Step 5: CHECKPOINT 2 - Rollback commands

Once I explicitly confirm:

1. Output the exact rollback commands in order, for example:

```bash
git reset --hard <hash>
git clean -fd
```

2. Remind me again that this operation cannot be undone with normal git commands.
3. Ask me to run the commands and then paste a fresh:

```bash
git status
git log --oneline -n 5
```

Wait for my reply before proceeding.

---

## Step 6: Verify rollback state

Using the new `git status` and `git log`:

1. Verify that:

   - The branch points at the expected last good commit.
   - The working tree is clean. There should be no modified or untracked files unless we intentionally kept them.

2. If anything looks wrong, explain the mismatch and propose follow up commands or safety checks. Do not suggest new destructive commands without another explicit confirmation.

---

## Step 7: Summarise and suggest next actions

Finish with a concise summary that covers:

- The commit hash and subject that we reset to.
- What kinds of changes were discarded by the rollback.
- Any recommended next steps, for example:

  - Re-run `SOP 20: start-work-unit` for a new attempt at this change with a tighter spec.
  - Re-run tests or smoke checks to confirm the system is behaving as expected.

Keep the final summary short and practical so I can see at a glance what just happened and what to do next.

---

**SOP 99 complete.**
