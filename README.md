# Loopr

A lightweight CLI that schedules recurring agent work. Loopr owns *when* work runs,
*what* gets handed to an agent, and *what came back* — not the agent's internal
reasoning.

See [`CONTEXT.md`](./CONTEXT.md) for the domain vocabulary and [`docs/adr/`](./docs/adr)
for architecture decisions. Implementation is tracked in [`docs/issues/`](./docs/issues).

## Status

Early development. Implemented so far:

- **Issue 01** — manual one-shot Firing of a single Loop (`loopr run`, `loopr runs`, `loopr show`).

## Install (dev)

```bash
uv sync
```

## Example `loopr.yaml`

```yaml
loops:
  - name: model-monitor
    mission: "Check the model dashboards and summarize anything degrading."
    workspace: ./infra
    agent: cursor
```

## Usage

```bash
loopr run model-monitor   # fire the loop once, now
loopr runs                # list past firings
loopr show <run-id>       # print the captured log of a firing
```
