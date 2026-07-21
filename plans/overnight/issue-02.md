# Issue 02 — Auth defer: skip Firing + Notification

**Source:** `.scratch/mcp-authorize-provisioning/issues/02-auth-defer-skip-notify.md`  
**Parent plan:** `docs/plans/2026-07-21-mcp-authorize-provisioning.md`  
**Blocked by:** issue 01 (must already be merged or present on the branch)

## What to build

When Adapter authorize does not reach `ready` (missing server, login failure, or 60s timeout), skip this Firing: do not spawn the agent, record an error run with a clear Log preamble, deliver a Notification on the Loop’s `on_auth_defer` channel, and release normally — no parked Firing or resume API (ADR 0003). The Notification names the Loop, MCP server(s), run/log pointers when available, and the operator hint (e.g. `cursor-agent mcp login <name>` for Cursor). Unknown `on_auth_defer` channels still fail at config load. `loopr provision` exercises the same authorize path as Firing. The next schedule, manual run, or Handoff Trigger retries naturally.

Primary test seam: `run_firing` with FakeAdapter authorize outcomes (not-ready / timeout) and an injectable notifier.

## Acceptance criteria

- [ ] Not-ready or authorize timeout (60s) skips agent spawn and completes the run as error with Log detail
- [ ] Auth-defer delivers a Notification on `on_auth_defer.notify` including Loop, MCP name(s), and login hint
- [ ] No pause/resume or held “waiting for auth” Firing state
- [ ] `loopr provision` runs the same authorize path as Firing Provisioning
- [ ] `run_firing` tests prove skip + Notification without real Cursor UI; Cursor Adapter timeout/not-ready covered with stubbed process runner

## Implementation notes

Locked design (do not reopen):

- Cursor authorize wall-clock **60s** for enable+login+list (`subprocess.run(..., timeout=60)` or cumulative budget); timeout → not ok.
- Not-ready / timeout → existing skip path (`STATUS_ERROR`, no spawn) **plus** Notification on `loop.on_auth_defer_notify`.
- Inject `notifier` into `run_firing` (same pattern as `handoff.py` `Notifier`), default `deliver`.
- Notification: source=loop name, channel=`on_auth_defer_notify`, summary/detail with MCP names + `cursor-agent mcp login <name>` hint, `run_id` / `log_path` when available.
- Only notify on MCP authorize failure (outcome `unauthorized` / timeout), not every tool-missing failure.
- Add **`loopr provision <loop>`** CLI: load config, resolve adapter, run `provision`, print report, exit non-zero if not ok (print report only; Notification optional for CLI).

TDD task order:

1. **Cursor timeout / not-ready** — stub runner: list not ready → `ok=False`; hang → timeout → `ok=False`.
2. **`run_firing` skip + notify** — FakeAdapter fail; injectable notifier; assert `STATUS_ERROR`, no agent argv, notifier once; tool-missing still skips but does **not** auth-defer notify.
3. **Wire notifier** — `run_firing(..., notifier=...)`; CLI/daemon keep default `deliver`.
4. **`loopr provision`** — Typer command in `cli.py`; tests in `test_cli.py`.

Prefer FakeAdapter as primary seam. Never call real Cursor UI or Windows toast in unit tests.

Validate: `uv run pytest -m 'not e2e'`.

## Done when

All acceptance criteria above are met, `uv run pytest -m 'not e2e'` is green, and the agent prints `GNHF_DONE`.
