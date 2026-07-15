# 03 — Structured Result capture

Status: done

## What to build

Give a Firing a machine-readable outcome without Loopr ever running an LLM. The Adapter
gains a way to obtain a small structured **Result** from the agent (via a known channel,
e.g. a `result.json` the agent is instructed to write) alongside the always-captured
**Log**. Loopr parses the Result's fields and stores it on the run. If no Result is
emitted, the run still succeeds and the Result is recorded as absent.

The Result shape is a small, documented contract. From `docs/adr/0001`, the fields are:

```
status: string        # agent-defined, e.g. "ok" | "issues"
summary: string       # short human-readable summary
next: string?         # optional hint (see issue 04 for how routing uses it)
artifacts: [ ... ]?   # optional list of durable outputs (PR/issue/file links)
```

`loopr show <run>` displays the parsed Result. Missions/Skills are responsible for
instructing the agent to emit it.

Vocabulary: `CONTEXT.md` (Result, Log, Artifact, Adapter).

## Acceptance criteria

- [ ] The Result contract (status/summary/next/artifacts) is documented as a stable schema
- [ ] The Cursor Adapter obtains and parses the structured Result via a known channel
- [ ] The raw Log is still always captured, independent of whether a Result was emitted
- [ ] A missing/invalid Result degrades gracefully (run succeeds, Result recorded absent)
- [ ] The parsed Result is persisted on the run and shown by `loopr show <run>`
- [ ] Loopr performs no LLM calls to interpret the Result

## Blocked by

- 01 — Manual one-shot Firing
