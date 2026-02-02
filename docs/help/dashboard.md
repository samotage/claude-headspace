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
- **State Bar** - Visual indicator of current state
- **Task Summary** - What the agent is currently doing
- **Priority Score** - Used for sorting
- **Headspace Button** - Click to focus the terminal window

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
