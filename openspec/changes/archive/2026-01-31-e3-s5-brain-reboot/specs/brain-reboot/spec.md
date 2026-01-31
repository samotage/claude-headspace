## ADDED Requirements

### Requirement: Brain Reboot Document Generation

The system SHALL provide a brain reboot generator that combines a project's waypoint and progress summary into a single formatted context restoration document without making LLM inference calls.

#### Scenario: Generate brain reboot with both artifacts present

- **WHEN** brain reboot generation is requested for a project that has both a waypoint and a progress summary
- **THEN** the system SHALL produce a formatted document containing: project name, generation timestamp, progress summary content, and waypoint content organised by priority sections (next up, upcoming, later, not now)
- **AND** the progress summary SHALL appear before the waypoint in the document

#### Scenario: Generate brain reboot with waypoint only

- **WHEN** brain reboot generation is requested and the project has a waypoint but no progress summary
- **THEN** the system SHALL include the waypoint content
- **AND** SHALL indicate that the progress summary is not yet available

#### Scenario: Generate brain reboot with progress summary only

- **WHEN** brain reboot generation is requested and the project has a progress summary but no waypoint
- **THEN** the system SHALL include the progress summary content
- **AND** SHALL indicate that the waypoint is not yet available

#### Scenario: Generate brain reboot with neither artifact

- **WHEN** brain reboot generation is requested and the project has neither a waypoint nor a progress summary
- **THEN** the system SHALL display a message indicating both artifacts are missing
- **AND** SHALL provide guidance on how to create them

#### Scenario: On-demand generation

- **WHEN** brain reboot generation is triggered
- **THEN** the content SHALL be generated on demand from current file-based artifacts
- **AND** no LLM inference calls SHALL be made

---

### Requirement: Brain Reboot API Endpoints

The system SHALL expose API endpoints for generating and retrieving brain reboot content.

#### Scenario: Generate brain reboot via POST

- **WHEN** POST `/api/projects/<id>/brain-reboot` is requested
- **THEN** the system SHALL generate a brain reboot for the specified project
- **AND** SHALL return the formatted content with generation metadata

#### Scenario: Retrieve last generated brain reboot via GET

- **WHEN** GET `/api/projects/<id>/brain-reboot` is requested
- **THEN** the system SHALL return the most recently generated brain reboot content
- **AND** if none has been generated yet, SHALL indicate that no brain reboot is available

#### Scenario: Project not found

- **WHEN** either endpoint is requested with a non-existent project ID
- **THEN** the system SHALL return a 404 error

---

### Requirement: Brain Reboot Export

The system SHALL support exporting the brain reboot document to the target project's filesystem.

#### Scenario: Successful export

- **WHEN** export is requested for a generated brain reboot
- **THEN** the system SHALL save the document as a markdown file in the target project's `docs/brain_reboot/` directory

#### Scenario: Directory creation on export

- **WHEN** the `docs/brain_reboot/` directory does not exist in the target project
- **THEN** the system SHALL create the directory structure before saving

#### Scenario: Overwrite existing export

- **WHEN** a brain reboot file already exists at the export location
- **THEN** the system SHALL overwrite it (brain reboots are regenerated on demand, not versioned)

#### Scenario: Export feedback

- **WHEN** an export operation completes
- **THEN** the system SHALL provide feedback indicating success or failure

---

### Requirement: Brain Reboot Dashboard Modal

The dashboard SHALL provide a modal overlay for viewing brain reboot content with copy and export actions.

#### Scenario: Open modal from dashboard

- **WHEN** the user clicks the "Brain Reboot" button for a project
- **THEN** a modal SHALL open displaying the generated brain reboot content

#### Scenario: Copy to clipboard

- **WHEN** the user clicks "Copy to Clipboard" in the modal
- **THEN** the full brain reboot content SHALL be copied as text
- **AND** visual feedback SHALL confirm the copy operation

#### Scenario: Export from modal

- **WHEN** the user clicks "Export" in the modal
- **THEN** the brain reboot document SHALL be saved to the target project's brain reboot directory
- **AND** feedback SHALL indicate success or failure

#### Scenario: Dismiss modal

- **WHEN** the user clicks the close button, backdrop, or presses Escape
- **THEN** the modal SHALL close

---

### Requirement: Staleness Detection

The system SHALL classify projects into freshness tiers based on time since last agent activity.

#### Scenario: Fresh project classification

- **WHEN** a project's most recent agent activity is within the fresh threshold (default 0-3 days)
- **THEN** the project SHALL be classified as "fresh"

#### Scenario: Aging project classification

- **WHEN** a project's most recent agent activity is within the aging threshold (default 4-7 days)
- **THEN** the project SHALL be classified as "aging"

#### Scenario: Stale project classification

- **WHEN** a project's most recent agent activity exceeds the stale threshold (default 8+ days)
- **THEN** the project SHALL be classified as "stale"

#### Scenario: Unknown freshness

- **WHEN** a project has no agent activity history
- **THEN** the project SHALL have unknown freshness and no staleness indicator

#### Scenario: Configurable thresholds

- **WHEN** config.yaml contains brain_reboot staleness threshold values
- **THEN** those values SHALL override the defaults

---

### Requirement: Staleness Dashboard Integration

The dashboard SHALL display visual staleness indicators per project.

#### Scenario: Stale project indicator

- **WHEN** a project is classified as stale
- **THEN** the dashboard SHALL display a prominent visual indicator and a "Needs Reboot" badge

#### Scenario: Aging project indicator

- **WHEN** a project is classified as aging
- **THEN** the dashboard SHALL display a warning-level visual indicator

#### Scenario: Fresh project indicator

- **WHEN** a project is classified as fresh
- **THEN** the dashboard SHALL display a positive freshness indicator or no special indicator

#### Scenario: Staleness updates

- **WHEN** the dashboard refreshes or receives SSE updates with new agent activity
- **THEN** staleness indicators SHALL reflect the updated activity timestamps

---

### Requirement: Brain Reboot Configuration

The system SHALL support configurable settings for brain reboot and staleness detection.

#### Scenario: Configuration schema

- **WHEN** config.yaml is loaded
- **THEN** the `brain_reboot` section SHALL include: staleness_threshold_days, aging_threshold_days, and export_filename
- **AND** sensible defaults SHALL be provided (stale=7, aging=4, filename=brain_reboot.md)

---

## MODIFIED Requirements

### Requirement: Dashboard Project Display

The dashboard project panels SHALL include brain reboot access and staleness indicators.

#### Scenario: Brain Reboot button displayed

- **WHEN** the dashboard renders a project panel (column or group view)
- **THEN** a "Brain Reboot" button SHALL be displayed in the project header

#### Scenario: Staleness indicator displayed

- **WHEN** the dashboard renders a project panel with staleness data
- **THEN** the appropriate freshness indicator SHALL be displayed alongside the project name
