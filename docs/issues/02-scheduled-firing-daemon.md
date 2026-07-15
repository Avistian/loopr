# 02 — Scheduled firing via the daemon

Status: done

## What to build

Make Loops fire on a schedule with no terminal open. Introduce the per-user Loopr
**daemon** that owns scheduling and firing, backed by the same SQLite state store, and
autostarts via systemd (Linux) / launchd (macOS). A Loop gains an optional `schedule`
(this slice covers recurring/interval + cron-style times); when its time arrives the
daemon performs a Firing exactly as `loopr run` does and records the run.

`loopr daemon status` reports whether the daemon is running and what is scheduled next.
This is the decision from `docs/adr/0002` (own daemon + SQLite, not system cron).

Vocabulary: `CONTEXT.md` (Trigger — schedule kind, Firing).

## Acceptance criteria

- [ ] A daemon process owns scheduling and firing; it survives terminal close and restarts
- [ ] The daemon autostarts via systemd user unit (Linux) and launchd (macOS)
- [ ] A Loop with a `schedule` fires automatically at the scheduled time
- [ ] Scheduled Firings produce the same run records + Logs as manual runs (issue 01)
- [ ] `loopr daemon status` shows daemon health and the next scheduled firing per Loop
- [ ] Schedule state is recovered from SQLite on daemon restart

## Blocked by

- 01 — Manual one-shot Firing (provides the Firing + state + config skeleton)
