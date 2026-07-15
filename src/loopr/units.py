"""Generate OS autostart units for the Loopr daemon (see docs/adr/0002).

The generators are pure (easy to test); ``install_unit`` writes the file and returns the
path plus the command a user runs to enable it. Actually enabling/loading the unit is
left to the user (it requires systemctl/launchctl outside this process).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

SYSTEMD = "systemd"
LAUNCHD = "launchd"


@dataclass(frozen=True)
class InstalledUnit:
    kind: str
    path: Path
    enable_hint: str


def current_platform() -> str:
    return LAUNCHD if sys.platform == "darwin" else SYSTEMD


def systemd_unit(loopr_bin: str, config_path: Path) -> str:
    return (
        "[Unit]\n"
        "Description=Loopr agent scheduler\n"
        "After=network.target\n\n"
        "[Service]\n"
        "Type=simple\n"
        f"ExecStart={loopr_bin} daemon run --config {config_path}\n"
        "Restart=on-failure\n\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )


def launchd_plist(loopr_bin: str, config_path: Path) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
        '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
        '<plist version="1.0">\n'
        "<dict>\n"
        "  <key>Label</key><string>dev.loopr.daemon</string>\n"
        "  <key>ProgramArguments</key>\n"
        "  <array>\n"
        f"    <string>{loopr_bin}</string>\n"
        "    <string>daemon</string>\n"
        "    <string>run</string>\n"
        "    <string>--config</string>\n"
        f"    <string>{config_path}</string>\n"
        "  </array>\n"
        "  <key>RunAtLoad</key><true/>\n"
        "  <key>KeepAlive</key><true/>\n"
        "</dict>\n"
        "</plist>\n"
    )


def unit_target_path(kind: str, home: Path) -> Path:
    if kind == SYSTEMD:
        return home / ".config" / "systemd" / "user" / "loopr.service"
    return home / "Library" / "LaunchAgents" / "dev.loopr.daemon.plist"


def install_unit(
    config_path: Path,
    *,
    loopr_bin: str | None = None,
    home: Path | None = None,
    kind: str | None = None,
) -> InstalledUnit:
    kind = kind or current_platform()
    home = home or Path.home()
    loopr_bin = loopr_bin or (sys.argv[0] or "loopr")

    if kind == SYSTEMD:
        content = systemd_unit(loopr_bin, config_path)
        hint = "systemctl --user daemon-reload && systemctl --user enable --now loopr.service"
    elif kind == LAUNCHD:
        content = launchd_plist(loopr_bin, config_path)
        target = unit_target_path(kind, home)
        hint = f"launchctl load {target}"
    else:  # pragma: no cover - guarded by current_platform
        raise ValueError(f"unknown unit kind: {kind}")

    target = unit_target_path(kind, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return InstalledUnit(kind=kind, path=target, enable_hint=hint)
