"""End-to-end tests that exercise the installed ``loopr`` CLI as a subprocess.

These are distinct from the CliRunner unit tests: they go through the console
entry point, a real process boundary, and the agent's own environment.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.e2e

# Resolve the console script from the same venv that runs pytest.
LOOPR_BIN = shutil.which("loopr") or str(
    Path(sys.executable).resolve().parent / "loopr"
)


@pytest.fixture
def home(tmp_path: Path) -> Path:
    """Isolated LOOPR_HOME so e2e runs never touch ~/.loopr."""
    h = tmp_path / "home"
    h.mkdir()
    return h


@pytest.fixture
def env(home: Path) -> dict[str, str]:
    e = os.environ.copy()
    e["LOOPR_HOME"] = str(home)
    # Stand-in for cursor-agent when a test uses agent: cursor.
    e["LOOPR_CURSOR_BIN"] = "echo"
    return e


def loopr(*args: str, env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    assert Path(LOOPR_BIN).exists(), f"loopr binary not found at {LOOPR_BIN}"
    result = subprocess.run(
        [LOOPR_BIN, *args],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"loopr {' '.join(args)} exited {result.returncode}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def make_result_script(tmp_path: Path, name: str, status: str, summary: str) -> str:
    """Write a tiny agent stand-in; return a ``command:`` line that runs it."""
    script = tmp_path / name
    script.write_text(
        textwrap.dedent(
            f"""\
            import json, os, sys
            path = os.environ["LOOPR_RESULT_PATH"]
            open(path, "w").write(json.dumps({{"status": {status!r}, "summary": {summary!r}}}))
            sys.stdout.write({summary!r})
            """
        )
    )
    # shlex.split on the Loop command; quote paths for spaces.
    return f'"{sys.executable}" "{script}"'


def write_config(tmp_path: Path, loops: list[dict]) -> Path:
    cfg = tmp_path / "loopr.yaml"
    cfg.write_text(yaml.safe_dump({"loops": loops}, sort_keys=False))
    return cfg


def test_help_lists_core_commands(env: dict[str, str]):
    result = loopr("--help", env=env)
    out = result.stdout
    assert "Fire a Loop once" in out or "run" in out
    for cmd in ("run", "runs", "show", "daemon", "loop"):
        assert cmd in out


def test_fire_command_loop_then_inspect_run(tmp_path: Path, env: dict[str, str]):
    ws = tmp_path / "ws"
    ws.mkdir()
    agent = make_result_script(tmp_path, "send.py", "ok", "newsletter sent")
    cfg = write_config(
        tmp_path,
        [
            {
                "name": "weekly",
                "workspace": str(ws),
                "agent": "command",
                "command": agent,
            }
        ],
    )

    fired = loopr("run", "weekly", "--config", str(cfg), env=env)
    assert "weekly" in fired.stdout
    assert "success" in fired.stdout

    listed = loopr("runs", "--json", env=env)
    runs = json.loads(listed.stdout)
    assert len(runs) == 1
    assert runs[0]["loop"] == "weekly"
    assert runs[0]["status"] == "success"
    assert runs[0]["result_status"] == "ok"
    assert runs[0]["result_summary"] == "newsletter sent"

    shown = loopr("show", str(runs[0]["id"]), "--json", env=env)
    detail = json.loads(shown.stdout)
    assert detail["result_status"] == "ok"
    assert "newsletter sent" in detail["log"]


def test_handoff_chain_fires_downstream_loop(tmp_path: Path, env: dict[str, str]):
    ws = tmp_path / "ws"
    ws.mkdir()
    radar = make_result_script(tmp_path, "radar.py", "staged", "staged 2 papers")
    review = make_result_script(tmp_path, "review.py", "ok", "reviewed 2 papers")
    cfg = write_config(
        tmp_path,
        [
            {
                "name": "radar",
                "workspace": str(ws),
                "agent": "command",
                "command": radar,
                "handoffs": [
                    {"when": 'result.status == "staged"', "trigger": "review"},
                ],
            },
            {
                "name": "review",
                "workspace": str(ws),
                "agent": "command",
                "command": review,
            },
        ],
    )

    loopr("run", "radar", "--config", str(cfg), env=env)

    listed = loopr("runs", "--json", env=env)
    runs = json.loads(listed.stdout)
    names = [r["loop"] for r in runs]
    # Newest first.
    assert names == ["review", "radar"]
    by_name = {r["loop"]: r for r in runs}
    assert by_name["radar"]["result_status"] == "staged"
    assert by_name["review"]["result_status"] == "ok"


def test_loop_lifecycle_via_cli(tmp_path: Path, env: dict[str, str]):
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = write_config(
        tmp_path,
        [
            {
                "name": "mon",
                "mission": "check dashboards",
                "workspace": str(ws),
                "agent": "cursor",
                "schedule": "every 5m",
            }
        ],
    )

    listed = loopr("loop", "list", "--config", str(cfg), "--json", env=env)
    assert json.loads(listed.stdout)[0]["name"] == "mon"

    loopr(
        "loop",
        "add",
        "--name",
        "fixer",
        "--mission",
        "fix issues",
        "--workspace",
        str(ws),
        "--config",
        str(cfg),
        "--json",
        env=env,
    )
    names = {
        l["name"]
        for l in json.loads(
            loopr("loop", "list", "--config", str(cfg), "--json", env=env).stdout
        )
    }
    assert names == {"mon", "fixer"}

    loopr("loop", "disable", "mon", "--config", str(cfg), "--json", env=env)
    status = json.loads(
        loopr("daemon", "status", "--config", str(cfg), "--json", env=env).stdout
    )
    assert status["running"] is False
    assert "mon" not in status["next_firings"]

    loopr("loop", "enable", "mon", "--config", str(cfg), "--json", env=env)
    status = json.loads(
        loopr("daemon", "status", "--config", str(cfg), "--json", env=env).stdout
    )
    assert "mon" in status["next_firings"]
