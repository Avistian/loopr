"""Human Handoff via Notifications (see docs/adr/0003).

A human Handoff delivers the Result (summary + links to the Log and Artifacts) to a
channel and terminates the chain — Loopr never blocks waiting on a human. Channels are
pluggable; the CLI channel ships by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Protocol, runtime_checkable

from .result import Result


class NotifyError(Exception):
    """Raised when an unknown notification channel is requested."""


@dataclass(frozen=True)
class Notification:
    source: str
    channel: str
    result: Result | None = None
    run_id: int | None = None
    log_path: str | None = None
    artifacts: list = field(default_factory=list)

    def render(self) -> str:
        lines = [f"[loopr] handoff to human from loop {self.source!r}"]
        if self.result is not None:
            summary = f" — {self.result.summary}" if self.result.summary else ""
            lines.append(f"  result: {self.result.status}{summary}")
        if self.run_id is not None:
            lines.append(f"  run: {self.run_id}")
        if self.log_path:
            lines.append(f"  log: {self.log_path}")
        for artifact in self.artifacts:
            lines.append(f"  artifact: {artifact}")
        return "\n".join(lines)


@runtime_checkable
class Channel(Protocol):
    name: str

    def deliver(self, notification: Notification) -> None: ...


class CliChannel:
    """Prints the Notification to stdout."""

    name = "cli"

    def __init__(self, writer: Callable[[str], None] = print):
        self._writer = writer

    def deliver(self, notification: Notification) -> None:
        self._writer(notification.render())


_BUILDERS: dict[str, type[Channel]] = {
    CliChannel.name: CliChannel,
}


def known_channels() -> list[str]:
    return sorted(_BUILDERS)


def get_channel(name: str) -> Channel:
    try:
        return _BUILDERS[name]()
    except KeyError:
        known = ", ".join(known_channels())
        raise NotifyError(f"unknown channel {name!r}; known channels: {known}") from None


def deliver(notification: Notification) -> None:
    """Default notifier: resolve the channel by name and deliver."""
    get_channel(notification.channel).deliver(notification)
