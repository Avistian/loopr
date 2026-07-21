# 01 — Global MCP Capability + Adapter authorize (happy path)

Status: ready-for-agent

## Parent

[.scratch/mcp-authorize-provisioning/PRD.md](../PRD.md)

## What to build

Let a Loop declare an MCP Capability by name only (no `server` block) meaning “use the global MCP entry; authorize it; do not write Workspace MCP config.” When `server` is present, keep today’s merge behavior and then authorize. Provisioning asks the Loop’s Adapter to authorize each MCP Capability. The Adapter protocol gains that authorize operation: Cursor implements enable → login → verify `ready`; Command no-ops. Require `on_auth_defer.notify` at config load whenever any MCP Capability is declared (cli is an allowed channel for this slice). When authorize succeeds, a Firing proceeds as today (including Cursor `--approve-mcps`). Skill and tool Capabilities stay unchanged. Idempotent across Loops sharing a Workspace.

Schema shape:

```yaml
capabilities:
  - type: mcp
    name: arxiv-local
on_auth_defer:
  notify: cli
```

## Acceptance criteria

- [ ] MCP Capability may omit `server`; Provisioning does not create or modify Workspace MCP config for that Capability
- [ ] MCP Capability with `server` still merges non-destructively, then authorizes
- [ ] Config load requires `on_auth_defer.notify` (known channel) when the Loop has any MCP Capability
- [ ] Adapter authorize hook exists; Cursor implements happy-path authorize; Command does not break command Loops
- [ ] Successful authorize leaves the Firing able to spawn the agent as before
- [ ] Tests cover config parse/validation, provision non-write for global MCP, and `run_firing` ready path via FakeAdapter

## Blocked by

None - can start immediately
