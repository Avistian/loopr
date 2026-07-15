# Declarative loopr.yaml as source of truth + agent-drivable CLI

Loops, Workspaces, Capabilities, and Handoffs are declared in a version-controllable
`loopr.yaml` that Loopr reconciles to. The CLI both edits that file and inspects state,
emits `--json`, and ships a `SKILL.md` so agents can schedule and manage Loops
themselves — a first-class goal (agents creating their own loops).

## Considered Options

- **Imperative CLI + hidden state store (crnd-style)** — rejected: state is not
  reviewable or diffable, and a config file better supports agents authoring loops.

## Consequences

- The `loopr.yaml` schema is a public contract that must stay stable and documented.
