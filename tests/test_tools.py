from pathlib import Path

import pytest

from chat_agent.knowledge import KnowledgeBase
from chat_agent.tools import CLIENT_TOOL_NAMES, run_client_tool, tool_definitions


def tools(max_web_searches: int = 10) -> list[dict[str, object]]:
    return [dict(tool) for tool in tool_definitions(max_web_searches)]


@pytest.fixture
def kb(tmp_path: Path) -> KnowledgeBase:
    root = tmp_path / "knowledge"
    (root / "notes").mkdir(parents=True)
    (root / "notes" / "todo.md").write_text("- buy milk")
    (root / "readme.txt").write_text("hello")
    (root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00")
    (root / "big.txt").write_text("z" * 200)
    return KnowledgeBase(root, max_read_bytes=100)


def test_ac21_tool_set_is_read_only() -> None:
    names = {tool["name"] for tool in tools()}
    assert names == {"web_search", "list_files", "read_file"}
    assert set(CLIENT_TOOL_NAMES) == {"list_files", "read_file"}


def test_ac12_web_search_is_server_tool_with_max_uses() -> None:
    (web_search,) = [t for t in tools(4) if t["name"] == "web_search"]
    assert web_search == {"type": "web_search_20250305", "name": "web_search", "max_uses": 4}


def test_web_search_max_uses_is_at_least_one() -> None:
    (web_search,) = [t for t in tools(0) if t["name"] == "web_search"]
    assert web_search["max_uses"] == 1


def test_client_tools_stream_input_eagerly() -> None:
    for tool in tools():
        if tool["name"] in CLIENT_TOOL_NAMES:
            assert tool.get("eager_input_streaming") is True


def test_ac21_unknown_tool_is_error(kb: KnowledgeBase) -> None:
    result = run_client_tool("write_file", {"path": "x.txt", "content": "boom"}, kb)
    assert result.is_error
    assert not (kb.root / "x.txt").exists()


def test_ac15_list_result_is_names_only_with_dir_marker(kb: KnowledgeBase) -> None:
    result = run_client_tool("list_files", {"path": ""}, kb)
    assert not result.is_error
    assert result.content.splitlines() == ["big.txt", "image.png", "notes/", "readme.txt"]


def test_ac15_list_path_is_optional(kb: KnowledgeBase) -> None:
    assert run_client_tool("list_files", {}, kb).content.splitlines()[0] == "big.txt"


def test_list_empty_folder_says_so(kb: KnowledgeBase) -> None:
    (kb.root / "empty").mkdir()
    assert run_client_tool("list_files", {"path": "empty"}, kb).content == "(empty folder)"


def test_ac16_read_result_is_file_text(kb: KnowledgeBase) -> None:
    result = run_client_tool("read_file", {"path": "notes/todo.md"}, kb)
    assert not result.is_error
    assert result.content == "- buy milk"


def test_ac17_result_includes_truncation_note(kb: KnowledgeBase) -> None:
    result = run_client_tool("read_file", {"path": "big.txt"}, kb)
    assert not result.is_error
    assert result.content.startswith("z" * 100)
    assert "truncated" in result.content.lower()


def test_ac18_not_text_is_error_result(kb: KnowledgeBase) -> None:
    result = run_client_tool("read_file", {"path": "image.png"}, kb)
    assert result.is_error
    assert "not a readable text file" in result.content


def test_ac19_missing_file_is_error_result(kb: KnowledgeBase) -> None:
    result = run_client_tool("read_file", {"path": "nope.md"}, kb)
    assert result.is_error
    assert "not found" in result.content.lower()


def test_ac20_escape_is_error_result(kb: KnowledgeBase) -> None:
    result = run_client_tool("read_file", {"path": "../../etc/passwd"}, kb)
    assert result.is_error
    assert "access denied" in result.content.lower()


@pytest.mark.parametrize(
    ("name", "tool_input"),
    [
        ("read_file", {}),
        ("read_file", {"path": 42}),
        ("read_file", "notes/todo.md"),
        ("list_files", {"path": None}),
    ],
)
def test_invalid_input_is_error_result(kb: KnowledgeBase, name: str, tool_input: object) -> None:
    result = run_client_tool(name, tool_input, kb)
    assert result.is_error
    assert "invalid input" in result.content.lower()


def test_nul_byte_path_is_tool_error(kb: KnowledgeBase) -> None:
    result = run_client_tool("read_file", {"path": "a\x00b"}, kb)
    assert result.is_error


def test_unreadable_file_is_tool_error(kb: KnowledgeBase) -> None:
    locked = kb.root / "locked.txt"
    locked.write_text("x")
    locked.chmod(0)
    try:
        result = run_client_tool("read_file", {"path": "locked.txt"}, kb)
    finally:
        locked.chmod(0o600)
    assert result.is_error
    assert str(kb.root) not in result.content  # no absolute paths in tool output
