# tailwind-css Specification

## Purpose
TBD - created by archiving change e1-s1-flask-bootstrap. Update Purpose after archive.
## Requirements
### Requirement: Tailwind CSS Build Pipeline
The application SHALL include a Tailwind CSS build pipeline.

#### Scenario: Build CSS
- **WHEN** `npm run build:css` is executed
- **THEN** Tailwind CSS SHALL compile from source
- **AND** output to `static/css/main.css`

#### Scenario: Watch mode
- **WHEN** `npm run watch:css` is executed
- **THEN** CSS SHALL rebuild automatically on source changes

### Requirement: Theme Color Palette
The application SHALL use a dark terminal theme color palette defined as CSS custom properties.

#### Scenario: Theme colors available
- **WHEN** the CSS is loaded
- **THEN** CSS custom properties SHALL be available for:
- **AND** background colors (--bg-void, --bg-deep, --bg-surface, --bg-elevated, --bg-hover)
- **AND** accent colors (--cyan, --green, --amber, --red, --blue, --magenta)
- **AND** text colors (--text-primary, --text-secondary, --text-muted)
- **AND** border colors (--border, --border-bright)
- **AND** monospace font (--font-mono)

