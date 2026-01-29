# Tasks: e2-s3-help-system

## Phase 1: Setup

- [x] Review existing modal patterns (_waypoint_editor.html)
- [x] Review keyboard shortcut implementation
- [x] Review base.html and header structure
- [x] Plan help content API architecture

## Phase 2: Implementation

### Documentation Content (FR9)
- [ ] Create docs/help/ directory structure
- [ ] Create docs/help/index.md - overview and TOC
- [ ] Create docs/help/getting-started.md - quick start
- [ ] Create docs/help/dashboard.md - dashboard overview
- [ ] Create docs/help/objective.md - objective management
- [ ] Create docs/help/configuration.md - config.yaml options
- [ ] Create docs/help/waypoints.md - waypoint editing
- [ ] Create docs/help/troubleshooting.md - common issues

### Help API (FR8)
- [ ] Create src/claude_headspace/routes/help.py blueprint
- [ ] Implement GET /api/help/topics endpoint
- [ ] Return topic list with slug, title, excerpt
- [ ] Implement GET /api/help/topics/<slug> endpoint
- [ ] Return topic content as markdown
- [ ] Handle 404 for unknown topics
- [ ] Register help_bp in app.py

### Help Modal UI (FR1-FR3, FR5-FR7)
- [ ] Create templates/partials/_help_modal.html
- [ ] Modal overlay with semi-transparent backdrop
- [ ] Search input field at top
- [ ] Table of contents sidebar
- [ ] Content area for documentation display
- [ ] Close button (X) in top-right
- [ ] Include modal in base.html

### Help Button (FR2)
- [ ] Add help button (?) to templates/partials/_header.html
- [ ] Style consistently with existing nav elements
- [ ] Wire click to open help modal

### Keyboard Shortcut (FR1, FR7, FR10)
- [ ] Create static/js/help.js
- [ ] Listen for `?` key on document
- [ ] Skip when focus in text input/textarea
- [ ] Open modal on keypress
- [ ] Close modal on Escape key
- [ ] Focus trap within modal
- [ ] Return focus on close

### Search Functionality (FR4, NFR1)
- [ ] Implement client-side search in help.js
- [ ] Build search index from topic content
- [ ] Match against titles and content
- [ ] Display results with title and excerpt
- [ ] Search results within 200ms

### Markdown Rendering (FR6)
- [ ] Implement markdown to HTML rendering
- [ ] Support headings (h1-h6)
- [ ] Support code blocks with syntax highlighting
- [ ] Support inline code
- [ ] Support links (internal and external)
- [ ] Support lists (ordered and unordered)
- [ ] Support emphasis (bold, italic)

### Accessibility (NFR2)
- [ ] Add ARIA labels and roles to modal
- [ ] Implement focus trap
- [ ] Announce modal open/close to screen readers
- [ ] Ensure keyboard navigation (Tab, Enter, Escape)
- [ ] Verify color contrast

## Phase 3: Testing

- [ ] Test GET /api/help/topics returns list
- [ ] Test GET /api/help/topics/<slug> returns content
- [ ] Test GET /api/help/topics/<invalid> returns 404
- [ ] Test markdown rendering
- [ ] Test search functionality
- [ ] Test modal opens on ? keypress
- [ ] Test modal closes on Escape
- [ ] Test modal closes on backdrop click
- [ ] Test focus trap
- [ ] Test help button opens modal

## Phase 4: Final Verification

- [ ] All tests passing
- [ ] Modal opens within 100ms
- [ ] Search results within 200ms
- [ ] No console errors
- [ ] Manual test: keyboard navigation
- [ ] Manual test: search and view topic
