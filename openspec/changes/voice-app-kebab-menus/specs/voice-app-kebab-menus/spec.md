## ADDED Requirements

### Requirement: Voice App Agent Chat Kebab Menu

The voice app agent chat view SHALL display a kebab menu trigger (three-dot vertical icon) in the chat header area. Activating the trigger SHALL open a dropdown menu via the shared `PortalKebabMenu` component, positioned relative to the trigger button.

The menu SHALL contain the following actions:
- **Fetch context** -- fetch and display agent context window usage
- **Attach** -- attach to the agent's tmux session (iTerm focus)
- **Agent info** -- display agent information
- **Reconcile** -- trigger transcript reconciliation
- **Handoff** -- initiate agent handoff (only visible when agent has a persona; requires confirmation)
- **Dismiss agent** -- shut down the agent (destructive; requires confirmation)

Destructive actions (dismiss, handoff) SHALL be visually differentiated with red text styling and separated from non-destructive actions by a divider.

#### Scenario: User opens agent chat kebab menu

- **WHEN** the user taps/clicks the kebab trigger in the agent chat header
- **THEN** a dropdown menu appears with agent-context actions
- **AND** the menu is positioned adjacent to the trigger button without causing layout shifts

#### Scenario: User dismisses agent via kebab menu

- **WHEN** the user selects "Dismiss agent" from the kebab menu
- **THEN** a confirmation dialog appears before executing the shutdown
- **AND** the menu closes immediately upon action selection

#### Scenario: Handoff action visibility

- **WHEN** the current agent has no persona assigned
- **THEN** the "Handoff" action SHALL NOT appear in the menu

#### Scenario: Menu dismissal

- **WHEN** the user clicks/taps outside the menu, presses Escape, or selects an action
- **THEN** the menu SHALL close

---

### Requirement: Voice App Channel Chat Kebab Menu

The voice app channel chat view SHALL display a kebab menu trigger (three-dot vertical icon) in the channel chat header area. Activating the trigger SHALL open a dropdown menu via the shared `PortalKebabMenu` component.

The menu SHALL contain the following actions:
- **Add member** -- expand the add-member picker
- **Channel info** -- display channel details
- **Complete channel** -- mark the channel as complete (chair-only)
- **Archive channel** -- end/archive the channel (chair-only; destructive; requires confirmation)
- **Copy slug** -- copy channel slug to clipboard
- **Leave channel** -- leave the channel and navigate back

Chair-only actions (complete, archive) SHALL only be visible when the operator is the channel chair.

Destructive actions (archive channel) SHALL be visually differentiated with red text styling and separated from non-destructive actions by a divider.

#### Scenario: User opens channel chat kebab menu

- **WHEN** the user taps/clicks the kebab trigger in the channel chat header
- **THEN** a dropdown menu appears with channel-context actions
- **AND** chair-only actions are visible only if the operator is the channel chair

#### Scenario: Non-chair user views channel kebab menu

- **WHEN** a non-chair member opens the kebab menu
- **THEN** "Complete channel" and "Archive channel" actions SHALL NOT be visible

#### Scenario: User archives channel via kebab menu

- **WHEN** the chair selects "Archive channel" from the kebab menu
- **THEN** a confirmation dialog appears before executing the archive
- **AND** upon confirmation, the channel is archived and the user is navigated back to the sidebar

#### Scenario: User copies channel slug

- **WHEN** the user selects "Copy slug" from the kebab menu
- **THEN** the channel slug is copied to the system clipboard
- **AND** a toast notification confirms the copy

#### Scenario: Menu dismissal

- **WHEN** the user clicks/taps outside the menu, presses Escape, or selects an action
- **THEN** the menu SHALL close

---

### Requirement: Touch Device Usability

All kebab menu triggers and menu items SHALL have a minimum tap target size of 44px on touch devices (enforced via `@media (pointer: coarse)`).

#### Scenario: Touch device interaction

- **WHEN** the user accesses the voice app on a touch device
- **THEN** kebab trigger buttons and menu items SHALL be at least 44px in their tappable area

---

### Requirement: Visual Consistency

Kebab menu appearance and behaviour SHALL be consistent between the agent chat and channel chat contexts. Both SHALL use the same shared `PortalKebabMenu` component, the same visual styling, the same interaction patterns (open, close, confirm), and differ only in their action sets.

#### Scenario: Consistent styling

- **WHEN** the agent chat kebab and channel chat kebab are both opened
- **THEN** they SHALL use the same menu styling, animation, icon sizing, and layout

---

### Requirement: No Layout Interference

The kebab menus SHALL NOT cause layout shifts or interfere with chat message display or text input controls.

#### Scenario: Menu open during active chat

- **WHEN** the kebab menu is open while messages are being received
- **THEN** the chat message area SHALL continue to display and scroll normally
- **AND** the text input SHALL remain functional

---

### Requirement: Extensibility

The kebab menu action lists SHALL be built via a function that returns an array of action objects. Future features (e.g., transcript download) SHALL be addable by appending to this array without restructuring the menu component.

#### Scenario: Adding a future action

- **WHEN** a new feature (e.g., transcript download) needs to add an action
- **THEN** it SHALL be achievable by adding one entry to the action builder function
- **AND** no changes to the menu component itself SHALL be required
