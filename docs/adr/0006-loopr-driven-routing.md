# Loopr-driven routing: chain topology lives in config, not in agents

Which Loop a conditional Handoff triggers is decided by a predicate over the structured
Result, declared on the source Loop in `loopr.yaml` and evaluated by Loopr. Agents
report generic Results (e.g. `status: "issues"`) and never name other Loops.

## Considered Options

- **Agent-driven routing (agent emits `next: fix-loop`)** — rejected: couples agents and
  Missions to other Loops' names, hurts agent reusability, and hides chain topology from
  the config.

## Consequences

- Agents/Skills stay generic and reusable across chains.
- Chain topology is reviewable in one place; cycle/loop-depth safety can be enforced
  centrally by Loopr (an open item).
