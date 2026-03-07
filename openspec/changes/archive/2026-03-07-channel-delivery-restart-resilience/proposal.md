## Why

Server restarts (especially werkzeug debug reloads during development) wipe `ChannelDeliveryService`'s in-memory `_channel_prompted` set and `_queue` dict, causing agent responses to be silently dropped because the relay gate rejects them as "likely a direct/DM conversation." This was observed in production when three agents had their channel responses dropped after a single reload.

## What Changes

- Add state reconstruction logic to `ChannelDeliveryService.__init__` that rebuilds `_channel_prompted` and `_queue` from existing `Message` and `ChannelMembership` database records
- Implement a 1-hour stale message cutoff to prevent false positives from old channel conversations
- Add INFO-level reconstruction logging for operational visibility
- Ensure reconstruction is idempotent (safe to run multiple times)

## Impact

- Affected specs: channel-delivery, channel-message-relay
- Affected code:
  - `src/claude_headspace/services/channel_delivery.py` — primary modification target (add reconstruction to `__init__`)
  - `src/claude_headspace/models/message.py` — read-only queries (no changes)
  - `src/claude_headspace/models/channel_membership.py` — read-only queries (no changes)
  - `src/claude_headspace/models/agent.py` — read-only queries (no changes)
  - `tests/services/test_channel_delivery.py` — new test cases for reconstruction
- No database schema changes or migrations required
- No breaking changes — reconstruction is additive and always-on
- Related git context: `channel_delivery.py` has been actively modified (3 recent commits for delivery logic fixes), but those changes are orthogonal to init-time reconstruction
