# Tasks: e5-s7-config-help-system

## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Config/UI Parity (Phase 2a)

- [ ] 2.1 Add `tmux_bridge` section to CONFIG_SCHEMA with 3 fields (health_check_interval: int default 30, subprocess_timeout: int default 10, text_enter_delay_ms: int default 100)
- [ ] 2.2 Add `dashboard` section to CONFIG_SCHEMA with 2 fields (stale_processing_seconds: int default 600, active_timeout_minutes: int default 5)
- [ ] 2.3 Add `archive` section to CONFIG_SCHEMA with 4 fields (enabled: bool default true, retention.policy: string default "keep_last_n", retention.keep_last_n: int default 10, retention.days: int default 90)
- [ ] 2.4 Add missing `openrouter` fields to CONFIG_SCHEMA (retry.base_delay_seconds: float default 1.0, retry.max_delay_seconds: float default 30.0, priority_scoring.debounce_seconds: float default 5.0)
- [ ] 2.5 Add missing `headspace` flow_detection fields to CONFIG_SCHEMA (flow_detection.min_turn_rate: int default 6, flow_detection.max_frustration: float default 3.0, flow_detection.min_duration_minutes: int default 15)
- [ ] 2.6 Add `commander` section defaults to config.yaml (socket_path, health_check_interval, response_timeout)
- [ ] 2.7 Add help_text metadata to all CONFIG_SCHEMA fields for popover content
- [ ] 2.8 Add section_description metadata to all CONFIG_SCHEMA sections for section popovers

## 3. Popover Component (Phase 2b)

- [ ] 3.1 Add popover CSS styles to static/css/src/input.css (dark theme card, arrow/caret, animation, responsive)
- [ ] 3.2 Create static/js/config-help.js with popover logic (create/position/show/hide, single instance, viewport-aware positioning)
- [ ] 3.3 Add keyboard accessibility to popover (Tab focus on icons, Enter/Space toggle, Escape dismiss)
- [ ] 3.4 Add click-outside dismiss handler
- [ ] 3.5 Rebuild Tailwind CSS

## 4. Config Template Updates (Phase 2c)

- [ ] 4.1 Add ⓘ help icon buttons to section headers in templates/config.html
- [ ] 4.2 Add ⓘ help icon buttons to field labels in templates/config.html
- [ ] 4.3 Embed help metadata (description, default, range, help_url) as data attributes on icons
- [ ] 4.4 Include config-help.js script in config template

## 5. Help Page Anchor Support (Phase 2d)

- [ ] 5.1 Update help.js markdown renderer to add id attributes to heading elements (slugified heading text)
- [ ] 5.2 Add scroll-to-anchor on page load (parse window.location.hash, scroll to element)
- [ ] 5.3 Add brief highlight animation on anchor target section
- [ ] 5.4 Update "Learn more" links in popover to use anchor URLs (/help/configuration#section-slug)

## 6. Documentation (Phase 2e)

- [ ] 6.1 Expand docs/help/configuration.md with per-field practical documentation (what it does, when to change, consequences)
- [ ] 6.2 Add section introductory paragraphs to configuration.md
- [ ] 6.3 Ensure heading structure in configuration.md matches anchor IDs used by popovers

## 7. Testing (Phase 3)

- [ ] 7.1 Add tests for new CONFIG_SCHEMA sections (tmux_bridge, dashboard, archive) in test_config_editor.py
- [ ] 7.2 Add tests for new openrouter and headspace fields in test_config_editor.py
- [ ] 7.3 Add tests for help_text and section_description metadata presence
- [ ] 7.4 Add route tests for new sections appearing in GET /api/config response
- [ ] 7.5 Run targeted tests to verify no regressions

## 8. Final Verification

- [ ] 8.1 All tests passing
- [ ] 8.2 No linter errors
- [ ] 8.3 Visual verification of help icons and popovers on config page
- [ ] 8.4 Verify anchor deep-linking on help page
- [ ] 8.5 Verify all config.yaml fields have corresponding UI fields
