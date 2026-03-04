"""Handoff detection service.

Scans a persona's handoff directory on agent creation and persists
recent handoff file paths as Turn records in the database.  Each file
becomes one AGENT/PROGRESS turn whose text is the full resolved path.

Because turns are persisted, they render through the normal turn
pipeline on both the dashboard and voice chat pages and survive
re-renders, reconnects, and page reloads.
"""

import logging
from datetime import datetime, timezone

from ..database import db
from .persona_assets import get_persona_dir

logger = logging.getLogger(__name__)

# Maximum number of recent handoff files to include
MAX_RECENT_HANDOFFS = 3


class HandoffDetectionService:
    """Detects prior handoff files for a persona and creates Turn records."""

    def __init__(self, app=None):
        self.app = app

    def detect_and_emit(self, agent) -> bool:
        """Scan the persona's handoff directory and create Turn records.

        Called after a new agent is created and assigned a persona.  Scans
        ``data/personas/{slug}/handoffs/`` for ``.md`` files, sorts by
        filename (reverse chronological), selects the top 3, and creates
        one AGENT/PROGRESS Turn per file with the full resolved path as text.

        A ``turn_created`` SSE event is broadcast for each turn so both
        dashboard and voice chat pick them up in real time.

        Args:
            agent: An Agent model instance.  Must have ``persona`` loaded.

        Returns:
            True if turns were created, False otherwise.
        """
        if not agent or not agent.persona:
            return False

        slug = agent.persona.slug

        # Resolve handoff directory via persona_assets (single source of truth)
        handoff_dir = get_persona_dir(slug) / "handoffs"

        if not handoff_dir.is_dir():
            logger.debug(
                f"handoff_detection: no handoff dir for persona {slug}: {handoff_dir}"
            )
            return False

        # Collect .md files
        md_files = sorted(
            (f for f in handoff_dir.iterdir() if f.suffix == ".md" and f.is_file()),
            key=lambda f: f.name,
            reverse=True,
        )

        if not md_files:
            logger.debug(f"handoff_detection: empty handoff dir for persona {slug}")
            return False

        # Take the most recent N files
        recent = md_files[:MAX_RECENT_HANDOFFS]

        # Need a command to attach turns to
        current_command = agent.get_current_command()
        if not current_command:
            # Create a bootstrap command so we have somewhere to hang the turns
            from ..models.command import Command, CommandState

            current_command = Command(
                agent_id=agent.id,
                state=CommandState.IDLE,
                instruction="[session start]",
                started_at=datetime.now(timezone.utc),
            )
            db.session.add(current_command)
            db.session.flush()

        # Create one Turn per handoff file
        from ..models.turn import Turn, TurnActor, TurnIntent

        created_turns = []
        for f in recent:
            full_path = str(f.resolve())
            turn = Turn(
                command_id=current_command.id,
                actor=TurnActor.AGENT,
                intent=TurnIntent.PROGRESS,
                text=full_path,
                timestamp_source="server",
            )
            db.session.add(turn)
            created_turns.append((turn, full_path))

        db.session.commit()

        # Broadcast turn_created SSE for each turn
        try:
            from .broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            for turn, text in created_turns:
                broadcaster.broadcast(
                    "turn_created",
                    {
                        "agent_id": agent.id,
                        "project_id": agent.project_id,
                        "text": text,
                        "actor": "agent",
                        "intent": "progress",
                        "command_id": current_command.id,
                        "command_instruction": current_command.instruction,
                        "turn_id": turn.id,
                        "timestamp": turn.timestamp.isoformat(),
                    },
                )
        except Exception as e:
            logger.warning(f"handoff_detection: broadcast failed — {e}")

        logger.info(
            f"handoff_detection: created {len(created_turns)} turns — "
            f"agent_id={agent.id}, persona={slug}"
        )
        return True
