"""Per-Workspace Lease acquisition (see docs/adr/0005).

A Lease serializes Firings within one Workspace: at most one active Firing per
Workspace, others wait. Different Workspaces are independent. Backed by the SQLite
store so the guard holds across processes (e.g. a manual `loopr run` vs the daemon).
"""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from typing import Callable, Iterator

from .db import Store


class LeaseTimeout(Exception):
    """Raised when a Workspace Lease could not be acquired within the timeout."""


def acquire(
    store: Store,
    workspace: str,
    run_id: int,
    *,
    timeout: float | None = None,
    poll: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    pid: int | None = None,
) -> bool:
    """Block until the Lease is acquired, or return False on timeout."""
    pid = pid if pid is not None else os.getpid()
    start = monotonic()
    while True:
        if store.try_acquire_lease(workspace, run_id, pid):
            return True
        if timeout is not None and (monotonic() - start) >= timeout:
            return False
        sleep(poll)


@contextmanager
def workspace_lease(
    store: Store,
    workspace: str,
    run_id: int,
    *,
    timeout: float | None = None,
    poll: float = 0.1,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
    pid: int | None = None,
) -> Iterator[None]:
    if not acquire(
        store,
        workspace,
        run_id,
        timeout=timeout,
        poll=poll,
        sleep=sleep,
        monotonic=monotonic,
        pid=pid,
    ):
        raise LeaseTimeout(f"could not acquire lease for workspace {workspace!r}")
    try:
        yield
    finally:
        store.release_lease(workspace, run_id)
