import sys
from pathlib import Path

from loopr.adapters.base import AgentInvocation
from loopr.config import Loop, SkillCapability, ToolCapability
from loopr.db import STATUS_ERROR, STATUS_FAILED, STATUS_SUCCESS, Store
from loopr.firing import run_firing


class FakeAdapter:
    """Adapter that runs a fixed argv, for deterministic firing tests."""

    name = "fake"

    def __init__(self, argv: list[str]):
        self._argv = argv

    def build_invocation(
        self, *, mission: str, workspace: Path, result_path: Path
    ) -> AgentInvocation:
        return AgentInvocation(argv=self._argv, cwd=Path(workspace))


class ResultAdapter:
    """Adapter whose agent writes a fixed structured Result to result_path."""

    name = "res"

    def __init__(self, payload: dict, exit_code: int = 0):
        self._payload = payload
        self._exit = exit_code

    def build_invocation(
        self, *, mission: str, workspace: Path, result_path: Path
    ) -> AgentInvocation:
        code = (
            "import json,sys;"
            f"open({str(result_path)!r},'w').write(json.dumps({self._payload!r}));"
            f"sys.exit({self._exit})"
        )
        return AgentInvocation(argv=[sys.executable, "-c", code], cwd=Path(workspace))


def make_loop(tmp_path: Path, *, mission: str = "hello") -> Loop:
    ws = tmp_path / "ws"
    ws.mkdir(exist_ok=True)
    return Loop(name="t", mission=mission, workspace=ws, agent="fake")


def py(code: str) -> list[str]:
    return [sys.executable, "-c", code]


def test_successful_firing(tmp_path: Path):
    loop = make_loop(tmp_path)
    adapter = FakeAdapter(py("import sys; sys.stdout.write('AGENT-RAN'); sys.exit(0)"))
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_SUCCESS
        assert record.exit_code == 0
        assert record.finished_at is not None
        assert Path(record.log_path).read_text().strip() == "AGENT-RAN"


def test_failed_firing_records_exit_code(tmp_path: Path):
    loop = make_loop(tmp_path)
    adapter = FakeAdapter(py("import sys; sys.exit(3)"))
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_FAILED
        assert record.exit_code == 3


def test_stderr_is_captured(tmp_path: Path):
    loop = make_loop(tmp_path)
    adapter = FakeAdapter(py("import sys; sys.stderr.write('BOOM'); sys.exit(1)"))
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert "BOOM" in Path(record.log_path).read_text()


def test_missing_binary_is_error(tmp_path: Path):
    loop = make_loop(tmp_path)
    adapter = FakeAdapter(["/definitely/not/a/real/binary"])
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_ERROR
        assert record.exit_code is None
        assert "not found" in Path(record.log_path).read_text()


def test_structured_result_is_captured(tmp_path: Path):
    loop = make_loop(tmp_path)
    adapter = ResultAdapter({"status": "issues", "summary": "3 degraded"})
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_SUCCESS
        assert record.result_status == "issues"
        assert record.result_summary == "3 degraded"


def test_absent_result_is_graceful(tmp_path: Path):
    loop = make_loop(tmp_path)
    adapter = FakeAdapter(py("import sys; sys.exit(0)"))  # writes no result.json
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_SUCCESS
        assert record.result_status is None


def test_provisioning_failure_blocks_firing(tmp_path: Path):
    loop = Loop(
        name="t",
        mission="m",
        workspace=(tmp_path / "ws"),
        agent="fake",
        capabilities=(ToolCapability(name="definitely-not-a-real-binary-xyz"),),
    )
    (tmp_path / "ws").mkdir()
    adapter = FakeAdapter(py("import sys; sys.exit(0)"))
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_ERROR
        log = Path(record.log_path).read_text()
        assert "provisioning failed" in log


def test_provisioning_preamble_in_log_on_success(tmp_path: Path):
    ws = tmp_path / "ws"
    ws.mkdir()
    src = tmp_path / "s.md"
    src.write_text("# skill")
    loop = Loop(
        name="t",
        mission="m",
        workspace=ws,
        agent="fake",
        capabilities=(SkillCapability(name="triage", path=src),),
    )
    adapter = FakeAdapter(py("import sys; sys.stdout.write('RAN'); sys.exit(0)"))
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_SUCCESS
        log = Path(record.log_path).read_text()
        assert "provisioning" in log
        assert "RAN" in log


def test_missing_workspace_is_error(tmp_path: Path):
    loop = Loop(
        name="t",
        mission="m",
        workspace=tmp_path / "does-not-exist",
        agent="fake",
    )
    adapter = FakeAdapter(py("pass"))
    with Store(tmp_path / "home") as store:
        record = run_firing(loop, store, adapter)
        assert record.status == STATUS_ERROR
        assert "workspace does not exist" in Path(record.log_path).read_text()
