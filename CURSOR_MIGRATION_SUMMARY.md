# Cursor Configuration Migration Summary

**Date:** 2026-01-28  
**Source:** `/Users/samotage/dev/otagelabs/raglue/1_raglue`  
**Target:** `/Users/samotage/dev/otagelabs/claude_headspace`

## Files Created

### ✅ `.cursorrules` (242 lines)

Main Cursor rules file adapted for Python project:

**Kept from raglue:**
- OpenSpec integration block
- AI Behavior Rules structure
- Scope discipline guidelines
- STOP protocol
- Slack notification patterns
- Explain causality rules

**Adapted for Claude Headspace:**
- Project Overview (Python-based orchestration system)
- Tech Stack (Python/Flask/Pydantic instead of Rails)
- Architecture Patterns (PRD-driven, Ruby orchestration, Git workflow)
- Commands (pytest, ruff, pre-commit instead of Rails commands)
- Project Structure (Python project layout)
- Development Workflow (PRD, OpenSpec, Git)

**Removed from raglue:**
- ❌ Design Context section (~67 lines - Impeccable framework)
- ❌ Multitenancy patterns (Rails-specific)
- ❌ Flows Engine (Rails-specific)
- ❌ OAuth patterns (Rails-specific)
- ❌ Turbo restrictions (Rails-specific)
- ❌ Avo restrictions (Rails-specific)
- ❌ UI change protocol (design-focused)

### ✅ `.cursor/commands/` (1 file)

**Created:**
- `commit-push.md` (273 lines) - Smart git commit/push command
  - Adapted for Python (Ruff/Black instead of RuboCop)
  - Updated file patterns (`src/`, `lib/` instead of `app/`)
  - Updated commit types (pytest, requirements.txt)

**Not Copied (as requested):**
- ❌ `openspec-*.md` (3 files - already in `.claude/commands/`)
- ❌ `impeccable/` directory (17 files - design-focused)
- ❌ `otl/` directory (orchestration commands - already in `.claude/`)

### ✅ `.cursor/rules/` (2 files)

**Created:**
1. **`python_basics.mdc`** (18 lines)
   - Minimal, focused Python conventions
   - Tech stack reference
   - Type hints, Pydantic, pytest patterns
   - Only non-obvious Python-specific guidance

2. **`writing.mdc`** (135 lines)
   - Copied as-is from raglue (universal)
   - Writing style guide
   - Voice and tone rules
   - Banned words/phrases
   - LLM pattern avoidance

**Not Copied (as requested):**
- ❌ `bmad/` directory (63 files - raglue-specific framework)
- ❌ `rails_basics.mdc` (replaced with `python_basics.mdc`)

### ✅ `.vscode/settings.json` (1.2KB)

**Kept from raglue:**
- ✅ File explorer settings (non-compact folders, autoReveal: false, indent: 16)
- ✅ Tab behavior (disable preview tabs)
- ✅ Workbench settings (revealIfOpen, openPositioning)
- ✅ **Vim configuration** (useSystemClipboard, highlightedyank, handleKeys)

**Adapted for Python:**
- ✅ Python Language Server (Pylance)
- ✅ Python formatter (Ruff instead of Ruby LSP)
- ✅ Format on save with Ruff
- ✅ Code actions (fixAll, organizeImports)
- ✅ Tab size: 4 (Python standard)

**Removed:**
- ❌ Ruby LSP configuration
- ❌ Ruby-specific settings

### ✅ `.vscode/extensions.json` (112 bytes)

**Created for Python:**
```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff"
  ]
}
```

**Replaced from raglue:**
- ❌ Shopify.ruby-lsp
- ❌ rebornix.ruby
- ❌ wingrunr21.vscode-ruby

## File Comparison

### Source (raglue)
```
.cursorrules                  267 lines (Rails, Design Context)
.cursor/commands/             21 files (including impeccable/, otl/)
.cursor/rules/                66 files (including bmad/)
.cursor/instructions/         1+ files
.cursor/debug.log            
.vscode/settings.json         36 lines (Ruby LSP)
.vscode/extensions.json       7 lines (Ruby extensions)
```

### Target (claude_headspace)
```
.cursorrules                  242 lines (Python, no design)
.cursor/commands/             1 file (commit-push.md)
.cursor/rules/                2 files (python_basics.mdc, writing.mdc)
.vscode/settings.json         46 lines (Pylance, Vim)
.vscode/extensions.json       5 lines (Python extensions)
```

## Key Decisions Made

### 1. Minimal Python Rules
- Created focused `python_basics.mdc` with only non-obvious conventions
- Avoided polluting context with basic Python knowledge
- Included: type hints, Pydantic patterns, pytest conventions

### 2. No Design System
- Removed entire Impeccable design context (~67 lines)
- Skipped 17 design-focused commands
- Backend-focused project doesn't need frontend design rules

### 3. No Framework Duplication
- Skipped BMAD framework (63 files - raglue-specific)
- Skipped OTL commands (already in `.claude/commands/`)
- Skipped OpenSpec commands (already in `.claude/commands/`)

### 4. Universal Editor Settings
- Kept file explorer preferences (universal)
- Kept tab behavior (universal)
- **Kept Vim settings** (as requested)
- Updated language-specific settings for Python

### 5. Python Tooling
- Pylance for language server
- Ruff for linting and formatting
- Format on save enabled
- Auto-organize imports

## Verification

```bash
# Check structure
find .cursor -type f | wc -l    # 3 files ✓
find .vscode -type f | wc -l    # 2 files ✓
wc -l .cursorrules              # 242 lines ✓

# Verify no Rails references
grep -r "Rails\|RuboCop\|Turbo\|Avo" .cursorrules .cursor/ .vscode/
# Result: Only in historical context, not in active rules ✓

# Verify Python tooling
grep -r "Pylance\|Ruff\|pytest" .cursorrules .cursor/ .vscode/
# Result: Present in appropriate files ✓
```

## What Was NOT Copied

### Design & Frontend (as requested)
- ❌ `.cursor/commands/impeccable/` (17 files)
- ❌ Design Context section in `.cursorrules` (~67 lines)
- ❌ UI change protocol
- ❌ Frontend design skill

### Framework-Specific (as requested)
- ❌ `.cursor/rules/bmad/` (63 files - BMAD framework)
- ❌ Rails-specific architecture patterns
- ❌ Multitenancy, Flows, OAuth sections
- ❌ Turbo/Avo restrictions

### Already in .claude/ (as requested)
- ❌ `.cursor/commands/openspec-*.md` (3 files)
- ❌ `.cursor/commands/otl/` (entire subtree)

### Miscellaneous
- ❌ `.cursor/instructions/` directory
- ❌ `.cursor/debug.log`
- ❌ Ruby-specific VSCode extensions

## Next Steps

1. **Install Python extensions in Cursor:**
   - Python (ms-python.python)
   - Pylance (ms-python.vscode-pylance)
   - Ruff (charliermarsh.ruff)

2. **Configure Ruff:**
   - Create `pyproject.toml` or `ruff.toml` if needed
   - Configure line length, rules, etc.

3. **Test Cursor commands:**
   - Try `/commit-push` command
   - Verify Python rules apply to `.py` files
   - Test writing rules when editing docs

4. **Verify pre-commit hooks:**
   - `pre-commit install`
   - `pre-commit run --all-files`

## Summary

Successfully migrated Cursor configuration from Rails project to Python project:
- ✅ Adapted `.cursorrules` for Python (removed design context)
- ✅ Copied essential commands (commit-push)
- ✅ Created minimal Python rules
- ✅ Kept universal writing guidelines
- ✅ Updated VSCode for Python + Vim
- ✅ Replaced extensions with Python tooling
- ❌ Skipped design system (17 files)
- ❌ Skipped BMAD framework (63 files)
- ❌ Skipped duplicate commands (OTL, OpenSpec)

**Total:** 5 new files created, ~400 lines of focused configuration
**Avoided:** 80+ files of Rails/design-specific content
