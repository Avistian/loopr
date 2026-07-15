# 05 — Human Handoff (Notification)

Status: done

## What to build

Let a chain terminate by delivering to a human. A Loop can declare a **Handoff** whose
target is a human; Loopr realizes it as a **Notification** that delivers the Result
(summary + links to the Log and any Artifacts) to a channel and ends the chain. Loopr
never blocks waiting on a human — per `docs/adr/0003`, approval happens out-of-band on
Artifacts (e.g. a PR), not via a pause/resume gate.

Ship at least one channel (CLI/desktop notification) with a pluggable channel interface
so Slack/email/etc. can be added later. The Notification includes the Result summary and
references to the Log and Artifacts.

```
handoffs:
  - when: result.status == "issues"
    notify: cli               # a human channel; terminates the chain
```

Vocabulary: `CONTEXT.md` (Notification, Handoff, Artifact, Result).

## Acceptance criteria

- [ ] A Loop can declare a human Handoff (notify) in `loopr.yaml`, optionally conditional on the Result
- [ ] A matching human Handoff delivers a Notification and terminates the chain
- [ ] The Notification includes the Result summary and links to the Log and any Artifacts
- [ ] At least one channel ships (CLI/desktop) behind a pluggable channel interface
- [ ] Loopr never blocks or persists paused human state

## Blocked by

- 03 — Structured Result capture (the Notification carries the Result)
