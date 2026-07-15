# Loopr

A lightweight CLI that schedules recurring agent work. Loopr owns *when* work runs,
*what* gets handed to an agent, and *what came back* — not the agent's internal
reasoning.

You declare **Loops** in `loopr.yaml`; a per-user background daemon fires them on a
schedule, optionally hands each **Result** off to another Loop or to a human, and records
every run (raw **Log** + structured **Result**).

See [`CONTEXT.md`](./CONTEXT.md) for the domain vocabulary, [`docs/adr/`](./docs/adr) for
architecture decisions, [`SKILL.md`](./SKILL.md) for driving Loopr from an agent, and
[Example: paper deep review](#example-paper-deep-review) for a full setup walkthrough with
API keys, MCP, and a two-loop handoff chain.

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

## Setup

Loopr discovers `loopr.yaml` by searching upward from the current directory. Point it at
a config explicitly with `--config /path/to/loopr.yaml` when needed.

### Install Loopr and the Cursor agent

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

Agent Loops (`agent: cursor`, the default) shell out to `cursor-agent`, which must be on
`PATH` and authenticated for the user that runs the daemon. Verify your install and the
model slug you pin in `loopr.yaml`:

```bash
cursor-agent --version
cursor-agent --list-models
```

### Cursor API key

Create a key in the Cursor dashboard (**Settings → API Keys**; value looks like `crsr_...`).

For **manual / interactive** runs, export it in your shell (add to `~/.bashrc` to persist):

```bash
export CURSOR_API_KEY="crsr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

For the **daemon**, a login shell's exports aren't visible, so pin the key on the service.
Install the unit first, then add a drop-in override (keeps the secret out of the unit file
and out of git):

```bash
loopr daemon install
systemctl --user edit loopr.service
```

```ini
[Service]
Environment=CURSOR_API_KEY=crsr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

Then reload, enable, and start:

```bash
systemctl --user daemon-reload
systemctl --user enable --now loopr.service
loginctl enable-linger "$USER"   # keep daemon running after logout
```

The override lives at `~/.config/systemd/user/loopr.service.d/override.conf` (mode `600`).
Treat it like any other secret — never commit it.

### MCP servers

`cursor-agent` reads MCP config from the user's global `~/.cursor/mcp.json`. Loopr can also
**provision** MCP entries into a workspace's `.cursor/mcp.json` via `capabilities` (see
[Capabilities](#capabilities)), but prefer the global file when the workspace is a git repo
and you do not want a tracked MCP config committed.

Example global entry for a local arXiv MCP (no API key required):

```json
{
  "mcpServers": {
    "arxiv-local": {
      "command": "~/.local/bin/arxiv-mcp-server",
      "args": []
    }
  }
}
```

Install the binary:

```bash
uv tool install arxiv-mcp-server
# symlink lands on ~/.local/bin/arxiv-mcp-server — ensure that is on PATH
```

### Git push (workspace repos)

Loops that commit and push from their workspace need working `git` credentials for the
daemon user (SSH agent, credential helper, or a deploy key). Loopr does not manage git
auth.

### Start the scheduler

```bash
loopr daemon run              # foreground (good for debugging)
loopr daemon status           # health + next firings + active leases
loopr daemon install          # systemd/launchd autostart unit
```

After editing schedules or adding Loops, restart the daemon so it reloads
(`systemctl --user restart loopr.service` for a systemd install).

## Capabilities

Declare what a Loop needs under `capabilities:` in `loopr.yaml`. Provisioning runs before
every Firing and is idempotent (no-op when already present).

```yaml
capabilities:
  - type: skill
    name: teach
    path: .agents/skills/teach/SKILL.md   # → <workspace>/.cursor/skills/teach/SKILL.md
  - type: mcp
    name: dashboards
    server: { command: dashboards-mcp }     # merged into <workspace>/.cursor/mcp.json
  - type: tool
    name: gh                                # must be on PATH; optional install: "brew install gh"
```

| Kind | What provisioning does | When to use |
| --- | --- | --- |
| **skill** | Copies `path` → `<workspace>/.cursor/skills/<name>/SKILL.md` | Reusable workflow docs referenced from the mission |
| **mcp** | Merges `server` into `<workspace>/.cursor/mcp.json` | Self-contained workspace; no global MCP setup |
| **tool** | Verifies binary on PATH; runs `install` if missing | `git`, `gh`, custom CLIs the mission shells out to |

**Global MCP vs capability:** if the MCP is already in `~/.cursor/mcp.json` and the
workspace should not get a committed `.cursor/mcp.json`, omit the capability and reference
the server by name in the mission instead.

## Example: paper deep review

The parent monorepo's [`loopr.yaml`](../loopr.yaml) wires a two-loop chain for curating ML
papers in `./relational`:

| Loop | Schedule | Role |
| --- | --- | --- |
| `tabular-paper-radar` | `0 9 * * 0` (Sun 09:00) | Search arXiv, append new papers to `CURRICULUM_STAGE.md`, commit+push |
| `paper-deep-review` | none (handoff only) | Write `reviews/<arxiv_id>.md` for every staged but un-reviewed paper, commit+push |

When the radar returns `{"status":"staged",...}`, Loopr automatically fires
`paper-deep-review` with that Result as context. Both Loops share workspace `./relational`,
so the per-workspace **Lease** serializes them.

### What is configured for these Loops

| Requirement | How it is set up |
| --- | --- |
| **API key** | `CURSOR_API_KEY` (`crsr_...`) for `cursor-agent` — see [Cursor API key](#cursor-api-key) |
| **Agent** | `agent: cursor`, `model: claude-opus-4-8-thinking-high` |
| **MCP** | Global `arxiv-local` in `~/.cursor/mcp.json` — **not** a `capabilities` entry |
| **Skills** | None — the mission text is self-contained (no SKILL.md provisioned) |
| **Tools** | `cursor-agent`, `arxiv-mcp-server`, `git` on PATH; git remote auth for push |
| **Workspace** | `./relational` (git repo with `CURRICULUM_STAGE.md` and `reviews/`) |

The paper Loops use these `arxiv-local` tools: `search_papers`, `get_abstract`,
`download_paper`, `read_paper`.

### Run deep review manually

From the directory that contains `loopr.yaml` (the monorepo root):

```bash
export CURSOR_API_KEY="crsr_..."    # if not already in the environment
loopr run paper-deep-review
```

The Loop is idempotent: it only writes reviews for staged papers that lack
`reviews/<arxiv_id>.md`. If nothing is pending it exits with
`{"status":"none","summary":"nothing to review"}` and makes no file changes.

### Run the full chain (radar → deep review)

```bash
loopr run tabular-paper-radar
# if new papers were staged, paper-deep-review fires automatically
```

### Inspect a firing

```bash
loopr runs                          # find the run id
loopr logs <run-id> -f              # follow live (stream-json from cursor-agent)
loopr show <run-id>                 # Log + parsed Result after completion
```

Expected Result shapes:

```json
{"status":"ok","summary":"Reviewed 2 paper(s): 2607.05476, 2607.05380","artifacts":[{"type":"file","url":"reviews/"}]}
{"status":"none","summary":"nothing to review"}
{"status":"issues","summary":"arxiv-local MCP error: ..."}
```

On `status: ok` or `status: issues`, a CLI notification is emitted (human handoff).

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
