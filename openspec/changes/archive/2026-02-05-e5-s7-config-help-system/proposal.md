# Proposal: e5-s7-config-help-system

## Why

The config page has 55+ fields across 13 sections but ~15 fields present in config.yaml are not exposed in the UI, and existing field descriptions are hidden in `aria-describedby` attributes with no visual guidance. Users cannot understand what numeric settings (timeouts, thresholds, intervals) do without reading source code.

## What Changes

### Config/UI Parity
- Add `tmux_bridge` section to CONFIG_SCHEMA (3 fields: health_check_interval, subprocess_timeout, text_enter_delay_ms)
- Add `dashboard` section to CONFIG_SCHEMA (2 fields: stale_processing_seconds, active_timeout_minutes)
- Add `archive` section to CONFIG_SCHEMA (4 fields: enabled, retention.policy, retention.keep_last_n, retention.days)
- Add missing `openrouter` fields: retry.base_delay_seconds, retry.max_delay_seconds, priority_scoring.debounce_seconds
- Add missing `headspace` fields: flow_detection.min_turn_rate, flow_detection.max_frustration, flow_detection.min_duration_minutes
- Add `commander` defaults to config.yaml

### Help System
- Add clickable ⓘ info icons to every section header and field label
- Implement popover component (vanilla JS) showing: description, default, range, "Learn more" link
- Single popover visible at a time, keyboard accessible, viewport-aware positioning
- Add anchor-based deep-linking to help page (heading IDs, scroll-to-anchor on load, highlight)
- Expand docs/help/configuration.md with practical per-field documentation

## Impact

- Affected specs: config, help
- Affected code:
  - `src/claude_headspace/services/config_editor.py` — CONFIG_SCHEMA additions (3 new sections, 6 new fields in existing sections)
  - `config.yaml` — Add commander defaults
  - `templates/config.html` — Help icons in section headers and field labels, popover container
  - `static/js/config-help.js` (new) — Popover component with positioning, keyboard handling, dismiss logic
  - `static/css/src/input.css` — Popover styles (following card-tooltip.js pattern)
  - `static/js/help.js` — Anchor ID generation on headers, scroll-to-anchor on page load
  - `docs/help/configuration.md` — Expanded per-field documentation with practical guidance
  - `tests/services/test_config_editor.py` — Tests for new schema sections
  - `tests/routes/test_config.py` — Tests for new sections in API responses

## Definition of Done

- [ ] Every config.yaml field (except openrouter.pricing) has a corresponding editable UI field
- [ ] Every section header displays a clickable ⓘ icon
- [ ] Every field label displays a clickable ⓘ icon
- [ ] Clicking a help icon opens a popover with description, default, range, "Learn more" link
- [ ] Only one popover visible at a time
- [ ] Popovers keyboard accessible (Tab, Enter/Space, Escape)
- [ ] Popovers position to avoid viewport overflow
- [ ] "Learn more" links navigate to /help/configuration#section-name
- [ ] Help page supports anchor deep-linking with scroll and highlight
- [ ] docs/help/configuration.md has practical documentation for all fields
- [ ] commander section in config.yaml with explicit defaults
- [ ] All tests passing

## Risks

- **Layout disruption:** Help icons could break field alignment — mitigated by using small inline icons with muted colour
- **Popover positioning edge cases:** Near viewport edges — mitigated by viewport-aware flip logic (established pattern in card-tooltip.js)
- **Schema growth:** Adding ~12 fields increases schema size — acceptable, all fields already exist in config.yaml

## Alternatives Considered

1. **Inline descriptions (always visible):** Rejected — clutters the form, descriptions already hidden in aria-describedby
2. **Hover tooltips instead of click popovers:** Rejected — not accessible, no mobile support
3. **Separate help modal per section:** Rejected — too heavy, breaks flow of config editing
