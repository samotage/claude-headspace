"""Centralised registry of all LLM prompt templates.

Every inference prompt in the codebase lives here so that prompt tuning
is a single-file activity.  Services call ``build_prompt(prompt_type, **ctx)``
instead of assembling strings inline.
"""

_PROMPT_TEMPLATES: dict[str, str] = {
    # --- Summarisation: turn prompts (per-intent) ---
    "turn_command": (
        "Summarise a very short and concise sentence around 18 tokens long the following command as an instruction:\n\n"
        "{instruction_context}"
        "User command: {text}"
    ),
    "turn_question": (
        "Summarise what the agent is asking the user in 1-2 concise sentences.\n\n"
        "{instruction_context}"
        "Agent question: {text}"
    ),
    "turn_completion": (
        "Summarise what the agent accomplished in 1-2 concise sentences.\n\n"
        "{instruction_context}"
        "Agent completion message: {text}"
    ),
    "turn_progress": (
        "Summarise what progress the agent has made in 1-2 concise sentences.\n\n"
        "{instruction_context}"
        "Agent progress update: {text}"
    ),
    "turn_answer": (
        "Summarise what information the user provided in 1-2 concise sentences.\n\n"
        "{instruction_context}"
        "User answer: {text}"
    ),
    "turn_end_of_task": (
        "Summarise the final outcome of this task in 1-2 concise sentences.\n\n"
        "{instruction_context}"
        "Final message: {text}"
    ),
    "turn_default": (
        "Summarise this turn in 1-2 concise sentences focusing on "
        "what action was taken or requested.\n\n"
        "{instruction_context}"
        "Turn: {text}\n"
        "Actor: {actor}\n"
        "Intent: {intent}"
    ),

    # --- Summarisation: task completion ---
    "task_completion": (
        "Summarise what was accomplished in this completed task in 2-3 sentences. "
        "Describe the outcome relative to what was originally asked.\n\n"
        "Original instruction: {instruction}\n"
        "Agent's final message: {final_turn_text}"
    ),

    # Task completion when no final agent message available — uses turn activity
    "task_completion_from_activity": (
        "Summarise what was accomplished in this completed task in 2-3 sentences. "
        "Describe the outcome relative to what was originally asked.\n\n"
        "Original instruction: {instruction}\n\n"
        "Activity during this task:\n{turn_activity}"
    ),

    # --- Summarisation: instruction ---
    "instruction": (
        "Summarise a very short and concise sentence around 18 tokens long the following command as in instruction:\n\n"
        "Focus on the core task or goal.\n\n"
        "User command: {command_text}"
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
        "Write a 3-5 paragraph narrative progress summary in past tense.\n"
        "Focus on accomplishments, patterns, and themes — not individual commits.\n"
        "Group related work into coherent paragraphs.\n"
        "Use a professional tone suitable for a development journal."
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
