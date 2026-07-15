"""Cursor Adapter: invokes the ``cursor-agent`` CLI headlessly."""

from __future__ import annotations

import os
from pathlib import Path

from ..result import RESULT_PATH_ENV, result_instruction
from .base import AgentInvocation

CURSOR_BIN_ENV = "LOOPR_CURSOR_BIN"
DEFAULT_CURSOR_BIN = "cursor-agent"


class CursorAdapter:
    """Runs ``cursor-agent`` headlessly in the Workspace.

    Uses ``-p`` (print/non-interactive) and ``--force`` so the unattended agent may
    write files and run shell commands (e.g. git push) without confirmation. Output is
    requested as ``stream-json`` so the Log captures the agent's activity (messages and
    tool calls) as it happens, which lets ``loopr logs -f`` show a live view of a Firing.
    The model is pinned with ``--model`` when the Loop declares one. The binary is
    overridable via $LOOPR_CURSOR_BIN so tests (and non-standard installs) can point
    elsewhere.
    """

    name = "cursor"

    def __init__(self, binary: str | None = None):
        self.binary = binary or os.environ.get(CURSOR_BIN_ENV, DEFAULT_CURSOR_BIN)

    def build_invocation(
        self,
        *,
        mission: str,
        workspace: Path,
        result_path: Path,
        model: str | None = None,
    ) -> AgentInvocation:
        prompt = mission + result_instruction(result_path)
        argv = [self.binary, "-p", "--force", "--output-format", "stream-json"]
        if model:
            argv += ["--model", model]
        argv.append(prompt)
        return AgentInvocation(
            argv=argv,
            cwd=Path(workspace),
            env={RESULT_PATH_ENV: str(result_path)},
        )
