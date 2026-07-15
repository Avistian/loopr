from pathlib import Path

import pytest

from loopr.config import (
    Config,
    ConfigError,
    Loop,
    McpCapability,
    SkillCapability,
    ToolCapability,
    find_config,
    load_config,
)


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "loopr.yaml"
    path.write_text(text)
    return path


def test_load_single_loop(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: model-monitor
            mission: "Check the dashboards and summarize."
            workspace: ./infra
            agent: cursor
        """,
    )
    config = load_config(path)
    assert isinstance(config, Config)
    loop = config.get_loop("model-monitor")
    assert isinstance(loop, Loop)
    assert loop.mission.startswith("Check")
    assert loop.agent == "cursor"
    # relative workspace resolved against the config's directory
    assert loop.workspace == (tmp_path / "infra").resolve()


def test_agent_defaults_to_cursor(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: do things
            workspace: .
        """,
    )
    assert load_config(path).get_loop("a").agent == "cursor"


def test_absolute_workspace_preserved(tmp_path: Path):
    path = write_config(
        tmp_path,
        f"""
        loops:
          - name: a
            mission: m
            workspace: {tmp_path}
        """,
    )
    assert load_config(path).get_loop("a").workspace == tmp_path


def test_missing_mission_is_error(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            workspace: .
        """,
    )
    with pytest.raises(ConfigError, match="mission"):
        load_config(path)


def test_duplicate_names_error(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: dup
            mission: m
            workspace: .
          - name: dup
            mission: m2
            workspace: .
        """,
    )
    with pytest.raises(ConfigError, match="duplicate"):
        load_config(path)


def test_unknown_loop_lists_known(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: known
            mission: m
            workspace: .
        """,
    )
    config = load_config(path)
    with pytest.raises(ConfigError, match="known"):
        config.get_loop("nope")


def test_parse_capabilities(tmp_path: Path):
    (tmp_path / "triage.md").write_text("# skill")
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
            capabilities:
              - type: skill
                name: triage
                path: ./triage.md
              - type: mcp
                name: dashboards
                server:
                  command: dash
                  args: ["--serve"]
              - type: tool
                name: gh
                install: "brew install gh"
        """,
    )
    loop = load_config(path).get_loop("a")
    assert len(loop.capabilities) == 3
    skill, mcp, tool = loop.capabilities
    assert isinstance(skill, SkillCapability)
    assert skill.path == (tmp_path / "triage.md").resolve()
    assert isinstance(mcp, McpCapability)
    assert mcp.server["command"] == "dash"
    assert isinstance(tool, ToolCapability)
    assert tool.install == "brew install gh"


def test_no_capabilities_defaults_empty(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
        """,
    )
    assert load_config(path).get_loop("a").capabilities == ()


def test_unknown_capability_type_errors(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
            capabilities:
              - type: bogus
                name: x
        """,
    )
    with pytest.raises(ConfigError, match="unknown capability type"):
        load_config(path)


def test_valid_schedule_parsed(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
            schedule: "every 5m"
        """,
    )
    assert load_config(path).get_loop("a").schedule == "every 5m"


def test_invalid_schedule_is_error(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
            schedule: "not a schedule"
        """,
    )
    with pytest.raises(ConfigError, match="valid interval or cron"):
        load_config(path)


def test_handoff_parsed(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: monitor
            mission: m
            workspace: .
            handoffs:
              - when: 'result.status == "issues"'
                trigger: fixer
          - name: fixer
            mission: fix
            workspace: .
        """,
    )
    monitor = load_config(path).get_loop("monitor")
    assert monitor.handoffs[0].trigger == "fixer"
    assert monitor.handoffs[0].when == 'result.status == "issues"'


def test_handoff_unknown_target_errors(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
            handoffs:
              - trigger: ghost
        """,
    )
    with pytest.raises(ConfigError, match="unknown loop 'ghost'"):
        load_config(path)


def test_handoff_invalid_predicate_errors(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
            handoffs:
              - when: 'evil()'
                trigger: a
        """,
    )
    with pytest.raises(ConfigError):
        load_config(path)


def test_handoff_requires_trigger_or_notify(tmp_path: Path):
    path = write_config(
        tmp_path,
        """
        loops:
          - name: a
            mission: m
            workspace: .
            handoffs:
              - when: 'result.status == "x"'
        """,
    )
    with pytest.raises(ConfigError, match="needs 'trigger' and/or 'notify'"):
        load_config(path)


def test_missing_file_is_error(tmp_path: Path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_find_config_searches_upward(tmp_path: Path):
    write_config(tmp_path, "loops: []")
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    assert find_config(nested) == tmp_path / "loopr.yaml"


def test_find_config_missing_raises(tmp_path: Path):
    with pytest.raises(ConfigError, match="no loopr.yaml"):
        find_config(tmp_path)
