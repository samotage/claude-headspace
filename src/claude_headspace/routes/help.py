"""Help page and API routes for serving documentation content."""

import logging
import re
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template

logger = logging.getLogger(__name__)

help_bp = Blueprint("help", __name__)

# Help documentation directory (relative to project root)
HELP_DIR = Path("docs/help")

# Application docs directory (sibling of help dir)
APPLICATION_DIR = Path("docs/application")

# Topic metadata extracted from filenames
TOPICS = [
    {"slug": "index", "title": "Help Overview", "order": 0},
    {"slug": "getting-started", "title": "Getting Started", "order": 1},
    {"slug": "dashboard", "title": "Dashboard", "order": 2},
    {"slug": "projects", "title": "Projects", "order": 3},
    {"slug": "input-bridge", "title": "Input Bridge", "order": 4},
    {"slug": "voice-bridge", "title": "Voice Bridge", "order": 5},
    {"slug": "objective", "title": "Objective", "order": 6},
    {"slug": "waypoints", "title": "Waypoints", "order": 7},
    {"slug": "brain-reboot", "title": "Brain Reboot", "order": 8},
    {"slug": "activity", "title": "Activity", "order": 9},
    {"slug": "headspace", "title": "Headspace", "order": 10},
    {"slug": "logging", "title": "Logging", "order": 11},
    {"slug": "configuration", "title": "Configuration", "order": 12},
    {"slug": "troubleshooting", "title": "Troubleshooting", "order": 13},
]


def get_help_dir() -> Path:
    """Get the help documentation directory path."""
    # Get project root from app config or use relative path
    project_root = getattr(current_app, "root_path", None)
    if project_root:
        # Go up from src/claude_headspace to project root
        root = Path(project_root).parent.parent
    else:
        root = Path.cwd()
    return root / HELP_DIR


def extract_excerpt(content: str, max_length: int = 150) -> str:
    """Extract a short excerpt from markdown content."""
    # Remove markdown headers
    text = re.sub(r"^#+\s+.*$", "", content, flags=re.MULTILINE)
    # Remove markdown links
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove inline code
    text = re.sub(r"`[^`]+`", "", text)
    # Remove emphasis
    text = re.sub(r"\*+([^*]+)\*+", r"\1", text)
    # Collapse whitespace
    text = " ".join(text.split())
    # Truncate
    if len(text) > max_length:
        text = text[:max_length].rsplit(" ", 1)[0] + "..."
    return text.strip()


def extract_title(content: str, default: str) -> str:
    """Extract title from first h1 heading in markdown."""
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return default


@help_bp.route("/help", methods=["GET"])
@help_bp.route("/help/<slug>", methods=["GET"])
def help_page(slug: str = "index"):
    """
    Render the help documentation page.

    Args:
        slug: Topic slug to display initially (default: index)
    """
    # Validate slug
    if not re.match(r"^[a-z0-9-]+$", slug):
        slug = "index"

    status_counts = {"input_needed": 0, "working": 0, "idle": 0}

    return render_template(
        "help.html",
        initial_topic=slug,
        status_counts=status_counts,
    )


@help_bp.route("/api/help/topics", methods=["GET"])
def list_topics():
    """
    List all available help topics.

    Returns:
        200: List of topics with slug, title, and excerpt
    """
    help_dir = get_help_dir()
    topics_list = []

    for topic in sorted(TOPICS, key=lambda t: t["order"]):
        file_path = help_dir / f"{topic['slug']}.md"

        topic_data = {
            "slug": topic["slug"],
            "title": topic["title"],
            "excerpt": "",
        }

        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
                # Extract title from content if available
                topic_data["title"] = extract_title(content, topic["title"])
                topic_data["excerpt"] = extract_excerpt(content)
            except Exception as e:
                logger.warning(f"Error reading help topic {topic['slug']}: {e}")

        topics_list.append(topic_data)

    return jsonify({"topics": topics_list}), 200


@help_bp.route("/api/help/topics/<slug>", methods=["GET"])
def get_topic(slug: str):
    """
    Get content for a specific help topic.

    Args:
        slug: Topic identifier (e.g., "getting-started")

    Returns:
        200: Topic content as markdown
        404: Topic not found
    """
    # Validate slug to prevent path traversal
    if not re.match(r"^[a-z0-9-]+$", slug):
        return jsonify({
            "error": "invalid_slug",
            "message": "Invalid topic slug",
        }), 400

    help_dir = get_help_dir()
    file_path = help_dir / f"{slug}.md"

    if not file_path.exists():
        return jsonify({
            "error": "not_found",
            "message": f"Topic '{slug}' not found",
        }), 404

    try:
        content = file_path.read_text(encoding="utf-8")
        title = extract_title(content, slug.replace("-", " ").title())

        return jsonify({
            "slug": slug,
            "title": title,
            "content": content,
        }), 200

    except PermissionError:
        return jsonify({
            "error": "permission_denied",
            "message": f"Cannot read topic '{slug}'",
        }), 403
    except Exception as e:
        logger.exception(f"Error reading help topic {slug}")
        return jsonify({
            "error": "read_error",
            "message": f"Failed to read topic: {type(e).__name__}",
        }), 500


@help_bp.route("/api/help/setup-prompt", methods=["GET"])
def get_setup_prompt():
    """
    Get the Claude Code setup prompt document.

    Returns:
        200: Setup prompt content as markdown
        404: Document not found
    """
    project_root = getattr(current_app, "root_path", None)
    if project_root:
        root = Path(project_root).parent.parent
    else:
        root = Path.cwd()

    file_path = root / APPLICATION_DIR / "claude_code_setup_prompt.md"

    if not file_path.exists():
        return jsonify({
            "error": "not_found",
            "message": "Setup prompt document not found",
        }), 404

    try:
        content = file_path.read_text(encoding="utf-8")
        title = extract_title(content, "Claude Code Setup Prompt")

        return jsonify({
            "title": title,
            "content": content,
        }), 200

    except PermissionError:
        return jsonify({
            "error": "permission_denied",
            "message": "Cannot read setup prompt document",
        }), 403
    except Exception as e:
        logger.exception("Error reading setup prompt document")
        return jsonify({
            "error": "read_error",
            "message": f"Failed to read document: {type(e).__name__}",
        }), 500


@help_bp.route("/api/help/search", methods=["GET"])
def get_search_index():
    """
    Get all topic content for client-side search indexing.

    Returns:
        200: All topics with full content for indexing
    """
    help_dir = get_help_dir()
    index_data = []

    for topic in TOPICS:
        file_path = help_dir / f"{topic['slug']}.md"

        if file_path.exists():
            try:
                content = file_path.read_text(encoding="utf-8")
                title = extract_title(content, topic["title"])

                index_data.append({
                    "slug": topic["slug"],
                    "title": title,
                    "content": content,
                })
            except Exception as e:
                logger.warning(f"Error reading help topic for index {topic['slug']}: {e}")

    return jsonify({"topics": index_data}), 200
