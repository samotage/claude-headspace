# Tasks: e1-s8-dashboard-ui

## Phase 1: Setup

- [ ] Create dashboard blueprint structure
- [ ] Create template partials directory structure
- [ ] Add any required Tailwind configuration

## Phase 2: Implementation

### Dashboard Route (FR1-FR3)
- [ ] Create dashboard blueprint at routes/dashboard.py
- [ ] Implement `/` route serving dashboard template
- [ ] Query projects with eager-loaded agents and tasks
- [ ] Calculate status counts (INPUT NEEDED, WORKING, IDLE)
- [ ] Pass data to template context
- [ ] Register blueprint in routes/__init__.py

### Header Bar (FR4-FR7)
- [ ] Create _header.html partial
- [ ] Display "CLAUDE >_headspace" title with terminal styling
- [ ] Add navigation tabs (dashboard, objective, logging)
- [ ] Display status count badges with accurate counts
- [ ] Add hooks/polling status indicator placeholder

### Project Groups (FR8-FR12)
- [ ] Create _project_group.html partial
- [ ] Display project name with traffic light indicator
- [ ] Show active agent count
- [ ] Implement traffic light colour logic (red/yellow/green)
- [ ] Add collapse/expand toggle with HTMX
- [ ] Display waypoint preview section (read-only)

### Agent Cards (FR13-FR20)
- [ ] Create _agent_card.html partial
- [ ] Display truncated session ID (#xxxxxxxx format)
- [ ] Add status badge (ACTIVE/IDLE based on last_seen_at)
- [ ] Show uptime as human-readable duration
- [ ] Create state bar with colour coding (5 states)
- [ ] Display task summary (100 char truncation)
- [ ] Add priority score badge (default 50)
- [ ] Add "Headspace" button placeholder

### State Visualization (FR17)
- [ ] Define state colours in Tailwind config or CSS
  - IDLE: Grey
  - COMMANDED: Yellow
  - PROCESSING: Blue
  - AWAITING_INPUT: Orange
  - COMPLETE: Green
- [ ] Add state bar component with colour and label

### Responsive Layout (FR21-FR24)
- [ ] Mobile layout: single column, stacked cards
- [ ] Tablet layout: two-column grid
- [ ] Desktop layout: multi-column grid (3+)
- [ ] Ensure 44px minimum touch targets

### Accessibility (NFR3-NFR4)
- [ ] Use semantic HTML elements (header, main, section, article)
- [ ] Add ARIA labels for traffic lights
- [ ] Add ARIA labels for state bars
- [ ] Ensure keyboard navigation for collapse/expand

## Phase 3: Testing

- [ ] Test dashboard route returns 200
- [ ] Test template renders with expected structure
- [ ] Test all projects displayed
- [ ] Test all agents displayed within projects
- [ ] Test status counts accuracy
- [ ] Test traffic light logic
- [ ] Test state bar rendering
- [ ] Test responsive breakpoints
- [ ] Test database query count (N+1 prevention)

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] No linting errors
- [ ] Visual verification at 320px, 768px, 1024px viewports
- [ ] Page load < 2 seconds verified
