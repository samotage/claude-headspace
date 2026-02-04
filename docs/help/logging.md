# Logging

The logging page provides a searchable, filterable view of all system events and LLM inference calls.

## Accessing Logging

Navigate to **>logging** in the header.

## Event Log

The default tab shows all system events.

### Filters

- **Project** - Filter events by project
- **Agent** - Filter events by agent
- **Event Type** - Filter by event type (e.g., hook_session_start, state_transition)

Click **Clear Filters** to reset.

### Event Types

Events are logged for:

- **Session lifecycle** - session_discovered, session_ended
- **State transitions** - state_transition (with from/to states)
- **Turn detection** - turn_detected
- **Hook events** - hook_session_start, hook_session_end, hook_user_prompt, hook_stop, hook_notification
- **Objective changes** - objective_changed
- **Notifications** - notification_sent

### Pagination

Events are shown 50 per page. Use the pagination controls at the bottom to navigate.

### Clearing Events

Click **Clear All** to delete all events from the database. This is irreversible.

## Inference Log

Click the **Inference** tab to view LLM inference calls.

### Filters

- **Search** - Full-text search across input text, result text, and purpose
- **Level** - Filter by inference level (turn, task, project, objective)
- **Model** - Filter by model used
- **Project** - Filter by project
- **Agent** - Filter by agent
- **Cached** - Filter by cache status (cached vs fresh)

### Columns

Each inference call shows:

- **Timestamp** - When the call was made
- **Agent** - Which agent triggered it
- **Level** - Turn, task, project, or objective
- **Model** - Which LLM model was used
- **Purpose** - What the call was for (e.g., turn_summary, frustration_detection)
- **Tokens** - Input and output token counts
- **Latency** - Round-trip time in milliseconds
- **Cost** - Estimated cost of the call
- **Status** - Success, cached, or error

### Clearing Inference Calls

Click **Clear All** to delete all inference call records.

## Real-Time Updates

New events appear automatically via SSE. The event log updates in real-time as hooks fire and state transitions occur.
