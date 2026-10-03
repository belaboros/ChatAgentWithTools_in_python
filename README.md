# ChatAgentWithTools_in_python

A local web chat assistant powered by Claude (Sonnet 5.5). It can **search the web** (with cited sources) and
**read text files in `./knowledge`**, and it can't read anything outside that folder. It only listens on
`127.0.0.1`.

Built with spec-driven development: see [CLAUDE.md](CLAUDE.md) and
[specs/001-web-chat-with-search-and-files/](specs/001-web-chat-with-search-and-files/).

## Setup

Requires [uv](https://docs.astral.sh/uv/) (it installs Python 3.14 if needed).

```sh
uv sync
cp .env.example .env   # then put your key in .env: ANTHROPIC_API_KEY=sk-ant-...
```

## Run

```sh
uv run chat-agent
```

Open http://127.0.0.1:8000. Put the documents you want the assistant to be able to read into `knowledge/`
(created on first start, git-ignored). Text files only (`.md`, `.txt`, `.py`, `.csv`, `.json`, …); files over 100 KB
are read only partially.

Each message can use at most 10 tool calls (web searches plus file reads), which keeps costs bounded.

## Develop

```sh
uv run pytest                     # unit + API tests (no network, no API cost)
uv run pytest -m live             # end-to-end against the real Claude API (needs a key; costs a little)
uv run ruff check --fix . && uv run ruff format .
uv run pyright
```

The browser UI is checked manually with [tests/manual/ui_checklist.md](tests/manual/ui_checklist.md).
