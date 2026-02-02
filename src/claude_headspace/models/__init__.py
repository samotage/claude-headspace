"""Database models package.

This package contains all SQLAlchemy model definitions for Claude Headspace.

Models:
    - Objective, ObjectiveHistory: Global objective and history tracking
    - Project: Monitored projects/codebases
    - Agent: Claude Code sessions
    - Task: Units of work with 5-state lifecycle
    - Turn: Individual exchanges (user ↔ agent)
    - Event: Audit trail events
    - InferenceCall: LLM inference call logging

Enums:
    - TaskState: idle, commanded, processing, awaiting_input, complete
    - TurnActor: user, agent
    - TurnIntent: command, answer, question, completion, progress
    - InferenceLevel: turn, task, project, objective
"""

from .agent import Agent
from .event import Event, EventType
from .inference_call import InferenceCall, InferenceLevel
from .objective import Objective, ObjectiveHistory
from .project import Project
from .task import Task, TaskState
from .turn import Turn, TurnActor, TurnIntent

__all__ = [
    # Models
    "Objective",
    "ObjectiveHistory",
    "Project",
    "Agent",
    "Task",
    "Turn",
    "Event",
    "InferenceCall",
    # Enums
    "TaskState",
    "TurnActor",
    "TurnIntent",
    "InferenceLevel",
    # Constants
    "EventType",
]
