from pathlib import Path

from loopr.config import Config, HandoffRule, Loop
from loopr.db import Store
from loopr.handoff import ChainContext, fire_with_handoffs, process_handoffs
from loopr.result import Result


def loop(name, tmp_path, *, handoffs=(), mission="m"):
    ws = tmp_path / name
    ws.mkdir(exist_ok=True)
    return Loop(name=name, mission=mission, workspace=ws, agent="fake", handoffs=tuple(handoffs))


def config_of(tmp_path, *loops, max_depth=10):
    return Config(
        loops={l.name: l for l in loops},
        source=tmp_path / "loopr.yaml",
        max_chain_depth=max_depth,
    )


class RecordingRunner:
    """Fake runner: records fired loops and returns synthetic results per loop."""

    def __init__(self, store: Store, results: dict[str, Result | None]):
        self.store = store
        self.results = results
        self.fired: list[str] = []
        self.contexts: dict[str, Result | None] = {}

    def __call__(self, loop, store, *, context=None, context_source=None):
        self.fired.append(loop.name)
        self.contexts[loop.name] = context
        run_id = store.create_run(loop_name=loop.name, workspace=str(loop.workspace), agent=loop.agent)
        result = self.results.get(loop.name)
        # persist the synthetic result where fire_with_handoffs will read it
        result_path = store.result_path_for(run_id)
        if result is not None:
            import json

            result_path.write_text(json.dumps(result.raw or {"status": result.status, "summary": result.summary}))
        store.complete_run(run_id, status="success", exit_code=0, log_path=None, result=result)
        return store.get_run(run_id)


def test_conditional_trigger_fires_on_match(tmp_path: Path):
    with Store(tmp_path / "home") as store:
        fixer = loop("fixer", tmp_path)
        monitor = loop(
            "monitor",
            tmp_path,
            handoffs=[HandoffRule(trigger="fixer", when='result.status == "issues"')],
        )
        cfg = config_of(tmp_path, monitor, fixer)
        runner = RecordingRunner(store, {"monitor": Result(status="issues", summary="bad")})
        fire_with_handoffs(monitor, cfg, store, runner=runner)
        assert runner.fired == ["monitor", "fixer"]


def test_conditional_trigger_skips_on_no_match(tmp_path: Path):
    with Store(tmp_path / "home") as store:
        fixer = loop("fixer", tmp_path)
        monitor = loop(
            "monitor",
            tmp_path,
            handoffs=[HandoffRule(trigger="fixer", when='result.status == "issues"')],
        )
        cfg = config_of(tmp_path, monitor, fixer)
        runner = RecordingRunner(store, {"monitor": Result(status="ok", summary="fine")})
        fire_with_handoffs(monitor, cfg, store, runner=runner)
        assert runner.fired == ["monitor"]


def test_unconditional_handoff_always_fires(tmp_path: Path):
    with Store(tmp_path / "home") as store:
        b = loop("b", tmp_path)
        a = loop("a", tmp_path, handoffs=[HandoffRule(trigger="b")])
        cfg = config_of(tmp_path, a, b)
        runner = RecordingRunner(store, {"a": None})  # no result at all
        fire_with_handoffs(a, cfg, store, runner=runner)
        assert runner.fired == ["a", "b"]


def test_context_passed_downstream(tmp_path: Path):
    with Store(tmp_path / "home") as store:
        fixer = loop("fixer", tmp_path)
        monitor = loop("monitor", tmp_path, handoffs=[HandoffRule(trigger="fixer")])
        cfg = config_of(tmp_path, monitor, fixer)
        upstream = Result(status="issues", summary="3 degraded")
        runner = RecordingRunner(store, {"monitor": upstream})
        fire_with_handoffs(monitor, cfg, store, runner=runner)
        assert runner.contexts["fixer"].summary == "3 degraded"


def test_cycle_is_stopped(tmp_path: Path):
    with Store(tmp_path / "home") as store:
        a = loop("a", tmp_path, handoffs=[HandoffRule(trigger="b")])
        b = loop("b", tmp_path, handoffs=[HandoffRule(trigger="a")])  # cycle
        cfg = config_of(tmp_path, a, b)
        runner = RecordingRunner(store, {"a": Result(status="x"), "b": Result(status="y")})
        fire_with_handoffs(a, cfg, store, runner=runner)
        # a -> b -> (a already visited, stop)
        assert runner.fired == ["a", "b"]


def test_depth_limit_stops_chain(tmp_path: Path):
    with Store(tmp_path / "home") as store:
        a = loop("a", tmp_path, handoffs=[HandoffRule(trigger="b")])
        b = loop("b", tmp_path, handoffs=[HandoffRule(trigger="c")])
        c = loop("c", tmp_path)
        cfg = config_of(tmp_path, a, b, c, max_depth=1)
        runner = RecordingRunner(
            store, {"a": Result(status="x"), "b": Result(status="y"), "c": Result(status="z")}
        )
        fire_with_handoffs(a, cfg, store, runner=runner)
        # depth 1 allows a -> b, but b -> c would be depth 2 > max_depth 1
        assert runner.fired == ["a", "b"]


def test_process_handoffs_reports_events(tmp_path: Path):
    with Store(tmp_path / "home") as store:
        fixer = loop("fixer", tmp_path)
        monitor = loop(
            "monitor",
            tmp_path,
            handoffs=[HandoffRule(trigger="fixer", when='result.status == "issues"')],
        )
        cfg = config_of(tmp_path, monitor, fixer)
        runner = RecordingRunner(store, {})
        events = process_handoffs(
            monitor,
            Result(status="issues"),
            cfg,
            store,
            ChainContext(depth=0, visited=frozenset({"monitor"}), max_depth=10),
            runner=runner,
        )
        kinds = [e.kind for e in events]
        assert "trigger" in kinds
