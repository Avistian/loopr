# 06 — Provisioning Capabilities before a Firing

Status: done

## What to build

Ensure a Loop's declared **Capabilities** exist in its Workspace before each Firing, so
the agent can actually do the Mission. A Loop declares Capabilities of three kinds — a
**Skill**, an **MCP server**, or a tool/binary. Before each Firing, Loopr runs an
idempotent **Provisioning** step (per `docs/adr/0001`-adjacent design and `CONTEXT.md`):

- **Skill** — materialize the SKILL.md-style file into the Workspace's skills location
- **MCP server** — merge the server entry into the Workspace's MCP config (e.g. `.cursor/mcp.json`) without clobbering existing entries
- **tool** — verify the binary is on PATH; warn/fail if missing, with an optional user-supplied install command as an escape hatch

Provisioning is a no-op when a Capability is already present, so Loops sharing a
Workspace never conflict. `loopr run`/scheduled Firings invoke it automatically; a
`loopr provision <loop>` command can run it on demand for debugging.

Vocabulary: `CONTEXT.md` (Provisioning, Capability, Skill, Workspace).

## Acceptance criteria

- [ ] A Loop can declare Capabilities of kinds: skill, mcp, tool in `loopr.yaml`
- [ ] Before each Firing, Provisioning ensures the Loop's Capabilities are present
- [ ] Skill files are materialized; MCP config is merged non-destructively
- [ ] Required tools are verified on PATH; missing tools warn/fail; optional install command supported
- [ ] Provisioning is idempotent (no-op when already present); shared Workspaces don't conflict
- [ ] `loopr provision <loop>` runs the step on demand

## Blocked by

- 01 — Manual one-shot Firing
