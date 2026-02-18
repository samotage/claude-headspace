# Commands: e2-s3-help-system

## Phase 1: Setup

- [x] Review existing modal patterns (_waypoint_editor.html)
- [x] Review keyboard shortcut implementation
- [x] Review base.html and header structure
- [x] Plan help content API architecture

## Phase 2: Implementation

### Documentation Content (FR9)
- [x] Create docs/help/ directory structure
- [x] Create docs/help/index.md - overview and TOC
- [x] Create docs/help/getting-started.md - quick start
- [x] Create docs/help/dashboard.md - dashboard overview
- [x] Create docs/help/objective.md - objective management
- [x] Create docs/help/configuration.md - config.yaml options
- [x] Create docs/help/waypoints.md - waypoint editing
- [x] Create docs/help/troubleshooting.md - common issues

### Help API (FR8)
- [x] Create src/claude_headspace/routes/help.py blueprint
- [x] Implement GET /api/help/topics endpoint
- [x] Return topic list with slug, title, excerpt
- [x] Implement GET /api/help/topics/<slug> endpoint
- [x] Return topic content as markdown
- [x] Handle 404 for unknown topics
- [x] Register help_bp in app.py

### Help Modal UI (FR1-FR3, FR5-FR7)
- [x] Create templates/partials/_help_modal.html
- [x] Modal overlay with semi-transparent backdrop
- [x] Search input field at top
- [x] Table of contents sidebar
- [x] Content area for documentation display
- [x] Close button (X) in top-right
- [x] Include modal in base.html

### Help Button (FR2)
- [x] Add help button (?) to templates/partials/_header.html
- [x] Style consistently with existing nav elements
- [x] Wire click to open help modal

### Keyboard Shortcut (FR1, FR7, FR10)
- [x] Create static/js/help.js
- [x] Listen for `?` key on document
- [x] Skip when focus in text input/textarea
- [x] Open modal on keypress
- [x] Close modal on Escape key
- [x] Focus trap within modal
- [x] Return focus on close

### Search Functionality (FR4, NFR1)
- [x] Implement client-side search in help.js
- [x] Build search index from topic content
- [x] Match against titles and content
- [x] Display results with title and excerpt
- [x] Search results within 200ms

### Markdown Rendering (FR6)
- [x] Implement markdown to HTML rendering
- [x] Support headings (h1-h6)
- [x] Support code blocks with syntax highlighting
- [x] Support inline code
- [x] Support links (internal and external)
- [x] Support lists (ordered and unordered)
- [x] Support emphasis (bold, italic)

### Accessibility (NFR2)
- [x] Add ARIA labels and roles to modal
- [x] Implement focus trap
- [x] Announce modal open/close to screen readers
- [x] Ensure keyboard navigation (Tab, Enter, Escape)
- [x] Verify color contrast

## Phase 3: Testing

- [x] Test GET /api/help/topics returns list
- [x] Test GET /api/help/topics/<slug> returns content
- [x] Test GET /api/help/topics/<invalid> returns 404
- [x] Test markdown rendering
- [x] Test search functionality
- [x] Test modal opens on ? keypress
- [x] Test modal closes on Escape
- [x] Test modal closes on backdrop click
- [x] Test focus trap
- [x] Test help button opens modal

## Phase 4: Final Verification

- [x] All tests passing
- [ ] Modal opens within 100ms
- [ ] Search results within 200ms
- [ ] No console errors
- [ ] Manual test: keyboard navigation
- [ ] Manual test: search and view topic
