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
from .predicate import evaluate_predicate
from .result import Result, parse_result


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
    on_notify: Callable[[Loop, Result | None, "HandoffEvent"], None] | None = None,
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
        runner=runner,
        on_notify=on_notify,
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
    runner: Runner = run_firing,
    on_notify: Callable[[Loop, Result | None, HandoffEvent], None] | None = None,
) -> list[HandoffEvent]:
    events: list[HandoffEvent] = []
    for rule in source.handoffs:
        if not _matches(rule.when, result):
            events.append(HandoffEvent(source.name, "skipped", rule.trigger or rule.notify))
            continue

        if rule.notify is not None and on_notify is not None:
            event = HandoffEvent(source.name, "notify", rule.notify)
            on_notify(source, result, event)
            events.append(event)

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
            on_notify=on_notify,
        )
    return events


def _matches(when: str | None, result: Result | None) -> bool:
    if when is None:
        return True  # unconditional
    if result is None:
        return False  # cannot evaluate a predicate without a Result
    return evaluate_predicate(when, result)
