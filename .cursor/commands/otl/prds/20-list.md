---
name: '20: prd-list'
description: 'Display all PRDs in the system with their metadata'
---

# 20: List PRDs

**Command name:** `20: prd-list`

**Purpose:** Show pending PRDs that are awaiting build (not in `done/` directories). Provides filename and 18-token summary for each PRD.

---

## Prompt

You are a PRD queue inspector. Your job is to scan the `docs/prds/` directory and list all pending PRDs that are ready for the orchestration engine.

**PRD Location Convention:**

- Pending PRDs: `docs/prds/{subsystem}/{prd-name}.md`
- Completed PRDs: `docs/prds/{subsystem}/done/{prd-name}.md`
- Root-level PRDs: Ignored (e.g., `walking-skeleton-prd.md`)

---

## Step 1: Scan for Pending PRDs

```bash
# Find all PRD files in subsystem folders, excluding done/ directories
find docs/prds -mindepth 2 -name "*.md" -type f | grep -v "/done/" | sort
```

---

## Step 2: Generate Summaries and Read Validation Status

For each PRD found:

1. **Read the file** to extract the Executive Summary or first substantive paragraph
2. **Generate 18-token summary** that captures the core purpose
3. **Read validation status** from PRD frontmatter using:
   ```bash
   ruby orch/prd_validator.rb status --prd-path [prd-path]
   ```
4. **Read validation metadata** (if status is valid or invalid) using:
   ```bash
   ruby orch/prd_validator.rb metadata --prd-path [prd-path]
   ```
5. **Group by subsystem** for organized output

**Validation Status Badges:**

- `[✓ Valid - Jan 2]` - PRD passed validation (show date from validated_at)
- `[✗ Invalid - 3 errors]` - PRD failed validation (show error count)
- `[⊗ Unvalidated]` - PRD not yet validated

---

## Step 3: Output Format

Present results in this format:

```
## Pending PRDs Awaiting Build

### {subsystem_1}/

- **{prd-filename-1}.md** [✓ Valid - Jan 2]
  `docs/prds/{subsystem_1}/{prd-filename-1}.md`
  "{18-token summary extracted from PRD content}"

- **{prd-filename-2}.md** [⊗ Unvalidated]
  `docs/prds/{subsystem_1}/{prd-filename-2}.md`
  "{18-token summary extracted from PRD content}"

### {subsystem_2}/

- **{prd-filename-3}.md** [✗ Invalid - 2 errors]
  `docs/prds/{subsystem_2}/{prd-filename-3}.md`
  "{18-token summary extracted from PRD content}"

---

**Total:** {N} PRDs pending across {M} subsystems
**Validation Status:** {X} valid, {Y} invalid, {Z} unvalidated

**Next Steps:**
- For unvalidated PRDs: `30: prd-validate docs/prds/{subsystem}/{prd-name}.md`
- For invalid PRDs: `10: prd-workshop docs/prds/{subsystem}/{prd-name}.md` (remediate)
- Sequence: `40: prd-sequence` for recommended build order
- Add valid PRDs to queue: `ruby orch/orchestrator.rb queue add --prd-path [path]`
```

---

## Example Output

```
## Pending PRDs Awaiting Build

### beta_signups/

- **beta-signups-05-track-invitations-prd.md** [✓ Valid - Jan 2]
  `docs/prds/beta_signups/beta-signups-05-track-invitations-prd.md`
  "Track invitation status changes and link beta signups to sent invitations for admin visibility"

- **beta-signups-06-status-tracking-prd.md** [⊗ Unvalidated]
  `docs/prds/beta_signups/beta-signups-06-status-tracking-prd.md`
  "Enable status tracking directly on beta signup records with automatic synchronization"

### campaigns/

- **campaign-visits-4-details-performance.md** [✓ Valid - Jan 1]
  `docs/prds/campaigns/campaign-visits-4-details-performance.md`
  "Add detailed performance metrics and visitor analytics to campaign admin pages"

- **google-analytics-integration.md** [✗ Invalid - 3 errors]
  `docs/prds/campaigns/google-analytics-integration.md`
  "Integrate Google Analytics tracking with campaign visits for cross-platform attribution"

---

**Total:** 4 PRDs pending across 2 subsystems
**Validation Status:** 2 valid, 1 invalid, 1 unvalidated

**Next Steps:**
- For unvalidated PRDs: `30: prd-validate docs/prds/{subsystem}/{prd-name}.md`
- For invalid PRDs: `10: prd-workshop docs/prds/{subsystem}/{prd-name}.md` (remediate)
- Sequence: `40: prd-sequence` for recommended build order
- Add valid PRDs to queue: `ruby orch/orchestrator.rb queue add --prd-path [path]`
```

---

## Empty State

If no pending PRDs are found:

```
## Pending PRDs Awaiting Build

✓ No pending PRDs found.

All PRDs are either:
- Completed (in `done/` subdirectories)
- Not yet created

**Next Steps:**
- Create a new PRD: `/prds/10-workshop`
- Check completed PRDs in `docs/prds/{subsystem}/done/`
```

---

## Summary Generation Guidelines

When generating the 18-token summary:

1. **Extract from Executive Summary** if present
2. **Fall back to first paragraph** of Context/Purpose section
3. **Focus on the WHAT** - what capability is being built
4. **Avoid implementation details** - no mention of specific technologies
5. **Keep it action-oriented** - what the feature does, not how

**Good summaries:**

- "Track invitation status changes and link beta signups to sent invitations for admin visibility"
- "Add real-time campaign performance dashboard with visitor analytics and conversion tracking"

**Bad summaries:**

- "This PRD describes the implementation of a new feature using Rails and Hotwire" (too generic, implementation-focused)
- "Beta signups" (too short, not descriptive)

---

## Notes

- This command is read-only; it does not modify any files
- Root-level PRDs (like `walking-skeleton-prd.md`) are intentionally excluded
- The 18-token limit is approximate; prioritize clarity over strict count
- Subsystems are auto-detected from the directory structure

---

**PRD List complete.**

