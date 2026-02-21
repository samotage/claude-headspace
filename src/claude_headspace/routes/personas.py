"""REST API endpoints for persona management."""

import logging

from flask import Blueprint, jsonify, request

from ..services.persona_registration import RegistrationError, register_persona

logger = logging.getLogger(__name__)

personas_bp = Blueprint("personas", __name__)


@personas_bp.route("/api/personas/register", methods=["POST"])
def api_register_persona():
    """Register a new persona via REST API.

    Accepts JSON:
        - name (required): Persona display name
        - role (required): Role name (lowercased on input)
        - description (optional): Persona description

    Returns:
        201: Persona created with {slug, id, path}
        400: Validation error
        500: Server error
    """
    data = request.get_json(silent=True) or {}

    name = data.get("name", "")
    role_name = data.get("role", "")
    description = data.get("description")

    try:
        result = register_persona(
            name=name, role_name=role_name, description=description
        )
    except RegistrationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.exception("Unexpected error during persona registration")
        return jsonify({"error": f"Server error: {e}"}), 500

    return jsonify({
        "slug": result.slug,
        "id": result.id,
        "path": result.path,
    }), 201


@personas_bp.route("/api/personas/<slug>/validate", methods=["GET"])
def api_validate_persona(slug: str):
    """Validate that a persona slug exists and is active.

    Returns:
        200: Persona exists and is active {valid: true, slug, id, name}
        404: Persona not found or not active {valid: false, error}
    """
    from ..models.persona import Persona

    persona = Persona.query.filter_by(slug=slug, status="active").first()
    if not persona:
        return jsonify({
            "valid": False,
            "error": f"Persona '{slug}' not found or not active. "
            "Register the persona first with: flask persona register --name <name> --role <role>",
        }), 404

    return jsonify({
        "valid": True,
        "slug": persona.slug,
        "id": persona.id,
        "name": persona.name,
    }), 200
