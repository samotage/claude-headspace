# Commands: e2-s1-config-ui

## Phase 1: Setup

- [x] Review existing navigation and tab patterns (base.html, dashboard.html)
- [x] Review existing config.py for configuration schema
- [x] Review existing route patterns (hooks.py, focus.py)
- [x] Plan service architecture

## Phase 2: Implementation

### API Endpoints (FR21-FR24)
- [x] Create src/claude_headspace/routes/config.py blueprint
- [x] Implement GET /api/config endpoint
- [x] Return current config as JSON (exclude env var overrides)
- [x] Implement POST /api/config endpoint
- [x] Accept JSON payload and validate all fields
- [x] Return validation errors as structured JSON on failure
- [x] Register config_bp in app.py

### Config Editor Service (FR11, NFR1-2)
- [x] Create src/claude_headspace/services/config_editor.py
- [x] Implement config schema definition with field types and constraints
- [x] Implement validation for each config section
- [x] Implement atomic file write (temp file then rename)
- [x] Ensure password values never logged in error messages
- [x] Add validation for type, required fields, and value ranges

### Navigation & Access (FR1-FR2)
- [x] Add Config tab to navigation in base.html
- [x] Follow existing navigation styling pattern
- [x] Implement active state indicator

### Config Tab Template (FR3-FR6)
- [x] Create templates/config.html
- [x] Display all 7 config sections as grouped form fieldsets
- [x] Add clear headings for each section
- [x] Pre-populate form with current config values
- [x] Add field descriptions/hints below each field

### Field Types (FR7-FR10)
- [x] Render string fields as text inputs
- [x] Render numeric fields as number inputs with min/max constraints
- [x] Render boolean fields as toggle switches
- [x] Render password fields as masked inputs with reveal toggle

### Form Validation (FR12-FR13)
- [x] Display validation errors inline next to invalid field
- [x] Prevent form submission while validation errors exist
- [x] Style invalid fields with red border and error text

### Save & Feedback (FR14-FR17)
- [x] Implement Save button submitting to POST /api/config
- [x] Display loading indicator during save
- [x] Show success toast: "Configuration saved"
- [x] Show error toast on failure with specific error

### Refresh Mechanism (FR18-FR20)
- [x] Display Refresh button after successful save
- [x] Indicate which settings require server restart
- [x] Implement refresh/restart behavior

### Accessibility (NFR4-5)
- [x] Add proper labels and ARIA attributes
- [x] Ensure keyboard navigation works
- [x] Test responsive layout at 768px viewport

## Phase 3: Testing

- [x] Test GET /api/config returns full config
- [x] Test POST /api/config with valid data saves correctly
- [x] Test POST /api/config with invalid data returns errors
- [x] Test validation for each field type
- [x] Test atomic write (temp file rename)
- [x] Test password masking in responses
- [x] Test form pre-population
- [x] Test inline validation errors display
- [x] Test success/error toast display
- [x] Test refresh button visibility after save

## Phase 4: Final Verification

- [x] All tests passing
- [ ] Form loads within 500ms
- [ ] Save operation completes within 1 second
- [ ] No console errors
- [ ] Manual test: edit server.port, save, verify in config.yaml
