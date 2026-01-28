# OTL Commands for Claude Code

Commands that automate the PRD-to-implementation workflow using OpenSpec change proposals. These commands handle the full development lifecycle from PRD creation through implementation, testing, and PR merge.

## Command Invocation

All OTL commands are registered with YAML frontmatter and can be invoked in Claude Code by typing the command name.

**Example:**
- To invoke the PRD workshop: Type `10: prd-workshop`
- To start the queue process: Type `20: prd-orchestrate`

Commands are organized in two subdirectories:
- `prds/` - PRD management commands (create, list, validate, sequence)
- `orch/` - Queue-based orchestration commands (automated build pipeline)

## Overview

These commands standardize how you work with OpenSpec change proposals. Each command automates specific steps in the spec-driven development process, reducing manual work and ensuring consistent workflow.

## Workflows

### PRD Management Commands

Use these commands to prepare PRDs before they enter the build process:

| Command | Name | Purpose |
|---------|------|---------|
| 10 | `prd-workshop` | Create or remediate PRDs interactively |
| 20 | `prd-list` | Show pending PRDs awaiting build |
| 30 | `prd-validate` | Quality gate (pass/fail) before orchestration |
| 40 | `prd-sequence` | Recommend build order based on dependencies |

See [PRD Command Suite README](prds/README.md) for detailed usage.

### Orchestration Commands (Automated Pipeline)

Use the orchestration commands for automated PRD-to-implementation with queue management:

| Command | Name | Purpose |
|---------|------|---------|
| 10 | `prd-queue-add` | Add validated PRDs to the processing queue |
| 20 | `prd-orchestrate` | Start the automated build pipeline |
| 30-60 | (sub-agents) | Proposal, Build, Test, Validate, Finalize, Post-Merge |
| 91-93 | (utilities) | Checkpoint handling, notifications, status display |

See [Orchestration README](orch/README.md) for detailed usage.

### Typical Workflow

```
10: prd-workshop     →  Create PRD
30: prd-validate     →  Quality gate
10: prd-queue-add    →  Add to queue
20: prd-orchestrate  →  Full automated build with checkpoints
```

**Human intervention points:**

1. After PRD creation - validate and fix issues
2. After OpenSpec proposal creation - review/adjust/approve
3. After testing - verify functionality works as expected
4. After PR creation - merge the pull request

### PRD Validation State

PRDs carry validation metadata in their YAML frontmatter to track their readiness for orchestration:

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

**Validation States:**

- **valid** - PRD passed validation checks, ready for orchestration
- **invalid** - PRD failed validation with documented errors
- **unvalidated** - PRD has not been validated yet

**Key Points:**

- The `10: prd-workshop` command auto-validates PRDs after creation
- The `20: prd-list` command displays validation status badges for each PRD
- The `30: prd-validate` command updates the frontmatter with validation results
- Only validated PRDs can be added to the orchestration queue (validation gate)
- Validation status is checked during `20: prd-orchestrate` to skip re-validating already valid PRDs

## Quick Start

### Single PRD Processing

1. **Create a PRD:**
   ```
   10: prd-workshop
   ```

2. **Validate the PRD:**
   ```
   30: prd-validate docs/prds/my-subsystem/my-feature-prd.md
   ```

3. **Add to queue and process:**
   ```
   10: prd-queue-add docs/prds/my-subsystem/my-feature-prd.md
   20: prd-orchestrate
   ```

4. **Respond to checkpoints** (proposal review, test review, PR merge)

### Batch Processing

1. **Add multiple PRDs:**
   ```
   10: prd-queue-add docs/prds/feature-1.md,docs/prds/feature-2.md
   ```

2. **Start batch orchestration:**
   ```
   20: prd-orchestrate
   ```

3. **Monitor status:**
   ```
   93: prd-queue-status
   ```

## Integration with OpenSpec

These commands are designed to work with OpenSpec change proposals. They expect:

- OpenSpec changes in `openspec/changes/<change-name>/`
- `proposal.md` for change description
- `tasks.md` for task tracking
- `spec.md` for detailed specifications (optional)

Commands automatically detect and use OpenSpec files when available.

## Requirements

- Python project with pytest
- Ruby (for orchestration scripts)
- OpenSpec installed and configured
- Git repository with `development` branch
- Claude Code or Cursor IDE with integrated terminal access

## PRD Location Convention

PRDs must be organized in subsystem folders:

```
docs/prds/
├── walking-skeleton-prd.md      # Root-level: IGNORED
├── beta_signups/
│   ├── feature-prd.md           # Pending (to build)
│   └── done/
│       └── completed-prd.md     # Completed
├── campaigns/
│   └── ...
```

- **Pending**: `docs/prds/{subsystem}/{name}.md`
- **Completed**: `docs/prds/{subsystem}/done/{name}.md`
- **Root-level**: Ignored by orchestration

**PRD File Format with Validation:**

Each PRD should include YAML frontmatter with validation metadata:

```markdown
---
validation:
  status: valid
  validated_at: "2026-01-03T10:30:00Z"
---

# PRD: Feature Name

## Executive Summary
...
```

The validation frontmatter is automatically managed by the `30: prd-validate` command and `10: prd-workshop` command.

## Troubleshooting

**Command not found:** Ensure the command file exists in `.claude/commands/otl/` and you're invoking it correctly in Claude Code.

**OpenSpec not empty:** Complete or archive any pending OpenSpec changes before starting a new PRD build. Run `openspec list` to see active changes.

**OpenSpec not detected:** Verify the change name matches the OpenSpec directory name in `openspec/changes/`.

**Tasks incomplete:** Review `openspec/changes/<change-name>/tasks.md` and mark completed tasks before finalizing.

**PRD validation fails:** Use `10: prd-workshop {path}` to remediate issues interactively.

**PRD not listed:** Ensure PRD is in a subsystem folder (not root level) and not in a `done/` subdirectory.

**Queue state issues:** Use `ruby orch/orchestrator.rb state reset` to reset orchestration state.

## Directory Structure

```
.claude/commands/otl/
├── README.md                    # This file
├── orch/                        # Queue-based orchestration
│   ├── README.md
│   ├── 10-queue-add.md         # Add PRDs to queue
│   ├── 20-start-queue-process.md  # Main orchestrator
│   ├── 30-proposal.md          # Proposal sub-agent
│   ├── 35-build.md             # Build sub-agent
│   ├── 40-test.md              # Test sub-agent
│   ├── 45-validate-build.md    # Validation sub-agent
│   ├── 50-finalize.md          # Finalize sub-agent
│   ├── 60-post-merge.md        # Post-merge sub-agent
│   ├── 91-checkpoint.md        # Checkpoint handler
│   ├── 92-notify.md            # Notification utility
│   └── 93-queue-status.md      # Status display
└── prds/                        # PRD management commands
    ├── README.md
    ├── 10-workshop.md          # PRD workshop
    ├── 20-list.md              # List PRDs
    ├── 30-validate.md          # Validate PRDs
    └── 40-sequence.md          # Sequence PRDs
```

## Ruby Backend

The orchestration commands use Ruby scripts in `orch/` for state management:

```
orch/
├── orchestrator.rb      # Main dispatcher
├── state_manager.rb     # State persistence (state.yaml)
├── queue_manager.rb     # Queue operations (queue.yaml)
├── prd_validator.rb     # PRD validation
├── notifier.rb          # Slack notifications
├── git_history_analyzer.rb  # Git history for conflict detection
├── config.yaml          # Orchestration config
├── commands/            # Ruby command implementations
├── working/             # State/queue files (gitignored)
└── log/                 # Log files (gitignored)
```

**Common Ruby commands:**

```bash
# Show orchestration status
ruby orch/orchestrator.rb status

# List queue items
ruby orch/orchestrator.rb queue list

# Reset state
ruby orch/orchestrator.rb state reset

# List PRDs with validation status
ruby orch/prd_validator.rb list-all
```
