console.log("SCRIPT LOADED ✔");

// ===== DOM ELEMENTS =====
const sessionList = document.getElementById("session-list");
const newChatBtn = document.getElementById("new-chat-btn");
const messagesDiv = document.getElementById("messages");
const inputField = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const typingIndicator = document.getElementById("typing-indicator");
const titleEl = document.getElementById("active-session-title");

// Backend base URL
const API_BASE = "http://localhost:8000";

let activeSessionId = localStorage.getItem("activeSessionId") || null;

// ===== INIT =====
window.addEventListener("load", async () => {
  await loadSessions();

  if (activeSessionId) {
    await loadChatHistory(activeSessionId);
  } else {
    await createNewSession();
  }
});

// ===== MARKDOWN RENDERING =====
function renderMarkdown(text) {
  if (!text) return "";

  // Configure marked
  marked.setOptions({
    breaks: true,
    gfm: true,
    highlight: function (code, lang) {
      try {
        if (lang && hljs.getLanguage(lang)) {
          return hljs.highlight(code, { language: lang }).value;
        }
      } catch (e) {
        console.error("Highlight error:", e);
      }
      return hljs.highlightAuto(code).value;
    }
  });

  const rawHtml = marked.parse(text);
  const cleanHtml = DOMPurify.sanitize(rawHtml);
  return cleanHtml;
}

// ===== SCROLL HELPERS =====
function scrollToBottom() {
  messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

// ===== MESSAGE RENDERING =====
function appendMessage(role, content, isStreaming = false, existingDiv = null) {
  let msgDiv = existingDiv;

  if (!msgDiv) {
    msgDiv = document.createElement("div");
    msgDiv.className = `message ${role}-message`;
    messagesDiv.appendChild(msgDiv);
  }

  if (role === "bot") {
    msgDiv.innerHTML = renderMarkdown(content || "");
    // Re-highlight code blocks
    msgDiv.querySelectorAll("pre code").forEach(block => {
      hljs.highlightElement(block);
    });
  } else {
    msgDiv.textContent = content;
  }

  if (!isStreaming) {
    scrollToBottom();
  }

  return msgDiv;
}

// ===== SESSIONS =====
async function createNewSession() {
  const newId = "session-" + Date.now();

  try {
    await fetch(`${API_BASE}/session/new`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: newId })
    });

    activeSessionId = newId;
    localStorage.setItem("activeSessionId", activeSessionId);

    messagesDiv.innerHTML = "";
    titleEl.textContent = "New Chat";

    await loadSessions();
    highlightActiveSession();
  } catch (err) {
    console.error("Create session error:", err);
  }
}

async function loadSessions() {
  try {
    const res = await fetch(`${API_BASE}/sessions`);
    const data = await res.json();
    const sessions = data.sessions || [];

    sessionList.innerHTML = "";

    sessions.forEach(session => {
      createSidebarItem(session);
    });

    highlightActiveSession();
  } catch (err) {
    console.error("Load sessions error:", err);
  }
}

function createSidebarItem(session) {
  const item = document.createElement("div");
  item.className = "session-item";
  item.dataset.sessionId = session.session_id;

  const title = session.session_name || "New Chat";

  item.innerHTML = `
    <span class="session-title" title="${title}">${title}</span>
    <div class="dots-menu">⋮</div>
    <div class="dropdown-menu">
      <div class="dropdown-item rename-option">Rename</div>
      <div class="dropdown-item delete-option delete-option">Delete</div>
    </div>
  `;

  // Click to switch session
  item.addEventListener("click", () => {
    switchSession(session.session_id);
  });

  const dots = item.querySelector(".dots-menu");
  const dropdown = item.querySelector(".dropdown-menu");

  dots.addEventListener("click", e => {
    e.stopPropagation();
    closeAllDropdowns();
    dropdown.style.display = "block";
  });

  // Rename
  item.querySelector(".rename-option").addEventListener("click", e => {
    e.stopPropagation();
    dropdown.style.display = "none";
    startInlineRename(item, session.session_id);
  });

  // Delete
  item.querySelector(".delete-option").addEventListener("click", async e => {
    e.stopPropagation();
    dropdown.style.display = "none";
    await deleteSession(session.session_id);
  });

  sessionList.appendChild(item);
}

// Close dropdowns when clicking outside
document.addEventListener("click", () => {
  closeAllDropdowns();
});

function closeAllDropdowns() {
  document.querySelectorAll(".dropdown-menu").forEach(menu => {
    menu.style.display = "none";
  });
}

function highlightActiveSession() {
  const items = document.querySelectorAll(".session-item");
  let title = "New Chat";

  items.forEach(item => {
    if (item.dataset.sessionId === activeSessionId) {
      item.classList.add("active");
      const span = item.querySelector(".session-title");
      if (span) title = span.textContent;
    } else {
      item.classList.remove("active");
    }
  });

  titleEl.textContent = title;
}

async function switchSession(id) {
  if (!id || id === activeSessionId) return;

  activeSessionId = id;
  localStorage.setItem("activeSessionId", activeSessionId);

  messagesDiv.innerHTML = "";
  highlightActiveSession();
  await loadChatHistory(id);
}

// ===== HISTORY =====
async function loadChatHistory(sessionId) {
  try {
    const res = await fetch(`${API_BASE}/history/${sessionId}`);
    const data = await res.json();

    messagesDiv.innerHTML = "";

    (data.messages || []).forEach(msg => {
      appendMessage(msg.role === "assistant" ? "bot" : "user", msg.content);
    });

    scrollToBottom();
  } catch (err) {
    console.error("Load history error:", err);
  }
}

// ===== INLINE RENAME =====
function startInlineRename(item, id) {
  const span = item.querySelector(".session-title");
  const oldName = span.textContent;

  const input = document.createElement("input");
  input.className = "session-title-input";
  input.value = oldName;

  input.addEventListener("click", e => e.stopPropagation());

  item.replaceChild(input, span);
  input.focus();
  input.select();

  const save = async () => {
    const newName = input.value.trim();
    if (!newName || newName === oldName) {
      cancel();
      return;
    }

    try {
      await fetch(`${API_BASE}/session/${id}/rename`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ new_name: newName })
      });

      await loadSessions();
      highlightActiveSession();
    } catch (err) {
      console.error("Rename error:", err);
      cancel();
    }
  };

  const cancel = () => {
    item.replaceChild(span, input);
  };

  input.addEventListener("keydown", e => {
    if (e.key === "Enter") save();
    if (e.key === "Escape") cancel();
  });

  input.addEventListener("blur", save);
}

// ===== DELETE SESSION =====
async function deleteSession(id) {
  try {
    await fetch(`${API_BASE}/session/${id}`, {
      method: "DELETE"
    });

    if (id === activeSessionId) {
      await createNewSession();
    } else {
      await loadSessions();
      highlightActiveSession();
    }
  } catch (err) {
    console.error("Delete session error:", err);
  }
}

// ===== INPUT HANDLING =====
function autoResizeTextarea() {
  inputField.style.height = "auto";
  inputField.style.height = inputField.scrollHeight + "px";
}

inputField.addEventListener("input", autoResizeTextarea);

// Enter to send, Shift+Enter new line
inputField.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

sendBtn.addEventListener("click", sendMessage);

// ===== SEND MESSAGE (STREAMING) =====
async function sendMessage() {
  const text = inputField.value.trim();
  if (!text || !activeSessionId) return;

  // add user message
  appendMessage("user", text);
  inputField.value = "";
  autoResizeTextarea();

  typingIndicator.style.display = "flex";
  scrollToBottom();

  // Create an empty bot message div for streaming
  let botDiv = appendMessage("bot", "", true);

  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text,
        session_id: activeSessionId
      })
    });

    if (!res.body) {
      console.error("Streaming not supported");
      const data = await res.text();
      botDiv = appendMessage("bot", data);
      typingIndicator.style.display = "none";
      await loadSessions();
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    let botText = "";

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      botText += chunk;

      appendMessage("bot", botText, true, botDiv);
      scrollToBottom();
    }

    typingIndicator.style.display = "none";
    appendMessage("bot", botText, false, botDiv);

    // Refresh sessions list to update preview/title
    await loadSessions();
  } catch (err) {
    console.error("Chat error:", err);
    typingIndicator.style.display = "none";
  }
}

// ===== NEW CHAT BUTTON =====
newChatBtn.addEventListener("click", async () => {
  await createNewSession();
});
