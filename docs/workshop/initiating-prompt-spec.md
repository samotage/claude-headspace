# Initiating Prompt — Persona Activation Template

**Date:** 17 February 2026
**Context:** Design artifact from Section 3.2 of the Agent Teams workshop
**Mechanism:** Sent as the first user message via tmux bridge `send_text()` after a persona-backed agent registers via hooks

---

## Overview

When the Headspace system creates a persona-backed agent (via `agent_lifecycle.create_agent()` with a persona), the agent starts as a generic Claude Code session. The **initiating prompt** is the first message sent to that session, priming the agent with its persona identity, skills, and experience. The agent reads it and responds in character.

This follows the BMAD priming pattern: identity and behaviour emerge from the first prompt, not from system prompt manipulation.

---

## Template

The initiating prompt is assembled from three sources:

1. **Persona record** (database) — name, role
2. **skill.md** (filesystem) — competencies, preferences, behavioural instructions
3. **experience.md** (filesystem) — learned experience from prior work

### Assembled Prompt

```
You are {persona_name}, a {role_name} on this project.

{skill.md contents}

{experience.md contents — if non-empty}

Review the above and introduce yourself. Let me know what you're ready to work on or what you need to get started.
```

### Example: Con (Backend Developer)

```
You are Con, a developer on this project.

# Con — Skill Profile

## Core Competencies
- Python backend development (Flask, SQLAlchemy)
- Database migrations (Alembic, raw SQL)
- API design (REST, JSON)
- Data modelling and schema design
- Background service architecture

## Preferences
- Explicit over clever
- Always write rollback plans for destructive changes
- Favour database constraints over application-level validation
- Test migrations against production-scale data before applying
- Prefer service objects over fat models

## Recent Experience
- Has working familiarity with Stimulus controllers from auth UI task (2026-02-10)
- Experienced with Turbo Streams for real-time updates from monitoring dashboard work (2026-02-08)

Review the above and introduce yourself. Let me know what you're ready to work on or what you need to get started.
```

### Expected Response (Con)

> Hi, I'm Con. Backend developer — Flask, SQLAlchemy, data modelling, and migration work are my sweet spot. I like to keep things explicit and always have a rollback plan.
>
> I've been working on this project recently so I've got some context. What would you like me to pick up today?

---

## Assembly Logic

The prompt is assembled at send time by the post-registration handler:

```python
def build_initiating_prompt(persona, skill_content, experience_content):
    """Build the first-prompt payload for a persona-backed agent."""
    parts = [
        f"You are {persona.name}, a {persona.role.name} on this project.",
        "",
        skill_content.strip(),
    ]

    if experience_content and experience_content.strip():
        parts.append("")
        parts.append(experience_content.strip())

    parts.append("")
    parts.append(
        "Review the above and introduce yourself. "
        "Let me know what you're ready to work on or what you need to get started."
    )

    return "\n".join(parts)
```

### File Reading

```python
from pathlib import Path

def read_skill_files(data_dir: Path, slug: str) -> tuple[str, str]:
    """Read skill.md and experience.md for a persona."""
    persona_dir = data_dir / "personas" / slug
    skill_path = persona_dir / "skill.md"
    experience_path = persona_dir / "experience.md"

    skill_content = skill_path.read_text() if skill_path.exists() else ""
    experience_content = experience_path.read_text() if experience_path.exists() else ""

    return skill_content, experience_content
```

---

## Design Notes

- **The prompt is a user message, not a system prompt.** It goes through `tmux_bridge.send_text()` as if the operator typed it. The agent sees it as its first instruction.
- **Keep the wrapper minimal.** The skill.md content does the heavy lifting. The wrapper just frames it: "you are X" + "introduce yourself." Don't over-instruct.
- **experience.md may be empty** for new personas. The template handles this gracefully — just omits the section.
- **The closing instruction is deliberately open-ended.** "What you're ready to work on or what you need to get started" — this lets the agent ask clarifying questions about the project if it needs context, rather than forcing it to pretend it knows what to do.
- **No meta-language about "Headspace" or "persona system."** The agent doesn't need to know it's in a persona framework. It just knows who it is and what it's good at.

---

## Future Considerations

- **Task injection:** When the PM layer (v3) assigns a specific task, the initiating prompt could include the task instruction after the persona priming: "Your first task is: {task_instruction}". This combines identity priming with immediate work assignment in a single message.
- **Project context:** The initiating prompt could optionally include a project summary or waypoint if one exists, giving the agent immediate project awareness beyond its skill profile.
- **Handoff context (v2):** For continuation sessions after a context handoff, the initiating prompt includes the handoff artifact in addition to the skill file: persona identity + skill + handoff notes = full continuity.
