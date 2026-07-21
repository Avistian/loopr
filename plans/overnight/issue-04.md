# Issue 04 — Wire paper Loops to global `arxiv-local`

**Source:** `.scratch/mcp-authorize-provisioning/issues/04-wire-paper-loops.md`  
**Parent plan:** `docs/plans/2026-07-21-mcp-authorize-provisioning.md`  
**Blocked by:** issue 03 (`desktop` channel must exist)

## What to build

Update the operator Loops that need arXiv MCP — `tabular-paper-radar` and `paper-deep-review` — to declare a global MCP Capability for `arxiv-local` and `on_auth_defer.notify: desktop`. Remove comments that say not to declare the MCP Capability. End state: a Sunday (or manual) Firing either runs with usable `arxiv-local`, or skips and Windows-toasts the operator to run login; after login, the next Trigger succeeds.

## Acceptance criteria

- [ ] Both Loops declare `type: mcp` / `name: arxiv-local` without `server`, plus `on_auth_defer.notify: desktop`
- [ ] Stale comments about omitting the MCP Capability are updated to match the new model
- [ ] Manual check documented or performed: unauth → toast + skip; `cursor-agent mcp login arxiv-local` → re-run proceeds

## Implementation notes

Locked design / tasks:

1. Update operator `loopr.yaml` (Projects root) for `tabular-paper-radar` and `paper-deep-review`:

```yaml
capabilities:
  - type: mcp
    name: arxiv-local
on_auth_defer:
  notify: desktop
```

2. Replace comments that say not to declare the MCP Capability with a short note pointing at global authorize-only.
3. Align `README.md` example / capabilities table with omit-`server` + authorize + `on_auth_defer`.
4. Manual verify (operator): break auth → `loopr run tabular-paper-radar` → Windows toast + skip; `cursor-agent mcp login arxiv-local` → re-run succeeds. Document result in issue comments or plan notes if performed; if environment cannot show a toast, document the attempted steps and blockers.
5. Optional ADR `docs/adr/0008-mcp-authorize-in-provisioning.md` summarizing omit-server, skip+notify, Adapter authorize, required `on_auth_defer`, desktop=Windows toast.

Config must load with unit suite green. Do not require live toast success in CI.

Validate: `uv run pytest -m 'not e2e'` (and config load for operator yaml if covered).

## Done when

Both Loops and README/comments match the new model, optional ADR written if straightforward, validate gate is green, and the agent prints `GNHF_DONE`. Note any manual toast check status in the PR/summary.
