---
name: loopr
description: Schedule and manage recurring agent work with the Loopr CLI. Use when the user wants to run an agent on a schedule, chain agent loops (e.g. monitor -> fixer), or get notified when a scheduled agent finds something.
---

# Driving Loopr

Loopr schedules recurring agent work. You configure **Loops** in `loopr.yaml`; a
background daemon fires them on a schedule, hands the result off to other loops
(conditionally) or to a human, and records every run.

All commands accept `--json` for machine-readable output and never prompt interactively,
so you can drive them directly. Non-zero exit codes indicate failure; with `--json` the
error is `{"error": "..."}` on stdout.

## Setup

Loopr discovers `loopr.yaml` by searching upward from the current directory.

### 1. Install the CLI and agent

```bash
# Loopr (from the loopr/ source tree)
cd loopr && uv tool install .

# Cursor headless agent — must be on PATH for agent: cursor Loops
# (ships with Cursor Desktop or install separately)
cursor-agent --version

# Verify the model slug you pin in loopr.yaml
cursor-agent --list-models
```

After changing Loopr source, rebuild the tool cache:

```bash
uv tool install --reinstall .
```

### 2. Authenticate Cursor (API key)

Agent Loops shell out to `cursor-agent` with `-p --force --approve-mcps`. The binary
must be authenticated for the **same user** that runs the daemon.

Create a key in the Cursor dashboard (**Settings → API Keys**; value looks like
`crsr_...`).

**Interactive / one-shot runs** — export in your shell (add to `~/.bashrc` to persist):

```bash
export CURSOR_API_KEY="crsr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
```

**Daemon runs** — a login shell's exports are not visible to systemd. Pin the key on the
service instead:

```bash
loopr daemon install          # writes ~/.config/systemd/user/loopr.service
systemctl --user edit loopr.service
```

```ini
[Service]
Environment=CURSOR_API_KEY=crsr_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now loopr.service
loginctl enable-linger "$USER"   # keep daemon running after logout
```

### 3. MCP servers

`cursor-agent` reads MCP config from the user's global `~/.cursor/mcp.json`. Loopr can
also **provision** MCP entries into a workspace's `.cursor/mcp.json` via `capabilities`
(see below), but prefer the global file when the workspace is a git repo and you do not
want a tracked MCP config committed.

**The paper deep review Loops below** use the global `arxiv-local` server (not declared as a
capability in `loopr.yaml`):

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

Install the local arXiv MCP binary (no API key required):

```bash
uv tool install arxiv-mcp-server
# symlink lands on ~/.local/bin/arxiv-mcp-server — ensure that is on PATH
```

Tools exposed by `arxiv-local` that the paper Loops rely on: `search_papers`,
`get_abstract`, `download_paper`, `read_paper`.

Remote Smithery arXiv servers (`arxiv`, `arxiv-mcp-server`) also exist in the global
config but the paper Loops are written against `arxiv-local`.

### 4. Git push (workspace repos)

Several Loops commit and push from their workspace (e.g. `./relational`). Ensure the
daemon user has working `git` credentials (SSH agent, credential helper, or a
deploy key) for that remote — Loopr does not manage git auth.

### 5. Start the scheduler

```bash
loopr daemon run                # foreground (good for debugging)
loopr daemon install            # systemd/launchd autostart
loopr daemon status --json      # health + next firings + active leases
```

After editing schedules or adding Loops, restart the daemon:
`systemctl --user restart loopr.service`.

## Core vocabulary

- **Loop**: a unit of agent work (mission + workspace + optional capabilities/schedule/handoffs).
- **Firing**: one execution of a Loop; produces a raw **Log** and an optional structured **Result**.
- **Handoff**: passes a Result to another Loop (conditionally) or to a human (a Notification).
- **Capability**: a Skill, MCP server, or tool/binary that Loopr provisions into the workspace before each Firing.

## Capabilities (skills, MCP, tools)

Declare what a Loop needs under `capabilities:` in `loopr.yaml`. Provisioning runs
before every Firing and is idempotent (no-op when already present).

```yaml
capabilities:
  - type: skill
    name: teach
    path: .agents/skills/teach/SKILL.md   # copied to <workspace>/.cursor/skills/teach/SKILL.md
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
the server by name in the mission (as the paper Loops do with `arxiv-local`).

## Example: paper deep review

A two-loop chain for curating ML papers in a git workspace (`./relational`). The radar
stages papers weekly; deep review runs on handoff (or manually for testing).

| Loop | Schedule | Role |
| --- | --- | --- |
| `tabular-paper-radar` | `0 9 * * 0` (Sun 09:00) | Search arXiv, append new papers to `CURRICULUM_STAGE.md`, commit+push |
| `paper-deep-review` | none (handoff only) | Write `reviews/<arxiv_id>.md` for every staged but un-reviewed paper, commit+push |

When the radar returns `{"status":"staged",...}`, Loopr automatically fires
`paper-deep-review` with that Result as context. Both Loops share workspace `./relational`,
so the per-workspace **Lease** serializes them.

### `loopr.yaml`

```yaml
loops:
  # arXiv MCP comes from global ~/.cursor/mcp.json — NOT declared as a capability
  # (that would write a tracked .cursor/mcp.json into the workspace).
  - name: tabular-paper-radar
    workspace: ./relational
    agent: cursor
    model: claude-opus-4-8-thinking-high
    schedule: "0 9 * * 0"      # every Sunday 09:00 local
    mission: |
      You curate a staging list of papers for this ML teaching repo. Do not ask
      questions — make reasonable decisions and finish autonomously.

      Focus on these THREE closely-related threads:
      1. TABULAR MODELS & FOUNDATIONAL / TABULAR-FOUNDATION MODELS: deep learning for
         tabular data, tree ensembles vs. neural nets, TabPFN and other tabular foundation
         models, in-context learning over tables, and tabular benchmarks.
      2. RELATIONAL DEEP LEARNING (RDL): learning directly over multi-table relational
         databases — deep models across primary/foreign-key-linked tables, relational
         foundation models, and benchmarks such as RelBench.
      3. RELATIONAL GRAPH DEEP LEARNING: GNNs / graph representation learning applied to
         the schema-and-rows graph induced by a relational database (heterogeneous /
         temporal graphs from linked tables), plus message-passing and graph-transformer
         methods for that setting.
      A paper is in scope if it clearly fits ANY of the three threads. Skip work that is
      only tangentially related (e.g. generic tabular ML on a single flat table with no
      relational/graph angle is thread 1 only; pure NLP/vision GNNs are out of scope).

      1. Read ./CURRICULUM_STAGE.md if it exists (create it with a "# Curriculum staging
         — candidate papers" header if not) and CURRICULUM.md, so you know what is
         ALREADY staged or taught.
      2. Use the `arxiv-local` MCP server tools to find recent papers across all three
         threads (roughly the last 2 weeks): run separate `search_papers` queries per
         thread (categories like cs.LG/stat.ML for tabular & RDL, plus cs.DB for relational
         databases and cs.SI for graph/relational-graph work; date_from/date_to,
         sort_by=submittedDate), then `get_abstract`/`read_paper` to confirm relevance.
         Prefer reproducible, novel, or notable work.
      3. Select ONLY papers not already in CURRICULUM_STAGE.md (dedupe by arXiv id and by
         title). If there are none, stop WITHOUT changing any files.
      4. Append each new paper to ./CURRICULUM_STAGE.md as a bullet, newest at the bottom.
         Tag which thread it belongs to (tabular | RDL | relational-graph):
         - [<title>](https://arxiv.org/abs/<id>) — <authors, year>. [<thread>] <1-2
           sentences on why it matters for the curriculum>. (staged <YYYY-MM-DD>)
      5. Only if you added something, commit and push:
         git add CURRICULUM_STAGE.md && git commit -m "Stage N paper(s)" &&
         git push origin HEAD
      6. Write your outcome to $LOOPR_RESULT_PATH:
         {"status":"staged","summary":"Staged N paper(s): <short titles>",
          "artifacts":[{"type":"file","url":"CURRICULUM_STAGE.md"}]}
         If nothing new: {"status":"none","summary":"no new papers this week"}.
         Use "status":"issues" and explain if something went wrong (e.g. arXiv/MCP error).
    handoffs:
      - when: 'result.status == "staged"'
        trigger: paper-deep-review
      - when: 'result.status == "issues"'
        notify: cli

  - name: paper-deep-review
    workspace: ./relational     # same workspace -> Lease serializes with the radar
    agent: cursor
    model: claude-opus-4-8-thinking-high
    # no schedule: fires on handoff from the radar, or run manually to test
    mission: |
      You write concise review briefs for EVERY staged paper that has not been reviewed
      yet, committing them to main. Do not ask questions — make reasonable decisions and
      finish autonomously.

      1. Read ./CURRICULUM_STAGE.md and list every staged paper (arXiv id + title).
      2. A paper counts as reviewed iff ./reviews/<arxiv_id>.md already exists. Build the
         list of papers with NO such file. If that list is empty, write
         {"status":"none","summary":"nothing to review"} and STOP without changes.
      3. For EACH un-reviewed paper, in staging order:
         a. Use the `arxiv-local` MCP tools (`download_paper` then `read_paper`, or
            `get_abstract` as a fallback) to read it.
         b. Write ./reviews/<arxiv_id>.md (~1 page): problem, method, key results/numbers,
            how it fits the tabular curriculum, and caveats/limitations. Link the abstract.
      4. Commit all new reviews together and push to main:
         git add reviews/ && git commit -m "Review N staged paper(s)" &&
         git push origin HEAD
      5. Write $LOOPR_RESULT_PATH:
         {"status":"ok","summary":"Reviewed N paper(s): <short ids/titles>",
          "artifacts":[{"type":"file","url":"reviews/"}]}
         Use "status":"issues" with an explanation if you could not.
    handoffs:
      - when: 'result.status == "ok"'
        notify: cli
      - when: 'result.status == "issues"'
        notify: cli
```

### What is configured for these Loops

| Requirement | How it is set up |
| --- | --- |
| **API key** | `CURSOR_API_KEY` (`crsr_...`) for `cursor-agent` — see Setup §2 |
| **Agent** | `agent: cursor`, `model: claude-opus-4-8-thinking-high` |
| **MCP** | Global `arxiv-local` in `~/.cursor/mcp.json` — **not** a `capabilities` entry |
| **Skills** | None — the mission text is self-contained (no SKILL.md provisioned) |
| **Tools** | `cursor-agent`, `arxiv-mcp-server`, `git` on PATH; git remote auth for push |
| **Workspace** | `./relational` (git repo with `CURRICULUM_STAGE.md` and `reviews/`) |

### Run deep review manually (test without waiting for the radar)

From the directory that contains `loopr.yaml`:

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
loopr runs --json                          # find the run id
loopr logs <run-id> -f                     # follow live (stream-json from cursor-agent)
loopr show <run-id> --json                 # Log + parsed Result after completion
```

Expected Result shapes:

```json
{"status":"ok","summary":"Reviewed 2 paper(s): 2607.05476, 2607.05380","artifacts":[{"type":"file","url":"reviews/"}]}
{"status":"none","summary":"nothing to review"}
{"status":"issues","summary":"arxiv-local MCP error: ..."}
```

On `status: ok` or `status: issues`, a CLI notification is emitted (human handoff).

## Add a Loop (non-interactive)

```bash
loopr loop add --name model-monitor \
  --mission "Check the model dashboards and summarize anything degrading." \
  --workspace ./infra \
  --schedule "0 9 * * 1-5" \
  --json
```

Interval schedules also work: `--schedule "every 6h"`. Omit `--schedule` for a Loop that
only runs when triggered by another Loop or manually.

## Manage Loops

```bash
loopr loop disable <name>       # stop the daemon auto-firing it (manual runs still work)
loopr loop enable <name>        # resume auto-scheduling
loopr loop remove <name>        # delete it from loopr.yaml (refused if another Loop hands off to it)
```

`enabled: false` in `loopr.yaml` has the same effect as `disable`. After changing the
schedule set, restart the daemon so it reloads: `systemctl --user restart loopr.service`.

## Command Loops (run a script, not an agent)

Set `agent: command` and `command` to schedule an ordinary command instead of an AI agent.
The command is split with POSIX rules and run in the Workspace (no shell, so wrap
pipes/redirects in a script). It receives `$LOOPR_RESULT_PATH` and may optionally write a
Result there.

```yaml
loops:
  - name: news-weekly
    workspace: ./news
    agent: command
    command: .venv/bin/python main.py --days 7
    schedule: "0 10 * * 0"
```

## Inspect

```bash
loopr loop list --json          # configured loops ([disabled] shown for paused ones)
loopr runs --json               # past firings, newest first
loopr show <run-id> --json      # one firing incl. Log and Result
loopr logs <run-id> -f          # follow a Firing live (renders cursor stream-json events)
loopr daemon status --json      # daemon health + next firings + active leases
```

## Run and schedule

```bash
loopr run <loop>                # fire once now (runs the full handoff chain)
loopr daemon run                # foreground scheduler (Ctrl-C to stop)
loopr daemon install            # generate a systemd/launchd autostart unit
```

## Structured Result contract

Have the agent write JSON to `$LOOPR_RESULT_PATH` so Loopr can route on it:

```json
{"status": "issues", "summary": "3 models degraded", "artifacts": [{"type": "pr", "url": "..."}]}
```

Only `status` is required. Loopr never runs an LLM to interpret it.

## Handoffs (edit loopr.yaml directly)

```yaml
loops:
  - name: model-monitor
    mission: "Check dashboards"
    workspace: ./infra
    schedule: "0 9 * * 1-5"
    handoffs:
      - when: 'result.status == "issues"'   # predicate over the Result; Loopr evaluates it
        trigger: fixer                        # fire another Loop, passing the Result as context
  - name: fixer
    mission: "Open a PR fixing the reported issues"
    workspace: ./infra
    handoffs:
      - notify: cli                           # hand off to a human; terminates the chain
```

Predicates may use `result.status`, `result.summary`, `result.next`, `result.artifacts`
with `==`, `!=`, `in`, `and`, `or`, `not`. Chains are cycle- and depth-guarded.
