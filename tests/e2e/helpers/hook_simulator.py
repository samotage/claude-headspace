"""Hook simulator for E2E tests.

Wraps HTTP POSTs to Claude Headspace hook endpoints, simulating
the lifecycle events that Claude Code sends during a session.
"""

import requests


class HookSimulator:
    """Simulates Claude Code hook events via HTTP POST."""

    def __init__(self, base_url: str, session_id: str, working_directory: str):
        self.base_url = base_url
        self.session_id = session_id
        self.working_directory = working_directory
        self._last_agent_id: int | None = None

    def _post(self, endpoint: str, extra: dict | None = None) -> dict:
        """Send a hook POST and return parsed JSON."""
        payload = {
            "session_id": self.session_id,
            "working_directory": self.working_directory,
        }
        if extra:
            payload.update(extra)

        resp = requests.post(
            f"{self.base_url}{endpoint}",
            json=payload,
            timeout=10,
        )
        assert resp.status_code == 200, (
            f"{endpoint} returned {resp.status_code}: {resp.text}"
        )
        data = resp.json()
        if "agent_id" in data:
            self._last_agent_id = data["agent_id"]
        return data

    def session_start(self) -> dict:
        """POST /hook/session-start"""
        return self._post("/hook/session-start")

    def user_prompt_submit(self, prompt: str = "Test command") -> dict:
        """POST /hook/user-prompt-submit"""
        return self._post("/hook/user-prompt-submit", {"prompt": prompt})

    def stop(self) -> dict:
        """POST /hook/stop"""
        return self._post("/hook/stop")

    def notification(self) -> dict:
        """POST /hook/notification"""
        return self._post("/hook/notification")

    def session_end(self) -> dict:
        """POST /hook/session-end"""
        return self._post("/hook/session-end")

    def get_agent_id(self) -> int | None:
        """Return the agent_id from the most recent response."""
        return self._last_agent_id
