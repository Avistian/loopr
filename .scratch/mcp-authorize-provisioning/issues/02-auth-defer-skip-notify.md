# 02 — Auth defer: skip Firing + Notification

Status: ready-for-agent

## Parent

[.scratch/mcp-authorize-provisioning/PRD.md](../PRD.md)

## What to build

When Adapter authorize does not reach `ready` (including missing server, login failure, or 60s timeout), skip this Firing: do not spawn the agent, record an error run with a clear Log preamble, deliver a Notification on the Loop’s `on_auth_defer` channel, and release normally — no parked Firing or resume API (ADR 0003). The Notification names the Loop, MCP server(s), run/log pointers when available, and the operator hint (e.g. `cursor-agent mcp login <name>` for Cursor). Unknown `on_auth_defer` channels still fail at config load. `loopr provision` exercises the same authorize path as Firing. The next schedule, manual run, or Handoff Trigger retries naturally.

Primary test seam: `run_firing` with FakeAdapter authorize outcomes (not-ready / timeout) and an injectable notifier.

## Acceptance criteria

- [ ] Not-ready or authorize timeout (60s) skips agent spawn and completes the run as error with Log detail
- [ ] Auth-defer delivers a Notification on `on_auth_defer.notify` including Loop, MCP name(s), and login hint
- [ ] No pause/resume or held “waiting for auth” Firing state
- [ ] `loopr provision` runs the same authorize path as Firing Provisioning
- [ ] `run_firing` tests prove skip + Notification without real Cursor UI; Cursor Adapter timeout/not-ready covered with stubbed process runner

## Blocked by

- [01 — Global MCP Capability + Adapter authorize](01-global-mcp-adapter-authorize.md)
