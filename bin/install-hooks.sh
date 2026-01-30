#!/bin/bash
#
# Claude Code Hooks Installation Script
#
# This script installs Claude Headspace hooks into Claude Code's configuration.
# It creates the notification script and updates Claude Code's settings.json.
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
            # Remove headspace hooks from settings
            TMP_FILE=$(mktemp)
            jq 'del(.hooks[] | select(.command | contains("notify-headspace")))' "$SETTINGS_FILE" > "$TMP_FILE"
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
    log_warn "Please install jq or manually add hooks to $SETTINGS_FILE"
    log_info ""
    log_info "Add the following to your $SETTINGS_FILE hooks array:"
    log_info ""
    cat << EOF
{
  "hooks": [
    {
      "event": "session-start",
      "command": "$NOTIFY_SCRIPT session-start"
    },
    {
      "event": "session-end",
      "command": "$NOTIFY_SCRIPT session-end"
    },
    {
      "event": "user-prompt-submit",
      "command": "$NOTIFY_SCRIPT user-prompt-submit"
    },
    {
      "event": "stop",
      "command": "$NOTIFY_SCRIPT stop"
    },
    {
      "event": "notification",
      "command": "$NOTIFY_SCRIPT notification"
    }
  ]
}
EOF
    exit 0
fi

# Create settings.json if it doesn't exist
if [ ! -f "$SETTINGS_FILE" ]; then
    echo '{}' > "$SETTINGS_FILE"
    log_info "Created settings file: $SETTINGS_FILE"
fi

# Build hooks configuration
HOOKS_CONFIG=$(cat << EOF
[
    {
        "event": "session-start",
        "command": "$NOTIFY_SCRIPT session-start"
    },
    {
        "event": "session-end",
        "command": "$NOTIFY_SCRIPT session-end"
    },
    {
        "event": "user-prompt-submit",
        "command": "$NOTIFY_SCRIPT user-prompt-submit"
    },
    {
        "event": "stop",
        "command": "$NOTIFY_SCRIPT stop"
    },
    {
        "event": "notification",
        "command": "$NOTIFY_SCRIPT notification"
    }
]
EOF
)

# Update settings.json
# First, remove any existing headspace hooks, then add new ones
TMP_FILE=$(mktemp)

# Check if hooks array exists
if jq -e '.hooks' "$SETTINGS_FILE" > /dev/null 2>&1; then
    # Remove existing headspace hooks and add new ones
    jq --argjson new_hooks "$HOOKS_CONFIG" '
        .hooks = ([.hooks[] | select(.command | contains("notify-headspace") | not)] + $new_hooks)
    ' "$SETTINGS_FILE" > "$TMP_FILE"
else
    # Create hooks array
    jq --argjson new_hooks "$HOOKS_CONFIG" '.hooks = $new_hooks' "$SETTINGS_FILE" > "$TMP_FILE"
fi

mv "$TMP_FILE" "$SETTINGS_FILE"
log_info "Updated settings: $SETTINGS_FILE"

# Verify installation
log_info ""
log_info "Installation complete!"
log_info ""
log_info "Hooks installed:"
jq '.hooks[] | select(.command | contains("notify-headspace"))' "$SETTINGS_FILE"
log_info ""
log_info "To verify hooks are working:"
log_info "  1. Start a new Claude Code session"
log_info "  2. Check the Headspace dashboard for the new agent"
log_info "  3. View hook status at http://localhost:5055/hook/status"
log_info ""
log_info "To uninstall: $0 --uninstall"
