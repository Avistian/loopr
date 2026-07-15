# 01 — Manual one-shot Firing of a single Loop

Status: done

## What to build

The tracer bullet: the thinnest end-to-end path that fires one agent and records it.

A user defines a minimal `loopr.yaml` describing a single **Loop** (name, Mission,
Workspace path, agent = `cursor`). Running `loopr run <loop>` reads the config, spawns a
fresh headless `cursor-agent` process with the Workspace as cwd and the Mission as
input (a **Firing**), waits for it to finish, captures the raw **Log**, and records a
run entry in SQLite. `loopr runs` lists past runs; `loopr show <run>` prints the Log.

This establishes the skeleton every later slice builds on: the `loopr.yaml` schema, the
SQLite state store, the CLI framework, and the **Adapter** interface (with a Cursor
implementation) — but stays thin: no schedule, no provisioning, no Result parsing, no
handoff.

Vocabulary and decisions: see `CONTEXT.md` (Loop, Firing, Log, Adapter, Workspace),
`docs/adr/0001` (thin dispatcher), `docs/adr/0004` (declarative config).

## Acceptance criteria

- [ ] A `loopr.yaml` with one Loop (name, mission, workspace, agent) parses and validates
- [ ] `loopr run <loop>` spawns `cursor-agent` headless with the Workspace as cwd and the Mission as input
- [ ] The raw Log (stdout/stderr) is captured and persisted, even on non-zero exit
- [ ] A run record (loop name, start/end time, exit status, log ref) is written to SQLite
- [ ] `loopr runs` lists runs; `loopr show <run>` prints the Log
- [ ] The Adapter is an interface with a `cursor` implementation (so new agents can be added later)

## Blocked by

None — can start immediately.
