"""Schedule parsing and next-fire computation.

Supports two forms (see CONTEXT.md: Trigger — schedule kind):

- **Intervals**: ``every 5m``, ``6h``, ``30s`` (units s/m/h/d)
- **Cron**: standard 5-field expressions like ``0 9 * * 1-5`` (via croniter)

Scheduling decisions use naive local ``datetime`` so cron expressions mean what a user
expects ("9am" = local 9am). Run timestamps are still stored in UTC elsewhere.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Protocol, runtime_checkable

from croniter import croniter

_UNIT_SECONDS = {"s": 1, "m": 60, "h": 3600, "d": 86400}
_INTERVAL_RE = re.compile(r"^\s*(?:every\s+)?(\d+)\s*([smhd])\s*$", re.IGNORECASE)


class ScheduleError(Exception):
    """Raised when a schedule string cannot be parsed."""


@runtime_checkable
class Schedule(Protocol):
    def next_after(self, dt: datetime) -> datetime: ...


@dataclass(frozen=True)
class IntervalSchedule:
    seconds: int

    def next_after(self, dt: datetime) -> datetime:
        return dt + timedelta(seconds=self.seconds)


@dataclass(frozen=True)
class CronSchedule:
    expression: str

    def next_after(self, dt: datetime) -> datetime:
        return croniter(self.expression, dt).get_next(datetime)


def parse_schedule(text: str) -> Schedule:
    if not isinstance(text, str) or not text.strip():
        raise ScheduleError("schedule must be a non-empty string")

    match = _INTERVAL_RE.match(text)
    if match:
        amount = int(match.group(1))
        if amount <= 0:
            raise ScheduleError(f"interval must be positive: {text!r}")
        unit = match.group(2).lower()
        return IntervalSchedule(seconds=amount * _UNIT_SECONDS[unit])

    expr = text.strip()
    if not croniter.is_valid(expr):
        raise ScheduleError(f"not a valid interval or cron expression: {text!r}")
    return CronSchedule(expression=expr)
