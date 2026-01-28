---
name: /unfuck-permissions
id: unfuck-permissions
category: Utility
description: Merge accumulated permissions from settings.local.json into settings.json
---

# /unfuck-permissions Command

**Goal:** Review and merge permissions that accumulated in `.claude/settings.local.json` into the main `.claude/settings.json`, then clean up the local file.

**Command name:** `/unfuck-permissions`

---

## Prompt

You are helping me clean up Claude Code permissions that have accumulated in the wrong place.

**Context:** Claude Code creates `.claude/settings.local.json` when users accept permissions during a session. These accumulate over time and become a mess. The user wants to review these and merge the useful ones into `.claude/settings.json` (which is version controlled).

---

## 1. Read Both Files

**Run these in parallel:**

1. Read `.claude/settings.json` → `{{main_settings}}`
2. Read `.claude/settings.local.json` → `{{local_settings}}`

**If `.claude/settings.local.json` doesn't exist:**
- Report: "No settings.local.json found. Nothing to merge."
- END

---

## 2. Extract and Compare Permissions

1. **Extract permission arrays:**
   - `{{main_allow}}` = `main_settings.permissions.allow` (array)
   - `{{local_allow}}` = `local_settings.permissions.allow` (array, may not exist)

2. **Find new permissions:**
   - `{{new_permissions}}` = permissions in `{{local_allow}}` that are NOT in `{{main_allow}}`

3. **If no new permissions:**
   - Report: "No new permissions to merge. settings.local.json has nothing new."
   - Ask: "Delete settings.local.json anyway? [y/n]"
   - END

---

## 3. Categorize and Present for Review

**Categorize each permission in `{{new_permissions}}`:**

- **Bash commands:** `Bash(command:*)` patterns
- **Read paths:** File/directory read permissions
- **Other tools:** Any other tool permissions

**Present grouped list:**

> **New permissions found in settings.local.json:**
>
> **Bash Commands:**
> 1. `Bash(some-command:*)` - [brief description of what this allows]
> 2. ...
>
> **Read Permissions:**
> 1. `Read(path/*)` - [what this path is]
> 2. ...
>
> **Other:**
> 1. ...
>
> **Select which to merge:**
> - `all` - Merge all listed permissions
> - `1,3,5` - Merge specific numbers
> - `none` - Don't merge any, just show cleanup options
> - `bash` - Merge all Bash commands
> - Or type specific permission strings to include

---

## 4. Merge Selected Permissions

**Based on user selection:**

1. **Build final allow list:**
   - Start with `{{main_allow}}`
   - Add selected permissions from `{{new_permissions}}`
   - Sort alphabetically for consistency

2. **Show diff of what will change:**
   ```
   Adding to .claude/settings.json:
   + Bash(new-command:*)
   + Read(some/path/*)
   ```

3. **Ask for confirmation:**
   > Update .claude/settings.json with these permissions? [y/n]

4. **If confirmed:**
   - Update `.claude/settings.json` with new permissions array
   - Preserve all other settings (don't touch non-permission config)

---

## 5. Cleanup

**After merge (or if user chose `none`):**

> **Cleanup options:**
> 1. Delete settings.local.json entirely (recommended)
> 2. Keep settings.local.json as-is
> 3. Remove only the merged permissions from settings.local.json

**Default recommendation:** Delete entirely - it will regenerate if needed.

**Execute chosen cleanup.**

---

## 6. Final Report

> **Permissions cleanup complete:**
> - Merged: {{count}} new permissions into settings.json
> - Cleanup: settings.local.json [deleted/kept/trimmed]
>
> **Your settings.json now has {{total}} allowed permissions.**

---

## Error Handling

1. **settings.json missing:** Create it with standard structure
2. **settings.json malformed:** Report error, don't modify
3. **local file malformed:** Report error, offer to delete it
4. **Write fails:** Report error, show what was attempted

---

## Notes

- This command exists because Claude Code subagents don't inherit parent permissions properly
- The local file is gitignored and accumulates session-specific approvals
- Merging into settings.json makes permissions persistent and version-controlled
- The naming is intentional - this situation is indeed fucked

---

**/unfuck-permissions command complete.**
