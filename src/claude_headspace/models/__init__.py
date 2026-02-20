"""Database models package.

This package contains all SQLAlchemy model definitions for Claude Headspace.

Models:
    - Objective, ObjectiveHistory: Global objective and history tracking
    - Project: Monitored projects/codebases
    - Agent: Claude Code sessions
    - Command: Units of work with 5-state lifecycle
    - Turn: Individual exchanges (user <-> agent)
    - Event: Audit trail events
    - InferenceCall: LLM inference call logging
    - ActivityMetric: Hourly activity metrics time-series
    - HeadspaceSnapshot: Headspace state snapshots (frustration, flow, alerts)
    - Role: Agent specialisation lookup (developer, tester, pm, architect)
    - Persona: Named agent identity with role and slug

Enums:
    - CommandState: idle, commanded, processing, awaiting_input, complete
    - TurnActor: user, agent
    - TurnIntent: command, answer, question, completion, progress
    - InferenceLevel: turn, command, project, objective
"""

from .activity_metric import ActivityMetric
from .agent import Agent
from .headspace_snapshot import HeadspaceSnapshot
from .event import Event, EventType
from .inference_call import InferenceCall, InferenceLevel
from .objective import Objective, ObjectiveHistory
from .persona import Persona
from .project import Project
from .role import Role
from .command import Command, CommandState
from .turn import Turn, TurnActor, TurnIntent

__all__ = [
    # Models
    "ActivityMetric",
    "HeadspaceSnapshot",
    "Objective",
    "ObjectiveHistory",
    "Project",
    "Agent",
    "Command",
    "Turn",
    "Event",
    "InferenceCall",
    "Role",
    "Persona",
    # Enums
    "CommandState",
    "TurnActor",
    "TurnIntent",
    "InferenceLevel",
    # Constants
    "EventType",
]
