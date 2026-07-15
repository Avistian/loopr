# 08 — Agent-drivable CLI (`--json` + SKILL.md)

Status: ready-for-agent

## What to build

Make Loopr something an agent can drive, not just a human — a first-class goal from
`docs/adr/0004` (agents authoring their own loops, e.g. the news/curriculum examples).
Add structured `--json` output to the CLI's read and mutate commands, ensure the CLI can
create/edit Loops in `loopr.yaml` non-interactively (no prompts that block an agent), and
ship a `SKILL.md` that teaches a coding agent how to schedule, list, inspect, and manage
Loops via Loopr.

Vocabulary: `CONTEXT.md` (Loop, Mission, Capability, Handoff).

## Acceptance criteria

- [ ] Read commands (`runs`, `show`, `daemon status`, list loops) support `--json` with a documented shape
- [ ] Mutating commands can add/edit a Loop in `loopr.yaml` non-interactively (no blocking prompts)
- [ ] Non-zero exit codes + machine-readable errors on failure
- [ ] A `SKILL.md` ships that teaches an agent to create, list, inspect, and manage Loops
- [ ] The SKILL.md is verified end-to-end by having an agent schedule and inspect a Loop

## Blocked by

- 01 — Manual one-shot Firing (establishes the CLI surface the JSON/SKILL wrap)
