---
name: '93: prd-queue-status'
description: 'Display current queue and orchestration status'
---

# 93: PRD Queue Status

**Command name:** `93: prd-queue-status`

**Purpose:** Display current queue and orchestration status.

---

## Prompt

You are displaying the PRD orchestration status.

**Check for bulk mode context:**
- If this command is being run during an active orchestration session, check if bulk_mode is set
- If bulk_mode context is available from command 20, include it in the status display
- If no bulk_mode context is available (standalone status check), display "N/A" for Mode

**Get full status:**

```bash
ruby orch/orchestrator.rb status
```

**Format the output:**

```
═══════════════════════════════════════════
  PRD ORCHESTRATION STATUS
═══════════════════════════════════════════

CURRENT STATE
─────────────
Phase:      [phase or "idle"]
Checkpoint: [checkpoint or "none"]
Change:     [change_name or "none"]
Branch:     [branch or "N/A"]
Mode:       [🤖 BULK (auto-approve reviews) or "Default" or "N/A"]

QUEUE STATISTICS
────────────────
Pending:     [n]
In Progress: [n]
Completed:   [n]
Failed:      [n]
Skipped:     [n]
───────────────
Total:       [n]

CURRENT PROCESSING
──────────────────
[If in_progress item exists:]
PRD:    [prd_path]
Change: [change_name]
Started: [timestamp]

[If no item in progress:]
No PRD currently being processed.

NEXT UP
───────
[If pending items exist:]
1. [prd_path]
2. [prd_path]
...

[If no pending items:]
Queue is empty.

═══════════════════════════════════════════
```

---

## Additional Commands

**List all queue items with details:**

```bash
ruby orch/orchestrator.rb queue list
```

**Show only state:**

```bash
ruby orch/orchestrator.rb state show
```

---

## Quick Actions

Based on status, suggest next action:

- If `checkpoint` is set: "Run 91: prd-checkpoint to respond"
- If `phase` is active and no checkpoint: "Orchestration in progress"
- If queue has pending and nothing in progress: "Run 20: prd-orchestrate to start"
- If queue empty and idle: "Run 10: prd-queue-add to add PRDs"

