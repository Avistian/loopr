# Thin dispatcher with a structured Result contract; Loopr never runs an LLM

Loopr spawns a fresh headless agent per Firing and captures its output; it does not
hold a conversation or reason about content itself. To make Handoffs decidable, the
agent emits a small structured **Result** (status/summary/next/artifacts) via a known
channel, while the raw **Log** is always saved. Loopr parses Result fields to drive
routing but never invokes an LLM to interpret anything.

## Considered Options

- **Raw output + an LLM/regex judge inside Loopr** — rejected: embeds intelligence and
  non-determinism into what should be a scheduler, raises cost, and makes behavior hard
  to reason about.
- **Structured Result required (hard fail if absent)** — rejected as too brittle;
  instead a missing Result degrades gracefully to unconditional/manual Handoffs.

## Consequences

- Missions/Skills must instruct agents to emit the Result contract.
- Loopr stays cheap, deterministic, and agent-agnostic; all judgment lives in the agent.
