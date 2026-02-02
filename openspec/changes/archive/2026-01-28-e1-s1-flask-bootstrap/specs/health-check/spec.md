## ADDED Requirements

### Requirement: Health Check Endpoint
The application SHALL expose a health check endpoint at `GET /health`.

#### Scenario: Health check success
- **WHEN** a GET request is made to `/health`
- **THEN** the response status is HTTP 200
- **AND** the response body is JSON `{"status": "healthy", "version": "<version>"}`
- **AND** the Content-Type header is `application/json`
