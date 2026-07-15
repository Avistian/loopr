"""Daemon process lifecycle: pidfile management and the run loop.

The daemon is a foreground process (``loopr daemon run``) that hosts the Scheduler.
Autostart via systemd/launchd wraps this command (see units.py).
"""

from __future__ import annotations

import os
from pathlib import Path

from .config import Config
from .db import Store
from .scheduler import Scheduler
from .util import pid_alive


def pid_file(store: Store) -> Path:
    return store.home / "daemon.pid"


def read_pid(store: Store) -> int | None:
    path = pid_file(store)
    if not path.is_file():
        return None
    try:
        return int(path.read_text().strip())
    except ValueError:
        return None


def is_running(store: Store) -> bool:
    pid = read_pid(store)
    if pid is None:
        return False
    return pid_alive(pid)


def run_daemon(config: Config, store: Store, *, poll_seconds: float = 1.0) -> None:
    """Write the pidfile and run the scheduler until interrupted."""
    path = pid_file(store)
    path.write_text(str(os.getpid()))
    try:
        Scheduler(config, store).run_forever(poll_seconds=poll_seconds)
    finally:
        if path.is_file():
            path.unlink()
