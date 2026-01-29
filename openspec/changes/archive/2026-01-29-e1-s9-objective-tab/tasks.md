# Tasks: e1-s9-objective-tab

## Phase 1: Setup

- [x] Review existing Objective and ObjectiveHistory models from Sprint 3
- [x] Review base template and existing routes for patterns
- [x] Plan API response formats

## Phase 2: Implementation

### API Endpoints (FR9-FR11)
- [x] Create objective.py blueprint with objective_bp
- [x] Implement GET /api/objective endpoint
  - Return current objective with id, current_text, constraints, set_at
  - Handle no objective case
- [x] Implement POST /api/objective endpoint
  - Accept JSON with text (required) and constraints (optional)
  - Create new objective if none exists
  - Update existing: set ended_at on current history, create new history
  - Return validation error if text is empty
- [x] Implement GET /api/objective/history endpoint
  - Accept page and per_page query params
  - Return paginated ObjectiveHistory records
  - Order by started_at descending
  - Include pagination metadata

### History Tracking Logic (FR12)
- [x] Implement history tracking in POST endpoint
  - First objective: create ObjectiveHistory with started_at=now, ended_at=null
  - Update: set ended_at on previous, create new record
  - Snapshot text and constraints at point in time

### Template (FR1, FR8)
- [x] Create objective.html extending base template
- [x] Add objective form section
- [x] Add objective history section
- [x] Add empty state messages
- [x] Apply dark terminal aesthetic (Tailwind classes)

### Form Implementation (FR2-FR5)
- [x] Add objective text input field with placeholder
- [x] Add constraints textarea with placeholder
- [x] Create objective.js for auto-save logic
- [x] Implement debounce (2-3 seconds)
- [x] Add save state indicators (saving, saved, error)
- [x] Add "Changes save automatically" hint

### History Display (FR6-FR7)
- [x] Display history entries with objective text
- [x] Display constraints if present
- [x] Display started_at and ended_at timestamps
- [x] Implement pagination with "Load more" button
- [x] Handle empty history state

### Error Handling (FR13)
- [x] Return 400 for validation errors with message
- [x] Return 500 for database errors with generic message
- [x] Display user-friendly error messages in UI

### Integration
- [x] Register objective_bp in app.py
- [x] Wire objective tab link in header navigation
- [x] Add objective route for tab page

## Phase 3: Testing

- [x] Test GET /api/objective returns current objective
- [x] Test GET /api/objective with no objective
- [x] Test POST /api/objective creates new objective
- [x] Test POST /api/objective updates existing objective
- [x] Test POST /api/objective creates history records
- [x] Test POST /api/objective validation (empty text)
- [x] Test GET /api/objective/history pagination
- [x] Test objective tab renders correctly
- [x] Test empty states display correctly

## Phase 4: Final Verification

- [x] All tests passing
- [x] Auto-save debounce works correctly
- [x] History pagination loads additional pages
- [x] UI matches dark terminal aesthetic
- [x] No console errors
