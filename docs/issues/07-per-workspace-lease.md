# 07 — Per-Workspace Lease serialization

Status: done

## What to build

Prevent two agents from mutating one repo at once. Because Workspaces are shared by
multiple Loops (`docs/adr/0005`), the daemon grants a **Lease** per Workspace: at most
one Firing is active in a given Workspace at a time; concurrent triggers for that
Workspace queue and run in order, while Firings in different Workspaces run in parallel.

The Lease is enforced by the daemon and recorded in SQLite so it survives a daemon
restart (a stale Lease from a crashed Firing must expire/recover so the Workspace isn't
locked forever). `loopr daemon status` shows which Workspaces are leased and what is
queued.

Vocabulary: `CONTEXT.md` (Lease, Workspace, Firing).

## Acceptance criteria

- [ ] At most one Firing is active per Workspace; others for that Workspace queue
- [ ] Firings in different Workspaces run concurrently
- [ ] Both scheduled and handoff-triggered Firings respect the Lease
- [ ] Lease state persists in SQLite and recovers cleanly after a daemon crash/restart (no permanent lock)
- [ ] `loopr daemon status` shows leased Workspaces and queued Firings

## Blocked by

- 02 — Scheduled firing via the daemon (the daemon grants and enforces Leases)
