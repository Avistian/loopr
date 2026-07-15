# Own background daemon + SQLite as the engine

A per-user Loopr daemon owns scheduling, firing, chain-triggering, leases, and state
(SQLite), autostarting via systemd/launchd. We chose this over delegating to system
cron/systemd timers because conditional loop-to-loop Handoffs, per-Workspace Leases,
and cross-Firing coordination need an owning process; cron alone makes chains and
leases awkward and OS-specific.

## Consequences

- There is a daemon to install, supervise, and keep healthy.
- Every comparable tool (crnd, cronai, Converge) made the same choice, which de-risks it.
