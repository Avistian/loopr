"""SQLite-backed state store for run records and their Logs.

Per docs/adr/0002, Loopr's state lives in SQLite. In this slice (issue 01) the store
records one row per Firing and keeps the raw Log as a file on disk. Later slices add
schedules, leases, and results to the same store.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .result import Result
from .util import pid_alive

# Firing status values.
STATUS_RUNNING = "running"
STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_ERROR = "error"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    loop_name    TEXT NOT NULL,
    workspace    TEXT NOT NULL,
    agent        TEXT NOT NULL,
    status       TEXT NOT NULL,
    exit_code    INTEGER,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    log_path     TEXT
);

CREATE TABLE IF NOT EXISTS leases (
    workspace    TEXT PRIMARY KEY,
    run_id       INTEGER NOT NULL,
    pid          INTEGER NOT NULL,
    acquired_at  TEXT NOT NULL
);
"""

# Columns added after the initial schema, applied idempotently on open.
_MIGRATIONS: dict[str, str] = {
    "result_status": "ALTER TABLE runs ADD COLUMN result_status TEXT",
    "result_summary": "ALTER TABLE runs ADD COLUMN result_summary TEXT",
    "result_json": "ALTER TABLE runs ADD COLUMN result_json TEXT",
}


def now_iso() -> str:
    """UTC timestamp in ISO-8601 with a trailing Z."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def resolve_home(explicit: Path | str | None = None) -> Path:
    """Loopr's state root: explicit arg, else $LOOPR_HOME, else ~/.loopr."""
    if explicit is not None:
        return Path(explicit)
    env = os.environ.get("LOOPR_HOME")
    if env:
        return Path(env)
    return Path.home() / ".loopr"


@dataclass(frozen=True)
class LeaseRecord:
    workspace: str
    run_id: int
    pid: int
    acquired_at: str


@dataclass(frozen=True)
class RunRecord:
    id: int
    loop_name: str
    workspace: str
    agent: str
    status: str
    exit_code: int | None
    started_at: str
    finished_at: str | None
    log_path: str | None
    result_status: str | None = None
    result_summary: str | None = None
    result_json: str | None = None


class Store:
    """A per-user SQLite store rooted at a home directory."""

    def __init__(self, home: Path | str | None = None):
        self.home = resolve_home(home)
        self.home.mkdir(parents=True, exist_ok=True)
        self.logs_dir = self.home / "logs"
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.home / "loopr.db"
        self.results_dir = self.home / "results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.executescript(_SCHEMA)
        self._migrate()
        self._conn.commit()

    def _migrate(self) -> None:
        existing = {
            row["name"]
            for row in self._conn.execute("PRAGMA table_info(runs)").fetchall()
        }
        for column, statement in _MIGRATIONS.items():
            if column not in existing:
                self._conn.execute(statement)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "Store":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def log_path_for(self, run_id: int) -> Path:
        return self.logs_dir / f"{run_id}.log"

    def result_path_for(self, run_id: int) -> Path:
        return self.results_dir / f"{run_id}.json"

    def create_run(self, *, loop_name: str, workspace: str, agent: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO runs (loop_name, workspace, agent, status, started_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (loop_name, workspace, agent, STATUS_RUNNING, now_iso()),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def complete_run(
        self,
        run_id: int,
        *,
        status: str,
        exit_code: int | None,
        log_path: str | None,
        result: Result | None = None,
    ) -> None:
        result_status = result.status if result else None
        result_summary = result.summary if result else None
        result_json = json.dumps(result.raw) if result else None
        self._conn.execute(
            "UPDATE runs SET status = ?, exit_code = ?, finished_at = ?, log_path = ?, "
            "result_status = ?, result_summary = ?, result_json = ? WHERE id = ?",
            (
                status,
                exit_code,
                now_iso(),
                log_path,
                result_status,
                result_summary,
                result_json,
                run_id,
            ),
        )
        self._conn.commit()

    def try_acquire_lease(self, workspace: str, run_id: int, pid: int) -> bool:
        """Grab the Workspace Lease, stealing it if the holder process is dead.

        Returns False only when a *live* different holder already owns it.
        """
        try:
            self._conn.execute(
                "INSERT INTO leases (workspace, run_id, pid, acquired_at) "
                "VALUES (?, ?, ?, ?)",
                (workspace, run_id, pid, now_iso()),
            )
            self._conn.commit()
            return True
        except sqlite3.IntegrityError:
            pass

        row = self._conn.execute(
            "SELECT run_id, pid FROM leases WHERE workspace = ?", (workspace,)
        ).fetchone()
        if row is None:  # released between INSERT and SELECT; retry
            return self.try_acquire_lease(workspace, run_id, pid)
        if row["run_id"] == run_id:
            return True  # reentrant
        if pid_alive(row["pid"]):
            return False
        # stale holder: steal it
        self._conn.execute(
            "UPDATE leases SET run_id = ?, pid = ?, acquired_at = ? WHERE workspace = ?",
            (run_id, pid, now_iso(), workspace),
        )
        self._conn.commit()
        return True

    def release_lease(self, workspace: str, run_id: int) -> bool:
        cur = self._conn.execute(
            "DELETE FROM leases WHERE workspace = ? AND run_id = ?", (workspace, run_id)
        )
        self._conn.commit()
        return cur.rowcount > 0

    def active_leases(self) -> list[LeaseRecord]:
        rows = self._conn.execute(
            "SELECT * FROM leases ORDER BY workspace"
        ).fetchall()
        return [
            LeaseRecord(
                workspace=r["workspace"],
                run_id=r["run_id"],
                pid=r["pid"],
                acquired_at=r["acquired_at"],
            )
            for r in rows
        ]

    def get_run(self, run_id: int) -> RunRecord | None:
        row = self._conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        return _row_to_record(row) if row else None

    def list_runs(self, *, limit: int = 50) -> list[RunRecord]:
        rows = self._conn.execute(
            "SELECT * FROM runs ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_record(row) for row in rows]


def _row_to_record(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        id=row["id"],
        loop_name=row["loop_name"],
        workspace=row["workspace"],
        agent=row["agent"],
        status=row["status"],
        exit_code=row["exit_code"],
        started_at=row["started_at"],
        finished_at=row["finished_at"],
        log_path=row["log_path"],
        result_status=row["result_status"],
        result_summary=row["result_summary"],
        result_json=row["result_json"],
    )
