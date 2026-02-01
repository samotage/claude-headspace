## MODIFIED Requirements

### Requirement: Task Data Model

The Task model SHALL include fields for instruction tracking and renamed completion summary.

#### Scenario: Task instruction field

- **WHEN** the migration is applied
- **THEN** the tasks table SHALL have a nullable `instruction` text field
- **AND** a nullable `instruction_generated_at` timestamp field

#### Scenario: Task completion summary field rename

- **WHEN** the migration is applied
- **THEN** the tasks table `summary` column SHALL be renamed to `completion_summary`
- **AND** the `summary_generated_at` column SHALL be renamed to `completion_summary_generated_at`
- **AND** existing data SHALL be preserved during the rename

#### Scenario: Backward compatibility with existing tasks

- **WHEN** a task exists from before this change with NULL `completion_summary` and NULL `instruction`
- **THEN** the task SHALL display without errors in the dashboard
- **AND** the agent card SHALL show appropriate fallback text
