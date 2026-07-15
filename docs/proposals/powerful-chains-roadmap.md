# Proposals — Improvements for powerful agentic chains

Status: proposed

Forward-looking roadmap, not yet built. It records where Loopr sits today, the
improvements that unlock materially more powerful chains, and an honest comparison against
a plain scheduler + shell scripts. Improvements are ranked by the chain power they unlock.

## Where Loopr is today

Loopr is a **durable scheduler + predicate-driven router**, not a conversation manager.
Three properties of the engine shape every design decision:

1. **Each Firing is a fresh, stateless `cursor-agent` process** (`-p --force
   --approve-mcps`) with full file/shell/git access and no memory between Firings. The
   inner think→act→observe loop belongs to the agent; Loopr owns *cadence* and *routing*.
2. **The Handoff payload is tiny** — only `status` + `summary` are injected downstream
   (`firing.py::_augment_mission`); `next` and `artifacts` are dropped.
3. **A Loop cannot re-trigger itself or anything already in the chain** — the
   `chain.visited` guard in `handoff.py::process_handoffs`.

The design rules that fall out of this (and that every good Loop obeys):

- **State lives in the Workspace/git, never in the Handoff.** "Reviewed" ≡
  `reviews/<id>.md` exists. That is what makes a Loop idempotent and resumable.
- **Convergence = repeated idempotent scheduled Firings**, not an in-Loopr while-loop.
- **Risky output terminates at an artifact (a PR); a human acts on it.** No approval gates;
  fire-and-notify (`docs/adr/0003`).

Net: today Loopr is **"recurring idempotent tasks with conditional routing."** Real and
useful, but not yet "agentic loops" in the strong sense — because a Loop can't iterate
toward a goal within a chain.

## The gap that matters most

The marquee use case — *"fix → test → if red, try again → escalate after N tries"* — is
impossible today. Convergence only happens at the external scheduler's coarse cadence
(e.g. daily). Closing this gap (Improvement A) changes Loopr's category.

## Improvements, ranked by chain power unlocked

### A. Bounded self-iteration (`retry: {max, while}`) — highest leverage
Relax the `visited` guard into an explicit, capped re-fire while a predicate holds (e.g.
`while: 'result.status == "red"'`, `max: 5`). Small, contained change to
`process_handoffs` plus a `retry` field on the Loop; preserves the "no LLM in routing"
principle (`docs/adr/0001`, `docs/adr/0006`).
- **Unlocks:** self-healing CI ("green-keeper"), review→implement→review convergence.

### B. Firing timeouts + failure/retry policy
`firing.py` calls `subprocess.run` with **no timeout**, so a hung agent holds the
Workspace Lease indefinitely. Add per-Loop `timeout`, `on_failure: notify|retry|trigger`,
and backoff. Let predicates route on run outcome (exit code, timed-out), not just Result.
- **Unlocks:** reliable 24/7 unattended operation; chains that react to failure/timeout.
- Prerequisite for trusting any ambitious chain overnight.

### C. Stateful predicates (run history)
Predicates only see the current Result (`predicate.py` allows only the `result` name).
Give `when:` read access to prior runs — `consecutive_failures >= 3`,
`status_changed_since_last`, `summary != runs.last.summary`.
- **Unlocks:** noise-free monitors — "escalate only after 3 straight failures," "notify
  only if the situation changed." Kills alert fatigue.

### D. Real notification channels (Slack / GitHub PR comment / webhook / email)
Only `cli` ships (`notify.py::_BUILDERS`), and it is a clean extension point (`Channel`
protocol). 
- **Unlocks:** team-facing chains — the difference between "I check the terminal" and "the
  loop pings on-call with the PR link." Cheapest high-visibility win; pairs with every
  monitor→fixer→notify chain.

### E. Dynamic fan-out / fan-in (`for_each` + a join Loop)
Today one Loop must be declared per target. Add `for_each: <file|command>` that expands
into N parallel per-Workspace Firings (Loopr already parallelizes across Workspaces via
the Lease), plus a join Loop that waits for and aggregates their Results.
- **Unlocks:** fleet-wide operations — "apply this codemod to all 40 services → 40 PRs in
  parallel → one rollout digest." This is where Loopr decisively beats cron+bash
  (per-target agent reasoning + parallelism + aggregation).

### F. Richer Handoff payload
Pass `next` and a bounded `artifacts` list downstream, not just `status` + `summary`
(extend `firing.py::_augment_mission`). Keep it bounded to avoid context bloat.
- **Unlocks:** precise pipelines — upstream computes the exact work list (arXiv IDs,
  changed files) and downstream consumes it instead of re-deriving from the filesystem.

### G. Opt-in approval-gated Handoff
A Handoff that stops on an artifact and resumes when a human acts (PR merged, reaction,
`loopr approve <run>`). Deliberately absent today (`docs/adr/0003`); make it explicit and
time-boxed so the non-blocking default is preserved.
- **Unlocks:** safe human-in-the-loop for deploys/migrations.

## Flagship chains these enable

| Chain | Needs | Behavior |
| --- | --- | --- |
| **Green-keeper** | A + B + D | Red `main` → fix → test → iterate to green or escalate to Slack with the diff |
| **Fleet migration** | E + F | Fan out `libX vN→vN+1` across all services → parallel PRs → fan-in dashboard + one ping |
| **Noise-free incident→fix** | C + D + F | Hourly Sentry query, act only on new/worsening errors, fixer gets exact issue IDs, opens PR, pings on-call |
| **Release train** | E + G | Collect merged PRs → changelog + version-bump PR → human approval → tag + publish |
| **Spec→implement→review→iterate** | A + F | Reviewer findings feed back to the implementer, bounded, until clean |

## Reasonable now vs. scheduler + bash?

Honest, and it depends on how many Loops and how much conditionality you have.

**Single scheduled agent task:** cron + `cursor-agent -p` in ~15 lines of bash is fine, and
Loopr is over-engineered for it.

**Where Loopr already earns its place** (re-implementing in bash means writing a worse,
untested version):

- **Conditional loop→loop Handoffs** via a *deterministic* predicate over structured JSON —
  no LLM in the routing path. In bash you hand-roll JSON parsing + if-trees per pipeline.
- **Per-Workspace Leases**: serialize same-repo Firings, parallelize across repos. That is
  `flock` + manual orchestration you would get subtly wrong.
- **A durable run journal** (sqlite) with `runs / show / logs -f` and live stream-json.
- **Idempotent provisioning** of skills/MCP/tools before each Firing.

**Tipping point:** the moment you want ≥2 Loops, conditional chains, or a real audit trail,
hand-rolled bash crosses into "reinventing Loopr, badly." The existing radar→review chain
is already past that line.

**Honest caveat:** without self-iteration (A) and failure/timeout handling (B), the
headline "agentic loop that converges until done" does not exist yet — today it is
"recurring idempotent tasks with conditional routing," which sits *just* over the bash
line, not far past it. Landing A, B, and C moves Loopr firmly into orchestration territory
you would not want to maintain as shell scripts.

## Suggested sequencing

1. **A (bounded retry)** and **B (timeout + failure routing)** — self-contained, highest
   leverage, unblock the flagship chains. Land with tests; existing chains untouched.
2. **D (Slack/webhook channel)** — easy high-visibility follow-up.
3. **C (stateful predicates)**, then **E/F/G** as fan-out and human-in-the-loop needs arise.
