"""The Handoff engine: evaluate a Loop's rules and trigger downstream Loops.

Chains emerge from Handoffs (see docs/adr/0006) — there is no pipeline object. A
config-declared predicate over the structured Result decides whether each Handoff
fires; Loopr evaluates it (never an LLM). Cycles and runaway depth are guarded.

Human Handoffs (``notify``) are handled in issue 05; this module wires loop→loop
(``trigger``) Handoffs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .config import Config, Loop
from .db import RunRecord, Store
from .firing import run_firing
from .notify import Notification
from .notify import deliver as deliver_notification
from .predicate import evaluate_predicate
from .result import Result, parse_result

Notifier = Callable[[Notification], None]


@dataclass(frozen=True)
class ChainContext:
    depth: int = 0
    visited: frozenset[str] = field(default_factory=frozenset)
    max_depth: int = 10


# A runner fires one Loop and returns its RunRecord. Injectable for testing.
Runner = Callable[..., RunRecord]


def fire_with_handoffs(
    loop: Loop,
    config: Config,
    store: Store,
    *,
    chain: ChainContext | None = None,
    context: Result | None = None,
    context_source: str | None = None,
    runner: Runner = run_firing,
    notifier: Notifier = deliver_notification,
) -> RunRecord:
    """Fire ``loop`` then process its Handoffs recursively."""
    if chain is None:
        chain = ChainContext(
            depth=0, visited=frozenset({loop.name}), max_depth=config.max_chain_depth
        )

    record = runner(loop, store, context=context, context_source=context_source)
    result = parse_result(store.result_path_for(record.id))

    process_handoffs(
        loop,
        result,
        config,
        store,
        chain,
        source_record=record,
        runner=runner,
        notifier=notifier,
    )
    return record


@dataclass(frozen=True)
class HandoffEvent:
    """A record of a Handoff decision, for observability/tests."""

    source: str
    kind: str  # "trigger" | "notify" | "cycle-stop" | "depth-stop" | "skipped"
    target: str | None
    detail: str = ""


def process_handoffs(
    source: Loop,
    result: Result | None,
    config: Config,
    store: Store,
    chain: ChainContext,
    *,
    source_record: RunRecord | None = None,
    runner: Runner = run_firing,
    notifier: Notifier | None = deliver_notification,
) -> list[HandoffEvent]:
    events: list[HandoffEvent] = []
    for rule in source.handoffs:
        if not _matches(rule.when, result):
            events.append(HandoffEvent(source.name, "skipped", rule.trigger or rule.notify))
            continue

        if rule.notify is not None and notifier is not None:
            notifier(
                Notification(
                    source=source.name,
                    channel=rule.notify,
                    result=result,
                    run_id=source_record.id if source_record else None,
                    log_path=source_record.log_path if source_record else None,
                    artifacts=list(result.artifacts) if result else [],
                )
            )
            events.append(HandoffEvent(source.name, "notify", rule.notify))

        if rule.trigger is None:
            continue

        target = config.get_loop(rule.trigger)
        if target.name in chain.visited:
            events.append(
                HandoffEvent(source.name, "cycle-stop", target.name, "already in chain")
            )
            continue
        if chain.depth + 1 > chain.max_depth:
            events.append(
                HandoffEvent(
                    source.name, "depth-stop", target.name, f"max depth {chain.max_depth}"
                )
            )
            continue

        events.append(HandoffEvent(source.name, "trigger", target.name))
        child = ChainContext(
            depth=chain.depth + 1,
            visited=chain.visited | {target.name},
            max_depth=chain.max_depth,
        )
        fire_with_handoffs(
            target,
            config,
            store,
            chain=child,
            context=result,
            context_source=source.name,
            runner=runner,
            notifier=notifier or deliver_notification,
        )
    return events


def _matches(when: str | None, result: Result | None) -> bool:
    if when is None:
        return True  # unconditional
    if result is None:
        return False  # cannot evaluate a predicate without a Result
    return evaluate_predicate(when, result)
