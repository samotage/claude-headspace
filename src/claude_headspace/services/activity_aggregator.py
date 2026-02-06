"""Activity aggregator service for computing and storing activity metrics.

Periodically queries Turn records, computes turn rate and average turn time
at agent, project, and overall levels, and stores results as hourly buckets
in the ActivityMetric table.
"""

import logging
import threading
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from flask import Flask

from ..database import db
from ..models.activity_metric import ActivityMetric
from ..models.agent import Agent
from ..models.turn import Turn, TurnActor

logger = logging.getLogger(__name__)

# Defaults (overridden by config.yaml → activity section)
DEFAULT_INTERVAL_SECONDS = 300  # 5 minutes
DEFAULT_RETENTION_DAYS = 30


class ActivityAggregator:
    """Background service that periodically computes activity metrics.

    Follows the AgentReaper pattern: __init__, start, stop, _loop.
    """

    def __init__(self, app: Flask, config: dict) -> None:
        self._app = app
        activity_config = config.get("activity", {})
        self._enabled = activity_config.get("enabled", True)
        self._interval = activity_config.get(
            "interval_seconds", DEFAULT_INTERVAL_SECONDS
        )
        self._retention_days = activity_config.get(
            "retention_days", DEFAULT_RETENTION_DAYS
        )
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start the aggregation background thread."""
        if not self._enabled:
            logger.info("Activity aggregator disabled by config")
            return

        if self._thread and self._thread.is_alive():
            logger.warning("Activity aggregator already running")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="ActivityAggregator"
        )
        self._thread.start()
        logger.info(f"Activity aggregator started (interval={self._interval}s)")

    def stop(self) -> None:
        """Stop the aggregator gracefully."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
            self._thread = None
            logger.info("Activity aggregator stopped")

    def _loop(self) -> None:
        """Background loop that calls aggregate_once at the configured interval."""
        while not self._stop_event.is_set():
            try:
                self.aggregate_once()
                self.prune_old_records()
            except Exception:
                logger.exception("Activity aggregation pass failed")

            self._stop_event.wait(timeout=self._interval)

    def aggregate_once(self) -> dict:
        """Run a single aggregation pass for the current hour bucket.

        Queries Turn records, computes metrics at agent/project/overall levels,
        and upserts ActivityMetric records.

        Returns:
            dict with counts of records created/updated.
        """
        with self._app.app_context():
            now = datetime.now(timezone.utc)
            bucket_start = now.replace(minute=0, second=0, microsecond=0)
            bucket_end = bucket_start + timedelta(hours=1)

            stats = {"agents": 0, "projects": 0, "overall": 0}

            # --- Agent-level metrics ---
            # Include agents still active OR ended during/after this bucket period.
            # An agent that ended at 10:30 should still contribute its turns to the 10:00 bucket.
            relevant_agents = (
                db.session.query(Agent)
                .filter(
                    sa.or_(
                        Agent.ended_at.is_(None),
                        Agent.ended_at >= bucket_start,
                    )
                )
                .all()
            )

            project_agent_counts: dict[int, int] = {}
            project_turn_counts: dict[int, int] = {}
            project_turn_time_sums: dict[int, float] = {}
            project_turn_time_counts: dict[int, int] = {}
            project_frustration: dict[int, int] = {}
            project_frustration_turns: dict[int, int] = {}
            project_max_frustration: dict[int, int] = {}
            project_max_frustration_at: dict[int, datetime | None] = {}

            # Single bulk query: fetch all turns in this bucket for all relevant agents
            from ..models.task import Task
            agent_ids = [a.id for a in relevant_agents]
            agent_map = {a.id: a for a in relevant_agents}

            all_turns = (
                db.session.query(Turn, Task.agent_id)
                .join(Task, Turn.task_id == Task.id)
                .filter(
                    Task.agent_id.in_(agent_ids),
                    Turn.timestamp >= bucket_start,
                    Turn.timestamp < bucket_end,
                )
                .order_by(Task.agent_id, Turn.timestamp.asc())
                .all()
            ) if agent_ids else []

            # Group turns by agent_id
            from collections import defaultdict
            turns_by_agent: dict[int, list] = defaultdict(list)
            for turn, agent_id in all_turns:
                turns_by_agent[agent_id].append(turn)

            for agent in relevant_agents:
                turns = turns_by_agent.get(agent.id, [])

                turn_count = len(turns)
                if turn_count == 0:
                    continue

                # Compute avg turn time (time between consecutive turns)
                avg_turn_time = None
                if turn_count >= 2:
                    deltas = []
                    for i in range(1, len(turns)):
                        delta = (turns[i].timestamp - turns[i - 1].timestamp).total_seconds()
                        deltas.append(delta)
                    avg_turn_time = sum(deltas) / len(deltas) if deltas else None

                # Compute frustration metrics from USER turns
                user_frustration_turns = [
                    t for t in turns
                    if t.actor == TurnActor.USER and t.frustration_score is not None
                ]
                frustration_sum = sum(t.frustration_score for t in user_frustration_turns)
                total_frustration = frustration_sum if frustration_sum > 0 else None
                frustration_turn_count = len(user_frustration_turns) if user_frustration_turns else None
                max_frustration_turn = max(user_frustration_turns, key=lambda t: t.frustration_score, default=None)
                max_frustration = int(max_frustration_turn.frustration_score) if max_frustration_turn else None
                max_frustration_at = max_frustration_turn.timestamp if max_frustration_turn else None

                # Upsert agent metric
                self._upsert_metric(
                    db.session,
                    bucket_start=bucket_start,
                    agent_id=agent.id,
                    project_id=None,
                    is_overall=False,
                    turn_count=turn_count,
                    avg_turn_time_seconds=avg_turn_time,
                    active_agents=None,
                    total_frustration=total_frustration,
                    frustration_turn_count=frustration_turn_count,
                    max_frustration=max_frustration,
                    max_frustration_at=max_frustration_at,
                )
                stats["agents"] += 1

                # Accumulate for project rollup
                pid = agent.project_id
                project_agent_counts[pid] = project_agent_counts.get(pid, 0) + 1
                project_turn_counts[pid] = project_turn_counts.get(pid, 0) + turn_count
                if avg_turn_time is not None:
                    project_turn_time_sums[pid] = project_turn_time_sums.get(pid, 0.0) + avg_turn_time * (turn_count - 1)
                    project_turn_time_counts[pid] = project_turn_time_counts.get(pid, 0) + (turn_count - 1)
                if total_frustration is not None:
                    project_frustration[pid] = project_frustration.get(pid, 0) + total_frustration
                if frustration_turn_count is not None:
                    project_frustration_turns[pid] = project_frustration_turns.get(pid, 0) + frustration_turn_count
                if max_frustration is not None:
                    if max_frustration > project_max_frustration.get(pid, 0):
                        project_max_frustration[pid] = max_frustration
                        project_max_frustration_at[pid] = max_frustration_at

            # --- Project-level metrics ---
            total_turn_count = 0
            total_active_agents = 0
            total_turn_time_sum = 0.0
            total_turn_time_count = 0
            total_frustration_sum = 0
            total_frustration_turn_count = 0
            total_max_frustration = 0
            total_max_frustration_at: datetime | None = None

            for pid, turn_count in project_turn_counts.items():
                active_count = project_agent_counts.get(pid, 0)
                avg_turn_time = None
                if pid in project_turn_time_counts and project_turn_time_counts[pid] > 0:
                    avg_turn_time = project_turn_time_sums[pid] / project_turn_time_counts[pid]

                pid_frustration = project_frustration.get(pid)
                pid_frustration_turns = project_frustration_turns.get(pid)
                pid_max_frustration = project_max_frustration.get(pid)
                pid_max_frustration_at = project_max_frustration_at.get(pid)

                self._upsert_metric(
                    db.session,
                    bucket_start=bucket_start,
                    agent_id=None,
                    project_id=pid,
                    is_overall=False,
                    turn_count=turn_count,
                    avg_turn_time_seconds=avg_turn_time,
                    active_agents=active_count,
                    total_frustration=pid_frustration,
                    frustration_turn_count=pid_frustration_turns,
                    max_frustration=pid_max_frustration,
                    max_frustration_at=pid_max_frustration_at,
                )
                stats["projects"] += 1

                # Accumulate for overall rollup
                total_turn_count += turn_count
                total_active_agents += active_count
                if pid in project_turn_time_counts:
                    total_turn_time_sum += project_turn_time_sums.get(pid, 0.0)
                    total_turn_time_count += project_turn_time_counts.get(pid, 0)
                if pid_frustration is not None:
                    total_frustration_sum += pid_frustration
                if pid_frustration_turns is not None:
                    total_frustration_turn_count += pid_frustration_turns
                if pid_max_frustration is not None:
                    if pid_max_frustration > total_max_frustration:
                        total_max_frustration = pid_max_frustration
                        total_max_frustration_at = pid_max_frustration_at

            # --- Overall-level metric ---
            if total_turn_count > 0:
                overall_avg = None
                if total_turn_time_count > 0:
                    overall_avg = total_turn_time_sum / total_turn_time_count

                self._upsert_metric(
                    db.session,
                    bucket_start=bucket_start,
                    agent_id=None,
                    project_id=None,
                    is_overall=True,
                    turn_count=total_turn_count,
                    avg_turn_time_seconds=overall_avg,
                    active_agents=total_active_agents,
                    total_frustration=total_frustration_sum if total_frustration_sum > 0 else None,
                    frustration_turn_count=total_frustration_turn_count if total_frustration_turn_count > 0 else None,
                    max_frustration=total_max_frustration if total_max_frustration > 0 else None,
                    max_frustration_at=total_max_frustration_at if total_max_frustration > 0 else None,
                )
                stats["overall"] = 1

            db.session.commit()

            if any(v > 0 for v in stats.values()):
                logger.info(
                    f"Aggregation pass: agents={stats['agents']}, "
                    f"projects={stats['projects']}, overall={stats['overall']}"
                )
                self._broadcast_activity_update(stats)
            else:
                logger.debug("Aggregation pass: no activity found")

            return stats

    def _broadcast_activity_update(self, stats: dict) -> None:
        """Broadcast an SSE event so the activity page refreshes in real-time."""
        try:
            from .broadcaster import get_broadcaster

            broadcaster = get_broadcaster()
            broadcaster.broadcast("activity_update", {
                "agents_updated": stats.get("agents", 0),
                "projects_updated": stats.get("projects", 0),
                "overall_updated": stats.get("overall", 0),
            })
        except Exception as e:
            logger.debug(f"Failed to broadcast activity update (non-fatal): {e}")

    def prune_old_records(self) -> int:
        """Delete ActivityMetric records older than the configured retention period.

        Returns:
            Number of records deleted.
        """
        with self._app.app_context():
            cutoff = datetime.now(timezone.utc) - timedelta(days=self._retention_days)
            deleted = (
                db.session.query(ActivityMetric)
                .filter(ActivityMetric.bucket_start < cutoff)
                .delete(synchronize_session=False)
            )
            db.session.commit()

            if deleted > 0:
                logger.info(f"Pruned {deleted} activity metric records older than {self._retention_days} days")

            return deleted

    @staticmethod
    def _upsert_metric(
        session,
        bucket_start: datetime,
        agent_id: int | None,
        project_id: int | None,
        is_overall: bool,
        turn_count: int,
        avg_turn_time_seconds: float | None,
        active_agents: int | None,
        total_frustration: int | None = None,
        frustration_turn_count: int | None = None,
        max_frustration: int | None = None,
        max_frustration_at: datetime | None = None,
    ) -> None:
        """Upsert an ActivityMetric record using INSERT ON CONFLICT.

        Uses the ``uq_activity_metrics_bucket_scope`` unique index
        (bucket_start, COALESCE(agent_id,-1), COALESCE(project_id,-1), is_overall)
        to atomically insert-or-update, preventing duplicate records.
        """
        from sqlalchemy.dialects.postgresql import insert

        stmt = insert(ActivityMetric).values(
            bucket_start=bucket_start,
            agent_id=agent_id,
            project_id=project_id,
            is_overall=is_overall,
            turn_count=turn_count,
            avg_turn_time_seconds=avg_turn_time_seconds,
            active_agents=active_agents,
            total_frustration=total_frustration,
            frustration_turn_count=frustration_turn_count,
            max_frustration=max_frustration,
            max_frustration_at=max_frustration_at,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ActivityMetric.bucket_start,
                sa.text("COALESCE(agent_id, -1)"),
                sa.text("COALESCE(project_id, -1)"),
                ActivityMetric.is_overall,
            ],
            set_={
                "turn_count": stmt.excluded.turn_count,
                "avg_turn_time_seconds": stmt.excluded.avg_turn_time_seconds,
                "active_agents": stmt.excluded.active_agents,
                "total_frustration": stmt.excluded.total_frustration,
                "frustration_turn_count": stmt.excluded.frustration_turn_count,
                "max_frustration": stmt.excluded.max_frustration,
                "max_frustration_at": stmt.excluded.max_frustration_at,
            },
        )

        session.execute(stmt)
