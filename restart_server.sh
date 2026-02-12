#!/bin/bash
# Restart the Claude Headspace Flask server
#
# Uses run.py which reads config.yaml for host/port/debug settings

# Get the configured port from config.yaml (default 5050)
cd "$(dirname "$0")"
PORT=$(grep -A2 "^server:" config.yaml 2>/dev/null | grep "port:" | awk '{print $2}' || echo "5050")

# Kill any existing server (scoped to this project to avoid killing other python apps)
pkill -if "python.*claude_headspace.*run\.py" 2>/dev/null
lsof -ti :$PORT | xargs kill -9 2>/dev/null

# Wait for process to die
sleep 1

# Activate venv if it exists
if [[ -d "venv" ]]; then
    source venv/bin/activate
fi

# TLS -- Tailscale HTTPS certificates
export TLS_CERT="/Users/samotage/certs/smac.griffin-blenny.ts.net.crt"
export TLS_KEY="/Users/samotage/certs/smac.griffin-blenny.ts.net.key"

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
