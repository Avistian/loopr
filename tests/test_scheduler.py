from datetime import datetime, timedelta
from pathlib import Path

from loopr.config import Config, Loop
from loopr.db import Store
from loopr.scheduler import Scheduler


def make_config(tmp_path: Path, *loops: Loop) -> Config:
    return Config(loops={loop.name: loop for loop in loops}, source=tmp_path / "loopr.yaml")


def scheduled_loop(tmp_path: Path, name: str, schedule: str) -> Loop:
    ws = tmp_path / name
    ws.mkdir(exist_ok=True)
    return Loop(name=name, mission="m", workspace=ws, agent="cursor", schedule=schedule)


def test_only_scheduled_loops_tracked(tmp_path: Path):
    cfg = make_config(
        tmp_path,
        scheduled_loop(tmp_path, "a", "every 5m"),
        Loop(name="b", mission="m", workspace=tmp_path, agent="cursor"),  # no schedule
    )
    with Store(tmp_path / "home") as store:
        sched = Scheduler(cfg, store, runner=lambda loop, s: None)
        sched.initialize(datetime(2026, 1, 1, 9, 0, 0))
        assert set(sched.next_fire_times()) == {"a"}


def test_tick_fires_when_due(tmp_path: Path):
    cfg = make_config(tmp_path, scheduled_loop(tmp_path, "a", "every 5m"))
    fired: list[str] = []
    with Store(tmp_path / "home") as store:
        sched = Scheduler(cfg, store, runner=lambda loop, s: fired.append(loop.name))
        t0 = datetime(2026, 1, 1, 9, 0, 0)
        sched.initialize(t0)
        # not due yet at t0 + 1m
        assert sched.tick(t0 + timedelta(minutes=1)) == []
        assert fired == []
        # due at t0 + 5m
        assert sched.tick(t0 + timedelta(minutes=5)) == ["a"]
        assert fired == ["a"]


def test_tick_advances_next_fire(tmp_path: Path):
    cfg = make_config(tmp_path, scheduled_loop(tmp_path, "a", "every 5m"))
    with Store(tmp_path / "home") as store:
        sched = Scheduler(cfg, store, runner=lambda loop, s: None)
        t0 = datetime(2026, 1, 1, 9, 0, 0)
        sched.initialize(t0)
        sched.tick(t0 + timedelta(minutes=5))
        # next fire is strictly after the fire time
        assert sched.next_fire_times()["a"] == datetime(2026, 1, 1, 9, 10, 0)


def test_long_downtime_rolls_forward(tmp_path: Path):
    cfg = make_config(tmp_path, scheduled_loop(tmp_path, "a", "every 5m"))
    with Store(tmp_path / "home") as store:
        sched = Scheduler(cfg, store, runner=lambda loop, s: None)
        t0 = datetime(2026, 1, 1, 9, 0, 0)
        sched.initialize(t0)
        # tick far in the future: fires once, next fire is in the future (not the past)
        far = t0 + timedelta(hours=2)
        assert sched.tick(far) == ["a"]
        assert sched.next_fire_times()["a"] > far


def test_multiple_loops(tmp_path: Path):
    cfg = make_config(
        tmp_path,
        scheduled_loop(tmp_path, "fast", "every 1m"),
        scheduled_loop(tmp_path, "slow", "every 10m"),
    )
    fired: list[str] = []
    with Store(tmp_path / "home") as store:
        sched = Scheduler(cfg, store, runner=lambda loop, s: fired.append(loop.name))
        t0 = datetime(2026, 1, 1, 9, 0, 0)
        sched.initialize(t0)
        result = sched.tick(t0 + timedelta(minutes=1))
        assert result == ["fast"]
        assert "slow" not in result
