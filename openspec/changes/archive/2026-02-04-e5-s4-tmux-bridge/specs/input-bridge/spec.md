## REMOVED Requirements

### Requirement: Commander Communication Service

- `commander_service.py` (socket-based send/health) is deleted
- Socket path derivation from `claude_session_id` is no longer used for input delivery
- `CommanderErrorType` enum is removed
- Config keys `socket_timeout` and `socket_path_prefix` are removed
