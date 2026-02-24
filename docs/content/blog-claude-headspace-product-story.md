# What happens when you run six AI agents at once

You open a terminal. You spin up a Claude Code agent to refactor the auth module. Another one is already running tests on the event system. A third is building a new API endpoint. You check your second project; two more agents are active there. One seems stuck. You think.

This is the state of AI-assisted development in 2026. The agents are capable. The bottleneck is you, trying to remember what each one is doing, which ones need input, and whether any of them have quietly gone off the rails.

Claude Headspace exists because I hit that wall.

## The problem nobody talks about

AI coding agents have gotten remarkably good at executing tasks. The tooling around managing them has not kept pace. When you run multiple Claude Code sessions across multiple projects, you end up with a collection of terminal windows and no coherent view of what's happening.

Questions that should be trivial become expensive:

- Which agent just finished its task?
- Is that agent stuck waiting for my input, or still working?
- Did the one on the billing service actually make progress, or has it been spinning for twenty minutes?
- What was agent #3 even working on?

You alt-tab between terminals. You scroll through output. You lose context. You interrupt flow to check on agents that were fine, and miss the one that actually needed you.

## A dashboard that knows what your agents are doing

Claude Headspace is a real-time web dashboard that monitors Claude Code sessions across all your projects. Every agent gets a card. Every card shows what that agent is working on, what state it's in, and whether it needs your attention.

The architecture hooks directly into Claude Code's lifecycle events. Eight hook types fire from every Claude Code session: session start, session end, user prompt, tool use (pre and post), stop events, notifications, and permission requests. The dashboard receives these events, correlates them to agents, and maintains a live state model.

Each agent tracks through five states: idle, commanded (you gave it a task), processing (it's working), awaiting input (it needs something from you), and complete. State transitions happen automatically based on the hook events and an intent detection pipeline that classifies each exchange.

The result: you glance at the dashboard and know, in seconds, what every agent across every project is doing right now.

## Click a card, focus the terminal

The dashboard integrates with iTerm2 through AppleScript. Click an agent's card; its terminal window comes to the foreground. No hunting through tabs, no guessing which window belongs to which session.

For agents running in tmux (which most of mine do), the integration goes deeper. The dashboard knows which tmux pane each agent lives in, tracks pane availability in the background, and can attach directly to the right session.

## AI-powered summaries instead of raw output

Raw terminal output is noisy. Nobody wants to read 200 lines of tool calls to figure out what happened. Claude Headspace runs each exchange through an LLM summarisation layer.

Individual turns get one-to-two sentence summaries. Completed tasks get two-to-three sentence completion summaries that capture what was accomplished. The dashboard cards show these summaries instead of raw output, which means you can scan six agents in the time it used to take to check one.

The summarisation runs through OpenRouter with content-based caching, rate limiting, and cost tracking. Turn-level summaries use a fast model (Haiku). Project-level analysis uses a more capable model (Sonnet). The system tracks every inference call, so you always know what you're spending.

## Priority scoring across projects

When you have agents working across multiple projects, a natural question emerges: which one matters most right now?

Claude Headspace answers this with cross-project priority scoring. You set a global objective ("ship the auth overhaul by Friday"), and the system scores each active agent 0-100 based on how closely their current work aligns with that objective. The scores update automatically. The dashboard sorts by priority.

This turns "I have six agents running" into "agent 4 is doing the most important work, and agent 2 needs my input to unblock something on the critical path."

## It watches you too

Here's where it gets interesting.

Every user turn gets a frustration score from 0 to 10. The headspace monitor tracks rolling averages across three windows: last 10 turns, last 30 minutes, and last 3 hours. When frustration trends upward, the dashboard shifts from green to yellow to red. You get a traffic-light indicator for your own state of mind.

The system also detects flow state. Long stretches of productive, low-frustration interaction get recognised. The dashboard celebrates these instead of interrupting them.

This sounds like a gimmick until you've been debugging a stubborn issue for an hour and the dashboard quietly turns yellow. In practice, the detection works surprisingly well. It picks up on the shift in tone when you start repeating yourself, asking terse questions, or pasting the same error for the third time. That signal, external to your own frustrated tunnel vision, is genuinely useful. It's the equivalent of a colleague noticing you've been banging your head against the wall and suggesting you take a walk. The scoring still needs refinement, but even in its current form it surfaces patterns you wouldn't notice on your own.

## Talk to your agents from your phone

The voice bridge (Epics 5 and 6) adds a mobile-first interface for interacting with agents. It's a Progressive Web App that connects to the same backend, shows the same agent state, and lets you send commands and responses through a chat-style interface.

The interaction flows through tmux. You type (or dictate) a message on your phone. The voice bridge sends it to the server. The server injects it into the correct tmux pane via `send-keys`. The agent receives it as if you typed it at the terminal.

File and image sharing works too. You can send screenshots from your phone to an agent that needs visual context.

The practical upside: you can step away from your desk while agents work, and handle the "awaiting input" moments from wherever you are.

## Agents with names and skills

The most recent major feature (Epic 8) introduces personas. Instead of tracking "Agent session 47a2f," the dashboard shows "Robbo is working on the architecture review."

Each persona has a name, a defined role, and a skill file that persists across sessions. I named mine deliberately to give them real human context: Robbo is the architect who thinks in systems and produces specifications. Gavin is the PM who decomposes work and sequences tasks. Con handles backend engineering. Al does frontend work. You work differently with an agent when it has a name and a defined way of thinking.

Personas aren't cosmetic labels. The skill file gets injected into the agent's context when a session starts, giving it persistent knowledge and behavioral patterns that accumulate over time. When an agent's context window fills up and it needs to hand off work, the handoff protocol captures what was accomplished, what's remaining, and transfers it to a fresh session with the same persona loaded.

The organisation model underneath supports hierarchical team structures, so you can model the way work actually flows: architect produces specs, PM breaks them into tasks, engineers execute, QA validates.

## How it's built

Claude Headspace is a Flask application with 22 blueprints, 40+ service modules, and 15 domain models backed by PostgreSQL. The frontend is vanilla JavaScript with Tailwind CSS and Server-Sent Events for real-time updates. No framework dependencies on the client side.

The service architecture uses dependency injection through Flask's `app.extensions` dictionary. Services register at startup and access each other through the app context. Background threads handle agent reaping (cleaning up inactive sessions), activity aggregation (hourly metrics), and tmux availability checking.

The LLM integration layer includes content-based caching with a 5-minute TTL, sliding-window rate limiting (calls per minute and tokens per minute), automatic retry with backoff, and per-call cost tracking. Every inference call gets logged with its model, token counts, latency, and purpose.

The whole thing runs on a single machine with TLS via Tailscale. It's a development tool, built for a developer, running alongside the work it monitors.

## 462 commits in three months

Claude Headspace itself was built primarily with Claude Code. The development followed a structured epic-and-sprint model: 8 epics, 65 PRDs across 13 subsystems, 33 merged pull requests, all driven by an orchestration pipeline that takes PRDs through workshop, proposal, build, test, and validation phases.

The irony is intentional and productive. Building a tool that monitors AI agents, using AI agents, creates a feedback loop. The tool gets better at tracking the agents building it. The agents get better-monitored as the tool improves. Rough edges in the developer experience surface immediately because the developer is the user.

## Where this goes

The current version focuses on software development. The architecture supports broader applications. The organisation model, workflow engine, and persona system are designed to handle different operational patterns: pipeline workflows for dev teams, iterative loops for marketing, continuous production for services, engagement workflows for consulting.

The core insight remains the same regardless of domain: when you work with multiple AI agents, you need a layer between you and them that handles the coordination, summarisation, and prioritisation that your brain used to do manually. Claude Headspace is that layer.

The code is at [github.com/samotage/claude_headspace](https://github.com/samotage/claude_headspace).
