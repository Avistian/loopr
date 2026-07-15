"""Provisioning: ensure a Loop's Capabilities exist in its Workspace.

Idempotent and run before each Firing (see CONTEXT.md: Provisioning). Skills are
materialized, MCP servers are merged non-destructively, and tools are verified on PATH
(optionally installed via a user-supplied command). A no-op when already present, so
Loops sharing a Workspace never conflict.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .config import (
    Capability,
    Loop,
    McpCapability,
    SkillCapability,
    ToolCapability,
)

# Outcomes that mean provisioning could not satisfy a Capability.
_BAD_OUTCOMES = {"missing", "failed"}


@dataclass(frozen=True)
class ProvisionAction:
    kind: str
    name: str
    outcome: str
    detail: str = ""


@dataclass
class ProvisionReport:
    actions: list[ProvisionAction] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(a.outcome not in _BAD_OUTCOMES for a in self.actions)

    def render(self) -> str:
        if not self.actions:
            return ""
        lines = ["[loopr] provisioning:"]
        for a in self.actions:
            suffix = f" ({a.detail})" if a.detail else ""
            lines.append(f"  - {a.kind}:{a.name} -> {a.outcome}{suffix}")
        return "\n".join(lines)


def provision(loop: Loop) -> ProvisionReport:
    report = ProvisionReport()
    for cap in loop.capabilities:
        report.actions.append(_ensure(cap, loop.workspace))
    return report


def _ensure(cap: Capability, workspace: Path) -> ProvisionAction:
    if isinstance(cap, SkillCapability):
        return _ensure_skill(cap, workspace)
    if isinstance(cap, McpCapability):
        return _ensure_mcp(cap, workspace)
    if isinstance(cap, ToolCapability):
        return _ensure_tool(cap, workspace)
    raise TypeError(f"unknown capability: {cap!r}")  # pragma: no cover


def _ensure_skill(cap: SkillCapability, workspace: Path) -> ProvisionAction:
    dest = workspace / ".cursor" / "skills" / cap.name / "SKILL.md"
    if dest.is_file():
        return ProvisionAction("skill", cap.name, "present")
    if not cap.path.is_file():
        return ProvisionAction("skill", cap.name, "failed", f"source missing: {cap.path}")
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cap.path, dest)
    return ProvisionAction("skill", cap.name, "materialized", str(dest))


def _ensure_mcp(cap: McpCapability, workspace: Path) -> ProvisionAction:
    config_path = workspace / ".cursor" / "mcp.json"
    data: dict = {}
    if config_path.is_file():
        try:
            data = json.loads(config_path.read_text()) or {}
        except json.JSONDecodeError:
            return ProvisionAction("mcp", cap.name, "failed", f"invalid JSON: {config_path}")
    if not isinstance(data, dict):
        return ProvisionAction("mcp", cap.name, "failed", "mcp.json is not an object")

    servers = data.setdefault("mcpServers", {})
    if not isinstance(servers, dict):
        return ProvisionAction("mcp", cap.name, "failed", "mcpServers is not an object")
    if cap.name in servers:
        return ProvisionAction("mcp", cap.name, "present")

    servers[cap.name] = cap.server
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data, indent=2) + "\n")
    return ProvisionAction("mcp", cap.name, "merged", str(config_path))


def _ensure_tool(cap: ToolCapability, workspace: Path) -> ProvisionAction:
    if shutil.which(cap.name):
        return ProvisionAction("tool", cap.name, "verified")
    if not cap.install:
        return ProvisionAction("tool", cap.name, "missing", "not on PATH, no install command")
    try:
        subprocess.run(cap.install, shell=True, cwd=str(workspace), check=True)
    except subprocess.CalledProcessError as exc:
        return ProvisionAction("tool", cap.name, "failed", f"install exited {exc.returncode}")
    if shutil.which(cap.name):
        return ProvisionAction("tool", cap.name, "installed")
    return ProvisionAction("tool", cap.name, "missing", "still not on PATH after install")
