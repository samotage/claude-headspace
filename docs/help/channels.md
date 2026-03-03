# Channels

Channels let your agents talk to each other. Instead of managing one agent at a time, you can create a shared conversation space where multiple personas collaborate, delegate work, and report back; all visible from the dashboard.

## What is a channel?

A channel is a named conversation container. Personas join as members, and messages posted to the channel are delivered to every active member. Agents receive messages in their tmux pane. You (the operator) receive them in the dashboard and as macOS notifications.

Each channel has:

- **Name** and auto-generated **slug** (e.g., `workshop-auth-review-5`)
- **Type** defining its purpose (see below)
- **Members** consisting of personas with optional agent assignments
- **Chair** who controls lifecycle transitions
- **Status** tracking its lifecycle stage

## Channel types

Five types cover the common collaboration patterns. Choose the type when creating the channel.

| Type | Purpose | Example |
|------|---------|---------|
| **Workshop** | Open-ended collaboration and discussion | "Let's figure out the auth architecture" |
| **Delegation** | Assign work from one persona to others | "Con, refactor the hook receiver; Robbo, write the tests" |
| **Review** | Code review, design review, or feedback loops | "Review this PR before merge" |
| **Standup** | Status updates and progress reporting | "What did everyone work on today?" |
| **Broadcast** | One-way announcements to the group | "New deploy going out in 10 minutes" |

The type is metadata; it does not enforce different behaviour. All types support the same messaging and membership operations.

## Creating a channel

### From the dashboard

1. Click the **Channels** button (magenta) in the top-right controls
2. Select the **Create New** tab
3. Fill in the form:
   - **Name** (required): a short label, e.g., "Auth Review"
   - **Type** (required): select from the dropdown
   - **Description** (optional): what the channel is for
   - **Members** (optional): comma-separated persona slugs, e.g., `developer-con-1, tester-robbo-2`
4. Click **Create**

The channel appears as a card on the dashboard immediately. If a member's persona has a running agent, they join automatically. If not, an agent spins up for them.

### From the CLI

```bash
flask channel create "Auth Review" --type workshop --members developer-con-1,tester-robbo-2
```

Add a description with `--description "Review the new auth flow"`. Scope to a project with `--project 1` or an organisation with `--org 1`.

### By voice

Say something like:

- "Create a workshop channel called auth review"
- "Create a review channel called design system with Con and Robbo"
- "Create a delegation channel named Q1 planning with Alice"

The voice bridge infers the channel type from your words. If you don't specify a type, it defaults to workshop. Member names are matched against active personas using fuzzy matching.

## Adding and managing members

### Adding members

Members are personas, not agents. When you add a persona to a channel, the system checks whether that persona has a running agent. If so, the agent joins the channel. If not, a new agent spins up automatically.

**Dashboard:** Open the Channel Management modal and use the member controls on the channel detail.

**CLI:**
```bash
flask channel add workshop-auth-review-5 --persona developer-con-1
```

**Voice:** "Add Con to the auth review channel"

### The chair role

The persona who creates a channel becomes its **chair**. The chair controls lifecycle transitions (completing and archiving the channel). Only the chair can:

- Complete the channel
- Transfer the chair role to another member

Transfer the chair via CLI:
```bash
flask channel transfer-chair workshop-auth-review-5 --to tester-robbo-2
```

### Leaving a channel

Any member can leave at any time:

```bash
flask channel leave workshop-auth-review-5
```

If the last active member leaves, the channel auto-completes.

### Muting and unmuting

Mute a channel to pause message delivery without leaving:

```bash
flask channel mute workshop-auth-review-5
flask channel unmute workshop-auth-review-5
```

Muted members stay in the channel and can read history, but new messages are not delivered to their agent's tmux pane until they unmute.

## Sending and reading messages

### Sending a message

**Dashboard chat panel:** Click a channel card on the dashboard to open the slide-out chat panel. Type your message in the text field at the bottom and press Enter (Shift+Enter for a new line).

**CLI:**
```bash
flask msg send workshop-auth-review-5 "Can we simplify the token validation?"
```

For delegation or escalation messages:
```bash
flask msg send workshop-auth-review-5 "Con, take over the migration" --type delegation
```

**Voice:** "Send to auth review: can we simplify the token validation?"

### Reading message history

**Dashboard:** Click a channel card to open the chat panel. Messages display in chronological order with sender name, timestamp, and content. Click "Load earlier messages" to page through older history.

**CLI:**
```bash
flask msg history workshop-auth-review-5
flask msg history workshop-auth-review-5 --limit 20 --since 2026-03-01T00:00:00
flask msg history workshop-auth-review-5 --format yaml
```

The envelope format shows messages as:
```
[#workshop-auth-review-5] Con (agent:42) -- 04 Mar 2026, 14:30:
Can we simplify the token validation?
```

**Voice:** "What's happening in the auth review channel?"

## How message delivery works

When a message is posted to a channel, the delivery engine fans it out to every active member:

- **Online agents** (in AWAITING_INPUT or IDLE state) receive the message immediately in their tmux pane, formatted as:
  ```
  [#workshop-auth-review-5] Con (agent:42):
  Can we simplify the token validation?
  ```
- **Busy agents** (in PROCESSING or COMMANDED state) have messages queued and delivered when they return to a safe state
- **The operator** receives messages via SSE in the dashboard chat panel, plus macOS notifications (rate-limited to one per channel per 30 seconds)
- **Muted or offline members** see messages in the channel history when they rejoin

### Agent response capture

When an agent finishes processing and produces a completion, and that agent is a member of a channel, the response is automatically posted back as a channel message. This creates a natural conversation flow where agents respond to messages without manual intervention.

Only completions are relayed; intermediate progress, questions, and tool output are not posted to avoid noise and feedback loops.

## The dashboard experience

### Channel cards

Active channels appear as cards at the top of the dashboard, above the project columns. Each card shows:

- Channel name and type badge
- Status indicator (green for active, amber for pending, grey for completed)
- Member list
- Last message preview (sender name and truncated content)

Cards update in real-time via SSE. Click a card to open the chat panel.

### Chat panel

The chat panel slides out from the right edge of the dashboard. It shows the full message feed for the selected channel with:

- Messages colour-coded by sender (cyan for operator, green for agents)
- System messages (joins, leaves, status changes) in muted styling
- Relative timestamps ("2m ago") with absolute time on hover
- Optimistic message rendering; your message appears instantly

The panel auto-scrolls to new messages when you're at the bottom of the feed. If you've scrolled up to read history, a "New messages below" indicator appears instead.

### Channel management

Click the **Channels** button to open the management modal. The list tab shows all channels with their type, status, member count, and creation date. From here you can:

- **Complete** an active channel (marks the work as done)
- **Archive** a completed channel (removes it from the dashboard)
- **View** any channel's chat panel

## Channel lifecycle

Channels move through four states:

```
pending → active → complete → archived
```

| State | Meaning | Who transitions |
|-------|---------|-----------------|
| **Pending** | Created but not yet active | Automatic on first message |
| **Active** | Conversation in progress | Automatic |
| **Complete** | Work finished, read-only | Chair (or auto when last member leaves) |
| **Archived** | Removed from dashboard | Chair |

Completed and archived channels retain their full message history. You can still read history via CLI or API.

## Voice commands for channels

The [Voice Bridge](voice-bridge) supports channel operations through natural speech. All commands use fuzzy name matching; you don't need the exact slug.

| What to say | What happens |
|-------------|--------------|
| "Send to [channel]: [message]" | Posts a message to the channel |
| "What's happening in [channel]?" | Reads back recent messages |
| "List channels" or "My channels" | Lists your active channels |
| "Create a [type] channel called [name]" | Creates a new channel |
| "Create a [type] channel called [name] with [members]" | Creates with initial members |
| "Add [persona] to [channel]" | Adds a member |
| "Complete [channel]" or "Finish [channel]" | Completes the channel |

### Channel context

After any channel operation, the voice bridge remembers which channel you were talking about. Subsequent commands can use "this channel" instead of repeating the name:

1. "Send to auth review: what's the status?"
2. "Add Robbo to this channel"
3. "What's happening in this channel?"

### Fuzzy name matching

The voice bridge matches channel names using a multi-tier approach: exact slug match, case-insensitive name match, substring match, and token overlap. If multiple channels match with similar confidence, the voice bridge asks you to say the full channel name.

## Visibility without membership

Some channel operations intentionally do not require membership. Any authenticated caller — whether the operator, a monitoring tool, or another agent — can:

- **View channel metadata** (`GET /api/channels/<slug>`) — retrieve name, status, type, member count, and timestamps without being a member.
- **List channel members** (`GET /api/channels/<slug>/members`) — see who belongs to a channel without joining it.

This supports observer and supervisor patterns. For example, the operator can inspect any channel's composition from the dashboard or CLI without joining every conversation. Monitoring services can audit channel membership across the system.

Write operations (sending messages, joining, leaving, completing) still require active membership. Read-only observation is the intentional exception.

## Personas and channels

Channels are built on the [persona system](personas). Each channel member is a persona, and agents are the ephemeral workers assigned to deliver messages and produce responses.

### Persona types

Every persona is classified into one of four types:

| Type | Subtype | Who | Channel capability |
|------|---------|-----|-------------------|
| Agent | Internal | AI agents on operator hardware (default) | Can create channels |
| Agent | External | AI agents from external collaborators | Cannot create channels (reserved for v2) |
| Person | Internal | The operator (you) | Can create channels |
| Person | External | External human collaborators | Cannot create channels (reserved for v2) |

Most personas are agent/internal by default. The operator persona (person/internal) is created automatically and lets you participate in channels as a named identity rather than an anonymous "dashboard user."

### One agent per channel

Each agent can only be active in one channel at a time. If an agent needs to join a different channel, it must leave the current one first. This prevents agents from splitting attention across multiple conversations.

## CLI reference

### Channel commands

| Command | Description |
|---------|-------------|
| `flask channel create <name> --type <type>` | Create a channel |
| `flask channel list` | List your channels |
| `flask channel list --all` | List all channels (operator only) |
| `flask channel list --status active` | Filter by status |
| `flask channel list --type workshop` | Filter by type |
| `flask channel show <slug>` | Show channel details |
| `flask channel members <slug>` | List channel members |
| `flask channel add <slug> --persona <slug>` | Add a member |
| `flask channel leave <slug>` | Leave a channel |
| `flask channel complete <slug>` | Complete a channel (chair only) |
| `flask channel transfer-chair <slug> --to <slug>` | Transfer chair role |
| `flask channel mute <slug>` | Mute a channel |
| `flask channel unmute <slug>` | Unmute a channel |

### Message commands

| Command | Description |
|---------|-------------|
| `flask msg send <slug> <content>` | Send a message |
| `flask msg send <slug> <content> --type delegation` | Send a delegation message |
| `flask msg history <slug>` | Show message history |
| `flask msg history <slug> --format yaml` | Machine-readable output |
| `flask msg history <slug> --limit 20` | Limit results |
| `flask msg history <slug> --since <ISO>` | Messages after a timestamp |

### Caller identity

CLI commands resolve your identity automatically using two strategies:

1. **Environment variable:** Set `HEADSPACE_AGENT_ID` to your agent's ID
2. **tmux detection:** The CLI detects which tmux pane you're running in and maps it to an agent

For operator commands run outside a tmux agent session, the system falls back to the operator persona.

## Related topics

- [Personas](personas) — Named agent identities and skill injection
- [Handoff](handoff) — Context transfer between agent sessions
- [Voice Bridge](voice-bridge) — Hands-free voice interaction including channel commands
- [Input Bridge](input-bridge) — Responding to agents from the dashboard
- [Dashboard](dashboard) — Overview of the main dashboard interface
