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
# Claude Code passes hook data via stdin as JSON containing:
#   session_id, cwd, transcript_path, hook_event_name, etc.
#
# Configuration:
#   HEADSPACE_URL - Base URL (default: http://localhost:5055)
#

# NOTE: Do NOT use set -e — silent exits mask hook failures

# Debug log (remove once hooks are confirmed working)
DEBUG_LOG="/tmp/headspace-hook-debug.log"

# Configuration
HEADSPACE_URL="${HEADSPACE_URL:-http://localhost:5055}"
CONNECT_TIMEOUT=1
MAX_TIME=2

# Get event type from argument
EVENT_TYPE="${1:-}"

echo "$(date '+%Y-%m-%d %H:%M:%S') ENTRY event=${EVENT_TYPE}" >> "$DEBUG_LOG"

if [ -z "$EVENT_TYPE" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') EXIT no event type" >> "$DEBUG_LOG"
    exit 0
fi

# Read hook input from stdin (Claude Code passes JSON via stdin)
STDIN_DATA=""
if [ ! -t 0 ]; then
    STDIN_DATA=$(cat)
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') STDIN tty_test=$([[ -t 0 ]] && echo 'is_tty' || echo 'not_tty') len=${#STDIN_DATA} data=${STDIN_DATA:0:200}" >> "$DEBUG_LOG"

# Extract fields from stdin JSON, fall back to environment variables
SESSION_ID=""
WORKING_DIR=""
PROMPT_TEXT=""
TRANSCRIPT_PATH=""
NOTIFICATION_MESSAGE=""
NOTIFICATION_TITLE=""
NOTIFICATION_TYPE=""
TOOL_NAME=""
TOOL_INPUT=""
if [ -n "$STDIN_DATA" ] && command -v jq &>/dev/null; then
    SESSION_ID=$(echo "$STDIN_DATA" | jq -r '.session_id // empty' 2>/dev/null) || true
    WORKING_DIR=$(echo "$STDIN_DATA" | jq -r '.cwd // empty' 2>/dev/null) || true
    PROMPT_TEXT=$(echo "$STDIN_DATA" | jq -r '.prompt // empty' 2>/dev/null) || true
    TRANSCRIPT_PATH=$(echo "$STDIN_DATA" | jq -r '.transcript_path // empty' 2>/dev/null) || true
    NOTIFICATION_MESSAGE=$(echo "$STDIN_DATA" | jq -r '.message // empty' 2>/dev/null) || true
    NOTIFICATION_TITLE=$(echo "$STDIN_DATA" | jq -r '.title // empty' 2>/dev/null) || true
    NOTIFICATION_TYPE=$(echo "$STDIN_DATA" | jq -r '.notification_type // empty' 2>/dev/null) || true
    TOOL_NAME=$(echo "$STDIN_DATA" | jq -r '.tool_name // empty' 2>/dev/null) || true
    TOOL_INPUT=$(echo "$STDIN_DATA" | jq -c '.tool_input // empty' 2>/dev/null) || true
    # jq -c outputs "null" or "" for missing keys; normalise to empty string
    if [ "$TOOL_INPUT" = "null" ] || [ "$TOOL_INPUT" = '""' ]; then
        TOOL_INPUT=""
    fi
fi

# Fall back to environment variables for session ID only
SESSION_ID="${SESSION_ID:-${CLAUDE_SESSION_ID:-}}"
# NOTE: Do NOT fall back to $PWD for working_directory.
# $PWD may be an internal directory (.claude/, /tmp/, etc.) that does not
# represent the actual project. Let the server handle missing working_directory.

# Read CLI-assigned session UUID from env (inherited: CLI -> Claude Code -> hook)
HEADSPACE_SESSION_ID="${CLAUDE_HEADSPACE_SESSION_ID:-}"

echo "$(date '+%Y-%m-%d %H:%M:%S') PARSED event=${EVENT_TYPE} sid=${SESSION_ID:-EMPTY} cwd=${WORKING_DIR:-EMPTY} hsid=${HEADSPACE_SESSION_ID:-EMPTY}" >> "$DEBUG_LOG"

if [ -z "$SESSION_ID" ]; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') EXIT no session_id for event=${EVENT_TYPE}" >> "$DEBUG_LOG"
    exit 0
fi

# Build endpoint URL
ENDPOINT="${HEADSPACE_URL}/hook/${EVENT_TYPE}"

# Build JSON payload using jq for safe encoding (handles quotes, newlines in prompt text)
PAYLOAD=$(jq -n \
    --arg sid "$SESSION_ID" \
    --arg wd "$WORKING_DIR" \
    --arg hsid "$HEADSPACE_SESSION_ID" \
    --arg prompt "$PROMPT_TEXT" \
    --arg tp "$TRANSCRIPT_PATH" \
    --arg msg "$NOTIFICATION_MESSAGE" \
    --arg title "$NOTIFICATION_TITLE" \
    --arg ntype "$NOTIFICATION_TYPE" \
    --arg tname "$TOOL_NAME" \
    --argjson tinput "${TOOL_INPUT:-null}" \
    '{session_id: $sid}
     + (if $wd != "" then {working_directory: $wd} else {} end)
     + (if $hsid != "" then {headspace_session_id: $hsid} else {} end)
     + (if $prompt != "" then {prompt: $prompt} else {} end)
     + (if $tp != "" then {transcript_path: $tp} else {} end)
     + (if $msg != "" then {message: $msg} else {} end)
     + (if $title != "" then {title: $title} else {} end)
     + (if $ntype != "" then {notification_type: $ntype} else {} end)
     + (if $tname != "" then {tool_name: $tname} else {} end)
     + (if $tinput != null then {tool_input: $tinput} else {} end)' 2>/dev/null) || PAYLOAD="{\"session_id\": \"${SESSION_ID}\"}"

# Send the request and capture result
CURL_RESULT=$(curl -s -w "\n%{http_code}" \
    --connect-timeout "$CONNECT_TIMEOUT" \
    --max-time "$MAX_TIME" \
    -X POST \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD" \
    "$ENDPOINT" 2>&1) || true

CURL_HTTP_CODE=$(echo "$CURL_RESULT" | tail -1)
echo "$(date '+%Y-%m-%d %H:%M:%S') SENT event=${EVENT_TYPE} sid=${SESSION_ID} endpoint=${ENDPOINT} http=${CURL_HTTP_CODE}" >> "$DEBUG_LOG"

exit 0
