"""Add slug column to projects table.

Adds a slug field derived from the project name for URL-friendly routing.
Backfills existing rows and adds unique constraint.

Revision ID: o7p8q9r0s1t2
Revises: n6o7p8q9r0s1
Create Date: 2026-02-04
"""

import re

from alembic import op
import sqlalchemy as sa

revision = "o7p8q9r0s1t2"
down_revision = "n6o7p8q9r0s1"
branch_labels = None
depends_on = None


def _generate_slug(name):
    """Generate a URL-safe slug from a project name."""
    slug = name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")
    return slug or "project"


def upgrade():
    # Add slug column as nullable first
    op.add_column("projects", sa.Column("slug", sa.String(), nullable=True))

    # Backfill existing rows
    conn = op.get_bind()
    projects = conn.execute(sa.text("SELECT id, name FROM projects ORDER BY id"))
    seen_slugs = set()

    for row in projects:
        base_slug = _generate_slug(row.name)
        slug = base_slug
        counter = 2
        while slug in seen_slugs:
            slug = f"{base_slug}-{counter}"
            counter += 1
        seen_slugs.add(slug)
        conn.execute(
            sa.text("UPDATE projects SET slug = :slug WHERE id = :id"),
            {"slug": slug, "id": row.id},
        )

    # Make non-nullable and add unique constraint + index
    op.alter_column("projects", "slug", nullable=False)
    op.create_unique_constraint("uq_projects_slug", "projects", ["slug"])
    op.create_index("ix_projects_slug", "projects", ["slug"])


def downgrade():
    op.drop_index("ix_projects_slug", table_name="projects")
    op.drop_constraint("uq_projects_slug", "projects", type_="unique")
    op.drop_column("projects", "slug")
