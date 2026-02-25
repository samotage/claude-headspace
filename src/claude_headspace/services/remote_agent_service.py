"""Remote agent service for external application integration.

Provides blocking agent creation with readiness polling, liveness checks,
and shutdown orchestration. This service wraps the existing agent_lifecycle
module with blocking semantics suitable for synchronous API consumers.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from flask import current_app

from ..database import db
from ..models.agent import Agent
from ..models.project import Project
from .agent_lifecycle import create_agent, shutdown_agent
from .session_token import SessionTokenService

logger = logging.getLogger(__name__)

# Default timeout for agent readiness polling (seconds)
DEFAULT_CREATION_TIMEOUT = 15

# Polling interval while waiting for agent readiness (seconds)
_POLL_INTERVAL = 0.5


@dataclass
class RemoteAgentResult:
    """Result of remote agent creation."""

    success: bool
    agent_id: Optional[int] = None
    embed_url: Optional[str] = None
    session_token: Optional[str] = None
    project_slug: Optional[str] = None
    persona_slug: Optional[str] = None
    tmux_session_name: Optional[str] = None
    status: str = "error"
    error_code: Optional[str] = None
    error_message: Optional[str] = None


class RemoteAgentService:
    """Service for managing remote agent lifecycle.

    Registered in app.extensions["remote_agent_service"].
    """

    def __init__(self, app=None, session_token_service: SessionTokenService | None = None):
        self._app = app
        self._session_token_service = session_token_service

    @property
    def _config(self) -> dict:
        """Get remote_agents config section."""
        app = self._app or current_app._get_current_object()
        config = app.config.get("APP_CONFIG", {})
        return config.get("remote_agents", {})

    @property
    def creation_timeout(self) -> int:
        """Get the configured creation timeout in seconds."""
        return self._config.get("creation_timeout_seconds", DEFAULT_CREATION_TIMEOUT)

    def _get_token_service(self) -> SessionTokenService:
        """Get the session token service."""
        if self._session_token_service:
            return self._session_token_service
        app = self._app or current_app._get_current_object()
        return app.extensions["session_token_service"]

    def create_blocking(
        self,
        project_slug: str,
        persona_slug: str,
        initial_prompt: str,
        feature_flags: dict | None = None,
    ) -> RemoteAgentResult:
        """Create an agent and block until it is fully ready.

        Flow:
        1. Resolve project by slug
        2. Call create_agent() (fire-and-forget tmux session)
        3. Poll DB for agent readiness (agent registered + persona skill injected)
        4. Send initial prompt via tmux bridge
        5. Generate session token
        6. Return complete result

        Args:
            project_slug: Slug of the project (e.g. "may-belle").
            persona_slug: Slug of the persona to use.
            initial_prompt: Text to send as the first user prompt.
            feature_flags: Optional feature flags for the embed view.

        Returns:
            RemoteAgentResult with all creation details or error info.
        """
        # 1. Resolve project by slug
        project = (
            db.session.query(Project)
            .filter(Project.slug == project_slug)
            .first()
        )
        if not project:
            return RemoteAgentResult(
                success=False,
                error_code="project_not_found",
                error_message=f"Project '{project_slug}' not found",
            )

        # 2. Call create_agent (fire-and-forget)
        create_result = create_agent(project.id, persona_slug=persona_slug)
        if not create_result.success:
            # Determine error code from message
            error_code = "server_error"
            if "not found or not active" in (create_result.message or ""):
                error_code = "persona_not_found"
            return RemoteAgentResult(
                success=False,
                error_code=error_code,
                error_message=create_result.message,
            )

        tmux_session_name = create_result.tmux_session_name
        logger.info(
            f"Remote agent creation started: tmux_session={tmux_session_name}, "
            f"project={project_slug}, persona={persona_slug}"
        )

        # 3. Poll for agent readiness
        timeout = self.creation_timeout
        start = time.time()
        agent = None

        while time.time() - start < timeout:
            time.sleep(_POLL_INTERVAL)

            # Look for an agent with matching tmux_session
            agent = (
                db.session.query(Agent)
                .filter(
                    Agent.tmux_session == tmux_session_name,
                    Agent.ended_at.is_(None),
                )
                .first()
            )

            if agent is None:
                # Agent not yet registered in DB by hooks
                continue

            # Check if persona skill has been injected
            if agent.prompt_injected_at is not None:
                logger.info(
                    f"Remote agent ready: agent_id={agent.id}, "
                    f"tmux_session={tmux_session_name}, "
                    f"elapsed={time.time() - start:.1f}s"
                )
                break
        else:
            # Timeout
            elapsed = time.time() - start
            logger.warning(
                f"Remote agent creation timeout: tmux_session={tmux_session_name}, "
                f"elapsed={elapsed:.1f}s, agent_found={agent is not None}"
            )
            return RemoteAgentResult(
                success=False,
                tmux_session_name=tmux_session_name,
                error_code="agent_creation_timeout",
                error_message=f"Agent did not become ready within {timeout} seconds",
            )

        # 4. Send initial prompt via tmux bridge
        from . import tmux_bridge

        app = self._app or current_app._get_current_object()
        config = app.config.get("APP_CONFIG", {})
        bridge_config = config.get("tmux_bridge", {})
        subprocess_timeout = bridge_config.get("subprocess_timeout", 5)
        text_enter_delay_ms = bridge_config.get("text_enter_delay_ms", 120)

        send_result = tmux_bridge.send_text(
            pane_id=agent.tmux_pane_id,
            text=initial_prompt,
            timeout=subprocess_timeout,
            text_enter_delay_ms=text_enter_delay_ms,
            verify_enter=True,
        )

        if not send_result.success:
            logger.warning(
                f"Remote agent initial prompt delivery failed: agent_id={agent.id}, "
                f"error={send_result.error_message}"
            )
            # Agent is created but prompt failed — still return success
            # with a note. The calling app can retry via the embed view.

        # 5. Generate session token
        token_service = self._get_token_service()
        session_token = token_service.generate(
            agent_id=agent.id,
            feature_flags=feature_flags or {},
        )

        # 6. Build embed URL
        application_url = config.get("server", {}).get(
            "application_url", "https://localhost:5055"
        )
        embed_url = f"{application_url}/embed/{agent.id}?token={session_token}"

        return RemoteAgentResult(
            success=True,
            agent_id=agent.id,
            embed_url=embed_url,
            session_token=session_token,
            project_slug=project.slug,
            persona_slug=persona_slug,
            tmux_session_name=tmux_session_name,
            status="ready",
        )

    def check_alive(self, agent_id: int) -> dict:
        """Check if an agent is alive.

        Args:
            agent_id: ID of the agent to check.

        Returns:
            Dict with alive status and agent state info.
        """
        agent = db.session.get(Agent, agent_id)
        if not agent:
            return {"alive": False, "reason": "agent_not_found"}

        if agent.ended_at is not None:
            return {"alive": False, "reason": "agent_ended"}

        # Check current state
        current_command = agent.get_current_command()
        state = current_command.state.value if current_command else "idle"

        return {
            "alive": True,
            "agent_id": agent.id,
            "state": state,
            "project_slug": agent.project.slug if agent.project else None,
        }

    def shutdown(self, agent_id: int) -> dict:
        """Initiate graceful agent shutdown (non-blocking).

        Checks agent state synchronously, revokes tokens, then fires the
        actual tmux shutdown asynchronously so the HTTP response returns
        immediately.

        Args:
            agent_id: ID of the agent to shut down.

        Returns:
            Dict with ``result`` key: ``"initiated"``, ``"already_terminated"``,
            or ``"not_found"``.
        """
        agent = db.session.get(Agent, agent_id)

        if not agent:
            return {"result": "not_found", "agent_id": agent_id}

        if agent.ended_at is not None:
            return {"result": "already_terminated", "agent_id": agent_id}

        # Revoke tokens synchronously (fast, in-memory)
        token_service = self._get_token_service()
        token_service.revoke_for_agent(agent_id)

        # Fire the actual tmux shutdown asynchronously so the caller
        # gets an immediate response (S5 FR3: non-blocking).
        app = self._app or current_app._get_current_object()
        threading.Thread(
            target=self._async_shutdown,
            args=(app, agent_id),
            daemon=True,
            name=f"shutdown-agent-{agent_id}",
        ).start()

        return {"result": "initiated", "agent_id": agent_id}

    @staticmethod
    def _async_shutdown(app, agent_id: int):
        """Run shutdown_agent inside an app context on a background thread."""
        with app.app_context():
            result = shutdown_agent(agent_id)
            if not result.success:
                logger.warning(
                    f"Async shutdown of agent {agent_id} failed: {result.message}"
                )
