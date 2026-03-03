# Future Considerations & Backlog

Items that are architecturally significant but beyond the current epic horizon. These are tracked here for future planning — not committed to any timeline.

---

## 1. Agent Execution Sandboxing

**Added:** 2026-03-04
**Priority:** TBD (pre-requisite for public-facing agents)
**Scope:** Infrastructure / Security

### Problem

Any agent exposed to the public — or participating in agent-to-agent communication — needs execution isolation. Running arbitrary tool calls, shell commands, or file operations on a bare host is a security boundary violation when the input source is untrusted.

This applies to:
- **Public-facing agents** (e.g., Jen, any future customer-facing persona)
- **Agent-to-agent communication** (future inter-agent orchestration)
- **External conversations** (third-party integrations, API consumers)

### Concept

Sandboxed execution environments that isolate agent actions from the host system. The agent operates inside a contained runtime where it can read/write files, run commands, and use tools — but cannot escape to the host filesystem, network, or processes.

### Key Considerations

- **Not tied to a specific tool.** Alibaba's OpenSandbox is one option (open-source, FastAPI control plane, Docker/K8s runtimes, multi-language SDKs). Others exist. The concept matters more than the implementation.
- **Lifecycle management:** Spin up a sandbox per agent session, tear it down on session end.
- **Resource constraints:** CPU, memory, disk, network limits per sandbox.
- **Network policy:** What can a sandboxed agent reach? Internal APIs only? Public internet? Configurable per persona/role?
- **State persistence:** Does anything survive sandbox teardown? Conversation logs yes, filesystem artifacts maybe, runtime state no.
- **Tool passthrough:** How do MCP tools interact with the sandbox boundary? Some tools may need host access (e.g., database queries), others should be fully contained.
- **Latency budget:** Sandbox spin-up time affects agent responsiveness. Cold starts need to be fast enough for interactive use.
- **Observability:** Headspace needs visibility into what's happening inside the sandbox for monitoring, frustration detection, and audit.

### Relationship to Existing Architecture

- The **Remote Agents API** already creates agents for external consumers — sandboxing would wrap the execution layer beneath that.
- The **Persona system** could drive sandbox configuration — public-facing personas get sandboxed, internal personas don't.
- The **Platform Guardrails** handle information boundary enforcement at the prompt level — sandboxing enforces it at the infrastructure level. Defence in depth.

### Open Questions

1. Where does the sandbox boundary sit? Per-agent? Per-session? Per-tool-call?
2. Docker-based (simple, local) vs K8s-based (scalable, complex) vs hybrid?
3. How does the tmux bridge (current agent I/O mechanism) interact with a sandboxed agent?
4. Cost model for running sandboxed containers at scale?
5. Does this change the deployment model from "single Flask server" to something distributed?

### References

- [Alibaba OpenSandbox](https://github.com/alibaba/OpenSandbox) — open-source agent sandboxing infrastructure
- Anthropic's Cowork VM approach — proprietary but conceptually similar
- General container isolation patterns (gVisor, Firecracker, etc.)

---

*Add new items below this line using the same format.*
