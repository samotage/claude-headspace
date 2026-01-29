# Tasks: e1-s8-dashboard-ui

## Phase 1: Setup

- [x] Create dashboard blueprint structure
- [x] Create template partials directory structure
- [x] Add any required Tailwind configuration

## Phase 2: Implementation

### Dashboard Route (FR1-FR3)
- [x] Create dashboard blueprint at routes/dashboard.py
- [x] Implement `/` route serving dashboard template
- [x] Query projects with eager-loaded agents and tasks
- [x] Calculate status counts (INPUT NEEDED, WORKING, IDLE)
- [x] Pass data to template context
- [x] Register blueprint in routes/__init__.py

### Header Bar (FR4-FR7)
- [x] Create _header.html partial
- [x] Display "CLAUDE >_headspace" title with terminal styling
- [x] Add navigation tabs (dashboard, objective, logging)
- [x] Display status count badges with accurate counts
- [x] Add hooks/polling status indicator placeholder

### Project Groups (FR8-FR12)
- [x] Create _project_group.html partial
- [x] Display project name with traffic light indicator
- [x] Show active agent count
- [x] Implement traffic light colour logic (red/yellow/green)
- [x] Add collapse/expand toggle with HTMX
- [x] Display waypoint preview section (read-only)

### Agent Cards (FR13-FR20)
- [x] Create _agent_card.html partial
- [x] Display truncated session ID (#xxxxxxxx format)
- [x] Add status badge (ACTIVE/IDLE based on last_seen_at)
- [x] Show uptime as human-readable duration
- [x] Create state bar with colour coding (5 states)
- [x] Display task summary (100 char truncation)
- [x] Add priority score badge (default 50)
- [x] Add "Headspace" button placeholder

### State Visualization (FR17)
- [x] Define state colours in Tailwind config or CSS
  - IDLE: Grey
  - COMMANDED: Yellow
  - PROCESSING: Blue
  - AWAITING_INPUT: Orange
  - COMPLETE: Green
- [x] Add state bar component with colour and label

### Responsive Layout (FR21-FR24)
- [x] Mobile layout: single column, stacked cards
- [x] Tablet layout: two-column grid
- [x] Desktop layout: multi-column grid (3+)
- [x] Ensure 44px minimum touch targets

### Accessibility (NFR3-NFR4)
- [x] Use semantic HTML elements (header, main, section, article)
- [x] Add ARIA labels for traffic lights
- [x] Add ARIA labels for state bars
- [x] Ensure keyboard navigation for collapse/expand

## Phase 3: Testing

- [x] Test dashboard route returns 200
- [x] Test template renders with expected structure
- [x] Test all projects displayed
- [x] Test all agents displayed within projects
- [x] Test status counts accuracy
- [x] Test traffic light logic
- [x] Test state bar rendering
- [x] Test responsive breakpoints
- [x] Test database query count (N+1 prevention)

## Phase 4: Final Verification

- [x] All tests passing
- [x] No linting errors
- [x] Visual verification at 320px, 768px, 1024px viewports
- [x] Page load < 2 seconds verified
