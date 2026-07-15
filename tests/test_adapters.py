from pathlib import Path

import pytest

from loopr.adapters import (
    AdapterError,
    AgentInvocation,
    CommandAdapter,
    CursorAdapter,
    get_adapter,
    known_agents,
)
from loopr.adapters.base import Adapter


def test_cursor_adapter_builds_invocation(tmp_path: Path):
    adapter = CursorAdapter(binary="cursor-agent")
    result_path = tmp_path / "r.json"
    inv = adapter.build_invocation(
        mission="do the thing", workspace=tmp_path, result_path=result_path
    )
    assert isinstance(inv, AgentInvocation)
    assert inv.argv[0] == "cursor-agent"
    # headless + auto-approve so the unattended agent can write & run commands
    assert "-p" in inv.argv
    assert "--force" in inv.argv
    # stream-json so the Log captures live activity for `loopr logs -f`
    assert inv.argv[inv.argv.index("--output-format") + 1] == "stream-json"
    # last arg is the prompt: mission plus the result-protocol instruction
    assert inv.argv[-1].startswith("do the thing")
    assert str(result_path) in inv.argv[-1]
    assert inv.cwd == tmp_path
    assert inv.env is not None and inv.env["LOOPR_RESULT_PATH"] == str(result_path)


def test_cursor_adapter_passes_model(tmp_path: Path):
    adapter = CursorAdapter(binary="cursor-agent")
    inv = adapter.build_invocation(
        mission="m", workspace=tmp_path, result_path=tmp_path / "r.json", model="opus-4.8"
    )
    assert "--model" in inv.argv
    assert inv.argv[inv.argv.index("--model") + 1] == "opus-4.8"


def test_cursor_adapter_omits_model_when_none(tmp_path: Path):
    adapter = CursorAdapter(binary="cursor-agent")
    inv = adapter.build_invocation(
        mission="m", workspace=tmp_path, result_path=tmp_path / "r.json"
    )
    assert "--model" not in inv.argv


def test_cursor_binary_env_override(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("LOOPR_CURSOR_BIN", "/opt/echo")
    adapter = CursorAdapter()
    inv = adapter.build_invocation(
        mission="m", workspace=tmp_path, result_path=tmp_path / "r.json"
    )
    assert inv.argv[0] == "/opt/echo"


def test_get_adapter_cursor_conforms_to_protocol():
    adapter = get_adapter("cursor")
    assert isinstance(adapter, Adapter)
    assert adapter.name == "cursor"


def test_get_unknown_adapter_raises():
    with pytest.raises(AdapterError, match="unknown agent"):
        get_adapter("nope")


def test_known_agents_lists_cursor():
    assert "cursor" in known_agents()


def test_command_adapter_splits_command(tmp_path: Path):
    adapter = CommandAdapter()
    inv = adapter.build_invocation(
        mission=".venv/bin/python main.py --days 7",
        workspace=tmp_path,
        result_path=tmp_path / "r.json",
    )
    assert inv.argv == [".venv/bin/python", "main.py", "--days", "7"]
    assert inv.cwd == tmp_path
    assert inv.env is not None and inv.env["LOOPR_RESULT_PATH"] == str(tmp_path / "r.json")


def test_command_adapter_rejects_empty(tmp_path: Path):
    with pytest.raises(ValueError, match="empty command"):
        CommandAdapter().build_invocation(
            mission="   ", workspace=tmp_path, result_path=tmp_path / "r.json"
        )


def test_get_adapter_command_conforms_to_protocol():
    adapter = get_adapter("command")
    assert isinstance(adapter, Adapter)
    assert adapter.name == "command"


def test_known_agents_lists_command():
    assert "command" in known_agents()
