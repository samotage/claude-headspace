# Proposal Summary: e5-s7-config-help-system

## Architecture Decisions
- Popover component built as vanilla JS module (config-help.js) following card-tooltip.js patterns — no framework dependencies
- Help metadata (help_text, section_description) embedded in CONFIG_SCHEMA FieldSchema/SectionSchema, not in a separate data file
- Popover content rendered from data attributes on help icon elements (no AJAX calls needed)
- Anchor deep-linking implemented in help.js by adding id attributes to rendered headings and parsing window.location.hash

## Implementation Approach
- **Schema-first:** Add all missing sections/fields to CONFIG_SCHEMA in config_editor.py. This automatically makes them appear in the config UI via existing Jinja2 iteration.
- **Metadata-driven popovers:** Add `help_text` (1-3 sentences) and `section_description` to schema definitions. Template renders these as data-* attributes on help icon buttons. JS reads data attributes to populate popover.
- **Single popover instance:** One DOM element repositioned and repopulated on each icon click (like card-tooltip.js pattern).
- **Help page anchors:** Modify help.js markdown renderer to generate slugified id attributes on heading elements. Add hash change listener for scroll-to-anchor.

## Files to Modify

### Services
- `src/claude_headspace/services/config_editor.py` — Add 3 new sections (tmux_bridge, dashboard, archive) + 6 new fields in existing sections (openrouter, headspace) + help_text metadata on all fields + section_description on all sections

### Config
- `config.yaml` — Add commander section with explicit defaults (socket_path, health_check_interval, response_timeout)

### Templates
- `templates/config.html` — Add ⓘ icon buttons in section headers and field labels, add popover container div, include config-help.js script tag

### Static Assets (New)
- `static/js/config-help.js` (new) — Popover component: create/position/show/hide, keyboard handling, click-outside dismiss, viewport-aware positioning

### Static Assets (Modified)
- `static/css/src/input.css` — Add .config-help-icon and .config-help-popover styles (dark theme card, arrow, animation)
- `static/js/help.js` — Add id attributes to rendered headings, scroll-to-anchor on page load, anchor highlight animation

### Documentation
- `docs/help/configuration.md` — Expand all field documentation with practical guidance (what it does, when to change, consequences)

### Tests
- `tests/services/test_config_editor.py` — Tests for new schema sections and help_text metadata
- `tests/routes/test_config.py` — Tests for new sections in API responses

## Acceptance Criteria
1. Every config.yaml field (except openrouter.pricing) has a corresponding editable field in the config UI
2. Every section header and field label displays a clickable ⓘ icon
3. Clicking a help icon opens a popover with description, default, range, and "Learn more" link
4. Only one popover visible at a time; keyboard accessible; viewport-aware
5. "Learn more" links navigate to /help/configuration#section-slug and scroll to target
6. Help page supports anchor deep-linking with scroll and brief highlight
7. docs/help/configuration.md has comprehensive per-field documentation
8. commander section present in config.yaml with explicit defaults

## Constraints and Gotchas
- **Tailwind rebuild required:** After adding CSS to input.css, must run `npx tailwindcss -i static/css/src/input.css -o static/css/main.css` (v3, NOT v4)
- **Nested field dot-notation:** CONFIG_SCHEMA uses dot-notation for nested fields (e.g., `retention.policy`). The flatten/unflatten functions in config_editor.py handle this. New archive and flow_detection fields must follow this pattern.
- **Hidden aria-describedby:** Field descriptions already exist as hidden paragraphs in config.html. The help system should use help_text from schema (richer content) rather than these existing descriptions.
- **openrouter.pricing exclusion:** The pricing map is explicitly out of scope — do not add to schema.
- **Template field-group structure:** Each field is wrapped in `.field-group` with `data-section` and `data-field` attributes. Help icons should be placed inside `.cfg-label` div, after the label element.
- **Card tooltip coexistence:** config-help.js popover is separate from card-tooltip.js. They use different CSS classes and don't interact.

## Git Change History

### Related Files
- Config: docs/prds/ui/done/e2-s1-config-ui-prd.md, openspec/changes/archive/2026-01-29-e2-s1-config-ui/

### OpenSpec History
- e2-s1-config-ui (archived 2026-01-29) — Original config UI implementation
- e4-s2b-project-controls-ui (archived 2026-02-02) — Project controls in UI

### Implementation Patterns
- Config UI follows schema-driven rendering: CONFIG_SCHEMA → Jinja2 iteration → form fields
- Vanilla JS modules in static/js/ with no build step
- CSS source of truth is static/css/src/input.css, compiled to static/css/main.css via Tailwind v3
- Dark theme with CSS variables (--border-bright, --text-primary, etc.)

## Q&A History
- No clarifications needed — PRD was clear and conflict-free

## Dependencies
- No new packages needed
- No database migrations
- No external services

## Testing Strategy
- Unit tests for CONFIG_SCHEMA completeness (all config.yaml keys present in schema)
- Unit tests for help_text and section_description metadata presence on all fields/sections
- Route tests verifying new sections appear in GET /api/config response
- Manual visual verification of popovers on config page
- Manual verification of anchor deep-linking on help page

## OpenSpec References
- proposal.md: openspec/changes/e5-s7-config-help-system/proposal.md
- tasks.md: openspec/changes/e5-s7-config-help-system/tasks.md
- spec.md: openspec/changes/e5-s7-config-help-system/specs/config/spec.md
