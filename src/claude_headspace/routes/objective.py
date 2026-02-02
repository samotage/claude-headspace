"""Objective API endpoints and page route."""

import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, render_template, request

from ..database import db
from ..models.objective import Objective, ObjectiveHistory

logger = logging.getLogger(__name__)

objective_bp = Blueprint("objective", __name__)


@objective_bp.route("/objective")
def objective_page():
    """
    Objective tab page.

    Returns:
        Rendered objective template with current objective and history
    """
    # Get current objective
    objective = db.session.query(Objective).first()

    # Get first page of history
    history_query = (
        db.session.query(ObjectiveHistory)
        .order_by(ObjectiveHistory.started_at.desc())
        .limit(10)
        .all()
    )

    # Get total count for pagination
    total_history = db.session.query(ObjectiveHistory).count()
    has_more = total_history > 10

    status_counts = {"input_needed": 0, "working": 0, "idle": 0}

    return render_template(
        "objective.html",
        objective=objective,
        history=history_query,
        has_more=has_more,
        total_history=total_history,
        status_counts=status_counts,
    )


@objective_bp.route("/api/objective", methods=["GET"])
def get_objective():
    """
    Get current objective.

    Returns:
        JSON with current objective or empty response
    """
    objective = db.session.query(Objective).first()

    if not objective:
        return jsonify({"message": "No objective set"}), 200

    return jsonify(
        {
            "id": objective.id,
            "current_text": objective.current_text,
            "constraints": objective.constraints,
            "set_at": objective.set_at.isoformat() if objective.set_at else None,
        }
    )


@objective_bp.route("/api/objective", methods=["POST"])
def update_objective():
    """
    Save or create a new objective.

    Accepts JSON body with:
        - text (required): The objective text
        - constraints (optional): Constraints text
        - new (optional, default false): If true, archives the current objective
          and creates a new one. If false, updates the current objective in-place.

    Returns:
        JSON with the objective or validation error
    """
    data = request.get_json()

    if not data:
        return jsonify({"error": "Request body must be JSON"}), 400

    text = (data.get("text") or "").strip()
    constraints = (data.get("constraints") or "").strip() or None
    is_new = data.get("new", False)

    if not text:
        return jsonify({"error": "Objective text is required"}), 400

    try:
        now = datetime.now(timezone.utc)
        objective = db.session.query(Objective).first()

        if objective and not is_new:
            # Update existing objective in-place (no new history entry)
            objective.current_text = text
            objective.constraints = constraints
            objective.set_at = now

            # Also update the open history record to match
            current_history = (
                db.session.query(ObjectiveHistory)
                .filter(
                    ObjectiveHistory.objective_id == objective.id,
                    ObjectiveHistory.ended_at.is_(None),
                )
                .first()
            )
            if current_history:
                current_history.text = text
                current_history.constraints = constraints

        elif objective and is_new:
            # Archive current objective and create new one
            current_history = (
                db.session.query(ObjectiveHistory)
                .filter(
                    ObjectiveHistory.objective_id == objective.id,
                    ObjectiveHistory.ended_at.is_(None),
                )
                .first()
            )
            if current_history:
                current_history.ended_at = now

            # Update the objective row
            objective.current_text = text
            objective.constraints = constraints
            objective.set_at = now

            # Create new history record
            new_history = ObjectiveHistory(
                objective_id=objective.id,
                text=text,
                constraints=constraints,
                started_at=now,
                ended_at=None,
            )
            db.session.add(new_history)

        else:
            # No objective exists yet — create one
            objective = Objective(
                current_text=text,
                constraints=constraints,
                set_at=now,
            )
            db.session.add(objective)
            db.session.flush()

            history = ObjectiveHistory(
                objective_id=objective.id,
                text=text,
                constraints=constraints,
                started_at=now,
                ended_at=None,
            )
            db.session.add(history)

        db.session.commit()

        return jsonify(
            {
                "id": objective.id,
                "current_text": objective.current_text,
                "constraints": objective.constraints,
                "set_at": objective.set_at.isoformat() if objective.set_at else None,
            }
        )

    except Exception:
        logger.exception("Failed to save objective")
        db.session.rollback()
        return jsonify({"error": "Failed to save objective"}), 500


@objective_bp.route("/api/objective/history", methods=["GET"])
def get_objective_history():
    """
    Get paginated objective history.

    Query parameters:
        - page (optional, default=1): Page number
        - per_page (optional, default=10): Items per page

    Returns:
        JSON with paginated history items and metadata
    """
    try:
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 10, type=int)

        # Validate parameters
        if page < 1:
            page = 1
        if per_page < 1:
            per_page = 10
        if per_page > 100:
            per_page = 100

        # Get total count
        total = db.session.query(ObjectiveHistory).count()

        # Calculate offset
        offset = (page - 1) * per_page

        # Get history items
        items = (
            db.session.query(ObjectiveHistory)
            .order_by(ObjectiveHistory.started_at.desc())
            .offset(offset)
            .limit(per_page)
            .all()
        )

        # Calculate total pages
        pages = (total + per_page - 1) // per_page if total > 0 else 0

        return jsonify(
            {
                "items": [
                    {
                        "id": item.id,
                        "text": item.text,
                        "constraints": item.constraints,
                        "started_at": (
                            item.started_at.isoformat() if item.started_at else None
                        ),
                        "ended_at": (
                            item.ended_at.isoformat() if item.ended_at else None
                        ),
                    }
                    for item in items
                ],
                "page": page,
                "per_page": per_page,
                "total": total,
                "pages": pages,
            }
        )

    except Exception:
        logger.exception("Failed to fetch objective history")
        return jsonify({"error": "Failed to fetch history"}), 500
