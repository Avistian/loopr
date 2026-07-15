"""The ``loopr`` command-line interface.

Issue 01 surface: `run`, `runs`, `show`. Structured `--json` output and agent-driving
ergonomics arrive in issue 08.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional

import typer
import yaml

from .config import ConfigError, Config, Loop, find_config, load_config
from .daemon import is_running, read_pid, run_daemon
from .db import LeaseRecord, RunRecord, Store
from .handoff import fire_with_handoffs
from .scheduler import Scheduler
from .units import install_unit

app = typer.Typer(help="Loopr: schedule recurring agent work.", no_args_is_help=True)
daemon_app = typer.Typer(help="Run and manage the Loopr scheduler daemon.", no_args_is_help=True)
loop_app = typer.Typer(help="Create and inspect Loops in loopr.yaml.", no_args_is_help=True)
app.add_typer(daemon_app, name="daemon")
app.add_typer(loop_app, name="loop")


def _load(config: Optional[Path], *, json_out: bool = False) -> Config:
    try:
        path = config if config is not None else find_config()
        return load_config(path)
    except ConfigError as exc:
        _fail(str(exc), code=2, json_out=json_out)


def _fail(message: str, *, code: int, json_out: bool = False) -> "typer.Exit":
    if json_out:
        typer.echo(json.dumps({"error": message}))
    else:
        typer.secho(f"error: {message}", fg=typer.colors.RED, err=True)
    raise typer.Exit(code=code)


def _run_to_dict(r: RunRecord) -> dict:
    return {
        "id": r.id,
        "loop": r.loop_name,
        "status": r.status,
        "exit_code": r.exit_code,
        "agent": r.agent,
        "workspace": r.workspace,
        "started_at": r.started_at,
        "finished_at": r.finished_at,
        "log_path": r.log_path,
        "result_status": r.result_status,
        "result_summary": r.result_summary,
    }


def _lease_to_dict(l: LeaseRecord) -> dict:
    return {"workspace": l.workspace, "run_id": l.run_id, "pid": l.pid, "acquired_at": l.acquired_at}


def _loop_to_dict(loop: Loop) -> dict:
    return {
        "name": loop.name,
        "agent": loop.agent,
        "workspace": str(loop.workspace),
        "schedule": loop.schedule,
        "mission": loop.mission,
        "capabilities": [c.name for c in loop.capabilities],
        "handoffs": [
            {"when": h.when, "trigger": h.trigger, "notify": h.notify} for h in loop.handoffs
        ],
    }


@app.command()
def run(
    loop: str = typer.Argument(..., help="Name of the Loop to fire."),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to loopr.yaml (default: search upward)."
    ),
) -> None:
    """Fire a Loop once, now."""
    cfg = _load(config)
    try:
        loop_def = cfg.get_loop(loop)
    except ConfigError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    store = Store()
    try:
        record = fire_with_handoffs(loop_def, cfg, store)
    finally:
        store.close()

    color = typer.colors.GREEN if record.status == "success" else typer.colors.RED
    typer.secho(
        f"run {record.id}: {loop_def.name} -> {record.status}"
        + (f" (exit {record.exit_code})" if record.exit_code is not None else ""),
        fg=color,
    )
    typer.echo(f"log: {record.log_path}")
    if record.status != "success":
        raise typer.Exit(code=1)


@app.command()
def runs(
    limit: int = typer.Option(20, "--limit", "-n", help="Max runs to show."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """List past Firings, newest first."""
    store = Store()
    try:
        records = store.list_runs(limit=limit)
    finally:
        store.close()

    if json_out:
        typer.echo(json.dumps([_run_to_dict(r) for r in records]))
        return

    if not records:
        typer.echo("no runs yet")
        return
    for r in records:
        typer.echo(_format_run_line(r))


@app.command()
def show(
    run_id: int = typer.Argument(..., help="Run id (see `loopr runs`)."),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Print the captured Log of a Firing."""
    store = Store()
    try:
        record = store.get_run(run_id)
    finally:
        store.close()

    if record is None:
        _fail(f"no run with id {run_id}", code=2, json_out=json_out)

    log = ""
    if record.log_path and Path(record.log_path).is_file():
        log = Path(record.log_path).read_text()

    if json_out:
        payload = _run_to_dict(record)
        payload["log"] = log
        typer.echo(json.dumps(payload))
        return

    typer.echo(_format_run_line(record))
    if record.result_status:
        typer.echo(f"result: {record.result_status}  {record.result_summary or ''}".rstrip())
    typer.echo("-" * 40)
    typer.echo(log if log else "(no log captured)")


@daemon_app.command("run")
def daemon_run(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to loopr.yaml (default: search upward)."
    ),
    poll: float = typer.Option(1.0, "--poll", help="Scheduler poll interval, seconds."),
) -> None:
    """Run the scheduler in the foreground (Ctrl-C to stop)."""
    cfg = _load(config)
    store = Store()
    if is_running(store):
        typer.secho(
            f"error: daemon already running (pid {read_pid(store)})",
            fg=typer.colors.RED,
            err=True,
        )
        store.close()
        raise typer.Exit(code=1)
    typer.echo(f"loopr daemon started (pid {os.getpid()})")
    try:
        run_daemon(cfg, store, poll_seconds=poll)
    except KeyboardInterrupt:
        typer.echo("\nloopr daemon stopped")
    finally:
        store.close()


@daemon_app.command("status")
def daemon_status(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to loopr.yaml (default: search upward)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Show daemon health and the next scheduled firing per Loop."""
    store = Store()
    try:
        running = is_running(store)
        pid = read_pid(store)
        leases = store.active_leases()

        fires: dict[str, str] = {}
        try:
            cfg = load_config(config if config is not None else _find())
            scheduler = Scheduler(cfg, store)
            scheduler.initialize()
            fires = {
                name: dt.isoformat(timespec="seconds")
                for name, dt in scheduler.next_fire_times().items()
            }
        except ConfigError:
            cfg = None

        if json_out:
            typer.echo(
                json.dumps(
                    {
                        "running": running,
                        "pid": pid,
                        "leases": [_lease_to_dict(l) for l in leases],
                        "next_firings": fires,
                    }
                )
            )
            return

        if running:
            typer.secho(f"daemon: running (pid {pid})", fg=typer.colors.GREEN)
        else:
            typer.secho("daemon: not running", fg=typer.colors.YELLOW)
        if leases:
            typer.echo("active firings (workspace leases):")
            for lease in leases:
                typer.echo(f"  {lease.workspace}  run={lease.run_id} pid={lease.pid}")
        if not fires:
            typer.echo("no scheduled loops")
            return
        typer.echo("next firings:")
        for name in sorted(fires):
            typer.echo(f"  {name:<20} {fires[name]}")
    finally:
        store.close()


@daemon_app.command("install")
def daemon_install(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to loopr.yaml (default: search upward)."
    ),
) -> None:
    """Generate an OS autostart unit (systemd/launchd) for the daemon."""
    cfg = _load(config)
    unit = install_unit(cfg.source)
    typer.echo(f"wrote {unit.kind} unit: {unit.path}")
    typer.echo(f"enable with:\n  {unit.enable_hint}")


@loop_app.command("list")
def loop_list(
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to loopr.yaml (default: search upward)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """List configured Loops."""
    cfg = _load(config, json_out=json_out)
    loops = [_loop_to_dict(loop) for loop in cfg.loops.values()]
    if json_out:
        typer.echo(json.dumps(loops))
        return
    if not loops:
        typer.echo("no loops configured")
        return
    for loop in loops:
        sched = loop["schedule"] or "(triggered/manual)"
        typer.echo(f"{loop['name']:<20} agent={loop['agent']:<8} schedule={sched}")


@loop_app.command("add")
def loop_add(
    name: str = typer.Option(..., "--name", help="Unique Loop name."),
    mission: str = typer.Option(..., "--mission", help="What the agent should do."),
    workspace: str = typer.Option(..., "--workspace", help="Working directory."),
    agent: str = typer.Option("cursor", "--agent", help="Agent to hand off to."),
    schedule: Optional[str] = typer.Option(None, "--schedule", help="Cron or interval."),
    config: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to loopr.yaml (default: search upward)."
    ),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON."),
) -> None:
    """Add a Loop to loopr.yaml non-interactively (for humans and agents)."""
    try:
        path = config if config is not None else find_config()
    except ConfigError as exc:
        _fail(str(exc), code=2, json_out=json_out)

    raw = yaml.safe_load(path.read_text()) or {}
    if not isinstance(raw, dict):
        _fail(f"{path}: top level must be a mapping", code=2, json_out=json_out)
    loops = raw.setdefault("loops", [])
    if not isinstance(loops, list):
        _fail(f"{path}: 'loops' must be a list", code=2, json_out=json_out)
    if any(isinstance(l, dict) and l.get("name") == name for l in loops):
        _fail(f"loop {name!r} already exists", code=2, json_out=json_out)

    entry: dict = {"name": name, "mission": mission, "workspace": workspace, "agent": agent}
    if schedule is not None:
        entry["schedule"] = schedule
    loops.append(entry)

    # Write, then re-validate by reloading; roll back on failure.
    original = path.read_text()
    path.write_text(yaml.safe_dump(raw, sort_keys=False))
    try:
        load_config(path)
    except ConfigError as exc:
        path.write_text(original)
        _fail(f"refused to add invalid loop: {exc}", code=2, json_out=json_out)

    if json_out:
        typer.echo(json.dumps({"ok": True, "added": name}))
    else:
        typer.secho(f"added loop {name!r} to {path}", fg=typer.colors.GREEN)


def _find() -> Path:
    return find_config()


def _format_run_line(r: RunRecord) -> str:
    return (
        f"{r.id:>4}  {r.status:<8}  {r.loop_name:<20}  "
        f"{r.started_at}  agent={r.agent}"
    )


if __name__ == "__main__":
    app()
