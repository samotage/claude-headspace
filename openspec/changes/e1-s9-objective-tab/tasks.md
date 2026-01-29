# Tasks: e1-s9-objective-tab

## Phase 1: Setup

- [ ] Review existing Objective and ObjectiveHistory models from Sprint 3
- [ ] Review base template and existing routes for patterns
- [ ] Plan API response formats

## Phase 2: Implementation

### API Endpoints (FR9-FR11)
- [ ] Create objective.py blueprint with objective_bp
- [ ] Implement GET /api/objective endpoint
  - Return current objective with id, current_text, constraints, set_at
  - Handle no objective case
- [ ] Implement POST /api/objective endpoint
  - Accept JSON with text (required) and constraints (optional)
  - Create new objective if none exists
  - Update existing: set ended_at on current history, create new history
  - Return validation error if text is empty
- [ ] Implement GET /api/objective/history endpoint
  - Accept page and per_page query params
  - Return paginated ObjectiveHistory records
  - Order by started_at descending
  - Include pagination metadata

### History Tracking Logic (FR12)
- [ ] Implement history tracking in POST endpoint
  - First objective: create ObjectiveHistory with started_at=now, ended_at=null
  - Update: set ended_at on previous, create new record
  - Snapshot text and constraints at point in time

### Template (FR1, FR8)
- [ ] Create objective.html extending base template
- [ ] Add objective form section
- [ ] Add objective history section
- [ ] Add empty state messages
- [ ] Apply dark terminal aesthetic (Tailwind classes)

### Form Implementation (FR2-FR5)
- [ ] Add objective text input field with placeholder
- [ ] Add constraints textarea with placeholder
- [ ] Create objective.js for auto-save logic
- [ ] Implement debounce (2-3 seconds)
- [ ] Add save state indicators (saving, saved, error)
- [ ] Add "Changes save automatically" hint

### History Display (FR6-FR7)
- [ ] Display history entries with objective text
- [ ] Display constraints if present
- [ ] Display started_at and ended_at timestamps
- [ ] Implement pagination with "Load more" button
- [ ] Handle empty history state

### Error Handling (FR13)
- [ ] Return 400 for validation errors with message
- [ ] Return 500 for database errors with generic message
- [ ] Display user-friendly error messages in UI

### Integration
- [ ] Register objective_bp in app.py
- [ ] Wire objective tab link in header navigation
- [ ] Add objective route for tab page

## Phase 3: Testing

- [ ] Test GET /api/objective returns current objective
- [ ] Test GET /api/objective with no objective
- [ ] Test POST /api/objective creates new objective
- [ ] Test POST /api/objective updates existing objective
- [ ] Test POST /api/objective creates history records
- [ ] Test POST /api/objective validation (empty text)
- [ ] Test GET /api/objective/history pagination
- [ ] Test objective tab renders correctly
- [ ] Test empty states display correctly

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Auto-save debounce works correctly
- [ ] History pagination loads additional pages
- [ ] UI matches dark terminal aesthetic
- [ ] No console errors
