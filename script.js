console.log("SCRIPT LOADED ✔");

const sessionList = document.getElementById("session-list");
const newChatBtn = document.getElementById("new-chat-btn");
const messagesDiv = document.getElementById("messages");
const inputField = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const typingIndicator = document.getElementById("typing-indicator");
const titleEl = document.getElementById("active-session-title");

let sessionId = localStorage.getItem("sessionId");

/* ----------------------- INITIAL LOAD ----------------------- */
window.onload = async () => {
    if (!sessionId) {
        await createNewSession();
    } else {
        await loadSessions();
        await loadChatHistory(sessionId);
    }
};

/* ----------------------- CREATE NEW SESSION ----------------------- */
async function createNewSession() {
    sessionId = "session-" + Date.now();
    localStorage.setItem("sessionId", sessionId);

    await fetch(`http://localhost:8000/session/${sessionId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId })
    });

    messagesDiv.innerHTML = "";
    addMessage("bot", "Hello! I'm your AI assistant. How can I help you today?");

    await loadSessions();
    highlightActiveSession();
}

/* ----------------------- LOAD SESSIONS ----------------------- */
async function loadSessions() {
    const res = await fetch("http://localhost:8000/sessions");
    const data = await res.json();

    sessionList.innerHTML = "";
    (data.sessions || []).forEach(s => createSidebarItem(s));

    highlightActiveSession();
}

/* ----------------------- SIDEBAR ITEM ----------------------- */
function createSidebarItem(s) {
    const item = document.createElement("div");
    item.className = "session-item";
    item.dataset.sessionId = s.session_id;

    const title = s.session_name || s.preview || "New Chat";

    item.innerHTML = `
        <span class="session-title">${title}</span>
        <div class="dots-menu">⋮</div>

        <div class="dropdown-menu">
            <div class="dropdown-item rename-option">Rename</div>
            <div class="dropdown-item delete-option">Delete</div>
        </div>
    `;

    item.onclick = () => switchSession(s.session_id);

    const dots = item.querySelector(".dots-menu");
    const dropdown = item.querySelector(".dropdown-menu");

    dots.onclick = (e) => {
        e.stopPropagation();
        closeAllDropdowns();
        dropdown.style.display = "block";
    };

    item.querySelector(".rename-option").onclick = () => {
        dropdown.style.display = "none";
        startInlineRename(item, s.session_id);
    };

    item.querySelector(".delete-option").onclick = async () => {
        dropdown.style.display = "none";
        await deleteSession(s.session_id);
    };

    sessionList.appendChild(item);
}

/* ----------------------- CLOSE MENUS ----------------------- */
document.addEventListener("click", () => closeAllDropdowns());
function closeAllDropdowns() {
    document.querySelectorAll(".dropdown-menu").forEach(menu => {
        menu.style.display = "none";
    });
}

/* ----------------------- HIGHLIGHT ACTIVE ----------------------- */
function highlightActiveSession() {
    const items = document.querySelectorAll(".session-item");
    let title = "Chat";

    items.forEach(item => {
        if (item.dataset.sessionId === sessionId) {
            item.classList.add("active");
            title = item.querySelector(".session-title").textContent;
        } else {
            item.classList.remove("active");
        }
    });

    titleEl.textContent = title;
}

/* ----------------------- SWITCH SESSION ----------------------- */
async function switchSession(id) {
    console.log("Switching to:", id);

    sessionId = id;
    localStorage.setItem("sessionId", sessionId);

    messagesDiv.innerHTML = ""; // instant clear (ChatGPT behavior)
    highlightActiveSession();
    await loadChatHistory(id);
}

/* ----------------------- LOAD HISTORY ----------------------- */
async function loadChatHistory(id) {
    const res = await fetch(`http://localhost:8000/history/${id}`);
    const data = await res.json();

    messagesDiv.innerHTML = "";
    (data.messages || []).forEach(m => addMessage(m.role, m.content));
}

/* ----------------------- INLINE RENAME ----------------------- */
function startInlineRename(item, id) {
    const span = item.querySelector(".session-title");
    const oldName = span.textContent;

    const input = document.createElement("input");
    input.className = "session-title-input";
    input.value = oldName;

    item.replaceChild(input, span);
    input.focus();

    const save = async () => {
        const newName = input.value.trim();
        if (!newName) return cancel();

        await fetch(`http://localhost:8000/session/${id}/rename`, {
            method: "PUT",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ new_name: newName })
        });

        await loadSessions();
    };

    const cancel = () => {
        item.replaceChild(span, input);
    };

    input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") save();
        if (e.key === "Escape") cancel();
    });

    input.addEventListener("blur", save);
}

/* ----------------------- DELETE SESSION ----------------------- */
async function deleteSession(id) {
    await fetch(`http://localhost:8000/session/${id}`, {
        method: "DELETE",
    });

    // if user deletes the active chat → create a new one
    if (id === sessionId) {
        await createNewSession();
    }

    await loadSessions();
    highlightActiveSession();
}

/* ----------------------- ADD MESSAGE ----------------------- */
function addMessage(role, text) {
    const div = document.createElement("div");
    div.className = `message ${role}-message`;
    div.innerHTML = text;

    messagesDiv.appendChild(div);
    messagesDiv.scrollTop = messagesDiv.scrollHeight;
}

/* ----------------------- SEND MESSAGE ----------------------- */
sendBtn.onclick = sendMessage;
inputField.onkeypress = (e) => {
    if (e.key === "Enter") sendMessage();
};

async function sendMessage() {
    const text = inputField.value.trim();
    if (!text) return;

    addMessage("user", text);
    inputField.value = "";
    typingIndicator.style.display = "block";

    const res = await fetch("http://localhost:8000/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            text,
            session_id: sessionId,
            conversation_history: [],
            expertise_level: "beginner"
        })
    });

    const data = await res.json();
    typingIndicator.style.display = "none";

    addMessage("bot", data.response);

    await loadSessions();
}

/* ----------------------- NEW CHAT BUTTON ----------------------- */
newChatBtn.addEventListener("click", async () => {
    await createNewSession();
});
