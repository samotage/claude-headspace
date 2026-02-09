"""Centralised registry of all LLM prompt templates.

Every inference prompt in the codebase lives here so that prompt tuning
is a single-file activity.  Services call ``build_prompt(prompt_type, **ctx)``
instead of assembling strings inline.
"""

_PROMPT_TEMPLATES: dict[str, str] = {
    # --- Summarisation: turn prompts (per-intent) ---
    #
    # IMPORTANT: All summarisation prompts must end with the anti-preamble
    # instruction to prevent models from echoing back the prompt structure.
    #
    # STYLE RULE: Summaries are task board entries. Use imperative/direct form.
    # NEVER describe the user ("The user wants...", "The user is...").
    # Good: "Fix login validation bug"  Bad: "The user wants to fix a bug"
    "turn_command": (
        "{instruction_context}"
        "Command: {text}\n\n"
        "Write a task board entry (~18 tokens) stating the goal of this command. "
        "Use imperative form (e.g. 'Fix login bug', 'Deploy to staging', 'Add unit tests for auth'). "
        "If the command references verifying or checking something, state what specifically is being verified. "
        "NEVER start with 'The user' or describe user behavior. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),
    "turn_question": (
        "{instruction_context}"
        "Agent asked: {text}\n\n"
        "Write a task board entry (~18 tokens) stating what the agent needs to know. "
        "Use direct form (e.g. 'Asking which auth method to use', 'Needs confirmation to delete files'). "
        "NEVER start with 'The user' or describe user behavior. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),
    "turn_completion": (
        "{instruction_context}"
        "Agent output: {text}\n\n"
        "Write a task board entry (~18 tokens) stating what was accomplished. "
        "Use past tense (e.g. 'Implemented auth middleware', 'Fixed CSS layout bug'). "
        "NEVER start with 'The user' or 'The agent'. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),
    "turn_progress": (
        "{instruction_context}"
        "Agent output: {text}\n\n"
        "Write a task board entry (~18 tokens) stating current progress. "
        "Use present tense (e.g. 'Running test suite', 'Refactoring auth module'). "
        "NEVER start with 'The user' or 'The agent'. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),
    "turn_answer": (
        "{instruction_context}"
        "Response: {text}\n\n"
        "Write a task board entry (~18 tokens) stating what was confirmed or provided. "
        "Use direct form (e.g. 'Use PostgreSQL for storage', 'Confirmed: proceed with refactor'). "
        "NEVER start with 'The user' or describe user behavior. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),
    "turn_end_of_task": (
        "{instruction_context}"
        "Final output: {text}\n\n"
        "Write a task board entry (~18 tokens) stating the final outcome. "
        "Use past tense (e.g. 'Completed auth implementation', 'All tests passing'). "
        "NEVER start with 'The user' or 'The agent'. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),
    "turn_default": (
        "{instruction_context}"
        "{actor}: {text}\n\n"
        "Write a task board entry (~18 tokens) stating the action taken or requested. "
        "Use direct form. NEVER start with 'The user' or 'The agent'. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),

    # --- Summarisation: task completion ---
    "task_completion": (
        "Task: {instruction}\n"
        "Final output: {final_turn_text}\n\n"
        "Write a task board entry (~18 tokens) stating what was accomplished. "
        "Use past tense. NEVER start with 'The user' or 'The agent'. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),

    # Task completion when no final agent message available — uses turn activity
    "task_completion_from_activity": (
        "Task: {instruction}\n\n"
        "Activity:\n{turn_activity}\n\n"
        "Write a task board entry (~18 tokens) stating what was accomplished. "
        "Use past tense. NEVER start with 'The user' or 'The agent'. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),

    # Task completion when only the instruction is available (no agent output)
    "task_completion_from_instruction": (
        "Task: {instruction}\n\n"
        "The task was completed but no agent output was captured. "
        "Write a task board entry (~18 tokens) stating what was likely accomplished. "
        "Use past tense. NEVER start with 'The user' or 'The agent'. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),

    # --- Summarisation: instruction ---
    "instruction": (
        "Command: {command_text}\n\n"
        "Write a task board entry (~18 tokens) stating the goal. "
        "Use imperative form (e.g. 'Fix login bug', 'Add dark mode support'). "
        "NEVER start with 'The user' or describe user behavior. "
        "Output ONLY the entry — no preamble, labels, or commentary."
    ),

    # --- Priority scoring ---
    "priority_scoring": (
        "You are prioritising agents working across multiple projects.\n\n"
        "{context_section}\n\n"
        "Agents to score:\n{agents_text}\n\n"
        "Score each agent 0-100 based on priority for user attention.\n"
        "Higher scores = needs attention sooner.\n\n"
        "Scoring factors (in order of importance):\n"
        "1. Objective/waypoint alignment (40%) - How well does the agent's current work align?\n"
        "2. Agent state (25%) - awaiting_input (highest) > processing > idle (lowest)\n"
        "3. Task duration (15%) - Longer running tasks may need attention\n"
        "4. Project context (10%) - Project waypoint priorities\n"
        "5. Recent activity (10%) - Recently active vs stale\n\n"
        'Return ONLY a JSON array: [{{"agent_id": N, "score": N, "reason": "..."}}]'
    ),

    # --- Progress summary ---
    "progress_summary": (
        "You are summarising recent development progress for the project '{project_name}'.\n\n"
        "{analysis_text}\n\n"
        "Write a short and concise progress summary in past tense.\n"
        "Focus on accomplishments, patterns, and themes — not individual commits.\n"
        "Output is a bullet point list of work, each with a short one sentence summary (~18 tokens) of each item.\n"
        "Use a professional tone suitable for a development journal."
    ),

    # --- Headspace: frustration-aware turn summarisation ---
    "turn_frustration": (
        "{instruction_context}"
        "Message: {text}\n\n"
        "1. Write a task board entry (~18 tokens) stating the goal or action. "
        "Use imperative form (e.g. 'Fix login bug', 'Confirmed: proceed with refactor'). "
        "NEVER start with 'The user' or describe user behavior. "
        "If the message references verifying or confirming something, state what specifically.\n"
        "2. Rate the apparent EMOTIONAL frustration level 0-10:\n"
        "   0-3: Calm, patient, constructive\n"
        "   4-5: Mildly frustrated (some exasperation, slight impatience)\n"
        "   6-7: Clearly frustrated (venting, repeated complaints, emotional language)\n"
        "   8-10: Very frustrated (caps, harsh language, threats to abandon, anger)\n\n"
        "IMPORTANT: Distinguish assertiveness from frustration. "
        "Being direct, firm, holding the agent accountable, or clearly stating problems "
        "is NOT frustration — it is assertive communication and should score 0-3. "
        "Only score higher when there are signs of genuine emotional distress, not just directness.\n\n"
        "Consider: tone, punctuation patterns (!!!, ???, CAPS), "
        "repetition of previous requests, explicit frustration signals "
        '("again", "still not working", "why won\'t you"), '
        "and patience indicators (clear instructions, positive framing).\n\n"
        'Return ONLY valid JSON: {{"summary": "...", "frustration_score": N}}'
    ),

    # --- Project metadata: description generation ---
    "project_description": (
        "Below is the CLAUDE.md file from a software project.\n\n"
        "---\n"
        "{claude_md_content}\n"
        "---\n\n"
        "Write a 1-2 sentence project description suitable for a dashboard card. "
        "Focus on what the project does and its primary technology. "
        "Output ONLY the description — no preamble, labels, or commentary."
    ),

    # --- Permission summary ---
    "permission_summary": (
        "Tool: {tool_name}\n"
        "Command: {command}\n"
        "{description_line}"
        "\n"
        "Write a ~10 token summary of what this permission request will do. "
        "Format: '{tool_name}: [concise action]'. "
        "Examples: 'Bash: read HTML from localhost', 'Bash: list files in src/', "
        "'Read: check test config', 'Bash: install npm packages'. "
        "Output ONLY the summary."
    ),

    # --- Classification: completion ---
    "completion_classification": (
        "Classify this agent output. Is the agent:\n"
        "A) FINISHED - delivering a final summary with no remaining work\n"
        "B) CONTINUING - still working, will produce more output\n"
        "C) ASKING - waiting for user input before proceeding\n"
        "D) BLOCKED - encountered an error requiring user intervention\n"
        "\n"
        "Agent output (last 15 lines):\n"
        "{tail}\n"
        "\n"
        "Respond with only the letter."
    ),

    # --- Classification: question ---
    "question_classification": (
        "You are classifying Claude Code agent output. "
        "Determine if the agent is asking the user a question or waiting for input.\n\n"
        "Agent output:\n{content}\n\n"
        "Is the agent asking the user a question or waiting for user input? "
        "Answer only 'yes' or 'no'."
    ),
}


def build_prompt(prompt_type: str, **context) -> str:
    """Build a prompt from the registry.

    Args:
        prompt_type: Key into _PROMPT_TEMPLATES (e.g. "turn_command",
            "task_completion", "priority_scoring").
        **context: Keyword arguments that fill the template placeholders.

    Returns:
        The fully-rendered prompt string.

    Raises:
        KeyError: If *prompt_type* is not in the registry.
    """
    return _PROMPT_TEMPLATES[prompt_type].format(**context)
