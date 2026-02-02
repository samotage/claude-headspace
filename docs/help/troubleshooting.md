# Troubleshooting

Common issues and how to resolve them.

## Session Registration Issues

### Session not appearing on dashboard

**Symptoms:** You started Claude Code but no agent card appears on the dashboard.

**Cause:** Sessions do NOT auto-detect. They must be registered through either the wrapper script or hooks.

**Solutions:**

1. **Use the wrapper script** (recommended):
   ```bash
   claude-headspace start
   ```
   This registers the session automatically. See [Getting Started](getting-started) for details.

2. **Install hooks** if using `claude` directly:
   ```bash
   ./bin/install-hooks.sh
   ```
   Then start a **new** `claude` session (existing sessions won't pick up new hooks).

3. **Check the server port** - the hook script must target the correct port. Verify `config.yaml` shows the right port (default: 5055) and that `notify-headspace.sh` matches. If you changed the port, set `HEADSPACE_URL`:
   ```bash
   export HEADSPACE_URL=http://localhost:5055
   ```

4. **Verify hooks are installed** by checking:
   ```bash
   cat ~/.claude/settings.json | grep notify-headspace
   ```
   You should see entries for `session-start`, `session-end`, `user-prompt-submit`, `stop`, and `notification`.

5. **Test the hook endpoint** directly:
   ```bash
   curl http://localhost:5055/hook/status
   ```
   If this fails, the server is not reachable.

### Session registered but state not updating

**Symptoms:** Agent card appears but stays stuck on one state.

**Solutions:**
1. Check that all five hook events are installed (not just `session-start`)
2. Verify the hook script is executable: `chmod +x ~/.claude/hooks/notify-headspace.sh`
3. Check server logs for hook processing errors

## Dashboard Issues

### No agents appearing

**Symptoms:** Dashboard shows "No agents found" even with active sessions.

**Solutions:**
1. Follow the "Session not appearing on dashboard" steps above
2. Check that the server is running on the expected port
3. Verify project paths in `config.yaml` match your actual paths

### Connection indicator shows disconnected

**Symptoms:** Gray or red connection dot, no real-time updates.

**Solutions:**
1. Refresh the page
2. Check server console for errors
3. Ensure no firewall blocking the connection

### Headspace button doesn't focus window

**Symptoms:** Clicking Headspace does nothing.

**Solutions:**
1. Grant Automation permissions: System Preferences → Privacy & Security → Automation
2. Ensure iTerm2 is the configured terminal
3. Check that the session is still running

## Input Bridge Issues

### Respond widget not appearing

**Symptoms:** Agent is in "Input Needed" (amber) state but no quick-action buttons or text input appear on the card.

**Solutions:**

1. **claudec must be installed** — the respond widget requires a commander socket. Install `claudec` and then start sessions with:
   ```bash
   claude-headspace start
   ```
   The wrapper auto-detects `claudec` and enables Input Bridge. If the preamble shows `Input Bridge: unavailable`, install `claudec`: `cargo install claude-commander` or download from [GitHub releases](https://github.com/sstraus/claude-commander/releases).

2. **Check that claudec is installed:**
   ```bash
   claudec --version
   ```
   If not found, install it: `cargo install claude-commander` or download from [GitHub releases](https://github.com/sstraus/claude-commander/releases).

3. **Socket startup delay** — there is a 2-5 second delay after launching `claudec` before the socket becomes available. The widget will appear automatically once the health check detects the socket.

4. **Check socket exists** — verify the commander socket file is present:
   ```bash
   ls /tmp/claudec-*.sock
   ```
   If no socket files exist, `claudec` may not be running or may have crashed.

5. **Agent needs a session ID** — if the agent has no `claude_session_id`, the socket path cannot be derived. This usually means the session didn't register properly via hooks.

### "Session unreachable" error when responding

**Symptoms:** You click a quick-action button or Send, and get a "Session unreachable" toast.

**Solutions:**

1. **Check if Claude Code is still running** — the process inside `claudec` may have exited
2. **Check the socket file:**
   ```bash
   ls -la /tmp/claudec-*.sock
   ```
   If the file exists but the process is dead, the socket is stale. Restart the session with `claudec`.
3. **Socket permissions** — ensure the socket file is readable/writable by your user

### "Agent not waiting for input" warning

**Symptoms:** Warning toast saying the agent is not waiting for input.

**Cause:** The agent already moved past the prompt before your response was sent. This is a race condition — the agent may have timed out or another input source (keyboard in iTerm) provided the response.

**Resolution:** No action needed. The state will update automatically on the next hook event.

### Widget appears then disappears

**Symptoms:** Respond widget flashes briefly then vanishes.

**Cause:** The commander availability health check ran and found the socket unreachable.

**Solutions:**
1. Check if the `claudec` process is still running
2. Check server logs for availability check failures
3. The health check runs every 30 seconds (configurable in `config.yaml` → `commander.health_check_interval`)

## Configuration Issues

### Config page shows validation error

**Symptoms:** Can't save configuration, error message displayed.

**Solutions:**
1. Check YAML syntax - use proper indentation
2. Ensure all required fields are present
3. Try the Reset button to restore last saved version

### Changes don't take effect

**Symptoms:** Configuration saved but behavior unchanged.

**Solutions:**
1. Restart the server for server/database settings
2. Refresh the page for objective/notification settings
3. Check server logs for configuration errors

## Waypoint Issues

### Permission denied saving waypoint

**Symptoms:** Error message with path when trying to save.

**Solutions:**
1. Check that you have write permission to the project directory
2. Verify the project path is accessible (not on network drive that's unmounted)
3. Try creating the `docs/brain_reboot/` directory manually

### Conflict detected unexpectedly

**Symptoms:** Conflict dialog appears but you didn't expect changes.

**Solutions:**
1. Click Reload to see current file contents
2. Check if another process modified the file
3. If it's your only edit, use Overwrite

## Performance Issues

### Dashboard loading slowly

**Symptoms:** Long wait before dashboard appears.

**Solutions:**
1. Check number of monitored projects (reduce if > 20)
2. Verify database file isn't on network storage
3. Restart the server to clear any stuck connections

### Search results slow

**Symptoms:** Help search takes more than 200ms.

**Solutions:**
1. Reduce documentation file sizes if very large
2. Refresh the page to rebuild search index
3. This is normal on first load (index building)

## Getting More Help

If these solutions don't work:

1. Check server console output for error messages
2. Review the project README for setup instructions
3. File an issue on GitHub with error details
