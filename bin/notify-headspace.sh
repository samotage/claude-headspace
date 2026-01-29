#!/bin/bash
#
# Claude Code Hook Notification Script
#
# This script is called by Claude Code hooks to notify Claude Headspace
# of session lifecycle events. It sends an HTTP request to the local
# Headspace server and exits silently on any error to avoid blocking
# Claude Code.
#
# Usage: notify-headspace.sh <event_type>
#
# Event types:
#   session-start       - Claude Code session started
#   session-end         - Claude Code session ended
#   user-prompt-submit  - User submitted a prompt
#   stop                - Claude turn completed
#   notification        - Claude sent a notification
#
# Environment variables used:
#   CLAUDE_SESSION_ID        - The Claude Code session identifier
#   CLAUDE_WORKING_DIRECTORY - The working directory (optional)
#   PWD                      - Fallback for working directory
#
# Configuration:
#   HEADSPACE_URL - Base URL (default: http://localhost:5050)
#

set -e

# Configuration
HEADSPACE_URL="${HEADSPACE_URL:-http://localhost:5050}"
CONNECT_TIMEOUT=1
MAX_TIME=2

# Get event type from argument
EVENT_TYPE="${1:-}"

if [ -z "$EVENT_TYPE" ]; then
    # No event type specified, exit silently
    exit 0
fi

# Get session ID from environment
SESSION_ID="${CLAUDE_SESSION_ID:-}"

if [ -z "$SESSION_ID" ]; then
    # No session ID, exit silently
    exit 0
fi

# Get working directory
WORKING_DIR="${CLAUDE_WORKING_DIRECTORY:-$PWD}"

# Build endpoint URL
ENDPOINT="${HEADSPACE_URL}/hook/${EVENT_TYPE}"

# Build JSON payload
PAYLOAD=$(cat <<EOF
{
    "session_id": "${SESSION_ID}",
    "working_directory": "${WORKING_DIR}"
}
EOF
)

# Send the request
# - Use curl with timeout to prevent blocking
# - Redirect all output to /dev/null
# - Always exit 0 to not block Claude Code
curl -s \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$ENDPOINT" > /dev/null 2>&1 || true

# Always exit successfully to not block Claude Code
exit 0
