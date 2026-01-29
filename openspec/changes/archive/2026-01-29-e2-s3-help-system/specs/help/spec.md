# Delta Spec: e2-s3-help-system

## ADDED Requirements

### Requirement: Help Modal Activation

The system SHALL provide keyboard and button access to the help modal.

#### Scenario: Keyboard shortcut opens help

When the user presses the `?` key
And focus is NOT in a text input field
Then the help modal opens within 100ms

#### Scenario: Keyboard shortcut ignored in text fields

When the user presses the `?` key
And focus IS in a text input or textarea
Then the `?` character is typed normally
And the help modal does NOT open

#### Scenario: Help button opens help

When the user clicks the help button in the header
Then the help modal opens

### Requirement: Help Modal Display

The system SHALL display a modal overlay with search, navigation, and content areas.

#### Scenario: Modal layout

When the help modal opens
Then it displays with:
- Semi-transparent backdrop
- Close button (X) in top-right corner
- Search input field at the top
- Table of contents sidebar
- Content area for documentation

### Requirement: Help Modal Dismissal

The system SHALL allow multiple methods to close the help modal.

#### Scenario: Escape key closes modal

When the help modal is open
And the user presses the Escape key
Then the modal closes
And focus returns to the previously focused element

#### Scenario: Backdrop click closes modal

When the help modal is open
And the user clicks outside the modal (on backdrop)
Then the modal closes

#### Scenario: Close button closes modal

When the help modal is open
And the user clicks the X button
Then the modal closes

### Requirement: Help Search

The system SHALL provide full-text search across documentation.

#### Scenario: Search matches topics

When the user types a search query
Then matching topics appear within 200ms
And results include title and excerpt
And matches are highlighted in results

#### Scenario: Search matches content

When the user types text that appears in topic content
Then topics containing that text appear in results

#### Scenario: Empty search shows all topics

When the search field is empty
Then all topics are displayed in the table of contents

### Requirement: Topic Navigation

The system SHALL allow navigation between documentation topics.

#### Scenario: TOC navigation

When the user clicks a topic in the table of contents
Then that topic's content loads in the content area

#### Scenario: Search result navigation

When the user clicks a search result
Then that topic's content loads in the content area
And the search field clears

### Requirement: Markdown Rendering

The system SHALL render markdown documentation with proper formatting.

#### Scenario: Heading rendering

When documentation contains markdown headings
Then they render as properly styled h1-h6 elements

#### Scenario: Code block rendering

When documentation contains fenced code blocks
Then they render with monospace font and syntax highlighting

#### Scenario: Link rendering

When documentation contains markdown links
Then internal links navigate within help
And external links open in new tab

#### Scenario: List rendering

When documentation contains markdown lists
Then they render as proper HTML lists

### Requirement: Help Content API

The system SHALL provide API endpoints for help content.

#### Scenario: List topics

When GET /api/help/topics is called
Then response includes array of topics with slug, title, excerpt

#### Scenario: Get topic content

When GET /api/help/topics/<slug> is called
And the topic exists
Then response includes topic markdown content

#### Scenario: Topic not found

When GET /api/help/topics/<invalid> is called
And the topic does not exist
Then response is 404 with error message

### Requirement: Accessibility

The system SHALL meet accessibility standards for the help modal.

#### Scenario: Focus trap

When the help modal is open
Then keyboard focus is trapped within the modal
And Tab cycles through focusable elements

#### Scenario: Screen reader support

When the help modal opens
Then screen readers announce the modal
And modal has proper ARIA labels and roles

#### Scenario: Keyboard navigation

When the help modal is open
Then all interactive elements are keyboard accessible
And Enter key activates focused element

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
