## Why

Developers managing multiple projects with AI agents lose mental context when switching between projects. Brain reboot combines existing artifacts (waypoint + progress summary) into a single context restoration document, and staleness detection proactively flags projects needing attention — completing the Epic 3 intelligence layer.

## What Changes

- Add BrainRebootService that composes waypoint + progress summary into a formatted brain reboot document (no LLM calls)
- Add StalenessService that classifies projects into freshness tiers (fresh/aging/stale) based on Agent.last_seen_at
- Add POST/GET `/api/projects/<id>/brain-reboot` API endpoints
- Add brain reboot modal to dashboard with copy-to-clipboard and export functionality
- Add staleness indicators and "Needs Reboot" badges to dashboard project headers
- Add `brain_reboot` configuration section to config.yaml defaults

## Impact

- Affected specs: brain-reboot (new)
- Affected code:
  - NEW: `src/claude_headspace/services/brain_reboot.py` — BrainRebootService
  - NEW: `src/claude_headspace/services/staleness.py` — StalenessService
  - NEW: `src/claude_headspace/routes/brain_reboot.py` — API endpoints blueprint
  - NEW: `templates/partials/_brain_reboot_modal.html` — Modal template
  - NEW: `static/js/brain-reboot.js` — Modal + clipboard + export JS
  - MODIFIED: `src/claude_headspace/app.py` — Register services + blueprint
  - MODIFIED: `src/claude_headspace/config.py` — Add brain_reboot defaults
  - MODIFIED: `templates/partials/_project_column.html` — Add Brain Reboot button + staleness indicators
  - MODIFIED: `templates/partials/_project_group.html` — Add Brain Reboot button + staleness indicators
  - MODIFIED: `templates/dashboard.html` — Include modal + JS
  - MODIFIED: `src/claude_headspace/routes/dashboard.py` — Pass staleness data to templates

## Definition of Done

1. BrainRebootService generates formatted document combining waypoint + progress summary
2. Missing artifact handling: waypoint-only, summary-only, both-missing all work gracefully
3. POST `/api/projects/<id>/brain-reboot` generates and returns brain reboot content
4. GET `/api/projects/<id>/brain-reboot` returns most recently generated content
5. Brain Reboot modal opens from dashboard with formatted content display
6. Copy to Clipboard copies full content with visual feedback
7. Export saves brain_reboot.md to target project's docs/brain_reboot/ directory
8. Export creates directory structure if missing
9. Modal dismissable via close button, backdrop click, escape key
10. StalenessService classifies projects into fresh/aging/stale tiers
11. Staleness thresholds configurable in config.yaml (defaults: fresh 0-3d, aging 4-7d, stale 8+d)
12. Dashboard shows staleness indicators per project (green/yellow/red)
13. Stale projects show "Needs Reboot" badge
14. Projects with no agent history show no staleness indicator
15. All tests pass with zero failures
