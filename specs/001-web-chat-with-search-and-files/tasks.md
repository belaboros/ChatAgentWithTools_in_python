# 001 — Web chat with web search and local files: Tasks

- **Spec:** [spec.md](spec.md) · **Plan:** [plan.md](plan.md)

Each task is small, independently testable, and done test-first. Check a box only when its tests pass
and lint/type checks are clean.

### Foundation

- [x] **T1** — Project scaffolding: `pyproject.toml` (Python ≥ 3.14, `src/chat_agent` package, `chat-agent` script),
  runtime and dev deps via `uv add`, ruff/pyright/pytest config (`asyncio_mode = "auto"`, markers `live`), empty
  package modules, `.env.example`, add `knowledge/` to `.gitignore`. *(no AC — enables all)*
  - Test: `tests/test_smoke.py::test_package_imports`; `uv run pytest`, `ruff`, `pyright` all green.
- [x] **T2** — `config.py` constants and startup checks: `require_api_key()` exits with a clear message when
  `ANTHROPIC_API_KEY` is unset or empty; `ensure_knowledge_dir()` creates `knowledge/` if missing. *(AC-22, AC-23)*
  - Test: `tests/test_main.py::test_ac23_missing_api_key_exits_with_message`,
    `::test_ac22_missing_knowledge_dir_is_created`.

### Sandboxed knowledge folder

- [x] **T3** — `KnowledgeBase._resolve(path)`: the single path-sandbox check (reject absolute and `~`; resolve, then
  `is_relative_to(root)`); `AccessDenied` messages don't leak resolved paths. *(AC-20)*
  - Test: `tests/test_knowledge.py::test_ac20_*` — parametrized `../x`, `a/../../x`, `/etc/passwd`, `~/x`,
    symlinked file → outside, symlinked dir → outside; error message contains no outside path.
- [x] **T4** — `KnowledgeBase.list_dir(path="")`: names only, relative POSIX paths, dir flag, sorted; hides entries
  whose resolved target escapes the root; `NotFound` for missing dirs. *(AC-15, AC-19, AC-20)*
  - Test: `test_ac15_lists_nested_names_only`, `test_ac19_list_missing_dir_not_found`,
    `test_ac20_listing_hides_escaping_symlinks`.
- [x] **T5** — `KnowledgeBase.read_text(path)`: UTF-8 text in nested folders; first 102 400 bytes with
  `truncated=True` for larger files (no split multi-byte character); `NotText` for binary / NUL / invalid UTF-8;
  `NotFound` for missing files or directories. *(AC-16, AC-17, AC-18, AC-19)*
  - Test: `test_ac16_reads_text_files_in_subfolders`, `test_ac17_large_file_truncated_at_100kb`,
    `test_ac17_truncation_does_not_split_utf8_char`, `test_ac18_binary_file_not_text`, `test_ac19_read_missing_not_found`.

### Tools & agent

- [x] **T6** — `tools.py`: tool definitions (`web_search_20260209` with `max_uses`, `list_files`, `read_file` with
  `eager_input_streaming`); `run_client_tool()` validates input, formats results (listing names with a trailing `/` for
  dirs; truncation note), maps `AccessDenied`/`NotFound`/`NotText`/invalid input/unknown tool to `is_error` results.
  *(AC-15, AC-17, AC-18, AC-19, AC-21)*
  - Test: `tests/test_tools.py::test_ac21_tool_set_is_read_only`, `::test_ac21_unknown_tool_is_error`,
    `::test_ac17_result_includes_truncation_note`, `::test_ac18_not_text_is_error_result`, `::test_invalid_input_is_error_result`.
- [x] **T7** — `events.py` domain events, `LLMClient`/`LLMStream` protocols in `llm.py`, and a scripted
  `FakeLLM` in `tests/fakes.py` that replays SDK-shaped `Message`s and records requests. *(no AC — test seam)*
  - Test: `tests/test_fakes.py::test_fake_llm_replays_script_and_records_requests`.
- [x] **T8** — `Agent.run_turn`, basic path: append user message, stream `TextDelta`s, append assistant content
  verbatim, stop on `end_turn`, emit `Done`; history carries over between turns. *(AC-3, AC-4)*
  - Test: `tests/test_agent.py::test_ac3_streams_text_deltas_then_done`, `::test_ac4_second_turn_includes_history`.
- [x] **T9** — Client-tool loop: on `tool_use`, emit `ToolActivity` (in call order), run tools, return all
  `tool_result`s in one user message, continue until the model finishes. *(AC-9, AC-10)*
  - Test: `test_ac9_tool_activity_events_in_order`, `test_ac10_list_then_read_then_answer`,
    `test_parallel_tool_results_in_single_message`.
- [x] **T10** — Tool budget of 10 per user message across client and server tools: `max_web_searches` passed as the
  remaining budget, extra `tool_use`s beyond the limit get `is_error`, next request has tools disabled. *(AC-11)*
  - Test: `test_ac11_eleventh_call_rejected_and_tools_disabled`, `test_ac11_web_searches_count_against_budget`,
    `test_ac11_budget_resets_per_user_message`.
- [x] **T11** — Web search handling in the agent: `ToolActivity("web_search", query)` from `server_tool_use`; resume
  on `pause_turn` (max 5 consecutive); `web_search_tool_result` errors don't raise; collect
  `web_search_result_location` citations into a de-duplicated `Sources` event before `Done`.
  *(AC-9, AC-12, AC-13, AC-14)*
  - Test: `test_ac12_server_search_results_flow_into_answer`, `test_ac12_pause_turn_is_resumed`,
    `test_ac13_citations_become_deduplicated_sources`, `test_ac14_search_error_result_does_not_break_turn`.
- [x] **T12** — Failure handling: `refusal`, `max_tokens` with a pending `tool_use`, and each SDK error type
  (`AuthenticationError`, `RateLimitError`, `APIConnectionError`, `APIStatusError`, unexpected) → readable
  `ErrorEvent` then `Done`; history rolled back to before the user message. *(AC-24)*
  - Test: `test_ac24_sdk_errors_map_to_readable_messages` (parametrized), `test_ac24_history_rolled_back_on_error`,
    `test_ac24_next_turn_succeeds_after_error`, `test_refusal_reports_error`, `test_truncated_tool_input_not_executed`.
- [x] **T13** — `prompts.py` system prompt: role; use `list_files`/`read_file` for `./knowledge` questions and web
  search for current information; cite sources; say plainly when a search fails or a file was truncated; answer in
  Markdown. Byte-stable (no timestamps). *(AC-12, AC-13, AC-14, AC-17)*
  - Test: `tests/test_prompts.py::test_system_prompt_covers_required_behaviors`, `::test_system_prompt_is_stable`.
- [x] **T14** — `AnthropicLLM` adapter: builds the request (`claude-sonnet-5-5`, `max_tokens=64000`, effort `medium`,
  system prompt, tools with `max_uses`, `tool_choice none` when disabled, top-level `cache_control`,
  `server-side-fallback-2026-07-01` + `fallbacks="default"`); turns SDK stream events into domain events; retries
  once on unparseable eager tool input. Tested against a mocked HTTP transport (recorded SSE). *(AC-11, AC-12, AC-14)*
  - Test: `tests/test_llm.py::test_ac12_request_includes_web_search_tool`, `::test_ac11_tools_disabled_sets_tool_choice_none`,
    `::test_ac11_max_uses_set_from_budget`, `::test_stream_events_translated`, `::test_ac14_search_error_block_passed_through`.

### Web app

- [x] **T15** — `ConversationStore`: `new()` → uuid4 with empty history; `get()`; per-conversation lock that rejects
  a second concurrent turn. *(AC-5, AC-7)*
  - Test: `tests/test_conversations.py::test_ac5_new_conversation_is_empty`, `::test_ac7_concurrent_turn_rejected`.
- [x] **T16** — `web.py` API: `POST /api/conversations`; `POST /api/chat` streaming SSE (`text`, `activity`,
  `sources`, `error`, `done`); 400 on blank message, 404 unknown id, 409 when busy. *(AC-3, AC-5, AC-7, AC-8, AC-9,
  AC-13, AC-24)*
  - Test: `tests/test_web.py::test_ac3_chat_streams_sse_text_then_done`, `::test_ac5_new_conversation_has_no_memory`,
    `::test_ac7_concurrent_chat_returns_409`, `::test_ac8_blank_message_returns_400`, `::test_unknown_conversation_404`,
    `::test_ac9_activity_events_serialized`, `::test_ac13_sources_event_serialized`, `::test_ac24_error_event_then_done`.
- [x] **T17** — Front end: `index.html`, `style.css`, `app.js` (new conversation on load and on "New chat"; send
  disabled while streaming and for blank input; render user text literally; stream reply; Markdown via `marked` +
  `DOMPurify.sanitize`; activity lines; sources as links; error display), vendored `marked.umd.js` and `purify.min.js`
  with licenses. *(AC-1, AC-3, AC-5, AC-6, AC-7, AC-8, AC-9, AC-13, AC-24, AC-25)*
  - Test: `tests/test_web.py::test_ac1_page_has_chat_controls`, `::test_ac25_page_loads_sanitizer_and_markdown`;
    browser behavior → manual checklist (T20).
- [x] **T18** — `__main__.py` wiring: load `.env`, run startup checks, build `AnthropicLLM` + `Agent` + store + app,
  run uvicorn on `127.0.0.1:8000`; `chat-agent` script. *(AC-2)*
  - Test: `tests/test_main.py::test_ac2_server_binds_localhost_only`, `::test_ac2_not_reachable_on_lan_ip`
    (skipped if the machine has no non-loopback IPv4).

### Verification support

- [ ] **T19** — Live smoke test (marker `live`, skipped without `ANTHROPIC_API_KEY`): a current-events question
  triggers a web search, and the answer has sources; a question about a temp `knowledge/` file reads it. *(AC-12, AC-13, AC-16)*
  - Test: `tests/live/test_live.py` — run with `uv run pytest -m live`.
- [x] **T20** — `tests/manual/ui_checklist.md` (one step per UI AC: exact input, expected result, pass/fail column)
  and `README.md` (setup, `.env`, running, tests, the knowledge folder). *(AC-1, AC-3, AC-5, AC-6, AC-7, AC-8, AC-9,
  AC-13, AC-24, AC-25)*
  - Test: checklist executed against the running app during `/verify`; results recorded in the file.

## AC coverage

| AC | Tasks | | AC | Tasks |
|---|---|---|---|---|
| AC-1 | T17, T20 | | AC-14 | T11, T13, T14 |
| AC-2 | T18 | | AC-15 | T4, T6 |
| AC-3 | T8, T16, T17, T20 | | AC-16 | T5, T19 |
| AC-4 | T8 | | AC-17 | T5, T6, T13 |
| AC-5 | T15, T16, T17, T20 | | AC-18 | T5, T6 |
| AC-6 | T17, T20 | | AC-19 | T4, T5, T6 |
| AC-7 | T15, T16, T17, T20 | | AC-20 | T3, T4 |
| AC-8 | T16, T17, T20 | | AC-21 | T6 |
| AC-9 | T9, T11, T16, T17, T20 | | AC-22 | T2 |
| AC-10 | T9 | | AC-23 | T2 |
| AC-11 | T10, T14 | | AC-24 | T12, T16, T17, T20 |
| AC-12 | T11, T13, T14, T19 | | AC-25 | T17, T20 |
| AC-13 | T11, T13, T16, T17, T19, T20 | | | |

All 25 ACs are covered; no gaps.

## Notes

Anything discovered during implementation (deviations must be reflected back into spec/plan first).

- **T17:** marked 18 no longer ships `marked.min.js`; vendored its browser build `lib/marked.umd.js` (v18.0.14) and
  DOMPurify `dist/purify.min.js` (v3.4.16), with license files. Plan updated to the new filename.
- **T15:** `ConversationStore` keeps at most 100 conversations (oldest dropped). Every reload creates one, so this
  keeps memory bounded. It's an implementation detail with no visible behavior change.
- **T12:** besides SDK errors, a `refusal`, a `max_tokens` cut-off with a pending tool call, and more than 5 `pause_turn`
  continuations also roll the turn back, so the conversation history is always valid.
- **T14:** SDK 1.x uses `httpx2`; the adapter tests mock the API with `httpx2.MockTransport` (`httpx2` added as a
  dev dependency). The unparseable-tool-input retry only fires if no text has been shown yet, so text is never
  duplicated.
- **T16:** the 409 check happens before streaming starts; a second guard inside the stream covers the (single-user,
  UI-prevented) race between two simultaneous requests.
- **T19:** live tests are written but **not yet run**: no `ANTHROPIC_API_KEY` was available during implementation.
  Run `uv run pytest -m live` during `/verify`.
- **Open trade-off (T10/T14):** `web_search.max_uses` follows the remaining tool budget, as the plan says, which is
  what makes AC-11 strict. But tools are the first part of the cached prompt prefix, so a changed `max_uses`
  invalidates the prompt cache for the next request within the same message. Correctness (AC-11) wins for now;
  revisit if costs matter.
