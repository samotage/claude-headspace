---
name: 'SOP 60: review-current-diff'
description: 'Summarise current diff changes and spot scope creep'
---

# SOP 60 – review-current-diff

**Command name:** `SOP 60: review-current-diff`

**Goal:** Summarise what actually changed in the current diff and spot scope creep relative to the intended change.

---

## Prompt

You analyse the current git diff for a feature branch and flag scope creep.

You are running inside Claude Code on a Python/Flask project.

Whenever shell commands are needed, you will **run them yourself** in the integrated terminal where possible. Only if command execution fails or is unavailable should you ask me to run a command and paste the output.

Be strict, structured, and explicit. Use clear **CHECKPOINT** stages and always pause for confirmation before moving to the next checkpoint.

---

## Step 0: Collect inputs before doing anything else

**IMPORTANT: DO NOT PROCEED without this input.**

Your **first response** after this prompt must only do the following:

1. **Check if change name is provided:**

   🔍 **CONDITIONAL CHECK - YOU MUST EVALUATE THIS EXACTLY**

   **Condition to check:** Is `{{change_name}}` empty, not provided, or appears as a placeholder (like "{{change_name}}")?

   **IF `{{change_name}}` is empty/placeholder:**

   🛑 **MANDATORY STOP - YOU MUST NOT PROCEED WITHOUT INPUT**

   **YOU MUST:**
   - Display the following message to the user:

     ```
     Please provide the change name to review the current diff.

     Example: `settings-controller-endpoint` or `inquiry-02-email`

     What is the change name?
     ```

   - **WAIT for user response in plain text**
   - **YOU MUST NOT proceed until the user provides a valid change name**
   - **YOU MUST end your message/turn after asking for the change name**

   **ELSE IF `{{change_name}}` is provided:**

   - **YOU MUST output:** `✓ Step 0.1 complete - Change name received: {{change_name}}`
   - **YOU MUST proceed to Step 0.2**

2. **Infer context and confirm:**

   - Store the provided value as `{{change_name}}`
   - Infer `{{change_desc}}` from the summary description for the current OpenSpec change with the same `{{change_name}}`
   - Echo the values back in a single context line, for example:
     > Context: `settings-controller-endpoint` – "Add filtering to settings index action"

3. **Confirm context:** Ask me to confirm: `Is this context correct? [y,n]`

4. If I answer **n**, ask me to provide corrections and update the context, then repeat step 3.

5. If I answer **y**, proceed to CHECKPOINT 1 of 3.

---

## Step 1: CHECKPOINT 1 of 3 – Inspect git status and diff

Your goal here is to get a complete view of the current working tree and diff.

1. Run the following commands (prefer to run them directly in the terminal):

   - `git status`
   - `git diff`

2. If you cannot run commands directly, ask me to run them and paste the outputs.

3. Once you have both outputs, summarise in **3–5 bullet points**:

   - Overall branch / status situation (e.g. clean/dirty, ahead/behind remote).
   - Whether there are untracked files.
   - Whether there are staged vs unstaged changes.

4. End this checkpoint by explicitly asking:

   > CHECKPOINT 1 of 3 complete. Proceed to grouping and summarising the changes? [y,n]

   Wait for my response. Do **not** proceed until I answer.

5. If I answer **n**, stop and ask what you should do instead.

6. If I answer **y**, proceed to Step 2.

---

## Step 2: Group changed files by area

Using the `git diff` output (and `git status` if needed), build a grouped view of the changed files.

1. Group changed files into the following categories:

   - `lib/` (Python modules)
   - `static/js/` (JavaScript files)
   - `static/css/` (Stylesheets)
   - `templates/` (HTML templates)
   - `bin/` (Scripts and CLI tools)
   - `config` (including `config.yaml`, `config.yaml.example`)
   - `test_*.py` / `*_test.py` (pytest test files)
   - `other` (everything else: docs, openspec, etc.)

2. For each non-empty group:

   - List the files in that group as a short bullet list.
   - Add a **1–2 line plain English summary** of what changed in that group based on the diff (e.g. "Added filter params to index and adjusted strong params", "Introduced new mailer and updated delivery options", etc.).

3. Present this as a structured section, for example:

   ```text
   ### Changes by area

   **lib/**
   - lib/sessions.py

   Summary: Added state transition detection for OpenRouter API optimization.

   **templates/**
   - templates/index.html

   Summary: Updated dashboard layout to show tmux session status.
   ```

4. After presenting the grouped summary, pause for a checkpoint:

   > CHECKPOINT 2 of 3 complete. Does this grouped summary match your mental model of the change? [y,n] (If **n**, please provide corrections)

   Wait for my response. Do **not** proceed until I answer.

5. If I answer **n**, incorporate my corrections and repeat the grouped summary, then ask again for confirmation.

6. If I answer **y**, proceed to scope comparison (Step 3).

---

## Step 3: Compare against intended scope and detect scope creep

Now compare the actual changes against `{{change_name}}` and `{{change_desc}}`.

1. Using the grouped summary and the original intent, assess whether each group is:

   - **Core to the described scope**.
   - **Related but optional / nice-to-have**.
   - **Likely scope creep / unrelated**.

2. Explicitly flag risky change types:

   - Deletions or large renames (entire files removed or moved, big sections deleted).
   - `requirements.txt` or other dependency changes.
   - Anything in `config.yaml` that changes global behaviour.
   - Changes to `monitor.py` (main application entry point).

3. Produce a concise report:

   - **Scope alignment** section:

     - Bullet list of groups/files that align well with `{{change_desc}}`.
     - Bullet list of groups/files that are _questionable_ or _unrelated_ to `{{change_name}}`.

   - **Risky changes** section:

     - Bullet list of any risky changes found (with file paths and a short explanation).

4. End this step with a clear overall assessment:

   - Either:

     - `Overall: Looks consistent with the described scope.`

   - Or:

     - `Overall: Scope creep detected – changes extend beyond the described scope.`

5. Mark the end of this phase as another checkpoint:

   > CHECKPOINT 3 of 3 complete. Do you want help deciding what to do about any scope creep or risky changes? [y,n]

   Wait for my response. Do **not** proceed until I answer.

6. If I answer **n**, stop here.

7. If I answer **y**, proceed to Step 4 to suggest next actions.

---

## Step 4: Suggest next actions when scope creep or risk is detected

If there is **no** scope creep and risks are minimal:

1. Say clearly:

   - `Recommendation: Looks consistent with the described scope. You can proceed to testing and wrap-up.`

2. Optionally suggest follow-up commands or SOPs (e.g. targeted tests, pre-commit checks).

If **scope creep or significant risk** is detected:

1. Propose concrete options, tailored to what you saw:

   - **Option A – Reset / rollback**:

     - Suggest manual git operations (e.g., `git reset`, `git restore`, or `git checkout`) to rollback if the diff shows messy or clearly off-track changes. Alternatively, if working from a clean branch, suggest starting over with a fresh branch.

   - **Option B – Split the work**:

     - Identify specific files or groups that could be split into a separate change/branch.
     - Suggest a possible new change name for the split work.

   - **Option C – Refine the spec and continue**:

     - If the changes are valid but broader than described, suggest updating the spec / `{{change_desc}}` so that the documentation matches reality.

2. Present these options as a short numbered list, with 1–2 sentences per option.

3. Finish with a direct question:

   > Which option would you like to take (A/B/C), or should we iterate on the diff further?

Always keep your answers concise, structured, and tightly focused on how the current diff does or does not align with the intended scope described by `{{change_name}}` and `{{change_desc}}`.

---

**SOP 60 complete.**
