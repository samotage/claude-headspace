"""rename task to command

Revision ID: a0b1c2d3e4f5
Revises: 88adcfd47a28
Create Date: 2026-02-18 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = 'a0b1c2d3e4f5'
down_revision = '88adcfd47a28'
branch_labels = None
depends_on = None


def upgrade():
    # ---------------------------------------------------------------------------
    # 1. Rename the tasks table to commands
    # ---------------------------------------------------------------------------
    op.rename_table('tasks', 'commands')

    # ---------------------------------------------------------------------------
    # 2. Rename the sequence that backs commands.id
    # ---------------------------------------------------------------------------
    op.execute("ALTER SEQUENCE tasks_id_seq RENAME TO commands_id_seq")

    # ---------------------------------------------------------------------------
    # 3. Rename the primary key constraint and index
    # ---------------------------------------------------------------------------
    op.execute("ALTER INDEX tasks_pkey RENAME TO commands_pkey")

    # ---------------------------------------------------------------------------
    # 4. Rename the taskstate enum type to commandstate
    #    (PostgreSQL supports ALTER TYPE ... RENAME TO for the type name itself)
    # ---------------------------------------------------------------------------
    op.execute("ALTER TYPE taskstate RENAME TO commandstate")

    # ---------------------------------------------------------------------------
    # 5. Rename enum values in turnintent:
    #    The live DB has both 'end_of_task' (lowercase value) and 'END_OF_TASK'
    #    (uppercase name, added by migration a5b6c7d8e9f0).
    #    Both must be renamed to their command equivalents.
    #    Use DO blocks to handle cases where a value might not exist (fresh DB).
    # ---------------------------------------------------------------------------
    op.execute("""
        DO $$
        BEGIN
            ALTER TYPE turnintent RENAME VALUE 'end_of_task' TO 'end_of_command';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            ALTER TYPE turnintent RENAME VALUE 'END_OF_TASK' TO 'END_OF_COMMAND';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END $$;
    """)

    # ---------------------------------------------------------------------------
    # 6. Rename indexes on the commands table (formerly tasks)
    # ---------------------------------------------------------------------------
    op.execute("ALTER INDEX ix_tasks_agent_id RENAME TO ix_commands_agent_id")
    op.execute("ALTER INDEX ix_tasks_agent_id_state RENAME TO ix_commands_agent_id_state")
    op.execute("ALTER INDEX ix_tasks_state RENAME TO ix_commands_state")

    # ---------------------------------------------------------------------------
    # 7. Rename the FK constraint on commands (tasks_agent_id_fkey)
    # ---------------------------------------------------------------------------
    op.execute(
        "ALTER TABLE commands RENAME CONSTRAINT tasks_agent_id_fkey TO commands_agent_id_fkey"
    )

    # ---------------------------------------------------------------------------
    # 8. Rename the check constraint on commands
    # ---------------------------------------------------------------------------
    op.execute(
        "ALTER TABLE commands RENAME CONSTRAINT ck_tasks_completed_after_started "
        "TO ck_commands_completed_after_started"
    )

    # ---------------------------------------------------------------------------
    # 9. Rename task_id column in turns → command_id; update FK and indexes
    # ---------------------------------------------------------------------------
    op.alter_column('turns', 'task_id', new_column_name='command_id')
    op.execute("ALTER INDEX ix_turns_task_id RENAME TO ix_turns_command_id")
    op.execute("ALTER INDEX ix_turns_task_id_timestamp RENAME TO ix_turns_command_id_timestamp")
    op.execute("ALTER INDEX ix_turns_task_id_actor RENAME TO ix_turns_command_id_actor")
    op.execute(
        "ALTER TABLE turns RENAME CONSTRAINT turns_task_id_fkey TO turns_command_id_fkey"
    )

    # ---------------------------------------------------------------------------
    # 10. Rename task_id column in events → command_id; update FK and index
    # ---------------------------------------------------------------------------
    op.alter_column('events', 'task_id', new_column_name='command_id')
    op.execute("ALTER INDEX ix_events_task_id RENAME TO ix_events_command_id")
    op.execute(
        "ALTER TABLE events RENAME CONSTRAINT events_task_id_fkey TO events_command_id_fkey"
    )

    # ---------------------------------------------------------------------------
    # 11. Rename task_id column in inference_calls → command_id; update FK
    #     NOTE: There is no ix_inference_calls_task_id index — verified from
    #     migration history. The FK constraint is renamed.
    # ---------------------------------------------------------------------------
    op.alter_column('inference_calls', 'task_id', new_column_name='command_id')
    op.execute(
        "ALTER TABLE inference_calls RENAME CONSTRAINT "
        "inference_calls_task_id_fkey TO inference_calls_command_id_fkey"
    )

    # ---------------------------------------------------------------------------
    # 12. Drop and recreate the ck_inference_calls_has_parent check constraint
    #     to reference command_id instead of task_id
    # ---------------------------------------------------------------------------
    op.drop_constraint('ck_inference_calls_has_parent', 'inference_calls', type_='check')
    op.create_check_constraint(
        'ck_inference_calls_has_parent',
        'inference_calls',
        'COALESCE(project_id, agent_id, command_id, turn_id) IS NOT NULL',
    )

    # ---------------------------------------------------------------------------
    # 13. Update InferenceLevel varchar values: 'task' → 'command'
    #     (InferenceLevel is NOT a PostgreSQL enum — it is a String(20) column)
    # ---------------------------------------------------------------------------
    op.execute("UPDATE inference_calls SET level = 'command' WHERE level = 'task'")


def downgrade():
    # ---------------------------------------------------------------------------
    # Reverse all operations in reverse order
    # ---------------------------------------------------------------------------

    # 13. Revert InferenceLevel varchar values: 'command' → 'task'
    op.execute("UPDATE inference_calls SET level = 'task' WHERE level = 'command'")

    # 12. Drop and recreate ck_inference_calls_has_parent with task_id
    op.drop_constraint('ck_inference_calls_has_parent', 'inference_calls', type_='check')
    op.create_check_constraint(
        'ck_inference_calls_has_parent',
        'inference_calls',
        'COALESCE(project_id, agent_id, task_id, turn_id) IS NOT NULL',
    )

    # 11. Rename command_id → task_id in inference_calls; restore FK constraint
    op.execute(
        "ALTER TABLE inference_calls RENAME CONSTRAINT "
        "inference_calls_command_id_fkey TO inference_calls_task_id_fkey"
    )
    op.alter_column('inference_calls', 'command_id', new_column_name='task_id')

    # 10. Rename command_id → task_id in events; restore FK and index
    op.execute(
        "ALTER TABLE events RENAME CONSTRAINT events_command_id_fkey TO events_task_id_fkey"
    )
    op.execute("ALTER INDEX ix_events_command_id RENAME TO ix_events_task_id")
    op.alter_column('events', 'command_id', new_column_name='task_id')

    # 9. Rename command_id → task_id in turns; restore FK and indexes
    op.execute(
        "ALTER TABLE turns RENAME CONSTRAINT turns_command_id_fkey TO turns_task_id_fkey"
    )
    op.execute("ALTER INDEX ix_turns_command_id_actor RENAME TO ix_turns_task_id_actor")
    op.execute("ALTER INDEX ix_turns_command_id_timestamp RENAME TO ix_turns_task_id_timestamp")
    op.execute("ALTER INDEX ix_turns_command_id RENAME TO ix_turns_task_id")
    op.alter_column('turns', 'command_id', new_column_name='task_id')

    # 8. Restore check constraint name on commands table
    op.execute(
        "ALTER TABLE commands RENAME CONSTRAINT ck_commands_completed_after_started "
        "TO ck_tasks_completed_after_started"
    )

    # 7. Restore FK constraint name on commands table
    op.execute(
        "ALTER TABLE commands RENAME CONSTRAINT commands_agent_id_fkey TO tasks_agent_id_fkey"
    )

    # 6. Restore indexes on commands table
    op.execute("ALTER INDEX ix_commands_state RENAME TO ix_tasks_state")
    op.execute("ALTER INDEX ix_commands_agent_id_state RENAME TO ix_tasks_agent_id_state")
    op.execute("ALTER INDEX ix_commands_agent_id RENAME TO ix_tasks_agent_id")

    # 5. Restore turnintent enum values
    op.execute("""
        DO $$
        BEGIN
            ALTER TYPE turnintent RENAME VALUE 'END_OF_COMMAND' TO 'END_OF_TASK';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END $$;
    """)
    op.execute("""
        DO $$
        BEGIN
            ALTER TYPE turnintent RENAME VALUE 'end_of_command' TO 'end_of_task';
        EXCEPTION WHEN invalid_parameter_value THEN
            NULL;
        END $$;
    """)

    # 4. Restore commandstate enum type name to taskstate
    op.execute("ALTER TYPE commandstate RENAME TO taskstate")

    # 3. Restore PK constraint name
    op.execute("ALTER INDEX commands_pkey RENAME TO tasks_pkey")

    # 2. Restore sequence name
    op.execute("ALTER SEQUENCE commands_id_seq RENAME TO tasks_id_seq")

    # 1. Rename commands table back to tasks
    op.rename_table('commands', 'tasks')
