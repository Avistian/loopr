"""The scheduling core (see docs/adr/0002).

``Scheduler`` owns which scheduled Loops are due and advances their next-fire times.
Time and the firing function are injected so the logic is testable without real sleeping
or real agents. The daemon (see daemon.py) wraps this in a poll loop.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Callable

from .config import Config, Loop
from .db import Store
from .handoff import fire_with_handoffs
from .schedule import Schedule, parse_schedule

Runner = Callable[[Loop, Store], object]
NowFn = Callable[[], datetime]


class Scheduler:
    def __init__(
        self,
        config: Config,
        store: Store,
        *,
        now_fn: NowFn = datetime.now,
        runner: Runner | None = None,
    ):
        self.config = config
        self.store = store
        self.now_fn = now_fn
        # By default a scheduled Firing runs the full Handoff chain.
        self.runner: Runner = runner or (
            lambda loop, store: fire_with_handoffs(loop, self.config, store)
        )
        # Only enabled Loops with a schedule are auto-fired; disabled Loops can still
        # be run manually or via Handoff.
        self._schedules: dict[str, Schedule] = {
            loop.name: parse_schedule(loop.schedule)
            for loop in config.loops.values()
            if loop.schedule and loop.enabled
        }
        self._next_fire: dict[str, datetime] = {}

    def initialize(self, now: datetime | None = None) -> None:
        now = now or self.now_fn()
        for name, sched in self._schedules.items():
            self._next_fire[name] = sched.next_after(now)

    def next_fire_times(self) -> dict[str, datetime]:
        return dict(self._next_fire)

    def tick(self, now: datetime | None = None) -> list[str]:
        """Fire all Loops due at ``now`` and advance their next-fire times."""
        if not self._next_fire:
            self.initialize(now)
            return []
        now = now or self.now_fn()
        fired: list[str] = []
        for name, when in list(self._next_fire.items()):
            if when <= now:
                self.runner(self.config.get_loop(name), self.store)
                fired.append(name)
                self._next_fire[name] = self._advance(name, now)
        return fired

    def _advance(self, name: str, now: datetime) -> datetime:
        sched = self._schedules[name]
        nxt = sched.next_after(now)
        while nxt <= now:
            nxt = sched.next_after(nxt)
        return nxt

    def run_forever(self, poll_seconds: float = 1.0, sleep: Callable[[float], None] = time.sleep) -> None:
        self.initialize()
        while True:
            self.tick()
            sleep(poll_seconds)
