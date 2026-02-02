# Claude Headspace Setup Prompt

Give this prompt to Claude Code to set up full integration with Claude Headspace. It installs hooks, creates the CLI symlink, ensures database access, and verifies everything works.

Copy everything inside the fenced block below and paste it as a prompt to Claude Code.

---

````text
Set up Claude Headspace integration for this system. This involves installing lifecycle hooks,
the CLI launcher, database, and verifying connectivity. Follow every step below in order.
If any REQUIRED step fails, stop and report the failure. If an OPTIONAL step fails, note it and continue.

IMPORTANT: Before running the commands in each step, print the step's "Tell the user" message
so they understand what is about to happen and why they are being asked to approve each command.

## Step 1: Detect paths (REQUIRED)

Tell the user: "Detecting system paths — reading your home directory, username, and locating the Claude Headspace repo and a bin directory for the CLI symlink. These are read-only checks."

Detect and confirm these values before proceeding:

- HOME_DIR: The current user's home directory ($HOME)
- USERNAME: The macOS username (whoami)
- CLAUDE_DIR: $HOME/.claude
- HOOKS_DIR: $HOME/.claude/hooks
- SETTINGS_FILE: $HOME/.claude/settings.json
- PROJECTS_DIR: $HOME/.claude/projects

Find the Claude Headspace repository by searching for a directory containing both
`bin/notify-headspace.sh` and `bin/install-hooks.sh`. Check these locations in order:
1. The current working directory
2. Common locations: ~/dev/**/claude_headspace, ~/projects/**/claude_headspace, ~/code/**/claude_headspace
3. Use `find ~ -maxdepth 5 -name "notify-headspace.sh" -path "*/bin/*" 2>/dev/null | head -5` as a last resort

Set:
- REPO_DIR: The root of the Claude Headspace repository (the directory containing bin/, src/, run.py)

Find the user's personal bin directory. Check in order of preference:
1. ~/bin (preferred — standard user bin location on macOS)
2. ~/.local/bin (alternative — XDG-style user bin location)
3. /usr/local/bin (fallback — system-wide, always in PATH)

Selection logic:
- If ~/bin exists, use it (regardless of whether it is currently in PATH)
- Else if ~/.local/bin exists, use it (regardless of whether it is currently in PATH)
- Else default to ~/bin (we will create it and handle PATH below)

If the selected directory does not exist yet, create it:
```bash
mkdir -p $USER_BIN
```

Check whether $USER_BIN is currently in $PATH:
```bash
echo "$PATH" | tr ':' '\n' | grep -qx "$USER_BIN" && echo "IN_PATH=yes" || echo "IN_PATH=no"
```

Set:
- USER_BIN: The user's bin directory for the CLI symlink
- USER_BIN_IN_PATH: Whether $USER_BIN is currently in the shell's PATH (yes/no)

Print all detected paths and confirm they look correct before proceeding.

## Step 2: Check prerequisites (REQUIRED)

Tell the user: "Checking that required tools are installed — PostgreSQL, curl, jq, Python 3.10+, and the Claude Code CLI. Also checking for terminal-notifier (optional, for macOS desktop notifications). All read-only checks."

Check each prerequisite. Report status for all, then fail if any REQUIRED one is missing.

### PostgreSQL (REQUIRED)
```bash
pg_isready
```
If PostgreSQL is not running, STOP and report:
"PostgreSQL is required but not running. Install with: brew install postgresql@16 && brew services start postgresql@16"

### curl (REQUIRED)
```bash
which curl
```

### jq (REQUIRED for hook installation)
```bash
which jq
```
If missing, STOP and report:
"jq is required for hook installation. Install with: brew install jq"

### terminal-notifier (OPTIONAL - enables macOS desktop notifications)
```bash
which terminal-notifier
```
If missing, note it as unavailable and continue. Do NOT auto-install — report:
"terminal-notifier is not installed. Desktop notifications will be unavailable.
 To install later: brew install terminal-notifier"

### Python 3.10+ (REQUIRED)
```bash
python3 --version
```
Parse the version number from the output and verify it is 3.10 or higher.
If below 3.10, STOP and report:
"Python 3.10+ is required but found version X.Y. Install with: brew install python@3.12"

### Claude Code CLI (REQUIRED)
```bash
which claude
```
If not found, STOP and report that Claude Code must be installed first.

## Step 3: Create PostgreSQL database (REQUIRED)

Tell the user: "Checking whether the 'claude_headspace' PostgreSQL database exists, and creating it if not. This is where the dashboard stores session data."

Try connecting to the database directly:
```bash
psql -d claude_headspace -c "SELECT 1;" 2>&1
```

If the connection succeeds, the database already exists — skip creation and move on.

If it fails (e.g. "database does not exist"), create it:
```bash
createdb claude_headspace
```

Then verify the newly created database is accessible:
```bash
psql -d claude_headspace -c "SELECT 1;" 2>&1
```

If this verification fails, report the error and STOP.

## Step 4: Install hooks using install-hooks.sh (REQUIRED)

Tell the user: "Running the hook installer script. This copies notify-headspace.sh into ~/.claude/hooks/ and adds hook entries to ~/.claude/settings.json so every Claude Code session sends lifecycle events to the Headspace server. Existing non-headspace hooks are preserved."

Run the installation script from the repository:
```bash
$REPO_DIR/bin/install-hooks.sh
```

This script:
- Copies `notify-headspace.sh` to `~/.claude/hooks/`
- Configures hooks in `~/.claude/settings.json` using the correct nested PascalCase format
- Preserves any existing non-headspace hooks in settings.json

NOTE: The script may exit with a non-zero status from its own internal verification step
even when hooks were installed correctly. Do NOT treat the exit code as fatal.
Instead, rely on the verification commands below to confirm success.

Verify the hooks were installed correctly:
```bash
cat ~/.claude/settings.json | jq '.hooks | keys'
```

Expected output should include: SessionStart, SessionEnd, Stop, Notification, UserPromptSubmit

Also verify the hook commands reference the correct script:
```bash
cat ~/.claude/settings.json | jq '.hooks.SessionStart[0].hooks[0].command'
```

It MUST be an absolute path (starting with /) pointing to `notify-headspace.sh`.

## Step 5: Symlink the claude-headspace CLI and ensure PATH access (REQUIRED)

Tell the user: "Making the claude-headspace CLI available system-wide by creating a symlink in your bin directory. This lets you launch monitored sessions with 'claude-headspace start' from anywhere."

```bash
chmod +x $REPO_DIR/bin/claude-headspace
ln -sf $REPO_DIR/bin/claude-headspace $USER_BIN/claude-headspace
```

Verify it's accessible:
```bash
which claude-headspace
```

If `which` finds it, this step is done — move on to Step 6.

If `which` does NOT find it (or if USER_BIN_IN_PATH was "no" from Step 1), the bin directory
is not in the shell's PATH. You MUST fix this before continuing:

### Step 5b: Add bin directory to PATH

Tell the user: "Your bin directory ($USER_BIN) is not in your shell's PATH, so the
claude-headspace command won't be found. I need to add it to one of your shell config files.
Let me check which config files exist on your system."

Scan for shell configuration files in the user's home directory:
```bash
ls -1 ~/.bashrc ~/.bash_profile ~/.profile ~/.zshrc ~/.zprofile 2>/dev/null
```

This will list only the files that actually exist. Collect the results into a list.

If NO config files are found, tell the user:
"No shell configuration files found. You will need to manually add the following line
to your shell's startup file:
  export PATH="$USER_BIN:$PATH"
Then open a new terminal or source the file."
Mark this step as a manual action and continue to Step 6.

If config files ARE found, present them to the user as a numbered list and ask which
one to use. For example:
"The following shell config files exist on your system:
  1. ~/.zshrc
  2. ~/.zprofile
  3. ~/.bash_profile
Which file should I add the PATH entry to? (Enter the number)"

Wait for the user's response. Once they choose a file (call it $SHELL_CONFIG):

First, check if the PATH export already exists in the chosen file:
```bash
grep -q "export PATH=\"$USER_BIN" "$SHELL_CONFIG" 2>/dev/null && echo "ALREADY_PRESENT" || echo "NOT_PRESENT"
```

If ALREADY_PRESENT:
Tell the user: "The PATH entry already exists in $SHELL_CONFIG. You may need to open
a new terminal or run: source $SHELL_CONFIG"
Continue to Step 6.

If NOT_PRESENT, append the PATH export to the chosen file:
```bash
echo '' >> "$SHELL_CONFIG"
echo '# Added by Claude Headspace setup — puts user bin directory in PATH' >> "$SHELL_CONFIG"
echo "export PATH=\"$USER_BIN:\$PATH\"" >> "$SHELL_CONFIG"
```

Tell the user: "Added PATH entry to $SHELL_CONFIG. To use claude-headspace in this terminal,
run:
  source $SHELL_CONFIG
Or simply open a new terminal window. The command will be available in all future sessions."

Verify the line was written:
```bash
tail -3 "$SHELL_CONFIG"
```

The last 3 lines should show the comment and export line that were just added.

## Step 6: Verify ~/.claude/projects/ access (REQUIRED)

Tell the user: "Checking that ~/.claude/projects/ is readable. The Headspace server reads Claude Code session JSONL files from this directory to track sessions. Read-only check."

The Headspace server reads Claude Code session JSONL files from this directory.

```bash
ls -la ~/.claude/projects/ 2>/dev/null
```

If the directory doesn't exist, that's OK — Claude Code creates it on first session.
If it exists, confirm the current user has read permission on it and its contents.

## Step 7: Verify the Headspace server (OPTIONAL)

Tell the user: "Checking whether the Headspace server is running on localhost:5055. This step is optional — hooks work fine even when the server is offline."

Check if the server is running:
```bash
curl -s --connect-timeout 2 http://localhost:5055/health
```

If the server is not running, report:
"Headspace server is not currently running. Start it with:
  cd $REPO_DIR && python run.py
This step is optional — hooks will queue silently when the server is offline."

If the server IS running, report that the health check passed.

Do NOT send a test hook event (e.g. to `/hook/session-start`). Test events create
phantom agents on the dashboard that never receive a session-end and persist forever.
Connectivity is sufficiently verified by the health check above.

## Step 8: Report results

Print a summary checklist:

```
Claude Headspace Setup Results
==============================
[PASS/FAIL] PostgreSQL running and claude_headspace database exists
[PASS/FAIL] Hook script installed at ~/.claude/hooks/notify-headspace.sh
[PASS/FAIL] Hooks configured in ~/.claude/settings.json (5 events)
[PASS/FAIL] claude-headspace CLI symlinked to $USER_BIN
[PASS/FAIL/MANUAL] PATH configured (bin directory in PATH or shell config updated)
[PASS/FAIL] ~/.claude/projects/ accessible
[PASS/SKIP] terminal-notifier installed (optional)
[PASS/SKIP] Headspace server reachable (health check, optional)
```

If all REQUIRED items passed:
  "Setup complete. Claude Headspace hooks are installed globally — every Claude Code
   session on this machine will now send lifecycle events to the Headspace server.

   To start the dashboard:  cd $REPO_DIR && python run.py
   To launch a monitored session:  claude-headspace start
   To view hook status:  curl http://localhost:5055/hook/status"

If PATH was updated during setup, add this note:
  "Note: If you haven't yet sourced your shell config or opened a new terminal, run:
     source $SHELL_CONFIG
   before using the claude-headspace command."

If any REQUIRED item failed:
  List the failures and what the user needs to fix before retrying.
````
