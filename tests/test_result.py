import json
from pathlib import Path

from loopr.result import RESULT_PATH_ENV, parse_result, result_instruction


def write(path: Path, data) -> Path:
    path.write_text(json.dumps(data) if not isinstance(data, str) else data)
    return path


def test_parse_full_result(tmp_path: Path):
    p = write(
        tmp_path / "r.json",
        {
            "status": "issues",
            "summary": "3 models degraded",
            "next": "fixer",
            "artifacts": [{"type": "pr", "url": "http://x/1"}],
        },
    )
    result = parse_result(p)
    assert result is not None
    assert result.status == "issues"
    assert result.summary == "3 models degraded"
    assert result.next == "fixer"
    assert result.artifacts == [{"type": "pr", "url": "http://x/1"}]
    assert result.raw["status"] == "issues"


def test_status_only_is_valid(tmp_path: Path):
    p = write(tmp_path / "r.json", {"status": "ok"})
    result = parse_result(p)
    assert result is not None
    assert result.status == "ok"
    assert result.summary == ""
    assert result.next is None
    assert result.artifacts == []


def test_missing_file_returns_none(tmp_path: Path):
    assert parse_result(tmp_path / "absent.json") is None


def test_malformed_json_returns_none(tmp_path: Path):
    p = write(tmp_path / "r.json", "{not json")
    assert parse_result(p) is None


def test_missing_status_returns_none(tmp_path: Path):
    p = write(tmp_path / "r.json", {"summary": "no status here"})
    assert parse_result(p) is None


def test_non_object_returns_none(tmp_path: Path):
    p = write(tmp_path / "r.json", [1, 2, 3])
    assert parse_result(p) is None


def test_instruction_mentions_path_and_env(tmp_path: Path):
    text = result_instruction(tmp_path / "r.json")
    assert str(tmp_path / "r.json") in text
    assert RESULT_PATH_ENV in text
