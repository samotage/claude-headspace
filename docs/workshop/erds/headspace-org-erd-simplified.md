# Claude Headspace — Organisational Model ERD (Simplified)

**Date:** 16 February 2026
**Status:** Simplified view — entities and relationships only, no field details
**Note:** Agent, Task, and Turn are existing Headspace 3.1 entities. SkillFile and ExperienceLog are version-managed files in the repo, not database tables. See headspace-org-erd-full.md for field-level detail.

---

```mermaid
erDiagram
    Persona ||--o{ SkillFile : "has (file ref)"
    Persona ||--o{ ExperienceLog : "has (file ref)"
    Persona ||--o{ PositionAssignment : "fills"

    Organisation ||--o{ Role : "defines"
    Organisation ||--o{ Position : "contains"

    Position }o--|| Role : "has"
    Position }o--o| Position : "reports to"

    PositionAssignment }o--|| Position : "for"

    Agent }o--|| Persona : "driven by"
    Agent }o--|| Position : "represents"
    Agent }o--o| Agent : "continues from"
    Agent ||--o{ Task : "works on"
    Agent ||--o| Handoff : "produces"

    Task ||--o{ Turn : "contains"
```

---

## Entity Summary

| Entity | Type | New or Existing |
|--------|------|-----------------|
| Persona | DB table | New |
| Organisation | DB table | New |
| Role | DB table | New |
| Position | DB table | New (self-referential hierarchy) |
| PositionAssignment | DB join table | New (lifecycle via timestamps, availability derived from Agent) |
| Handoff | DB table | New (content container, belongs to outgoing agent) |
| Agent | DB table | Existing — extended with persona_id, position_id, previous_agent_id (self-ref chain) |
| Task | DB table | Existing — unchanged |
| Turn | DB table | Existing — unchanged |
| SkillFile | File reference | Version-managed file in repo |
| ExperienceLog | File reference | Version-managed file in repo |
