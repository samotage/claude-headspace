## Product Requirements Document (PRD) — Help/Documentation System

**Project:** Claude Headspace v3.1
**Scope:** Epic 2, Sprint 3 (E2-S3) — Searchable help and documentation system
**Author:** PM Agent
**Status:** Valid

---

## Executive Summary

Claude Headspace needs an accessible, searchable help system that allows users to understand and effectively use all features without leaving the application. Users should be able to quickly find answers about the dashboard, objectives, configuration, waypoints, and troubleshooting through a keyboard-accessible modal overlay.

The help system provides self-service documentation that reduces friction for new users, enables feature discovery, and serves as a reference for power users. Documentation is markdown-based for easy maintenance and updates as features evolve.

Success means users can press `?` to instantly access searchable documentation, find relevant topics within seconds, and close the modal seamlessly to return to their workflow.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace is a Kanban-style dashboard for tracking Claude Code sessions across multiple projects. As the application grows with configuration UI (E2-S1), waypoint editing (E2-S2), and future intelligence features (Epic 3), users need a centralized place to learn how features work.

Currently, users must read source code, CLAUDE.md, or external documentation to understand the system. This creates friction, especially for new users or when exploring less-used features.

### 1.2 Target User

- **New users** getting started with Claude Headspace for the first time
- **Existing users** exploring features they haven't used before (e.g., waypoint editing)
- **Power users** looking up specific configuration options or troubleshooting steps

### 1.3 Success Moment

A user wonders "How do I set an objective?" → presses `?` → types "objective" → sees the Objective documentation → understands how to use the feature → closes modal and sets their first objective.

---

## 2. Scope

### 2.1 In Scope

- Help modal overlay accessible via `?` keyboard shortcut
- Help button in UI for keyboard-less access
- Markdown-based documentation source files
- Client-side full-text search across all documentation
- Table of contents navigation
- Documentation topics covering:
  - Getting started / Quick start
  - Dashboard overview and usage
  - Objective setting and management
  - Configuration options (config.yaml)
  - Waypoint editing and brain_reboot
  - Troubleshooting common issues
- Modal dismissal via Escape key or click outside
- Server-side help content API endpoint

### 2.2 Out of Scope

- Video tutorials or screencasts
- Multi-language/internationalization support
- User-contributed documentation or wiki features
- Context-sensitive help (tooltips on UI elements)
- AI-powered help chat or Q&A
- PDF export of documentation
- Version-specific documentation branches

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Press `?` key on dashboard → help modal opens within 100ms
2. Help button visible in UI → clicking opens help modal
3. Type search query → relevant topics appear instantly (< 200ms)
4. Click topic in results or TOC → full documentation displays
5. Press Escape or click outside modal → modal closes
6. All major features have documentation (dashboard, objective, config, waypoint, troubleshooting)
7. Documentation renders markdown correctly (headings, code blocks, links, lists)

### 3.2 Non-Functional Success Criteria

1. Search index loads within 500ms on page load
2. Modal is keyboard-navigable (Tab, Enter, Escape)
3. Modal meets WCAG 2.1 AA accessibility standards
4. Documentation files are easily editable (plain markdown)
5. Help system works without JavaScript disabled (graceful degradation to static docs link)

---

## 4. Functional Requirements (FRs)

### FR1: Keyboard Shortcut Activation

The help modal opens when the user presses the `?` key anywhere in the application, except when focus is in a text input field.

### FR2: Help Button Activation

A help button (e.g., `?` icon) is visible in the dashboard header, providing mouse/touch access to the help modal.

### FR3: Modal Overlay Display

The help modal displays as a centered overlay with:
- Semi-transparent backdrop
- Close button (X) in top-right corner
- Search input field at the top
- Table of contents sidebar
- Content area for displaying documentation

### FR4: Search Functionality

Users can type in the search field to filter documentation topics. Search matches against:
- Topic titles
- Topic content (full-text)
- Keywords/tags

Results display as a list of matching topics with title and brief excerpt.

### FR5: Table of Contents Navigation

A table of contents displays all available documentation topics, organized hierarchically:
- Getting Started
- Dashboard
- Objective
- Configuration
- Waypoints
- Troubleshooting

Clicking a topic loads its content in the main content area.

### FR6: Documentation Rendering

Markdown documentation files render with proper formatting:
- Headings (h1-h6)
- Code blocks with syntax highlighting
- Inline code
- Links (internal navigation and external URLs)
- Lists (ordered and unordered)
- Emphasis (bold, italic)

### FR7: Modal Dismissal

The modal closes when:
- User presses Escape key
- User clicks outside the modal (on backdrop)
- User clicks the close button (X)

Focus returns to the previously focused element after modal closes.

### FR8: Help Content API

A server-side API endpoint serves help documentation content:
- Returns markdown content for requested topic
- Supports listing all available topics
- Optional: Returns search index data for client-side search

### FR9: Documentation Topics

The following documentation topics are created:
- `index.md` — Table of contents and overview
- `getting-started.md` — Quick start guide for new users
- `dashboard.md` — Dashboard overview, agent cards, states, sorting
- `objective.md` — Setting and managing the global objective
- `configuration.md` — config.yaml options and how to edit them
- `waypoints.md` — Waypoint editing, brain_reboot concept, archiving
- `troubleshooting.md` — Common issues and solutions

### FR10: Help Accessibility from All Pages

The `?` keyboard shortcut and help button function on all application pages (dashboard, objective, logging).

---

## 5. Non-Functional Requirements (NFRs)

### NFR1: Performance

- Modal open time: < 100ms from keypress
- Search results: < 200ms from keystroke
- Initial search index load: < 500ms

### NFR2: Accessibility

- Modal traps focus while open
- All interactive elements keyboard accessible
- Proper ARIA labels and roles
- Sufficient color contrast (WCAG 2.1 AA)
- Screen reader announces modal open/close

### NFR3: Maintainability

- Documentation stored as plain markdown files
- No build step required to update documentation
- Documentation changes take effect on next page load

### NFR4: Browser Compatibility

- Works in Safari, Chrome, Firefox (latest 2 versions)
- Graceful degradation if JavaScript disabled

---

## 6. UI Overview

### 6.1 Help Modal Layout

```
┌─────────────────────────────────────────────────────────────┐
│  ┌─────────────────────────────────────────────────────┐ X │
│  │ 🔍 Search documentation...                          │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────┐  ┌────────────────────────────────────┐  │
│  │ Contents     │  │                                    │  │
│  │              │  │  # Getting Started                 │  │
│  │ • Getting    │  │                                    │  │
│  │   Started    │  │  Welcome to Claude Headspace...    │  │
│  │ • Dashboard  │  │                                    │  │
│  │ • Objective  │  │  ## Quick Start                    │  │
│  │ • Config     │  │                                    │  │
│  │ • Waypoints  │  │  1. Launch a Claude Code session   │  │
│  │ • Trouble-   │  │  2. Open the dashboard...          │  │
│  │   shooting   │  │                                    │  │
│  │              │  │                                    │  │
│  └──────────────┘  └────────────────────────────────────┘  │
│                                                             │
│  Press Escape or click outside to close                     │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 Search Results View

When user types in search field, the content area shows search results:

```
┌────────────────────────────────────────────────────────────┐
│  Results for "objective"                                   │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │ Objective                                          │   │
│  │ Set and manage the global objective that guides... │   │
│  └────────────────────────────────────────────────────┘   │
│                                                            │
│  ┌────────────────────────────────────────────────────┐   │
│  │ Dashboard                                          │   │
│  │ ...agents are prioritized according to objective... │   │
│  └────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────┘
```

### 6.3 Help Button Location

The help button appears in the dashboard header, aligned with other navigation elements:

```
┌─────────────────────────────────────────────────────────────┐
│  Claude Headspace          Dashboard  Objective  Logging  ? │
└─────────────────────────────────────────────────────────────┘
```

### 6.4 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `?` | Open help modal |
| `Escape` | Close help modal |
| `Tab` | Navigate between elements |
| `Enter` | Select focused topic |
| `/` | Focus search input (when modal open) |

---

## 7. Technical Context

*Note: This section provides implementation guidance, not requirements.*

### 7.1 Recommended Approach

- **Search library:** lunr.js for client-side full-text search (lightweight, no dependencies)
- **Markdown rendering:** marked.js or similar client-side markdown parser
- **Modal pattern:** Follow existing partials pattern (`templates/partials/_help_modal.html`)
- **JavaScript:** Add `static/js/help.js` for modal and search logic
- **Routes:** Add `src/claude_headspace/routes/help.py` for help content API

### 7.2 Documentation Location

```
docs/help/
├── index.md
├── getting-started.md
├── dashboard.md
├── objective.md
├── configuration.md
├── waypoints.md
└── troubleshooting.md
```

### 7.3 Integration Points

- Modal overlays on existing Epic 1 dashboard (all pages)
- Keyboard event listener on document level
- Help button in `_header.html` partial

---

## 8. Open Questions

### 8.1 Search Index Location

**Question:** Should the search index be pre-built at server startup or built client-side on first load?

**Options:**
- Client-side build: Simpler, no build step, slightly slower first load
- Pre-built: Faster first load, requires server restart to update

**Recommendation:** Client-side build for simplicity. Documentation is small enough that index build time is negligible.

### 8.2 External Links

**Question:** Should documentation link to external resources (Claude Code docs, Anthropic docs)?

**Options:**
- Yes: More comprehensive, may become stale
- No: Self-contained, less maintenance

**Recommendation:** Yes, sparingly, with note that external links may change.

---

## 9. Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-01-29 | PM Agent | Initial PRD for E2-S3 Help System |
