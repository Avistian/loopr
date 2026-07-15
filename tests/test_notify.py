import pytest

from loopr.notify import (
    CliChannel,
    Notification,
    NotifyError,
    deliver,
    get_channel,
    known_channels,
)
from loopr.result import Result


def test_render_includes_result_and_log():
    n = Notification(
        source="monitor",
        channel="cli",
        result=Result(status="issues", summary="3 degraded"),
        run_id=7,
        log_path="/logs/7.log",
        artifacts=[{"type": "pr", "url": "http://x/1"}],
    )
    text = n.render()
    assert "monitor" in text
    assert "issues" in text
    assert "3 degraded" in text
    assert "/logs/7.log" in text
    assert "http://x/1" in text


def test_cli_channel_writes_via_writer():
    captured: list[str] = []
    channel = CliChannel(writer=captured.append)
    channel.deliver(Notification(source="a", channel="cli"))
    assert captured and "handoff to human" in captured[0]


def test_get_channel_cli():
    assert get_channel("cli").name == "cli"


def test_unknown_channel_raises():
    with pytest.raises(NotifyError, match="unknown channel"):
        get_channel("carrier-pigeon")


def test_known_channels_lists_cli():
    assert "cli" in known_channels()


def test_deliver_dispatches(capsys):
    deliver(Notification(source="a", channel="cli", result=Result(status="ok")))
    out = capsys.readouterr().out
    assert "handoff to human" in out
