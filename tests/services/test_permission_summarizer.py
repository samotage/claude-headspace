"""Tests for permission command summarizer."""

import pytest

from claude_headspace.services.permission_summarizer import (
    classify_safety,
    summarize_permission_command,
)


class TestSummarizePermissionCommand:
    """Tests for summarize_permission_command."""

    # --- Bash: HTTP clients ---

    def test_bash_curl_with_url(self):
        result = summarize_permission_command("Bash", {"command": "curl -s http://localhost:5055/dashboard"})
        assert result == "Bash: curl from localhost:5055"

    def test_bash_curl_https(self):
        result = summarize_permission_command("Bash", {"command": "curl https://api.example.com/v1/data"})
        assert result == "Bash: curl from api.example.com"

    def test_bash_wget(self):
        result = summarize_permission_command("Bash", {"command": "wget https://example.com/file.tar.gz"})
        assert result == "Bash: wget from example.com"

    def test_bash_curl_no_url(self):
        result = summarize_permission_command("Bash", {"command": "curl --version"})
        # --version is a flag, so no URL found
        assert result == "Bash: curl"

    # --- Bash: File readers ---

    def test_bash_cat(self):
        result = summarize_permission_command("Bash", {"command": "cat /etc/hosts"})
        assert result == "Bash: read hosts"

    def test_bash_tail(self):
        result = summarize_permission_command("Bash", {"command": "tail -f /var/log/syslog"})
        assert result == "Bash: read syslog"

    def test_bash_head(self):
        result = summarize_permission_command("Bash", {"command": "head -n 20 src/app.py"})
        assert result == "Bash: read app.py"

    # --- Bash: Directory listing ---

    def test_bash_ls(self):
        result = summarize_permission_command("Bash", {"command": "ls -la /tmp"})
        assert result == "Bash: list /tmp"

    def test_bash_find(self):
        result = summarize_permission_command("Bash", {"command": "find . -name '*.py'"})
        assert result == "Bash: list ."

    # --- Bash: Git ---

    def test_bash_git_status(self):
        result = summarize_permission_command("Bash", {"command": "git status"})
        assert result == "Bash: git status"

    def test_bash_git_push(self):
        result = summarize_permission_command("Bash", {"command": "git push origin main"})
        assert result == "Bash: git push"

    def test_bash_git_diff(self):
        result = summarize_permission_command("Bash", {"command": "git diff --staged"})
        assert result == "Bash: git diff"

    # --- Bash: Package managers ---

    def test_bash_npm_install(self):
        result = summarize_permission_command("Bash", {"command": "npm install express"})
        assert result == "Bash: npm install"

    def test_bash_pip_install(self):
        result = summarize_permission_command("Bash", {"command": "pip install -e '.[dev]'"})
        assert result == "Bash: pip install"

    def test_bash_brew(self):
        result = summarize_permission_command("Bash", {"command": "brew install tmux"})
        assert result == "Bash: brew install"

    # --- Bash: File operations ---

    def test_bash_rm(self):
        result = summarize_permission_command("Bash", {"command": "rm -rf /tmp/test"})
        assert result == "Bash: rm test"

    def test_bash_mkdir(self):
        result = summarize_permission_command("Bash", {"command": "mkdir -p src/components"})
        assert result == "Bash: mkdir components"

    def test_bash_cp(self):
        result = summarize_permission_command("Bash", {"command": "cp file.txt backup.txt"})
        assert result == "Bash: cp backup.txt"

    # --- Bash: Script runners ---

    def test_bash_python(self):
        result = summarize_permission_command("Bash", {"command": "python run.py"})
        assert result == "Bash: run run.py"

    def test_bash_node(self):
        result = summarize_permission_command("Bash", {"command": "node server.js"})
        assert result == "Bash: run server.js"

    # --- Bash: Text transforms ---

    def test_bash_sed(self):
        result = summarize_permission_command("Bash", {"command": "sed -i 's/old/new/g' config.yaml"})
        assert result == "Bash: transform config.yaml"

    # --- Bash: Container tools ---

    def test_bash_docker(self):
        result = summarize_permission_command("Bash", {"command": "docker build -t myapp ."})
        assert result == "Bash: docker build"

    def test_bash_kubectl(self):
        result = summarize_permission_command("Bash", {"command": "kubectl get pods"})
        assert result == "Bash: kubectl get"

    # --- Bash: Piped commands ---

    def test_bash_piped_command_uses_first(self):
        result = summarize_permission_command(
            "Bash",
            {"command": "curl -s http://localhost:5055/dashboard | sed -n '630,645p'"},
        )
        assert result == "Bash: curl from localhost:5055"

    # --- Bash: Commands with env vars ---

    def test_bash_env_var_prefix(self):
        result = summarize_permission_command(
            "Bash",
            {"command": "DATABASE_URL=postgres://localhost/test python run.py"},
        )
        assert result == "Bash: run run.py"

    # --- Bash: Empty/missing command ---

    def test_bash_empty_command(self):
        result = summarize_permission_command("Bash", {"command": ""})
        assert result == "Bash: (empty command)"

    def test_bash_no_command_key(self):
        result = summarize_permission_command("Bash", {})
        assert result == "Bash: (empty command)"

    # --- Bash: Chained commands ---

    def test_bash_chained_with_and(self):
        result = summarize_permission_command(
            "Bash",
            {"command": "npm install && npm run build"},
        )
        assert result == "Bash: npm install"

    # --- Bash: Test runners ---

    def test_bash_pytest(self):
        result = summarize_permission_command(
            "Bash",
            {"command": "pytest tests/services/test_hook_receiver.py"},
        )
        assert result == "Bash: pytest test_hook_receiver.py"

    # --- Bash: Build tools ---

    def test_bash_make(self):
        result = summarize_permission_command("Bash", {"command": "make build"})
        assert result == "Bash: make build"

    # --- Read/Write/Edit tools ---

    def test_read_tool(self):
        result = summarize_permission_command("Read", {"file_path": "/Users/sam/project/src/app.py"})
        assert result == "Read: src/app.py"

    def test_write_tool(self):
        result = summarize_permission_command("Write", {"file_path": "/tmp/claude-501/scratchpad/output.txt"})
        assert result == "Write: (temp) output.txt"

    def test_edit_tool(self):
        result = summarize_permission_command("Edit", {"file_path": "/Users/sam/project/config.yaml"})
        assert result == "Edit: project/config.yaml"

    def test_read_no_path(self):
        result = summarize_permission_command("Read", {})
        assert result == "Read: (no path)"

    # --- Glob/Grep ---

    def test_glob_tool(self):
        result = summarize_permission_command("Glob", {"pattern": "**/*.py"})
        assert result == "Search: **/*.py"

    def test_grep_tool(self):
        result = summarize_permission_command("Grep", {"pattern": "def process_hook"})
        assert result == "Search: def process_hook"

    # --- Web tools ---

    def test_webfetch(self):
        result = summarize_permission_command("WebFetch", {"url": "https://docs.python.org/3/library/re.html"})
        assert result == "Web: fetch docs.python.org"

    def test_websearch(self):
        result = summarize_permission_command("WebSearch", {"query": "flask sse tutorial"})
        assert result == "Web: search 'flask sse tutorial'"

    # --- Unknown tool ---

    def test_unknown_tool(self):
        result = summarize_permission_command("CustomTool", {"some": "input"})
        assert result == "Permission: CustomTool"

    # --- No tool name ---

    def test_no_tool_name(self):
        result = summarize_permission_command(None, None)
        assert result == "Permission needed"

    # --- Pane context with description ---

    def test_pane_context_description_preferred(self):
        result = summarize_permission_command(
            "Bash",
            {"command": "curl -s http://localhost:5055/dashboard"},
            pane_context={"description": "Check state-bar HTML around line 634"},
        )
        assert result == "Bash: Check state-bar HTML around line 634"

    def test_pane_context_empty_description_ignored(self):
        result = summarize_permission_command(
            "Bash",
            {"command": "git status"},
            pane_context={"description": ""},
        )
        assert result == "Bash: git status"

    # --- Truncation ---

    def test_long_summary_truncated(self):
        result = summarize_permission_command(
            "Bash",
            {"command": "curl http://very-long-hostname-that-goes-on-and-on-and-on.example.com/with/a/very/long/path/too"},
        )
        assert len(result) <= 63  # MAX_SUMMARY_LENGTH + "..."


class TestClassifySafety:
    """Tests for classify_safety."""

    # --- Read-only tools ---

    def test_read_tool_safe_read(self):
        assert classify_safety("Read", {"file_path": "/any/file"}) == "safe_read"

    def test_glob_safe_read(self):
        assert classify_safety("Glob", {"pattern": "**/*.py"}) == "safe_read"

    def test_grep_safe_read(self):
        assert classify_safety("Grep", {"pattern": "foo"}) == "safe_read"

    def test_webfetch_safe_read(self):
        assert classify_safety("WebFetch", {"url": "https://example.com"}) == "safe_read"

    # --- Write tools ---

    def test_write_tool_safe_write(self):
        assert classify_safety("Write", {"file_path": "/any/file"}) == "safe_write"

    def test_edit_tool_safe_write(self):
        assert classify_safety("Edit", {"file_path": "/any/file"}) == "safe_write"

    # --- Bash: safe read commands ---

    def test_bash_cat_safe_read(self):
        assert classify_safety("Bash", {"command": "cat /etc/hosts"}) == "safe_read"

    def test_bash_ls_safe_read(self):
        assert classify_safety("Bash", {"command": "ls -la"}) == "safe_read"

    def test_bash_grep_safe_read(self):
        assert classify_safety("Bash", {"command": "grep -r 'pattern' ."}) == "safe_read"

    def test_bash_curl_get_safe_read(self):
        assert classify_safety("Bash", {"command": "curl https://api.example.com"}) == "safe_read"

    def test_bash_curl_post_safe_write(self):
        assert classify_safety("Bash", {"command": "curl -X POST https://api.example.com -d 'data'"}) == "safe_write"

    # --- Bash: git commands ---

    def test_bash_git_status_safe_read(self):
        assert classify_safety("Bash", {"command": "git status"}) == "safe_read"

    def test_bash_git_log_safe_read(self):
        assert classify_safety("Bash", {"command": "git log --oneline"}) == "safe_read"

    def test_bash_git_diff_safe_read(self):
        assert classify_safety("Bash", {"command": "git diff"}) == "safe_read"

    def test_bash_git_commit_safe_write(self):
        assert classify_safety("Bash", {"command": "git commit -m 'msg'"}) == "safe_write"

    def test_bash_git_push_safe_write(self):
        assert classify_safety("Bash", {"command": "git push origin main"}) == "safe_write"

    def test_bash_git_push_force_destructive(self):
        assert classify_safety("Bash", {"command": "git push --force origin main"}) == "destructive"

    # --- Bash: destructive commands ---

    def test_bash_rm_destructive(self):
        assert classify_safety("Bash", {"command": "rm -rf /tmp/test"}) == "destructive"

    # --- Bash: unknown commands ---

    def test_bash_unknown_command(self):
        assert classify_safety("Bash", {"command": "some-custom-tool arg1"}) == "unknown"

    # --- No tool name ---

    def test_no_tool_name(self):
        assert classify_safety(None, None) == "unknown"

    # --- Package managers ---

    def test_bash_npm_install_safe_write(self):
        assert classify_safety("Bash", {"command": "npm install express"}) == "safe_write"

    def test_bash_pip_install_safe_write(self):
        assert classify_safety("Bash", {"command": "pip install flask"}) == "safe_write"

    # --- Script/test runners ---

    def test_bash_python_safe_write(self):
        assert classify_safety("Bash", {"command": "python run.py"}) == "safe_write"

    def test_bash_pytest_safe_write(self):
        assert classify_safety("Bash", {"command": "pytest tests/"}) == "safe_write"

    # --- Unknown tool ---

    def test_unknown_tool(self):
        assert classify_safety("CustomTool", {"anything": "here"}) == "unknown"

    # --- Empty command ---

    def test_bash_empty_command(self):
        assert classify_safety("Bash", {"command": ""}) == "unknown"
