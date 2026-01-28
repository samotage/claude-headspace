---
name: '30: prd-validate'
description: 'Quality gate that validates PRDs before orchestration'
---

# 30: Validate PRD

**Command name:** `30: prd-validate`

**Purpose:** Quality gate that validates PRDs before they enter the orchestration engine. Outputs structured PASS/FAIL/BLOCKED result suitable for sub-agent invocation.

**Input:** `{{prd_path}}` - Path to PRD file (e.g., `docs/prds/campaigns/my-feature-prd.md`)

---

## Orchestration Engine Integration

**CRITICAL:** This command is designed for sub-agent invocation by the orchestration engine.

**Sub-Agent Invocation Pattern:**

```
Orchestration Engine (20-prd-queue-process)
  ↓
BATCH VALIDATE PHASE (all PRDs first):
  ↓
For each PRD in queue:
  → Spawn sub-agent: 30: prd-validate {prd-path}
  → Collect results (PASS/FAIL/BLOCKED)
  ↓
After ALL validated:
  → Show summary of results
  → Checkpoint for human review of failures
  → Build queue = only PASSED PRDs
```

---

## Prompt

You are a PRD validator. Your job is to check if a PRD is ready for the orchestration engine. You perform systematic checks and output a structured result.

**Input:** PRD file path at `{{prd_path}}`

---

## Step 0: Get PRD Path Input

**IMPORTANT: DO NOT PROCEED without this input.**

1. **Check if PRD path is provided:**

   🔍 **CONDITIONAL CHECK - YOU MUST EVALUATE THIS EXACTLY**

   **Condition to check:** Is `{{prd_path}}` empty, not provided, or appears as a placeholder (like "{{prd_path}}")?

   **IF `{{prd_path}}` is empty/placeholder:**

   🛑 **MANDATORY STOP - YOU MUST NOT PROCEED WITHOUT INPUT**

   **YOU MUST:**
   - Display the following message to the user:

     ```
     Please provide the path to the PRD file you want to validate.

     Example: docs/prds/campaigns/my-feature-prd.md

     What is the PRD file path?
     ```

   - **WAIT for user response in plain text**
   - **YOU MUST NOT proceed until the user provides a valid file path**
   - **YOU MUST end your message/turn after asking for the path**

   **ELSE IF `{{prd_path}}` is provided:**

   - **YOU MUST output:** `✓ Step 0.1 complete - PRD path received: {{prd_path}}`
   - **YOU MUST proceed to Step 0.2**

2. **Verify the PRD file exists:**

   - Once user provides the path, store it as `{{prd_path}}`
   - Read/check the file at `{{prd_path}}`
   - **IF file doesn't exist:**
     - **YOU MUST output error:** `❌ File not found: {{prd_path}}`
     - **YOU MUST ask user for correct path again**
     - **YOU MUST NOT proceed**
   - **IF file exists:**
     - **YOU MUST output:** `✓ Step 0.2 complete - PRD file verified`
     - **YOU MUST proceed to Step 1**

---

## Step 1: Load PRD

```bash
# Verify file exists
test -f "{{prd_path}}" && echo "File exists" || echo "ERROR: File not found"
```

Read the PRD content and parse its structure.

---

## Step 2: Run Validation Checks

Perform each check and record results:

### Check 1: Format Compliance

Verify required sections are present:

```
Required Sections:
- [ ] Executive Summary or equivalent introduction
- [ ] Scope (In Scope / Out of Scope)
- [ ] Success Criteria
- [ ] Functional Requirements (numbered: FR1, FR2, etc.)

Optional but Recommended:
- [ ] Non-Functional Requirements (NFR1, NFR2, etc.)
- [ ] UI Overview (if user-facing feature)
```

**Severity:**
- Missing Executive Summary → ERROR
- Missing Scope → ERROR
- Missing Success Criteria → WARNING
- Missing Functional Requirements → BLOCKING
- Missing NFRs → INFO (acceptable for some PRDs)

### Check 2: Gap Detection

Scan for incomplete content:

```
Gaps to Detect:
- [ ] TODO markers (case-insensitive: TODO, todo, To-Do)
- [ ] Placeholder text: [TBD], [placeholder], [to be determined], [fill in]
- [ ] Empty list items (lines with just "- " or "* ")
- [ ] Empty sections (headers with no content below)
- [ ] Question marks indicating uncertainty: "Should we...?", "TBD?"
```

**Severity:**
- TODO markers → ERROR
- Placeholder text → ERROR
- Empty list items → WARNING
- Empty sections → WARNING

### Check 3: Requirement Focus (WHAT not HOW)

Flag implementation details that don't belong:

```
Implementation Details to Flag:
- [ ] Specific class/method names: "Create UserService class"
- [ ] Database specifics: "Add index on column", "Use JSONB"
- [ ] Framework specifics: "Use Sidekiq", "Add Stimulus controller"
- [ ] File paths: "in app/services/", "create lib/..."
- [ ] Code snippets or pseudocode

Acceptable (requirement-focused):
- "Users can filter by status"
- "System sends email notifications"
- "Data is validated before saving"
```

**Severity:**
- Heavy implementation details → WARNING
- Occasional technical references → INFO

### Check 4: Conflict Detection

Check for overlaps with existing work:

```bash
# Check OpenSpec for related changes
openspec list 2>/dev/null | head -20

# Check for related pending PRDs
find docs/prds -mindepth 2 -name "*.md" -type f | grep -v "/done/" | grep -v "{{prd_path}}"
```

**Conflicts to Check:**
- [ ] Active OpenSpec changes covering same functionality
- [ ] Other pending PRDs with overlapping scope
- [ ] Requirements that contradict each other within the PRD

**Severity:**
- Direct conflict with active change → BLOCKING
- Overlap with pending PRD → WARNING
- Internal contradictions → ERROR

### Check 5: Scope Assessment

Estimate task count to check scope appropriateness:

```
Task Estimation:
- Count functional requirements
- Estimate ~2-3 tasks per FR (implementation + test)
- Add overhead for setup, integration, finalization

Target: 20-30 tasks
Warning: >30 tasks (consider splitting)
Blocking: >50 tasks (too large for single PRD)
```

**Severity:**
- ≤30 tasks → PASS
- 31-50 tasks → WARNING (recommend splitting)
- >50 tasks → ERROR (must split)

### Check 6: Ambiguity Check

Identify vague or unmeasurable requirements:

```
Ambiguous Patterns:
- [ ] "Should be fast" (no metric)
- [ ] "User-friendly" (subjective)
- [ ] "As needed" (undefined trigger)
- [ ] "Appropriate" (undefined standard)
- [ ] "Etc." or "and so on" (incomplete lists)
- [ ] "Similar to X" without specifics
```

**Severity:**
- Multiple vague requirements → WARNING
- Critical requirements that are vague → ERROR

### Check 7: Orchestration Readiness

Verify PRD structure matches what `proposal.rb` expects:

```
Orchestration Requirements:
- [ ] File is valid Markdown
- [ ] Sections are properly structured (headers, lists)
- [ ] Requirements are numbered and parseable
- [ ] No syntax that would break parsing
```

**Severity:**
- Parsing issues → ERROR
- Structure issues → WARNING

---

## Step 3: Generate Validation Result

**CRITICAL:** Output MUST be in this exact YAML format for orchestration engine parsing:

```yaml
---
validation_result:
  status: PASS | FAIL | BLOCKED
  prd_path: "{{prd_path}}"
  timestamp: "[ISO timestamp]"
  
  checks:
    format_compliance:
      status: pass | fail
      issues: []
    
    gap_detection:
      status: pass | fail
      issues:
        - type: gap_detection
          severity: warning | error
          message: "PRD contains TODO marker"
          location: "line 45"
    
    requirement_focus:
      status: pass | fail
      issues: []
    
    conflict_detection:
      status: pass | fail
      issues: []
    
    scope_assessment:
      status: pass | fail
      estimated_tasks: 25
      issues: []
    
    ambiguity_check:
      status: pass | fail
      issues: []
    
    orchestration_readiness:
      status: pass | fail
      issues: []
  
  summary:
    total_issues: 3
    blocking: 0
    errors: 1
    warnings: 2
    info: 0
  
  ready_for_build: true | false
  
  recommendation: "PRD is ready for orchestration" | "Address errors before proceeding" | "Human intervention required"
---
```

---

## Step 4: Human-Readable Summary

After the YAML block, provide a human-readable summary:

### On PASS:

```
## ✓ Validation PASSED

**PRD:** {{prd_path}}

All checks passed. This PRD is ready for the orchestration engine.

**Summary:**
- Format: ✓
- Gaps: ✓ (none found)
- Requirements: ✓ (focused on WHAT)
- Conflicts: ✓ (none detected)
- Scope: ✓ (~25 tasks estimated)
- Clarity: ✓ (no ambiguous requirements)
- Orchestration: ✓ (structure valid)

✓ PRD frontmatter updated: status=valid

**Next Steps:**
- Add to queue: `ruby orch/orchestrator.rb queue add --prd-path {{prd_path}}`
```

### On FAIL:

```
## ✗ Validation FAILED

**PRD:** {{prd_path}}

This PRD has issues that must be addressed before orchestration.

**Issues Found:**

1. **[ERROR]** Gap Detection - line 45
   PRD contains TODO marker: "TODO: Define acceptance criteria"

2. **[WARNING]** Scope Assessment
   Estimated 35 tasks exceeds target of 20-30. Consider splitting.

3. **[WARNING]** Ambiguity Check - FR7
   Requirement "should be performant" lacks specific metrics.

**Summary:** 1 error, 2 warnings

✓ PRD frontmatter updated: status=invalid (3 errors documented)

**Remediation Options:**

1. **Fix manually** - Edit the PRD file directly
2. **Workshop fixes** - Run `10: prd-workshop {{prd_path}}` for guided remediation
3. **Skip for now** - Remove from queue and address later

CHECKPOINT: How would you like to proceed? [1/2/3]
```

### On BLOCKED:

```
## ⊘ Validation BLOCKED

**PRD:** {{prd_path}}

This PRD has blocking issues that require human intervention.

**Blocking Issues:**

1. **[BLOCKING]** Conflict Detection
   Active OpenSpec change `beta-signups-04` covers overlapping functionality.
   Cannot proceed until conflict is resolved.

2. **[BLOCKING]** Scope Assessment
   Estimated 65 tasks is too large for a single PRD.
   Must split into multiple PRDs before proceeding.

**Summary:** 2 blocking issues

✓ PRD frontmatter updated: status=invalid (2 blocking issues documented)

**Required Actions:**

1. Resolve conflict with existing change
2. Split PRD into smaller units using `10: prd-workshop`

Human intervention required. Orchestration cannot proceed with this PRD.
```

---

## Step 5: Update PRD Metadata

**CRITICAL:** After validation, update the PRD frontmatter with the validation results.

**Run the validation status updater:**

```bash
# For PASS status
ruby orch/prd_validator.rb update --prd-path "{{prd_path}}" --status valid

# For FAIL or BLOCKED status, collect error messages
ruby orch/prd_validator.rb update --prd-path "{{prd_path}}" --status invalid --errors "Error 1,Error 2,Error 3"
```

**What this does:**

- Writes validation metadata to PRD YAML frontmatter
- Status will be 'valid', 'invalid', or 'unvalidated'
- Timestamp is added automatically (ISO 8601 format)
- Error messages are stored for invalid PRDs

**After updating metadata:**

```
✓ PRD frontmatter updated with validation status
```

**Important:** This metadata is used by:
- `20: prd-list` command - to display validation status
- `10: prd-queue-add` command - to enforce validation gate
- `20: start-prd-queue-process` - to skip re-validation of already validated PRDs

---

## Remediation Flow

When validation fails and user chooses to remediate:

```
Initiating remediation via PRD Workshop...

Run: 10: prd-workshop {{prd_path}}

The workshop will:
1. Load your PRD content
2. Walk through issues identified
3. Guide you to fix each one
4. Save the updated PRD
5. Return here for re-validation
```

After remediation, re-run validation:

```
Re-validating: 30: prd-validate {{prd_path}}
```

---

## Batch Validation Mode (Orchestration Engine)

When the orchestration engine validates multiple PRDs:

```
## Batch Validation Summary

Validating 4 PRDs in queue...

| PRD | Status | Issues |
|-----|--------|--------|
| beta-signups-05-prd.md | ✓ PASS | 0 |
| campaign-visits-4-prd.md | ✓ PASS | 2 warnings |
| google-analytics-prd.md | ✗ FAIL | 1 error, 3 warnings |
| large-feature-prd.md | ⊘ BLOCKED | 1 blocking |

---

**Validation Complete:**
- ✓ PASS (2): beta-signups-05-prd.md, campaign-visits-4-prd.md
- ✗ FAIL (1): google-analytics-prd.md
- ⊘ BLOCKED (1): large-feature-prd.md

**Build Queue:** 2 PRDs ready

CHECKPOINT: How should we handle failed/blocked PRDs?
- a) Proceed with passed PRDs only
- b) Remediate failures now
- c) Abort and fix all issues first
```

---

## Notes

- This command is designed for both interactive use and sub-agent invocation
- The YAML output block is required for orchestration engine parsing
- Human-readable summary follows the YAML for interactive use
- Remediation flows back to `10-workshop` command
- Re-validation should always follow remediation

---

**PRD Validation complete.**


