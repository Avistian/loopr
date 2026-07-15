import os
from pathlib import Path

import pytest

from loopr.db import Store
from loopr.lease import LeaseTimeout, acquire, workspace_lease


def test_acquire_and_release(tmp_path: Path):
    with Store(tmp_path) as store:
        assert store.try_acquire_lease("/ws", run_id=1, pid=os.getpid())
        assert [l.workspace for l in store.active_leases()] == ["/ws"]
        assert store.release_lease("/ws", run_id=1)
        assert store.active_leases() == []


def test_live_holder_blocks_other(tmp_path: Path):
    # Two Store connections on the same home simulate two processes.
    with Store(tmp_path) as a, Store(tmp_path) as b:
        assert a.try_acquire_lease("/ws", run_id=1, pid=os.getpid())
        # different run, live holder (this very process) -> denied
        assert b.try_acquire_lease("/ws", run_id=2, pid=os.getpid()) is False


def test_reentrant_same_run(tmp_path: Path):
    with Store(tmp_path) as store:
        assert store.try_acquire_lease("/ws", run_id=1, pid=os.getpid())
        assert store.try_acquire_lease("/ws", run_id=1, pid=os.getpid()) is True


def test_stale_holder_is_stolen(tmp_path: Path):
    with Store(tmp_path) as store:
        dead_pid = 2147483646
        assert store.try_acquire_lease("/ws", run_id=1, pid=dead_pid)
        # holder is dead -> a new run can steal it
        assert store.try_acquire_lease("/ws", run_id=2, pid=os.getpid()) is True
        lease = store.active_leases()[0]
        assert lease.run_id == 2


def test_different_workspaces_independent(tmp_path: Path):
    with Store(tmp_path) as store:
        assert store.try_acquire_lease("/ws-a", run_id=1, pid=os.getpid())
        assert store.try_acquire_lease("/ws-b", run_id=2, pid=os.getpid())


def test_acquire_times_out_when_held(tmp_path: Path):
    fake_time = [0.0]

    def monotonic():
        return fake_time[0]

    def sleep(seconds):
        fake_time[0] += seconds

    with Store(tmp_path) as store:
        store.try_acquire_lease("/ws", run_id=1, pid=os.getpid())
        got = acquire(
            store,
            "/ws",
            run_id=2,
            timeout=1.0,
            poll=0.5,
            sleep=sleep,
            monotonic=monotonic,
        )
        assert got is False


def test_context_manager_releases(tmp_path: Path):
    with Store(tmp_path) as store:
        with workspace_lease(store, "/ws", run_id=1):
            assert store.active_leases()[0].workspace == "/ws"
        assert store.active_leases() == []


def test_context_manager_timeout_raises(tmp_path: Path):
    with Store(tmp_path) as store:
        store.try_acquire_lease("/ws", run_id=1, pid=os.getpid())
        with pytest.raises(LeaseTimeout):
            with workspace_lease(store, "/ws", run_id=2, timeout=0.0):
                pass
