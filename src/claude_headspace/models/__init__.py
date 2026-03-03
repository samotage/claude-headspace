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
    - ApiCallLog: External API request/response logging
    - ActivityMetric: Hourly activity metrics time-series
    - HeadspaceSnapshot: Headspace state snapshots (frustration, flow, alerts)
    - Organisation: Organisational grouping (active, dormant, archived)
    - Position: Org chart seat with self-referential hierarchy
    - Role: Agent specialisation lookup (developer, tester, pm, architect)
    - PersonaType: Persona classification lookup (agent/person x internal/external)
    - Persona: Named agent identity with role and slug
    - Handoff: Agent context handoff metadata
    - Channel: Named conversation container for inter-agent communication
    - ChannelMembership: Persona membership in a channel with mutable agent delivery
    - Message: Immutable message record in a channel

Enums:
    - CommandState: idle, commanded, processing, awaiting_input, complete
    - TurnActor: user, agent
    - TurnIntent: command, answer, question, completion, progress
    - InferenceLevel: turn, command, project, objective
    - AuthStatus: authenticated, failed, unauthenticated, bypassed
    - ChannelType: workshop, delegation, review, standup, broadcast
    - MessageType: message, system, delegation, escalation
"""

from .activity_metric import ActivityMetric
from .agent import Agent
from .api_call_log import ApiCallLog, AuthStatus
from .channel import Channel, ChannelType
from .channel_membership import ChannelMembership
from .command import Command, CommandState
from .event import Event, EventType
from .handoff import Handoff
from .headspace_snapshot import HeadspaceSnapshot
from .inference_call import InferenceCall, InferenceLevel
from .message import Message, MessageType
from .objective import Objective, ObjectiveHistory
from .organisation import Organisation
from .persona import Persona
from .persona_type import PersonaType
from .position import Position
from .project import Project
from .role import Role
from .turn import Turn, TurnActor, TurnIntent

__all__ = [
    # Models
    "ActivityMetric",
    "Agent",
    "ApiCallLog",
    "Channel",
    "ChannelMembership",
    "Command",
    "Event",
    "Handoff",
    "HeadspaceSnapshot",
    "InferenceCall",
    "Message",
    "Objective",
    "ObjectiveHistory",
    "Organisation",
    "Persona",
    "PersonaType",
    "Position",
    "Project",
    "Role",
    "Turn",
    # Enums
    "AuthStatus",
    "ChannelType",
    "CommandState",
    "InferenceLevel",
    "MessageType",
    "TurnActor",
    "TurnIntent",
    # Constants
    "EventType",
]
