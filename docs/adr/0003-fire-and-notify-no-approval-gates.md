# Fire-and-notify human handoff; no approval-gate machinery

A Handoff to a human is a Notification that delivers the Result and terminates the
chain. Loopr deliberately does **not** build pause/resume, approval TTLs, or a resume
interface. Human approval is achieved out-of-band by having a Loop produce an
**Artifact** the human acts on (e.g. a PR whose review *is* the approval).

## Considered Options

- **Durable approval gates (async pause/resume + TTL)** — the textbook HITL pattern, but
  rejected for v1: it is the single heaviest feature and would compromise the tool's
  lightweight goal.

## Consequences

- Loopr never holds paused human state, which keeps the daemon and state model simple.
- Workflows needing sign-off must route through reviewable Artifacts (PRs, issues).
- If true in-tool blocking approval is ever required, this decision must be revisited.
