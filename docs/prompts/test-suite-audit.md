# Test Suite Audit & Cleanup

## Context

This project has 1161 tests across unit, route, e2e, and integration tiers. The full suite takes ~3 minutes to run. Many tests were written for features that have since been refactored or deprecated (e.g., the stop-hook debounce mechanism). The result is failing tests that don't reflect real bugs — they reflect stale expectations.

## Known Failures

These 3 tests currently fail:

1. `tests/e2e/test_debounce.py::TestStopAndNotificationBehaviour::test_stop_without_prior_processing_is_harmless`
   - Expects IDLE after firing stop on an IDLE agent, but gets COMPLETE
   - The stop hook broadcasts COMPLETE even when there's no task (fallback default)
   - The test file header says "The stop-hook debounce mechanism was deprecated" — this test may be testing assumptions that no longer hold

2. `tests/e2e/test_edge_cases.py::TestEdgeCases::test_session_end_during_awaiting_input`
   - Fires stop after user_prompt_submit and expects AWAITING_INPUT
   - But stop now only produces AWAITING_INPUT if transcript text contains a question pattern
   - The test has no transcript content, so stop completes to COMPLETE
   - This test was written when a different mechanism (likely debounce + notification race) produced AWAITING_INPUT

3. `tests/routes/test_dashboard.py::TestDashboardWithData::test_state_dots_displayed`
   - Fails with `database "claude_headspace_test" does not exist`
   - Infrastructure issue, not a code bug

Additionally, 58 integration tests ERROR (not fail) because the test database doesn't exist at collection time.

## Your Task

Audit the test suite and produce a cleanup plan. Work through these phases:

### Phase 1: Diagnose the 3 Failing Tests

For each failing test:
1. Read the test code and understand what it asserts
2. Read the production code it exercises
3. Determine: is the test wrong (stale expectations) or is the code wrong (regression)?
4. If the test is stale, propose the fix (update assertion, rewrite test, or delete it)

### Phase 2: Find Stale Tests

Search for tests that reference deprecated or changed concepts:

- **Debounce**: The stop-hook debounce was deprecated. Any test that relies on debounce timing, debounce windows, or stop-then-notification race conditions is suspect. Search for "debounce", "DEBOUNCE", "debounce_window", "delay" in test files.
- **Stop hook assumptions**: Tests that assume stop always produces COMPLETE are now wrong — stop can produce AWAITING_INPUT if a question is detected in the transcript. Find tests with hardcoded COMPLETE expectations after stop.
- **Pre-tool-use / notification overlap**: The AWAITING_INPUT detection has been expanded (pre_tool_use, notification, permission_request, and now transcript question detection). Tests that assume only one path to AWAITING_INPUT may be incomplete or contradictory.
- **File watcher**: If file watcher behaviour has changed, polling-based tests may be stale.

Search patterns:
```
grep -r "debounce" tests/
grep -r "COMPLETE" tests/e2e/
grep -r "process_stop.*COMPLETE" tests/
grep -r "AWAITING_INPUT" tests/e2e/
```

### Phase 3: Assess Test Value

For each test file, evaluate:
- Does this test verify behaviour that still exists?
- Is the test testing implementation details (mocks of internal methods) or observable behaviour?
- Are there duplicate tests that verify the same thing at different tiers (unit + route + e2e)?
- Could this test be simplified or merged with another?

Flag tests that are:
- **Dead**: Testing removed/deprecated features
- **Fragile**: Passing by accident due to mock setup that doesn't reflect reality
- **Redundant**: Same assertion exists in a faster test tier
- **Broken infrastructure**: Failing due to missing DB or env, not code

### Phase 4: Produce the Cleanup Plan

Output a structured plan:

```
## Tests to Delete (with reason)
- tests/path/test_file.py::TestClass::test_name — reason

## Tests to Update (with what changed)
- tests/path/test_file.py::TestClass::test_name — update assertion from X to Y because Z

## Tests to Investigate Further
- tests/path/test_file.py::TestClass::test_name — unclear if test or code is wrong, need to verify X

## Infrastructure Fixes
- Issue and fix for integration test DB errors
```

### Phase 5: Implement the Changes

After producing the plan, implement the fixes:
- Delete dead tests
- Update stale assertions
- Fix infrastructure issues where straightforward
- Leave "investigate further" items clearly documented

## Constraints

- Do NOT delete tests just to make the suite green. Only delete tests that genuinely test deprecated behaviour.
- Do NOT weaken assertions. If a test catches a real bug, fix the code, not the test.
- Run the targeted test files after each batch of changes to verify: `pytest tests/path/to/changed_file.py -v`
- Do NOT run the full 1161-test suite repeatedly. Run targeted tests for the files you change.

## Key Files to Read First

- `tests/e2e/test_debounce.py` — the debounce test file (likely mostly stale)
- `tests/e2e/test_edge_cases.py` — edge case tests with state assumptions
- `tests/e2e/test_turn_lifecycle.py` — core lifecycle tests
- `src/claude_headspace/services/hook_lifecycle_bridge.py` — current stop hook logic
- `src/claude_headspace/services/hook_receiver.py` — current hook processing
- `src/claude_headspace/services/intent_detector.py` — question detection patterns
- `tests/e2e/helpers/hook_simulator.py` — how e2e tests simulate hooks
