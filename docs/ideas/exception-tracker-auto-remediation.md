# Idea: Lightweight Exception Tracker & Auto-Remediation

**Status:** Idea — Not yet assigned to an epic
**Author:** Sam
**Date:** 2026-02-15
**Priority:** High — addresses silent failure problem across all monitored projects

---

## 1. Problem Statement

Exceptions blow up silently across projects. No one knows until something visibly breaks — by which time the root cause is buried under subsequent failures. There is no systematic way to:

- **Know when something fails** — exceptions happen in production/dev and disappear into log files nobody reads
- **Understand what failed** — stack traces require manual investigation to understand root cause
- **Fix it automatically** — even when the fix is straightforward, it requires a human to notice, investigate, and manually start a Claude Code session to fix it

### The Vision

Applications post their failures to Claude Headspace. Claude Headspace receives them, analyses them, notifies the user, and then drives the fix — automatically spawning Claude Code agents to remediate, tracking the entire lifecycle from "exception caught" to "fix committed" on the dashboard.

This turns Claude Headspace from a passive monitoring tool into an **active remediation platform**.

---

## 2. How It Works

### Phase 1: Exception Ingestion

Applications report exceptions to Claude Headspace via a simple HTTP POST. No SDK required — just a `curl` call or a few lines of Python in an error handler.

```
POST /api/exceptions
{
  "project": "my-app",
  "exception_type": "IntegrityError",
  "message": "duplicate key value violates unique constraint",
  "stacktrace": "...",
  "context": {
    "endpoint": "/api/users",
    "method": "POST",
    "request_id": "abc-123"
  }
}
```

**Ingestion sources:**

| Source | Mechanism |
|--------|-----------|
| Flask apps (including Headspace itself) | `got_request_exception` signal → self-post |
| Other Python apps | Lightweight exception hook (logging handler or sys.excepthook) |
| Claude Code hooks | Hook failures already flow through the hook receiver — surface them |
| Any HTTP-capable app | Raw POST to the endpoint |
| Background threads/services | Wrap thread targets with exception capture |

**On ingestion, Claude Headspace:**

1. Persists the exception (new model: `Exception` or `Failure`)
2. Deduplicates — groups by exception type + location (file:line) + message fingerprint
3. Tracks occurrence count, first/last seen, affected projects
4. Broadcasts an SSE event to the dashboard

### Phase 2: Analysis & Notification

When a new exception (or a new occurrence of a grouped exception) arrives:

1. **LLM analysis** — send the stack trace + context to the inference service for root cause analysis. Use the existing OpenRouter integration (Haiku-level for triage, Sonnet for deeper analysis)
2. **Severity classification** — critical (app down), error (feature broken), warning (degraded), noise (expected/transient)
3. **Notify the user:**
   - macOS notification (terminal-notifier, already wired up) for critical/error
   - Dashboard panel showing active exceptions with occurrence count, severity, LLM analysis
   - Email digest (SMTPHandler) for when you're away — configurable frequency (immediate for critical, hourly digest for errors)
4. **Link to project** — match the reporting project to an existing Claude Headspace project record for context

### Phase 3: Auto-Remediation

This is where it gets interesting. When an exception is identified and analysed:

1. **Assess fixability** — LLM determines if this is something an agent can likely fix automatically (e.g., missing migration, type error, import error) vs. something that needs human judgment (architectural issue, data corruption)
2. **User approval gate** — for auto-fixable exceptions, present the proposed fix approach on the dashboard with an "Approve Auto-Fix" button. User can approve, reject, or modify the approach. Configurable: trusted projects can skip approval for low-severity fixes.
3. **Spawn Claude Code agent** — on approval, launch a Claude Code session in the affected project's directory with a targeted prompt: the exception, stack trace, LLM analysis, and fix instructions
4. **Track on dashboard** — the spawned agent appears as a normal agent card on the dashboard, but tagged with the exception it's fixing. The exception's status moves through: `NEW → ANALYSING → FIX_PROPOSED → FIX_IN_PROGRESS → FIX_COMMITTED → VERIFIED → RESOLVED`
5. **Verification** — after the agent commits a fix, optionally re-run the failing scenario to verify the exception no longer occurs. Mark as resolved or re-open.

---

## 3. Data Model

```
Exception/Failure:
  id, project_id, fingerprint (hash for dedup grouping)
  exception_type, message, stacktrace
  context (JSONB - endpoint, method, request data, environment)
  severity (critical/error/warning/noise)
  status (new/analysing/fix_proposed/fix_in_progress/fix_committed/verified/resolved/ignored)
  llm_analysis (text - root cause summary)
  fix_approach (text - proposed remediation)
  occurrence_count, first_seen_at, last_seen_at
  agent_id (FK - the agent spawned to fix it, nullable)
  resolved_at, resolved_by (agent or human)
```

---

## 4. Dashboard Integration

New "Exceptions" panel on the dashboard (or a dedicated view):

- **Exception cards** grouped by fingerprint, showing: type, message snippet, occurrence count, severity badge, time since last occurrence, project, status
- **Expandable detail** with full stack trace, LLM analysis, context
- **Action buttons:** Ignore, Approve Auto-Fix, Assign to Agent, Mark Resolved
- **Filtering** by project, severity, status
- **SSE-driven** — new exceptions appear in real-time, status updates as agents work fixes

---

## 5. Configuration

New section in `config.yaml`:

```yaml
exceptions:
  enabled: true
  api_key: "optional-shared-secret-for-ingestion-auth"

  notification:
    macos: true                    # terminal-notifier for critical/error
    email:
      enabled: false
      smtp_host: "smtp.gmail.com"
      smtp_port: 587
      from: "headspace@example.com"
      to: ["sam@example.com"]
      digest_interval: 3600        # seconds between email digests (0 = immediate)

  auto_remediation:
    enabled: false                 # opt-in — off by default
    approval_required: true        # require dashboard approval before spawning agent
    trusted_projects: []           # projects that can skip approval for low-severity
    max_concurrent_fixes: 2        # limit concurrent auto-fix agents

  dedup:
    fingerprint_fields: ["exception_type", "stacktrace_location"]
    cooldown: 300                  # seconds before re-notifying for same fingerprint

  analysis:
    model_level: "turn"            # inference level for triage (haiku)
    deep_analysis_level: "task"    # inference level for root cause (sonnet)
```

---

## 6. Client Integration Examples

### Flask app (self-integration for Claude Headspace)

```python
from flask import got_request_exception
import requests

def report_exception(sender, exception, **kwargs):
    requests.post("https://smac.griffin-blenny.ts.net:5055/api/exceptions", json={
        "project": "claude-headspace",
        "exception_type": type(exception).__name__,
        "message": str(exception),
        "stacktrace": traceback.format_exc(),
    }, verify=False, timeout=5)

got_request_exception.connect(report_exception, app)
```

### Generic Python (any project)

```python
# Add to project's error handling or as a logging handler
import logging

class HeadspaceExceptionHandler(logging.Handler):
    def emit(self, record):
        if record.exc_info:
            # POST to Claude Headspace /api/exceptions
            ...
```

### Claude Code hook failures

Already flowing through `hook_receiver.py` — surface processing errors as exceptions automatically.

---

## 7. Implementation Phases

| Phase | Scope | Effort |
|-------|-------|--------|
| **P1: Ingest & Store** | POST endpoint, Exception model, dedup, migration | Small |
| **P2: Notify** | macOS notifications, dashboard panel (SSE), basic severity classification | Small-Medium |
| **P3: Analyse** | LLM triage via existing inference service, root cause summaries | Small |
| **P4: Email** | SMTPHandler integration, digest mode | Small |
| **P5: Auto-Remediate** | Agent spawning, fix lifecycle tracking, approval UI | Medium-Large |
| **P6: Verify** | Post-fix verification, auto-close loop | Medium |

P1-P3 deliver immediate value — you'll know when things break and why. P5-P6 are the ambitious end-state.

---

## 8. Why Build, Not Buy

- **No new infrastructure** — uses existing PostgreSQL, SSE, inference service, notification service
- **No SaaS dependency** — runs entirely within Claude Headspace
- **Tight integration** — exceptions link directly to projects and agents on the dashboard
- **Auto-remediation is novel** — no off-the-shelf tool spawns Claude Code agents to fix the bugs it catches
- **Simple ingestion API** — any app can POST; no SDK lock-in, no vendor agent to install
