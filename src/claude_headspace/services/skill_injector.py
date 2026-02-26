"""Persona skill file injection service.

Reads persona skill and experience content from disk and delivers it
as a priming message to the agent's tmux pane via the tmux bridge.

Idempotency is enforced via the agent.prompt_injected_at DB column —
once set, re-injection is blocked for the lifetime of the agent record.
This survives server restarts and eliminates the session lifecycle
collision that previously caused re-injection storms.

Guardrail injection is FAIL-CLOSED for remote agents: if the platform
guardrails file is missing, empty, or unreadable, injection fails and
the agent is not primed. Failures are reported to otageMon via
ExceptionReporter.
"""

import logging
from datetime import datetime, timezone

from ..services.persona_assets import (
    GuardrailValidationError,
    read_experience_file,
    read_skill_file,
    validate_guardrails_content,
)
from ..services.tmux_bridge import HealthCheckLevel, check_health, send_text

logger = logging.getLogger(__name__)


def _report_guardrail_failure(agent_id: int, reason: str) -> None:
    """Report a guardrail injection failure to otageMon via ExceptionReporter.

    Best-effort: silently drops if ExceptionReporter is not configured.
    """
    try:
        from flask import current_app
        reporter = current_app.extensions.get("exception_reporter")
        if reporter and reporter.is_configured:
            exc = GuardrailValidationError(reason)
            reporter.report(
                exc=exc,
                source="guardrail_injection",
                severity="error",
                context={"agent_id": agent_id, "reason": reason},
            )
    except (ImportError, RuntimeError):
        pass  # Outside Flask context — cannot report


def _compose_priming_message(
    persona_name: str,
    skill_content: str,
    experience_content: str | None = None,
    guardrails_content: str | None = None,
) -> str:
    """Compose the priming message from guardrails, skill, and experience content.

    Guardrails are prepended BEFORE persona content so they take
    precedence — the guardrails document itself states it overrides
    all other instructions.
    """
    parts = []

    if guardrails_content:
        parts.extend([
            "## Platform Guardrails",
            "",
            guardrails_content.strip(),
            "",
        ])

    parts.extend([
        f"You are {persona_name}. Read the following skill and experience "
        "content carefully. Absorb this identity and respond in character "
        "with a brief greeting confirming who you are and what you do.",
        "",
        "## Skills",
        "",
        skill_content.strip(),
    ])
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

    Idempotency is enforced by the agent.prompt_injected_at column.
    Once set, this function returns False immediately — no in-memory
    state, no cooldown timers, no race conditions.

    Args:
        agent: Agent record with persona_id, tmux_pane_id, persona
               relationship, and prompt_injected_at attributes.

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

    # DB-level idempotency: skip if already injected
    if getattr(agent, "prompt_injected_at", None) is not None:
        logger.debug(
            f"skill_injection: skipped — agent_id={agent_id}, "
            f"already injected at {agent.prompt_injected_at}"
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

    # Read platform guardrails — FAIL-CLOSED for remote agents.
    # For remote agents (created via RemoteAgentService), missing or empty
    # guardrails is a hard failure. For local/dashboard agents, it remains
    # a warning to avoid breaking the operator's local workflow.
    is_remote_agent = getattr(agent, "_is_remote_agent", False)
    guardrails_content = None
    guardrails_hash = None
    try:
        guardrails_content, guardrails_hash = validate_guardrails_content()
    except GuardrailValidationError as e:
        reason = str(e)
        if is_remote_agent:
            logger.error(
                f"skill_injection: FAILED (fail-closed) — agent_id={agent_id}, "
                f"guardrails validation error: {reason}"
            )
            _report_guardrail_failure(agent_id, reason)
            return False
        else:
            logger.warning(
                f"skill_injection: platform-guardrails.md not available — "
                f"agent_id={agent_id} will operate WITHOUT platform guardrails "
                f"({reason})"
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
    message = _compose_priming_message(
        persona_name, skill_content, experience_content, guardrails_content
    )
    result = send_text(agent.tmux_pane_id, message)

    if not result.success:
        error_msg = result.error_message or "unknown tmux error"
        logger.error(
            f"skill_injection: failed — agent_id={agent_id}, slug={slug}, "
            f"send_text error: {error_msg}"
        )
        if is_remote_agent:
            _report_guardrail_failure(
                agent_id,
                f"tmux send failure during guardrail delivery: {error_msg}",
            )
        return False

    # Record injection in DB — this is the source of truth for idempotency.
    # The caller (process_session_start) commits this along with other
    # session_start changes.
    agent.prompt_injected_at = datetime.now(timezone.utc)

    # Store guardrails version hash for staleness detection.
    if guardrails_hash:
        agent.guardrails_version_hash = guardrails_hash

    logger.info(
        f"skill_injection: success — agent_id={agent_id}, slug={slug}, "
        f"persona_name={persona_name}, guardrails_hash={guardrails_hash or 'none'}"
    )
    return True


def clear_injection_record(agent_id: int) -> None:
    """No-op: prompt_injected_at on the agent record handles idempotency.

    This function exists for backwards compatibility with callers in
    process_session_end. The DB column is never cleared — once injected,
    the agent record permanently records the fact.
    """


def reset_injection_state() -> None:
    """No-op: injection state is now in the DB, not in memory.

    Tests that need to reset injection state should set
    agent.prompt_injected_at = None on their mock/fixture directly.
    """
