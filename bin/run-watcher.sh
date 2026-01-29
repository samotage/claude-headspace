#!/bin/bash
# run-watcher.sh - Process supervision wrapper for Claude Headspace watcher
#
# This script provides simple process supervision for Epic 1:
# - Automatically restarts the watcher on crash
# - Implements crash loop protection (max 5 restarts in 60 seconds)
# - Logs restart events

set -euo pipefail

# Configuration
MAX_RESTARTS=5
RESTART_WINDOW=60  # seconds
RESTART_DELAY=2    # seconds between restarts

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Tracking variables
RESTART_COUNT=0
RESTART_TIMES=()

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1" >&2
}

# Check if we're in a crash loop
check_crash_loop() {
    local now
    now=$(date +%s)
    local cutoff=$((now - RESTART_WINDOW))

    # Remove old timestamps outside the window
    local new_times=()
    for t in "${RESTART_TIMES[@]}"; do
        if [ "$t" -ge "$cutoff" ]; then
            new_times+=("$t")
        fi
    done
    RESTART_TIMES=("${new_times[@]}")

    # Check if we've exceeded max restarts
    if [ ${#RESTART_TIMES[@]} -ge $MAX_RESTARTS ]; then
        return 0  # In crash loop
    fi
    return 1  # Not in crash loop
}

record_restart() {
    RESTART_TIMES+=("$(date +%s)")
    RESTART_COUNT=$((RESTART_COUNT + 1))
}

cleanup() {
    log "Supervisor shutting down..."

    # Forward signal to child process if running
    if [ -n "${WATCHER_PID:-}" ] && kill -0 "$WATCHER_PID" 2>/dev/null; then
        log "Forwarding signal to watcher (PID: $WATCHER_PID)..."
        kill -TERM "$WATCHER_PID" 2>/dev/null || true

        # Wait for child to exit
        wait "$WATCHER_PID" 2>/dev/null || true
    fi

    log "Supervisor stopped"
    exit 0
}

# Set up signal handlers
trap cleanup SIGTERM SIGINT

log "=============================================="
log "Claude Headspace Watcher Supervisor Starting"
log "PID: $$"
log "Max restarts: $MAX_RESTARTS in $RESTART_WINDOW seconds"
log "=============================================="

# Main supervision loop
while true; do
    log "Starting watcher process..."

    # Activate virtual environment if it exists
    if [ -f "$PROJECT_ROOT/.venv/bin/activate" ]; then
        source "$PROJECT_ROOT/.venv/bin/activate"
    fi

    # Start the watcher process
    python "$SCRIPT_DIR/watcher.py" &
    WATCHER_PID=$!

    log "Watcher started with PID: $WATCHER_PID"

    # Wait for the process to exit
    set +e
    wait "$WATCHER_PID"
    EXIT_CODE=$?
    set -e

    log "Watcher exited with code: $EXIT_CODE"

    # Check if this was a clean exit
    if [ $EXIT_CODE -eq 0 ]; then
        log "Watcher exited cleanly"
        break
    fi

    # Check for crash loop
    if check_crash_loop; then
        log_error "Crash loop detected! $MAX_RESTARTS restarts in $RESTART_WINDOW seconds"
        log_error "Stopping supervisor to prevent further restarts"
        exit 1
    fi

    # Record this restart
    record_restart

    log "Restart $RESTART_COUNT - waiting $RESTART_DELAY seconds before restart..."
    sleep $RESTART_DELAY
done

log "Supervisor exiting normally"
exit 0
