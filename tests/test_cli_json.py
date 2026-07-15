import json
from pathlib import Path

from typer.testing import CliRunner

from loopr.cli import app

runner = CliRunner()


def base_env(tmp_path: Path) -> dict[str, str]:
    return {"LOOPR_HOME": str(tmp_path / "home"), "LOOPR_CURSOR_BIN": "echo"}


def make_config(tmp_path: Path) -> Path:
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


def apply_env(monkeypatch, tmp_path):
    for k, v in base_env(tmp_path).items():
        monkeypatch.setenv(k, v)


def test_loop_list_json(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    result = runner.invoke(app, ["loop", "list", "--config", str(cfg), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data[0]["name"] == "mon"
    assert data[0]["schedule"] == "every 5m"


def test_runs_json_empty(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    result = runner.invoke(app, ["runs", "--json"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_daemon_status_json(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    result = runner.invoke(app, ["daemon", "status", "--config", str(cfg), "--json"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["running"] is False
    assert "mon" in data["next_firings"]


def test_loop_add_then_list(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    add = runner.invoke(
        app,
        [
            "loop", "add",
            "--name", "curator",
            "--mission", "curate news",
            "--workspace", str(tmp_path / "ws"),
            "--schedule", "every 1h",
            "--config", str(cfg),
            "--json",
        ],
    )
    assert add.exit_code == 0, add.output
    assert json.loads(add.output)["added"] == "curator"

    listed = runner.invoke(app, ["loop", "list", "--config", str(cfg), "--json"])
    names = {l["name"] for l in json.loads(listed.output)}
    assert names == {"mon", "curator"}


def test_loop_add_duplicate_errors_json(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    result = runner.invoke(
        app,
        [
            "loop", "add",
            "--name", "mon",
            "--mission", "x",
            "--workspace", str(tmp_path / "ws"),
            "--config", str(cfg),
            "--json",
        ],
    )
    assert result.exit_code == 2
    assert "already exists" in json.loads(result.output)["error"]


def test_loop_add_invalid_rolled_back(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    before = cfg.read_text()
    result = runner.invoke(
        app,
        [
            "loop", "add",
            "--name", "bad",
            "--mission", "x",
            "--workspace", str(tmp_path / "ws"),
            "--schedule", "not-a-schedule",
            "--config", str(cfg),
            "--json",
        ],
    )
    assert result.exit_code == 2
    assert "error" in json.loads(result.output)
    # config file is restored (rolled back)
    assert cfg.read_text() == before


def test_loop_disable_then_enable(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)

    disabled = runner.invoke(
        app, ["loop", "disable", "mon", "--config", str(cfg), "--json"]
    )
    assert disabled.exit_code == 0, disabled.output
    assert json.loads(disabled.output)["enabled"] is False

    listed = runner.invoke(app, ["loop", "list", "--config", str(cfg), "--json"])
    assert json.loads(listed.output)[0]["enabled"] is False

    # disabled loops drop out of the daemon's next firings
    status = runner.invoke(app, ["daemon", "status", "--config", str(cfg), "--json"])
    assert "mon" not in json.loads(status.output)["next_firings"]

    enabled = runner.invoke(
        app, ["loop", "enable", "mon", "--config", str(cfg), "--json"]
    )
    assert json.loads(enabled.output)["enabled"] is True
    status2 = runner.invoke(app, ["daemon", "status", "--config", str(cfg), "--json"])
    assert "mon" in json.loads(status2.output)["next_firings"]


def test_loop_disable_unknown_errors(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    result = runner.invoke(
        app, ["loop", "disable", "ghost", "--config", str(cfg), "--json"]
    )
    assert result.exit_code == 2
    assert "no loop named" in json.loads(result.output)["error"]


def test_loop_remove(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    result = runner.invoke(app, ["loop", "remove", "mon", "--config", str(cfg), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["removed"] == "mon"

    listed = runner.invoke(app, ["loop", "list", "--config", str(cfg), "--json"])
    assert json.loads(listed.output) == []


def test_loop_remove_unknown_errors(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    cfg = make_config(tmp_path)
    result = runner.invoke(app, ["loop", "remove", "ghost", "--config", str(cfg), "--json"])
    assert result.exit_code == 2
    assert "no loop named" in json.loads(result.output)["error"]


def test_loop_remove_refused_when_handoff_target(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    cfg = tmp_path / "loopr.yaml"
    cfg.write_text(
        f"""
loops:
  - name: monitor
    mission: check
    workspace: {ws}
    handoffs:
      - trigger: fixer
  - name: fixer
    mission: fix
    workspace: {ws}
"""
    )
    before = cfg.read_text()
    result = runner.invoke(app, ["loop", "remove", "fixer", "--config", str(cfg), "--json"])
    assert result.exit_code == 2
    assert "error" in json.loads(result.output)
    # rolled back: fixer still present
    assert cfg.read_text() == before


def test_run_json(tmp_path: Path, monkeypatch):
    apply_env(monkeypatch, tmp_path)
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
"""
    )
    runner.invoke(app, ["run", "mon", "--config", str(cfg)])
    result = runner.invoke(app, ["runs", "--json"])
    data = json.loads(result.output)
    assert data[0]["loop"] == "mon"
    assert data[0]["status"] == "success"

    shown = runner.invoke(app, ["show", str(data[0]["id"]), "--json"])
    show_data = json.loads(shown.output)
    assert "log" in show_data
