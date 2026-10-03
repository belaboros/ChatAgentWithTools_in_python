# 001 — Web chat with web search and local files: Technical plan

- **Spec:** [spec.md](spec.md)
- **Status:** Approved

## Approach

A single local Python process serves both a small static web page and a JSON/streaming HTTP API. The browser sends
each user message to the server; the server runs an **agent loop** against the Claude API and streams events
(text deltas, tool activity, sources, errors) back to the browser, which renders them.

```
Browser (index.html + app.js)                    Python server (FastAPI on 127.0.0.1)
 ─ marked + DOMPurify render Markdown             ─ ConversationStore (in memory, per conversation id)
 ─ POST /api/chat  ───────────────────────────▶  ─ Agent loop ──▶ Claude API (Sonnet 5.5, streaming)
 ◀── text/event-stream: text | activity |              │            ├─ server tool: web_search (Anthropic-hosted)
      sources | error | done                           │            └─ client tools: list_files, read_file
                                                       └─▶ KnowledgeBase (sandboxed ./knowledge, read-only)
```

Key decisions:

1. **Claude API with a manual agent loop** (`AsyncAnthropic`, `client.beta.messages.stream`). Web search uses
   Anthropic's **server-side** `web_search_20260209` tool, which runs the searches and returns citations, so we don't
   need a separate search provider or API key. `list_files` / `read_file` are **client tools** that we run locally.
2. **Conversation state lives on the server, in memory**, keyed by a random conversation id that the page creates on
   every load (so a reload starts fresh, AC-6) and on "New chat" (AC-5). The server stores the assistant's content
   blocks exactly as returned (thinking blocks, tool calls, search results) and only ever appends to them. That is
   required for multi-turn tool use and for Sonnet 5.5's preserved-thinking check, and it is why history is not
   round-tripped through the browser.
3. **One tool budget per user message (AC-11).** Every `tool_use` (client) and `server_tool_use` (web search) block
   counts against a budget of 10. Before each API request, `web_search.max_uses` is set to the remaining budget, so the
   server-side search loop can't overshoot either. When the budget runs out, the next request is sent with
   `tool_choice: {"type": "none"}` and a short note that the limit was reached, so the model must answer with what it
   has. Any `tool_use` blocks beyond the budget get an `is_error` result ("tool-call limit reached"), because every
   tool call must receive a result.
4. **A thin LLM adapter as the test seam.** `llm.py` is the only module that talks to the Anthropic SDK. It turns SDK
   stream events into a few domain events and returns the final message. The agent loop depends on a small
   `LLMClient` protocol, so tests drive it with a scripted fake: no network, deterministic, and free.
5. **Sandboxing by path resolution (AC-20).** Every model-supplied path is rejected if it is absolute or starts with
   `~`. Otherwise it is joined to the knowledge root and fully resolved with `Path.resolve()`, which follows symlinks.
   The result must satisfy `is_relative_to(root.resolve())`. The check runs on the *resolved* path, so `..`, absolute
   paths, and symlinks pointing outside are all caught by the same rule. Directory listings leave out entries whose
   resolved target escapes the root, so no outside names are revealed.
6. **Markdown is rendered in the browser** with `marked` and sanitized with `DOMPurify` before insertion, so no HTML
   or script in a reply can run (AC-25). Both libraries are vendored into `static/vendor/`, so the app works without a
   CDN and with no build step.

### Alternatives considered

- **Gradio / Streamlit chat UI** instead of FastAPI plus a hand-written page. They are faster to start, but give
  little control over the streaming protocol, tool-activity lines, input locking, and sanitization (AC-7, AC-9,
  AC-25). They are also harder to test at the HTTP level and pull in a large dependency tree. Rejected.
- **SDK Tool Runner** (`client.beta.messages.tool_runner`) instead of a manual loop. Its Python version does not
  resume `pause_turn` (the server-side web search can pause), and it doesn't let us share one tool budget across
  server and client tools or switch to `tool_choice: none` at the limit. A manual loop of about 100 lines is simpler
  than working around both.
- **Browser holds the conversation history** (stateless server). Rejected: the history contains opaque thinking and
  search-result blocks that must be echoed back unchanged, and the browser could tamper with them.
- **A separate search API (Tavily, Brave, …) as a client tool.** Rejected: it needs another key and account, and we
  would have to build citations ourselves.
- **WebSockets** instead of a streamed HTTP response. Rejected: one request and one streamed reply is all we need,
  and a plain `fetch` stream is simpler to build and test.

## Components

| Module / file | Responsibility | New or changed |
|---|---|---|
| `pyproject.toml`, `uv.lock` | Project metadata, deps, `chat-agent` script entry point, ruff/pyright/pytest config | New |
| `src/chat_agent/config.py` | Constants: `HOST="127.0.0.1"`, `PORT=8000`, `KNOWLEDGE_DIR` (project-root `knowledge/`), `MODEL="claude-sonnet-5-5"`, `MAX_TOOL_CALLS=10`, `MAX_READ_BYTES=102_400`; API-key check | New |
| `src/chat_agent/knowledge.py` | `KnowledgeBase(root)`: `list_dir(path)`, `read_text(path)`, the path sandbox, text/binary detection, truncation. Pure filesystem code with no LLM knowledge | New |
| `src/chat_agent/tools.py` | Tool definitions (JSON schemas, including `web_search`); `run_client_tool(name, input, kb)` validates input and maps domain errors to `is_error` tool results | New |
| `src/chat_agent/llm.py` | `LLMClient` protocol plus `AnthropicLLM` adapter: builds the request (model, tools, system prompt, caching, fallbacks), streams, and turns SDK events into domain events | New |
| `src/chat_agent/agent.py` | `Agent.run_turn(conversation, user_text) -> AsyncIterator[AgentEvent]`: the agent loop, tool budget, `pause_turn` resume, source collection, error mapping, rollback on failure | New |
| `src/chat_agent/events.py` | Domain event dataclasses: `TextDelta`, `ToolActivity`, `Sources`, `ErrorEvent`, `Done` | New |
| `src/chat_agent/conversations.py` | `ConversationStore`: id → message list plus an `asyncio.Lock` (rejects concurrent turns); `new()`, `get()` | New |
| `src/chat_agent/web.py` | `create_app(agent, store)`: `GET /` (page), static files, `POST /api/conversations` (new id), `POST /api/chat` (SSE stream) | New |
| `src/chat_agent/__main__.py` | Startup: load `.env`, check API key (AC-23), create `knowledge/` (AC-22), run uvicorn on `127.0.0.1` (AC-2) | New |
| `src/chat_agent/prompts.py` | System prompt: role, tool usage, cite sources, say when search fails, mention truncation, answer in Markdown | New |
| `src/chat_agent/static/index.html`, `app.js`, `style.css` | Chat UI: message list, input, send, "New chat", activity lines, sources list, streaming render, input lock | New |
| `src/chat_agent/static/vendor/marked.umd.js`, `purify.min.js` | Vendored Markdown renderer and sanitizer (pinned versions; licenses kept) | New |
| `tests/…`, `tests/manual/ui_checklist.md` | Unit and API tests; manual UI checklist (see Test strategy) | New |
| `.gitignore` | Add `knowledge/` (spec: private contents), `.env` (already present) | Changed |
| `.env.example` | `ANTHROPIC_API_KEY=` placeholder | New |

## Interfaces & data structures

```python
# knowledge.py
class AccessDenied(Exception): ...
class NotFound(Exception): ...
class NotText(Exception): ...

@dataclass(frozen=True)
class Entry: path: str; is_dir: bool            # path relative to root, POSIX style

@dataclass(frozen=True)
class FileContent: path: str; text: str; truncated: bool

class KnowledgeBase:
    def __init__(self, root: Path) -> None
    def list_dir(self, path: str = "") -> list[Entry]         # names only (AC-15)
    def read_text(self, path: str) -> FileContent             # ≤ MAX_READ_BYTES (AC-16/17/18)

# events.py  — what the agent yields and the web layer serializes to SSE
TextDelta(text: str)
ToolActivity(kind: Literal["web_search", "list_files", "read_file"], detail: str)
Sources(items: list[Source])          # Source(url: str, title: str | None), de-duplicated, first-seen order
ErrorEvent(message: str)              # user-readable, never contains the API key
Done()

# llm.py
class LLMClient(Protocol):
    def stream(self, messages: list[MessageParam], *, max_web_searches: int,
               tools_enabled: bool) -> AsyncContextManager[LLMStream]
class LLMStream(Protocol):
    def __aiter__(self) -> AsyncIterator[TextDelta | ToolActivity]   # web_search activity comes from server_tool_use
    async def final_message(self) -> Message                          # SDK Message (content, stop_reason)

# agent.py
class Agent:
    def __init__(self, llm: LLMClient, kb: KnowledgeBase, max_tool_calls: int = 10) -> None
    async def run_turn(self, history: list[MessageParam], user_text: str) -> AsyncIterator[AgentEvent]
```

**Agent loop (per user message):**

```
append user message; budget = 10
loop:
  stream request (max_uses = budget, tool_choice none if budget == 0) → forward TextDelta / ToolActivity
  msg = final message; append msg.content (verbatim) as assistant turn
  budget -= count(server_tool_use blocks in msg)
  match msg.stop_reason:
    "pause_turn"  → continue (server resumes; at most 5 consecutive continuations)
    "refusal"     → ErrorEvent("The model declined…"); stop
    "max_tokens"  → if a tool_use is present: ErrorEvent; stop    (never run truncated tool input)
    "tool_use"    → run up to `budget` client tools (emit ToolActivity), is_error for the rest;
                    budget -= ran; append all tool_results in ONE user message; continue
    else          → stop
emit Sources (citations of type web_search_result_location on text blocks), then Done
on any SDK error → roll the conversation back to before this user message, emit ErrorEvent, Done
```

**HTTP API**

- `POST /api/conversations` → `{"id": "<uuid4>"}`
- `POST /api/chat` body `{"conversation_id": str, "message": str}` → `text/event-stream` with events
  `text`, `activity`, `sources`, `error`, `done` (each `data:` is JSON).
  - `400` for an empty or whitespace-only message (AC-8, also guarded in the UI)
  - `404` for an unknown conversation id
  - `409` if a turn is already running for that conversation (AC-7, also guarded in the UI)

**Error mapping (AC-24):** `AuthenticationError` → "API key is invalid…"; `RateLimitError` → "Rate limited, try again
in a moment"; `APIConnectionError` → "Could not reach the Claude API"; `APIStatusError` (other) → "Claude API error
(status N)"; unexpected exception → generic message plus server-side log. The SDK's built-in retries (2, on
429/5xx/connection errors) stay on.

**Request settings:** `model="claude-sonnet-5-5"` (user's choice: enough for this project, half Opus's price at
$2 / $10 per MTok), `max_tokens=64000` (streaming), `output_config={"effort": "medium"}` (Sonnet 5.5 defaults to
`high`; `medium` is the recommended start for multi-step tool use), thinking left at its default (adaptive), top-level `cache_control={"type": "ephemeral"}`
(the system prompt and tools stay byte-stable, so multi-step turns hit the cache),
`betas=["server-side-fallback-2026-07-01"]` with `fallbacks="default"` (if Sonnet 5.5's safety classifier declines, the
API reruns the request on a suitable fallback model instead of failing; the `"default"` form is the one Sonnet 5.5
supports on the Claude API). Client tools set
`eager_input_streaming: true` (SDK guidance for streaming), so inputs are validated in `tools.py` and an unparseable
input (`ValueError` from the stream) is retried once.

## Dependencies

| Package | Why | Kind |
|---|---|---|
| `anthropic` | Official SDK: streaming, typed errors, web search server tool | runtime |
| `fastapi` | HTTP routes, request validation, streaming responses | runtime |
| `uvicorn` | ASGI server, bound to `127.0.0.1` | runtime |
| `python-dotenv` | Load `ANTHROPIC_API_KEY` from a git-ignored `.env` | runtime |
| `pytest`, `pytest-asyncio` | Tests (async agent loop) | dev |
| `httpx` | `ASGITransport` client for API tests | dev |
| `ruff`, `pyright` | Lint/format, type check (per `CLAUDE.md`) | dev |
| `marked`, `DOMPurify` (vendored JS) | Markdown rendering plus HTML sanitizing in the browser | static asset |

Environment: `ANTHROPIC_API_KEY` (required). External services: Claude API only; web search is billed by Anthropic
per search, capped by the 10-call budget.

## Test strategy

The agent and API tests use a **scripted fake `LLMClient`**, which replays predefined messages, stop reasons, and
citations. Tests are deterministic and never call the real API. One optional **live smoke test** (marker `live`,
skipped unless `ANTHROPIC_API_KEY` is set and `-m live` is given) exercises the real `AnthropicLLM` adapter and web
search end to end.

**No automated browser tests** (user decision: skip them). Browser-side behavior (rendering, button states, links) is
checked with a **manual UI checklist**, `tests/manual/ui_checklist.md`, which has one numbered step per UI AC with
the exact prompt to type and the expected result. It is run against the real app before `/verify`, and the results
are recorded in the checklist. Every UI AC also has the strongest automated check that can run without a browser
(API status codes, SSE event content, served HTML containing the required controls). `app.js` is kept small and
logic-free (it renders the events it receives), so little can go wrong there unseen.

| AC | Test type | Test location | Notes |
|---|---|---|---|
| AC-1 | api + manual | `tests/test_web.py`, `tests/manual/ui_checklist.md` | `GET /` serves HTML with input, send button, "New chat" button (by id); manual: page looks and works right |
| AC-2 | unit + integration | `tests/test_main.py` | uvicorn is configured with host `127.0.0.1`; the started server is not reachable on the machine's LAN IP |
| AC-3 | api + manual | `tests/test_web.py`, checklist | SSE emits several `text` events before `done`; manual: user message shown, then reply grows progressively |
| AC-4 | unit | `tests/test_agent.py` | Second turn's request contains the first turn's messages |
| AC-5 | api + manual | `tests/test_web.py`, checklist | New conversation id has empty history and the old id's history isn't used; manual: UI clears messages |
| AC-6 | manual | checklist | After reload, page is empty and the assistant has no memory of the earlier exchange |
| AC-7 | api + manual | `tests/test_web.py`, checklist | Concurrent POST for same conversation → 409; manual: send disabled while streaming, re-enabled after reply/error |
| AC-8 | api + manual | `tests/test_web.py`, checklist | Empty / whitespace message → 400; manual: pressing send on blank input does nothing |
| AC-9 | unit + api + manual | `tests/test_agent.py`, `tests/test_web.py`, checklist | `ToolActivity` events in call order with query/path, serialized as SSE `activity`; manual: lines shown in order |
| AC-10 | unit | `tests/test_agent.py` | Fake script: list → read → search → answer; all executed, final text returned |
| AC-11 | unit | `tests/test_agent.py` | 10 calls run, 11th gets `is_error`; next request has `tool_choice none`; `max_uses` shrinks as budget is spent |
| AC-12 | unit + live | `tests/test_llm.py`, `tests/test_agent.py`, `tests/live/test_live.py` | Request includes `web_search_20260209`; server-tool results flow into the answer; live: current-events question triggers a search |
| AC-13 | unit + api + manual | `tests/test_agent.py`, `tests/test_web.py`, checklist | Citations become de-duplicated `Sources` and an SSE `sources` event; manual: shown as clickable links |
| AC-14 | unit | `tests/test_agent.py`, `tests/test_llm.py` | `web_search_tool_result` with error content doesn't raise; turn completes; system prompt instructs to report failure |
| AC-15 | unit | `tests/test_knowledge.py` | Nested listing returns relative names with dir flag only; tool output contains no sizes |
| AC-16 | unit | `tests/test_knowledge.py` | Read `.md`/`.py`/`.csv`/`.json` in nested folder → full text |
| AC-17 | unit | `tests/test_knowledge.py` | 150 KB file → first 102 400 bytes (no split UTF-8 char), `truncated=True`, note in tool result |
| AC-18 | unit | `tests/test_knowledge.py` | PNG bytes / invalid UTF-8 / NUL bytes → `NotText` → `is_error` result |
| AC-19 | unit | `tests/test_knowledge.py` | Missing file and dir → `NotFound` → `is_error` result |
| AC-20 | unit | `tests/test_knowledge.py` | Parametrized: `../x`, `a/../../x`, `/etc/passwd`, `~/x`, symlinked file → outside, symlinked dir → outside, listing hides escaping symlinks; error message leaks no outside names |
| AC-21 | unit | `tests/test_tools.py` | Tool set is exactly `{web_search, list_files, read_file}`; `KnowledgeBase` exposes no write methods; unknown tool name → `is_error` |
| AC-22 | unit | `tests/test_main.py` | Startup with missing `knowledge/` creates it empty |
| AC-23 | unit | `tests/test_main.py` | No `ANTHROPIC_API_KEY` → exits non-zero with message naming the variable and `.env.example` |
| AC-24 | unit + api + manual | `tests/test_agent.py`, `tests/test_web.py`, checklist | Each SDK error type → readable `ErrorEvent`, history rolled back; next message succeeds; manual: error shown (invalid key), input usable again |
| AC-25 | api + manual | `tests/test_web.py`, checklist | Served page loads vendored `purify.min.js` and `marked.umd.js`; manual: heading/list/table/code render formatted; a reply quoting `<script>alert(1)</script>` and `<img src=x onerror=alert(1)>` shows no alert; user message shown literally |

Every test name starts with its AC ID (e.g. `test_ac20_symlink_escape_is_denied`).

## Risks & mitigations

- **Path-sandbox escape** (the highest-impact risk): one resolution-based check, applied in a single place
  (`KnowledgeBase._resolve`), plus an exhaustive parametrized test suite (AC-20). Tool errors never echo resolved
  absolute paths.
- **Prompt injection from web pages or files** (a page tells the model to do something else): the model's only
  capabilities are reading `./knowledge` and searching. It can't write, run code, or reach other paths, and rendered
  output is sanitized (AC-25). We accept the remaining risk that it *repeats* misleading content.
- **Cost overrun:** 10-tool-call budget per message (AC-11), prompt caching, `effort: medium`, and SDK retries capped
  at 2.
- **SDK/API drift** (new beta names, event shapes): all SDK coupling sits in `llm.py`, and the live smoke test catches
  drift.
- **Streaming broken by an error mid-reply:** the agent catches errors around the whole turn, emits `error` then
  `done`, and rolls back history, so the conversation is never left half-written (AC-24).
- **Front-end regressions with no browser tests:** `app.js` stays thin, and the manual checklist is rerun before
  `/verify` and after any change to `static/`.
