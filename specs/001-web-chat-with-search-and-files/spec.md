# 001 — Web chat with web search and local files

- **Status:** In progress
- **Created:** 2026-10-03
- **Depends on:** none

## Summary

A small chat assistant powered by Claude (Anthropic API), used from a local web page. It can search the web,
and it can list and read text files inside a single fixed folder (`./knowledge`), to answer the user's questions.

## Problem / motivation

The user wants an assistant that can combine current information from the web with their own local notes and
documents, without copying file contents into the chat by hand. It must never be able to see files outside the
folder the user deliberately put there.

## User stories

- As the user, I want to chat with an assistant in my browser so that I get a comfortable, readable conversation.
- As the user, I want the assistant to search the web when it needs current information, and to show me its sources,
  so that I can check its claims.
- As the user, I want the assistant to find and read files in my `./knowledge` folder so that it can answer questions
  about my own documents.
- As the user, I want to see what the assistant is doing (searching, reading a file) so that I understand where an
  answer comes from.
- As the user, I want to be certain the assistant cannot read anything outside `./knowledge`.

## Acceptance criteria

### Chat & web UI

- **AC-1** — *Given* the app is started, *when* I open its address in a browser on the same machine, *then* I see a
  chat page with a message input, a send control, and a "New chat" button.
- **AC-2** — *Given* the app is running, *when* another device on the network tries to connect to it, *then* the
  connection is not accepted (the app listens on localhost only).
- **AC-3** — *Given* the chat page is open, *when* I send a message, *then* my message appears in the conversation and
  the assistant's reply appears below it, streamed in progressively as it is generated.
- **AC-25** — *Given* the assistant's reply contains Markdown (headings, lists, emphasis, links, tables, code blocks),
  *when* it is displayed, *then* it is rendered as formatted Markdown, not shown as raw Markdown syntax. My own messages
  are shown as plain text. Rendering must not execute any HTML or scripts contained in a reply.
- **AC-4** — *Given* an ongoing conversation, *when* I send a follow-up message, *then* the assistant's reply takes the
  earlier messages of this conversation into account.
- **AC-5** — *Given* an ongoing conversation, *when* I click "New chat", *then* the conversation is cleared and the
  next message starts a conversation with no memory of the previous one.
- **AC-6** — *Given* an ongoing conversation, *when* I reload the page, *then* a fresh, empty conversation starts.
- **AC-7** — *Given* the assistant is still replying, *when* I look at the input, *then* I cannot send another message
  until the reply has finished (or failed).
- **AC-8** — *Given* I submit an empty or whitespace-only message, *when* I press send, *then* nothing is sent.

### Tool activity

- **AC-9** — *Given* the assistant uses a tool while answering, *when* the tool is invoked, *then* the conversation
  shows a short activity line describing it (e.g. "Searching the web: *query*", "Reading file: *notes/todo.md*",
  "Listing files in: *notes/*"), in the order the tool calls happen.
- **AC-10** — *Given* a single user message, *when* the assistant needs several tool calls to answer it, *then* it can
  make several in a row (e.g. list files, then read one, then search the web) before giving its final answer.
- **AC-11** — *Given* a single user message, *when* the assistant has made 10 tool calls without finishing, *then* it
  stops calling tools and gives the best answer it can, saying it hit the limit.

### Web search

- **AC-12** — *Given* a question that needs current or external information, *when* the assistant answers it, *then* it
  searches the web and uses the results in its answer.
- **AC-13** — *Given* an answer that uses web search results, *when* it is displayed, *then* it lists the source URLs it
  relied on, as clickable links.
- **AC-14** — *Given* a web search fails (e.g. network error or no results), *when* the assistant answers, *then* it
  tells me the search did not work rather than inventing results, and the chat stays usable.

### Local files (`./knowledge`)

- **AC-15** — *Given* files exist in `./knowledge` and its subfolders, *when* the assistant lists a folder, *then* it
  sees only the names of the files and subfolders in it (no sizes or other metadata), as paths relative to
  `./knowledge`, with subfolders distinguishable from files.
- **AC-16** — *Given* a text file (e.g. `.txt`, `.md`, `.py`, `.csv`, `.json`) inside `./knowledge` or any of its
  subfolders, *when* the assistant reads it, *then* it receives the file's full text content.
- **AC-17** — *Given* a text file larger than 100 KB, *when* the assistant reads it, *then* it receives the first
  100 KB of text together with a clear note that the file was truncated, and it mentions this to me if relevant.
- **AC-18** — *Given* a binary or non-text file (e.g. an image, PDF, or archive), *when* the assistant tries to read it,
  *then* it receives an error saying the file is not a readable text file, and it tells me so.
- **AC-19** — *Given* a path that does not exist inside `./knowledge`, *when* the assistant tries to read or list it,
  *then* it receives a "not found" error and the chat continues normally.
- **AC-20** — *Given* any path pointing outside `./knowledge` — including `..` segments, absolute paths, `~`, or a
  symbolic link inside `./knowledge` that points outside it — *when* the assistant tries to read or list it, *then* the
  request is refused with an "access denied" error, and no content or file names from outside the folder are revealed.
- **AC-21** — *Given* the assistant is running, *when* it uses its file abilities, *then* it can only list and read; it
  has no way to create, modify, move, or delete any file.
- **AC-22** — *Given* the `./knowledge` folder does not exist at startup, *when* the app starts, *then* it creates the
  folder empty and starts normally.

### Errors & configuration

- **AC-23** — *Given* no Anthropic API key is configured, *when* I start the app, *then* it exits immediately with a
  clear message explaining how to set the key.
- **AC-24** — *Given* the Anthropic API returns an error or is unreachable during a reply (e.g. invalid key, rate
  limit, network failure), *when* this happens, *then* the chat shows a readable error message, and I can send
  another message or start a new chat without restarting the app.

## Non-goals

- Terminal / CLI chat interface (possible later spec reusing the same assistant).
- Access from other devices, public deployment, user accounts, or authentication.
- Saving conversations across page reloads or app restarts; multiple conversations or a chat history sidebar.
- Writing, editing, moving, or deleting files.
- Reading PDFs, Office documents, images, or other non-text formats.
- Choosing a different readable folder (at startup or during the chat).
- Supporting LLM providers other than Claude.
- Stopping or cancelling a reply while it is generating.
- File uploads through the web UI.

## Constraints & assumptions

- **Security:** File access is strictly sandboxed to `./knowledge` (resolved relative to the project root). This is
  the most important constraint of the feature and must be covered by tests for every escape route listed in AC-20.
- **Secrets:** The Anthropic API key comes from the environment (or a local, git-ignored `.env` file) and is never
  shown in the UI, logs, or committed to git.
- **Privacy:** The contents of `./knowledge` are personal and must not be committed to git.
- **Cost:** At most 10 tool calls per user message (AC-11) to keep API and search costs bounded.
- **Platform:** Runs locally on macOS with Python 3.14; a recent desktop browser (Chrome, Firefox, Safari).
- **Assumption:** "Text file" means a file that decodes as UTF-8 text; anything else is treated as non-text (AC-18).
- **Assumption:** A single user uses a single browser tab at a time; simultaneous use from several tabs is not a
  supported scenario.

## Open questions

- [x] ~~100 KB file read limit?~~ — Confirmed (AC-17).
- [x] ~~Tool-call limit~~ — 10 tool calls per message confirmed (AC-11).
- [x] ~~Markdown or plain text?~~ — Replies are rendered as Markdown (AC-25).
- [x] ~~Show file sizes in listings?~~ — Names only (AC-15).

## Changelog

- 2026-10-03 — Created.
- 2026-10-03 — Confirmed 10 tool-call limit; added AC-25 (Markdown rendering); AC-15 clarified to names only.
- 2026-10-03 — Confirmed 100 KB file read limit; all open questions resolved.
- 2026-10-03 — Approved.
- 2026-10-03 — Plan approved (Claude Sonnet 5.5; UI ACs verified by manual checklist instead of browser tests).
