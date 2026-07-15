"""The Adapter contract."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class AgentInvocation:
    """A concrete headless agent process to spawn: argv + working directory."""

    argv: list[str]
    cwd: Path
    env: dict[str, str] | None = None


@runtime_checkable
class Adapter(Protocol):
    """Turns a Mission + Workspace into a spawnable agent process.

    The Adapter also arranges for the agent to emit a structured Result to
    ``result_path`` (issue 03) — typically by injecting an env var and appending the
    result protocol instruction to the Mission.
    """

    name: str

    def build_invocation(
        self, *, mission: str, workspace: Path, result_path: Path
    ) -> AgentInvocation: ...
