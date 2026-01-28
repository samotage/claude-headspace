## ADDED Requirements

### Requirement: Application Startup
The Flask application SHALL start via the standard `flask run` command and bind to the host and port specified in configuration.

#### Scenario: Successful startup
- **WHEN** `flask run` is executed from project root
- **THEN** the server starts successfully
- **AND** logs show "Running on http://{host}:{port}"

### Requirement: Application Factory Pattern
The application SHALL use the Flask application factory pattern for testability.

#### Scenario: Create app instance
- **WHEN** `create_app()` is called
- **THEN** a configured Flask application instance is returned
- **AND** all blueprints are registered
- **AND** error handlers are configured

### Requirement: Base HTML Template
The application SHALL provide a base HTML template with dark terminal aesthetic.

#### Scenario: Template structure
- **WHEN** the base template is rendered
- **THEN** it SHALL include DOCTYPE, html, head, body elements
- **AND** meta tags for charset (UTF-8) and viewport
- **AND** link to Tailwind CSS stylesheet
- **AND** block regions for title and content

#### Scenario: Theme colors
- **WHEN** the base template is rendered
- **THEN** the page SHALL display with dark background (#08080a)
- **AND** primary text color (#e8e8ed)
- **AND** monospace font (SF Mono, Monaco, or fallback)

### Requirement: Development vs Production Mode
The application SHALL behave differently based on mode configuration.

#### Scenario: Development mode
- **WHEN** `server.debug` is true or `FLASK_DEBUG=true`
- **THEN** debug mode is enabled
- **AND** auto-reload is enabled
- **AND** error details are shown
- **AND** log level defaults to DEBUG

#### Scenario: Production mode
- **WHEN** `server.debug` is false (default)
- **THEN** debug mode is disabled
- **AND** auto-reload is disabled
- **AND** error details are hidden
- **AND** log level defaults to INFO
