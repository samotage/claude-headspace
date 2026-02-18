"""Voice output formatting service for voice bridge API responses."""

import logging

logger = logging.getLogger(__name__)


class VoiceFormatter:
    """Formats API responses for voice consumption.

    Applies a voice-friendly structure: status_line + results + next_action.
    Supports three verbosity levels: concise, normal, detailed.
    """

    def __init__(self, config: dict, inference_service=None):
        vb_config = config.get("voice_bridge", {})
        self.default_verbosity = vb_config.get("default_verbosity", "concise")
        self.inference_service = inference_service

    def format_sessions(self, agents: list[dict], verbosity: str | None = None) -> dict:
        """Format active agent list for voice consumption.

        Args:
            agents: List of agent dicts with keys: name, project, state,
                    awaiting_input, summary, last_activity_ago
            verbosity: concise, normal, or detailed
        """
        v = verbosity or self.default_verbosity
        if not agents:
            return {
                "status_line": "No agents are currently running.",
                "results": [],
                "next_action": "none",
            }

        awaiting = [a for a in agents if a.get("awaiting_input")]
        total = len(agents)

        if awaiting:
            status = (
                f"You have {total} agent{'s' if total != 1 else ''} running. "
                f"{len(awaiting)} need{'s' if len(awaiting) == 1 else ''} your input."
            )
        else:
            status = f"You have {total} agent{'s' if total != 1 else ''} running. None need input."

        results = []
        for a in agents:
            line = f"{a.get('project', 'unknown')}: {a.get('state', 'unknown')}"
            if a.get("summary"):
                line += f" — {a['summary']}"
            if v != "concise" and a.get("last_activity_ago"):
                line += f" ({a['last_activity_ago']})"
            results.append(line)

        next_action = "none"
        if awaiting:
            names = [a.get("project", "unknown") for a in awaiting]
            next_action = f"Respond to {', '.join(names)}."

        return {
            "status_line": status,
            "results": results,
            "next_action": next_action,
        }

    def format_command_result(self, agent_name: str, success: bool, error: str | None = None) -> dict:
        """Format voice command result."""
        if success:
            return {
                "status_line": f"Command sent to {agent_name}. Agent is now processing.",
                "results": [],
                "next_action": "none",
            }
        return {
            "status_line": f"Could not send command to {agent_name}.",
            "results": [error or "Unknown error"],
            "next_action": "Check the agent status and try again.",
        }

    def format_question(self, agent_data: dict) -> dict:
        """Format question detail for voice consumption.

        Args:
            agent_data: Dict with keys: project, question_text, question_options,
                       question_source_type
        """
        project = agent_data.get("project", "unknown")
        q_text = agent_data.get("question_text", "No question text available.")
        q_type = agent_data.get("question_source_type", "unknown")
        options = agent_data.get("question_options")

        results = [f"Question: {q_text}"]

        if options and isinstance(options, list):
            for i, opt in enumerate(options, 1):
                label = opt.get("label", f"Option {i}")
                desc = opt.get("description", "")
                line = f"{i}. {label}"
                if desc:
                    line += f" — {desc}"
                results.append(line)

        next_action = "Speak your answer or select an option number."
        if q_type == "free_text":
            next_action = "Speak your answer."

        return {
            "status_line": f"{project} is asking a question.",
            "results": results,
            "next_action": next_action,
        }

    def format_output(self, agent_name: str, commands: list[dict], verbosity: str | None = None) -> dict:
        """Format recent agent output for voice consumption.

        Args:
            agent_name: Agent display name
            commands: List of command dicts with keys: instruction, completion_summary,
                      full_command, full_output, state
            verbosity: concise, normal, or detailed
        """
        v = verbosity or self.default_verbosity
        if not commands:
            return {
                "status_line": f"No recent activity for {agent_name}.",
                "results": [],
                "next_action": "none",
            }

        results = []
        for cmd in commands:
            if v == "concise":
                summary = cmd.get("completion_summary") or cmd.get("instruction") or "Command completed"
                results.append(summary)
            elif v == "normal":
                instr = cmd.get("instruction") or "Unknown command"
                summary = cmd.get("completion_summary") or "Completed"
                results.append(f"{instr}: {summary}")
            else:  # detailed
                instr = cmd.get("instruction") or "Unknown command"
                results.append(f"Command: {instr}")
                if cmd.get("full_command"):
                    results.append(f"Full command: {cmd['full_command'][:200]}")
                if cmd.get("full_output"):
                    results.append(f"Output: {cmd['full_output'][:500]}")

        return {
            "status_line": f"Recent activity for {agent_name}: {len(commands)} command{'s' if len(commands) != 1 else ''}.",
            "results": results,
            "next_action": "none",
        }

    def format_error(self, error_type: str, suggestion: str) -> dict:
        """Format error response for voice consumption."""
        return {
            "status_line": error_type,
            "results": [],
            "next_action": suggestion,
        }
