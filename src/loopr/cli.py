"""The ``loopr`` command-line interface.

Issue 01 surface: `run`, `runs`, `show`. Structured `--json` output and agent-driving
ergonomics arrive in issue 08.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

import typer

from .config import ConfigError, Config, find_config, load_config
from .daemon import is_running, read_pid, run_daemon
from .db import RunRecord, Store
from .firing import run_firing
from .scheduler import Scheduler
from .units import install_unit

app = typer.Typer(help="Loopr: schedule recurring agent work.", no_args_is_help=True)
daemon_app = typer.Typer(help="Run and manage the Loopr scheduler daemon.", no_args_is_help=True)
app.add_typer(daemon_app, name="daemon")


def _load(config: Optional[Path]) -> Config:
    try:
        path = config if config is not None else find_config()
        return load_config(path)
    except ConfigError as exc:
        typer.secho(f"error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)


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
        record = run_firing(loop_def, store)
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
) -> None:
    """List past Firings, newest first."""
    store = Store()
    try:
        records = store.list_runs(limit=limit)
    finally:
        store.close()

    if not records:
        typer.echo("no runs yet")
        return

    for r in records:
        typer.echo(_format_run_line(r))


@app.command()
def show(
    run_id: int = typer.Argument(..., help="Run id (see `loopr runs`)."),
) -> None:
    """Print the captured Log of a Firing."""
    store = Store()
    try:
        record = store.get_run(run_id)
    finally:
        store.close()

    if record is None:
        typer.secho(f"error: no run with id {run_id}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2)

    typer.echo(_format_run_line(record))
    if record.result_status:
        typer.echo(f"result: {record.result_status}  {record.result_summary or ''}".rstrip())
    typer.echo("-" * 40)
    if record.log_path and Path(record.log_path).is_file():
        typer.echo(Path(record.log_path).read_text())
    else:
        typer.echo("(no log captured)")


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
) -> None:
    """Show daemon health and the next scheduled firing per Loop."""
    store = Store()
    try:
        running = is_running(store)
        pid = read_pid(store)
        if running:
            typer.secho(f"daemon: running (pid {pid})", fg=typer.colors.GREEN)
        else:
            typer.secho("daemon: not running", fg=typer.colors.YELLOW)

        leases = store.active_leases()
        if leases:
            typer.echo("active firings (workspace leases):")
            for lease in leases:
                typer.echo(f"  {lease.workspace}  run={lease.run_id} pid={lease.pid}")

        try:
            cfg = load_config(config if config is not None else _find())
        except ConfigError:
            return
        scheduler = Scheduler(cfg, store)
        scheduler.initialize()
        fires = scheduler.next_fire_times()
        if not fires:
            typer.echo("no scheduled loops")
            return
        typer.echo("next firings:")
        for name in sorted(fires):
            typer.echo(f"  {name:<20} {fires[name].isoformat(timespec='seconds')}")
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


def _find() -> Path:
    return find_config()


def _format_run_line(r: RunRecord) -> str:
    return (
        f"{r.id:>4}  {r.status:<8}  {r.loop_name:<20}  "
        f"{r.started_at}  agent={r.agent}"
    )


if __name__ == "__main__":
    app()
