import json
from pathlib import Path

from loopr.config import McpCapability, SkillCapability, ToolCapability, Loop
from loopr.provision import provision


def make_loop(workspace: Path, caps) -> Loop:
    return Loop(name="t", mission="m", workspace=workspace, agent="cursor", capabilities=tuple(caps))


def test_skill_materialized_then_present(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    src = tmp_path / "triage.md"
    src.write_text("# Triage skill")
    loop = make_loop(ws, [SkillCapability(name="triage", path=src)])

    first = provision(loop)
    assert first.ok
    assert first.actions[0].outcome == "materialized"
    dest = ws / ".cursor" / "skills" / "triage" / "SKILL.md"
    assert dest.read_text() == "# Triage skill"

    second = provision(loop)
    assert second.actions[0].outcome == "present"


def test_skill_missing_source_fails(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    loop = make_loop(ws, [SkillCapability(name="x", path=tmp_path / "nope.md")])
    report = provision(loop)
    assert not report.ok
    assert report.actions[0].outcome == "failed"


def test_mcp_merged_preserves_existing(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = ws / ".cursor" / "mcp.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text(json.dumps({"mcpServers": {"existing": {"command": "x"}}}))

    loop = make_loop(ws, [McpCapability(name="dashboards", server={"command": "dash"})])
    report = provision(loop)
    assert report.ok
    assert report.actions[0].outcome == "merged"

    data = json.loads(cfg.read_text())
    assert data["mcpServers"]["existing"] == {"command": "x"}
    assert data["mcpServers"]["dashboards"] == {"command": "dash"}

    # idempotent
    assert provision(loop).actions[0].outcome == "present"


def test_mcp_invalid_json_fails(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    cfg = ws / ".cursor" / "mcp.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text("{not json")
    loop = make_loop(ws, [McpCapability(name="d", server={})])
    assert not provision(loop).ok


def test_tool_verified_when_on_path(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    loop = make_loop(ws, [ToolCapability(name="sh")])
    report = provision(loop)
    assert report.ok
    assert report.actions[0].outcome == "verified"


def test_tool_missing_no_install(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    loop = make_loop(ws, [ToolCapability(name="definitely-not-a-real-binary-xyz")])
    report = provision(loop)
    assert not report.ok
    assert report.actions[0].outcome == "missing"


def test_tool_install_runs_but_still_missing(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    loop = make_loop(
        ws,
        [ToolCapability(name="definitely-not-a-real-binary-xyz", install="true")],
    )
    report = provision(loop)
    assert not report.ok
    assert report.actions[0].outcome == "missing"
    assert "after install" in report.actions[0].detail
