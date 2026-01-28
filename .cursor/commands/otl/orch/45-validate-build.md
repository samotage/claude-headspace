---
name: "45: prd-validate-build"
description: "Sub-agent for VALIDATE phase - spec compliance check before commit"
---

# 45: PRD Validate Build

**Command name:** `45: prd-validate-build`

**Purpose:** Fresh sub-agent for VALIDATE phase. Spawned by Command 40 after tests pass. Validates that the implementation matches all spec artifacts before committing. This is spec-driven development enforcement.

**This runs with fresh context to ensure reliable validation.**

---

## Prompt

You are a fresh sub-agent handling the VALIDATE phase for a PRD build. Your responsibility is to perform an AI code review comparing the implementation against all spec artifacts, generate a compliance report, and handle failures with a retry loop (up to 2 attempts).

---

## Step 0: Load State

**This command reads all context from state. No context needs to be passed from the spawner.**

```bash
ruby orch/orchestrator.rb state show
```

Read the YAML to get:

- `change_name` - The change being processed
- `prd_path` - The PRD file path
- `branch` - The feature branch
- `bulk_mode` - Processing mode (true = bulk, false = default)
- `spec_compliance_attempts` - Current retry attempt count

If `bulk_mode` is not set, default to `bulk_mode = false` (Default Mode).

---

## PHASE: VALIDATE

**Track usage for testing phase (validation is part of testing):**

```bash
ruby orch/orchestrator.rb usage increment --phase testing
```

```bash
ruby orch/orchestrator.rb validate
```

**Read the YAML output for spec artifacts and compliance status.**

The output includes:
- `data.artifacts` - Paths to all spec files (PRD, proposal.md, tasks.md, design.md, specs/*.md)
- `data.artifacts_status` - Which artifacts exist
- `data.spec_files` - List of delta spec files
- `data.compliance` - Current retry status

---

### Step 1: Read All Spec Artifacts

Read each spec artifact to understand the requirements:

**1.1 Read the PRD (functional requirements):**
```bash
cat [prd_path]
```

**1.2 Read proposal.md (planned changes + Definition of Done):**
```bash
cat openspec/changes/[change_name]/proposal.md
```

**1.3 Read tasks.md (implementation checklist):**
```bash
cat openspec/changes/[change_name]/tasks.md
```

**1.4 Read design.md (technical patterns) if it exists:**
```bash
cat openspec/changes/[change_name]/design.md
```

**1.5 Read proposal-summary.md (build context):**
```bash
cat openspec/changes/[change_name]/proposal-summary.md
```

**1.6 Read all delta spec files:**
```bash
find openspec/changes/[change_name]/specs -name "*.md" -exec cat {} \;
```

---

### Step 2: Review Implementation Against Spec

Perform a comprehensive code review checking:

**2.1 Acceptance Criteria (from proposal.md Definition of Done):**
- [ ] Each acceptance criterion is satisfied
- [ ] No acceptance criteria were missed

**2.2 PRD Functional Requirements:**
- [ ] All requirements from the PRD are implemented
- [ ] No requirements were partially implemented
- [ ] No extra features added beyond scope

**2.3 Tasks Completion (from tasks.md):**
- [ ] All tasks are marked as complete [x]
- [ ] No incomplete tasks remain [ ]

**2.4 Design Patterns (from design.md):**
- [ ] Code follows the specified technical approach
- [ ] Patterns match the design decisions

**2.5 Delta Specs (ADDED/MODIFIED/REMOVED):**
- [ ] ADDED requirements are fully implemented
- [ ] MODIFIED requirements reflect the changes
- [ ] REMOVED features are actually removed

---

### Step 3: Generate Compliance Report

Create a brief, high-level compliance report at:
`openspec/changes/[change_name]/compliance-report.md`

**Report Format:**

```markdown
# Compliance Report: [change_name]

**Generated:** [timestamp]
**Status:** [COMPLIANT / NON-COMPLIANT]

## Summary

[1-2 sentence summary of compliance status]

## Acceptance Criteria

| Criterion | Status | Notes |
|-----------|--------|-------|
| [criterion 1] | ✓ / ✗ | [brief note] |
| ... | ... | ... |

## Requirements Coverage

- **PRD Requirements:** [X/Y covered]
- **Tasks Completed:** [X/Y complete]
- **Design Compliance:** [Yes/No]

## Issues Found

[If non-compliant, list issues briefly]

1. [Issue description]
2. [Issue description]

## Recommendation

[PROCEED / FIX REQUIRED]
```

---

### Step 4: Record Results

```bash
ruby orch/orchestrator.rb validate record --compliant --report-path openspec/changes/[change_name]/compliance-report.md
```

Or if issues found:

```bash
ruby orch/orchestrator.rb validate record --not-compliant --issues '[{"type":"missing_requirement","description":"..."}]' --report-path openspec/changes/[change_name]/compliance-report.md
```

**Read the response:**

---

### If `outcome: compliant`

Implementation matches spec. Proceed to finalize.

Display summary:
```
✓ Spec Compliance Validated

All acceptance criteria satisfied.
All PRD requirements implemented.
All tasks completed.
Design patterns followed.

Proceeding to finalize...
```

**Proceed to SPAWN NEXT COMMAND section.**

---

### If `outcome: retry`

- This is compliance attempt [N] of 2
- Analyze the issues found
- Determine fixes needed:

**Fix Scope (in order of preference):**
1. **Code fixes** - Implementation doesn't match spec
2. **Test fixes** - Missing test coverage for requirements
3. **Spec amendments** - If spec was ambiguous or incorrect

**After making fixes:**

1. Re-run tests to ensure fixes don't break anything:
```bash
pytest -v
```

2. If tests pass, re-validate by returning to Step 2

3. If tests fail, fix test failures first, then re-validate

---

### If `outcome: human_intervention`

- Compliance loop exhausted (2 attempts failed)

**This checkpoint ALWAYS stops in both Default and Bulk modes.**

Unlike test review checkpoints which can be auto-approved in bulk_mode, spec compliance failure requires explicit human decision because:
- The implementation fundamentally doesn't match the spec
- Automated fixes have failed twice
- Human judgment needed on whether to proceed or refactor

**Send notification:**

```bash
ruby orch/notifier.rb decision_needed --change-name "[change_name]" --message "Spec compliance failed after 2 retry attempts" --checkpoint "spec_compliance_failed_review" --action "Review compliance issues and choose: fix manually, skip validation, or abort"
```

**CHECKPOINT: Use AskUserQuestion**

- Question: "Spec compliance failed after 2 attempts. The implementation doesn't fully match the spec.

  **Issues Found:**
  [List from compliance report]

  **Attempts Made:**
  [Summary of fix attempts]

  How would you like to proceed?"

- Options:
  - "I'll fix manually - then re-run this command"
  - "Skip validation - proceed to finalize anyway (with warning)"
  - "Abort - stop processing this PRD"

**Based on response:**
- **Fix manually**: STOP, user will re-run `45: prd-validate-build`
- **Skip validation**: Set warning flag and proceed to SPAWN NEXT COMMAND
- **Abort**: Mark as failed and STOP

---

## SPAWN NEXT COMMAND

**CRITICAL: Do NOT stop here. You MUST spawn the FINALIZE phase.**

**Validation complete. Spawning FINALIZE phase.**

Display summary:

```
═══════════════════════════════════════════
  45: PRD-VALIDATE-BUILD COMPLETE
═══════════════════════════════════════════

Change:     [change_name]
Branch:     [branch]

Spec Compliance:
  Status:   [COMPLIANT ✓ / SKIPPED ⚠️]
  Attempts: [N]
  Report:   openspec/changes/[change_name]/compliance-report.md

Validation Areas:
  ✓ Acceptance Criteria
  ✓ PRD Requirements
  ✓ Task Completion
  ✓ Design Patterns
  ✓ Delta Specs

Spawning finalize command...
═══════════════════════════════════════════
```

**Update state to indicate validation complete:**

```bash
ruby orch/orchestrator.rb state set --key phase --value validate_complete
```

**MANDATORY: Spawn the finalize command using the Skill tool:**

```
Use Skill tool with: skill = "otl:orch:50-finalize"
```

This is NOT optional - you MUST use the Skill tool to invoke `50: prd-finalize`. Command 50 will:
- Read `change_name` from state
- Automatically commit ALL changes (including compliance report) using polling-based staging
- Create PR and await merge confirmation

**If you do not have access to the Skill tool, then execute these commands directly:**

```bash
ruby orch/orchestrator.rb finalize
```

Then proceed with committing, PR creation, and merge checkpoint as described in Command 50.

---

## Error Handling

On any error:

```bash
ruby orch/notifier.rb error --change-name "[change_name]" --message "[error]" --phase "validate" --resolution "[fix suggestion]"
```

STOP. The pipeline will need to be manually restarted after fixing the issue.
