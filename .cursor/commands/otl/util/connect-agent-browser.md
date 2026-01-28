---
name: Connect Agent Browser
description: Connect agent-browser to Chrome via CDP and take a snapshot
category: Util
tags: [browser, agent-browser, cdp]
args:
  - name: url
    description: "URL to navigate to (e.g., http://claude-monitor.otagelabs.test/)"
    required: true
---

Connect agent-browser to a running Chrome instance via CDP port 9222.

**Prerequisites:**
- Chrome must be running with `--remote-debugging-port=9222`
- Run `/otl/util/start-chrome-debug` first if not already running
- Note: The debug Chrome uses a separate profile - you won't have your logged-in sessions

## Instructions

1. Navigate to the provided URL:

```bash
agent-browser --cdp 9222 open "$ARGUMENTS"
```

2. Take a snapshot to see the page content:

```bash
agent-browser --cdp 9222 snapshot
```

## Other Commands

```bash
# Take accessibility snapshot of current page
agent-browser --cdp 9222 snapshot

# Interactive elements only
agent-browser --cdp 9222 snapshot -i

# Click an element by ref (from snapshot)
agent-browser --cdp 9222 click @e5

# Type into an element
agent-browser --cdp 9222 type @e3 "hello"

# Take screenshot
agent-browser --cdp 9222 screenshot
```

## Authentication (Optional)

If the target site requires authentication, add a Bearer token:

```bash
agent-browser --cdp 9222 open "$ARGUMENTS" --headers '{"Authorization":"Bearer YOUR_TOKEN_HERE"}'
```

To make this persistent, update the command above with your actual token.
