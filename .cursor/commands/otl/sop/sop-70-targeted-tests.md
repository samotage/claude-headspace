---
name: 'SOP 70: targeted-tests'
description: 'Choose and run most relevant tests for a given change'
---

# SOP 70: targeted-tests

**Command name:** `SOP 70: targeted-tests`

**Prompt:**

You help me choose and run the most relevant tests for a given change in a Python/Flask project.

You have access to Claude Code's workspace and terminal. Whenever these instructions mention running shell commands or reading/writing files, **you must perform those actions yourself** using Claude Code's tools.

- Do **not** ask me to run shell commands or manually open/edit files, except to confirm that a plan or result looks correct.
- After each critical action (collecting context, reading OpenSpec, computing changed files, planning tests, running tests, updating tasks), **checkpoint with me and wait for confirmation** before proceeding.
- **Always update the Testing Status Summary section in `tasks.md` after test runs are complete**, before finishing the command.

---

## Step 0: Get Change Name Input

**IMPORTANT: DO NOT PROCEED without this input.**

1. **Check if change name is provided:**

   🔍 **CONDITIONAL CHECK - YOU MUST EVALUATE THIS EXACTLY**

   **Condition to check:** Is `{{change_name}}` empty, not provided, or appears as a placeholder (like "{{change_name}}")?

   **IF `{{change_name}}` is empty/placeholder:**

   🛑 **MANDATORY STOP - YOU MUST NOT PROCEED WITHOUT INPUT**

   **YOU MUST:**
   - Display the following message to the user:

     ```
     Please provide the change name to run targeted tests.

     Example: `tmux-session-router` or `openrouter-optimization`

     What is the change name?
     ```

   - **WAIT for user response in plain text**
   - **YOU MUST NOT proceed until the user provides a valid change name**
   - **YOU MUST end your message/turn after asking for the change name**

   **ELSE IF `{{change_name}}` is provided:**

   - **YOU MUST output:** `✓ Step 0 complete - Change name received: {{change_name}}`
   - Store the value as `{{change_name}}`
   - **YOU MUST proceed to Step 0.5**

---

## Step 0.5: Verify implementation tasks are complete

**Before proceeding with testing, you must verify that all preceding implementation tasks are complete.**

Now that you have the change name, automatically perform this verification:

1. **Read the OpenSpec `tasks.md` file** (if it exists) for this change:

   - Locate `openspec/changes/{{change_name}}/tasks.md`
   - Read the entire file to understand all task phases

2. **Identify all implementation-related tasks** (tasks that should be completed before testing):

   - Look for sections labeled "Implementation", "Phase 2: Implementation", or similar
   - Include validation tasks that are prerequisites to testing
   - Exclude testing tasks themselves (those will be verified after tests run)

3. **Check task completion status**:

   - Identify all implementation/validation tasks that are NOT marked as complete (`- [ ]` instead of `- [x]`)
   - Create a list of incomplete tasks with their descriptions

4. **Investigate incomplete tasks**:

   - First, run `git diff --name-only` to get changed files (needed for investigation)
   - For each incomplete task, check if the work described has actually been completed:
     - Review changed files from git diff to see if the task work is present
     - Read relevant source files mentioned in task descriptions to verify implementation
     - Check if the described functionality exists in the codebase
     - Compare task requirements with actual code changes
   - Determine if each task can be safely marked as complete based on code verification
   - **If tasks can be verified as complete, automatically update `tasks.md` to mark them complete** (update checkboxes from `- [ ]` to `- [x]`)
   - Track which tasks were auto-completed for the checkpoint report

5. **Determine if blockers exist**:

   - After investigation, categorize tasks:
     - Tasks that were auto-completed (verified in code)
     - Tasks that remain incomplete but can be verified (auto-completed)
     - Tasks that remain incomplete and **cannot** be verified through code inspection (blockers)

6. **Handle blockers**:

   - **If there are blockers** (incomplete tasks that cannot be verified as complete):
     - Present findings and stop:
       > **⚠️ BLOCKER: Implementation Task Status**
       >
       > **Remaining incomplete tasks that cannot be verified:**
       >
       > - `- [ ] 2.5 Manual browser testing` - **Investigation**: No evidence this has been performed. **Recommendation**: Requires manual verification before proceeding.
       >
       > [List any tasks that cannot be marked complete after investigation]
       >
       > **Testing cannot proceed until these tasks are completed.**
       >
       > [Wait for user to complete remaining tasks]
     - **WAIT for user confirmation** before proceeding
   - **If there are NO blockers** (all tasks complete or auto-completed):
     - If any tasks were auto-completed, briefly note: `✓ Auto-completed [N] implementation task(s) based on code verification`
     - **Auto-proceed directly to Steps 1.1-1.3** without stopping for confirmation

**Important:** Only stop and wait for confirmation if there are incomplete implementation tasks that cannot be verified as complete through code inspection. If all tasks are complete or can be auto-completed, proceed automatically to testing.

---

## Step 1: Automate initial setup

**After Step 0 and Step 0.5 complete (change name collected and implementation verified):**

The change name is already stored as `{{change_name}}` from Step 0.

**After Step 0.5 completes (no blockers, or blockers resolved and user approved):**

Automatically perform Steps 1.1, 1.2, and 1.3 without waiting for confirmation.

**Important:** Step 0.5 will only stop if there are blockers (incomplete tasks that cannot be auto-completed). If all tasks are complete or can be auto-completed, it will auto-proceed to Steps 1.1-1.3.

---

## Step 1.1: Infer context and description

1. Try to infer `{{change_desc}}` from the OpenSpec change with the same `{{change_name}}`:

   - Check if `openspec/changes/{{change_name}}/proposal.md` or `openspec/changes/{{change_name}}/spec.md` exists.
   - If found, read it and extract a brief description.
   - If not found, use a placeholder like `"Change description not found in OpenSpec"`.

2. Prepare the context line (but don't ask for confirmation yet):
   - Context: `{{change_name}}` – `{{change_desc}}`

---

## Step 1.2: Locate OpenSpec `tasks.md`

Locate and read the OpenSpec `tasks.md` file for this change **using Claude Code's file tools**:

1. Check if `openspec/changes/{{change_name}}/tasks.md` exists in the workspace.
2. If it exists:

   - Open and read the file.
   - Identify all test-related tasks (look for sections like `Testing`, `7. Testing`, or checklist items that clearly relate to tests).
   - Note the task numbers/labels and their descriptions.

3. If it doesn't exist:

   - Note: `No OpenSpec tasks.md found for this change`.
   - Continue with test proposal (the change may not use OpenSpec).

Prepare a summary (but don't ask for confirmation yet):

- Found tasks.md: [y/n based on findings]
- Test-related tasks: [short list or `none`]

---

## Step 1.3: Compute changed files via git

Determine the changed files using git **yourself**:

1. From the repository root, use Claude Code's terminal to run:

   - `git diff --name-only`

2. Capture the full command output.

3. Prepare the output in a fenced code block format (but don't ask for confirmation yet).

4. Prepare a clean bullet list of changed files.

Do **not** ask me to run `git diff`; you are responsible for running it and pasting the results here.

---

## Step 1.4: Automated test file discovery

**Automatically discover test files** based on Python/pytest conventions and changed files:

1. For each changed file, apply the following discovery rules:

   **Python modules** (`lib/*.py`, `*.py`):

   - Direct: `test_{module_name}.py` or `{module_name}_test.py`
   - Related: `tests/test_{module_name}.py` if tests directory exists

   **Main application** (`monitor.py`):

   - Direct: `test_monitor.py`
   - Related: Integration tests that exercise the Flask app

   **Library modules** (`lib/*.py`):

   - Direct: `test_{filename}.py` (e.g., `lib/sessions.py` → `test_sessions.py`)
   - Related: Tests in `tests/` directory matching the module name

   **Test files** (`test_*.py`, `*_test.py`):

   - Direct: Run the changed test file itself

   **Static files** (`static/**`):

   - Related: Feature/integration tests that exercise the frontend

   **Templates** (`templates/**`):

   - Related: Integration tests that render the templates

   **Configuration** (`config.yaml`, `config.yaml.example`):

   - Related: Tests that use configuration values

2. For each discovered test file, check if it exists using file system tools.

3. Prioritize discovered test files:

   - **Priority 1**: Direct test files (changed test files or exact matches)
   - **Priority 2**: Module-level tests (direct pytest convention matches)
   - **Priority 3**: Integration tests (broader coverage)
   - **Priority 4**: All tests (if no specific tests found)

4. Limit to **5-7 most relevant test files** (prioritize by specificity and relevance).

5. Prepare a list of discovered test files with their priority and mapping to changed files (but don't ask for confirmation yet).

---

## Step 1.5: Display context and discovered information (informational only)

After completing Steps 1.1, 1.2, 1.3, and 1.4 automatically, present all results together for informational purposes, then auto-proceed:

> **Context and Test Discovery Summary:**
>
> **1. Context:**
> Context: `{{change_name}}` – `{{change_desc}}`
>
> **2. OpenSpec summary for `{{change_name}}`:**
>
> - Found tasks.md: [y/n based on findings]
> - Test-related tasks: [short list or `none`]
> - Use for task mapping: [yes/no based on whether tasks.md exists and has test tasks]
>
> **3. Changed files from `git diff --name-only`:**
>
> ```
> # Output of: git diff --name-only
> [paste the actual output here]
> ```
>
> Detected changed files:
>
> - [list each file]
>
> **4. Automatically discovered test files:**
>
> - [Priority 1] `test_sessions.py` (matches: `lib/sessions.py`)
> - [Priority 2] `test_tmux.py` (matches: `lib/tmux.py`)
> - [Priority 3] `test_monitor.py` (related to: `monitor.py`)
>
> → Proceeding automatically to create test plan and run tests...

**Auto-proceed to Step 2** without waiting for confirmation.

---

## Step 2: Map tests to OpenSpec tasks and create test plan

1. Review the test-related tasks identified in Step 1.2 (if available).

2. For each discovered test file from Step 1.4, identify which OpenSpec task(s) it covers (if tasks.md exists).

3. Create a mapping between test files and OpenSpec tasks.

4. Group test files by type for execution:

   - **Group 1**: Unit tests (fast, isolated module tests)
   - **Group 2**: Integration tests (Flask app tests, API tests)
   - **Group 3**: End-to-end tests (if any)

5. Present the test plan with mapping (informational), then auto-proceed:

> **Test Plan:**
>
> **Group 1 (Unit tests):**
>
> 1. `pytest test_sessions.py -v` → Covers tasks 13.9
>
> **Group 2 (Integration tests):**
> 2. `pytest test_tmux.py -v` → Covers tasks 13.4, 13.8, 13.10
>
> **Group 3 (Full test suite):**
> 3. `pytest -v` → Covers all tasks
>
> **Total: 3 test runs planned**
>
> → Starting test execution...

**Auto-proceed directly to Step 3 (running tests)** without asking for confirmation.

---

## Step 3: Execute tests

1. **Run tests in order of priority**: Start with specific tests, then broader suites.

2. **Execution strategy**:

   - Run unit tests first (fastest, most isolated)
   - Then integration tests (moderate speed)
   - Finally full test suite if needed (comprehensive)

3. For each test execution:

   - Run the command using Claude Code's terminal: `pytest <test_file> -v`
   - Capture the full output (stdout and stderr)
   - Parse the output to extract:
     - Total tests
     - Passing count
     - Failing count
     - Skipped count
     - Failure details (test name, file, line number, error message)

4. **After all tests complete**, collect all outputs and prepare a comprehensive summary (but don't ask for confirmation yet).

5. Present results:

> **Test Execution Results:**
>
> **Group 1 (Unit tests):**
>
> ```
> # Output of: pytest test_sessions.py -v
> [paste full output]
> ```
>
> ✅ **Result**: 12 passed, 0 failed
>
> **Group 2 (Integration tests):**
>
> ```
> # Output of: pytest test_tmux.py -v
> [paste full output]
> ```
>
> ✅ **Result**: 8 passed, 0 failed
>
> **Overall Summary:**
>
> - Total: 20 tests
> - Passing: 20 (100%)
> - Skipped: 0 (0%)
> - Failing: 0 (0%)

**Do not checkpoint after each individual test** - wait until all tests complete, then proceed to Step 4.

---

## Step 4: Diagnose failures and suggest fixes

**After all tests complete**, analyze the results:

1. **Overall status**: Determine if all tests passed, or if there are failures/skipped tests.

2. **For each failure**:

   - Extract test name, file, and line number
   - Analyze error message to identify likely cause
   - Apply common failure pattern detection:

     **Pattern: Import error**

     - Error: `ModuleNotFoundError` or `ImportError`
     - Suggestion: Check if module exists, verify imports, check `PYTHONPATH`

     **Pattern: Missing fixture**

     - Error: `fixture 'xxx' not found`
     - Suggestion: Define fixture in `conftest.py` or test file

     **Pattern: Assertion error**

     - Error: `AssertionError` or `assert` failure
     - Suggestion: Check expected vs actual values, review test logic

     **Pattern: Attribute error**

     - Error: `AttributeError: 'xxx' has no attribute 'yyy'`
     - Suggestion: Check if method/attribute exists, verify object type

     **Pattern: Type error**

     - Error: `TypeError: xxx() takes N positional arguments`
     - Suggestion: Check function signature, verify argument count

     **Pattern: File not found**

     - Error: `FileNotFoundError` or `IOError`
     - Suggestion: Check file paths, verify test fixtures exist

     **Pattern: Configuration error**

     - Error: Related to `config.yaml` or settings
     - Suggestion: Check test configuration, verify config file exists

3. **Present comprehensive diagnosis**:

   - **If there are test failures:**
     - Present diagnosis and wait for confirmation:
       > **CHECKPOINT 3 of 4: Test results and diagnosis**
       >
       > **Overall Status:**
       >
       > - ❌ Failures: [count and details]
       > - ⚠️ Skipped: [count and details]
       >
       > **Failure Details:**
       >
       > 1. **Test**: `test_sessions.py::test_state_transition` - line 123
       >    - **Error**: `AssertionError: assert 'idle' == 'processing'`
       >    - **Likely cause**: State transition logic not returning expected value
       >    - **Suggested fix**: Check `should_refresh_priorities()` in `lib/headspace.py`
       >    - **Re-run command**: `pytest test_sessions.py::test_state_transition -v`
       >
       > **Next Steps:**
       >
       > - [List actionable fixes with file paths and commands]
       >
       > **Does this diagnosis look correct? [y,n]**
       >
       > - If **n**, specify what needs adjustment.
       > - If **y**, proceed to update tasks.md.
     - Wait for user response before proceeding to Step 5.
   - **If all tests pass** (no failures, only passing/skipped):
     - Present summary (informational only):
       > **Test Results Summary:**
       >
       > **Overall Status:**
       >
       > - ✅ All tests passing: [yes/no]
       > - ⚠️ Skipped: [count and details if any]
       >
       > → All tests passed. Proceeding to update tasks.md...
     - **Auto-proceed to Step 5** without confirmation.

---

## Step 5: Update Testing Status Summary in `tasks.md`

**This step must be completed before finishing the command, regardless of test pass/fail status.**

1. Check if `openspec/changes/{{change_name}}/tasks.md` exists.

2. If it exists:

   - Read the current `tasks.md` file using Claude Code's file editing tools.
   - Locate the "Testing Status Summary" section (usually at the end of the Testing section).
   - If the section doesn't exist, create it after the Testing section.

3. **Automatically parse test results** and update the section:

   - Extract from test outputs:
     - Test file names
     - Test counts (total, passing, failing, skipped)
     - Failure details (if any)
   - Format with proper status indicators:
     - ✅ for all passing
     - ⚠️ for warnings/skipped
     - ❌ for failures
   - Include overall summary statistics
   - Note any new tests written or existing tests updated

4. **Format example**:

   ```markdown
   **Testing Status Summary:**

   **Overall Test Results:**

   - Total tests: 20
   - Passing: 20 (100%)
   - Skipped: 0 (0%)
   - Failing: 0 (0%)

   **Test File Breakdown:**

   1. ✅ **Unit tests: `test_sessions.py`** (12 tests, all passing)

      - All existing tests passing
      - Added 5 new tests for state transition detection
      - Status: ✅ **100% passing**

   2. ✅ **Integration tests: `test_tmux.py`** (8 tests, all passing)

      - tmux session tests (4 tests) - all passing
      - send/capture tests (4 tests) - all passing
      - Status: ✅ **100% passing**
   ```

5. Write the updated `tasks.md` file back using Claude Code's file editing tools.

6. Display confirmation:

   > ✓ Updated `openspec/changes/{{change_name}}/tasks.md`
   > ✓ Updated Testing Status Summary with current test results

7. If `tasks.md` doesn't exist, note this and continue to Step 6 (if applicable).

**Important:** This summary should always reflect the actual current state of testing, whether tests passed or failed.

---

## Step 6: Update OpenSpec `tasks.md` task checkboxes (if all tests pass)

**Only proceed with this step if ALL relevant tests have passed and `tasks.md` exists.**

1. Review which test tasks correspond to the passing tests (from the Step 2 mapping).

2. Show me which tasks you propose to mark complete:

> **CHECKPOINT 4 of 4: Update OpenSpec task checkboxes**
>
> **OpenSpec Tasks to Update:**
> The following tasks will be marked complete in `openspec/changes/{{change_name}}/tasks.md`:
>
> - [x] 13.1 Write unit tests for state transition detection
> - [x] 13.2 Write tests for turn completion detection
> - [x] 13.3 Write integration tests for tmux session handling
> - [x] 13.4 Write tests for OpenRouter API optimization
>
> **Is this the correct set of tasks to mark complete? [y,n]**

3. Wait for my response. Do **not** proceed until I answer.

4. If I answer **y**:

   - Using Claude Code's file editing tools, read the current `tasks.md` file.
   - Update the relevant task checkboxes from `- [ ]` to `- [x]`.
   - Write the updated file back.
   - Optionally show a small diff or snippet of the updated section.
   - Display confirmation:

     > ✓ Updated `openspec/changes/{{change_name}}/tasks.md`
     > ✓ Marked the following tasks as complete: [list task numbers]

5. If I answer **n** or `tasks.md` doesn't exist, clearly state that you are skipping the update and why.

**Important:** Only mark tasks complete if **all** corresponding tests passed. If any tests failed, do not update `tasks.md` task checkboxes (but still update the Testing Status Summary).

---

## Return / Response format

**Before tests are run:**

- **Step 0 (Input collection)** - Only if change name not provided:
  - MANDATORY STOP to collect change name
  - Wait for user response before proceeding
- **Step 0.5 (Prerequisite check)** - Only if blockers are found:
  - Implementation task completion status
  - Investigation results for incomplete tasks
  - Auto-completed tasks (if any)
  - Blockers that must be resolved
  - **STOPS and waits for user confirmation** only if blockers exist
  - If no blockers, auto-proceeds silently (may note auto-completed tasks)
- **Context and Test Discovery Summary (informational only)** - Auto-proceeds:
  - A short **Context** line using the inputs
  - A summary of OpenSpec test-related tasks (or a note that none were found)
  - Changed files from `git diff --name-only`
  - **Automatically discovered test files** with priority and mapping
  - States "→ Proceeding automatically to create test plan and run tests..."
- **Test Plan (informational only)** - Auto-proceeds:
  - **Automatically discovered test files** organized into groups
  - **Mapping to OpenSpec tasks** (if `tasks.md` exists)
  - States "→ Starting test execution..."
  - **Runs tests immediately** without confirmation

**While running tests:**

- For each test group:
  - List the test files being run
  - After completion, show outputs
  - Summary for the group (pass/fail counts)
- No per-command checkpoints (batch reporting instead)

**After tests are complete:**

- **If test failures exist:**
  - Comprehensive diagnosis checkpoint (CHECKPOINT 3 of 4) with:
    - **Overall Pass/Fail summary** (all groups combined)
    - **Per-failure details** with file/line, error analysis, and suggested fixes
    - **Common failure pattern detection** with actionable suggestions
    - A **Next steps** section with concrete guidance
    - **Asks for confirmation** before proceeding
- **If all tests pass:**
  - Test results summary (informational only)
  - States "→ All tests passed. Proceeding to update tasks.md..."
  - **Auto-proceeds** to Step 5 without confirmation

**After tests are complete (regardless of pass/fail):**

- Automatic update of "Testing Status Summary" section in `tasks.md` (if it exists)
- Include test file names, pass/fail counts, and overall status
- Parsed and formatted automatically from test outputs

**If all tests pass and `tasks.md` exists:**

- Final checkpoint (CHECKPOINT 4 of 4) showing which OpenSpec tasks correspond to passing tests
- Ask for confirmation before updating task checkboxes in `tasks.md`
- After confirmation, update task checkboxes using Claude Code's file tools and display what changed

**Summary of checkpoint flow:**
- **Before tests:** 0-1 checkpoints (only if Step 0 finds blockers)
- **After tests (failures):** 1 checkpoint (diagnosis confirmation)
- **After tests (all pass):** 0 checkpoints (auto-proceed) + 1 final checkpoint (task checkbox update)

Always keep responses focused and practical, optimised for a tight Python/pytest TDD feedback loop, and always run commands + file edits yourself, checkpointing only when user intervention is required.

---

**SOP 70 complete.**
