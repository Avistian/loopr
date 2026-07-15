from pathlib import Path

from loopr.db import (
    STATUS_FAILED,
    STATUS_RUNNING,
    STATUS_SUCCESS,
    Store,
    resolve_home,
)


def test_resolve_home_precedence(tmp_path: Path, monkeypatch):
    explicit = tmp_path / "explicit"
    assert resolve_home(explicit) == explicit

    monkeypatch.setenv("LOOPR_HOME", str(tmp_path / "env"))
    assert resolve_home() == tmp_path / "env"

    monkeypatch.delenv("LOOPR_HOME")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "user"))
    assert resolve_home() == tmp_path / "user" / ".loopr"


def test_store_creates_layout(tmp_path: Path):
    with Store(tmp_path) as store:
        assert store.db_path.exists()
        assert store.logs_dir.is_dir()


def test_create_and_complete_run(tmp_path: Path):
    with Store(tmp_path) as store:
        run_id = store.create_run(loop_name="mon", workspace="/ws", agent="cursor")
        record = store.get_run(run_id)
        assert record is not None
        assert record.status == STATUS_RUNNING
        assert record.finished_at is None

        log_path = str(store.log_path_for(run_id))
        store.complete_run(run_id, status=STATUS_SUCCESS, exit_code=0, log_path=log_path)

        done = store.get_run(run_id)
        assert done.status == STATUS_SUCCESS
        assert done.exit_code == 0
        assert done.finished_at is not None
        assert done.log_path == log_path


def test_list_runs_newest_first(tmp_path: Path):
    with Store(tmp_path) as store:
        first = store.create_run(loop_name="a", workspace="/ws", agent="cursor")
        second = store.create_run(loop_name="b", workspace="/ws", agent="cursor")
        store.complete_run(second, status=STATUS_FAILED, exit_code=1, log_path=None)

        runs = store.list_runs()
        assert [r.id for r in runs] == [second, first]
        assert runs[0].status == STATUS_FAILED


def test_get_missing_run_returns_none(tmp_path: Path):
    with Store(tmp_path) as store:
        assert store.get_run(999) is None


def test_state_persists_across_reopen(tmp_path: Path):
    with Store(tmp_path) as store:
        run_id = store.create_run(loop_name="a", workspace="/ws", agent="cursor")
    with Store(tmp_path) as reopened:
        assert reopened.get_run(run_id) is not None
