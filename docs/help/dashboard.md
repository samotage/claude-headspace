# Dashboard

The dashboard is the main view of Claude Headspace, showing all your active Claude Code sessions.

## Layout

### Header

The header shows:

- **Navigation** - Links to Dashboard, Projects, Activity, Objective, Logging, Help, and Config pages
- **Status Counts** - How many agents are in each state (Input Needed, Working, Idle)
- **Headspace Indicator** - Traffic-light dot showing current frustration level (see [Headspace](headspace))
- **Connection Status** - Shows if real-time updates are connected (Live/Connecting/Offline)

### Project Groups

By default, agents are grouped by project. Each project group shows:

- **Traffic Light** - Overall project status (dots showing agent states)
- **Project Name** - The monitored project (click to open project detail page)
- **Brain Reboot** - Button to generate a brain reboot for the project
- **Active Count** - Number of active agents in this project
- **Staleness Badge** - Shows how recently the project had activity
- **Waypoint Preview** - Current project waypoint with [Edit] button

### Agent Cards

Each agent has a card showing:

- **Status Badge** - ACTIVE or IDLE
- **Persona Identity** - Agents with a [persona](personas) show their name and role (e.g., "Con — developer") instead of a truncated UUID
- **State Bar** - Visual indicator of current state (click to focus iTerm window)
- **Context Bar** - Shows context usage percentage; changes colour when [handoff](handoff) threshold is reached
- **Command Instruction** - The current prompt or command being worked on
- **Command Summary** - AI-generated summary of progress
- **Respond Widget** - Quick-action buttons and text input (only when awaiting input with tmux pane available)
- **Handoff Button** - Appears on persona agents when context usage exceeds the handoff threshold (see [Handoff](handoff))
- **Priority Score** - Used for sorting

### Recommended Next

When agents need attention, a highlighted panel at the top suggests which agent to focus on next. It shows:

- The agent's session ID and project
- Current state and priority score
- A rationale for why this agent is recommended
- Click to focus the iTerm window

### Respond Widget (Input Bridge)

When an agent is in the **Input Needed** (amber) state and a tmux pane is available, a respond widget appears on the card:

- **Quick-action buttons** — Parsed from numbered options in the prompt (e.g., "1. Yes", "2. No"). Click to send just the number.
- **Free-text input** — Type any response and click Send or press Enter.
- **Feedback** — Success shows a green highlight and toast. Errors show a toast with a specific message.

The widget only appears when the tmux pane is reachable. If the pane is not available, the card shows the normal state bar (click to focus iTerm) without the input widget.

See [Input Bridge](input-bridge) for setup instructions and details.

## Sorting

Use the sort controls to change how agents are displayed:

- **By Project** (default) - Groups agents under their projects
- **By Priority** - Flat list sorted by priority score
- **Kanban** - Groups agents by state (Input Needed, Working, Idle)

## Real-Time Updates

The dashboard updates automatically via Server-Sent Events (SSE). The connection indicator shows:

- **Green dot** - Connected, receiving updates
- **Gray dot** - Connecting or reconnecting
- **Red dot** - Connection lost

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `?` | Open help |
