"""Headspace monitoring service for frustration tracking and flow state detection."""

import logging
import random
import threading
from datetime import datetime, timedelta, timezone

from ..database import db
from ..models.headspace_snapshot import HeadspaceSnapshot
from ..models.turn import Turn, TurnActor

logger = logging.getLogger(__name__)

GENTLE_ALERTS_DEFAULT = [
    "Think of your cortisol.",
    "Your body's gonna hate you for this.",
    "If you keep getting frustrated, you're going to pay for it later.",
    "Who owns this, you or the robots?",
    "The robots don't care if you're upset. But your body does.",
    "Time for a glass of water?",
    "Your future self called. They said chill.",
    "Frustration is feedback. What's it telling you?",
    "Step back. The code will still be here in 5 minutes.",
    "Your shoulders are probably up by your ears right now.",
    "Deep breath. Seriously.",
    "You're arguing with a machine. The machine doesn't mind.",
]

FLOW_MESSAGES_DEFAULT = [
    "You've been in the zone for {minutes} minutes. Nice!",
    "Flow state detected. Keep riding it.",
    "Productive streak: {minutes} minutes and counting.",
    "{turns} turns, low frustration. You're cooking.",
]

RETENTION_DAYS_DEFAULT = 7


class HeadspaceMonitor:
    """Orchestrates frustration calculation, threshold detection, alerting, and flow state."""

    def __init__(self, app, config: dict):
        self._app = app
        hs = config.get("headspace", {})
        self._enabled = hs.get("enabled", True)

        thresholds = hs.get("thresholds", {})
        self._yellow_threshold = thresholds.get("yellow", 4)
        self._red_threshold = thresholds.get("red", 7)

        self._cooldown_minutes = hs.get("alert_cooldown_minutes", 10)
        self._retention_days = hs.get("snapshot_retention_days", RETENTION_DAYS_DEFAULT)

        flow = hs.get("flow_detection", {})
        self._flow_min_turn_rate = flow.get("min_turn_rate", 6)
        self._flow_max_frustration = flow.get("max_frustration", 3)
        self._flow_min_duration = flow.get("min_duration_minutes", 15)

        self._session_rolling_window_minutes = hs.get("session_rolling_window_minutes", 180)

        messages = hs.get("messages", {})
        self._gentle_alerts = messages.get("gentle_alerts", GENTLE_ALERTS_DEFAULT)
        self._flow_messages = messages.get("flow_messages", FLOW_MESSAGES_DEFAULT)

        # In-memory state (thread-safe)
        self._lock = threading.Lock()
        self._last_alert_at: datetime | None = None
        self._suppressed_until: datetime | None = None
        self._flow_start: datetime | None = None
        self._last_flow_message_at: datetime | None = None
        self._last_state: str = "green"
        self._sustained_state_since: datetime | None = None
        self._alert_count_today: int = 0
        self._alert_count_date: str | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def suppress_alerts(self, hours: int = 1) -> None:
        """Suppress alerts for the given number of hours (called by 'I'm fine' button)."""
        with self._lock:
            self._suppressed_until = datetime.now(timezone.utc) + timedelta(hours=hours)

    def get_current_state(self) -> dict:
        """Get the current headspace state from the latest snapshot."""
        with self._app.app_context():
            snapshot = (
                db.session.query(HeadspaceSnapshot)
                .order_by(HeadspaceSnapshot.timestamp.desc())
                .first()
            )
            if not snapshot:
                return {
                    "state": "green",
                    "frustration_rolling_10": None,
                    "frustration_rolling_30min": None,
                    "frustration_rolling_3hr": None,
                    "is_flow_state": False,
                    "flow_duration_minutes": None,
                    "alert_suppressed": self._is_suppressed(),
                    "peak_frustration_today": self._calc_peak_today(),
                    "timestamp": None,
                }
            return self._snapshot_to_dict(snapshot)

    def recalculate(self, turn) -> None:
        """Recalculate headspace state after a user turn with frustration score."""
        if not self._enabled:
            return

        try:
            with self._app.app_context():
                now = datetime.now(timezone.utc)

                # Calculate rolling averages
                rolling_10 = self._calc_rolling_10()
                rolling_30min = self._calc_rolling_30min(now)
                rolling_3hr = self._calc_rolling_3hr(now)

                # Determine traffic light state
                state = self._determine_state(rolling_10, rolling_30min)

                # Calculate turn rate
                turn_rate = self._calc_turn_rate(now)

                # Detect flow state
                is_flow, flow_duration = self._detect_flow(
                    rolling_10, rolling_30min, turn_rate, now
                )

                # Check alert thresholds
                alert_triggered = self._check_thresholds(
                    turn, rolling_10, rolling_30min, state, now
                )

                # Create snapshot
                snapshot = self._create_snapshot(
                    now, rolling_10, rolling_30min, rolling_3hr, state,
                    turn_rate, is_flow, flow_duration,
                )

                # Prune old snapshots
                self._prune_snapshots(now)

                # Update state tracking under lock before broadcasting
                with self._lock:
                    prev_state = self._last_state
                    self._last_state = state

                if state != prev_state:
                    self._broadcast_state_update(snapshot)

                if alert_triggered:
                    self._broadcast_alert(alert_triggered)

                if is_flow:
                    self._maybe_broadcast_flow(flow_duration, turn_rate, now)

        except Exception as e:
            logger.error(f"Headspace recalculation failed: {e}")

    def _calc_rolling_10(self) -> float | None:
        """Calculate rolling average of last 10 scored user turns."""
        turns = (
            db.session.query(Turn.frustration_score)
            .filter(
                Turn.actor == TurnActor.USER,
                Turn.frustration_score.isnot(None),
            )
            .order_by(Turn.timestamp.desc())
            .limit(10)
            .all()
        )
        if not turns:
            return None
        scores = [t[0] for t in turns]
        return sum(scores) / len(scores)

    def _calc_rolling_30min(self, now: datetime) -> float | None:
        """Calculate rolling average of scored user turns in the last 30 minutes."""
        cutoff = now - timedelta(minutes=30)
        turns = (
            db.session.query(Turn.frustration_score)
            .filter(
                Turn.actor == TurnActor.USER,
                Turn.frustration_score.isnot(None),
                Turn.timestamp >= cutoff,
            )
            .all()
        )
        if not turns:
            return None
        scores = [t[0] for t in turns]
        return sum(scores) / len(scores)

    def _calc_rolling_3hr(self, now: datetime) -> float | None:
        """Calculate rolling average of scored user turns in the session window."""
        cutoff = now - timedelta(minutes=self._session_rolling_window_minutes)
        turns = (
            db.session.query(Turn.frustration_score)
            .filter(
                Turn.actor == TurnActor.USER,
                Turn.frustration_score.isnot(None),
                Turn.timestamp >= cutoff,
            )
            .all()
        )
        if not turns:
            return None
        scores = [t[0] for t in turns]
        return sum(scores) / len(scores)

    def _calc_turn_rate(self, now: datetime) -> float:
        """Calculate user turns per hour in the last hour."""
        cutoff = now - timedelta(hours=1)
        count = (
            db.session.query(Turn)
            .filter(
                Turn.actor == TurnActor.USER,
                Turn.timestamp >= cutoff,
            )
            .count()
        )
        return float(count)

    def _calc_peak_today(self) -> float | None:
        """Return the highest frustration_score from any USER turn today."""
        from sqlalchemy import func
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = (
            db.session.query(func.max(Turn.frustration_score))
            .filter(
                Turn.actor == TurnActor.USER,
                Turn.frustration_score.isnot(None),
                Turn.timestamp >= today_start,
            )
            .scalar()
        )
        return float(result) if result is not None else None

    def _determine_state(self, rolling_10: float | None, rolling_30min: float | None) -> str:
        """Determine traffic light state from rolling averages."""
        avg = None
        if rolling_10 is not None and rolling_30min is not None:
            avg = max(rolling_10, rolling_30min)
        elif rolling_10 is not None:
            avg = rolling_10
        elif rolling_30min is not None:
            avg = rolling_30min

        if avg is None:
            return "green"
        if avg >= self._red_threshold:
            return "red"
        if avg >= self._yellow_threshold:
            return "yellow"
        return "green"

    def _detect_flow(
        self, rolling_10: float | None, rolling_30min: float | None,
        turn_rate: float, now: datetime,
    ) -> tuple[bool, int | None]:
        """Detect flow state. Returns (is_flow, flow_duration_minutes)."""
        # Use the lower of rolling averages for flow (we want low frustration)
        avg = None
        if rolling_10 is not None and rolling_30min is not None:
            avg = min(rolling_10, rolling_30min)
        elif rolling_10 is not None:
            avg = rolling_10
        elif rolling_30min is not None:
            avg = rolling_30min

        conditions_met = (
            avg is not None
            and avg <= self._flow_max_frustration
            and turn_rate >= self._flow_min_turn_rate
        )

        with self._lock:
            if conditions_met:
                if self._flow_start is None:
                    self._flow_start = now
                duration = int((now - self._flow_start).total_seconds() / 60)
                if duration >= self._flow_min_duration:
                    return True, duration
                return False, None
            else:
                self._flow_start = None
                self._last_flow_message_at = None
                return False, None

    def _check_thresholds(
        self, turn, rolling_10: float | None, rolling_30min: float | None,
        state: str, now: datetime,
    ) -> str | None:
        """Check alert thresholds. Returns alert_type if triggered, else None."""
        if self._is_suppressed():
            return None
        if self._is_in_cooldown(now):
            return None

        # Use the higher average for threshold checks
        avg = None
        if rolling_10 is not None and rolling_30min is not None:
            avg = max(rolling_10, rolling_30min)
        elif rolling_10 is not None:
            avg = rolling_10
        elif rolling_30min is not None:
            avg = rolling_30min

        # Track sustained state timing BEFORE checks so duration is correct
        with self._lock:
            if state != self._last_state:
                self._sustained_state_since = now
            elif self._sustained_state_since is None:
                self._sustained_state_since = now

        alert_type = None

        # Absolute spike: single turn >= 8
        score = getattr(turn, "frustration_score", None)
        if score is not None and score >= 8:
            alert_type = "absolute_spike"

        # Sustained red: avg >= 7 for 2+ minutes
        if not alert_type and state == "red":
            with self._lock:
                if self._sustained_state_since and state == self._last_state:
                    duration = (now - self._sustained_state_since).total_seconds() / 60
                    if duration >= 2:
                        alert_type = "sustained_red"

        # Sustained yellow: avg >= 5 for 5+ minutes
        if not alert_type and avg is not None and avg >= 5:
            with self._lock:
                if self._sustained_state_since and self._last_state in ("yellow", "red"):
                    duration = (now - self._sustained_state_since).total_seconds() / 60
                    if duration >= 5:
                        alert_type = "sustained_yellow"

        # Rising trend: +3 over last 5 turns
        if not alert_type:
            recent = (
                db.session.query(Turn.frustration_score)
                .filter(
                    Turn.actor == TurnActor.USER,
                    Turn.frustration_score.isnot(None),
                )
                .order_by(Turn.timestamp.desc())
                .limit(5)
                .all()
            )
            if len(recent) >= 5:
                scores = [r[0] for r in reversed(recent)]
                if scores[-1] - scores[0] >= 3:
                    alert_type = "rising_trend"

        # Time-based: avg >= 4 for 30+ minutes
        if not alert_type and avg is not None and avg >= 4:
            with self._lock:
                if self._sustained_state_since:
                    duration = (now - self._sustained_state_since).total_seconds() / 60
                    if duration >= 30:
                        alert_type = "time_based"

        if alert_type:
            with self._lock:
                self._last_alert_at = now
                self._update_daily_alert_count(now)
            return alert_type
        return None

    def _is_suppressed(self) -> bool:
        with self._lock:
            if self._suppressed_until and datetime.now(timezone.utc) < self._suppressed_until:
                return True
            return False

    def _is_in_cooldown(self, now: datetime) -> bool:
        with self._lock:
            if self._last_alert_at:
                elapsed = (now - self._last_alert_at).total_seconds() / 60
                return elapsed < self._cooldown_minutes
            return False

    def _update_daily_alert_count(self, now: datetime) -> None:
        today = now.strftime("%Y-%m-%d")
        if self._alert_count_date != today:
            self._alert_count_date = today
            self._alert_count_today = 0
        self._alert_count_today += 1

    def _create_snapshot(
        self, now, rolling_10, rolling_30min, rolling_3hr, state,
        turn_rate, is_flow, flow_duration,
    ) -> HeadspaceSnapshot:
        with self._lock:
            last_alert_at = self._last_alert_at
            alert_count = self._alert_count_today

        snapshot = HeadspaceSnapshot(
            timestamp=now,
            frustration_rolling_10=rolling_10,
            frustration_rolling_30min=rolling_30min,
            frustration_rolling_3hr=rolling_3hr,
            state=state,
            turn_rate_per_hour=turn_rate,
            is_flow_state=is_flow,
            flow_duration_minutes=flow_duration,
            last_alert_at=last_alert_at,
            alert_count_today=alert_count,
        )
        db.session.add(snapshot)
        db.session.commit()
        return snapshot

    def _prune_snapshots(self, now: datetime) -> int:
        cutoff = now - timedelta(days=self._retention_days)
        deleted = (
            db.session.query(HeadspaceSnapshot)
            .filter(HeadspaceSnapshot.timestamp < cutoff)
            .delete()
        )
        if deleted:
            db.session.commit()
        return deleted

    def _broadcast_state_update(self, snapshot: HeadspaceSnapshot) -> None:
        try:
            from .broadcaster import get_broadcaster
            broadcaster = get_broadcaster()
            broadcaster.broadcast("headspace_update", {
                "state": snapshot.state,
                "frustration_rolling_10": snapshot.frustration_rolling_10,
                "frustration_rolling_30min": snapshot.frustration_rolling_30min,
                "frustration_rolling_3hr": snapshot.frustration_rolling_3hr,
                "is_flow_state": snapshot.is_flow_state,
                "flow_duration_minutes": snapshot.flow_duration_minutes,
                "peak_frustration_today": self._calc_peak_today(),
            })
        except Exception as e:
            logger.debug(f"Failed to broadcast headspace update (non-fatal): {e}")

    def _broadcast_alert(self, alert_type: str) -> None:
        try:
            from .broadcaster import get_broadcaster
            broadcaster = get_broadcaster()
            message = random.choice(self._gentle_alerts)
            broadcaster.broadcast("headspace_alert", {
                "message": message,
                "alert_type": alert_type,
                "dismissable": True,
            })
        except Exception as e:
            logger.debug(f"Failed to broadcast headspace alert (non-fatal): {e}")

    def _maybe_broadcast_flow(self, flow_duration: int, turn_rate: float, now: datetime) -> None:
        with self._lock:
            if self._last_flow_message_at:
                elapsed = (now - self._last_flow_message_at).total_seconds() / 60
                if elapsed < 15:
                    return
            self._last_flow_message_at = now

        try:
            from .broadcaster import get_broadcaster
            broadcaster = get_broadcaster()
            template = random.choice(self._flow_messages)
            message = template.format(minutes=flow_duration, turns=int(turn_rate))
            broadcaster.broadcast("headspace_flow", {
                "message": message,
                "minutes": flow_duration,
                "turns": int(turn_rate),
            })
        except Exception as e:
            logger.debug(f"Failed to broadcast flow message (non-fatal): {e}")

    def _snapshot_to_dict(self, snapshot: HeadspaceSnapshot) -> dict:
        return {
            "state": snapshot.state,
            "frustration_rolling_10": snapshot.frustration_rolling_10,
            "frustration_rolling_30min": snapshot.frustration_rolling_30min,
            "frustration_rolling_3hr": snapshot.frustration_rolling_3hr,
            "turn_rate_per_hour": snapshot.turn_rate_per_hour,
            "is_flow_state": snapshot.is_flow_state,
            "flow_duration_minutes": snapshot.flow_duration_minutes,
            "last_alert_at": snapshot.last_alert_at.isoformat() if snapshot.last_alert_at else None,
            "alert_count_today": snapshot.alert_count_today,
            "alert_suppressed": self._is_suppressed(),
            "peak_frustration_today": self._calc_peak_today(),
            "timestamp": snapshot.timestamp.isoformat() if snapshot.timestamp else None,
        }
