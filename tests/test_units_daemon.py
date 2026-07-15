import os
from pathlib import Path

from loopr.db import Store
from loopr.daemon import is_running, pid_file, read_pid
from loopr.units import (
    LAUNCHD,
    SYSTEMD,
    install_unit,
    launchd_plist,
    systemd_unit,
    unit_target_path,
)


def test_systemd_unit_content(tmp_path: Path):
    unit = systemd_unit("/usr/bin/loopr", tmp_path / "loopr.yaml")
    assert "ExecStart=/usr/bin/loopr daemon run --config" in unit
    assert "WantedBy=default.target" in unit


def test_launchd_plist_content(tmp_path: Path):
    plist = launchd_plist("/usr/bin/loopr", tmp_path / "loopr.yaml")
    assert "dev.loopr.daemon" in plist
    assert "<string>/usr/bin/loopr</string>" in plist


def test_install_systemd_writes_file(tmp_path: Path):
    home = tmp_path / "home"
    unit = install_unit(
        tmp_path / "loopr.yaml", loopr_bin="loopr", home=home, kind=SYSTEMD
    )
    assert unit.path == unit_target_path(SYSTEMD, home)
    assert unit.path.is_file()
    assert "systemctl --user" in unit.enable_hint


def test_install_launchd_writes_file(tmp_path: Path):
    home = tmp_path / "home"
    unit = install_unit(
        tmp_path / "loopr.yaml", loopr_bin="loopr", home=home, kind=LAUNCHD
    )
    assert unit.path == unit_target_path(LAUNCHD, home)
    assert unit.path.is_file()
    assert "launchctl load" in unit.enable_hint


def test_daemon_not_running_by_default(tmp_path: Path):
    with Store(tmp_path) as store:
        assert read_pid(store) is None
        assert is_running(store) is False


def test_daemon_detects_live_pid(tmp_path: Path):
    with Store(tmp_path) as store:
        pid_file(store).write_text(str(os.getpid()))
        assert read_pid(store) == os.getpid()
        assert is_running(store) is True


def test_daemon_detects_dead_pid(tmp_path: Path):
    with Store(tmp_path) as store:
        # PID 2^31-1 is essentially never a live process
        pid_file(store).write_text("2147483646")
        assert is_running(store) is False
