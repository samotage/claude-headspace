# Delta Spec: e1-s9-objective-tab

## ADDED Requirements

### Requirement: Objective Tab Template

The system SHALL provide an objective tab page.

#### Scenario: Objective tab displays form and history

Given a user navigates to the objective tab
When the page loads
Then the objective form is displayed
And the objective history section is displayed below
And the page uses dark terminal aesthetic

### Requirement: Objective Form

The system SHALL provide a form for setting objectives.

#### Scenario: Objective text field

Given the objective form is displayed
When the form renders
Then a text input with placeholder "What's your objective right now?" is shown
And the field is required

#### Scenario: Constraints field

Given the objective form is displayed
When the form renders
Then a textarea for optional constraints is shown
And placeholder text guides the user

#### Scenario: Form loads current objective

Given an objective exists
When the objective tab loads
Then the form fields are populated with current values

### Requirement: Auto-Save with Debounce

The system SHALL auto-save objective changes.

#### Scenario: Debounced save

Given user is typing in objective form
When user stops typing for 2-3 seconds
Then POST request is sent to /api/objective

#### Scenario: Cancel pending save

Given a save is pending
When user continues typing
Then the pending save is cancelled
And new debounce timer starts

#### Scenario: Empty objective not saved

Given objective text field is empty
When debounce timer fires
Then no save request is sent

### Requirement: Save State Indicators

The system SHALL display save state feedback.

#### Scenario: Saving indicator

Given a save request is in flight
When the form displays status
Then "Saving..." indicator is shown

#### Scenario: Saved confirmation

Given a save request succeeds
When the form displays status
Then "Saved" confirmation is shown
And it auto-dismisses after brief delay

#### Scenario: Error message

Given a save request fails
When the form displays status
Then an error message is shown
And it persists until next action

### Requirement: Objective History Display

The system SHALL display objective history.

#### Scenario: History list

Given objective history exists
When history section renders
Then entries are ordered by started_at descending
And each entry shows objective text
And each entry shows constraints if present
And each entry shows started_at timestamp
And each entry shows ended_at timestamp (except current)

#### Scenario: History pagination

Given more than 10 history entries exist
When first page loads
Then 10 entries are displayed
And "Load more" navigation is available

#### Scenario: Empty history

Given no objective history exists
When history section renders
Then "No objective history yet" is displayed

### Requirement: GET /api/objective Endpoint

The system SHALL provide endpoint to retrieve current objective.

#### Scenario: Get current objective

Given an objective exists
When GET /api/objective is called
Then response includes id, current_text, constraints, set_at
And response is JSON

#### Scenario: No objective exists

Given no objective exists
When GET /api/objective is called
Then appropriate response indicates no objective

### Requirement: POST /api/objective Endpoint

The system SHALL provide endpoint to create/update objective.

#### Scenario: Create new objective

Given no objective exists
When POST /api/objective with valid text
Then new objective is created
And new ObjectiveHistory record is created with started_at=now
And response returns the objective

#### Scenario: Update existing objective

Given an objective exists
When POST /api/objective with new text
Then previous ObjectiveHistory gets ended_at timestamp
And new ObjectiveHistory record is created
And objective is updated
And response returns the updated objective

#### Scenario: Validation error

Given POST /api/objective with empty text
When request is processed
Then 400 response with error message is returned

### Requirement: GET /api/objective/history Endpoint

The system SHALL provide endpoint to retrieve objective history.

#### Scenario: Get history with pagination

Given objective history exists
When GET /api/objective/history with page=1
Then paginated list of ObjectiveHistory records is returned
And entries are ordered by started_at descending
And response includes total count and pagination metadata

#### Scenario: Custom page size

Given objective history exists
When GET /api/objective/history with per_page=5
Then 5 entries per page are returned

### Requirement: Error Handling

The system SHALL handle errors gracefully.

#### Scenario: Validation error response

Given invalid input
When API endpoint processes request
Then 400 response with descriptive message

#### Scenario: Database error response

Given database error occurs
When API endpoint processes request
Then 500 response with generic error message

#### Scenario: Frontend error display

Given API request fails
When response is received
Then user-friendly error message is displayed

## MODIFIED Requirements

None.

## REMOVED Requirements

None.
