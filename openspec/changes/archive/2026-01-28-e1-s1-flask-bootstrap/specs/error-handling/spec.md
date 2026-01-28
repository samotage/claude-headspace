## ADDED Requirements

### Requirement: Error Handling 404
The application SHALL return a styled 404 error page for non-existent routes.

#### Scenario: Route not found
- **WHEN** a request is made to a non-existent route
- **THEN** the response status is HTTP 404
- **AND** the response is a styled HTML page with dark theme
- **AND** the page displays "Page not found" message

### Requirement: Error Handling 500
The application SHALL return a styled 500 error page for unhandled exceptions.

#### Scenario: Server error in production
- **WHEN** an unhandled exception occurs in production mode
- **THEN** the response status is HTTP 500
- **AND** the response is a styled HTML page with dark theme
- **AND** no stack traces, file paths, or sensitive information is exposed

#### Scenario: Server error in development
- **WHEN** an unhandled exception occurs in development mode (debug=true)
- **THEN** detailed error information MAY be shown for debugging
