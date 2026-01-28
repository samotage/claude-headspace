---
name: '92: prd-notify'
description: 'Debug/utility command to manually send Slack notifications'
---

# 92: PRD Notify (Debug/Utility)

**Command name:** `92: prd-notify`

**Purpose:** Debug/utility command to manually send Slack notifications.

**Input:** 
- `{{type}}` - Notification type: decision_needed, error, complete
- `{{message}}` - Message to send

---

## Prompt

You are sending a manual Slack notification for debugging or utility purposes.

**Available notification types:**

1. `decision_needed` - Alert that human intervention is required
2. `error` - Alert about an error condition
3. `complete` - Alert that processing finished

---

## Send Notification

```bash
ruby orch/notifier.rb {{type}} --message "{{message}}" --change-name "[optional: current change name]" --branch "[optional: current branch]"
```

**For decision_needed, also include:** `--checkpoint "[type]" --action "[what to do]"`

**For error, also include:** `--phase "[current phase]" --resolution "[suggested fix]"`

**For complete, also include:** `--next-prd "[path to next PRD if any]"`

---

## Examples

### Decision Needed
```bash
ruby orch/notifier.rb decision_needed --change-name "inquiry-02-email" --message "Proposal ready for review" --checkpoint "awaiting_proposal_approval" --action "Review the OpenSpec files and approve"
```

### Error
```bash
ruby orch/notifier.rb error --change-name "inquiry-02-email" --message "Tests failed after retries" --phase "test" --resolution "Review test failures and fix manually"
```

### Complete
```bash
ruby orch/notifier.rb complete --change-name "inquiry-02-email" --message "PR merged successfully" --next-prd "docs/prds/inquiry-03-sms-prd.md"
```

---

## Output

```
✅ Slack notification sent
   Type: {{type}}
   Message: {{message}}
```

Or if webhook not configured:

```
⚠️ SLACK_WEBHOOK_URL not set - notification skipped
```

