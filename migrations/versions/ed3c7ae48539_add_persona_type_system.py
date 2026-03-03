"""add persona_type_system — PersonaType lookup table, Persona FK, operator Persona

Revision ID: ed3c7ae48539
Revises: b7f8c9d0e1f2
Create Date: 2026-03-03 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ed3c7ae48539'
down_revision = 'b7f8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    # Step 1: Create persona_types lookup table
    op.create_table(
        'persona_types',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('type_key', sa.String(16), nullable=False),
        sa.Column('subtype', sa.String(16), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('type_key', 'subtype', name='uq_persona_type_key_subtype'),
    )

    # Step 2: Seed 4 rows with explicit IDs (2x2 matrix)
    persona_types = sa.table(
        'persona_types',
        sa.column('id', sa.Integer),
        sa.column('type_key', sa.String),
        sa.column('subtype', sa.String),
    )
    op.bulk_insert(persona_types, [
        {'id': 1, 'type_key': 'agent', 'subtype': 'internal'},
        {'id': 2, 'type_key': 'agent', 'subtype': 'external'},
        {'id': 3, 'type_key': 'person', 'subtype': 'internal'},
        {'id': 4, 'type_key': 'person', 'subtype': 'external'},
    ])

    # Reset sequence so future inserts auto-increment from 5
    op.execute("SELECT setval('persona_types_id_seq', 4)")

    # Step 3: Add persona_type_id column as NULLABLE (3-step NOT NULL pattern)
    op.add_column('personas', sa.Column('persona_type_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_personas_persona_type_id',
        'personas',
        'persona_types',
        ['persona_type_id'],
        ['id'],
        ondelete='RESTRICT',
    )

    # Step 4: Backfill all existing personas to agent/internal (id=1)
    op.execute("UPDATE personas SET persona_type_id = 1 WHERE persona_type_id IS NULL")

    # Step 5: Alter column to NOT NULL
    op.alter_column('personas', 'persona_type_id', nullable=False)

    # Step 6: Create "operator" Role (idempotent)
    op.execute("""
        INSERT INTO roles (name, description, created_at)
        SELECT 'operator', 'System operator — human identity for channel participation', NOW()
        WHERE NOT EXISTS (SELECT 1 FROM roles WHERE name = 'operator')
    """)

    # Step 7: Create "Sam" operator Persona (idempotent)
    op.execute("""
        INSERT INTO personas (name, slug, description, status, role_id, persona_type_id, created_at)
        SELECT
            'Sam',
            '_pending_operator',
            'System operator',
            'active',
            (SELECT id FROM roles WHERE name = 'operator'),
            3,
            NOW()
        WHERE NOT EXISTS (
            SELECT 1 FROM personas p
            JOIN roles r ON p.role_id = r.id
            WHERE p.name = 'Sam' AND r.name = 'operator'
        )
    """)

    # Step 8: Fix operator slug from _pending_operator to operator-sam-{id}
    # (Raw SQL migration does not trigger the ORM after_insert event)
    op.execute("""
        UPDATE personas
        SET slug = 'operator-sam-' || id
        WHERE slug = '_pending_operator'
    """)

    # Step 9: Ensure operator persona has correct persona_type_id (person/internal)
    # Handles re-run case where backfill (Step 4) overwrote the operator's type
    # after a downgrade/upgrade cycle preserved the operator record.
    op.execute("""
        UPDATE personas
        SET persona_type_id = 3
        WHERE role_id = (SELECT id FROM roles WHERE name = 'operator')
          AND name = 'Sam'
          AND persona_type_id != 3
    """)


def downgrade():
    # Drop FK constraint and column
    op.drop_constraint('fk_personas_persona_type_id', 'personas', type_='foreignkey')
    op.drop_column('personas', 'persona_type_id')
    # Drop persona_types table
    op.drop_table('persona_types')
    # Note: operator Role and operator Persona are NOT removed on downgrade
