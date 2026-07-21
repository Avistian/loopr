# Issue 03 — Desktop Notification channel (Windows toast from WSL)

**Source:** `.scratch/mcp-authorize-provisioning/issues/03-desktop-windows-toast.md`  
**Parent plan:** `docs/plans/2026-07-21-mcp-authorize-provisioning.md`  
**Blocked by:** issue 02 (auth-defer Notification path must exist)

## What to build

Ship a `desktop` Notification channel that delivers a Windows host toast when Loopr runs under WSL2, so auth-defer (and any other human Notification using this channel) is visible outside the daemon’s CLI. Keep the channel behind the existing pluggable Notification interface; inject the low-level toast runner so tests never depend on a real Windows UI. `cli` remains available. Email/Slack stay out of scope but the same `notify:` name mechanism must work for `desktop`.

## Acceptance criteria

- [ ] `desktop` is a known Notification channel selectable via `notify: desktop` / `on_auth_defer.notify: desktop`
- [ ] On WSL2, delivery invokes a Windows host toast (not Linux-only `notify-send` alone)
- [ ] Toast runner is injectable; unit tests assert title/body dispatch without showing a real toast
- [ ] Auth-defer path can target `desktop` the same way it targets `cli`

## Implementation notes

Locked design (do not reopen):

- Register `desktop` in `notify.py` `_BUILDERS`.
- `DesktopChannel` takes injectable `toast: Callable[[str, str], None]` (title, body).
- Default toast: invoke `powershell.exe` with a small WinRT/Toast script (BurntToast-free) on the Windows host from WSL. Delivery failures should log and continue (match robust CLI channel behavior) — do not crash the daemon hard.
- Default runner selected at `get_channel("desktop")` construction; tests inject a list-append toast.

TDD task order:

1. **Channel registration + inject** — `tests/test_notify.py`: `desktop` in `known_channels()`; deliver calls injected toast with title/body from `Notification.render()` (or auth-defer-friendly title).
2. **Default Windows toast helper** — unit-test expected `powershell.exe` argv (mock `subprocess.run`), not that a toast appears.
3. **Config** — `on_auth_defer.notify: desktop` loads once channel exists.

No real toast required in CI. Validate: `uv run pytest -m 'not e2e'`.

## Done when

All acceptance criteria above are met, `uv run pytest -m 'not e2e'` is green, and the agent prints `GNHF_DONE`.
