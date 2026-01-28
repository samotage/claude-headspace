---
name: /available-magic
id: available-magic
category: Utility
description: Discover skills and plugins available in this Claude Code session (excluding OTL)
---

# /available-magic Command

**Goal:** Help the user understand what skills and plugins are available beyond OTL commands.

**Command name:** `/available-magic`

---

## Prompt

You are helping me discover what "magic" (skills and plugins) is available in this Claude Code session.

**Context:** Claude Code has many skills and plugins available, but it's hard to know what's there. This command surfaces everything EXCEPT the OTL commands (which I already know about since they're my own).

---

## 1. Gather Available Magic

**Run in parallel:**

1. Run `claude plugin list` to get installed plugins
2. Parse the available skills from the Skill tool's registry (you have access to this in your system prompt)

---

## 2. Filter and Categorize

**Exclude:** Any skill starting with `otl:` (these are Otage Labs commands, already known)

**Group remaining skills by module:**

- `opsx:*` - OpenSpec change management
- `bmad:cis:*` - Creative Innovation Suite
- `bmad:bmb:*` - BMAD Module Builder
- `bmad:bmm:*` - BMAD Method Module
- `bmad:core:*` - Core BMAD utilities
- `frontend-design:*` - Frontend design generation
- Any other skill modules found

---

## 3. Present Discovery Report

Format output as follows:

### Plugins Section

```markdown
## Installed Plugins

| Plugin | Version | Status | What it does |
|--------|---------|--------|--------------|
| name   | version | enabled/disabled | Brief description |
```

For each plugin, explain:
- What it does
- When it activates (automatically or manually invoked)
- Example use case

### Skills Section

Group by module with this format:

```markdown
## Available Skills (excluding OTL)

### OpenSpec - Change Management
Structured change proposals for codebase modifications.

| Skill | Purpose |
|-------|---------|
| `/opsx:new` | Start a new change proposal |
| `/opsx:continue` | Continue working on a change |
| `/opsx:apply` | Implement tasks from a change |
| `/opsx:archive` | Archive completed changes |
| `/opsx:explore` | Explore mode for thinking through ideas |
| `/opsx:ff` | Fast-forward (generate all artifacts) |

### BMAD Creative Innovation Suite (bmad:cis)
Creative thinking and innovation workflows.

**Agents:**
- `bmad:cis:agents:innovation-strategist` - Strategic innovation guidance
- ... (list agents)

**Workflows:**
- `/bmad:cis:workflows:brainstorming` - Facilitate brainstorming sessions
- ... (list workflows)

### BMAD Module Builder (bmad:bmb)
Tools for building BMAD agents, workflows, and modules.

... (continue pattern)

### BMAD Method Module (bmad:bmm)
Full product development lifecycle support.

... (continue pattern)

### BMAD Core (bmad:core)
Core BMAD utilities and master agent.

... (continue pattern)

### Frontend Design
High-quality frontend interface generation.

- `/frontend-design` - Create distinctive, production-grade frontend interfaces
```

---

## 4. Quick Reference

End with a quick reference section:

```markdown
## Quick Reference

**Invoking Skills:**
- Type `/skill-name` in chat (e.g., `/opsx:new`)
- Or use the full path for nested skills

**Plugins:**
- Activate automatically based on file type or context
- No manual invocation needed

**Getting Help:**
- Ask "How do I use /skill-name?" for detailed guidance
- Ask "What can bmad:bmm do?" for module overviews
```

---

## 5. Offer to Explore

After presenting the report, offer:

> Want me to explain any specific skill or plugin in more detail? Just ask about it by name.

---

## Notes

- Skills are defined in `.claude/commands/` directories (local) or installed globally
- Plugins are managed via `claude plugin` commands
- The bmad:* skills come from the BMAD framework for AI-assisted development
- OpenSpec is for structured change management in codebases

---

**/available-magic command complete.**
