"""Cursor Adapter: invokes the ``cursor-agent`` CLI headlessly."""

from __future__ import annotations

import os
from pathlib import Path

from ..result import RESULT_PATH_ENV, result_instruction
from .base import AgentInvocation

CURSOR_BIN_ENV = "LOOPR_CURSOR_BIN"
DEFAULT_CURSOR_BIN = "cursor-agent"


class CursorAdapter:
    """Runs ``cursor-agent -p <mission>`` in the Workspace.

    The binary is overridable via $LOOPR_CURSOR_BIN so tests (and users with a
    non-standard install) can point at a different executable.
    """

    name = "cursor"

    def __init__(self, binary: str | None = None):
        self.binary = binary or os.environ.get(CURSOR_BIN_ENV, DEFAULT_CURSOR_BIN)

    def build_invocation(
        self, *, mission: str, workspace: Path, result_path: Path
    ) -> AgentInvocation:
        prompt = mission + result_instruction(result_path)
        return AgentInvocation(
            argv=[self.binary, "-p", prompt],
            cwd=Path(workspace),
            env={RESULT_PATH_ENV: str(result_path)},
        )
