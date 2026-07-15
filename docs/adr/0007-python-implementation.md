# Python as the implementation language

Loopr is built in Python. We chose it over Go/Rust/Bun for fastest iteration, fit with
the surrounding workspace, and a batteries-included standard library (sqlite3,
subprocess, asyncio) that covers the daemon, state store, and agent-spawning needs. CLI
via Typer/Click; config via PyYAML.

## Considered Options

- **Go** (single static binary, like sundial) — rejected for v1: more ceremony, slower to
  prototype the domain model we just designed.
- **Bun/TypeScript** (like crnd) and **Rust** (like schedx) — rejected similarly; both add
  runtime/build friction without a v1 benefit that outweighs iteration speed.

## Consequences

- Distribution is via `uv`/`pipx` (an installed Python), not a single self-contained binary.
  If single-binary distribution becomes a priority, this decision must be revisited.
