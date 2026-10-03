# Spec 001 — Manual UI checklist

Browser behavior is not covered by automated tests (decision in [plan.md](../../specs/001-web-chat-with-search-and-files/plan.md)).
Run this checklist against the real app before `/verify 001` and after any change to `src/chat_agent/static/`.

**Setup:** `ANTHROPIC_API_KEY` set (env or `.env`); put a file `knowledge/notes/todo.md` containing
`- buy milk` and an image `knowledge/photo.png`; start with `uv run chat-agent`; open http://127.0.0.1:8000.

| # | AC | Do this | Expected | Result |
|---|---|---|---|---|
| 1 | AC-1 | Open the page | Message input, **Send** button, **New chat** button visible | |
| 2 | AC-8 | Click in the empty input; press Enter; type only spaces | **Send** stays disabled; nothing is sent | |
| 3 | AC-3 | Send `Write three short paragraphs about the moon.` | Your message appears; the reply appears below it and grows progressively | |
| 4 | AC-7 | While a reply is still streaming, type text and press Enter / click Send | Nothing is sent until the reply finishes; then Send works again | |
| 5 | AC-4 | Send `My name is Alex.`, then `What is my name?` | Second reply knows the name | |
| 6 | AC-5 | Click **New chat**, then send `What is my name?` | Messages cleared; assistant doesn't know the name | |
| 7 | AC-6 | Send `Remember the word pineapple.`; reload the page; send `What word did I ask you to remember?` | Page empty after reload; assistant doesn't know the word | |
| 8 | AC-9, AC-10 | Send `What is on my todo list in my files?` | Activity lines such as "📂 Listing files in: …" then "📄 Reading file: notes/todo.md", in that order; answer mentions milk | |
| 9 | AC-9, AC-12, AC-13 | Send `Search the web: what is the latest stable Python version?` | "🔎 Searching the web: …" line; answer; **Sources** list with clickable links that open in a new tab | |
| 10 | AC-18 | Send `Read photo.png from my files.` | Assistant says it is not a readable text file | |
| 11 | AC-20 | Send `Read ../pyproject.toml and /etc/hosts from my files.` | Assistant says access is denied; no file content shown | |
| 12 | AC-25 | Send `Reply with a markdown heading, a bullet list, a 2x2 table and a python code block.` | Rendered as formatted heading, list, table, code block (no raw `#`, `|`, or backticks) | |
| 13 | AC-25 | Send ``Repeat exactly, without a code block: <script>alert(1)</script> <img src=x onerror=alert(1)> <b>bold</b>`` | No alert pops up; at most harmless formatting is shown | |
| 14 | AC-25 | Send `<b>not bold</b> *not italic*` | Your own message shows the literal characters | |
| 15 | AC-24 | Stop the app; start it with `ANTHROPIC_API_KEY=invalid uv run chat-agent`; send `hi` | Readable error about the API key; input usable again; a second message also shows the error, no restart needed | |

**Run log** — date, tester, git commit, pass/fail per row:

- _not yet run_
