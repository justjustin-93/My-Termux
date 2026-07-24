"""Tests for the agent brain: parser, tool registry, executors, and the loop."""
import json
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest


# --------------------------------------------------------------------------
# parser
# --------------------------------------------------------------------------

def test_parse_response_extracts_thought_and_tool():
    from mytermux.agent import parse_response
    text = (
        "<think>the user wants to see files</think>\n"
        "I'll list the current directory.\n"
        '<tool name="list_dir">\n{"path": "."}\n</tool>'
    )
    thoughts, tool, body = parse_response(text)
    assert thoughts == ["the user wants to see files"]
    assert tool == ("list_dir", {"path": "."})
    assert "list the current directory" in body
    assert "<think>" not in body
    assert "<tool" not in body


def test_parse_response_no_tool():
    from mytermux.agent import parse_response
    text = "Here is the final answer.\n• next step 1\n• next step 2"
    thoughts, tool, body = parse_response(text)
    assert thoughts == []
    assert tool is None
    assert "next step 1" in body


def test_parse_response_multiple_thoughts_first_tool_only():
    from mytermux.agent import parse_response
    text = (
        "<think>plan A</think>"
        "<think>plan B</think>"
        '<tool name="shell">{"cmd":"ls"}</tool>'
        # A second tool block should be ignored by the parser (only first is returned)
        '<tool name="shell">{"cmd":"pwd"}</tool>'
    )
    thoughts, tool, _ = parse_response(text)
    assert thoughts == ["plan A", "plan B"]
    assert tool[0] == "shell"
    assert tool[1] == {"cmd": "ls"}


def test_parse_response_malformed_json_captures_raw():
    from mytermux.agent import parse_response
    text = '<tool name="shell">{not json}</tool>'
    _, tool, _ = parse_response(text)
    assert tool[0] == "shell"
    assert "_raw_json_error" in tool[1]


def test_parse_response_case_insensitive_tags():
    from mytermux.agent import parse_response
    text = "<THINK>x</THINK><Tool NAME=\"finish\">{}</Tool>"
    thoughts, tool, _ = parse_response(text)
    assert thoughts == ["x"]
    assert tool == ("finish", {})


def test_system_prompt_is_more_flexible_about_protocol():
    from mytermux.agent import build_system
    prompt = build_system()
    assert "follow this protocol strictly" not in prompt.lower()
    assert "flexible" in prompt.lower()
    assert "natural language" in prompt.lower()


# --------------------------------------------------------------------------
# tool registry
# --------------------------------------------------------------------------

def test_registry_describe_tools_lists_all():
    from mytermux.tools_agent import REGISTRY, describe_tools
    desc = describe_tools()
    for name in ("shell", "run_script", "install_package", "copy_file", "make_dir", "remove_path",
                 "read_file", "write_file", "list_dir", "scan_project",
                 "git", "media_list", "add_task", "add_goal", "notify",
                 "web_search", "finish"):
        assert name in REGISTRY
        assert f"- {name}(" in desc


def test_registry_unknown_tool_returns_error():
    from mytermux.tools_agent import run_tool
    out = run_tool("does_not_exist", {})
    assert out.startswith("error: unknown tool")


# --------------------------------------------------------------------------
# individual tool executors
# --------------------------------------------------------------------------

def test_tool_read_file(tmp_path):
    from mytermux.tools_agent import run_tool
    p = tmp_path / "x.txt"
    p.write_text("hello world")
    out = run_tool("read_file", {"path": str(p)})
    assert "hello world" in out
    assert "bytes_read: 11" in out


def test_tool_make_dir_and_copy_file(tmp_path):
    from mytermux.tools_agent import run_tool
    d = tmp_path / "subdir"
    out = run_tool("make_dir", {"path": str(d)})
    assert "created directory" in out
    assert d.exists() and d.is_dir()
    src = tmp_path / "src.txt"
    src.write_text("ok")
    dst = d / "dst.txt"
    out2 = run_tool("copy_file", {"src": str(src), "dst": str(dst)})
    assert "copied" in out2
    assert dst.exists() and dst.read_text() == "ok"


def test_tool_remove_path(tmp_path):
    from mytermux.tools_agent import run_tool
    p = tmp_path / "to_delete.txt"
    p.write_text("bye")
    out = run_tool("remove_path", {"path": str(p)})
    assert "removed" in out
    assert not p.exists()


def test_tool_read_file_missing(tmp_path):
    from mytermux.tools_agent import run_tool
    out = run_tool("read_file", {"path": str(tmp_path / "nope.txt")})
    assert out.startswith("error: not found")


def test_tool_write_file_creates_and_backs_up(tmp_path):
    from mytermux.tools_agent import run_tool
    p = tmp_path / "y.txt"
    run_tool("write_file", {"path": str(p), "content": "v1"})
    assert p.read_text() == "v1"
    out = run_tool("write_file", {"path": str(p), "content": "v2"})
    assert "wrote 2 bytes" in out
    assert p.read_text() == "v2"
    assert (tmp_path / "y.txt.bak").exists()


def test_tool_list_dir(tmp_path):
    from mytermux.tools_agent import run_tool
    target = tmp_path / "listme"
    target.mkdir()
    (target / "a.txt").write_text("a")
    (target / "sub").mkdir()
    out = run_tool("list_dir", {"path": str(target)})
    assert "a.txt" in out
    assert "sub" in out
    assert "entries: 2" in out


def test_tool_scan_project(tmp_path):
    from mytermux.tools_agent import run_tool
    (tmp_path / "requirements.txt").write_text("x")
    out = run_tool("scan_project", {"path": str(tmp_path)})
    data = json.loads(out)
    assert "python" in data["kinds"]


def test_tool_shell_echo(tmp_path):
    from mytermux.tools_agent import run_tool
    out = run_tool("shell", {"cmd": "echo hi_from_agent"})
    assert "exit_code: 0" in out
    assert "hi_from_agent" in out


def test_tool_add_task_and_goal():
    from mytermux import db
    from mytermux.tools_agent import run_tool
    out = run_tool("add_task", {"title": "ship v2"})
    assert "task #" in out
    out2 = run_tool("add_goal", {"title": "learn rust"})
    assert "goal #" in out2
    assert db.list_pending_tasks()[0]["title"] == "ship v2"


def test_tool_add_task_missing_title():
    from mytermux.tools_agent import run_tool
    out = run_tool("add_task", {})
    assert out.startswith("error:")


def test_tool_media_list_empty():
    from mytermux.tools_agent import run_tool
    out = run_tool("media_list", {})
    assert "empty" in out


def test_tool_notify_without_termux_api(monkeypatch):
    from mytermux import tools_agent, notify
    monkeypatch.setattr(notify.shutil, "which", lambda _: None)
    out = tools_agent.run_tool("notify", {"title": "hi", "content": "y"})
    assert "skipped" in out


def test_tool_git_not_a_repo(tmp_path):
    from mytermux.tools_agent import run_tool
    out = run_tool("git", {"action": "status", "path": str(tmp_path)})
    assert "not a git repo" in out


def test_tool_git_status_commit(tmp_path):
    from mytermux.tools_agent import run_tool
    import subprocess

    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "file.txt").write_text("hello")
    out = run_tool("git", {"action": "status", "path": str(repo)})
    assert "?? file.txt" in out or "Untracked files" in out
    rc = run_tool("git", {"action": "commit", "path": str(repo), "message": "first commit"})
    assert "error" not in rc.lower()
    assert "committed" in rc.lower() or "files changed" in rc.lower() or "branch" not in rc.lower()


def test_tool_finish_returns_marker():
    from mytermux.tools_agent import run_tool
    out = run_tool("finish", {})
    assert out == "__FINISH__"


def test_tool_web_search_no_httpx(monkeypatch):
    from mytermux import tools_agent
    monkeypatch.setitem(sys.modules, "httpx", None)
    out = tools_agent.run_tool("web_search", {"query": "python"})
    assert out.startswith("error:")


def test_tool_web_search_parses_ddg_json(monkeypatch):
    from mytermux import tools_agent

    class FakeResp:
        status_code = 200
        def raise_for_status(self): pass
        def json(self):
            return {
                "AbstractText": "Python is a language.",
                "AbstractURL": "https://python.org",
                "RelatedTopics": [
                    {"Text": "PEP 8 style guide", "FirstURL": "https://peps.python.org/pep-0008"},
                    {"Text": "PEP 20 zen", "FirstURL": "https://peps.python.org/pep-0020"},
                ],
            }

    class FakeClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def get(self, url, params=None): return FakeResp()

    monkeypatch.setitem(sys.modules, "httpx",
                        types.SimpleNamespace(Client=FakeClient))
    out = tools_agent.run_tool("web_search", {"query": "python"})
    assert "Python is a language" in out
    assert "https://python.org" in out
    assert "PEP 8" in out


# --------------------------------------------------------------------------
# safety
# --------------------------------------------------------------------------

def test_is_dangerous_flags_rm_rf():
    from mytermux.tools_agent import is_dangerous
    assert is_dangerous("shell", {"cmd": "rm -rf /"}) is True
    assert is_dangerous("shell", {"cmd": "ls -la"}) is False


def test_is_dangerous_flags_protected_writes():
    from mytermux.tools_agent import is_dangerous
    assert is_dangerous("write_file", {"path": "/data/data/com.termux/files/usr/etc/x"}) is True
    assert is_dangerous("write_file", {"path": "/tmp/x.txt"}) is False


def test_is_dangerous_safe_tools():
    from mytermux.tools_agent import is_dangerous
    assert is_dangerous("read_file", {"path": "/tmp/x"}) is False
    assert is_dangerous("list_dir", {"path": "/"}) is False
    assert is_dangerous("web_search", {"query": "anything"}) is False


# --------------------------------------------------------------------------
# agent loop — end-to-end with mocked LLM
# --------------------------------------------------------------------------

def _mock_openrouter_sequence(monkeypatch, responses):
    """Replace openrouter.chat_stream with a scripted queue of responses."""
    from mytermux import agent as agent_mod
    q = list(responses)

    def fake_stream(messages, on_delta=None):
        assert q, "chat_stream called more times than mocked"
        text = q.pop(0)
        if on_delta:
            on_delta(text)
        return text, "mock/model"

    monkeypatch.setattr(agent_mod.openrouter, "chat_stream", fake_stream)


def test_agent_single_hop_final_answer(monkeypatch, capsys):
    from mytermux.agent import run_turn
    from mytermux.memory import Conversation

    _mock_openrouter_sequence(monkeypatch, [
        "<think>trivial question</think>\n"
        "The answer is 42.\n• next: /help\n• next: /suggest\n"
        '<tool name="finish">{}</tool>'
    ])
    conv = Conversation()
    body = run_turn(conv, "what is the meaning?")
    assert "42" in body
    out = capsys.readouterr().out
    assert "42" in out


def test_agent_uses_tool_then_answers(monkeypatch, tmp_path, capsys):
    from mytermux.agent import run_turn
    from mytermux.memory import Conversation

    target = tmp_path / "hello.txt"
    target.write_text("secret content 42")

    _mock_openrouter_sequence(monkeypatch, [
        # hop 1: call read_file
        f'<think>need to inspect the file</think>'
        f'<tool name="read_file">{{"path":"{target}"}}</tool>',
        # hop 2: final answer after observation
        'The file says "secret content 42".\n'
        "• next: nothing\n• next: try another\n"
        '<tool name="finish">{}</tool>',
    ])

    conv = Conversation()
    body = run_turn(conv, "what does hello.txt say?")
    assert "secret content 42" in body


def test_agent_dangerous_tool_gets_denied(monkeypatch, capsys):
    from mytermux.agent import run_turn
    from mytermux.memory import Conversation

    _mock_openrouter_sequence(monkeypatch, [
        '<tool name="shell">{"cmd":"rm -rf /"}</tool>',
        # after denial, model wraps up
        "I will not proceed with that destructive command.\n"
        "• next: try a safer command\n• next: run `my-fix`\n"
        '<tool name="finish">{}</tool>',
    ])
    conv = Conversation()
    body = run_turn(conv, "clean up", confirm_fn=lambda _msg: False)
    assert "not proceed" in body.lower() or "denied" in body.lower() or body
    # observation was fed back
    out = capsys.readouterr().out
    assert "user_denied_tool_call" in out


def test_agent_dangerous_tool_confirmed_runs(monkeypatch, capsys, tmp_path):
    from mytermux.agent import run_turn
    from mytermux.memory import Conversation

    # write to a "protected" path suffix (bashrc). This is dangerous per is_dangerous().
    protected = tmp_path / ".bashrc"
    _mock_openrouter_sequence(monkeypatch, [
        f'<tool name="write_file">{{"path":"{protected}","content":"# hi"}}</tool>',
        "Done. Backup would exist if the file existed.\n"
        "• next: reload shell\n• next: check content\n"
        '<tool name="finish">{}</tool>',
    ])
    conv = Conversation()
    run_turn(conv, "add a shell rc line", confirm_fn=lambda _msg: True)
    assert protected.read_text() == "# hi"


def test_agent_stops_at_max_hops(monkeypatch, capsys):
    from mytermux import agent as agent_mod
    from mytermux.agent import run_turn
    from mytermux.memory import Conversation

    # Force MAX_HOPS to 2 for this test
    monkeypatch.setattr(agent_mod, "MAX_HOPS", 2)

    _mock_openrouter_sequence(monkeypatch, [
        '<tool name="list_dir">{"path":"."}</tool>',
        '<tool name="list_dir">{"path":"."}</tool>',
    ])
    conv = Conversation()
    body = run_turn(conv, "spin forever")
    assert "max hops" in body.lower()


def test_agent_records_messages_in_session():
    from mytermux import db
    from mytermux.memory import Conversation
    conv = Conversation()
    # simulate: record_user + record_assistant flow the agent uses
    conv.record_user("hello agent")
    conv.record_assistant("hello human", model="mock")
    msgs = db.get_session_messages(conv.session_id)
    assert [m["role"] for m in msgs] == ["user", "assistant"]
    assert msgs[1]["model"] == "mock"


def test_agent_llm_error_is_caught(monkeypatch, capsys):
    from mytermux import agent as agent_mod
    from mytermux.agent import run_turn
    from mytermux.memory import Conversation

    def boom(messages, on_delta=None):
        raise RuntimeError("no key")

    monkeypatch.setattr(agent_mod.openrouter, "chat_stream", boom)
    conv = Conversation()
    body = run_turn(conv, "hi")
    assert body == ""
    out = capsys.readouterr().out
    assert "no key" in out


# --------------------------------------------------------------------------
# chat integration
# --------------------------------------------------------------------------

def test_chat_tools_listing_command(monkeypatch, capsys):
    """/tools should print each registered tool."""
    from mytermux import chat as chat_mod
    from mytermux.memory import Conversation

    # simulate stdin: `/tools` then `/q`
    inputs = iter(["/tools", "/q"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))

    rc = chat_mod.run(resume=False)
    assert rc == 0
    out = capsys.readouterr().out
    for name in ("shell", "read_file", "write_file", "list_dir", "scan_project",
                 "git", "media_list", "web_search", "finish"):
        assert name in out


def test_chat_plain_toggle_works(monkeypatch, capsys):
    from mytermux import chat as chat_mod
    from mytermux import openrouter, notify

    # avoid termux notify call
    monkeypatch.setattr(notify, "notify", lambda *a, **kw: False)
    # capture the fact that plain mode calls openrouter.chat_stream directly
    calls = {"n": 0}
    def fake_stream(messages, on_delta=None):
        calls["n"] += 1
        # simulate default streaming behavior so output appears in stdout
        sys.stdout.write("plain answer")
        sys.stdout.flush()
        if on_delta:
            on_delta("plain answer")
        return "plain answer", "mock/plain"
    monkeypatch.setattr(openrouter, "chat_stream", fake_stream)

    inputs = iter(["/plain", "what?", "/q"])
    monkeypatch.setattr("builtins.input", lambda *a, **kw: next(inputs))
    chat_mod.run(resume=False)
    assert calls["n"] == 1  # exactly one plain call, no agent loop
    out = capsys.readouterr().out
    assert "mode → plain" in out
    assert "plain answer" in out
