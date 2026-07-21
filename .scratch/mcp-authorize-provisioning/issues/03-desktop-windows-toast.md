# 03 — Desktop Notification channel (Windows toast from WSL)

Status: ready-for-agent

## Parent

[.scratch/mcp-authorize-provisioning/PRD.md](../PRD.md)

## What to build

Ship a `desktop` Notification channel that delivers a Windows host toast when Loopr runs under WSL2, so auth-defer (and any other human Notification using this channel) is visible outside the daemon’s CLI. Keep the channel behind the existing pluggable Notification interface; inject the low-level toast runner so tests never depend on a real Windows UI. `cli` remains available. Email/Slack stay out of scope but the same `notify:` name mechanism must work for `desktop`.

## Acceptance criteria

- [ ] `desktop` is a known Notification channel selectable via `notify: desktop` / `on_auth_defer.notify: desktop`
- [ ] On WSL2, delivery invokes a Windows host toast (not Linux-only `notify-send` alone)
- [ ] Toast runner is injectable; unit tests assert title/body dispatch without showing a real toast
- [ ] Auth-defer path can target `desktop` the same way it targets `cli`

## Blocked by

- [02 — Auth defer: skip Firing + Notification](02-auth-defer-skip-notify.md)
