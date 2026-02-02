# Dashboard

The dashboard is the main view of Claude Headspace, showing all your active Claude Code sessions.

## Layout

### Header

The header shows:

- **Navigation** - Links to Dashboard, Objective, Logging, and Config pages
- **Status Counts** - How many agents are in each state
- **Connection Status** - Shows if real-time updates are connected

### Project Groups

By default, agents are grouped by project. Each project group shows:

- **Traffic Light** - Overall project status (red/yellow/green)
- **Project Name** - The monitored project
- **Active Count** - Number of active agents in this project
- **Waypoint Preview** - Current project waypoint with [Edit] button

### Agent Cards

Each agent has a card showing:

- **Status Badge** - ACTIVE or IDLE
- **Session ID** - Unique identifier
- **State Bar** - Visual indicator of current state (click to focus iTerm window)
- **Task Instruction** - The current prompt or task being worked on
- **Task Summary** - AI-generated summary of progress
- **Respond Widget** - Quick-action buttons and text input (only when awaiting input with commander available)
- **Priority Score** - Used for sorting

### Respond Widget (Input Bridge)

When an agent is in the **Input Needed** (amber) state and the session was launched with `claudec`, a respond widget appears on the card:

- **Quick-action buttons** — Parsed from numbered options in the prompt (e.g., "1. Yes", "2. No"). Click to send just the number.
- **Free-text input** — Type any response and click Send or press Enter.
- **Feedback** — Success shows a green highlight and toast. Errors show a toast with a specific message.

The widget only appears when the commander socket is reachable. If the session was not launched with `claudec`, the card shows the normal state bar (click to focus iTerm) without the input widget.

See [Input Bridge](input-bridge) for setup instructions and details.

## Sorting

Use the sort controls to change how agents are displayed:

- **By Project** (default) - Groups agents under their projects
- **By Priority** - Flat list sorted by priority score

## Real-Time Updates

The dashboard updates automatically via Server-Sent Events (SSE). The connection indicator shows:

- **Green dot** - Connected, receiving updates
- **Gray dot** - Connecting or reconnecting
- **Red dot** - Connection lost

## Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `?` | Open help |
