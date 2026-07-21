# MCP authorize in Provisioning

Status: ready-for-agent

## Problem Statement

When a scheduled or manual Loop Firing needs an MCP server (for example `tabular-paper-radar` needing `arxiv-local`), the agent often hits permission / auth errors because the server is configured but not authorized for the headless Cursor session. Today Provisioning only merges Workspace MCP config and verifies tools; `--approve-mcps` on the Cursor Adapter is not enough for servers that still need `mcp login`. Loops that intentionally use a global MCP entry (to avoid committing Workspace `.cursor/mcp.json`) have no way to declare “authorize this server before firing.” A daemon Notification on `cli` is easy to miss, so a failed auth attempt is invisible until the next time someone inspects logs.

## Solution

Extend Provisioning so MCP Capabilities are made *usable* before a Firing: the Loop’s Adapter authorizes each required MCP server (Cursor: enable + login, verify `ready`, 60s timeout). MCP Capabilities may omit `server` to mean “global config only — authorize, do not write Workspace MCP config.” If authorization is not ready, skip this Firing (no park/resume), notify the human on a required per-Loop visible channel (`on_auth_defer.notify`), and let the next Trigger retry. Ship a `desktop` Notification channel that shows a Windows toast from WSL. Update paper-radar / deep-review Loops to declare `arxiv-local` this way.

## User Stories

1. As a Loop author, I want to declare an MCP Capability with only a name (no `server` block), so that Loopr authorizes a global MCP entry without writing Workspace MCP config.
2. As a Loop author, I want declaring `server` on an MCP Capability to still merge Workspace MCP config *and* authorize that server, so that self-contained Workspaces keep working.
3. As a Loop author, I want config load to fail if I declare any MCP Capability without `on_auth_defer.notify`, so that I cannot ship a Loop that silently skips Firings with no visible alert.
4. As a Loop author, I want to set `on_auth_defer.notify: desktop` on `tabular-paper-radar`, so that auth failures are visible on my Windows session.
5. As a Loop author, I want the same MCP + `on_auth_defer` declaration on `paper-deep-review`, so that handoff-triggered reviews do not fail on unauthorized `arxiv-local`.
6. As a Loop operator, I want Provisioning to try authorizing MCP servers before spawning the agent, so that routine Firings self-heal when login can succeed headlessly.
7. As a Loop operator, I want authorization attempts to time out after 60 seconds, so that a browser/popup-bound `mcp login` cannot hold a Workspace Lease indefinitely.
8. As a Loop operator, I want a Firing to be skipped (not parked) when MCP auth is not ready, so that the daemon stays simple and ADR 0003 (no approval gates) remains intact.
9. As a Loop operator, I want the next schedule, manual run, or Handoff Trigger to retry authorization automatically, so that fixing auth once unblocks future Firings without a resume API.
10. As a Loop operator, I want a desktop Notification when auth defer happens, so that I notice the problem without watching CLI output from a systemd user service.
11. As a Loop operator on WSL2, I want the `desktop` channel to show a Windows toast on the host, so that the alert appears where I actually look.
12. As a Loop operator, I want the auth-defer Notification to name the Loop, the MCP server, and the exact login command to run, so that I can fix it quickly.
13. As a Loop operator, I want the skipped attempt recorded as a run with an error status and a Log preamble, so that I can audit what happened.
14. As a Loop operator, I want `loopr provision <loop>` to exercise MCP authorization the same way a Firing does, so that I can debug auth without waiting for the schedule.
15. As an agent Adapter author, I want MCP authorization to be an Adapter responsibility, so that Cursor’s `mcp` CLI is not hardcoded into Provisioning forever.
16. As an agent Adapter author, I want the Cursor Adapter to implement authorize via `mcp enable`, `mcp login`, and status/`ready` verification, so that headless Cursor Loops match how Cursor expects MCP auth to work.
17. As an agent Adapter author, I want non-Cursor Adapters (e.g. `command`) to no-op or skip MCP authorize cleanly, so that command Loops are unaffected.
18. As a future Adapter author (claude/codex), I want a clear authorize hook to implement later, so that MCP-using Loops on those agents can get the same Provisioning guarantee.
19. As a Loop author, I want Skill and tool Capability behavior unchanged, so that existing Loops keep provisioning as before.
20. As a Loop author, I want shared Workspaces to remain conflict-free when multiple Loops declare the same global MCP name, so that authorize stays idempotent.
21. As a daemon operator, I want auth-defer Notifications to use the Notification subsystem (not a one-off side channel), so that future email/Slack channels can be selected the same way.
22. As a daemon operator, I want email Notification to remain out of this slice but possible later via the same `notify:` channel name, so that I can switch `on_auth_defer.notify` without redesigning Provisioning.
23. As a Loop author, I want unknown `on_auth_defer.notify` channel names to fail at config load, so that typos are caught before Sunday morning.
24. As a Loop operator, I want `--approve-mcps` on Cursor Firings to remain, so that tool-use approval is still automatic after the server is authorized.
25. As a Loop operator, I want a missing global MCP server (not in global/workspace MCP config) to count as not ready, so that Provisioning defers instead of spawning a doomed agent.
26. As a Loop operator, I want a successful authorize path to leave no extra human steps when status is already `ready`, so that happy-path Firings stay fast.
27. As a reviewer of Loopr, I want this behavior documented against Provisioning / Capability / Adapter / Notification vocabulary, so that agents and humans share one language.
28. As a maintainer, I want tests at `run_firing` with a FakeAdapter authorize outcome, so that skip-vs-fire and Notification delivery are proven without real Cursor or Windows UI.
29. As a maintainer, I want the desktop channel’s Windows-toast runner injectable in tests, so that CI never depends on a real toast.
30. As a user of the paper-radar chain, I want Sunday Firings to either stage papers or toast me to authorize `arxiv-local`, so that I never discover MCP permission errors only in opaque agent Logs.

## Implementation Decisions

- Extend MCP Capability so `server` is optional. Absence means global authorize-only: do not create or modify Workspace `.cursor/mcp.json`. Presence means merge-as-today, then authorize.
- Require `on_auth_defer.notify` at config load whenever a Loop has one or more MCP Capabilities. Channel must be a known Notification channel.
- Shape (decision-rich schema, not a prototype demo):

```yaml
capabilities:
  - type: mcp
    name: arxiv-local
on_auth_defer:
  notify: desktop
```

- Provisioning remains the pre-Firing step that makes Capabilities ready. For each MCP Capability it still handles config merge when applicable, then asks the Loop’s Adapter to authorize that MCP name.
- Adapter protocol gains an authorize-MCP operation used by Provisioning. Cursor implements it; Command does not authorize (no MCP). Unknown future agents add their own implementation.
- Cursor authorize sequence: ensure approved (`mcp enable`), attempt `mcp login <name>`, verify ready (e.g. via `mcp list` / status). Overall wall-clock budget 60s; on timeout or not-ready, Provisioning reports failure for that Capability.
- On authorize failure: do not spawn the agent; complete the run as error/skipped with Log detail; deliver a Notification on the Loop’s `on_auth_defer` channel; release any Lease normally (no parked Firing state). Aligns with ADR 0003.
- Notification payload for auth defer includes Loop name, MCP server name(s), run/log pointers when available, and the operator command hint (`cursor-agent mcp login <name>` for Cursor).
- Add `desktop` Notification channel. On this project’s target environment (WSL2), delivery is a Windows host toast invoked from WSL (PowerShell / toast bridge). Inject the low-level toast command/runner for tests and portability.
- Keep `cli` channel; it remains valid for `on_auth_defer.notify` if someone chooses it, but paper Loops should use `desktop`.
- Firing orchestration already skips spawn when Provisioning is not ok; wire auth-defer Notification into that failure path (not via Result handoff predicates — no Result exists yet).
- `loopr provision` must run the same authorize path as Firing Provisioning.
- Update the live paper Loops that need `arxiv-local` to declare the global MCP Capability + `on_auth_defer.notify: desktop`, and remove comments that say not to declare the MCP Capability.
- Do not invent pause/resume, auth TTLs, or a “resume firing” CLI.
- Prefer extending existing modules (config, provision, adapters, notify, firing) over new subsystems.

## Testing Decisions

- Good tests assert external behavior only: config accepted/rejected, Workspace files written or not, whether the agent process would spawn, run status, Notification delivered to the chosen channel, authorize CLI argv/timeout boundaries when testing the Cursor Adapter with a stubbed process runner. Do not assert internal helper structure or private call order beyond what the public report/Notification exposes.
- **Primary seam: `run_firing`**, with a FakeAdapter that implements authorize outcomes (ready / not-ready / timeout) and an injectable notifier. Assert: ready → agent runs; not ready → no spawn, error status, Notification on `on_auth_defer` channel.
- Supporting tests on existing modules (prior art: provision, config, adapters, notify, firing test files):
  - Config: omit-`server` MCP parses; MCP without `on_auth_defer` errors; unknown notify channel errors; `server` present still parses as merge+authorize.
  - Provision: global MCP leaves Workspace MCP config untouched; merge path still preserves existing servers; authorize failure marks report not ok.
  - Adapter: Cursor authorize uses enable/login/ready with 60s budget against a fake subprocess; Command authorize is a no-op success when no MCP (or skipped by provision when N/A).
  - Notify: `desktop` registered in known channels; channel calls injected Windows-toast runner with title/body; no real toast in CI.
- Avoid e2e dependence on real `arxiv-local` auth or Windows UI for the default unit suite; optional manual/e2e notes may mention them under Further Notes.

## Out of Scope

- Email (or Slack) Notification channel implementation (channel name reserved for later; not required to ship).
- Parked Firings, resume commands, or approval-gate state (rejected; see ADR 0003).
- Authorizing non-MCP credentials (git, `CURSOR_API_KEY`, agent `login`) — unchanged operator responsibility.
- Declaring MCP servers by inferring names from Mission text.
- Auto-installing MCP server binaries or editing `~/.cursor/mcp.json` contents beyond enable/login/approve flows the Adapter already uses.
- Claude/Codex Adapter authorize implementations (hook only).
- Changing Lease semantics beyond “do not hold waiting for interactive human auth.”
- Broader redesign of Capabilities or a separate “Authorization” domain object outside Provisioning + Adapter.

## Further Notes

- Vocabulary lives in Loopr `CONTEXT.md` (Provisioning, Capability, Adapter, Notification, Firing, Trigger). Prefer those terms in code and docs.
- Motivating Loops: `tabular-paper-radar` and `paper-deep-review` in the operator `loopr.yaml`, both needing global `arxiv-local`.
- Cursor CLI surface used by the Cursor Adapter: `agent mcp enable|login|list` (binary overridable as today).
- Consider a follow-up ADR capturing: omit-`server` = global authorize-only; skip+notify (not park); Adapter-owned authorize; required `on_auth_defer` for MCP Loops; `desktop` = Windows toast from WSL.
- Manual verification on the operator machine: unset/break `arxiv-local` auth, `loopr run tabular-paper-radar`, confirm Windows toast and no agent work; run `cursor-agent mcp login arxiv-local`; re-run and confirm Firing proceeds.
