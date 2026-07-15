# Loopr

A lightweight CLI that schedules recurring agent work. Loopr owns *when* work runs,
*what* gets handed to an agent, and *what came back* — not the agent's internal
reasoning.

You declare **Loops** in `loopr.yaml`; a per-user background daemon fires them on a
schedule, optionally hands each **Result** off to another Loop or to a human, and records
every run (raw **Log** + structured **Result**).

See [`CONTEXT.md`](./CONTEXT.md) for the domain vocabulary, [`docs/adr/`](./docs/adr) for
architecture decisions, and [`SKILL.md`](./SKILL.md) for driving Loopr from an agent.

## Concepts

| Term | Meaning |
| --- | --- |
| **Loop** | A reusable unit of work: mission/command + workspace + optional schedule, capabilities, handoffs. |
| **Firing** | One execution of a Loop. Produces a **Log** (raw output) and an optional **Result** (structured JSON). |
| **Handoff** | Passes a Result to another Loop (conditionally) or to a human (a Notification). |
| **Capability** | Something a Loop needs provisioned first: a Skill, an MCP server, or a tool on PATH. |
| **Lease** | Per-Workspace lock so Firings sharing a Workspace never run concurrently. |

## Status

All v1 vertical slices are implemented (see [`docs/issues/`](./docs/issues)):

- **01** manual one-shot Firing · **02** scheduled firing via the daemon ·
  **03** structured Result capture · **04** conditional loop→loop Handoff ·
  **05** human Handoff (Notification) · **06** Provisioning Capabilities ·
  **07** per-Workspace Lease · **08** agent-drivable CLI (`--json` + `SKILL.md`)

Since v1:

- **Live log streaming** — the Cursor adapter runs with `--output-format stream-json`, so
  `loopr logs <run> -f` shows an agent's activity (messages, tool calls) in real time.
- **Command Loops** — `agent: command` runs an ordinary command line instead of an AI
  agent (e.g. a scheduled script).
- **Loop lifecycle** — `enabled` flag plus `loopr loop enable` / `disable` / `remove`.

## Install

For development, run against the source tree with [uv](https://docs.astral.sh/uv/):

```bash
uv sync
uv run loopr --help
```

To install `loopr` as a user CLI (and to run the daemon):

```bash
uv tool install .
# after changing the source, force a rebuild so the cache doesn't serve stale code:
uv tool install --reinstall .
```

The Cursor adapter shells out to `cursor-agent`, which must be on `PATH` and authenticated
(logged in, or `CURSOR_API_KEY` set) for the user the daemon runs as.

## Example `loopr.yaml`

```yaml
max_chain_depth: 10
loops:
  # An AI-agent Loop that hands off conditionally.
  - name: model-monitor
    mission: "Check the model dashboards and summarize anything degrading."
    workspace: ./infra
    model: claude-opus-4-8-thinking-high   # optional; pins the agent model
    schedule: "0 9 * * 1-5"                # cron, or e.g. "every 6h"
    capabilities:
      - type: skill
        name: triage
        path: ./skills/triage/SKILL.md
      - type: mcp
        name: dashboards
        server: { command: dashboards-mcp }
      - type: tool
        name: gh
    handoffs:
      - when: 'result.status == "issues"'  # predicate over the Result
        trigger: fixer                      # fire another Loop with the Result as context
  - name: fixer
    mission: "Open a PR fixing the reported issues."
    workspace: ./infra
    handoffs:
      - notify: cli                         # hand off to a human; terminates the chain

  # A command Loop: run a script on a schedule (no AI agent).
  - name: news-weekly
    workspace: ./news
    agent: command
    command: .venv/bin/python main.py --days 7
    schedule: "0 10 * * 0"                  # every Sunday at 10:00 local

  # A defined-but-paused Loop: skipped by the daemon, still runnable manually.
  - name: nightly-audit
    mission: "Audit access logs and report anomalies."
    workspace: ./infra
    schedule: "0 2 * * *"
    enabled: false
```

Schedules are either **cron** (`0 9 * * 1-5`) or **intervals** (`every 6h`, `30m`, `1d`).
Omit `schedule` for a Loop that only runs when triggered by another Loop or manually.

### The Result contract

An agent signals its outcome by writing JSON to `$LOOPR_RESULT_PATH`; Loopr routes Handoffs
on it without ever running an LLM to interpret it:

```json
{"status": "issues", "summary": "3 models degraded", "artifacts": [{"type": "pr", "url": "..."}]}
```

Only `status` is required. Predicates in `when:` may reference `result.status`,
`result.summary`, `result.next`, and `result.artifacts` with `==`, `!=`, `in`, `and`,
`or`, `not`. Chains are cycle- and depth-guarded (`max_chain_depth`).

## Usage

```bash
# Fire and inspect
loopr run model-monitor       # fire once now (runs the full handoff chain)
loopr runs                    # list past firings, newest first
loopr show <run-id>           # print the captured Log + parsed Result
loopr logs <run-id> -f        # follow a Firing live (renders stream-json events)

# Manage loops (edit loopr.yaml non-interactively)
loopr loop list               # configured loops ([disabled] shown for paused ones)
loopr loop add --name news --mission "curate news" --workspace ./news --schedule "every 6h"
loopr loop disable <name>     # stop auto-scheduling (manual runs still work)
loopr loop enable  <name>     # resume
loopr loop remove  <name>     # delete from loopr.yaml (refused if a Handoff targets it)

# Daemon
loopr daemon run              # foreground scheduler (Ctrl-C to stop)
loopr daemon status           # health + next firings + active leases
loopr daemon install          # generate a systemd/launchd autostart unit
```

After editing the schedule set, restart the daemon so it reloads
(`systemctl --user restart loopr.service` for a systemd install).

Every read/inspect command supports `--json`, and mutating commands are non-interactive,
so an agent can drive Loopr directly (see [`SKILL.md`](./SKILL.md)).

## Development

```bash
uv run pytest        # 137 tests
```
