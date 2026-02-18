# Projects

Projects represent the codebases you're monitoring with Claude Headspace.

## Projects Page

Navigate to **>projects** in the header to see all registered projects. Each row shows:

- **Name** - Clickable link to the project detail page
- **Path** - Filesystem path to the codebase
- **Agents** - Number of active agents in this project
- **Inference** - Whether LLM inference is active or paused

Click **+ Add Project** to register a new project.

## Adding a Project

1. Click **+ Add Project**
2. Enter the project **Name** and **Path** (filesystem path to the codebase)
3. Optionally enter a **GitHub repo** (owner/repo format)
4. Click **Save**
5. Git metadata and an LLM-generated description are auto-detected

## Project Show Page

Click any project name to open the detail page. The show page includes:

### Header
- Project name, path, GitHub link, branch, and creation date
- LLM-generated description of the codebase
- Inference status (active or paused with timestamp/reason)
- Control buttons: Edit, Delete, Pause/Resume Inference, Regen Description, Refetch Git Info

### Waypoint
- Displays the project's waypoint (Next Up, Upcoming, Later, Not Now sections)
- Click **Edit** to open inline editor with Save/Cancel

### Brain Reboot
- Shows the combined waypoint + progress summary document
- Click **Generate** to create a new brain reboot
- Click **Export** to write it to the project's filesystem

### Progress Summary
- LLM-generated narrative summary from recent git commit history
- Click **Regenerate** to create a fresh summary

### Agents
- Collapsible accordion showing all agents (active and ended)
- Each agent expands to show commands, which expand to show turns
- Displays state, timing, and AI-generated summaries at each level

### Activity Metrics
- Hourly activity chart (Chart.js) with day/week/month windows
- Summary cards: turns, average turn time, active agents, frustration turns
- Period navigation (back/forward) for historical data

### Archive History
- Lists archived versions of waypoints, brain reboots, and progress summaries
- Click to view any archived version

### Inference Usage
- Total calls, total tokens, input tokens, and estimated cost for this project

## Project Settings

Each project has inference settings:

- **Pause Inference** - Stop all LLM calls for this project (summarisation, priority scoring)
- **Resume Inference** - Re-enable LLM calls
- Paused projects still receive hooks and track state; only LLM features are disabled

## Deleting a Project

1. Open the project show page
2. Click **Delete**
3. Confirm in the dialog
4. All associated agents, commands, turns, and events are deleted
