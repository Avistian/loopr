"""Agent Adapters.

An Adapter knows how to invoke one agent CLI headlessly (see CONTEXT.md: Adapter, and
docs/adr/0001). Issue 01 ships the Cursor Adapter; new agents (claude, codex) are added
by registering another builder here.
"""

from __future__ import annotations

from .base import Adapter, AgentInvocation
from .cursor import CursorAdapter


class AdapterError(Exception):
    """Raised when an unknown agent is requested."""


_BUILDERS: dict[str, type[Adapter]] = {
    CursorAdapter.name: CursorAdapter,
}


def get_adapter(name: str) -> Adapter:
    try:
        builder = _BUILDERS[name]
    except KeyError:
        known = ", ".join(sorted(_BUILDERS))
        raise AdapterError(f"unknown agent {name!r}; known agents: {known}") from None
    return builder()


def known_agents() -> list[str]:
    return sorted(_BUILDERS)


__all__ = [
    "Adapter",
    "AgentInvocation",
    "AdapterError",
    "CursorAdapter",
    "get_adapter",
    "known_agents",
]
