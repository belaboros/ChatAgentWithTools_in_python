"""Tool definitions and execution of the client-side (local) tools."""

from dataclasses import dataclass

from anthropic.types.beta import BetaToolParam, BetaToolUnionParam, BetaWebSearchTool20250305Param

from chat_agent.knowledge import KnowledgeBase, KnowledgeError

LIST_FILES = "list_files"
READ_FILE = "read_file"
WEB_SEARCH = "web_search"
CLIENT_TOOL_NAMES = (LIST_FILES, READ_FILE)

_LIST_FILES_TOOL: BetaToolParam = {
    "name": LIST_FILES,
    "description": (
        "List the files and subfolders inside a folder of the user's knowledge folder. "
        "Returns one name per line, as paths relative to the knowledge folder; "
        "folders end with '/'. "
        "Use this to discover which documents exist before reading them."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Folder relative to the knowledge folder; '' for the top level.",
            }
        },
        "additionalProperties": False,
    },
    "eager_input_streaming": True,
}

_READ_FILE_TOOL: BetaToolParam = {
    "name": READ_FILE,
    "description": (
        "Read a UTF-8 text file (e.g. .txt, .md, .py, .csv, .json) "
        "from the user's knowledge folder. "
        "Files larger than 100 KB are truncated, and the result says so. "
        "Binary files (images, PDFs, archives) cannot be read."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "File path relative to the knowledge folder, e.g. 'notes/todo.md'.",
            }
        },
        "required": ["path"],
        "additionalProperties": False,
    },
    "eager_input_streaming": True,
}


def tool_definitions(max_web_searches: int) -> list[BetaToolUnionParam]:
    """All tools offered to the model. File access is read-only by construction (AC-21).

    Web search uses the basic `web_search_20250305` version: its answers carry structured
    citations (AC-13). The `_20260209` "dynamic filtering" version searches from a code
    sandbox and cites only as links in the text.
    """
    web_search: BetaWebSearchTool20250305Param = {
        "type": "web_search_20250305",
        "name": WEB_SEARCH,
        "max_uses": max(1, max_web_searches),
    }
    return [web_search, _LIST_FILES_TOOL, _READ_FILE_TOOL]


@dataclass(frozen=True)
class ToolOutput:
    content: str
    is_error: bool = False


def _path_arg(tool_input: object, *, required: bool) -> str | None:
    """Validate tool input: eager input streaming means the API no longer validates it."""
    if not isinstance(tool_input, dict):
        return None
    if "path" not in tool_input:
        return None if required else ""
    path = tool_input["path"]
    return path if isinstance(path, str) else None


def run_client_tool(name: str, tool_input: object, kb: KnowledgeBase) -> ToolOutput:
    if name not in CLIENT_TOOL_NAMES:
        return ToolOutput(f"Unknown tool '{name}'.", is_error=True)
    path = _path_arg(tool_input, required=name == READ_FILE)
    if path is None:
        return ToolOutput(f"Invalid input for {name}: expected a string 'path'.", is_error=True)
    try:
        if name == LIST_FILES:
            entries = kb.list_dir(path)
            lines = [entry.path + ("/" if entry.is_dir else "") for entry in entries]
            return ToolOutput("\n".join(lines) or "(empty folder)")
        content = kb.read_text(path)
    except KnowledgeError as error:
        return ToolOutput(str(error), is_error=True)
    if content.truncated:
        limit_kb = kb.max_read_bytes // 1024
        note = f"[Truncated: this file is larger than {limit_kb} KB; only the beginning is shown.]"
        return ToolOutput(f"{content.text}\n\n{note}")
    return ToolOutput(content.text)
