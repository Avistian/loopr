# Loopr

A lightweight CLI that schedules recurring agent work. Loopr owns *when* work runs,
*what* gets handed to an agent, and *what came back* — not the agent's internal
reasoning.

See [`CONTEXT.md`](./CONTEXT.md) for the domain vocabulary and [`docs/adr/`](./docs/adr)
for architecture decisions. Implementation is tracked in [`docs/issues/`](./docs/issues).

## Status

All v1 vertical slices implemented (see [`docs/issues/`](./docs/issues)):

- **01** manual one-shot Firing · **02** scheduled firing via the daemon ·
  **03** structured Result capture · **04** conditional loop→loop Handoff ·
  **05** human Handoff (Notification) · **06** Provisioning Capabilities ·
  **07** per-Workspace Lease · **08** agent-drivable CLI (`--json` + `SKILL.md`)

## Install (dev)

```bash
uv sync
```

## Example `loopr.yaml`

```yaml
max_chain_depth: 10
loops:
  - name: model-monitor
    mission: "Check the model dashboards and summarize anything degrading."
    workspace: ./infra
    schedule: "0 9 * * 1-5"          # cron, or e.g. "every 6h"
    capabilities:
      - type: skill
        name: triage
        path: ./skills/triage/SKILL.md
      - type: mcp
        name: dashboards
        server: { command: dashboards-mcp }
      - type: tool
        name: gh
    handoffs:
      - when: 'result.status == "issues"'
        trigger: fixer
  - name: fixer
    mission: "Open a PR fixing the reported issues."
    workspace: ./infra
    handoffs:
      - notify: cli
```

## Usage

```bash
loopr run model-monitor     # fire once now (runs the full handoff chain)
loopr runs                  # list past firings
loopr show <run-id>         # print the captured Log + parsed Result

loopr loop list             # list configured loops
loopr loop add --name news --mission "curate news" --workspace ./news --schedule "every 6h"

loopr daemon run            # foreground scheduler (Ctrl-C to stop)
loopr daemon status         # health + next firings + active leases
loopr daemon install        # generate a systemd/launchd autostart unit
```

Every read/inspect command supports `--json`, and mutating commands are non-interactive,
so an agent can drive Loopr directly (see [`SKILL.md`](./SKILL.md)).

## Development

```bash
uv run pytest        # 119 tests
```
