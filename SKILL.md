---
name: loopr
description: Schedule and manage recurring agent work with the Loopr CLI. Use when the user wants to run an agent on a schedule, chain agent loops (e.g. monitor -> fixer), or get notified when a scheduled agent finds something.
---

# Driving Loopr

Loopr schedules recurring agent work. You configure **Loops** in `loopr.yaml`; a
background daemon fires them on a schedule, hands the result off to other loops
(conditionally) or to a human, and records every run.

All commands accept `--json` for machine-readable output and never prompt interactively,
so you can drive them directly. Non-zero exit codes indicate failure; with `--json` the
error is `{"error": "..."}` on stdout.

## Core vocabulary

- **Loop**: a unit of agent work (mission + workspace + optional capabilities/schedule/handoffs).
- **Firing**: one execution of a Loop; produces a raw **Log** and an optional structured **Result**.
- **Handoff**: passes a Result to another Loop (conditionally) or to a human (a Notification).

## Add a Loop (non-interactive)

```bash
loopr loop add --name model-monitor \
  --mission "Check the model dashboards and summarize anything degrading." \
  --workspace ./infra \
  --schedule "0 9 * * 1-5" \
  --json
```

Interval schedules also work: `--schedule "every 6h"`. Omit `--schedule` for a Loop that
only runs when triggered by another Loop or manually.

## Inspect

```bash
loopr loop list --json          # configured loops
loopr runs --json               # past firings, newest first
loopr show <run-id> --json      # one firing incl. Log and Result
loopr daemon status --json      # daemon health + next firings + active leases
```

## Run and schedule

```bash
loopr run <loop>                # fire once now (runs the full handoff chain)
loopr daemon run                # foreground scheduler (Ctrl-C to stop)
loopr daemon install            # generate a systemd/launchd autostart unit
```

## Structured Result contract

Have the agent write JSON to `$LOOPR_RESULT_PATH` so Loopr can route on it:

```json
{"status": "issues", "summary": "3 models degraded", "artifacts": [{"type": "pr", "url": "..."}]}
```

Only `status` is required. Loopr never runs an LLM to interpret it.

## Handoffs (edit loopr.yaml directly)

```yaml
loops:
  - name: model-monitor
    mission: "Check dashboards"
    workspace: ./infra
    schedule: "0 9 * * 1-5"
    handoffs:
      - when: 'result.status == "issues"'   # predicate over the Result; Loopr evaluates it
        trigger: fixer                        # fire another Loop, passing the Result as context
  - name: fixer
    mission: "Open a PR fixing the reported issues"
    workspace: ./infra
    handoffs:
      - notify: cli                           # hand off to a human; terminates the chain
```

Predicates may use `result.status`, `result.summary`, `result.next`, `result.artifacts`
with `==`, `!=`, `in`, `and`, `or`, `not`. Chains are cycle- and depth-guarded.
