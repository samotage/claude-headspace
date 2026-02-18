# Remediation Plan: Issues 3 & 9 - State Machine Integration and Event Logging

**Created:** 2026-01-29
**Status:** COMPLETE
**Completed:** 2026-01-29
**Related Issues:** Issue 3 (Hook Receiver Bypasses State Machine), Issue 9 (Event Log Not Populated)

---

## Executive Summary

The `hook_receiver.py` service currently performs direct state manipulation without using the established `StateMachine` and `CommandLifecycleManager` services. This bypasses validation logic and fails to write events to the audit log. This remediation plan outlines a refactoring approach to integrate these services properly.

---

## Problem Analysis

### Issue 3: State Machine Bypass

**Current Behavior:**
```python
# hook_receiver.py - Direct state manipulation
current_command.state = CommandState.PROCESSING  # No validation!
current_command.state = CommandState.COMPLETE    # No validation!
```

**Expected Behavior:**
```python
# Should use StateMachine for validation
lifecycle = CommandLifecycleManager(db.session, event_writer)
result = lifecycle.process_turn(agent, TurnActor.USER, text=None)
```

**Specific Problems:**

1. **No Transition Validation:** The hook receiver sets `CommandState` directly without checking if the transition is valid according to the 5-state model.

2. **Inconsistent State Transitions:**
   - `process_user_prompt_submit()` transitions to `PROCESSING` but skips `COMMANDED` state
   - `process_stop()` marks task `COMPLETE` immediately without going through intermediate states
   - The state machine defines: `IDLE → COMMANDED → PROCESSING → AWAITING_INPUT/COMPLETE`

3. **No Intent Detection:** The hook receiver doesn't use intent detection to determine the appropriate state transition.

4. **Command Creation Outside Manager:** Commands are created directly in `process_user_prompt_submit()` instead of using `CommandLifecycleManager.create_command()`.

### Issue 9: Missing Event Logging

**Current Behavior:**
- Hook events update state but never call `EventWriter`
- The `Event` table has no record of hook-driven state changes
- Audit trail is incomplete

**Expected Behavior:**
- All state transitions should write to the Event table
- Hook events should create `HOOK_RECEIVED` events
- State changes should create `STATE_TRANSITION` events

---

## Architecture Analysis

### Existing Services

| Service | Purpose | Location |
|---------|---------|----------|
| `StateMachine` | Validates state transitions | `services/state_machine.py` |
| `CommandLifecycleManager` | Manages command lifecycle, writes events | `services/command_lifecycle.py` |
| `EventWriter` | Writes events to database | `services/event_writer.py` |

### Current Data Flow (Problematic)

```
Hook Event → hook_receiver.py → Direct DB manipulation
                                (no validation, no events)
```

### Target Data Flow

```
Hook Event → hook_receiver.py → CommandLifecycleManager → StateMachine (validation)
                                         ↓
                                    EventWriter (audit log)
                                         ↓
                                    Database (state + events)
```

---

## Implementation Plan

### Phase 1: Create Hook-to-Lifecycle Bridge

Create a new module that bridges hook events to the lifecycle manager.

**File:** `src/claude_headspace/services/hook_lifecycle_bridge.py`

```python
"""Bridge between hook events and command lifecycle management."""

import logging
from datetime import datetime, timezone
from typing import Optional

from ..database import db
from ..models.agent import Agent
from ..models.command import CommandState
from ..models.turn import TurnActor, TurnIntent
from .event_writer import EventWriter, create_event_writer
from .command_lifecycle import CommandLifecycleManager, TurnProcessingResult

logger = logging.getLogger(__name__)


class HookLifecycleBridge:
    """
    Bridge between hook events and the command lifecycle system.

    Translates hook events into lifecycle operations with proper
    state machine validation and event logging.
    """

    def __init__(
        self,
        event_writer: Optional[EventWriter] = None,
    ) -> None:
        self._event_writer = event_writer

    def process_user_prompt_submit(
        self,
        agent: Agent,
        claude_session_id: str,
    ) -> TurnProcessingResult:
        """
        Process a user_prompt_submit hook as a user command.

        Maps to: USER + COMMAND intent
        Expected transition: IDLE/AWAITING_INPUT → COMMANDED → PROCESSING
        """
        lifecycle = CommandLifecycleManager(
            session=db.session,
            event_writer=self._event_writer,
        )

        # User submitting a prompt is a USER COMMAND
        result = lifecycle.process_turn(
            agent=agent,
            actor=TurnActor.USER,
            text=None,  # Hook doesn't provide text
        )

        # After user command, immediately transition to processing
        # since Claude will start working
        if result.success and result.command:
            current_state = result.command.state
            if current_state == CommandState.COMMANDED:
                # Simulate agent starting work
                lifecycle.update_task_state(
                    task=result.task,
                    to_state=CommandState.PROCESSING,
                    trigger="hook:user_prompt_submit",
                    confidence=1.0,
                )

        return result

    def process_stop(
        self,
        agent: Agent,
        claude_session_id: str,
    ) -> TurnProcessingResult:
        """
        Process a stop hook as agent completion.

        Maps to: AGENT + COMPLETION intent
        Expected transition: PROCESSING → COMPLETE
        """
        lifecycle = CommandLifecycleManager(
            session=db.session,
            event_writer=self._event_writer,
        )

        current_task = lifecycle.get_current_task(agent)
        if not current_command:
            # No active command - nothing to complete
            return TurnProcessingResult(
                success=True,
                error="No active command to complete",
            )

        # Complete the task
        lifecycle.complete_task(
            task=current_task,
            trigger="hook:stop",
        )

        return TurnProcessingResult(
            success=True,
            task=current_task,
            event_written=self._event_writer is not None,
        )

    def process_session_end(
        self,
        agent: Agent,
        claude_session_id: str,
    ) -> TurnProcessingResult:
        """
        Process a session_end hook by completing any active command.

        This is a forced completion regardless of current state.
        """
        lifecycle = CommandLifecycleManager(
            session=db.session,
            event_writer=self._event_writer,
        )

        current_task = lifecycle.get_current_task(agent)
        if current_command:
            lifecycle.complete_task(
                task=current_task,
                trigger="hook:session_end",
            )

        return TurnProcessingResult(
            success=True,
            task=current_task,
            event_written=self._event_writer is not None,
        )


# Global bridge instance
_bridge: Optional[HookLifecycleBridge] = None


def get_hook_bridge() -> HookLifecycleBridge:
    """Get or create the global hook lifecycle bridge."""
    global _bridge
    if _bridge is None:
        # Try to get event writer from app config
        try:
            from flask import current_app
            config = current_app.config.get("APP_CONFIG", {})
            db_url = _get_database_url(config)
            event_writer = create_event_writer(db_url, config) if db_url else None
        except RuntimeError:
            # Outside Flask context
            event_writer = None

        _bridge = HookLifecycleBridge(event_writer=event_writer)

    return _bridge


def _get_database_url(config: dict) -> Optional[str]:
    """Build database URL from config."""
    db_config = config.get("database", {})
    host = db_config.get("host")
    if not host:
        return None

    port = db_config.get("port", 5432)
    name = db_config.get("name", "claude_headspace")
    user = db_config.get("user", "postgres")
    password = db_config.get("password", "")

    return f"postgresql://{user}:{password}@{host}:{port}/{name}"
```

### Phase 2: Update Hook Receiver

Refactor `hook_receiver.py` to use the bridge while maintaining backward compatibility.

**Changes to `src/claude_headspace/services/hook_receiver.py`:**

```python
# Add import at top
from .hook_lifecycle_bridge import get_hook_bridge, HookLifecycleBridge

# Option A: Full integration (recommended)
def process_user_prompt_submit(
    agent: Agent,
    claude_session_id: str,
) -> HookEventResult:
    """Process a user prompt submit hook event."""
    state = get_receiver_state()
    state.record_event(HookEventType.USER_PROMPT_SUBMIT)

    try:
        agent.last_seen_at = datetime.now(timezone.utc)

        # Use lifecycle bridge for proper state management
        bridge = get_hook_bridge()
        result = bridge.process_user_prompt_submit(agent, claude_session_id)

        db.session.commit()

        # Broadcast state change
        new_state = result.command.state.value if result.task else CommandState.IDLE.value
        _broadcast_state_change(agent, "user_prompt_submit", new_state)

        logger.info(
            f"hook_event: type=user_prompt_submit, agent_id={agent.id}, "
            f"session_id={claude_session_id}, new_state={new_state}"
        )

        return HookEventResult(
            success=result.success,
            agent_id=agent.id,
            state_changed=True,
            new_state=new_state,
            error_message=result.error,
        )
    except Exception as e:
        logger.exception(f"Error processing user_prompt_submit: {e}")
        db.session.rollback()
        return HookEventResult(success=False, error_message=str(e))


# Option B: Gradual migration with feature flag
def process_user_prompt_submit(
    agent: Agent,
    claude_session_id: str,
    use_lifecycle: bool = False,  # Feature flag
) -> HookEventResult:
    """Process a user prompt submit hook event."""
    if use_lifecycle:
        return _process_user_prompt_submit_with_lifecycle(agent, claude_session_id)
    else:
        return _process_user_prompt_submit_legacy(agent, claude_session_id)
```

### Phase 3: Add Event Writer to App Factory

Ensure the EventWriter is available application-wide.

**Changes to `src/claude_headspace/app.py`:**

```python
def create_app(config_path: str = "config.yaml") -> Flask:
    # ... existing code ...

    # Initialize event writer (only if database is connected)
    if db_connected:
        from .services.event_writer import create_event_writer
        db_url = _build_database_url(config)
        event_writer = create_event_writer(db_url, config)
        app.extensions["event_writer"] = event_writer
        logger.info("Event writer initialized")

    # ... rest of existing code ...
```

### Phase 4: Add Hook-Specific Event Types

Update event types to include hook events.

**Changes to `src/claude_headspace/models/event.py`:**

```python
class EventType:
    """Supported event types."""
    # ... existing types ...

    # Hook events
    HOOK_SESSION_START = "hook_session_start"
    HOOK_SESSION_END = "hook_session_end"
    HOOK_USER_PROMPT = "hook_user_prompt"
    HOOK_STOP = "hook_stop"
    HOOK_NOTIFICATION = "hook_notification"
```

### Phase 5: Write Hook Events to Audit Log

Add helper function to write hook events.

**Add to `hook_receiver.py` or `hook_lifecycle_bridge.py`:**

```python
def _write_hook_event(
    event_type: str,
    agent: Agent,
    claude_session_id: str,
    payload: Optional[dict] = None,
) -> None:
    """Write a hook event to the audit log."""
    try:
        from flask import current_app
        event_writer = current_app.extensions.get("event_writer")
        if not event_writer:
            return

        event_payload = {
            "claude_session_id": claude_session_id,
            "hook_type": event_type,
            **(payload or {}),
        }

        event_writer.write_event(
            event_type=f"hook_{event_type}",
            payload=event_payload,
            agent_id=agent.id,
            project_id=agent.project_id,
        )
    except Exception as e:
        logger.debug(f"Hook event write failed (non-fatal): {e}")
```

---

## Migration Strategy

### Option A: Big Bang (Recommended for MVP)

1. Implement all phases in one PR
2. Run full test suite
3. Manual verification of state transitions
4. Deploy

**Pros:** Clean implementation, consistent behavior
**Cons:** Higher risk if something breaks

### Option B: Gradual Migration

1. Phase 1-2: Add bridge with feature flag (default: off)
2. Phase 3-5: Add event writing infrastructure
3. Enable feature flag in staging
4. Monitor and verify
5. Enable in production
6. Remove legacy code and feature flag

**Pros:** Lower risk, easy rollback
**Cons:** More code complexity during migration

---

## Testing Strategy

### Unit Tests

1. **Test bridge methods:**
   ```python
   def test_bridge_user_prompt_creates_task():
       """User prompt should create task via lifecycle manager."""

   def test_bridge_stop_completes_task():
       """Stop hook should complete active command."""

   def test_bridge_validates_transitions():
       """Invalid transitions should be rejected."""
   ```

2. **Test event writing:**
   ```python
   def test_hook_writes_event():
       """Hook processing should write to Event table."""

   def test_state_transition_event_written():
       """State changes should create STATE_TRANSITION events."""
   ```

### Integration Tests

1. **End-to-end hook flow:**
   ```python
   def test_full_hook_lifecycle():
       """Test session_start → user_prompt → stop → session_end."""
   ```

2. **Event audit trail:**
   ```python
   def test_events_created_for_hooks():
       """Verify Event table contains expected hook events."""
   ```

### Verification Queries

```sql
-- Verify events are being written
SELECT event_type, COUNT(*)
FROM events
WHERE event_type LIKE 'hook_%'
GROUP BY event_type;

-- Verify state transitions are logged
SELECT * FROM events
WHERE event_type = 'state_transition'
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Rollback Plan

If issues arise after deployment:

1. **Immediate:** Revert to legacy code path via feature flag
2. **Investigation:** Check Event table for anomalies
3. **Fix:** Address specific issues
4. **Re-deploy:** With fixes applied

---

## Success Criteria

1. All 700+ existing tests pass
2. New tests for bridge functionality pass
3. Hook events create Event records
4. State transitions are validated
5. No performance regression (< 10ms added latency)
6. Event table shows complete audit trail

---

## Open Questions for Product Owner

1. **State Model Alignment:** The hook `stop` event implies completion, but should we:
   - Mark task as COMPLETE? (current behavior)
   - Mark as IDLE and let next interaction start new task?
   - Support both based on context?

2. **Event Retention:** How long should hook events be retained in the Event table?

3. **Validation Strictness:** Should we reject invalid transitions or log warnings and proceed?

---

## Files to Modify

| File | Changes |
|------|---------|
| `services/hook_lifecycle_bridge.py` | NEW - Bridge module |
| `services/hook_receiver.py` | Integrate bridge |
| `app.py` | Initialize EventWriter |
| `models/event.py` | Add hook event types |
| `tests/services/test_hook_lifecycle_bridge.py` | NEW - Bridge tests |
| `tests/services/test_hook_receiver.py` | Update for integration |

---

## Appendix: State Transition Matrix

Current valid transitions (from `state_machine.py`):

| From State | Actor | Intent | To State |
|------------|-------|--------|----------|
| IDLE | USER | COMMAND | COMMANDED |
| COMMANDED | AGENT | PROGRESS | PROCESSING |
| COMMANDED | AGENT | QUESTION | AWAITING_INPUT |
| COMMANDED | AGENT | COMPLETION | COMPLETE |
| PROCESSING | AGENT | PROGRESS | PROCESSING |
| PROCESSING | AGENT | QUESTION | AWAITING_INPUT |
| PROCESSING | AGENT | COMPLETION | COMPLETE |
| AWAITING_INPUT | USER | ANSWER | PROCESSING |

**Hook Event Mappings:**

| Hook Event | Actor | Intent | Expected Flow |
|------------|-------|--------|---------------|
| `user_prompt_submit` | USER | COMMAND | IDLE → COMMANDED → PROCESSING |
| `stop` | AGENT | COMPLETION | PROCESSING → COMPLETE |
| `session_end` | N/A | N/A | Any → COMPLETE (forced) |

---

**End of Remediation Plan**
