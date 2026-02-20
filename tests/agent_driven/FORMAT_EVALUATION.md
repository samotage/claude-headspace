# Declarative Scenario Format Evaluation (FR20)

## Decision: No YAML format -- plain pytest functions are sufficient.

## Rationale

After implementing FR15-FR19 (shared helpers, permission flow, bug-driven scenarios,
structured output), I evaluated whether a declarative YAML scenario format would
reduce duplication and improve maintainability.

### What YAML would look like

```yaml
scenario: Simple Command Round-Trip
steps:
  - navigate: voice_chat
  - select_agent: true
  - send_message: "Create a file called /tmp/test.txt with 'hello'"
  - wait_for: agent_bubble
  - assert_db: command_state == COMPLETE
```

### Why NOT to implement it

1. **Minimal duplication remaining.** After extracting `verify_cross_layer_consistency`
   into `helpers/cross_layer.py` and `test_step`/`test_scenario_header`/`test_scenario_footer`
   into `helpers/output.py`, the remaining per-test code is the actual scenario logic --
   which is different for each test by definition.

2. **YAML adds indirection without reducing code.** Each YAML step would need a Python
   executor function. The mapping layer (YAML key -> Python function) is itself code that
   must be maintained. For 5-8 scenarios, the overhead of maintaining the YAML schema
   and executor exceeds the duplication it eliminates.

3. **Plain functions are more debuggable.** When a test fails, the stack trace points
   directly to the failing line in the test function. With YAML, the stack trace points
   to the executor, and you must correlate back to the YAML step. For integration tests
   that interact with real Claude Code sessions and tmux, debuggability is critical.

4. **Scenario variation is high.** Each scenario has unique interaction patterns:
   - Simple command: send + wait
   - Question/answer: send + wait + verify AWAITING_INPUT + tmux Enter + wait
   - Multi-turn: send + wait + poll COMPLETE + send again + wait
   - Permission: send + poll AWAITING_INPUT + tmux approve + wait
   - Bug regression: send long text + verify no swallow + verify no backflush

   A YAML format expressive enough to handle all of these would essentially be
   reimplementing Python control flow in YAML.

5. **Constraint C8 makes YAML optional by design.** Every scenario must remain writable
   as a plain pytest function. Since we must support plain functions anyway, adding YAML
   as a parallel format doubles the maintenance surface without a forcing function.

### What DID reduce duplication

- **`helpers/cross_layer.py`**: Eliminated ~120 lines of duplicated cross-layer
  verification code across test files. Used by 3+ tests.
- **`helpers/output.py`**: Provides consistent structured output (scenario name,
  step progress, timing) without per-test boilerplate. Used by 5+ tests.
- **`VoiceAssertions`** (existing): Already handles navigate/select/send/capture.

### Conclusion

The shared helper extraction (FR15) was the right deduplication lever. A YAML format
would add complexity without proportional benefit at the current scenario count (5-8).
If the scenario count grows to 20+ with high structural similarity, YAML should be
re-evaluated.

---

*Evaluated: 2026-02-20*
*Per FR20 / Constraint C7 / Constraint C8*
