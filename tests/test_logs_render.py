import json

from loopr.cli import _render_stream_line


def render(event: dict) -> str | None:
    return _render_stream_line(json.dumps(event))


def test_non_json_passes_through():
    assert _render_stream_line("[loopr] provisioning: ...") == "[loopr] provisioning: ..."


def test_blank_dropped():
    assert _render_stream_line("   ") is None


def test_system_init_shows_model():
    assert render({"type": "system", "subtype": "init", "model": "Opus 4.8"}) == (
        "-- session started (model=Opus 4.8)"
    )


def test_assistant_text_rendered():
    event = {"type": "assistant", "message": {"content": [{"type": "text", "text": "hello"}]}}
    assert render(event) == "[agent] hello"


def test_user_prompt_echo_dropped():
    event = {"type": "user", "message": {"content": [{"type": "text", "text": "the prompt"}]}}
    assert render(event) is None


def test_result_done():
    assert render({"type": "result", "is_error": False, "duration_ms": 4200}) == "-- done in 4.2s"


def test_result_error():
    assert render({"type": "result", "is_error": True}) == "-- ERROR"


def test_mcp_tool_call_rendered():
    event = {
        "type": "tool_call",
        "subtype": "started",
        "tool_call": {
            "mcpToolCall": {
                "args": {
                    "toolName": "search_papers",
                    "serverIdentifier": "arxiv-local",
                }
            }
        },
    }
    assert render(event) == "[tool] mcp arxiv-local/search_papers"


def test_shell_tool_call_rendered():
    event = {
        "type": "tool_call",
        "subtype": "started",
        "tool_call": {"shellToolCall": {"args": {"command": "git add -A && git commit -m x"}}},
    }
    assert render(event) == "[tool] shell: git add -A && git commit -m x"


def test_read_tool_call_rendered():
    event = {
        "type": "tool_call",
        "subtype": "started",
        "tool_call": {"readToolCall": {"args": {"path": "CURRICULUM.md"}}},
    }
    assert render(event) == "[tool] read CURRICULUM.md"


def test_tool_call_completed_is_dropped():
    # only the "started" event renders, so a tool shows once
    event = {
        "type": "tool_call",
        "subtype": "completed",
        "tool_call": {"shellToolCall": {"args": {"command": "ls"}}},
    }
    assert render(event) is None


def test_unknown_tool_kind_falls_back():
    event = {
        "type": "tool_call",
        "subtype": "started",
        "tool_call": {"webSearchToolCall": {"args": {}}},
    }
    assert render(event) == "[tool] webSearch"
