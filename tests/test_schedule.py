from datetime import datetime

import pytest

from loopr.schedule import (
    CronSchedule,
    IntervalSchedule,
    ScheduleError,
    parse_schedule,
)


def test_parse_interval_variants():
    assert parse_schedule("every 5m") == IntervalSchedule(300)
    assert parse_schedule("5m") == IntervalSchedule(300)
    assert parse_schedule("every 6h") == IntervalSchedule(6 * 3600)
    assert parse_schedule("30s") == IntervalSchedule(30)
    assert parse_schedule("2d") == IntervalSchedule(2 * 86400)


def test_interval_next_after():
    sched = parse_schedule("every 5m")
    base = datetime(2026, 1, 1, 9, 0, 0)
    assert sched.next_after(base) == datetime(2026, 1, 1, 9, 5, 0)


def test_parse_cron():
    sched = parse_schedule("0 9 * * 1-5")
    assert isinstance(sched, CronSchedule)


def test_cron_next_after_weekday_morning():
    sched = parse_schedule("0 9 * * 1-5")
    # Friday 2026-01-02 10:00 -> next is Monday 2026-01-05 09:00
    friday_10 = datetime(2026, 1, 2, 10, 0, 0)
    assert sched.next_after(friday_10) == datetime(2026, 1, 5, 9, 0, 0)


def test_zero_interval_rejected():
    with pytest.raises(ScheduleError):
        parse_schedule("0m")


def test_garbage_rejected():
    with pytest.raises(ScheduleError):
        parse_schedule("not a schedule")


def test_empty_rejected():
    with pytest.raises(ScheduleError):
        parse_schedule("")
