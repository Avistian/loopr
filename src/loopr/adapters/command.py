"""Command Adapter: runs a plain command line in the Workspace.

Unlike the agent adapters, this does not spawn an AI agent — it executes the Loop's
``command`` directly (e.g. ``.venv/bin/python main.py --days 7``). Useful for
scheduling ordinary scripts alongside agent Loops. The command receives
``$LOOPR_RESULT_PATH`` in its environment so it *may* emit a structured Result, but
this is optional; a command that writes nothing there simply yields no Result.

The Loop's ``command`` string is passed in as ``mission`` by the firing layer and split
with ``shlex`` (POSIX rules). It is run without a shell, so pipes/redirects are not
interpreted — wrap those in a script if you need them.
"""

from __future__ import annotations

import shlex
from pathlib import Path

from ..result import RESULT_PATH_ENV
from .base import AgentInvocation


class CommandAdapter:
    name = "command"

    def build_invocation(
        self,
        *,
        mission: str,
        workspace: Path,
        result_path: Path,
        model: str | None = None,
    ) -> AgentInvocation:
        argv = shlex.split(mission)
        if not argv:
            raise ValueError("command loop has an empty command")
        return AgentInvocation(
            argv=argv,
            cwd=Path(workspace),
            env={RESULT_PATH_ENV: str(result_path)},
        )
