## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 CLI Launcher — claudec Removal

- [ ] 2.1.1 Remove `detect_claudec()` function from `launcher.py`
- [ ] 2.1.2 Remove `shutil` import (no longer needed after claudec removal)
- [ ] 2.1.3 Remove `claudec_path` parameter from `launch_claude()` — always construct `["claude"] + claude_args`
- [ ] 2.1.4 Remove claudec detection block from `cmd_start()` (lines 418-425)

### 2.2 CLI Launcher — tmux Pane Detection

- [ ] 2.2.1 Add `get_tmux_pane_id()` function that reads `$TMUX_PANE` env var, returns pane ID string or None
- [ ] 2.2.2 Update `cmd_start()`: when `--bridge` is passed, call `get_tmux_pane_id()` and output bridge status
  - Available: `Input Bridge: available (tmux pane %N)` (stdout)
  - Unavailable: `Input Bridge: unavailable (not in tmux session)` (stderr warning)
- [ ] 2.2.3 Move tmux pane detection BEFORE `register_session()` call so pane ID is available for registration

### 2.3 CLI Launcher — Session Registration Update

- [ ] 2.3.1 Add `tmux_pane_id: str | None = None` parameter to `register_session()`
- [ ] 2.3.2 Include `tmux_pane_id` in registration payload when provided
- [ ] 2.3.3 Update `cmd_start()` to pass `tmux_pane_id` to `register_session()`

### 2.4 CLI Help Text

- [ ] 2.4.1 Update `--bridge` flag help text to reference tmux-based input bridge instead of claudec

### 2.5 Sessions Route — tmux_pane_id Support

- [ ] 2.5.1 Extract `tmux_pane_id` from POST request payload in `create_session()`
- [ ] 2.5.2 Store `tmux_pane_id` on Agent model at creation time
- [ ] 2.5.3 Register agent with `CommanderAvailability` service when `tmux_pane_id` is provided

### 2.6 CLI Launcher — launch_claude Cleanup

- [ ] 2.6.1 Remove `claudec_path` from `launch_claude()` call in `cmd_start()` — always pass None or remove kwarg entirely

## 3. Testing (Phase 3)

### 3.1 Launcher Tests

- [ ] 3.1.1 Remove `TestDetectClaudec` class
- [ ] 3.1.2 Remove `test_launch_with_claudec` and `test_launch_with_claudec_no_extra_args` tests
- [ ] 3.1.3 Add `TestGetTmuxPaneId` class: test in tmux (env set), test outside tmux (env not set)
- [ ] 3.1.4 Update `TestLaunchClaude`: remove claudec_path tests, verify always launches `["claude"] + args`
- [ ] 3.1.5 Update `test_start_command_with_bridge_flag`: verify tmux detection instead of claudec detection
- [ ] 3.1.6 Update `test_start_command_without_bridge_skips_claudec`: verify no tmux detection without --bridge
- [ ] 3.1.7 Add test: `--bridge` inside tmux outputs available message and passes pane ID to register_session
- [ ] 3.1.8 Add test: `--bridge` outside tmux outputs unavailable warning and launches without pane ID
- [ ] 3.1.9 Update `test_start_command_full_success`: remove claudec mock, verify clean launch

### 3.2 Sessions Route Tests

- [ ] 3.2.1 Add test: POST /api/sessions with tmux_pane_id stores it on Agent
- [ ] 3.2.2 Add test: POST /api/sessions with tmux_pane_id registers with CommanderAvailability
- [ ] 3.2.3 Add test: POST /api/sessions without tmux_pane_id works (backward compatible)

## 4. Final Verification

- [ ] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 No references to claudec, claude-commander, or detect_claudec remain in launcher code
