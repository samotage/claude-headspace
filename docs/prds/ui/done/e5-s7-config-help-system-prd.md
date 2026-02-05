---
validation:
  status: valid
  validated_at: '2026-02-05T18:45:41+11:00'
---

## Product Requirements Document (PRD) — Configuration Help System & UI Parity

**Project:** Claude Headspace
**Scope:** Config page help icons, popovers, documentation, and full config.yaml/UI parity
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

The Claude Headspace configuration page has grown to encompass 13+ sections with 55+ fields, many of which are numeric values (timeouts, thresholds, intervals, pool sizes) whose purpose and impact are not self-evident. Additionally, approximately 15 fields present in config.yaml are not exposed in the config UI, creating hidden configuration that users cannot manage through the interface.

This PRD addresses both problems: (1) closing the parity gap so every config.yaml setting is editable via the UI, and (2) adding a contextual help system with info icons, popovers, and expanded documentation so users understand what each setting does before changing it.

The result is a fully self-documenting configuration system where every setting is visible, every setting is explained, and guidance is available at the point of change.

---

## 1. Context & Purpose

### 1.1 Context

After 5 epics of feature development, each new subsystem (headspace monitoring, archive, tmux bridge, dashboard controls, flow detection) added configuration fields. The config schema that drives the UI did not keep pace with config.yaml, resulting in hidden settings. The existing help documentation at `/help/configuration` provides only brief one-liners per field without practical guidance on when or why to change values.

### 1.2 Target User

The primary user of Claude Headspace — a developer managing multiple Claude Code sessions who needs to tune system behaviour (reaper timeouts, frustration thresholds, polling intervals, notification settings) without reading source code or risking misconfiguration.

### 1.3 Success Moment

The user hovers over a config field they don't understand, sees a popover explaining what it does and what happens if they set it too high or low, clicks "Learn more" to read the full docs, and confidently makes the change.

---

## 2. Scope

### 2.1 In Scope

- Expose all config.yaml fields in the config UI by adding missing sections and fields to CONFIG_SCHEMA (closing the parity gap)
- Add a clickable help/info icon to every config section header
- Add a clickable help/info icon to every config field label
- Implement a popover component that displays: field description, default value, valid range (if applicable), and a "Learn more" link
- The "Learn more" link navigates to `/help/configuration` and scrolls to the relevant section/field anchor
- Add deep-link anchor support to the help page so external links can target specific sections within a topic
- Expand `docs/help/configuration.md` with practical per-field documentation (1-3 sentences per field covering: what it does, when you'd change it, and consequences of incorrect values)
- Ensure any section in CONFIG_SCHEMA also has explicit values in config.yaml (add `commander` defaults to config.yaml)

### 2.2 Out of Scope

- Editing the dynamic pricing map (`openrouter.pricing`) — this is a dynamic mapping of model names to pricing and is excluded from the UI
- Adding brand-new configuration options that do not currently exist in config.yaml
- Restructuring the config.yaml format, section naming, or key hierarchy
- Changes to help topics other than `configuration.md`
- Building a general-purpose tooltip/popover framework for reuse outside the config page

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Every field present in config.yaml (except `openrouter.pricing`) has a corresponding editable field in the config UI
2. Every section header in the config UI displays a clickable help icon
3. Every field label in the config UI displays a clickable help icon
4. Clicking a help icon opens a popover containing: a practical description, the default value, the valid range (for numeric fields), and a "Learn more" link
5. The "Learn more" link navigates to `/help/configuration` and scrolls to the correct section or field anchor
6. The help page supports anchor-based deep-linking (e.g., `/help/configuration#headspace`) that scrolls to the target section on load
7. `docs/help/configuration.md` contains practical documentation for every exposed config field
8. The `commander` section appears in config.yaml with explicit default values

### 3.2 Non-Functional Success Criteria

1. Popovers are accessible via keyboard (focusable, dismissible with Escape)
2. Popovers do not obscure the field input they describe
3. Only one popover is visible at a time (opening one closes any other)
4. Help icons do not disrupt the existing config page layout or field alignment

---

## 4. Functional Requirements (FRs)

### Config/UI Parity

**FR1:** The config UI must expose the `tmux_bridge` section with fields: `health_check_interval`, `subprocess_timeout`, `text_enter_delay_ms`.

**FR2:** The config UI must expose the `dashboard` section with fields: `stale_processing_seconds`, `active_timeout_minutes`.

**FR3:** The config UI must expose the `archive` section with fields: `enabled`, `retention.policy`, `retention.keep_last_n`, `retention.days`.

**FR4:** The config UI must expose the missing `openrouter` fields: `retry.base_delay_seconds`, `retry.max_delay_seconds`, `priority_scoring.debounce_seconds`.

**FR5:** The config UI must expose the missing `headspace` flow detection fields: `flow_detection.min_turn_rate`, `flow_detection.max_frustration`, `flow_detection.min_duration_minutes`.

**FR6:** The `commander` section must be added to config.yaml with explicit default values matching the schema defaults.

### Help Icons

**FR7:** Each config section header must display a small, clickable info icon (e.g., a circled "i" or question mark) adjacent to the section title.

**FR8:** Each config field label must display a small, clickable info icon adjacent to the label text.

**FR9:** Help icons must be visually subtle (muted colour) and not compete with the field label or input for attention.

### Popover Component

**FR10:** Clicking a field help icon must display a popover containing:
- A practical description of the field (1-3 sentences)
- The default value
- The valid range (for numeric fields with min/max constraints)
- A "Learn more" link to the corresponding section in `/help/configuration`

**FR11:** Clicking a section help icon must display a popover containing:
- A brief description of what the section controls
- A "Learn more" link to the corresponding section in `/help/configuration`

**FR12:** Only one popover may be visible at a time. Opening a new popover must close any currently open popover.

**FR13:** Popovers must be dismissible by clicking outside them, pressing Escape, or clicking the help icon again.

**FR14:** Popovers must position themselves to avoid overflowing the viewport (e.g., flip above if near the bottom of the screen).

### Deep-Link Anchors

**FR15:** The help page must support anchor-based deep-linking. Navigating to `/help/configuration#section-name` must scroll to and highlight the target section.

**FR16:** The "Learn more" links in popovers must use anchor URLs that correspond to section headings in the configuration help document.

### Documentation

**FR17:** `docs/help/configuration.md` must contain documentation for every config field exposed in the UI, organised by section.

**FR18:** Each field's documentation must include: what the field controls, when a user would want to change it, and what happens if the value is set too high or too low (for numeric fields).

**FR19:** Each section must have a brief introductory paragraph explaining what the section controls and how its fields relate to each other.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Popovers must be keyboard-accessible: help icons must be focusable via Tab, activatable via Enter/Space, and popovers dismissible via Escape.

**NFR2:** Popover content must be readable at all supported viewport widths (down to 640px mobile breakpoint already supported by the config page).

**NFR3:** The popover implementation must use vanilla JS consistent with the project's no-framework frontend approach.

---

## 6. UI Overview

### Config Page Changes

The config page layout remains the same. Two additions:

1. **Section headers:** A small `ⓘ` icon appears to the right of each section title (e.g., "HEADSPACE ⓘ"). Clicking it opens a section-level popover.

2. **Field labels:** A small `ⓘ` icon appears to the right of each field label (e.g., "polling interval ⓘ"). Clicking it opens a field-level popover.

### Popover Appearance

A small card/tooltip anchored near the help icon containing:
- **Title:** Field name in readable form
- **Description:** 1-3 sentences of practical guidance
- **Default:** The default value
- **Range:** Min–Max (for numeric fields only)
- **Link:** "Learn more →" linking to the help page section

The popover has a subtle border, matches the application's dark theme, and has a small arrow/caret pointing to the help icon.

### Help Page Changes

The configuration topic in the help page gains heading anchors (IDs on section headers) so that external links can deep-link to specific sections. When navigated to via anchor, the target section briefly highlights to orient the user.
