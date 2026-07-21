# 04 — Wire paper Loops to global `arxiv-local`

Status: ready-for-agent

## Parent

[.scratch/mcp-authorize-provisioning/PRD.md](../PRD.md)

## What to build

Update the operator Loops that need arXiv MCP — `tabular-paper-radar` and `paper-deep-review` — to declare a global MCP Capability for `arxiv-local` and `on_auth_defer.notify: desktop`. Remove comments that say not to declare the MCP Capability. End state: a Sunday (or manual) Firing either runs with usable `arxiv-local`, or skips and Windows-toasts the operator to run login; after login, the next Trigger succeeds.

## Acceptance criteria

- [ ] Both Loops declare `type: mcp` / `name: arxiv-local` without `server`, plus `on_auth_defer.notify: desktop`
- [ ] Stale comments about omitting the MCP Capability are updated to match the new model
- [ ] Manual check documented or performed: unauth → toast + skip; `cursor-agent mcp login arxiv-local` → re-run proceeds

## Blocked by

- [03 — Desktop Notification channel (Windows toast from WSL)](03-desktop-windows-toast.md)
