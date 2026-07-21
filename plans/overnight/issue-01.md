# Issue 01 — Global MCP Capability + Adapter authorize (happy path)

**Source:** `.scratch/mcp-authorize-provisioning/issues/01-global-mcp-adapter-authorize.md`  
**Parent plan:** `docs/plans/2026-07-21-mcp-authorize-provisioning.md`  
**Blocked by:** none

## What to build

Let a Loop declare an MCP Capability by name only (no `server` block) meaning “use the global MCP entry; authorize it; do not write Workspace MCP config.” When `server` is present, keep today’s merge behavior and then authorize. Provisioning asks the Loop’s Adapter to authorize each MCP Capability. The Adapter protocol gains that authorize operation: Cursor implements enable → login → verify `ready`; Command no-ops. Require `on_auth_defer.notify` at config load whenever any MCP Capability is declared (`cli` is an allowed channel for this slice). When authorize succeeds, a Firing proceeds as today (including Cursor `--approve-mcps`). Skill and tool Capabilities stay unchanged. Idempotent across Loops sharing a Workspace.

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

## Implementation notes

Locked design (do not reopen):

- `McpCapability.server: dict | None = None` — omit/`None` ⇒ authorize-only, no Workspace `mcp.json` write.
- `Loop.on_auth_defer_notify: str | None` from YAML `on_auth_defer.notify`.
- Require `on_auth_defer.notify` at load when any MCP Capability exists (channel in `known_channels()`).
- `provision(loop, adapter)` — after skill/mcp-merge/tool steps, for each `McpCapability` call `adapter.authorize_mcp(name)` and record a `ProvisionAction`.
- Adapter protocol: `authorize_mcp(self, name: str) -> AuthorizeResult` with `ok: bool` and `detail: str`.
- Cursor: subprocess `{binary} mcp enable|login|list` (injectable runner); happy path in this issue (timeout/not-ready fully wired in 02, but implement real enable/login/ready sequence here).
- Command: `authorize_mcp` returns `ok=True` immediately (no-op).
- FakeAdapters in tests must grow the method.

TDD task order:

1. **Config** — optional `server`; parse/validate `on_auth_defer`; update MCP fixtures in `tests/test_config.py`.
2. **Provision** — `_ensure_mcp`: `server is None` → skip merge; dict → keep merge.
3. **Adapter** — Protocol + Cursor happy path + Command no-op; tests in `tests/test_adapters.py`; update FakeAdapter / ResultAdapter.
4. **Wire** — provision calls authorize; bad outcome e.g. `unauthorized` in `_BAD_OUTCOMES`; `firing.py` uses `provision(loop, adapter)`; `run_firing` happy path with FakeAdapter.
5. **Docs (light)** — README Capabilities note (full wording can finish in 04).

Prefer extending existing modules; no new subsystem packages. Never call real `cursor-agent mcp` in default unit tests.

Validate after each green cluster: `uv run pytest -m 'not e2e'`.

## Done when

All acceptance criteria above are met, `uv run pytest -m 'not e2e'` is green, and the agent prints `GNHF_DONE`.
