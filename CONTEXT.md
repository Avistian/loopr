# Loopr

Loopr is a lightweight CLI that schedules recurring agent work. It owns *when* work
runs, *what* gets handed to an agent, and *what came back* — not the agent's internal
reasoning.

## Language

**Loop**:
A reusable unit of agent work — a Mission + Capabilities + a Workspace — that Loopr
fires when triggered. Loopr owns the trigger, the handoff, and the result; never the
agent's internal act-observe iteration. A Loop's schedule is optional: it may be
scheduled, triggered by another Loop's Handoff, or run manually.
_Avoid_: cron job, task, pipeline, job

**Firing**:
A single execution of a Loop: Loopr spawns a fresh headless agent process (e.g.
`cursor-agent`, later `claude`/`codex`) with the Workspace as cwd and the Mission as
input, waits, and captures the Result. One firing = one agent process = one Result.
Loopr holds no live conversation — it fires, waits, collects.
_Avoid_: tick, execution, invocation

**Trigger**:
What causes a Firing. One of: a schedule (recurring or at a time), a Handoff from
another Loop, or a manual run.
_Avoid_: event, cause

**Result**:
The small structured summary a Firing's agent emits via a known channel (e.g. status,
summary, next, artifacts). Loopr parses it to drive Handoffs but never runs an LLM to
interpret it. A Result is what a Handoff carries to the next actor. If absent,
conditional Handoffs fall back to unconditional/manual.
_Avoid_: output, response, outcome

**Log**:
The raw, opaque agent output/transcript of a Firing. Always captured and saved,
independent of whether a structured Result was emitted.
_Avoid_: output, transcript, trace

**Handoff**:
The transfer of a Loop's Result and control to the next actor. Two kinds: to another
Loop (which it triggers, passing the Result as context), or to a human (a Notification
that terminates the chain). A Handoff may be conditional: the source Loop declares a
predicate over the structured Result, which Loopr evaluates (never an LLM). Chains of
Loops emerge from Handoffs; there is no separate pipeline object.
_Avoid_: routing, dispatch, handback

**Notification**:
The delivery of a Result (summary + links to the Log and any Artifacts) to a human via
a channel (CLI, Slack, etc.). A human Handoff is realized as a Notification and
terminates the chain. Loopr never blocks waiting on a human.
_Avoid_: alert, message, report

**Artifact**:
A durable external output a Firing produces — a PR, an issue, a file, a published
report. Artifacts are how a chain reaches a human for out-of-band action: approval
happens by a human acting on an Artifact (e.g. reviewing a PR), not by Loopr pausing.
_Avoid_: output, deliverable, product

**Provisioning**:
The idempotent step run before each Firing that ensures the Loop's declared
Capabilities are present in the Workspace — materializing Skill files, merging MCP
config, and verifying required tools are on PATH (warn/fail if missing; optional
user-supplied install command). A no-op when a Capability is already present, so
Loops sharing a Workspace never conflict.
_Avoid_: setup, install, bootstrap

**Lease**:
The daemon's grant of exclusive access to a Workspace for the duration of a Firing.
At most one Firing holds a Workspace's Lease at a time; other triggers for that
Workspace queue. Firings in different Workspaces run in parallel.
_Avoid_: lock, mutex, semaphore

**Adapter**:
The per-agent plug-in that knows how to invoke one agent CLI (cursor now, claude/codex
later) headlessly — building its command, injecting the Mission and provisioned
Capabilities, and obtaining the structured Result. A Loop names its agent; supporting a
new agent means adding an Adapter.
_Avoid_: driver, backend, provider, plugin

**Mission**:
The loop-specific instruction — what the agent should accomplish on each firing.
Written inline on the Loop, specific to it (e.g. "check the model dashboards and
summarize anything degrading").
_Avoid_: prompt, task, goal

**Capability**:
A typed requirement a Loop declares so its agent can perform the Mission. Three kinds:
a Skill, an MCP server, or a tool/binary. Loopr's provisioning ensures declared
Capabilities are present in the environment before a Handoff.
_Avoid_: dependency, resource, requirement

**Skill**:
A Capability that is a reusable, descriptive know-how bundle — a SKILL.md-style
document describing a workflow the agent should follow. Reusable across Loops and
distinct from the Loop-specific Mission.
_Avoid_: playbook, recipe

**Workspace**:
A working directory — typically a git repo — that one or more Loops operate in.
Handoffs execute with the Workspace as cwd, and provisioning applies to it. Decoupled
from any single Loop, so multiple Loops (e.g. a monitor and a fixer) can share one.
_Avoid_: project, repo, environment, directory
