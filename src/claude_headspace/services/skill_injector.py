"""Persona skill file injection service.

Reads persona skill and experience content from disk and delivers it
as a priming message to the agent's tmux pane via the tmux bridge.
"""

import logging
import threading
import time

from ..services.persona_assets import read_experience_file, read_skill_file
from ..services.tmux_bridge import HealthCheckLevel, check_health, send_text

logger = logging.getLogger(__name__)

# In-memory dict of agent_id -> injection timestamp.
# Uses a cooldown period instead of permanent idempotency so that
# session_end clearing the record (which caused re-injection storms)
# is no longer needed.  Thread-safe via _injected_lock.
_injected_agents: dict[int, float] = {}
_injected_lock = threading.Lock()
_INJECTION_COOLDOWN_SECONDS = 300.0  # 5 minutes


def _compose_priming_message(
    persona_name: str,
    skill_content: str,
    experience_content: str | None = None,
) -> str:
    """Compose the priming message from skill and experience content."""
    parts = [
        f"You are {persona_name}. Read the following skill and experience "
        "content carefully. Absorb this identity and respond in character "
        "with a brief greeting confirming who you are and what you do.",
        "",
        "## Skills",
        "",
        skill_content.strip(),
    ]
    if experience_content:
        parts.extend([
            "",
            "## Experience",
            "",
            experience_content.strip(),
        ])
    return "\n".join(parts)


def inject_persona_skills(agent) -> bool:
    """Inject persona skill and experience content into an agent's tmux pane.

    Args:
        agent: Agent record with persona_id, tmux_pane_id, and persona
               relationship attributes.

    Returns:
        True if injection was performed, False if skipped or failed.
    """
    agent_id = agent.id

    # Skip agents without a persona
    if not getattr(agent, "persona_id", None):
        return False

    # Skip agents without a tmux pane
    if not getattr(agent, "tmux_pane_id", None):
        logger.debug(
            f"skill_injection: skipped — agent_id={agent_id}, no tmux_pane_id"
        )
        return False

    # Cooldown check: skip if injected within the cooldown period
    with _injected_lock:
        last_injected = _injected_agents.get(agent_id)
        if last_injected is not None:
            elapsed = time.time() - last_injected
            if elapsed < _INJECTION_COOLDOWN_SECONDS:
                logger.debug(
                    f"skill_injection: skipped — agent_id={agent_id}, "
                    f"injected {elapsed:.0f}s ago (cooldown={_INJECTION_COOLDOWN_SECONDS}s)"
                )
                return False

    # Load persona slug
    persona = getattr(agent, "persona", None)
    if persona is None:
        # Relationship not loaded — query directly
        from ..models.persona import Persona

        persona = Persona.query.get(agent.persona_id)
    if persona is None:
        logger.warning(
            f"skill_injection: skipped — agent_id={agent_id}, "
            f"persona_id={agent.persona_id} not found in DB"
        )
        return False

    slug = persona.slug
    persona_name = persona.name

    # Read skill file (required)
    skill_content = read_skill_file(slug)
    if skill_content is None:
        logger.warning(
            f"skill_injection: skipped — agent_id={agent_id}, "
            f"slug={slug}, skill.md not found on disk"
        )
        return False

    # Read experience file (optional)
    experience_content = read_experience_file(slug)
    if experience_content is None:
        logger.debug(
            f"skill_injection: experience.md not found for slug={slug}, "
            f"proceeding with skill.md only"
        )

    # Health check
    health = check_health(agent.tmux_pane_id, level=HealthCheckLevel.COMMAND)
    if not health.available:
        logger.warning(
            f"skill_injection: skipped — agent_id={agent_id}, slug={slug}, "
            f"tmux pane {agent.tmux_pane_id} unhealthy: {health.error_message}"
        )
        return False

    # Compose and send
    message = _compose_priming_message(persona_name, skill_content, experience_content)
    result = send_text(agent.tmux_pane_id, message)

    if not result.success:
        logger.error(
            f"skill_injection: failed — agent_id={agent_id}, slug={slug}, "
            f"send_text error: {result.error_message}"
        )
        return False

    # Record injection with timestamp
    with _injected_lock:
        _injected_agents[agent_id] = time.time()

    logger.info(
        f"skill_injection: success — agent_id={agent_id}, slug={slug}, "
        f"persona_name={persona_name}"
    )
    return True


def clear_injection_record(agent_id: int) -> None:
    """No-op: cooldown handles expiry naturally.

    Previously this cleared the idempotency flag on session_end, which
    caused re-injection storms when session_end/session_start collided.
    The cooldown-based approach makes this unnecessary — the injection
    record expires automatically after _INJECTION_COOLDOWN_SECONDS.
    """
    # Intentionally a no-op. The cooldown timer handles expiry.


def reset_injection_state() -> None:
    """Clear all injection records (for testing)."""
    global _injected_agents
    with _injected_lock:
        _injected_agents.clear()
