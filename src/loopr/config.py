"""Parsing and validation of ``loopr.yaml``.

The config file is the declarative source of truth (see docs/adr/0004). This slice
(issue 01) supports a single field set per Loop: name, mission, workspace, agent.
Later slices extend the schema (schedule, capabilities, handoffs).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_AGENT = "cursor"
DEFAULT_CONFIG_NAME = "loopr.yaml"


class ConfigError(Exception):
    """Raised when a loopr.yaml is missing, malformed, or invalid."""


@dataclass(frozen=True)
class SkillCapability:
    """A reusable SKILL.md-style document to materialize into the Workspace."""

    name: str
    path: Path  # source SKILL.md


@dataclass(frozen=True)
class McpCapability:
    """An MCP server entry to merge into the Workspace's MCP config."""

    name: str
    server: dict


@dataclass(frozen=True)
class ToolCapability:
    """A tool/binary that must be on PATH (optionally installed via a command)."""

    name: str
    install: str | None = None


Capability = SkillCapability | McpCapability | ToolCapability


@dataclass(frozen=True)
class Loop:
    """A reusable unit of agent work (see CONTEXT.md: Loop)."""

    name: str
    mission: str
    workspace: Path
    agent: str = DEFAULT_AGENT
    capabilities: tuple[Capability, ...] = ()


@dataclass(frozen=True)
class Config:
    """The parsed loopr.yaml: Loops keyed by name."""

    loops: dict[str, Loop]
    source: Path

    def get_loop(self, name: str) -> Loop:
        try:
            return self.loops[name]
        except KeyError:
            known = ", ".join(sorted(self.loops)) or "(none)"
            raise ConfigError(f"no Loop named {name!r}; known loops: {known}") from None


def find_config(start: Path | None = None) -> Path:
    """Search upward from ``start`` (default cwd) for a loopr.yaml."""
    current = (start or Path.cwd()).resolve()
    for directory in (current, *current.parents):
        candidate = directory / DEFAULT_CONFIG_NAME
        if candidate.is_file():
            return candidate
    raise ConfigError(f"no {DEFAULT_CONFIG_NAME} found in {current} or any parent")


def load_config(path: Path) -> Config:
    """Load and validate a loopr.yaml."""
    path = Path(path)
    if not path.is_file():
        raise ConfigError(f"config file not found: {path}")

    try:
        raw = yaml.safe_load(path.read_text()) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"invalid YAML in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: top level must be a mapping")

    raw_loops = raw.get("loops", [])
    if not isinstance(raw_loops, list):
        raise ConfigError(f"{path}: 'loops' must be a list")

    base = path.parent
    loops: dict[str, Loop] = {}
    for index, entry in enumerate(raw_loops):
        loop = _parse_loop(entry, index=index, base=base, source=path)
        if loop.name in loops:
            raise ConfigError(f"{path}: duplicate loop name {loop.name!r}")
        loops[loop.name] = loop

    return Config(loops=loops, source=path)


def _parse_loop(entry: object, *, index: int, base: Path, source: Path) -> Loop:
    where = f"{source}: loops[{index}]"
    if not isinstance(entry, dict):
        raise ConfigError(f"{where} must be a mapping")

    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"{where}: 'name' is required and must be a non-empty string")

    mission = entry.get("mission")
    if not isinstance(mission, str) or not mission.strip():
        raise ConfigError(f"{where} ({name}): 'mission' is required and must be a non-empty string")

    workspace = entry.get("workspace")
    if not isinstance(workspace, str) or not workspace.strip():
        raise ConfigError(f"{where} ({name}): 'workspace' is required and must be a non-empty string")

    agent = entry.get("agent", DEFAULT_AGENT)
    if not isinstance(agent, str) or not agent.strip():
        raise ConfigError(f"{where} ({name}): 'agent' must be a non-empty string")

    workspace_path = Path(workspace)
    if not workspace_path.is_absolute():
        workspace_path = (base / workspace_path).resolve()

    raw_caps = entry.get("capabilities", [])
    if not isinstance(raw_caps, list):
        raise ConfigError(f"{where} ({name}): 'capabilities' must be a list")
    capabilities = tuple(
        _parse_capability(cap, where=f"{where} ({name}) capabilities[{i}]", base=base)
        for i, cap in enumerate(raw_caps)
    )

    return Loop(
        name=name,
        mission=mission,
        workspace=workspace_path,
        agent=agent,
        capabilities=capabilities,
    )


def _parse_capability(entry: object, *, where: str, base: Path) -> Capability:
    if not isinstance(entry, dict):
        raise ConfigError(f"{where} must be a mapping")
    kind = entry.get("type")
    name = entry.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ConfigError(f"{where}: 'name' is required")

    if kind == "skill":
        src = entry.get("path")
        if not isinstance(src, str) or not src.strip():
            raise ConfigError(f"{where} (skill {name}): 'path' is required")
        src_path = Path(src)
        if not src_path.is_absolute():
            src_path = (base / src_path).resolve()
        return SkillCapability(name=name, path=src_path)

    if kind == "mcp":
        server = entry.get("server")
        if not isinstance(server, dict):
            raise ConfigError(f"{where} (mcp {name}): 'server' mapping is required")
        return McpCapability(name=name, server=server)

    if kind == "tool":
        install = entry.get("install")
        if install is not None and not isinstance(install, str):
            raise ConfigError(f"{where} (tool {name}): 'install' must be a string")
        return ToolCapability(name=name, install=install)

    raise ConfigError(f"{where}: unknown capability type {kind!r} (skill|mcp|tool)")
