# MCP Authorize Provisioning — all issues (sequential overnight)

**Parent plan:** `docs/plans/2026-07-21-mcp-authorize-provisioning.md`  
**Issues:** `plans/overnight/issue-01.md` … `issue-04.md` (detail); `.scratch/mcp-authorize-provisioning/issues/`

Run **in order**. Do not start issue N+1 until issue N’s acceptance criteria pass and `uv run pytest -m 'not e2e'` is green. Prefer one commit cluster per issue when committing is appropriate; do not invent product decisions — locked design in the parent plan wins.

---

## Phase 1 — Issue 01: Global MCP + Adapter authorize

Follow `plans/overnight/issue-01.md` exactly.

**Done for phase:** issue 01 AC met; unit suite green.

---

## Phase 2 — Issue 02: Auth defer skip + notify

Follow `plans/overnight/issue-02.md` exactly. Depends on phase 1.

**Done for phase:** issue 02 AC met; unit suite green.

---

## Phase 3 — Issue 03: Desktop Windows toast channel

Follow `plans/overnight/issue-03.md` exactly. Depends on phase 2.

**Done for phase:** issue 03 AC met; unit suite green. No real toast required in CI.

---

## Phase 4 — Issue 04: Wire paper Loops

Follow `plans/overnight/issue-04.md` exactly. Depends on phase 3.

Update operator `loopr.yaml` (Projects root) for `tabular-paper-radar` and `paper-deep-review`. Document manual toast check as done/skipped/blocked — do not fail the run solely because a live Windows toast could not be shown.

**Done for phase:** issue 04 AC met; unit suite green.

---

## Cross-cutting constraints

- Extend existing modules; no new subsystem packages.
- FakeAdapter is the primary seam for firing behavior; never call real `cursor-agent mcp` or show a real Windows toast in default unit tests.
- Existing MCP-with-`server` fixtures must include `on_auth_defer` once issue 01 validation lands.
- Optional ADR `docs/adr/0008-mcp-authorize-in-provisioning.md` is nice-to-have in phase 4 if time remains.

## Acceptance criteria (whole run)

- [ ] Issues 01–04 acceptance criteria all satisfied
- [ ] `uv run pytest -m 'not e2e'` green at end of run
- [ ] Global MCP omit-`server` + required `on_auth_defer` works
- [ ] Authorize failure skips Firing and notifies (cli and desktop selectable)
- [ ] Paper Loops declare global `arxiv-local` + `on_auth_defer.notify: desktop`

## Done when

All four phases are complete, the full unit suite (not e2e) is green, and the agent prints `GNHF_DONE`.
