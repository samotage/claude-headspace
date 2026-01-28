---
name: '10: prd-queue-add'
description: 'Add PRDs to the processing queue for continuous orchestration'
---

# 10: PRD Queue Add

**Command name:** `10: prd-queue-add`

**Purpose:** Add one or more PRDs to the processing queue for continuous orchestration.

**Input:** `{{prd_paths}}` - Comma-separated list of PRD file paths (or single path)

---

## Step 0: Get PRD Path(s) Input

**IMPORTANT: DO NOT PROCEED without this input.**

1. **Check if PRD path(s) are provided:**

   🔍 **CONDITIONAL CHECK - YOU MUST EVALUATE THIS EXACTLY**

   **Condition to check:** Is `{{prd_paths}}` empty, not provided, or appears as a placeholder (like "{{prd_paths}}")?

   **IF `{{prd_paths}}` is empty/placeholder:**

   🛑 **MANDATORY STOP - YOU MUST NOT PROCEED WITHOUT INPUT**

   **YOU MUST:**
   - Display the following message to the user:

     ```
     Please provide the path(s) to the PRD file(s) you want to add to the queue.

     Single PRD example: docs/prds/campaigns/my-feature-prd.md

     Multiple PRDs example: docs/prds/campaigns/feature-1-prd.md,docs/prds/campaigns/feature-2-prd.md

     What is the PRD file path (or comma-separated paths)?
     ```

   - **WAIT for user response in plain text**
   - **YOU MUST NOT proceed until the user provides valid file path(s)**
   - **YOU MUST end your message/turn after asking for the path(s)**

   **ELSE IF `{{prd_paths}}` is provided:**

   - **YOU MUST output:** `✓ Step 0.1 complete - PRD path(s) received: {{prd_paths}}`
   - **YOU MUST proceed to Step 0.2**

2. **Verify the PRD file(s) exist:**

   - For each path in `{{prd_paths}}` (split by comma if multiple):
     - Check the file exists
     - **IF any file doesn't exist:**
       - **YOU MUST output error:** `❌ File not found: [path]`
       - **YOU MUST ask user for correct path(s) again**
       - **YOU MUST NOT proceed**
   - **IF all files exist:**
     - **YOU MUST output:** `✓ Step 0.2 complete - All PRD file(s) verified`
     - **YOU MUST proceed to Step 0.3**

3. **Check validation status (Validation Gate):**

   - For each PRD path, check its validation status:
   
   ```bash
   ruby orch/prd_validator.rb status --prd-path [prd-path]
   ```
   
   - **IF any PRD has status 'invalid' or 'unvalidated':**
     - **YOU MUST output error:**
       
       ```
       ❌ Cannot add PRD to queue: [prd-path]
       
       Validation Status: [invalid/unvalidated]
       
       This PRD must be validated before it can be added to the orchestration queue.
       
       Next Steps:
       1. Validate: Run `30: prd-validate [prd-path]`
       2. If validation fails: Run `10: prd-workshop [prd-path]` to remediate
       3. After passing validation: Re-run this command to add to queue
       ```
     
     - **YOU MUST NOT proceed to add this PRD to the queue**
     - **YOU MUST ask if user wants to proceed with remaining valid PRDs (if multiple)**
   
   - **IF all PRDs have status 'valid':**
     - **YOU MUST output:** `✓ Step 0.3 complete - All PRD(s) validated (validation gate passed)`
     - **YOU MUST proceed to execute the queue add command**

---

## Prompt

You are managing the PRD processing queue. Add the specified PRD(s) to the queue.

**Run the Ruby script to add PRDs:**

```bash
ruby orch/orchestrator.rb queue add --paths "{{prd_paths}}"
```

**If only one PRD:**

```bash
ruby orch/orchestrator.rb queue add --prd-path "{{prd_paths}}"
```

**Interpret the YAML output:**

- `success: true` - PRD(s) added successfully
- `success: false` - PRD already in queue or error
- `position` - Queue position for the added item

**After adding, show queue status:**

```bash
ruby orch/orchestrator.rb queue status
```

**Display summary:**

```
✅ PRD Queue Updated
────────────────────
Added: [count]
Skipped: [count] (already in queue)

Queue Status:
- Pending: [n]
- In Progress: [n]
- Completed: [n]
```

---

## Usage Examples

Single PRD:

```
{{prd_paths}} = docs/prds/inquiry-system/inquiry-02-email-prd.md
```

Multiple PRDs:

```
{{prd_paths}} = docs/prds/inquiry-02-email-prd.md,docs/prds/inquiry-03-sms-prd.md
```
