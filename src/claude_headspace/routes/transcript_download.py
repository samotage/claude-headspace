"""Transcript download API endpoints."""

import logging

from flask import Blueprint, Response, current_app, jsonify

logger = logging.getLogger(__name__)

transcript_download_bp = Blueprint("transcript_download", __name__)


def _get_service():
    """Get the transcript export service. Returns (service, error_response)."""
    service = current_app.extensions.get("transcript_export_service")
    if service is None:
        return None, (
            jsonify({"error": "Transcript export service not available"}),
            503,
        )
    return service, None


@transcript_download_bp.route("/api/agents/<int:agent_id>/transcript", methods=["GET"])
def download_agent_transcript(agent_id: int):
    """Download an agent session transcript as a Markdown file.

    Assembles all turns across all commands for the agent, formats as
    Markdown with YAML frontmatter, saves server-side, and returns as
    a file download.
    """
    service, err = _get_service()
    if err:
        return err

    try:
        filename, content = service.assemble_agent_transcript(agent_id)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error("Agent transcript generation failed for agent %s: %s", agent_id, e)
        return jsonify({"error": "Transcript generation failed"}), 500

    return Response(
        content,
        mimetype="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@transcript_download_bp.route("/api/channels/<slug>/transcript", methods=["GET"])
def download_channel_transcript(slug: str):
    """Download a channel chat transcript as a Markdown file.

    Assembles all messages in the channel, formats as Markdown with YAML
    frontmatter, saves server-side, and returns as a file download.
    """
    service, err = _get_service()
    if err:
        return err

    try:
        filename, content = service.assemble_channel_transcript(slug)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logger.error("Channel transcript generation failed for '%s': %s", slug, e)
        return jsonify({"error": "Transcript generation failed"}), 500

    return Response(
        content,
        mimetype="text/markdown; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )
