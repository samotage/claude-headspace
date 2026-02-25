"""Flask CLI command for extracting agent transcripts.

Provides ``flask transcript show <agent-id>`` to output an agent's full
conversation history as structured markdown. Used by the revival flow
("Seance") so successor agents can recover their predecessor's context.

Also adds ``claude-headspace transcript <agent-id>`` via the argparse
launcher for use outside Flask app context (delegates to flask transcript).
"""

import click
from flask.cli import AppGroup

from ..database import db
from ..models.agent import Agent
from ..models.command import Command, CommandState
from ..models.turn import Turn, TurnActor

transcript_cli = AppGroup("transcript", help="Agent transcript commands.")


@transcript_cli.command("show")
@click.argument("agent_id", type=int)
def show_transcript(agent_id: int) -> None:
    """Output an agent's full conversation history as structured markdown.

    Queries Agent -> Commands (ordered by started_at ASC) -> Turns
    (ordered by timestamp ASC), formatting as markdown with command
    headings and turn entries.
    """
    agent = db.session.get(Agent, agent_id)
    if not agent:
        click.echo(f"Error: Agent #{agent_id} not found", err=True)
        raise SystemExit(1)

    output = format_transcript(agent)
    click.echo(output)


def format_transcript(agent: Agent) -> str:
    """Format an agent's full transcript as structured markdown.

    Args:
        agent: The agent whose transcript to format.

    Returns:
        Markdown-formatted transcript string.
    """
    lines: list[str] = []

    # Header
    lines.append(f"# Transcript for Agent #{agent.id}")
    lines.append("")

    # Agent metadata
    session_uuid_short = str(agent.session_uuid)[:8]
    lines.append(f"- **Session:** {session_uuid_short}")
    if agent.project:
        lines.append(f"- **Project:** {agent.project.name}")
    if agent.persona:
        lines.append(f"- **Persona:** {agent.persona.name}")
    if agent.started_at:
        lines.append(f"- **Started:** {agent.started_at.isoformat()}")
    if agent.ended_at:
        lines.append(f"- **Ended:** {agent.ended_at.isoformat()}")
    lines.append("")

    # Query commands ordered by started_at ASC
    commands = (
        db.session.query(Command)
        .filter(Command.agent_id == agent.id)
        .order_by(Command.started_at.asc())
        .all()
    )

    if not commands:
        lines.append("_No commands found for this agent._")
        return "\n".join(lines)

    for cmd in commands:
        # Command heading
        instruction = cmd.instruction or cmd.full_command or "Untitled command"
        state_label = cmd.state.value
        lines.append(f"## Command: {instruction}")
        lines.append(f"_State: {state_label}_")
        if cmd.started_at:
            lines.append(f"_Started: {cmd.started_at.isoformat()}_")
        if cmd.completed_at:
            lines.append(f"_Completed: {cmd.completed_at.isoformat()}_")
        lines.append("")

        # Query turns ordered by timestamp ASC, filtering empty/null text
        turns = (
            db.session.query(Turn)
            .filter(
                Turn.command_id == cmd.id,
                Turn.text.isnot(None),
                Turn.text != "",
            )
            .order_by(Turn.timestamp.asc())
            .all()
        )

        if not turns:
            lines.append("_No turns recorded for this command._")
            lines.append("")
            continue

        for turn in turns:
            actor_label = "**User:**" if turn.actor == TurnActor.USER else "**Agent:**"
            timestamp = turn.timestamp.isoformat() if turn.timestamp else ""
            lines.append(f"{actor_label} _{timestamp}_")
            lines.append("")
            lines.append(turn.text)
            lines.append("")

        # Completion summary if available
        if cmd.completion_summary:
            lines.append(f"**Completion Summary:** {cmd.completion_summary}")
            lines.append("")

    return "\n".join(lines)
