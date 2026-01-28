---
name: 'SOP 20: start-work-unit'
description: 'Start new change: name it, create feature branch, prepare OpenSpec'
---

# SOP 20 – start-work-unit

**Command name:** `SOP 20: start-work-unit`

**Goal:** Start a new change cleanly: name it, create a feature branch, and prepare an OpenSpec proposal.

**Inputs:**

- Change name: `{{change_name}}`
- Brief description of the change: `{{change_desc}}`

---

## Prompt

You are an assistant helping me start a new, tightly scoped change in a Python/Flask project using OpenSpec.

Your job is to:

- Collect the change metadata interactively.
- Ensure git state is correct and the feature branch is created.
- Help define a one-line Definition of Done (DoD).
- Prepare a ready-to-paste `/openspec/proposal` message.
- Run all necessary commands yourself, and checkpoint with me at critical steps.

---

## Step 0 – Collect inputs before doing anything else

**IMPORTANT: DO NOT PROCEED without these inputs.**

Your **first response after this command is invoked** must do **only** the following:

1. **Check if inputs are provided:**

   🔍 **CONDITIONAL CHECK - YOU MUST EVALUATE THIS EXACTLY**

   **Condition to check:** Are `{{change_name}}` and `{{change_desc}}` empty, not provided, or appear as placeholders (like "{{change_name}}" or "{{change_desc}}")?

   **IF either input is empty/placeholder:**

   🛑 **MANDATORY STOP - YOU MUST NOT PROCEED WITHOUT INPUTS**

   **YOU MUST:**
   - Display the following message to the user:

     ```
     Please provide the following information to start your work unit:

     - **Change name** (e.g. `settings-controller-endpoint`)
     - **Brief description of the change** (1–3 sentences)

     Example:
     - Change name: `inquiry-email-notifications`
     - Description: "Add email notifications when inquiry forms are submitted, including admin alerts and user confirmation emails."

     What is your change name and description?
     ```

   - **WAIT for user response in plain text**
   - **YOU MUST NOT proceed until the user provides both values**
   - **YOU MUST end your message/turn after asking for the inputs**

   **ELSE IF both `{{change_name}}` and `{{change_desc}}` are provided:**

   - **YOU MUST output:** `✓ Step 0 complete - Inputs received`
   - Reply with a single confirmation line, for example:

     > Context: `settings-controller-endpoint` – "Add filtering to settings index action"

   - **YOU MUST proceed to Step 1**

2. **After user provides inputs:**
   - Store the provided values as `{{change_name}}` and `{{change_desc}}`
   - Echo them back in a confirmation line
   - **YOU MUST proceed to Step 1**

Do **not** assume or invent these values.

---

## Step 1 – Lock in context

Once I provide the inputs (or they are pre-filled):

1. Echo them back in a short summary, for example:

   > Change: `{{change_name}}` – "{{change_desc}}"

2. **Conditional confirmation**: Only ask for confirmation if the inputs seem ambiguous, incomplete, or unclear. If the inputs are clear and specific, proceed directly to Step 2.

   - If confirmation is needed: `Is this summary correct? [y,n]`
   - If inputs are clear: Proceed to Step 2 with a brief acknowledgment.

---

## Step 2 – Verify git state

Quickly verify git state (assume `SOP 10: preflight` has already been run):

1. Run the following commands automatically using the terminal and show the output:

   - `git branch --show-current`
   - `git status`

2. From those outputs, verify:

   - That we are on `development` branch (or can switch to it).
   - The working tree is clean or has only expected changes.

3. If the repo is not in a good state for branching (dirty tree, wrong branch, conflicts):

   - Instruct me to run `SOP 10: preflight` first.
   - Stop this command until preflight has been completed and confirmed.

4. If the repo is in a good state, proceed directly to Step 3 without additional confirmation.

---

## Step 3 – Derive the feature branch name

1. From `{{change_name}}`, automatically derive a kebab-case identifier by:

   - Lowercasing the string.
   - Converting spaces/underscores to `-`.
   - Removing problematic characters.

2. Construct the branch name as:

   - `feature/{{change_name-kebab}}`

3. Present the derived branch name and proceed with it, for example:

   > Using branch name: `feature/{{change_name-kebab}}`

4. Only if the user requests a different branch name, ask what name to use instead and adopt that value. Otherwise, proceed to Step 4.

---

## Step 4 – CHECKPOINT 1 of 2: Create the branch (run commands)

At this checkpoint, you **must run** the git commands yourself using the terminal. This step is **automated** if we're on the `development` branch; otherwise, it requires confirmation.

1. **Check current branch** by running `git branch --show-current` to verify we're on `development`.

2. **If on `development` branch:**

   - Automatically proceed with creating the feature branch.
   - Summarise what you are about to do, for example:

     > Creating feature branch from `development`:
     >
     > - `git checkout development`
     > - `git pull --rebase`
     > - `git checkout -b feature/{{change_name-kebab}}`

   - Use the terminal to run the commands **one by one**:

     - `git checkout development`
     - `git pull --rebase`
     - `git checkout -b feature/{{change_name-kebab}}`

3. **If NOT on `development` branch:**

   - Stop and summarise what you are about to do, for example:

     > I will create the feature branch from `development` by running:
     >
     > - `git checkout development`
     > - `git pull --rebase`
     > - `git checkout -b feature/{{change_name-kebab}}`
     >   Then I will verify with `git branch --show-current` and `git status`.
     >
     > **Note:** Currently on `[current-branch]`, not `development`. Proceed? [y,n]

   - **Wait for explicit "y"** before running any commands.

   - If I answer **y**, use the terminal to run the commands **one by one**:

     - `git checkout development`
     - `git pull --rebase`
     - `git checkout -b feature/{{change_name-kebab}}`

   - If I answer **n** or if there are concerns:

     - Instruct me to run `SOP 10: preflight` first to resolve git state issues.
     - Stop this command until preflight has been completed and confirmed.

4. After branch creation, run:

   - `git branch --show-current`
   - `git status`

5. Summarise the outputs:

   - Confirm the current branch (should be `feature/{{change_name-kebab}}` or whatever final name we chose).
   - Confirm whether the working tree is clean or list any modified/unstaged files.

6. If any command fails (e.g. branch already exists, merge conflicts, or other git errors):

   - Stop and show me the error.
   - Ask how I want to resolve it (e.g. use an existing branch, choose a different name, or fix conflicts).
   - Do **not** attempt risky auto-fixes.

7. Once the branch is successfully created and verified, explicitly mark this checkpoint, for example:

   > CHECKPOINT 1 of 2 ✅ – Branch `feature/{{change_name-kebab}}` created and verified.

---

## Step 5 – Help define a one-line Definition of Done (DoD)

Using `{{change_desc}}` and any additional context I've given:

1. Propose a clear, one-line Definition of Done, for example:

   > Proposed DoD: "Users can filter the settings index by status and date range via the UI and API."

2. **Evaluate the proposed DoD for clarity and scope:**

   - If the DoD seems vague, too broad, or lacks specificity, suggest refinement before asking for acceptance.
   - A good DoD should be: specific, measurable, testable, and tightly scoped to the change description.
   - If refinement is needed, propose a more specific version and explain why.

3. Ask me: `Do you accept this DoD? [y,n]` (If **n**, I will want to provide edits)

4. If I answer **n** (want changes):

   - Incorporate my edits.
   - Repeat back the **final** DoD exactly as agreed, labelled clearly as:

     - `Definition of Done: "..."`

5. Do not proceed until the DoD is explicitly agreed.

---

## Step 6 – CHECKPOINT 2 of 2: Prepare OpenSpec proposal message

Now prepare a ready-to-paste `/openspec/proposal` message.

1. Draft the message in a fenced code block, using this shape as a guide:

   ```text
   /openspec/proposal
   Change name: {{change_name}}
   Branch: feature/{{change_name-kebab}}
   Definition of Done: "<final agreed DoD>"

   Context:
   - Stack: Python/Flask, YAML config, vanilla JS/CSS.
   - This change is about: {{change_desc}}
   - Relevant areas (if known): lib modules, templates, static assets, API endpoints, or any other key areas you've identified.

    Phased Approach Required:
    1. PHASE 1 ONLY: Create OpenSpec proposal files (proposal.md, tasks.md, specs/landing-page/spec.md) and validate
    2. STOP after Phase 1 for review/approval checkpoint
    3. PHASE 2 (after approval): Implement code changes (controller, view, layout, routes, tests)


   Instructions for the planning agent:
   - Restate your understanding of the change in your own words.
   - Ask any clarifying questions before proposing a plan.
   - Propose a small, stepwise implementation plan that:
     - Touches only the necessary files.
     - Minimises risk and scope.
     - Calls out where tests should be added or updated.
   - Ensure that nothing has been missed and that assumptions are minimised.
   - Review your work before presenting it back to check that your work is correct.
   - Re-iterate that scope and feature detail are critical - stay tightly scoped to the Definition of Done.
   - Stop after presenting the plan and questions.
   ```

2. Make sure the message:

   - Includes the exact `{{change_name}}`.
   - Includes the **final agreed** DoD sentence.
   - Includes the derived branch name.

3. Present this as a clearly separated block so I can copy/paste it into a new planning tab.

4. Ask me explicitly:

   > Are you happy to use this `/openspec/proposal` message as-is? [y,n] (If **n**, I will provide edits)

5. If I answer **n** (request edits), refine the message and show the updated version until I confirm it is final with **y**.

6. Once confirmed, mark this checkpoint, for example:

   > CHECKPOINT 2 of 2 ✅ – OpenSpec proposal prepared and approved.

---

## Step 7 – Wrap-up checklist

Finish by showing a comprehensive checklist so I can visually verify everything is ready:

- [ ] Change name confirmed: `{{change_name}}`
- [ ] Feature branch created and verified: `feature/{{change_name-kebab}}`
- [ ] Definition of Done agreed and documented
- [ ] OpenSpec proposal message prepared and approved
- [ ] Proposal includes all required elements (change name, branch, DoD, context, phased approach, instructions)
- [ ] Git working tree is clean on the feature branch

End with a final reminder of what to do next:

> **Next steps:**
>
> 1. Copy the `/openspec/proposal` message into a new planning agent and let the planning agent generate the implementation plan.
> 2. When satisfied with the plan and the change documents (spec, design, tasks, etc.), run **SOP 30: prebuild-snapshot** to commit the plan to git before build. This provides a rollback checkpoint.

---

**SOP 20 complete.**
