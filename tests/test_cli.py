from pathlib import Path

from typer.testing import CliRunner

from loopr.cli import app

runner = CliRunner()


def setup_project(tmp_path: Path, *, mission: str = "hello-world") -> Path:
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = tmp_path / "loopr.yaml"
    cfg.write_text(
        f"""
loops:
  - name: mon
    mission: {mission}
    workspace: {ws}
    agent: cursor
"""
    )
    return cfg


def base_env(tmp_path: Path) -> dict[str, str]:
    # `echo` stands in for cursor-agent: it exits 0 and echoes its args into the Log.
    return {"LOOPR_HOME": str(tmp_path / "home"), "LOOPR_CURSOR_BIN": "echo"}


def test_run_then_runs_then_show(tmp_path: Path, monkeypatch):
    for k, v in base_env(tmp_path).items():
        monkeypatch.setenv(k, v)
    cfg = setup_project(tmp_path, mission="curate-news")

    result = runner.invoke(app, ["run", "mon", "--config", str(cfg)])
    assert result.exit_code == 0, result.output
    assert "success" in result.output

    listed = runner.invoke(app, ["runs"])
    assert listed.exit_code == 0
    assert "mon" in listed.output

    shown = runner.invoke(app, ["show", "1"])
    assert shown.exit_code == 0
    # echo printed "-p curate-news" into the Log
    assert "curate-news" in shown.output


def test_run_captures_and_shows_result(tmp_path: Path, monkeypatch):
    # A stand-in agent that honors $LOOPR_RESULT_PATH by writing a structured Result.
    agent = tmp_path / "fake-agent.sh"
    agent.write_text(
        '#!/bin/sh\n'
        'printf \'{"status":"ok","summary":"did it"}\' > "$LOOPR_RESULT_PATH"\n'
        'echo "agent ran"\n'
    )
    agent.chmod(0o755)

    monkeypatch.setenv("LOOPR_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("LOOPR_CURSOR_BIN", str(agent))
    cfg = setup_project(tmp_path)

    run_result = runner.invoke(app, ["run", "mon", "--config", str(cfg)])
    assert run_result.exit_code == 0, run_result.output

    shown = runner.invoke(app, ["show", "1"])
    assert shown.exit_code == 0
    assert "result: ok" in shown.output
    assert "did it" in shown.output


def test_run_unknown_loop_exits_2(tmp_path: Path, monkeypatch):
    for k, v in base_env(tmp_path).items():
        monkeypatch.setenv(k, v)
    cfg = setup_project(tmp_path)

    result = runner.invoke(app, ["run", "nope", "--config", str(cfg)])
    assert result.exit_code == 2
    assert "no Loop named" in result.output


def test_show_missing_run_exits_2(tmp_path: Path, monkeypatch):
    for k, v in base_env(tmp_path).items():
        monkeypatch.setenv(k, v)

    result = runner.invoke(app, ["show", "123"])
    assert result.exit_code == 2
    assert "no run with id" in result.output


def test_runs_empty(tmp_path: Path, monkeypatch):
    for k, v in base_env(tmp_path).items():
        monkeypatch.setenv(k, v)

    result = runner.invoke(app, ["runs"])
    assert result.exit_code == 0
    assert "no runs yet" in result.output


def scheduled_config(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    cfg = tmp_path / "loopr.yaml"
    cfg.write_text(
        f"""
loops:
  - name: mon
    mission: check
    workspace: {ws}
    agent: cursor
    schedule: "every 5m"
"""
    )
    return cfg


def test_daemon_status_not_running(tmp_path: Path, monkeypatch):
    for k, v in base_env(tmp_path).items():
        monkeypatch.setenv(k, v)
    cfg = scheduled_config(tmp_path)

    result = runner.invoke(app, ["daemon", "status", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "not running" in result.output
    assert "mon" in result.output  # listed under next firings


def test_daemon_install_writes_unit(tmp_path: Path, monkeypatch):
    for k, v in base_env(tmp_path).items():
        monkeypatch.setenv(k, v)
    monkeypatch.setenv("HOME", str(tmp_path / "fakehome"))
    cfg = scheduled_config(tmp_path)

    result = runner.invoke(app, ["daemon", "install", "--config", str(cfg)])
    assert result.exit_code == 0
    assert "unit:" in result.output
    assert "enable with" in result.output
