# Shared Workspaces with per-Workspace Lease serialization

A Workspace is decoupled from any single Loop; multiple Loops (e.g. a monitor and a
fixer) may share one repo. To prevent two agents mutating one repo concurrently, the
daemon grants a **Lease** per Workspace: at most one Firing is active per Workspace,
others queue, and Firings in different Workspaces run in parallel.

## Considered Options

- **One private directory per Loop** — rejected: breaks the monitor+fixer-share-a-repo
  use case that motivated the design.
- **Ephemeral git worktree per Firing** — rejected for v1: more parallelism but adds
  worktree creation and merge-back complexity.

## Consequences

- Concurrency is bounded by the number of distinct Workspaces, not Loops.
- A long Firing blocks other Loops targeting the same Workspace until it releases.
