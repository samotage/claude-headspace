#!/bin/bash
#
# Claude Code Hooks Installation Script
#
# This script installs Claude Headspace hooks into Claude Code's configuration.
# It creates the notification script and updates Claude Code's settings.json
# using the nested PascalCase hook format that Claude Code expects.
#
# Usage: install-hooks.sh [--uninstall]
#
# Requirements:
#   - Claude Code must be installed
#   - jq must be installed (for JSON manipulation)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
CLAUDE_DIR="$HOME/.claude"
HOOKS_DIR="$CLAUDE_DIR/hooks"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
NOTIFY_SCRIPT="$HOOKS_DIR/notify-headspace.sh"

# Get the absolute path to this script's directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_SCRIPT="$SCRIPT_DIR/notify-headspace.sh"

# Function to print colored output
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Function to check if a path is absolute
is_absolute_path() {
    case "$1" in
        /*) return 0 ;;
        *) return 1 ;;
    esac
}

# Build a single hook entry for the nested format
# Usage: build_hook_entry "event-type"
build_hook_entry() {
    local event_arg="$1"
    cat <<ENTRY
[
  {
    "matcher": "",
    "hooks": [
      {
        "type": "command",
        "command": "$NOTIFY_SCRIPT $event_arg"
      }
    ]
  }
]
ENTRY
}

# Function to uninstall hooks
uninstall_hooks() {
    log_info "Uninstalling Claude Headspace hooks..."

    # Remove notification script
    if [ -f "$NOTIFY_SCRIPT" ]; then
        rm "$NOTIFY_SCRIPT"
        log_info "Removed $NOTIFY_SCRIPT"
    fi

    # Remove hooks from settings.json
    if [ -f "$SETTINGS_FILE" ]; then
        if command -v jq &> /dev/null; then
            TMP_FILE=$(mktemp)
            # Remove headspace hook entries from each event type
            # For each event key, filter out entries whose hooks contain notify-headspace
            jq '
                if .hooks then
                    .hooks |= with_entries(
                        .value |= map(
                            select(
                                .hooks | all(
                                    .command | contains("notify-headspace") | not
                                )
                            )
                        )
                    )
                    # Remove event keys that have empty arrays
                    | .hooks |= with_entries(select(.value | length > 0))
                else
                    .
                end
            ' "$SETTINGS_FILE" > "$TMP_FILE"
            mv "$TMP_FILE" "$SETTINGS_FILE"
            log_info "Removed hooks from $SETTINGS_FILE"
        else
            log_warn "jq not installed, cannot automatically update settings.json"
            log_warn "Please manually remove notify-headspace hooks from $SETTINGS_FILE"
        fi
    fi

    log_info "Uninstallation complete"
    exit 0
}

# Check for uninstall flag
if [ "$1" = "--uninstall" ]; then
    uninstall_hooks
fi

# Verify source script exists
if [ ! -f "$SOURCE_SCRIPT" ]; then
    log_error "Source script not found: $SOURCE_SCRIPT"
    log_error "Please run this script from the claude_headspace directory"
    exit 1
fi

# Create hooks directory if needed
if [ ! -d "$HOOKS_DIR" ]; then
    mkdir -p "$HOOKS_DIR"
    log_info "Created hooks directory: $HOOKS_DIR"
fi

# Copy notification script
cp "$SOURCE_SCRIPT" "$NOTIFY_SCRIPT"
chmod +x "$NOTIFY_SCRIPT"
log_info "Installed notification script: $NOTIFY_SCRIPT"

# Verify the path is absolute (Claude Code requires absolute paths)
if ! is_absolute_path "$NOTIFY_SCRIPT"; then
    log_error "Script path is not absolute: $NOTIFY_SCRIPT"
    exit 1
fi

# Check if jq is available
if ! command -v jq &> /dev/null; then
    log_warn "jq is not installed. Cannot automatically update settings.json"
    log_warn "Please install jq (brew install jq) or manually add hooks to $SETTINGS_FILE"
    log_info ""
    log_info "Merge the following into your $SETTINGS_FILE hooks object:"
    log_info ""
    cat << EOF
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$NOTIFY_SCRIPT session-start"
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$NOTIFY_SCRIPT session-end"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$NOTIFY_SCRIPT stop"
          }
        ]
      }
    ],
    "Notification": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$NOTIFY_SCRIPT notification"
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$NOTIFY_SCRIPT user-prompt-submit"
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "AskUserQuestion",
        "hooks": [
          {
            "type": "command",
            "command": "$NOTIFY_SCRIPT pre-tool-use"
          }
        ]
      }
    ],
    "PermissionRequest": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "$NOTIFY_SCRIPT permission-request"
          }
        ]
      }
    ]
  }
}
EOF
    exit 0
fi

# Create settings.json if it doesn't exist
if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{}' > "$SETTINGS_FILE"
    log_info "Created settings file: $SETTINGS_FILE"
fi

# Build a hook entry with a specific matcher
# Usage: build_matched_hook_entry "event-type" "matcher-value"
build_matched_hook_entry() {
    local event_arg="$1"
    local matcher="$2"
    cat <<MENTRY
{
    "matcher": "$matcher",
    "hooks": [
      {
        "type": "command",
        "command": "$NOTIFY_SCRIPT $event_arg"
      }
    ]
}
MENTRY
}

# Build the hooks configuration using the nested PascalCase format
# Each event type maps to an array of hook groups
# Notification hooks use matchers for specific notification types
NOTIFICATION_HOOKS=$(jq -n \
    --argjson elicitation "$(build_matched_hook_entry 'notification' 'elicitation_dialog')" \
    --argjson permission "$(build_matched_hook_entry 'notification' 'permission_prompt')" \
    --argjson idle "$(build_matched_hook_entry 'notification' 'idle_prompt')" \
    --argjson catchall "$(build_matched_hook_entry 'notification' '')" \
    '[$elicitation, $permission, $idle, $catchall]')

PRE_TOOL_USE_HOOKS=$(jq -n \
    --argjson ask "$(build_matched_hook_entry 'pre-tool-use' 'AskUserQuestion')" \
    '[$ask]')

PERMISSION_REQUEST_HOOKS=$(jq -n \
    --argjson catchall "$(build_matched_hook_entry 'permission-request' '')" \
    '[$catchall]')

HOOKS_OBJ=$(jq -n \
    --argjson session_start "$(build_hook_entry 'session-start')" \
    --argjson session_end "$(build_hook_entry 'session-end')" \
    --argjson stop "$(build_hook_entry 'stop')" \
    --argjson notification "$NOTIFICATION_HOOKS" \
    --argjson user_prompt "$(build_hook_entry 'user-prompt-submit')" \
    --argjson post_tool_use "$(build_hook_entry 'post-tool-use')" \
    --argjson pre_tool_use "$PRE_TOOL_USE_HOOKS" \
    --argjson permission_request "$PERMISSION_REQUEST_HOOKS" \
    '{
        "SessionStart": $session_start,
        "SessionEnd": $session_end,
        "Stop": $stop,
        "Notification": $notification,
        "UserPromptSubmit": $user_prompt,
        "PostToolUse": $post_tool_use,
        "PreToolUse": $pre_tool_use,
        "PermissionRequest": $permission_request
    }')

# Update settings.json
# Merge new hooks into existing settings, preserving non-headspace hooks
TMP_FILE=$(mktemp)

if jq -e '.hooks' "$SETTINGS_FILE" > /dev/null 2>&1; then
    # Settings already has hooks — merge carefully
    # For each of our 5 event types:
    #   1. Remove existing entries that reference notify-headspace
    #   2. Add our new entries
    # Preserve any other event types and non-headspace hooks
    jq --argjson new_hooks "$HOOKS_OBJ" '
        .hooks as $existing |
        .hooks = (
            # Start with existing hooks
            ($existing // {}) |
            # For each new hook event type, merge it in
            reduce ($new_hooks | to_entries[]) as $entry (
                .;
                # Get existing entries for this event type, minus any headspace ones
                ($entry.key) as $key |
                ((.[$key] // []) | map(
                    select(.hooks | all(.command | contains("notify-headspace") | not))
                )) as $kept |
                # Append our new entries
                .[$key] = ($kept + $entry.value)
            )
        )
    ' "$SETTINGS_FILE" > "$TMP_FILE"
else
    # No hooks yet — add the hooks object
    jq --argjson new_hooks "$HOOKS_OBJ" '.hooks = $new_hooks' "$SETTINGS_FILE" > "$TMP_FILE"
fi

mv "$TMP_FILE" "$SETTINGS_FILE"
log_info "Updated settings: $SETTINGS_FILE"

# Verify installation
log_info ""
log_info "Installation complete!"
log_info ""
log_info "Hooks installed for events:"
jq -r '.hooks | to_entries[] | select(.value | any(.hooks[]?; .command | contains("notify-headspace"))) | "  \(.key)"' "$SETTINGS_FILE"
log_info ""
log_info "To verify hooks are working:"
log_info "  1. Start a new Claude Code session"
log_info "  2. Check the Headspace dashboard for the new agent"
log_info "  3. View hook status at http://localhost:5055/hook/status"
log_info ""
log_info "To uninstall: $0 --uninstall"
