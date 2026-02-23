"""Persona filesystem asset utilities.

Manages persona asset files (skill.md, experience.md) using the
``data/personas/{slug}/`` directory convention. All functions are
stateless — they operate on slug strings with no database dependency.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# Directory and filename constants
PERSONAS_DIR = "data/personas"


def _resolve_personas_dir(project_root: Path | None = None) -> Path:
    """Resolve the base personas directory.

    Resolution order:
    1. Explicit ``project_root`` argument (direct service/test calls).
    2. ``current_app.config["PERSONA_DATA_ROOT"]`` (HTTP/CLI context).
    3. ``Path.cwd() / PERSONAS_DIR`` (fallback for non-Flask context).
    """
    if project_root is not None:
        return project_root / PERSONAS_DIR

    try:
        from flask import current_app
        configured = current_app.config.get("PERSONA_DATA_ROOT")
        if configured:
            return Path(configured)
    except (ImportError, RuntimeError):
        # No Flask or outside application context — fall through
        pass

    return Path.cwd() / PERSONAS_DIR


SKILL_FILENAME = "skill.md"
EXPERIENCE_FILENAME = "experience.md"

# Template for skill.md
SKILL_TEMPLATE = """\
# {persona_name} — {role_name}

## Core Identity
[Who this persona is — 1-2 sentences]

## Skills & Preferences
[Key competencies and working style]

## Communication Style
[How this persona communicates]
"""

# Template for experience.md
EXPERIENCE_TEMPLATE = """\
# Experience Log — {persona_name}

<!-- Append-only. New entries added at the top. -->
<!-- Periodically curated to remove outdated learnings. -->
"""


@dataclass
class AssetStatus:
    """Result of checking persona asset file existence."""

    skill_exists: bool
    experience_exists: bool
    directory_exists: bool


def get_persona_dir(slug: str, project_root: Path | None = None) -> Path:
    """Resolve a persona slug to its asset directory path.

    Args:
        slug: Persona slug (e.g. "developer-con-1").
        project_root: Project root directory. Defaults to cwd.

    Returns:
        Path to the persona's asset directory.
    """
    return _resolve_personas_dir(project_root) / slug


def create_persona_dir(slug: str, project_root: Path | None = None) -> Path:
    """Create a persona's asset directory, including parents.

    Idempotent — does not fail if the directory already exists.

    Args:
        slug: Persona slug.
        project_root: Project root directory. Defaults to cwd.

    Returns:
        Path to the created directory.
    """
    persona_dir = get_persona_dir(slug, project_root)
    persona_dir.mkdir(parents=True, exist_ok=True)
    return persona_dir


def seed_skill_file(
    slug: str,
    persona_name: str,
    role_name: str,
    project_root: Path | None = None,
) -> Path:
    """Create a skill.md template file for a persona.

    Does not overwrite an existing file.

    Args:
        slug: Persona slug.
        persona_name: Display name (e.g. "Con").
        role_name: Role name (e.g. "developer").
        project_root: Project root directory. Defaults to cwd.

    Returns:
        Path to the skill file.
    """
    persona_dir = create_persona_dir(slug, project_root)
    skill_path = persona_dir / SKILL_FILENAME

    if not skill_path.exists():
        content = SKILL_TEMPLATE.format(
            persona_name=persona_name,
            role_name=role_name,
        )
        skill_path.write_text(content, encoding="utf-8")
        logger.info("Seeded skill file: %s", skill_path)

    return skill_path


def seed_experience_file(
    slug: str,
    persona_name: str,
    project_root: Path | None = None,
) -> Path:
    """Create an experience.md template file for a persona.

    Does not overwrite an existing file.

    Args:
        slug: Persona slug.
        persona_name: Display name (e.g. "Con").
        project_root: Project root directory. Defaults to cwd.

    Returns:
        Path to the experience file.
    """
    persona_dir = create_persona_dir(slug, project_root)
    experience_path = persona_dir / EXPERIENCE_FILENAME

    if not experience_path.exists():
        content = EXPERIENCE_TEMPLATE.format(persona_name=persona_name)
        experience_path.write_text(content, encoding="utf-8")
        logger.info("Seeded experience file: %s", experience_path)

    return experience_path


def create_persona_assets(
    slug: str,
    persona_name: str,
    role_name: str,
    project_root: Path | None = None,
) -> Path:
    """Create a persona's directory and seed both template files.

    Combines directory creation, skill file seeding, and experience file
    seeding into a single operation. Idempotent — existing files are not
    overwritten.

    Args:
        slug: Persona slug.
        persona_name: Display name (e.g. "Con").
        role_name: Role name (e.g. "developer").
        project_root: Project root directory. Defaults to cwd.

    Returns:
        Path to the persona's asset directory.
    """
    persona_dir = create_persona_dir(slug, project_root)
    seed_skill_file(slug, persona_name, role_name, project_root)
    seed_experience_file(slug, persona_name, project_root)
    return persona_dir


def read_skill_file(slug: str, project_root: Path | None = None) -> str | None:
    """Read a persona's skill.md content.

    Args:
        slug: Persona slug.
        project_root: Project root directory. Defaults to cwd.

    Returns:
        File content as a string, or None if the file does not exist.
    """
    skill_path = get_persona_dir(slug, project_root) / SKILL_FILENAME
    if not skill_path.exists():
        return None
    return skill_path.read_text(encoding="utf-8")


def read_experience_file(slug: str, project_root: Path | None = None) -> str | None:
    """Read a persona's experience.md content.

    Args:
        slug: Persona slug.
        project_root: Project root directory. Defaults to cwd.

    Returns:
        File content as a string, or None if the file does not exist.
    """
    experience_path = get_persona_dir(slug, project_root) / EXPERIENCE_FILENAME
    if not experience_path.exists():
        return None
    return experience_path.read_text(encoding="utf-8")


def write_skill_file(
    slug: str, content: str, project_root: Path | None = None
) -> Path:
    """Write content to a persona's skill.md file.

    Creates the persona directory if it does not exist. Overwrites any
    existing skill.md content.

    Args:
        slug: Persona slug.
        content: Markdown content to write.
        project_root: Project root directory. Defaults to cwd.

    Returns:
        Path to the written skill file.
    """
    persona_dir = create_persona_dir(slug, project_root)
    skill_path = persona_dir / SKILL_FILENAME
    skill_path.write_text(content, encoding="utf-8")
    logger.info("Wrote skill file: %s", skill_path)
    return skill_path


def get_experience_mtime(slug: str, project_root: Path | None = None) -> str | None:
    """Get the last-modified timestamp of a persona's experience.md.

    Args:
        slug: Persona slug.
        project_root: Project root directory. Defaults to cwd.

    Returns:
        ISO 8601 timestamp string, or None if the file does not exist.
    """
    experience_path = get_persona_dir(slug, project_root) / EXPERIENCE_FILENAME
    if not experience_path.exists():
        return None
    mtime = experience_path.stat().st_mtime
    dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
    return dt.isoformat()


def check_assets(slug: str, project_root: Path | None = None) -> AssetStatus:
    """Check whether persona asset files exist on disk.

    Args:
        slug: Persona slug.
        project_root: Project root directory. Defaults to cwd.

    Returns:
        AssetStatus reporting presence of skill.md and experience.md.
    """
    persona_dir = get_persona_dir(slug, project_root)
    return AssetStatus(
        skill_exists=(persona_dir / SKILL_FILENAME).exists(),
        experience_exists=(persona_dir / EXPERIENCE_FILENAME).exists(),
        directory_exists=persona_dir.is_dir(),
    )
