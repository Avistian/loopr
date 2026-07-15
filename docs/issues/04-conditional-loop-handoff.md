# 04 — Conditional loop→loop Handoff

Status: done

## What to build

Let a Loop's Result trigger another Loop, so chains (e.g. monitor→fixer) emerge without
any pipeline object. A source Loop declares one or more **Handoff** rules in
`loopr.yaml` as predicates over the structured Result, evaluated by Loopr (never an
LLM), per `docs/adr/0006`:

```
handoffs:
  - when: result.status == "issues"
    trigger: fixer            # another Loop by name
```

When a Firing completes, the daemon evaluates the rules against the Result; on a match
it triggers the target Loop (a Trigger of kind "handoff"), passing the upstream Result
as context. To stay safe, enforce a basic guard against runaway chains: a configurable
max chain depth and cycle detection, recorded on the run so a chain that exceeds it is
stopped and surfaced.

Context-passing may be minimal here (inject the upstream Result summary into the
downstream Mission); a richer scheme can come later.

Vocabulary: `CONTEXT.md` (Handoff, Trigger, Result).

## Acceptance criteria

- [ ] A Loop can declare `handoffs` as predicate rules over Result fields in `loopr.yaml`
- [ ] On Firing completion the daemon evaluates the rules and triggers matching target Loops
- [ ] The upstream Result is passed as context to the triggered Loop's Firing
- [ ] Non-matching predicates trigger nothing; the chain simply ends
- [ ] A configurable max chain depth and cycle detection stop runaway chains and surface why
- [ ] Chain lineage (which run triggered which) is recorded and viewable

## Blocked by

- 02 — Scheduled firing via the daemon (the daemon owns chain-triggering)
- 03 — Structured Result capture (predicates read Result fields)
