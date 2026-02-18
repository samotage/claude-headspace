"""Integration tests for summary field persistence on Turn and Command models."""

from datetime import datetime, timezone

import pytest

from claude_headspace.models.agent import Agent
from claude_headspace.models.project import Project
from claude_headspace.models.command import Command, CommandState
from claude_headspace.models.turn import Turn, TurnActor, TurnIntent


class TestTurnSummaryPersistence:

    def test_turn_created_without_summary(self, db_session):
        """Turn can be created with null summary fields."""
        project = Project(name="test-project", slug="test-project", path="/test/path")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Working on something",
        )
        db_session.add(turn)
        db_session.flush()

        fetched = db_session.get(Turn, turn.id)
        assert fetched.summary is None
        assert fetched.summary_generated_at is None

    def test_turn_summary_persisted(self, db_session):
        """Turn summary and timestamp can be set and persisted."""
        project = Project(name="test-project-2", slug="test-project-2", path="/test/path-2")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="11111111-2222-3333-4444-555555555555",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.PROGRESS,
            text="Refactoring auth middleware",
        )
        db_session.add(turn)
        db_session.flush()

        # Set summary
        now = datetime.now(timezone.utc)
        turn.summary = "Agent refactored the authentication middleware."
        turn.summary_generated_at = now
        db_session.flush()

        fetched = db_session.get(Turn, turn.id)
        assert fetched.summary == "Agent refactored the authentication middleware."
        assert fetched.summary_generated_at is not None

    def test_turn_summary_can_be_updated(self, db_session):
        """Turn summary can be overwritten."""
        project = Project(name="test-project-3", slug="test-project-3", path="/test/path-3")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="22222222-3333-4444-5555-666666666666",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        command = Command(agent_id=agent.id, state=CommandState.PROCESSING)
        db_session.add(command)
        db_session.flush()

        turn = Turn(
            command_id=command.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Fix the bug",
            summary="First summary",
            summary_generated_at=datetime.now(timezone.utc),
        )
        db_session.add(turn)
        db_session.flush()

        turn.summary = "Updated summary"
        db_session.flush()

        fetched = db_session.get(Turn, turn.id)
        assert fetched.summary == "Updated summary"


class TestCommandSummaryPersistence:

    def test_command_created_without_summary(self, db_session):
        """Command can be created with null summary fields."""
        project = Project(name="cmd-test-project", slug="cmd-test-project", path="/test/cmd-path")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="33333333-4444-5555-6666-777777777777",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        command = Command(agent_id=agent.id, state=CommandState.COMPLETE)
        db_session.add(command)
        db_session.flush()

        fetched = db_session.get(Command, command.id)
        assert fetched.completion_summary is None
        assert fetched.completion_summary_generated_at is None

    def test_command_summary_persisted(self, db_session):
        """Command summary and timestamp can be set and persisted."""
        project = Project(name="cmd-test-project-2", slug="cmd-test-project-2", path="/test/cmd-path-2")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="44444444-5555-6666-7777-888888888888",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        command = Command(
            agent_id=agent.id,
            state=CommandState.COMPLETE,
            completed_at=datetime.now(timezone.utc),
        )
        db_session.add(command)
        db_session.flush()

        # Set summary
        now = datetime.now(timezone.utc)
        command.completion_summary = "Implemented JWT auth with refresh tokens. All tests passing."
        command.completion_summary_generated_at = now
        db_session.flush()

        fetched = db_session.get(Command, command.id)
        assert fetched.completion_summary == "Implemented JWT auth with refresh tokens. All tests passing."
        assert fetched.completion_summary_generated_at is not None

    def test_command_summary_with_turns(self, db_session):
        """Command with turns can have summary persisted independently."""
        project = Project(name="cmd-test-project-3", slug="cmd-test-project-3", path="/test/cmd-path-3")
        db_session.add(project)
        db_session.flush()

        agent = Agent(
            session_uuid="55555555-6666-7777-8888-999999999999",
            project_id=project.id,
            started_at=datetime.now(timezone.utc),
            last_seen_at=datetime.now(timezone.utc),
        )
        db_session.add(agent)
        db_session.flush()

        command = Command(
            agent_id=agent.id,
            state=CommandState.COMPLETE,
            completed_at=datetime.now(timezone.utc),
            completion_summary="Command outcome summary",
            completion_summary_generated_at=datetime.now(timezone.utc),
        )
        db_session.add(command)
        db_session.flush()

        # Add turns with their own summaries
        turn1 = Turn(
            command_id=command.id,
            actor=TurnActor.USER,
            intent=TurnIntent.COMMAND,
            text="Fix the login bug",
            summary="User requested a login bug fix.",
            summary_generated_at=datetime.now(timezone.utc),
        )
        turn2 = Turn(
            command_id=command.id,
            actor=TurnActor.AGENT,
            intent=TurnIntent.COMPLETION,
            text="Fixed and tested",
            summary="Agent fixed and tested the login bug.",
            summary_generated_at=datetime.now(timezone.utc),
        )
        db_session.add_all([turn1, turn2])
        db_session.flush()

        fetched_command = db_session.get(Command, command.id)
        assert fetched_command.completion_summary == "Command outcome summary"
        assert len(fetched_command.turns) == 2
        assert fetched_command.turns[0].summary == "User requested a login bug fix."
        assert fetched_command.turns[1].summary == "Agent fixed and tested the login bug."
