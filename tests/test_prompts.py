import importlib

from chat_agent import prompts


def test_system_prompt_covers_required_behaviors() -> None:
    prompt = prompts.SYSTEM_PROMPT.lower()
    for phrase in [
        "knowledge folder",  # files live in ./knowledge (AC-15/16)
        "list_files",
        "read_file",
        "web search",  # current information (AC-12)
        "sources",  # cite sources (AC-13)
        "search fails",  # say so, don't invent results (AC-14)
        "truncated",  # mention truncation (AC-17)
        "markdown",  # replies rendered as Markdown (AC-25)
        "tool-call limit",  # 10 tool calls per message (AC-11)
    ]:
        assert phrase in prompt, phrase


def test_system_prompt_is_stable() -> None:
    # Byte-stable across imports so the prompt cache keeps hitting (no timestamps etc.).
    first = prompts.SYSTEM_PROMPT
    assert first == importlib.reload(prompts).SYSTEM_PROMPT
