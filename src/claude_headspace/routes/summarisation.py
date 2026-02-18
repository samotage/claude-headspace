"""Summarisation API routes."""

from flask import Blueprint, current_app, jsonify

summarisation_bp = Blueprint("summarisation", __name__, url_prefix="/api/summarise")


def _get_service():
    """Get the summarisation service from app extensions."""
    return current_app.extensions.get("summarisation_service")


@summarisation_bp.route("/turn/<int:turn_id>", methods=["POST"])
def summarise_turn(turn_id):
    """Trigger summarisation for a specific turn.

    Returns the existing summary if already generated.
    Returns 404 if turn not found, 503 if inference unavailable.
    """
    service = _get_service()
    if not service:
        return jsonify({"error": "Summarisation service not available"}), 503

    from ..database import db
    from ..models.turn import Turn

    turn = db.session.get(Turn, turn_id)
    if not turn:
        return jsonify({"error": "Turn not found"}), 404

    # Return existing summary without re-generating
    if turn.summary:
        return jsonify({
            "turn_id": turn_id,
            "summary": turn.summary,
            "generated_at": turn.summary_generated_at.isoformat() if turn.summary_generated_at else None,
            "cached": True,
        })

    # Check if inference service is available
    inference = current_app.extensions.get("inference_service")
    if not inference or not inference.is_available:
        return jsonify({"error": "Inference service not available"}), 503

    summary = service.summarise_turn(turn, db_session=db.session)
    if summary is None:
        return jsonify({"error": "Summarisation failed"}), 500

    if summary and turn.command and turn.command.agent:
        from ..services.card_state import broadcast_card_refresh
        broadcast_card_refresh(turn.command.agent, "manual_turn_summary")

    return jsonify({
        "turn_id": turn_id,
        "summary": summary,
        "generated_at": turn.summary_generated_at.isoformat() if turn.summary_generated_at else None,
        "cached": False,
    })


@summarisation_bp.route("/command/<int:command_id>", methods=["POST"])
def summarise_command(command_id):
    """Trigger summarisation for a specific command.

    Returns the existing summary if already generated.
    Returns 404 if command not found, 503 if inference unavailable.
    """
    service = _get_service()
    if not service:
        return jsonify({"error": "Summarisation service not available"}), 503

    from ..database import db
    from ..models.command import Command

    command = db.session.get(Command, command_id)
    if not command:
        return jsonify({"error": "Command not found"}), 404

    # Return existing summary without re-generating
    if command.completion_summary:
        return jsonify({
            "command_id": command_id,
            "summary": command.completion_summary,
            "generated_at": command.completion_summary_generated_at.isoformat() if command.completion_summary_generated_at else None,
            "cached": True,
        })

    # Check if inference service is available
    inference = current_app.extensions.get("inference_service")
    if not inference or not inference.is_available:
        return jsonify({"error": "Inference service not available"}), 503

    summary = service.summarise_command(command, db_session=db.session)
    if summary is None:
        return jsonify({"error": "Summarisation failed"}), 500

    if summary and command.agent:
        from ..services.card_state import broadcast_card_refresh
        broadcast_card_refresh(command.agent, "manual_command_summary")

    return jsonify({
        "command_id": command_id,
        "summary": summary,
        "generated_at": command.completion_summary_generated_at.isoformat() if command.completion_summary_generated_at else None,
        "cached": False,
    })
