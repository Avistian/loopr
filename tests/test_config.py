from pathlib import Path

import pytest

from loopr.config import Config, ConfigError, Loop, find_config, load_config


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
