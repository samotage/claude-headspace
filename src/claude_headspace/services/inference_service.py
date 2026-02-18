"""Inference service orchestrating model selection, caching, rate limiting, and logging."""

import logging
import time
from datetime import datetime, timezone

from ..models.inference_call import InferenceCall, InferenceLevel
from .inference_cache import InferenceCache
from .inference_rate_limiter import InferenceRateLimiter, RateLimitResult
from .openrouter_client import InferenceResult, OpenRouterClient, OpenRouterClientError

logger = logging.getLogger(__name__)


class InferenceServiceError(Exception):
    """Error from the inference service."""

    def __init__(self, message: str, rate_limited: bool = False, retry_after: float = 0.0):
        super().__init__(message)
        self.rate_limited = rate_limited
        self.retry_after = retry_after


class InferenceService:
    """Orchestrates inference calls with caching, rate limiting, and logging."""

    def __init__(self, config: dict, db_session_factory=None, database_url: str | None = None):
        """Initialize the inference service.

        Args:
            config: Application configuration dictionary
            db_session_factory: Callable that returns a database session (for logging, backward compat)
            database_url: Database URL for independent logging session (preferred over db_session_factory)
        """
        self.config = config
        self._log_session_factory = None
        self._independent_engine = None

        if database_url:
            self._init_independent_engine(database_url)
        elif db_session_factory:
            self._log_session_factory = db_session_factory

        self.client = OpenRouterClient(config)
        self.cache = InferenceCache(config)
        self.rate_limiter = InferenceRateLimiter(config)

        or_config = config.get("openrouter", {})
        self.models = or_config.get("models", {})
        self.pricing = or_config.get("pricing", {})

    def _init_independent_engine(self, database_url: str) -> None:
        """Create an independent engine and sessionmaker for logging.

        This ensures InferenceCall records are committed in their own
        transaction, isolated from the caller's session lifecycle.
        """
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        self._independent_engine = create_engine(
            database_url,
            pool_size=1,
            max_overflow=2,
            pool_pre_ping=True,
        )
        self._log_session_factory = sessionmaker(bind=self._independent_engine)

    def stop(self) -> None:
        """Dispose of the independent database engine, releasing connections."""
        if self._independent_engine:
            self._independent_engine.dispose()
            logger.info("Inference service: independent engine disposed")

    @property
    def is_available(self) -> bool:
        """Check if the service is operational (API key configured)."""
        return self.client.is_configured

    def get_model_for_level(self, level: str) -> str:
        """Get the configured model for a given inference level."""
        model = self.models.get(level)
        if not model:
            raise InferenceServiceError(f"No model configured for level '{level}'")
        return model

    def _calculate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated cost based on token counts and pricing config."""
        model_pricing = self.pricing.get(model, {})
        input_rate = model_pricing.get("input_per_million", 0)
        output_rate = model_pricing.get("output_per_million", 0)
        return (input_tokens * input_rate / 1_000_000) + (output_tokens * output_rate / 1_000_000)

    def _log_call(
        self,
        level: str,
        purpose: str,
        model: str,
        input_hash: str | None,
        result: InferenceResult | None,
        error_message: str | None = None,
        cached: bool = False,
        input_text: str | None = None,
        project_id: int | None = None,
        agent_id: int | None = None,
        command_id: int | None = None,
        turn_id: int | None = None,
    ) -> None:
        """Log an inference call to the database.

        When using an independent engine (production), the session is fully
        isolated from the caller's transaction — commit/rollback here cannot
        affect the caller's session.
        """
        if not self._log_session_factory:
            return

        session = None
        try:
            session = self._log_session_factory()
            cost = None
            if result and result.input_tokens and result.output_tokens:
                cost = self._calculate_cost(model, result.input_tokens, result.output_tokens)

            now = datetime.now(timezone.utc)
            record = InferenceCall(
                timestamp=now,
                level=level,
                purpose=purpose,
                model=model,
                input_tokens=result.input_tokens if result else None,
                output_tokens=result.output_tokens if result else None,
                input_hash=input_hash,
                input_text=input_text,
                result_text=result.text if result else None,
                latency_ms=result.latency_ms if result else None,
                cost=cost,
                error_message=error_message,
                cached=cached,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command_id,
                turn_id=turn_id,
            )
            session.add(record)
            session.commit()

            # Resolve display fields from related tables using the live session
            agent_session = None
            if record.agent_id:
                from ..models.agent import Agent
                agent_row = session.query(Agent.session_uuid).filter(
                    Agent.id == record.agent_id
                ).first()
                if agent_row:
                    agent_session = str(agent_row.session_uuid)

            project_name = None
            if record.project_id:
                from ..models.project import Project
                project_row = session.query(Project.name).filter(
                    Project.id == record.project_id
                ).first()
                if project_row:
                    project_name = project_row.name

            self._broadcast_inference_call({
                "id": record.id,
                "timestamp": record.timestamp.isoformat() if record.timestamp else None,
                "level": record.level,
                "purpose": record.purpose,
                "model": record.model,
                "input_tokens": record.input_tokens,
                "output_tokens": record.output_tokens,
                "latency_ms": record.latency_ms,
                "cost": record.cost,
                "error_message": record.error_message,
                "cached": record.cached,
                "project_id": record.project_id,
                "project_name": project_name,
                "agent_id": record.agent_id,
                "agent_session": agent_session,
                "input_text": record.input_text,
                "result_text": record.result_text,
            })
        except Exception as e:
            logger.error(f"Failed to log inference call: {e}")
        finally:
            if session:
                session.close()

    def _broadcast_inference_call(self, payload: dict) -> None:
        """Broadcast an inference call event via SSE."""
        try:
            from .broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            broadcaster.broadcast("inference_call", payload)
        except Exception as e:
            logger.debug(f"Failed to broadcast inference call (non-fatal): {e}")

    def infer(
        self,
        level: str,
        purpose: str,
        input_text: str,
        project_id: int | None = None,
        agent_id: int | None = None,
        command_id: int | None = None,
        turn_id: int | None = None,
    ) -> InferenceResult:
        """Make an inference call.

        Args:
            level: Inference level (turn, command, project, objective)
            purpose: Free-text description of the inference purpose
            input_text: The input text to send to the LLM
            project_id: Optional project FK
            agent_id: Optional agent FK
            command_id: Optional command FK
            turn_id: Optional turn FK

        Returns:
            InferenceResult with the response

        Raises:
            InferenceServiceError: On rate limit or service unavailability
            OpenRouterClientError: On API errors after retry exhaustion
        """
        if not self.is_available:
            raise InferenceServiceError("Inference service not available: API key not configured")

        model = self.get_model_for_level(level)
        input_hash = OpenRouterClient.compute_input_hash(input_text)

        logger.debug(
            f"Inference request: level={level}, purpose={purpose}, model={model}, "
            f"input_len={len(input_text)}"
        )

        # Check cache
        cached_entry = self.cache.get(input_hash)
        if cached_entry:
            result = InferenceResult(
                text=cached_entry.result_text,
                input_tokens=cached_entry.input_tokens,
                output_tokens=cached_entry.output_tokens,
                model=cached_entry.model,
                latency_ms=0,
                cached=True,
            )
            self._log_call(
                level=level,
                purpose=purpose,
                model=model,
                input_hash=input_hash,
                result=result,
                cached=True,
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command_id,
                turn_id=turn_id,
            )
            logger.debug(f"Cache hit for inference call (level={level}, purpose={purpose})")
            return result

        # Check rate limits
        rate_check = self.rate_limiter.check()
        if not rate_check.allowed:
            self._log_call(
                level=level,
                purpose=purpose,
                model=model,
                input_hash=input_hash,
                result=None,
                error_message=rate_check.reason,
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command_id,
                turn_id=turn_id,
            )
            raise InferenceServiceError(
                rate_check.reason,
                rate_limited=True,
                retry_after=rate_check.retry_after_seconds,
            )

        # Make API call
        messages = [{"role": "user", "content": input_text}]

        try:
            result = self.client.chat_completion(model=model, messages=messages)

            logger.debug(
                f"Inference response: level={level}, purpose={purpose}, model={model}, "
                f"input_tokens={result.input_tokens}, output_tokens={result.output_tokens}, "
                f"latency_ms={result.latency_ms}"
            )

            # Record rate limit usage
            total_tokens = (result.input_tokens or 0) + (result.output_tokens or 0)
            self.rate_limiter.record(total_tokens)

            # Cache the result
            self.cache.put(
                input_hash=input_hash,
                result_text=result.text,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                model=result.model,
            )

            # Log success
            self._log_call(
                level=level,
                purpose=purpose,
                model=model,
                input_hash=input_hash,
                result=result,
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command_id,
                turn_id=turn_id,
            )

            return result

        except OpenRouterClientError as e:
            logger.debug(
                f"Inference failed: level={level}, purpose={purpose}, model={model}, "
                f"error={e}"
            )
            # Log failure
            self._log_call(
                level=level,
                purpose=purpose,
                model=model,
                input_hash=input_hash,
                result=None,
                error_message=str(e),
                input_text=input_text,
                project_id=project_id,
                agent_id=agent_id,
                command_id=command_id,
                turn_id=turn_id,
            )
            raise

    def get_status(self) -> dict:
        """Get service status including connectivity and configuration."""
        connectivity = False
        if self.is_available:
            connectivity = self.client.check_connectivity()

        return {
            "available": self.is_available,
            "openrouter_connected": connectivity,
            "models": self.models,
            "rate_limits": self.rate_limiter.current_usage,
            "cache": self.cache.stats,
        }

    def get_usage(self, db_session=None) -> dict:
        """Get usage statistics from the database.

        Args:
            db_session: Database session for querying

        Returns:
            Dictionary with usage statistics
        """
        owns_session = False
        if not db_session:
            if self._log_session_factory:
                db_session = self._log_session_factory()
                owns_session = True
            else:
                return {"error": "No database session available"}

        from sqlalchemy import func

        try:
            # Total calls
            total_calls = db_session.query(func.count(InferenceCall.id)).scalar() or 0

            # Calls by level
            calls_by_level = dict(
                db_session.query(InferenceCall.level, func.count(InferenceCall.id))
                .group_by(InferenceCall.level)
                .all()
            )

            # Calls by model
            calls_by_model = dict(
                db_session.query(InferenceCall.model, func.count(InferenceCall.id))
                .group_by(InferenceCall.model)
                .all()
            )

            # Token totals
            total_input_tokens = db_session.query(func.sum(InferenceCall.input_tokens)).scalar() or 0
            total_output_tokens = db_session.query(func.sum(InferenceCall.output_tokens)).scalar() or 0

            # Cost breakdown by model
            cost_by_model = dict(
                db_session.query(InferenceCall.model, func.sum(InferenceCall.cost))
                .group_by(InferenceCall.model)
                .all()
            )

            total_cost = sum(v for v in cost_by_model.values() if v)

            return {
                "total_calls": total_calls,
                "calls_by_level": calls_by_level,
                "calls_by_model": calls_by_model,
                "total_input_tokens": total_input_tokens,
                "total_output_tokens": total_output_tokens,
                "total_cost": round(total_cost, 6),
                "cost_by_model": {k: round(v, 6) for k, v in cost_by_model.items() if v},
            }
        except Exception as e:
            logger.error(f"Failed to fetch usage stats: {e}")
            return {"error": str(e)}
        finally:
            if owns_session and db_session:
                db_session.close()
