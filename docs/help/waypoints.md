# Waypoints

Waypoints are markdown files that define the path ahead for each project. They're a core artifact of the brain_reboot system.

## What is a Waypoint?

A waypoint lives at `brain_reboot/waypoint.md` in each project. It contains four sections:

- **Next Up** - Immediate next steps
- **Upcoming** - Coming soon
- **Later** - Future work
- **Not Now** - Parked or deprioritized items

## Editing Waypoints

### From the Dashboard

1. Find the project in the dashboard
2. Click the **[Edit]** button next to the waypoint preview
3. The waypoint editor modal opens
4. Make your changes
5. Click **Save**

### Editor Features

- **Edit Mode** - Write markdown in the textarea
- **Preview Mode** - See rendered markdown output
- **Toggle** - Switch between edit and preview
- **Unsaved Indicator** - Shows when you have unsaved changes

## Automatic Archiving

When you save a waypoint:

1. The current waypoint is archived to `brain_reboot/archive/`
2. Archive filename includes date: `waypoint_2026-01-29.md`
3. Multiple saves per day get counters: `waypoint_2026-01-29_2.md`
4. Your new content replaces the waypoint

## Conflict Detection

If someone else edits the waypoint while you're editing:

1. A conflict dialog appears when you try to save
2. Choose **Reload** to discard your changes and load the current file
3. Or choose **Overwrite** to save your version anyway

## Creating New Waypoints

If a project doesn't have a waypoint yet:

1. Click **[Edit]** - the editor loads a template
2. Fill in the sections
3. Click **Save**
4. The directory structure is created automatically

## Best Practices

- Keep "Next Up" focused on 1-3 items
- Move completed items out regularly
- Use "Not Now" for parking, not deleting
- Review waypoints when returning to stale projects
