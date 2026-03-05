"""Channel admin page route."""

import logging

from flask import Blueprint, render_template

logger = logging.getLogger(__name__)

channels_page_bp = Blueprint("channels_page", __name__)


@channels_page_bp.route("/channels")
def channels_page():
    """Channel admin page — listing, filtering, and management."""
    status_counts = {"input_needed": 0, "working": 0, "idle": 0}
    return render_template("channels.html", status_counts=status_counts)
