#!/bin/bash
# Restart the Claude Headspace Flask server
#
# Uses run.py which reads config.yaml for host/port/debug settings

# Get the configured port from config.yaml (default 5050)
cd "$(dirname "$0")"
PORT=$(grep -A2 "^server:" config.yaml 2>/dev/null | grep "port:" | awk '{print $2}' || echo "5050")

# Kill any existing server.
# Port-based kill is the most reliable — port 5055 is unique to this app.
# First try graceful SIGTERM on anything holding the port, then SIGKILL stragglers.
lsof -ti :$PORT 2>/dev/null | xargs kill 2>/dev/null
sleep 1
# SIGKILL anything still holding the port (zombie werkzeug workers, etc.)
lsof -ti :$PORT 2>/dev/null | xargs kill -9 2>/dev/null
sleep 0.5

# Also kill any orphaned run.py processes that lost their socket but are still alive.
# On macOS, framework Python shows as "Python run.py" (no full path in args).
# Scope by checking each candidate's cwd matches this project directory.
for pid in $(pgrep -f "[Pp]ython.*run\.py" 2>/dev/null); do
    pid_cwd=$(lsof -p "$pid" -d cwd -Fn 2>/dev/null | tail -1 | sed 's/^n//')
    if [[ "$pid_cwd" == "$(pwd)" ]]; then
        kill -9 "$pid" 2>/dev/null
    fi
done

# Activate venv if it exists
if [[ -d "venv" ]]; then
    source venv/bin/activate
fi

# TLS -- Tailscale HTTPS certificates
export TLS_CERT="/Users/samotage/certs/smac.griffin-blenny.ts.net.crt"
export TLS_KEY="/Users/samotage/certs/smac.griffin-blenny.ts.net.key"

# Strip Werkzeug reloader env vars so the new server starts fresh.
# When this script is called from within a running Flask process (e.g. the config
# page restart button), WERKZEUG_RUN_MAIN and WERKZEUG_SERVER_FD leak into the
# environment.  If they reach the new python3 process it skips the reloader and
# tries to reuse a dead file descriptor, crashing with "Socket operation on non-socket".
unset WERKZEUG_RUN_MAIN WERKZEUG_SERVER_FD

# Start server in background using run.py (reads config.yaml)
python3 run.py > /tmp/claude_headspace.log 2>&1 &

# Wait for startup
sleep 2

# Verify it's running
if lsof -i :$PORT > /dev/null 2>&1; then
    echo "Server started on https://0.0.0.0:$PORT (TLS)"
    lsof -i :$PORT | head -3
else
    echo "Server failed to start. Check /tmp/claude_headspace.log"
    tail -20 /tmp/claude_headspace.log
fi
