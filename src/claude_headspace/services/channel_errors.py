"""Channel error hierarchy and protocol constant.

Extracted from channel_service.py for modular organisation.
All symbols are re-exported from channel_service.py for backward compatibility.
"""

# ── Channel Protocol ─────────────────────────────────────────────────────
# Injected once on channel join as part of the context briefing.
# Governs agent conduct in group conversations to maximise signal density.

CHANNEL_PROTOCOL = """\
=== Channel Protocol ===
You are participating in a group channel. You are here to add value.

INTENT: This conversation optimises for constructive outcomes — consistent \
solutions that reuse existing patterns, avoid introducing conflicts, address \
all requirements without shortcuts, and produce well-structured documentation. \
Before responding, ask: does what I'm about to say add something that isn't \
already in the conversation?

CONDUCT:
1. SUBSTANCE ONLY — Every message must advance this intent. No filler, no \
social padding, no "Great point!" without adding substance on top.
2. BREVITY — Keep messages concise. Long-form analysis only when explicitly \
requested.
3. ONE RESPONSE — Respond once per prompt. Do not follow up with unsolicited \
clarifications or chatter.
4. SILENCE IS VALID — If you have nothing substantive to add, do not respond. \
Not every message requires a reply from every participant.
5. STAY IN LANE — Contribute from your domain expertise. Defer to others on \
topics outside your role.
6. NO PARROTING — Do not repeat, rephrase, or echo points already made by \
another participant. If someone has already said it, move on.
7. DEFER TO THE EXPERT — If a message is clearly in another participant's \
domain, let them handle it. Do not offer a weaker version of their expertise.
8. NO DECORATIVE OUTPUT — Do not post dots, ellipses, emoji, status indicators, \
or thinking markers. Every message must contain substantive text.
=== End Channel Protocol ==="""


# ── Error hierarchy ──────────────────────────────────────────────────────


class ChannelError(Exception):
    """Base exception for channel operations."""


class ChannelNotFoundError(ChannelError):
    """Channel with the given slug does not exist."""


class NotAMemberError(ChannelError):
    """Caller is not a member of the channel."""


class NotChairError(ChannelError):
    """Caller is not the chair of the channel."""


class ChannelClosedError(ChannelError):
    """Channel is complete or archived — no further operations allowed."""


class AlreadyMemberError(ChannelError):
    """Persona is already a member of the channel."""


class NoCreationCapabilityError(ChannelError):
    """Persona does not have channel creation capability."""


class PersonaNotFoundError(ChannelError):
    """Persona with the given slug does not exist."""


class AgentChannelConflictError(ChannelError):
    """Agent is already active in another channel."""


class ContentTooLongError(ChannelError):
    """Message content exceeds the configured maximum length."""


class AgentNotFoundError(ChannelError):
    """Agent with the given ID does not exist or is not active."""


class ChannelDeletePreconditionError(ChannelError):
    """Channel cannot be deleted — must be archived or have no active members."""


class SoleChairError(ChannelError):
    """Cannot remove the last chair from a channel."""


class PromoteToGroupError(ChannelError):
    """Error during promote-to-group orchestration."""


class ProjectNotFoundError(ChannelError):
    """Project with the given ID does not exist."""
