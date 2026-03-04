## Why

The voice app (`/voice`) is the primary interaction interface for Claude Headspace, yet it lacks the contextual action menus (kebab menus) already available on the dashboard's agent cards and channel chat panel. Users must switch to the dashboard to access actions like dismiss, handoff, add member, or leave channel. This creates a disjointed workflow for the operator who primarily interacts through the voice app.

## What Changes

- Add a kebab menu trigger (three-dot icon) to the voice app **agent chat header** (`main-header`) with agent-context actions:
  - Dismiss agent (destructive, requires confirmation)
  - Attach to session
  - View context usage
  - View agent info
  - Trigger reconciliation
  - Initiate handoff (destructive, requires confirmation; only shown when agent has a persona)
- Add a kebab menu trigger (three-dot icon) to the voice app **channel chat header** (`channel-chat-header`) with channel-context actions:
  - Add member
  - Channel info
  - Mark complete (chair-only)
  - Archive channel (chair-only, destructive, requires confirmation)
  - Copy slug
  - Leave channel
- Both menus use the existing `PortalKebabMenu` shared component (already loaded in voice.html)
- Menus close on action selection, outside click/tap, or Escape key
- Minimum 44px tap targets on touch devices
- Extensible structure for future actions (e.g., transcript download)

## Impact

- Affected specs: voice-app (static/voice/), portal-kebab-menu
- Affected code:
  - `static/voice/voice.html` -- add kebab trigger buttons to agent chat header and channel chat header
  - `static/voice/voice-chat-controller.js` or new module -- agent chat kebab action handling
  - `static/voice/voice-channel-chat.js` -- channel chat kebab action handling
  - `static/voice/voice.css` -- kebab button styling in chat headers
  - `static/js/portal-kebab-menu.js` -- may need channel-context icon additions (add-member, complete, end, copy-slug, leave)
  - `static/voice/voice-app.js` -- close kebab menus on outside click
- No backend changes required -- all actions use existing API endpoints
- No database changes
- No breaking changes
