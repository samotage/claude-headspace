## ADDED Requirements

### Requirement: Structured Logging
The application SHALL log to both console and file with structured format.

#### Scenario: Log entry format
- **WHEN** a log entry is created
- **THEN** it SHALL include timestamp in ISO 8601 format
- **AND** log level (DEBUG, INFO, WARNING, ERROR)
- **AND** logger name (module)
- **AND** message

#### Scenario: Log destinations
- **WHEN** the application logs a message
- **THEN** it SHALL appear in console (stdout)
- **AND** in `logs/app.log` file

#### Scenario: Log level configuration
- **WHEN** `FLASK_LOG_LEVEL=DEBUG` is set
- **THEN** DEBUG level messages SHALL be logged
