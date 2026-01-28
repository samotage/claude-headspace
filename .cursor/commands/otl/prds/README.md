# PRD Workflow Commands

This directory contains commands for managing the PRD (Product Requirements Document) workflow. These commands prepare PRDs for the automated orchestration pipeline.

## Commands Overview

| Command | Name | Purpose |
|---------|------|---------|
| 10 | `prd-workshop` | Interactive workshop for creating or remediating PRDs |
| 20 | `prd-list` | List all PRDs with validation status |
| 30 | `prd-validate` | Validate a PRD before adding to orchestration queue |
| 40 | `prd-sequence` | Create a sequence of related PRDs |

## Quick Start

**Create a new PRD:**
```
10: prd-workshop
```

**Remediate an existing PRD:**
```
10: prd-workshop docs/prds/my-subsystem/my-feature-prd.md
```

**Validate a PRD:**
```
30: prd-validate docs/prds/my-subsystem/my-feature-prd.md
```

**List all PRDs:**
```
20: prd-list
```

## Git History Integration

### What It Does

The PRD workflow now incorporates git commit history analysis to help the AI understand:
- What has already been implemented in the codebase
- Recent development activity in related subsystems
- Patterns established by previous OpenSpec changes
- Files that are likely to be affected by new requirements

### When It's Used

#### During PRD Creation (10: prd-workshop)

**Phase 3: Existing Implementation Check**

Before defining detailed requirements, the workshop analyzes git history to:
1. Find related files in the codebase
2. Identify recent commits (last 12 months)
3. Map OpenSpec changes previously applied
4. Detect implementation patterns

This helps the AI:
- Detect potential conflicts early
- Suggest requirements that integrate well with existing code
- Recommend approaches consistent with project patterns
- Avoid duplicating existing functionality

**AI Context Only Mode:**

The git history information is used by the AI to inform its suggestions, but is NOT shown as raw data dumps to the user. Instead, the AI synthesizes findings into human-friendly summaries:

```
I've analyzed the project history for the inquiry subsystem.

**Existing Implementation:**
- 12 files found related to inquiries
- Active development: Last commit 2 weeks ago
- Follows pattern: model → service → controller → policy → views

**OpenSpec History:**
- inquiry-04-admin-crud - Archived Nov 20 - Added admin CRUD
- inquiry-03-email - Archived Nov 5 - Added email notifications

**Recommendations:**
- Consider integrating with existing InquiryProcessor service
- Follow established admin pattern (see admin/inquiries_controller.rb)
```

### Configuration

Default settings:
- **Timeframe:** 12 months back
- **Subsystem detection:** Automatic from PRD path (docs/prds/{subsystem}/)
- **Presentation:** AI context only (no raw dumps to user)

### Benefits

1. **Better Requirements** - AI suggests requirements aware of existing code
2. **Fewer Conflicts** - Early detection of overlapping work
3. **Consistent Patterns** - New features follow established conventions
4. **Accurate Scoping** - Understanding of affected files improves estimates

### Troubleshooting

**Git history analysis fails:**
- Ensure you're in a git repository
- Check that `git` command is available in PATH
- Verify OpenSpec directory structure exists

If analysis fails, the workflow continues without git context - PRDs can still be created, but without historical insights.

**Subsystem not detected:**
- Ensure PRD is saved in proper structure: `docs/prds/{subsystem}/{name}-prd.md`
- Root-level PRDs won't have subsystem context
- You can manually specify: `--subsystem inquiry-system`

### Performance

Git analysis adds approximately 2-5 seconds to PRD workflow.
- File listing: ~1s
- Commit history: ~1-2s
- OpenSpec mapping: ~1s

For very large repositories (>10K commits), consider reducing timeframe:
```bash
ruby orch/git_history_analyzer.rb --subsystem campaigns --months-back 6
```

## PRD Location Convention

PRDs must be organized in subsystem folders:

```
docs/prds/
├── walking-skeleton-prd.md      # Root-level: IGNORED by orchestration
├── dashboard/
│   ├── feature-prd.md           # Pending (to build)
│   └── done/
│       └── completed-prd.md     # Completed
├── notifications/
│   └── slack-integration-prd.md
```

- **Pending PRDs**: `docs/prds/{subsystem}/{prd-name}.md`
- **Epic/Sprint prefix**: If the initial workshop prompt (or Phase 0 response) includes an epic and sprint, the workshop saves the PRD as `e<epic>-s<sprint>-{prd-name}.md` (e.g. `e2-s3-voice-bridge-prd.md`).
- **Completed PRDs**: `docs/prds/{subsystem}/done/{prd-name}.md`
- **Root-level PRDs**: Ignored by orchestration

## Validation States

PRDs carry validation metadata in their YAML frontmatter:

```yaml
---
validation:
  status: valid | invalid | unvalidated
  validated_at: "2026-01-03T10:30:00Z"
  validation_errors:  # Only present when invalid
    - "Missing Success Criteria section"
    - "TODO marker found on line 45"
---
```

**Status Badges in `20: prd-list`:**

- `[✓ Valid - Jan 2]` - Ready for orchestration queue
- `[✗ Invalid - 3 errors]` - Needs remediation via `10: prd-workshop`
- `[⊗ Unvalidated]` - Needs validation via `30: prd-validate`

**Validation Gate:** Only PRDs with `status: valid` can be added to the orchestration queue.

## Related Documentation

- **Orchestration Commands:** See `orch/README.md` for the automated build pipeline
- **Main OTL README:** See `../README.md` for overall workflow
- **Ruby Backend:** `orch/prd_validator.rb` for validation implementation
