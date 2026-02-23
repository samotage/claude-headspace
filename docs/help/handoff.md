# Handoff

Handoff enables seamless context transfer between Claude Code agents. When a persona agent approaches its context limit, an operator can trigger a handoff — the outgoing agent writes a first-person summary of its work, then a successor agent picks up where it left off with the same persona.

## When to Use Handoff

Handoff is designed for long-running work that exceeds a single agent's context window. Common triggers:

- **Context limit** — The agent has used most of its context capacity
- **Shift boundary** — Scheduled rotation of agent sessions
- **Task boundary** — Natural handover point between phases of work

## Eligibility

The handoff button only appears on an agent card when **all** of these conditions are met:

1. The agent has a **persona** assigned (anonymous agents cannot hand off)
2. The agent's **context usage** is at or above the handoff threshold (default: 80%)
3. The agent is **active** (not ended)
4. The agent has a **tmux pane** available

When eligible, the context bar on the agent card changes colour and a "Handoff" button appears.

## Triggering a Handoff

### From the Dashboard

Click the **Handoff** button on an eligible agent card. The button shows a handoff icon and triggers the flow immediately.

### Via API

```bash
curl -X POST https://your-server:5055/api/agents/{id}/handoff \
  -H "Content-Type: application/json" \
  -d '{"reason": "context_limit"}'
```

The `reason` field is optional (defaults to `"manual"`). Common values: `context_limit`, `shift_end`, `task_boundary`.

## What Happens During Handoff

The handoff flow is fully automated after you trigger it:

### 1. Validation

The system checks that the agent:
- Exists and is active
- Has a persona assigned
- Has a reachable tmux pane
- Does not already have a handoff in progress

If any check fails, you receive an error message explaining why.

### 2. Instruction Delivery

The system sends a message to the outgoing agent via tmux, instructing it to write a handoff document. The instruction asks the agent to cover:

- Current work in progress
- Progress and completion status
- Key decisions made
- Blockers or unresolved issues
- Files modified
- Recommended next steps

The agent then calls `/exit` to end its session.

### 3. Handoff File

The outgoing agent writes its handoff document to:

```
data/personas/{slug}/handoffs/{YYYYMMDDTHHmmss}-{agent_id}.md
```

This file is a first-person account of the agent's work — written by the agent itself, not generated from metadata. This ensures the document captures context and nuance that only the working agent knows.

### 4. File Verification

When the outgoing agent's stop hook fires, the system verifies the handoff file:
- File must exist at the expected path
- File must be non-empty

If verification fails, the handoff halts and an error is surfaced.

### 5. Database Record

A Handoff record is created with:
- The outgoing agent's ID
- The trigger reason
- The handoff file path
- An injection prompt for the successor

### 6. Outgoing Agent Shutdown

The outgoing agent is gracefully shut down. Its `ended_at` timestamp is set.

### 7. Successor Creation

A new agent is created with:
- The same persona slug as the outgoing agent
- A `previous_agent_id` linking to the outgoing agent

### 8. Successor Bootstrap

When the successor agent starts and registers via hooks:
1. **Skill injection** happens first — the persona's `skill.md` is delivered
2. **Handoff injection** follows — the successor receives a prompt telling it to read the handoff file and continue the work

The successor reads the handoff document using its tools and picks up where the predecessor left off.

## Handoff Threshold

The context threshold that enables handoff eligibility is configurable:

```yaml
context_monitor:
  handoff_threshold: 80    # Percentage of context used
```

At 80% (default), agents with personas become handoff-eligible. The context bar on the dashboard card changes appearance to indicate this.

## Handoff History

Each handoff creates a file in the persona's `handoffs/` directory. Over time, this builds a chronological record of work across agent generations:

```
data/personas/developer-con-1/handoffs/
  20260222T091500-00000042.md    # Agent #42's handoff
  20260222T143000-00000043.md    # Agent #43's handoff
```

These files can be reviewed to understand the progression of work across multiple agent sessions.

## Error Handling

Every step in the handoff pipeline surfaces errors to the operator:

| Error | Meaning | Resolution |
|-------|---------|------------|
| **Agent not found** | The agent ID doesn't exist | Check the agent ID |
| **Agent is not active** | The agent has already ended | No handoff needed |
| **Agent has no persona** | Anonymous agents can't hand off | Assign a persona first |
| **No tmux pane** | The tmux pane is not available | Check if the session is running |
| **Handoff already in progress** | A handoff was already triggered | Wait for it to complete |
| **Handoff file not found** | The outgoing agent didn't write the file | The agent may have exited before completing the document |
| **Handoff file empty** | The file exists but has no content | Same as file not found — treated as failure |
| **Successor creation failed** | Could not start the replacement agent | Check server logs; the Handoff DB record is preserved |

Errors are broadcast via SSE to the dashboard and logged for debugging.

## Limitations

- **Persona required** — Only agents with personas can participate in handoff. Anonymous agents are not supported.
- **tmux required** — The handoff instruction is delivered via tmux send-keys. Agents without tmux panes cannot receive handoff instructions.
- **One handoff at a time** — An agent can only have one active handoff. Duplicate triggers return a 409 conflict.
- **File-based** — The handoff document is a local file. It is not replicated or backed up automatically.
- **Agent-authored** — The quality of the handoff depends on the outgoing agent's response. If the agent produces a poor summary, the successor has less context.

## Related Topics

- [Personas](personas) — Setting up and managing agent personas
- [Dashboard](dashboard) — Agent cards and handoff button
- [Input Bridge](input-bridge) — Responding to agents via the dashboard
- [Configuration](configuration) — Adjusting handoff threshold and other settings
