"""Firing orchestration: spawn an agent for one Loop and capture the Log.

See CONTEXT.md (Firing, Log) and docs/adr/0001 (thin dispatcher). Loopr spawns a fresh
process, waits, and records the outcome. Structured Result capture arrives in issue 03.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from .adapters import Adapter, get_adapter
from .config import Loop
from .db import STATUS_ERROR, STATUS_FAILED, STATUS_SUCCESS, RunRecord, Store
from .provision import provision
from .result import parse_result


def run_firing(loop: Loop, store: Store, adapter: Adapter | None = None) -> RunRecord:
    """Execute one Firing of ``loop`` synchronously and return its run record."""
    adapter = adapter or get_adapter(loop.agent)
    run_id = store.create_run(
        loop_name=loop.name,
        workspace=str(loop.workspace),
        agent=loop.agent,
    )
    log_path = store.log_path_for(run_id)
    result_path = store.result_path_for(run_id)

    status, exit_code = _spawn_and_capture(loop, adapter, log_path, result_path)
    result = parse_result(result_path)
    store.complete_run(
        run_id,
        status=status,
        exit_code=exit_code,
        log_path=str(log_path),
        result=result,
    )

    record = store.get_run(run_id)
    assert record is not None  # just created
    return record


def _spawn_and_capture(
    loop: Loop, adapter: Adapter, log_path: Path, result_path: Path
) -> tuple[str, int | None]:
    if not loop.workspace.is_dir():
        log_path.write_text(
            f"[loopr] workspace does not exist: {loop.workspace}\n"
        )
        return STATUS_ERROR, None

    report = provision(loop)
    preamble = report.render()
    if preamble:
        log_path.write_text(preamble + "\n")
    if not report.ok:
        with open(log_path, "a") as log_file:
            log_file.write("[loopr] provisioning failed; skipping firing\n")
        return STATUS_ERROR, None

    invocation = adapter.build_invocation(
        mission=loop.mission, workspace=loop.workspace, result_path=result_path
    )
    env = {**os.environ, **(invocation.env or {})}

    try:
        with open(log_path, "ab") as log_file:
            proc = subprocess.run(
                invocation.argv,
                cwd=str(invocation.cwd),
                env=env,
                stdout=log_file,
                stderr=subprocess.STDOUT,
                check=False,
            )
    except FileNotFoundError:
        with open(log_path, "a") as log_file:
            log_file.write(f"[loopr] agent executable not found: {invocation.argv[0]!r}\n")
        return STATUS_ERROR, None

    status = STATUS_SUCCESS if proc.returncode == 0 else STATUS_FAILED
    return status, proc.returncode
