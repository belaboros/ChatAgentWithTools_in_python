# Chat Agent: your own AI chat assistant

Chat Agent is a small program you run on your own computer. You open it in your web browser and type questions in
everyday language, the way you would write a message to a knowledgeable friend. It writes back an answer.

It can do three things:

- **Answer from general knowledge.** Explain a topic, help you write or rephrase a text, summarize, brainstorm, etc.
- **Search the internet** for current information, and show you the web pages it used.
- **Read your own documents** that you put in one specific folder, and answer questions about them.

This guide assumes you have never used an AI assistant before.

---

## Contents

1. [What is an AI chat assistant?](#1-what-is-an-ai-chat-assistant)
2. [Where do the answers come from?](#2-where-do-the-answers-come-from)
3. [What you need](#3-what-you-need)
4. [Installation (one time)](#4-installation-one-time)
5. [Starting and stopping the app](#5-starting-and-stopping-the-app)
6. [Using the chat](#6-using-the-chat)
7. [Letting the assistant read your documents](#7-letting-the-assistant-read-your-documents)
8. [Privacy: what leaves your computer](#8-privacy-what-leaves-your-computer)
9. [Costs](#9-costs)
10. [Limits and mistakes: what to watch out for](#10-limits-and-mistakes-what-to-watch-out-for)
11. [Tips for good questions](#11-tips-for-good-questions)
12. [Troubleshooting](#12-troubleshooting)
13. [For developers](#13-for-developers)

---

## 1. What is an AI chat assistant?

An AI chat assistant is a computer program that understands written language and writes answers in natural
language. The "brain" behind this app is **Claude**, an AI model made by the company Anthropic. (A "model" is the
trained program that produces the answers.)

Claude learned by reading a very large amount of text: books, websites, articles, and code. From that it learned
how language works and picked up a lot of general knowledge. When you ask a question, it doesn't look the answer
up in a database. It **writes** a new answer, word by word, based on what it learned.

Two consequences matter for you:

- It can write fluent, helpful answers on almost any topic, in many languages.
- It can also be **wrong while sounding confident**. Treat it like a well-read assistant, not like an encyclopedia.
  For anything important (health, money, law, safety), check the answer.

This app gives Claude two extra abilities, called **tools**: searching the web and reading files in your
`knowledge` folder. Claude decides by itself when a tool is useful, and the app shows you every time it uses one.

---

## 2. Where do the answers come from?

Every answer comes from one, or a mix, of **three sources**. The chat window shows you which ones were used.

### Source 1: Claude's own trained knowledge

**When:** general questions, explanations, writing help, ideas. For example *"Explain how a mortgage works"* or
*"Help me write a polite email declining an invitation."*

**How you recognize it:** the answer appears with **no activity lines** above it and **no "Sources" list** under it.

**Keep in mind:**
- This knowledge has a **cut-off date**. Claude was trained at a certain point in time and doesn't automatically know
  about later events, prices, versions, or news.
- It can't name an exact source for this kind of knowledge, and it occasionally gets details wrong (names, numbers,
  dates, quotes). Verify important facts.

### Source 2: The internet (web search)

**When:** questions about current or changing things, such as news, recent releases, opening hours, prices,
"what is the latest…". You can also ask directly: *"Search the web for …"*.

**How you recognize it:**
- While it works, a line like **🔎 Searching the web: latest Python version** appears in the conversation.
- Under the answer, a **Sources** list shows the web pages it relied on, as clickable links. Links open in a new
  browser tab, so your conversation stays open.

**Keep in mind:**
- The search itself runs on Anthropic's servers, not in your browser.
- Web pages can be outdated, biased, or wrong, and Claude can misread them. **Click the sources** to check anything
  important.
- If a search fails or finds nothing useful, the assistant is instructed to say so rather than guess.

### Source 3: Your own documents (the `knowledge` folder)

**When:** questions about your notes and files. For example *"What's on my todo list?"* or *"Summarize my notes
from the project meeting."*

**How you recognize it:** activity lines such as:
- **📂 Listing files in: (top level)**: it looks at which files exist.
- **📄 Reading file: notes/todo.md**: it reads a specific file.

**Keep in mind:**
- It can only see files **inside the `knowledge` folder** of this project. It can't open, change, create, or delete
  any file, there or anywhere else on your computer.
- It reads text files only (see [section 7](#7-letting-the-assistant-read-your-documents)).
- Very large files (over 100 KB, roughly 50 pages of plain text) are only read **partially**. The assistant is told
  this and should mention it when it matters.

### Mixed answers

One answer can combine sources. For example, it might read your project notes, search the web for a current price,
and then use its general knowledge to explain the result. Every file read and every web search used appears as an
activity line, in the order it happened.

### Quick reference

| What you see in the chat | Where the answer came from |
|---|---|
| Just the answer, nothing else | Claude's trained knowledge (may be outdated; no sources) |
| 🔎 *Searching the web: …* and a **Sources** list | Web pages found by the search (click to check) |
| 📂 *Listing files in: …* / 📄 *Reading file: …* | Your files in the `knowledge` folder |
| A red message | Something went wrong (see [Troubleshooting](#12-troubleshooting)) |

---

## 3. What you need

- A computer running **macOS**, **Linux**, or **Windows**.
- An internet connection.
- A modern web browser (Chrome, Firefox, Safari, or Edge).
- An **Anthropic API key**, a personal password-like code that lets the app use Claude. Getting one requires an
  account with Anthropic and a payment method, because each question costs a small amount (see
  [Costs](#9-costs)).
- About 10 minutes for the one-time installation. You'll type a few commands into the **Terminal**, a window where
  you type commands instead of clicking.
  - macOS: open *Applications → Utilities → Terminal*.
  - Windows: open *PowerShell* from the Start menu.
  - Linux: open your *Terminal* application.

---

## 4. Installation (one time)

### Step 1: Get an API key

1. Go to the Anthropic Console at <https://console.anthropic.com> and create an account.
2. Add a payment method and some credit under *Billing*.
3. Open *API Keys* and create a new key. It starts with `sk-ant-…`.
4. Copy it somewhere safe for the next step. **Treat it like a password**: anyone who has it can use Claude at your
   expense. Never share it or post it online.

### Step 2: Install `uv`

`uv` is a free helper that installs everything else this app needs (including the right version of Python, the
programming language the app is written in).

- **macOS / Linux**: paste this into the Terminal and press Enter:
  ```sh
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ```
- **Windows** (PowerShell):
  ```powershell
  powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
  ```

Close the Terminal window and open a new one afterwards.

### Step 3: Get the app and install it

Put this project folder on your computer (download or clone it), then in the Terminal go into that folder and
install:

```sh
cd path/to/ChatAgentWithTools_in_python
uv sync
```

(Replace `path/to/` with where the folder actually is. On macOS you can type `cd `, with a space, and then drag the
folder into the Terminal window.)

### Step 4: Store your API key

Make a copy of the example settings file named `.env`:

```sh
cp .env.example .env
```

(On Windows PowerShell: `Copy-Item .env.example .env`.)

Open `.env` in a text editor and put your key after the `=` sign:

```
ANTHROPIC_API_KEY=sk-ant-your-key-here
```

Save the file. `.env` stays on your computer, and the project is set up so it is never shared or uploaded to code
repositories.

---

## 5. Starting and stopping the app

**Start** (in the Terminal, inside the project folder):

```sh
uv run chat-agent
```

You'll see a line like `Chat agent running at http://127.0.0.1:8000`. Leave this Terminal window open while you use
the app.

**Open** <http://127.0.0.1:8000> in your web browser.

The app is only reachable from **your own computer** (`127.0.0.1` means "this computer"). Other people on your
network can't open it.

**Stop**: go back to the Terminal window and press **Ctrl + C**.

---

## 6. Using the chat

- **Ask something:** type in the box at the bottom and press **Enter** (or click **Send**). For a line break without
  sending, press **Shift + Enter**.
- **Watch the answer appear:** the reply is written word by word as it is generated. While it is being written,
  you can't send another message.
- **Follow-up questions:** the assistant remembers what was said earlier **in the same conversation**, so you can
  ask *"Can you make that shorter?"* or *"Why?"*.
- **Start over:** click **New chat**. The assistant then forgets the previous conversation. Reloading the page
  also starts a new, empty conversation.
- **Formatting:** answers can contain headings, lists, tables, and code, shown nicely formatted. For safety, images
  in answers are never shown or loaded (see [Privacy](#8-privacy-what-leaves-your-computer)).

**Conversations are not saved.** When you click *New chat*, reload the page, or stop the app, the conversation is
gone. Copy anything you want to keep.

**Up to 10 tools per question:** for each message, the assistant can do at most 10 web searches and file reads in
total. If it needs more, it answers with what it found so far and tells you it hit the limit. You can then ask a
narrower follow-up question.

---

## 7. Letting the assistant read your documents

The first time the app starts, it creates a folder called **`knowledge`** inside the project folder. Put the
documents you want the assistant to be able to read there. Subfolders are fine.

**What it can read:** plain-text files, such as `.txt`, `.md` (Markdown notes), `.csv` (simple spreadsheets
exported as text), `.json`, and source code files.

**What it can't read:** Word documents (`.docx`), PDFs, Excel files (`.xlsx`), images, and other non-text formats.
Tip: save or export such documents as plain text (`.txt`) first, e.g. in Word use *File → Save As → Plain Text*.

**Good to know:**
- You don't need to tell it file names. Just ask, e.g. *"Do I have any notes about the garden?"*, and it will look.
  Mentioning the folder or file helps, though.
- Changes you make to files are seen immediately. There's no need to restart.
- The assistant has **read-only** access to this one folder. It can't change your files or see anything else on
  your computer.
- Don't put files there that you wouldn't want sent to Anthropic (see the next section). And don't create *hard
  links* in `knowledge/` that point to private files elsewhere: they look like ordinary files and would be readable.

---

## 8. Privacy: what leaves your computer

The app runs on your computer, but the AI does not. To produce an answer, the app sends data over the internet to
**Anthropic's servers**:

- **Sent to Anthropic:** your messages, the conversation so far, the contents of any of your files the assistant
  decides to read, and web search requests (searches are performed by Anthropic on your behalf).
- **Stays on your computer:** your API key file (`.env`), files in `knowledge/` that the assistant doesn't read,
  and everything else on your computer.
- **Not stored by this app:** conversations exist only in memory while the app runs.

For how Anthropic handles data sent through its API, see Anthropic's privacy policy and commercial terms on
<https://www.anthropic.com>.

**Protection against tricky content:** web pages and documents can contain hidden instructions meant to trick an
AI ("prompt injection"). This app limits what such tricks can achieve:
- The assistant can only read files, never write them.
- Answers can't run code or load images or other content from the internet in your browser.
- The app refuses requests from other websites.

Even so, read answers that are based on unknown web pages with healthy skepticism.

---

## 9. Costs

The app itself is free, but Anthropic charges for using Claude through your API key:

- **Text:** you pay per amount of text processed, both what is sent (your messages, the conversation so far, file
  contents) and what Claude writes back. A short question and answer typically costs a fraction of a cent to a few
  cents.
- **Web searches:** each search has a small additional fee.
- **Things that cost more:** long conversations (the whole conversation is sent again with each message), reading
  large files, and many searches. Starting a **New chat** for a new topic keeps costs down.

The 10-tool limit per message caps the cost of a single question. You can see your actual spending, and set spending
limits, in the Anthropic Console under *Billing* / *Usage*. Current prices are on <https://www.anthropic.com/pricing>.

---

## 10. Limits and mistakes: what to watch out for

- **It can be wrong.** AI assistants sometimes state incorrect facts confidently or make up details (this is called
  "hallucination"). The risk is highest for answers *without* sources: specific numbers, quotes, names, or recent
  events.
- **It's not a professional.** Don't rely on it alone for medical, legal, financial, or safety decisions.
- **Its general knowledge has a cut-off date.** For anything current, ask it to search the web.
- **Web sources vary in quality.** Check the linked pages for important facts.
- **Large files are read partially** (first 100 KB), and only text files can be read.
- **No memory between conversations.** Each new chat starts from zero.
- **It may misunderstand you.** If an answer misses the point, rephrase or add details. That's normal and expected.

---

## 11. Tips for good questions

- **Be specific.** *"Suggest three vegetarian dinner recipes under 30 minutes"* works better than *"dinner ideas"*.
- **Give context.** Say who it's for and why: *"Explain inflation to a 12-year-old."*
- **Say what format you want.** *"As a table"*, *"in 5 bullet points"*, *"in German"*, *"max. 100 words"*.
- **Ask for sources.** *"Search the web and give me sources"* for anything current or factual.
- **Point to your files.** *"Using my notes in the knowledge folder, …"*
- **Iterate.** Follow up: *"Shorter, please"*, *"Explain step 2 in more detail"*, *"Are you sure? Please check."*

---

## 12. Troubleshooting

| Problem | What to do |
|---|---|
| Terminal says `ANTHROPIC_API_KEY is not set` | Create the `.env` file with your key (see [Step 4](#step-4-store-your-api-key)) and start again. |
| Chat says *"The Anthropic API key was rejected"* | The key in `.env` is wrong or was deleted. Create a new key in the Console, update `.env`, restart the app. |
| Chat says *"rate-limiting"* | Too many requests in a short time, or your credit is used up. Wait a minute; check *Billing* in the Console. |
| Chat says *"Could not reach the Claude API"* | Check your internet connection and try again. |
| The browser says the page can't be reached | The app isn't running. Start it with `uv run chat-agent` and keep that Terminal window open. |
| Terminal says the address/port is already in use | The app is probably already running in another Terminal window. Use that one, or stop it with Ctrl + C. |
| *"knowledge … exists but is not a folder"* | There's a *file* named `knowledge` in the project folder. Rename or move it, then start again. |
| It says it can't read a file | Only text files can be read (see [section 7](#7-letting-the-assistant-read-your-documents)), and only inside `knowledge/`. |
| The page looks broken after an update | Reload with **Cmd + Shift + R** (macOS) or **Ctrl + Shift + R** (Windows/Linux). |

---

## 13. For developers

This project is built with spec-driven development. The workflow and coding rules are in [CLAUDE.md](CLAUDE.md), and
the feature specification, technical plan, and task list are in
[specs/001-web-chat-with-search-and-files/](specs/001-web-chat-with-search-and-files/).

- Stack: Python 3.14, uv, FastAPI/uvicorn, Anthropic Python SDK (Claude Sonnet 5.5 with server-side web search),
  plain HTML/JS front end with vendored `marked` and `DOMPurify`.
- Source: `src/chat_agent/` (`agent.py` agent loop, `knowledge.py` sandboxed file access, `llm.py` Claude API
  adapter, `web.py` HTTP/SSE API, `static/` chat page).

```sh
uv run pytest                     # unit + API tests (no network, no API cost)
uv run pytest -m live             # end-to-end against the real Claude API (needs a key; costs a little)
uv run ruff check --fix . && uv run ruff format .
uv run pyright
```

The browser UI is checked manually with [tests/manual/ui_checklist.md](tests/manual/ui_checklist.md).
