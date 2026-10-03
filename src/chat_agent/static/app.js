// Chat page: renders the server's SSE events. Keep this thin — logic lives in Python.
"use strict";

const messages = document.getElementById("messages");
const input = document.getElementById("message-input");
const sendButton = document.getElementById("send-button");
const newChatButton = document.getElementById("new-chat-button");
const composer = document.getElementById("composer");

const ACTIVITY_LABELS = {
  web_search: "🔎 Searching the web:",
  list_files: "📂 Listing files in:",
  read_file: "📄 Reading file:",
};

let conversationId = null;
let busy = false;
let controller = null;

function updateSendButton() {
  // AC-7: no sending while a reply is in progress. AC-8: no sending blank messages.
  sendButton.disabled = busy || conversationId === null || input.value.trim() === "";
}

function scrollToBottom() {
  messages.scrollTop = messages.scrollHeight;
}

function addElement(parent, tag, className, text) {
  const element = document.createElement(tag);
  element.className = className;
  if (text !== undefined) element.textContent = text; // textContent: never parsed as HTML
  parent.appendChild(element);
  return element;
}

async function newConversation() {
  // AC-5 / AC-6: every page load and every "New chat" starts an empty conversation.
  if (controller) controller.abort();
  conversationId = null;
  messages.replaceChildren();
  updateSendButton();
  try {
    const response = await fetch("/api/conversations", { method: "POST" });
    conversationId = (await response.json()).id;
  } catch {
    addElement(messages, "div", "error", "Could not start a conversation. Is the app running?");
  }
  updateSendButton();
  input.focus();
}

// One assistant reply: a sequence of Markdown text segments, activity lines, sources, errors.
function createReply() {
  const container = addElement(messages, "div", "message assistant");
  let segment = null;
  let markdown = "";

  return {
    text(delta) {
      if (segment === null) {
        segment = addElement(container, "div", "markdown");
        markdown = "";
      }
      markdown += delta;
      // AC-25: render Markdown, and sanitize so no HTML or script in a reply can run.
      segment.innerHTML = DOMPurify.sanitize(marked.parse(markdown));
    },
    activity({ kind, detail }) {
      const label = ACTIVITY_LABELS[kind] || "Using tool:";
      addElement(container, "div", "activity", `${label} ${detail}`);
      segment = null; // text after a tool call starts a new segment, keeping the order (AC-9)
    },
    sources({ items }) {
      const block = addElement(container, "div", "sources");
      addElement(block, "div", "sources-title", "Sources");
      const list = addElement(block, "ol", "");
      for (const { url, title } of items) {
        if (!/^https?:\/\//i.test(url)) continue;
        const link = addElement(addElement(list, "li", ""), "a", "", title || url);
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
      }
      segment = null;
    },
    error({ message }) {
      addElement(container, "div", "error", message);
      segment = null;
    },
  };
}

async function readEvents(response, reply) {
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    buffer += decoder.decode(value, { stream: true });
    let boundary;
    while ((boundary = buffer.indexOf("\n\n")) !== -1) {
      const chunk = buffer.slice(0, boundary);
      buffer = buffer.slice(boundary + 2);
      const fields = Object.fromEntries(
        chunk.split("\n").map((line) => [line.slice(0, line.indexOf(": ")), line.slice(line.indexOf(": ") + 2)]),
      );
      const data = JSON.parse(fields.data);
      if (fields.event === "done") return;
      if (fields.event in reply) reply[fields.event](data);
      scrollToBottom();
    }
  }
}

async function send() {
  const text = input.value;
  if (busy || conversationId === null || text.trim() === "") return;
  busy = true;
  input.value = "";
  updateSendButton();
  addElement(messages, "div", "message user", text); // AC-25: user text shown literally
  const reply = createReply();
  scrollToBottom();
  controller = new AbortController();
  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ conversation_id: conversationId, message: text }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => ({}));
      reply.error({ message: body.detail || `Request failed (${response.status}).` });
    } else {
      await readEvents(response, reply);
    }
  } catch (error) {
    if (error.name !== "AbortError") reply.error({ message: "Lost connection to the app." });
  } finally {
    controller = null;
    busy = false;
    updateSendButton();
    scrollToBottom();
  }
}

composer.addEventListener("submit", (event) => {
  event.preventDefault();
  send();
});
input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    send();
  }
});
input.addEventListener("input", updateSendButton);
newChatButton.addEventListener("click", newConversation);

newConversation();
