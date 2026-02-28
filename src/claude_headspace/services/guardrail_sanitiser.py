"""Error output sanitisation for remote agent guardrails.

Strips system-revealing information from tool error output before it
reaches the agent's conversational context:
- File paths (absolute and relative)
- Python stack traces (Traceback blocks)
- Module/class/function names from tracebacks
- Environment details (venv paths, Python version strings)
- Process IDs (pid=NNN, PID: NNN)

Sanitised output preserves a generic failure message so the agent
can acknowledge the failure and retry without leaking system details.
"""

import re
import logging

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────
# Compiled patterns for stripping sensitive information
# ──────────────────────────────────────────────────────────────

# Absolute file paths: /foo/bar/baz.py, /home/user/.venv/lib/...
_ABSOLUTE_PATH = re.compile(
    r'(?<![a-zA-Z0-9])/(?:[a-zA-Z0-9._-]+/)+[a-zA-Z0-9._-]+'
)

# Python traceback blocks: "Traceback (most recent call last): ... ExceptionType: message"
_TRACEBACK_BLOCK = re.compile(
    r'Traceback \(most recent call last\):.*?(?=\n\n|\n[^\s]|\Z)',
    re.DOTALL,
)

# Individual traceback frame lines: "  File "/path/to/file.py", line 42, in func_name"
_TRACEBACK_FRAME = re.compile(
    r'^\s*File\s+"[^"]+",\s+line\s+\d+.*$',
    re.MULTILINE,
)

# Module dotted names from error lines: "module.submodule.ClassName: error message"
# Also matches dotted names followed by ) as in "(psycopg2.errors.UndefinedColumn)"
_MODULE_ERROR = re.compile(
    r'\b(?:[a-zA-Z_]\w*\.){2,}[a-zA-Z_]\w*(?=[:\)\s])',
)

# Python/virtualenv path fragments
_VENV_PATH = re.compile(
    r'(?:venv|\.venv|virtualenv|site-packages|dist-packages)'
    r'(?:/[a-zA-Z0-9._-]+)*',
)

# Process IDs: "pid=12345", "PID: 12345", "process 12345"
_PROCESS_ID = re.compile(
    r'\b(?:pid[=:]\s*\d+|PID[=:]\s*\d+|process\s+\d+)\b',
    re.IGNORECASE,
)

# Python version strings: "Python 3.10.4", "python3.10"
_PYTHON_VERSION = re.compile(
    r'\bpython\s*3\.\d+(?:\.\d+)?\b',
    re.IGNORECASE,
)

# Environment variable patterns: "ENV_VAR=value" or "SOME_SETTING: value"
_ENV_VAR = re.compile(
    r'\b[A-Z][A-Z0-9_]{3,}(?:=\S+|:\s+\S+)',
)

# Generic replacement for redacted content
_REDACTION = "[details redacted]"

# Pre-lowercased error indicators for efficient matching
_ERROR_INDICATORS = [
    "traceback (most recent call last)",
    "error:",
    "exception:",
    "failed",
    "fatal:",
    "panic:",
]


def sanitise_error_output(text: str | None) -> str | None:
    """Strip system-revealing information from error output text.

    Removes file paths, stack traces, module names, environment details,
    and process IDs. Preserves a generic failure indication so the agent
    can retry.

    Args:
        text: Raw error output from a tool invocation.

    Returns:
        Sanitised text with sensitive details replaced by [details redacted].
    """
    if not text:
        return text

    result = text

    # Strip full traceback blocks first (most comprehensive)
    result = _TRACEBACK_BLOCK.sub(_REDACTION, result)

    # Strip individual traceback frame lines that may survive
    result = _TRACEBACK_FRAME.sub(_REDACTION, result)

    # Strip module dotted names from error lines
    result = _MODULE_ERROR.sub(_REDACTION, result)

    # Strip absolute file paths
    result = _ABSOLUTE_PATH.sub(_REDACTION, result)

    # Strip venv/virtualenv path fragments
    result = _VENV_PATH.sub(_REDACTION, result)

    # Strip process IDs
    result = _PROCESS_ID.sub(_REDACTION, result)

    # Strip Python version strings
    result = _PYTHON_VERSION.sub(_REDACTION, result)

    # Strip environment variable patterns
    result = _ENV_VAR.sub(_REDACTION, result)

    # Collapse multiple consecutive redactions into one
    result = re.sub(
        r'(?:\[details redacted\]\s*){2,}',
        '[details redacted] ',
        result,
    )

    # Clean up empty lines left by redaction
    result = re.sub(r'\n\s*\n\s*\n', '\n\n', result)

    return result.strip()


def contains_error_patterns(text: str) -> bool:
    """Check if text contains patterns that indicate error output.

    Used to decide whether sanitisation should be applied. Normal
    agent output (non-error) is never sanitised to avoid false positives.

    Args:
        text: Text to check.

    Returns:
        True if the text contains error indicators.
    """
    if not text:
        return False

    # Check for common error indicators (pre-lowercased for efficiency)
    text_lower = text.lower()
    for indicator in _ERROR_INDICATORS:
        if indicator in text_lower:
            return True

    # Check for file path patterns in context that suggests error output
    if _ABSOLUTE_PATH.search(text) and ("error" in text_lower or "failed" in text_lower):
        return True

    return False
