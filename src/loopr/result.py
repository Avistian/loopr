"""The structured Result contract (see CONTEXT.md: Result, and docs/adr/0001).

The agent writes a small JSON document to the path in $LOOPR_RESULT_PATH. Loopr parses
it to drive Handoffs but never runs an LLM to interpret it. Parsing is deliberately
lenient: a missing or malformed Result degrades to ``None`` so the Firing still
succeeds and conditional Handoffs fall back to unconditional/manual.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

RESULT_PATH_ENV = "LOOPR_RESULT_PATH"


@dataclass(frozen=True)
class Result:
    status: str
    summary: str = ""
    next: str | None = None
    artifacts: list = field(default_factory=list)
    raw: dict = field(default_factory=dict)


def result_instruction(result_path: Path) -> str:
    """The standard protocol text appended to a Mission telling the agent how to report.

    Kept small and agent-agnostic so any Adapter can reuse it.
    """
    return (
        "\n\n---\n"
        "When you finish, write a JSON summary of your outcome to the file at "
        f"{result_path} (also available as ${RESULT_PATH_ENV}). Use this shape:\n"
        '{"status": "<short machine token, e.g. ok|issues>", '
        '"summary": "<one-line human summary>", '
        '"next": null, '
        '"artifacts": [{"type": "pr|issue|file", "url": "<link or path>"}]}\n'
        "Only 'status' is required."
    )


def parse_result(path: Path) -> Result | None:
    """Parse a result.json file, or return None if absent/invalid."""
    path = Path(path)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None

    status = data.get("status")
    if not isinstance(status, str) or not status.strip():
        return None

    summary = data.get("summary", "")
    summary = summary if isinstance(summary, str) else str(summary)

    next_hint = data.get("next")
    next_hint = next_hint if isinstance(next_hint, str) else None

    artifacts = data.get("artifacts", [])
    artifacts = artifacts if isinstance(artifacts, list) else []

    return Result(
        status=status,
        summary=summary,
        next=next_hint,
        artifacts=artifacts,
        raw=data,
    )
