# Full Cycle Sequence Diagram

## Session Lifecycle: CLI Start → Task Complete → Session End

```mermaid
sequenceDiagram
    actor User
    participant CLI as claude-headspace<br/>(bin/claude-headspace)
    participant Flask as Flask Server<br/>(localhost:5055)
    participant DB as Database
    participant CC as Claude Code<br/>(claude)
    participant Hook as notify-headspace.sh<br/>(bin/notify-headspace.sh)
    participant SSE as SSE Broadcaster
    participant Dash as Dashboard<br/>(Browser)

    Note over User,Dash: Phase 1: Session Registration (CLI)

    User->>CLI: claude-headspace start
    CLI->>CLI: Generate session_uuid (UUID v4)
    CLI->>CLI: Detect project path, name, git branch
    CLI->>CLI: Read ITERM_SESSION_ID env var

    CLI->>Flask: POST /api/sessions<br/>{session_uuid, project_path,<br/>project_name, branch, iterm_pane_id}

    Flask->>DB: Find or create Project<br/>(by path)
    DB-->>Flask: Project (id, name, path)

    Flask->>DB: Create Agent<br/>(session_uuid, project_id,<br/>claude_session_id=NULL,<br/>state=IDLE)
    DB-->>Flask: Agent (id)

    Flask->>SSE: Broadcast "session_created"
    SSE-->>Dash: SSE event → render agent card

    Flask-->>CLI: 201 {agent_id}

    CLI->>CLI: Set env vars:<br/>CLAUDE_HEADSPACE_URL<br/>CLAUDE_HEADSPACE_SESSION_ID

    CLI->>CC: Launch claude process<br/>(with env vars set)

    Note over User,Dash: Phase 2: Session Start Hook (Claude Code initializes)

    CC->>Hook: Hook fires: session-start<br/>(stdin: {session_id, cwd})
    Hook->>Flask: POST /hook/session-start<br/>{session_id, working_directory,<br/>headspace_session_id}

    Flask->>Flask: SessionCorrelator.correlate_session()<br/>Match headspace_session_id → Agent.session_uuid
    Flask->>DB: Link claude_session_id to Agent
    Flask->>DB: Update Agent.last_seen_at

    Flask-->>Hook: 200 {agent_id, method: "headspace_session_id"}
    Hook-->>CC: exit 0

    Note over User,Dash: Phase 3: User Submits a Command

    User->>CC: Type prompt + press Enter

    CC->>Hook: Hook fires: user-prompt-submit<br/>(stdin: {session_id})
    Hook->>Flask: POST /hook/user-prompt-submit<br/>{session_id, headspace_session_id}

    Flask->>Flask: SessionCorrelator → resolve Agent

    Flask->>DB: Create Task<br/>(agent_id, state=IDLE)
    Flask->>DB: Create Turn<br/>(task_id, actor=USER,<br/>intent=COMMAND)
    Flask->>DB: Transition Task:<br/>IDLE → COMMANDED → PROCESSING
    Flask->>DB: Create Event<br/>(type=HOOK_USER_PROMPT)
    Flask->>DB: Update Agent.last_seen_at

    Flask->>SSE: Broadcast "state_changed"<br/>{agent_id, new_state=PROCESSING}
    SSE-->>Dash: SSE event → card shows PROCESSING

    Flask-->>Hook: 200 {status: ok}
    Hook-->>CC: exit 0

    Note over User,Dash: Phase 4: Claude Responds (Turn Complete)

    CC->>CC: Process prompt...<br/>generate response

    CC->>Hook: Hook fires: stop<br/>(stdin: {session_id})
    Hook->>Flask: POST /hook/stop<br/>{session_id, headspace_session_id}

    Flask->>Flask: SessionCorrelator → resolve Agent

    Flask->>DB: Create Turn<br/>(task_id, actor=AGENT,<br/>intent=COMPLETION)
    Flask->>DB: Transition Task:<br/>PROCESSING → COMPLETE
    Flask->>DB: Set Task.completed_at = now
    Flask->>DB: Create Event<br/>(type=HOOK_STOP)
    Flask->>DB: Update Agent.last_seen_at
    Flask->>Flask: Send macOS notification<br/>(terminal-notifier)

    Flask->>SSE: Broadcast "state_changed"<br/>{agent_id, new_state=IDLE}
    SSE-->>Dash: SSE event → card shows IDLE

    Flask-->>Hook: 200 {status: ok}
    Hook-->>CC: exit 0

    CC-->>User: Display response

    Note over User,Dash: Phase 5: Session End

    User->>CC: Exit claude (/exit or Ctrl+C)

    CC->>Hook: Hook fires: session-end<br/>(stdin: {session_id})
    Hook->>Flask: POST /hook/session-end<br/>{session_id, headspace_session_id}

    Flask->>Flask: SessionCorrelator → resolve Agent
    Flask->>DB: Complete any active Task
    Flask->>DB: Set Agent.ended_at = now
    Flask->>DB: Create Event<br/>(type=HOOK_SESSION_END)

    Flask->>SSE: Broadcast "session_ended"
    SSE-->>Dash: SSE event → remove agent card

    Flask-->>Hook: 200 {status: ok}
    Hook-->>CC: exit 0

    CC-->>CLI: Process exits

    CLI->>Flask: DELETE /api/sessions/{session_uuid}
    Flask->>DB: Mark Agent ended (if not already)
    Flask-->>CLI: 200 OK

    CLI-->>User: Session complete
```

## Entity Relationship Summary

```mermaid
erDiagram
    Project ||--o{ Agent : "has many"
    Agent ||--o{ Task : "has many"
    Task ||--o{ Turn : "has many"
    Agent ||--o{ Event : "logged by"
    Task ||--o{ Event : "logged by"
    Turn ||--o{ Event : "logged by"

    Project {
        int id PK
        string name
        string path UK
        string github_repo
        string current_branch
        datetime created_at
    }

    Agent {
        int id PK
        string session_uuid UK "CLI-generated UUID"
        string claude_session_id "Linked via hooks"
        int project_id FK
        string iterm_pane_id
        datetime started_at
        datetime last_seen_at
        datetime ended_at "NULL while active"
    }

    Task {
        int id PK
        int agent_id FK
        enum state "IDLE COMMANDED PROCESSING AWAITING_INPUT COMPLETE"
        datetime started_at
        datetime completed_at
    }

    Turn {
        int id PK
        int task_id FK
        enum actor "USER or AGENT"
        enum intent "COMMAND ANSWER QUESTION COMPLETION PROGRESS"
        text text
        datetime timestamp
    }

    Event {
        int id PK
        datetime timestamp
        enum event_type "HOOK_SESSION_START HOOK_USER_PROMPT HOOK_STOP etc"
        int project_id FK
        int agent_id FK
        int task_id FK
        int turn_id FK
        jsonb payload
    }
```

## Task State Machine

```mermaid
stateDiagram-v2
    [*] --> IDLE : Task created
    IDLE --> COMMANDED : user-prompt-submit hook
    COMMANDED --> PROCESSING : immediate transition
    PROCESSING --> COMPLETE : stop hook
    PROCESSING --> AWAITING_INPUT : notification hook (input needed)
    AWAITING_INPUT --> COMMANDED : user-prompt-submit hook
    COMPLETE --> [*]
```

## Agent State Derivation

Agent does not store its own state. It is derived from the current task:

```mermaid
flowchart LR
    A[Agent.state] --> B{Has incomplete task?}
    B -->|No| C[IDLE]
    B -->|Yes| D[Current Task.state]
```
