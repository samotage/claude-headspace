# Claude Headspace v3.1: Conceptual Overview

**Date:** 28.1.26  
**Version:** 3.1 (Terminology aligned)

---

## 1. Overall Concept & Dashboard

A tool for managing agentic tasks working towards an **objective**.

It works across multiple **projects**, each having a number of **agents** performing **tasks**.

The state of each agent's tasks is monitored and prioritised according to how it contributes towards the **objective**.

The system supports a **brain_reboot** of each project based on its **progress_summary** (derived from git history) and **waypoint** (the path ahead). The brain_reboot helps the user get back up to speed on a stale project and is used to prioritise and align with the objective.

The system presents a **dashboard** that shows the **objective** above a **Kanban**-styled listing of each agent working on the project. Each agent's card has detail of its current **status**, **task**, **prioritisation**, and **turn**, together with the ability to click the agent's card to go to the agent's **iTerm2 terminal** or see the detail of the tasks performed by that agent.

Each turn of the agent is monitored and when complete its task is summarised by an **inference call** and prioritised according to its contribution towards the objective.

---

## 2. System Integration & Automation

The system reflects on agent **commit** activity and updates the **progress_summary**.

The **git history** of the project feeds the **progress_summary**, which forms part of the **brain_reboot** - a view of the project that summarises what's been done, and what's next.

The **progress_summary** and **waypoint** are **repo artifacts** stored in each target project's repository (not in Claude Headspace itself).

The system integrates with **Claude Code**. It reads the **jsonl** files in the **.claude/projects** root directory and watches these to update the agent's task and turn information.

The system maintains **settings** for each project, such as the **github repo** and the actual **project path** interpreted from the Claude Code projects path information.

The system works with **iTerm2** and uses **AppleScript** to focus on iTerm2 terminals.

The system has the ability to send **text** into the iTerm2 terminal.

The **Claude Code session** uses **hooks** to notify the system of **exits**.

The system uses **SSE** (Server-Sent Events) to send real-time updates to the browser powering the dashboard.

The system sends **system notifications** to the host macOS notification feature.

---

## 3. Inference, Logging & Setup

The system maintains **logging** of inference calls via **OpenRouter**.

Logs include **Turn.text** for each turn.

Logs are organised by:
- **Project**
- **Agent**
- **Command**
- **Turn**

...and used to calculate summaries at each level.

The system uses **inference calls** at four levels:

| Level | Purpose | Model (typical) |
|-------|---------|-----------------|
| **turn** | Summarise individual turn for dashboard display and prioritisation | Haiku |
| **command** | Summarise completed command outcome | Haiku |
| **project** | Generate progress_summary, brain_reboot, recent activity summary | Sonnet |
| **objective** | Cross-project prioritisation, alignment to objective | Sonnet |

The system has **scripts** for initialising Claude Code sessions to link them.

The **brain_reboot**, **waypoint**, and **progress_summary** belong to each target project's repository, which the system has access to.

The system is able to **set up** the project with all the necessary artifacts (waypoint, progress_summary, brain_reboot, Claude project settings for hooks, etc.).

The system has **documentation** and **help**, which is searchable.

---

## 4. State Model

This section defines the core mechanics of how Agents, Commands, and Turns interact.

### 4.1 Hierarchy

```
Objective (global singleton)
    │
    └── Project (1:N)
            │
            └── Agent (1:N per project, concurrent allowed)
                    │
                    └── Command (1:N per agent, sequential)
                            │
                            └── Turn (1:N per command)
```

### 4.2 Command State Machine

A Command progresses through the following states:

```
                                ┌─────────────────────────────────┐
                                │                                 │
                                ▼                                 │
┌──────────┐    user command   ┌───────────┐                      │
│          │ ─────────────────▶│           │                      │
│   idle   │                   │ commanded │                      │
│          │◀─┐                │           │                      │
└──────────┘  │                └─────┬─────┘                      │
              │                      │                            │
              │                      │ agent starts processing    │
              │                      ▼                            │
              │                ┌────────────┐                     │
              │                │            │◀────────────────┐   │
              │                │ processing │                 │   │
              │                │            │─────────┐       │   │
              │                └─────┬──────┘         │       │   │
              │                      │                │       │   │
              │     agent completes  │                │       │   │
              │                      ▼                │       │   │
              │                ┌──────────┐           │       │   │
              │                │          │   agent   │       │   │
              │                │ complete │   asks    │       │   │
              │                │          │  question │       │   │
              │                └────┬─────┘           │       │   │
              │                     │                 ▼       │   │
              │                     │          ┌────────────┐ │   │
              │  command complete      │          │  awaiting  │ │   │
              └─────────────────────┘          │   input    │─┘   │
                                               │            │     │
                                               └──────┬─────┘     │
                                                      │           │
                                                      │ user      │
                                                      │ answers   │
                                                      └───────────┘
```

### 4.3 Turn Model

Each Turn represents one exchange in the conversation.

```
Turn
├── actor: user | agent
├── text: (the content of the turn)
├── intent: command | answer | question | completion | progress | end_of_command
└── timestamp
```

**Actor values:**
- `user` - the human operator
- `agent` - Claude Code

**Intent values:**
- `command` - user initiates a task (starts a new Command)
- `answer` - user responds to agent's question
- `question` - agent asks user for clarification
- `progress` - agent reports intermediate progress
- `completion` - agent signals task is done (ends the Command)
- `end_of_command` - agent explicitly signals end of command (also ends the Command)

### 4.4 Turn Intent to Command State Mapping

| Current Command State | Turn Actor | Turn Intent | New Command State |
|--------------------|------------|-------------|----------------|
| idle | user | command | commanded |
| commanded | agent | progress | processing |
| commanded | agent | question | awaiting_input |
| commanded | agent | completion | complete |
| commanded | agent | end_of_command | complete |
| processing | agent | progress | processing |
| processing | agent | question | awaiting_input |
| processing | agent | completion | complete |
| processing | agent | end_of_command | complete |
| processing | user | answer | processing |
| awaiting_input | user | answer | processing |
| awaiting_input | agent | completion | complete |
| awaiting_input | agent | end_of_command | complete |
| complete | - | - | idle (command ends) |

### 4.5 Command Lifecycle Summary

```
COMMAND START
    │
    │  Turn: { actor: user, intent: command }
    │
    ▼
[ ... multiple turns ... ]
    │
    │  Turn: { actor: agent, intent: completion }
    │
    ▼
COMMAND END
```

A Command:
- **Starts** with: `actor: user, intent: command`
- **Ends** with: `actor: agent, intent: completion`

### 4.6 Agent State

An Agent's state is derived from its current Command:

```
Agent.state = current_command.state
```

If no active command, Agent.state = `idle`.

---

## 5. Core Domain Model

```
Objective (global singleton)
│
├── guides prioritisation of →
│
└── Project (1:N)
    ├── name
    ├── path
    ├── goal
    ├── context (tech_stack, target_users)
    ├── brain_reboot_path (points to docs/brain_reboot/ in target repo)
    ├── state (status)
    │
    └── has many → Agent (1:N per project, concurrent allowed)
                   │
                   ├── 1:1 with TerminalSession (iTerm2 pane)
                   ├── state (derived from current command)
                   │
                   └── has many → Command (1:N per agent, sequential)
                                  │
                                  ├── state: idle | commanded | processing 
                                  │          | awaiting_input | complete
                                  │
                                  └── has many → Turn (1:N per command)
                                                 │
                                                 ├── actor: user | agent
                                                 ├── text
                                                 ├── intent: command | answer | question 
                                                 │           | completion | progress | end_of_command
                                                 ├── timestamp
                                                 │
                                                 └── triggers → InferenceCall (0:N)
                                                                ├── level: turn | command 
                                                                │          | project | objective
                                                                ├── purpose
                                                                ├── model
                                                                ├── input_hash
                                                                ├── result
                                                                └── timestamp
```

### External Data Source

```
GitRepository (per project)
├── recent_commits → feeds → progress_summary (via LLM)
├── files_changed → enriches → Command context
└── commit_messages → informs → progress narrative
```

---

## 6. Repo Artifacts

Repo artifacts are stored in each **target project's repository** (e.g., RAGlue, ICU Solarcam), not in Claude Headspace itself. Claude Headspace reads from and writes to these locations.

### 6.1 Directory Structure

```
<target_project>/
└── docs/
    └── brain_reboot/
        ├── waypoint.md                      (current)
        ├── progress_summary.md              (current)
        └── archive/
            ├── waypoint_2025-01-15.md       (timestamped)
            ├── waypoint_2025-01-28.md       (timestamped)
            ├── progress_summary_2025-01-10.md
            ├── progress_summary_2025-01-20.md
            └── ...
```

### 6.2 Artifact Definitions

**waypoint.md** - The path ahead. Contains:
- `next_up` - immediate next steps
- `upcoming` - coming soon
- `later` - future work
- `not_now` - parked/deprioritised

**progress_summary.md** - LLM-generated narrative of what's been completed, derived from git commit history.

**brain_reboot** - The combined view (waypoint + progress_summary) that enables rapid mental context restoration when returning to a stale project.

### 6.3 Archiving

When artifacts are updated, the previous version is moved to the `archive/` directory with a date timestamp appended to the filename (e.g., `waypoint_2025-01-28.md`).

---

## 7. Glossary

| Term | Definition |
|------|------------|
| **objective** | Global singleton. The overarching goal that guides prioritisation across all projects. |
| **project** | A codebase/repo being worked on. Has agents, tasks, and repo artifacts. |
| **agent** | A Claude Code instance working on a project, linked to an iTerm2 terminal session. |
| **command** | A unit of work initiated by a user command and completed by an agent completion. |
| **turn** | A single exchange in a command conversation - either user or agent speaking. |
| **actor** | Who is speaking in a turn: `user` or `agent`. |
| **intent** | The purpose of a turn: `command`, `answer`, `question`, `progress`, `completion`, `end_of_command`. |
| **text** | The content of a turn. |
| **brain_reboot** | A view combining waypoint and progress_summary to rapidly restore mental context. |
| **waypoint** | The path ahead - next_up, upcoming, later, not_now. |
| **progress_summary** | LLM-generated narrative of completed work, derived from git history. |
| **repo artifacts** | Markdown files stored in the target project's repository (waypoint.md, progress_summary.md). |
| **inference call** | An LLM API call for summarisation or prioritisation, categorised by level. |
| **level** | The scope of an inference call: `turn`, `task`, `project`, or `objective`. |
