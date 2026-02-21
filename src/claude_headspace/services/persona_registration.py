"""Persona registration service.

Orchestrates end-to-end persona creation: input validation, role
lookup/create, persona DB insert, and filesystem asset creation.
The service function is callable without CLI or HTTP context.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

from ..database import db
from ..models.persona import Persona
from ..models.role import Role
from .persona_assets import create_persona_assets, get_persona_dir

logger = logging.getLogger(__name__)


@dataclass
class RegistrationResult:
    """Result of a successful persona registration."""

    slug: str
    id: int
    path: str


class RegistrationError(Exception):
    """Raised when persona registration fails validation."""


def register_persona(
    name: str,
    role_name: str,
    description: str | None = None,
    project_root: Path | None = None,
) -> RegistrationResult:
    """Register a new persona end-to-end.

    Performs the full creation flow:
    1. Validate inputs (name and role_name required, non-empty)
    2. Lookup or create Role (case-insensitive, lowercased on storage)
    3. Insert Persona record (slug auto-generated via after_insert event)
    4. Create filesystem directory and seed template files

    Args:
        name: Persona display name (e.g. "Con"). Case preserved in DB.
        role_name: Role name (e.g. "developer"). Lowercased for storage/lookup.
        description: Optional persona description.
        project_root: Project root for filesystem assets. Defaults to cwd.

    Returns:
        RegistrationResult with slug, database ID, and filesystem path.

    Raises:
        RegistrationError: If validation fails (empty name or role).
    """
    # 1. Validate inputs
    if not name or not name.strip():
        raise RegistrationError("Persona name is required and cannot be empty.")
    if not role_name or not role_name.strip():
        raise RegistrationError("Role name is required and cannot be empty.")

    name = name.strip()
    role_name_lower = role_name.strip().lower()

    # 2. Lookup or create Role
    role = Role.query.filter_by(name=role_name_lower).first()
    if role is None:
        role = Role(name=role_name_lower)
        db.session.add(role)
        db.session.flush()
        logger.info("Created role: %s (id=%d)", role.name, role.id)

    # 3. Insert Persona record
    persona = Persona(
        name=name,
        role_id=role.id,
        role=role,
        description=description,
        status="active",
    )
    db.session.add(persona)
    db.session.flush()  # Triggers after_insert event which sets the real slug
    logger.info("Created persona: %s (id=%d, slug=%s)", persona.name, persona.id, persona.slug)

    # 4. Create filesystem assets
    try:
        asset_dir = create_persona_assets(
            persona.slug, persona.name, role.name, project_root=project_root
        )
        asset_path = str(asset_dir)
    except Exception as e:
        # Partial failure: DB record exists but filesystem failed.
        # Commit the DB record and report the error.
        db.session.commit()
        logger.error(
            "Filesystem creation failed for persona %s (id=%d, slug=%s): %s",
            persona.name, persona.id, persona.slug, e,
        )
        raise RegistrationError(
            f"Persona created in database (id={persona.id}, slug={persona.slug}) "
            f"but filesystem creation failed: {e}"
        ) from e

    db.session.commit()

    persona_dir = get_persona_dir(persona.slug, project_root=project_root)
    return RegistrationResult(
        slug=persona.slug,
        id=persona.id,
        path=str(persona_dir),
    )
