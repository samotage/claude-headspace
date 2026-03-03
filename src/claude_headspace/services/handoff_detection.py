"""Handoff detection service.

Scans a persona's handoff directory on agent creation and emits a
``synthetic_turn`` SSE event listing the most recent handoff files.
This gives the operator (not the agent) visibility into prior handoffs
without consuming agent context window.

The service is synchronous and filesystem-only — no database queries,
no background threads.
"""

import logging

from .persona_assets import get_persona_dir

logger = logging.getLogger(__name__)

# Maximum number of recent handoff files to include in the listing
MAX_RECENT_HANDOFFS = 3


class HandoffDetectionService:
    """Detects prior handoff files for a persona and emits SSE events."""

    def __init__(self, app=None):
        self.app = app

    def detect_and_emit(self, agent) -> bool:
        """Scan the persona's handoff directory and emit a synthetic_turn event.

        Called after a new agent is created and assigned a persona. Scans
        ``data/personas/{slug}/handoffs/`` for ``.md`` files, sorts by
        filename (reverse chronological), selects the top 3, and emits
        a ``synthetic_turn`` SSE event for the dashboard.

        Args:
            agent: An Agent model instance. Must have ``persona`` loaded.

        Returns:
            True if a synthetic_turn event was emitted, False otherwise.
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

        filenames = [f.name for f in recent]
        file_paths = [str(f.resolve()) for f in recent]

        # Emit synthetic_turn SSE event
        try:
            from .broadcaster import get_broadcaster

            get_broadcaster().broadcast(
                "synthetic_turn",
                {
                    "agent_id": agent.id,
                    "persona_slug": slug,
                    "turns": [
                        {
                            "type": "handoff_listing",
                            "filenames": filenames,
                            "file_paths": file_paths,
                        }
                    ],
                },
            )
            logger.info(
                f"handoff_detection: emitted synthetic_turn — "
                f"agent_id={agent.id}, persona={slug}, "
                f"files={len(recent)}"
            )
            return True
        except Exception as e:
            logger.warning(f"handoff_detection: broadcast failed — {e}")
            return False
