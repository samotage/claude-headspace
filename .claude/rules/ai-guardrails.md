# AI Assistant Guardrails

**CRITICAL:** Rules to prevent destructive operations and ensure human oversight.

## Follow Instructions Literally

**When instructions are explicit, follow them exactly.**

- Do NOT reinterpret, add conditions, or substitute your own judgment
- Do NOT add "safety" checks on top of already-granted permissions
- Do NOT ask for confirmation when settings.json already allows the action
- "Explicit" means "do this" — not "consider doing this"
- If CLAUDE.md, settings.json, guardrails, or the user says X, do X. No hedging, no second-guessing.
- If permissions are granted in settings.json, they are GRANTED. Do not re-ask.

## Permissions Hierarchy

**BEFORE applying rules below, check `.claude/settings.json` first.**

1. Check `permissions.allow` list
2. If command matches a pre-approved pattern → Execute without asking. Do NOT prompt.
3. If NOT pre-approved → Apply rules below
4. A blanket permission (e.g., `"Read"`) covers ALL paths — never prompt for specific paths when a blanket permission exists

## Database Protection

**CRITICAL: Tests must NEVER touch production or development databases.**

**Protected databases:** Any database that does NOT end in `_test`. This includes `claude_headspace`, `ot_monitor`, and all other non-test databases on the system.

**Test database rule:**
- ALL pytest tests MUST connect to `claude_headspace_test` (or the appropriate `_test`-suffixed database)
- The `_force_test_database` fixture in `tests/conftest.py` enforces this — it is a session-scoped autouse fixture that sets `DATABASE_URL` to the test database before any test runs
- NEVER remove, bypass, weaken, or modify the `_force_test_database` fixture without explicit user approval
- NEVER set `DATABASE_URL` to a non-test database in test code
- All new test files MUST use the existing fixture system (`app`, `client`, `db_session`). No ad-hoc database connections (e.g., raw `create_engine()` or `psql` calls targeting production) are permitted in tests

**Direct database commands:**
- NEVER run destructive SQL (`DROP DATABASE`, `DROP TABLE`, `TRUNCATE`, `DELETE FROM`) against any non-test database without explicit user approval
- NEVER run `flask db downgrade` against a non-test database without explicit user approval
- `flask db upgrade` on the development database is permitted (it's additive), but ALWAYS confirm the target database first
- When running `psql` commands, ALWAYS verify the target database name before executing

**Verification before any database operation:**
1. Check which database will be affected
2. If the database name does NOT end in `_test`, STOP and ask the user
3. Exception: read-only queries (`SELECT`, `\d`, `\dt`, `\l`) are safe on any database

## Protected Operations

**Pip Operations:**
- NEVER run `pip install` or `pip uninstall` without approval
- Show what packages will change first

**Configuration Changes:**
- NEVER modify config files without showing changes and getting approval
- Protected files: `config.yaml`, `requirements.txt`
- Process: Read → Show diff → Explain → Wait for approval → Make changes

**Destructive Operations:**
ALWAYS ask confirmation before:
- Deleting files/directories
- Resetting git history
- Removing dependencies

## Git Operations

- Never force push to main/master
- Never skip hooks without user request
- Always use `--no-verify` only when explicitly requested

## Testing

**Database safety is non-negotiable.** See "Database Protection" section above.

### Targeted Testing (Default)

**Do NOT run the full test suite on every change.** The suite has ~960 tests and takes minutes to complete. Instead:

1. **Run only tests relevant to the change** — e.g., if you edited `hook_receiver.py`, run `pytest tests/services/test_hook_receiver.py tests/routes/test_hooks.py`
2. **Use `-k` to narrow further** when only a specific behavior changed
3. **Run the full suite only when:**
   - The user explicitly asks for it
   - Preparing a commit or PR (final verification)
   - Changes are broad/cross-cutting (e.g., model changes, conftest changes)

### Test Status Reporting

Report what you ran and the result:
- "Ran 12 targeted tests (test_hook_receiver, test_hooks) — all passed" (good)
- "Tests not run yet" (good)
- No mention of tests (acceptable for exploratory/research work)

### New Test Files

**New test files MUST:**
- Use the existing fixture system (`app`, `client`, `db_session` from conftest.py)
- NEVER create ad-hoc database connections (no raw `create_engine()`, no direct `psql` in tests)
- NEVER hardcode database connection strings
- Verify that `_force_test_database` fixture is active (it's autouse, session-scoped)

### Test Commands
```bash
pytest tests/services/test_foo.py    # Targeted (preferred)
pytest tests/routes/test_bar.py -k "test_specific_case"  # Narrow
pytest                               # Full suite — only when asked
pytest --cov=src                     # Full suite + coverage — only when asked
```

## No Unverified Claims

MUST NOT claim changes are working unless:
- Tests were run and passed
- You have actual output as proof

If unverified, phrase as expectations:
- Bad: "The feature now works correctly"
- Good: "This code should implement the feature. Not yet verified with tests."

## User Observations Are Ground Truth

**When the user reports something is broken, believe them.**

- User's direct visual observations override tool outputs
- Accessibility snapshots, DOM data, and API responses do NOT represent visual rendering
- Never say "it's working" when the user says it isn't
- If your tools show different data than what the user reports, acknowledge the discrepancy immediately: "You're right that it's not displaying correctly. My tool shows the data exists in the DOM, but something is preventing it from rendering. Let me investigate why."

**The correct response when a user reports a problem:**
1. Acknowledge their observation as fact
2. Investigate the cause
3. Fix it

**NOT:**
1. Run a tool
2. Tell them it looks fine to you
3. Make them prove it again

## STOP Means STOP

When user says "STOP", "HANG ON", "WAIT", or similar:
- IMMEDIATELY stop all actions
- Do NOT finish the current operation
- Simply acknowledge: "Stopped." and wait for instructions

## Scope Discipline

- Do ONLY what was explicitly requested
- If user says "don't do X" - take it seriously
- When fixing one thing, do NOT "improve" nearby code
- If you discover something that needs fixing, REPORT it - don't fix it unasked

## Server Restart Policy

**Auto-restart the Flask server** after any changes to `monitor.py` or other code that requires a server restart:
- Run `./restart_server.sh` automatically after making such changes
- Do NOT ask the user or wait for them to restart manually
- This applies to any Python code changes, template changes, or configuration changes that affect the running server

## UI Change Verification

**For any HTML, CSS, or JavaScript changes, you MUST verify visually before claiming completion.**

Flask caches templates aggressively. Browser caches static files. Telling the user "just refresh" is NOT verification.

**Required workflow for UI changes:**
1. Make the code change (HTML/CSS/JS)
2. Restart the Flask server (`./restart_server.sh`)
3. If agent-browser is connected: take a screenshot and verify the change is visible
4. If agent-browser is NOT connected: tell the user you cannot verify and ask them to confirm
5. Only after visual confirmation: report the change as complete

**Never say:**
- "Done. Just do a hard refresh."
- "The CSS is correct, must be browser cache."
- "I've verified the file has the right content."

**Instead say:**
- "Let me restart the server and verify with agent-browser."
- "I cannot verify visually - can you confirm the change appears correctly?"

File content verification (grep, cat) is NOT sufficient for UI changes. The rendered result is what matters.

**Tailwind CSS Warning:**
Tailwind is particularly problematic for verification. Its utility class approach:
- Obfuscates styling - classes like `px-4 py-2 bg-blue-500` tell you nothing about actual rendered appearance
- Creates a black box - utility classes may conflict, be purged, or not apply as expected
- Cannot be reasoned about from code alone - you MUST verify visually

For Tailwind projects: **ALWAYS take a screenshot after any styling change.** Never assume utility classes will produce the expected result. The gap between code and rendered output is larger than with traditional CSS.

## CSS Source-of-Truth

**CRITICAL: Never write custom CSS directly to `static/css/main.css`.**

`main.css` is a **compiled output** generated by Tailwind CLI from `static/css/src/input.css`. Any styles written directly to `main.css` will be **destroyed** on the next Tailwind rebuild.

**Rules:**
- ALL custom CSS (non-Tailwind-utility rules) MUST be added to `static/css/src/input.css`
- NEVER edit `static/css/main.css` directly — it is a build artifact
- After adding custom CSS to `input.css`, rebuild with: `npx @tailwindcss/cli -i static/css/src/input.css -o static/css/main.css`
- When running a Tailwind build as part of other work, verify that no custom styles were lost by checking that all CSS class selectors used in templates still exist in the compiled output

**Verification after any CSS build:**
1. Run the Tailwind build command
2. Spot-check that key custom selectors (`.objective-banner-*`, `.card-editor`, `.state-strip`, `.metric-card`, `.logging-subtab`, etc.) are present in the compiled `main.css`
3. If selectors are missing, the source `input.css` is incomplete — fix it before committing

## AppleScript Considerations

This project uses osascript for iTerm integration:
- Test AppleScript changes carefully on macOS
- Be aware of macOS security/permission requirements for automation
- AppleScript errors may require user to grant permissions in System Preferences

## General Principles

- When in doubt, ask the user
- Explain before acting
- Prefer safe operations
- Make incremental changes
- Be transparent about failures

## Quick Checklist

Before executing commands:
- [ ] Pre-approved in settings.json? → Execute
- [ ] **Database operation?** → Is target a `_test` database? If not, STOP
- [ ] Destructive? → Get approval
- [ ] Config change? → Show diff first
- [ ] Pip install/uninstall? → Explicit approval
- [ ] Git commit? → Did user ask?
- [ ] Claiming success? → Have proof?
