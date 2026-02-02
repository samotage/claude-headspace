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
    "turn_command": (
        "{instruction_context}"
        "User command: {text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising this command as an instruction. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),
    "turn_question": (
        "{instruction_context}"
        "Agent question: {text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising what the agent is asking. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),
    "turn_completion": (
        "{instruction_context}"
        "Agent completion message: {text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising what the agent accomplished. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),
    "turn_progress": (
        "{instruction_context}"
        "Agent progress update: {text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising the agent's current progress. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),
    "turn_answer": (
        "{instruction_context}"
        "User answer: {text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising what information the user provided. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),
    "turn_end_of_task": (
        "{instruction_context}"
        "Final message: {text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising the final outcome. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),
    "turn_default": (
        "{instruction_context}"
        "Turn: {text}\n"
        "Actor: {actor}\n"
        "Intent: {intent}\n\n"
        "Write a single concise sentence (~18 tokens) summarising the action taken or requested. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),

    # --- Summarisation: task completion ---
    "task_completion": (
        "Original instruction: {instruction}\n"
        "Agent's final message: {final_turn_text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising what was accomplished. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),

    # Task completion when no final agent message available — uses turn activity
    "task_completion_from_activity": (
        "Original instruction: {instruction}\n\n"
        "Activity during this task:\n{turn_activity}\n\n"
        "Write a single concise sentence (~18 tokens) summarising what was accomplished. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
    ),

    # --- Summarisation: instruction ---
    "instruction": (
        "User command: {command_text}\n\n"
        "Write a single concise sentence (~18 tokens) summarising this as an instruction. "
        "Focus on the core task or goal. "
        "Output ONLY the summary sentence — no preamble, labels, or commentary."
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
        "User message: {text}\n\n"
        "1. Summarise this user turn in 1-2 concise sentences (~18 tokens).\n"
        "2. Rate the user's apparent frustration level 0-10:\n"
        "   0-3: Calm, patient, constructive\n"
        "   4-6: Showing some frustration (repetition, mild exasperation)\n"
        "   7-10: Clearly frustrated (caps, punctuation, harsh language, repeated complaints)\n\n"
        "Consider: tone and language intensity, punctuation patterns (!!!, ???, CAPS), "
        "repetition of previous requests, explicit frustration signals "
        '("again", "still not working", "why won\'t you"), '
        "and patience indicators (clear instructions, positive framing).\n\n"
        'Return ONLY valid JSON: {{"summary": "...", "frustration_score": N}}'
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
